"""Exact reuse must preserve selection, requirements, assets and provenance."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import cadquery as cq
from crate_studio import workspace_agent as wa, workspace_cache as gc
from tests.test_workspace_agent import base, plan, response


class ExactReuseTests(unittest.TestCase):
    def test_saved_revision_snapshot_is_exact_copied_and_asset_bound(self):
        from crate_studio import workspace_server as ws

        class LockGuard:
            blocked = False

            def __enter__(self):
                if self.blocked:
                    raise AssertionError(
                        "Warm saved revisions must not enter the CAD lock"
                    )

            def __exit__(self, *args):
                return False

        lock = LockGuard()
        ws._revision_snapshot.cache_clear()
        document = ws.normalize_document(
            {
                "name": "Revision cache control",
                "features": [
                    {
                        "id": "box",
                        "type": "box",
                        "params": {"width": 10, "depth": 20, "height": 30},
                    }
                ],
            }
        )
        with patch.object(ws, "snapshot", wraps=ws.snapshot) as native:
            first = ws.revision_snapshot(document, "cad-cache-control", lock)
            first["document"]["name"] = "Mutated caller"
            lock.blocked = True
            second = ws.revision_snapshot(document, "cad-cache-control", lock)
            self.assertNotEqual(second["document"]["name"], "Mutated caller")
            self.assertEqual(native.call_count, 1)
            lock.blocked = False
            document["metadata"]["drawing_layout"] = "legacy-v1"
            ws.revision_snapshot(document, "cad-cache-control", lock)
            self.assertEqual(native.call_count, 2)
        self.assertEqual(ws._revision_snapshot.cache_info().hits, 1)
        with tempfile.TemporaryDirectory(dir="output") as folder:
            asset = Path(folder) / "shape.step"
            document = ws.normalize_document(
                {
                    "name": "Asset cache control",
                    "features": [
                        {
                            "id": "import",
                            "type": "import_step",
                            "params": {"asset_id": "unchanged-id"},
                        }
                    ],
                }
            )
            sizes = []
            with (
                patch.object(ws, "asset_path", return_value=asset),
                patch.object(ws, "snapshot", wraps=ws.snapshot) as native,
            ):
                for width in (8, 12):
                    cq.exporters.export(cq.Workplane("XY").box(width, 4, 2), str(asset))
                    sizes.append(
                        ws.revision_snapshot(document, "cad-asset-control", lock)[
                            "metrics"
                        ]["size_mm"][0]
                    )
                self.assertEqual(native.call_count, 2)
            self.assertEqual(sizes, [8.0, 12.0])

    def test_bootstrap_loads_requested_document_once_and_metadata_skips_geometry(self):
        from crate_studio import workspace_server as ws
        from fastapi import HTTPException

        routes = {
            r.path: r.endpoint for r in ws.create_router(threading.RLock()).routes
        }
        bootstrap = routes["/api/studio/bootstrap"]
        target = {"id": "requested", "geometry": "retained snapshot"}
        with (
            patch.object(
                ws,
                "current_document",
                side_effect=AssertionError("Unrelated default must not load"),
            ),
            patch.object(ws, "read_document", return_value=target) as read,
            patch.object(ws, "list_documents", return_value=[]),
            patch.object(wa.agent, "configured", return_value=True),
        ):
            self.assertEqual(bootstrap(document_id="requested")["document"], target)
            read.assert_called_once()
            self.assertIsNone(bootstrap(include_document=False)["document"])
            self.assertEqual(read.call_count, 1)
            read.side_effect = HTTPException(404, "Missing requested revision")
            with self.assertRaises(HTTPException):
                bootstrap(document_id="missing")

    def test_imported_drawing_cache_tracks_actual_asset_bytes(self):
        from crate_studio import workspace_server as ws

        with tempfile.TemporaryDirectory(dir="output") as root:
            asset = Path(root) / "asset.step"
            doc = ws.normalize_document(
                {
                    "name": "Asset revision",
                    "features": [
                        {
                            "id": "import",
                            "type": "import_step",
                            "params": {"asset_id": "unchanged-id"},
                        }
                    ],
                }
            )
            ws.projected.cache_clear()
            legacy_key = json.dumps(
                {k: doc[k] for k in ("features", "name", "annotations")}, sort_keys=True
            )
            with patch.object(ws, "asset_path", return_value=asset):
                cq.exporters.export(cq.Workplane("XY").box(10, 8, 2), str(asset))
                old_key = ws.drawing_key(doc)
                self.assertIn("W 10", ws.projected(legacy_key))
                cq.exporters.export(cq.Workplane("XY").box(20, 8, 2), str(asset))
                self.assertNotEqual(ws.drawing_key(doc), old_key)
                value = ws.snapshot(doc, threading.RLock())
                self.assertEqual(value["metrics"]["size_mm"][0], 20)
                self.assertIn("W 20", value["drawing_svg"])
                # Control: omitting content identity really does preserve the
                # stale projection despite the native imported body changing.
                self.assertIn("W 10", ws.projected(legacy_key))

    def setUp(self):
        gc.cache_clear()

    def test_geometry_reused_across_ai_and_studio_and_invalidated(self):
        from crate_studio.workspace_server import built, build_key, DEFAULT_DOCUMENT

        doc = deepcopy(DEFAULT_DOCUMENT)
        built.cache_clear()
        a = gc.cached_build(doc)
        before = gc.cache_info()
        b = built(build_key(doc))
        self.assertIs(a, b)
        self.assertGreater(gc.cache_info().hits, before.hits)
        changed = deepcopy(doc)
        changed["features"][0]["params"]["height"] += 1
        self.assertNotEqual(gc.cached_build(changed)["metrics"], a["metrics"])

    def test_import_file_bytes_invalidate_even_same_asset_id(self):
        with tempfile.TemporaryDirectory(dir="output") as directory:
            path = Path(directory) / "asset.step"
            doc = {
                "features": [
                    {
                        "id": "import",
                        "type": "import_step",
                        "params": {"asset_id": "same"},
                    }
                ]
            }
            cq.exporters.export(cq.Workplane("XY").box(10, 10, 10), str(path))
            a = gc.cached_build(doc, lambda _: path)["metrics"]["volume_mm3"]
            cq.exporters.export(cq.Workplane("XY").box(20, 10, 10), str(path))
            b = gc.cached_build(doc, lambda _: path)["metrics"]["volume_mm3"]
            self.assertAlmostEqual(b, 2 * a)

    def test_exact_proposal_cache_and_all_key_dependencies(self):
        p = plan([{"action": "update", "id": "box", "params": {"height": 40}}])
        with (
            tempfile.TemporaryDirectory(dir="output") as directory,
            patch.object(wa, "RUNS", Path(directory)),
            patch.object(wa, "load_env"),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline-only"}),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.object(wa, "request", return_value=response(p)) as transport,
        ):
            a = wa.propose_document(base(), "make it 40 mm tall", run_id="a")
            b = wa.propose_document(base(), "make it 40 mm tall", run_id="b")
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(a["document"], b["document"])
            self.assertEqual(b["calls"], 0)
            self.assertEqual(b["estimated_cost_usd"], 0)
            self.assertEqual(b["response_ids"], [])
            self.assertEqual(b["cache"]["source_response_ids"], a["response_ids"])
            variants = [
                ({**base(), "metadata": {"brief": "Different intent"}}, {}),
                (
                    base(),
                    {"selection_context": {"topology_ids": ["body_001:face_0001"]}},
                ),
                (base(), {"reasoning_effort": "low"}),
                (base(), {"context_mode": "compact"}),
                (base(), {"use_cache": False}),
            ]
            for i, (doc, options) in enumerate(variants):
                result = wa.propose_document(
                    doc, "make it 40 mm tall", run_id=f"variant{i}", **options
                )
                self.assertFalse(result["cache"]["hit"])
            self.assertEqual(transport.call_count, 6)

    def test_concurrent_identical_generation_is_one_transport(self):
        started, release = threading.Event(), threading.Event()

        def reply(*args, **kwargs):
            started.set()
            self.assertTrue(release.wait(3))
            return response(
                plan([{"action": "update", "id": "box", "params": {"height": 40}}])
            )

        with (
            tempfile.TemporaryDirectory(dir="output") as directory,
            patch.object(wa, "RUNS", Path(directory)),
            patch.object(wa, "load_env"),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline-only"}),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.object(wa, "request", side_effect=reply) as transport,
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            a = pool.submit(
                wa.propose_document, base(), "make it 40 mm tall", run_id="a"
            )
            self.assertTrue(started.wait(3))
            b = pool.submit(
                wa.propose_document, base(), "make it 40 mm tall", run_id="b"
            )
            release.set()
            results = [a.result(), b.result()]
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(sorted(x["calls"] for x in results), [0, 1])

    def test_provider_cached_tokens_are_accounted_without_releasing_reservation(self):
        reply = response(
            plan([{"action": "update", "id": "box", "params": {"height": 40}}])
        )
        reply[0]["usage"]["prompt_tokens_details"] = {"cached_tokens": 80}
        with (
            tempfile.TemporaryDirectory(dir="output") as directory,
            patch.object(wa, "RUNS", Path(directory)),
            patch.object(wa, "load_env"),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline-only"}),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.object(wa, "request", return_value=reply),
        ):
            result = wa.propose_document(
                base(), "make it 40 mm tall", run_id="cached-provider"
            )
            self.assertAlmostEqual(
                result["estimated_cost_usd"], 20 * 4e-6 + 80 * 0.2e-6 + 100 * 20e-6
            )
            events = [
                json.loads(s)
                for s in (Path(directory) / "cached-provider/events.jsonl")
                .read_text()
                .splitlines()
            ]
            self.assertGreater(
                sum(e.get("budget_charge_usd", 0) for e in events),
                result["estimated_cost_usd"],
            )

    def test_compact_faces_roundtrip_and_focused_selection_not_lost(self):
        p = plan([{"action": "update", "id": "box", "params": {"height": 40}}])
        with (
            tempfile.TemporaryDirectory(dir="output") as directory,
            patch.object(wa, "RUNS", Path(directory)),
            patch.object(wa, "load_env"),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline-only"}),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.object(wa, "request", return_value=response(p)) as transport,
        ):
            selected = {"topology_ids": ["body_001:face_0005"]}
            for mode in ["full", "compact", "focused"]:
                wa.propose_document(
                    base(),
                    "make it 40 mm tall",
                    run_id=mode,
                    context_mode=mode,
                    selection_context=selected,
                )
            contexts = [
                json.loads(c.args[3]["messages"][1]["content"])
                for c in transport.call_args_list
            ]
            full, compact, focused = contexts
            table = compact["planar_face_context"]
            self.assertEqual(
                [dict(zip(table["columns"], r)) for r in table["rows"]],
                full["planar_face_context"],
            )
            self.assertEqual(
                focused["selected_topology_context"], full["selected_topology_context"]
            )
            self.assertEqual(len(focused["planar_face_context"]["rows"]), 1)
            self.assertEqual(focused["document"], full["document"])

    def test_router_deduplication_and_explicit_new_proposal(self):
        import time
        from fastapi import HTTPException
        from crate_studio import workspace_server as ws

        started, release = threading.Event(), threading.Event()

        def propose(doc, prompt, **kwargs):
            started.set()
            self.assertTrue(release.wait(3))
            result = wa.apply_plan(
                doc,
                plan([{"action": "update", "id": "box", "params": {"height": 40}}]),
                prompt,
            )
            result.update(
                model=wa.MODEL,
                run_id=kwargs["run_id"],
                response_ids=["offline-http"],
                calls=1,
                estimated_cost_usd=0,
            )
            return result

        with (
            tempfile.TemporaryDirectory(dir="output") as directory,
            patch.object(ws, "DATA", Path(directory)),
            patch.object(ws, "DOCS", Path(directory) / "documents"),
            patch.object(ws, "JOBS", {}),
            patch.object(wa.agent, "configured", return_value=True),
            patch.object(wa, "propose_document", side_effect=propose) as model,
        ):
            routes = {
                route.path: route.endpoint
                for route in ws.create_router(threading.RLock()).routes
            }
            create = routes["/api/studio/documents"]
            start = routes["/api/studio/agent"]
            get = routes["/api/studio/jobs/{id}"]
            doc = {
                "name": "HTTP fixture",
                "features": base()["features"],
                "annotations": [],
                "metadata": {},
                "display": {},
            }
            saved = create(ws.SaveBody(document=doc))
            payload = {"document_id": saved["id"], "prompt": "make it 40 mm tall"}
            first = start(ws.PromptBody(**payload))
            self.assertTrue(started.wait(3))
            duplicate = start(ws.PromptBody(**payload))
            self.assertEqual(first["id"], duplicate["id"])
            with self.assertRaises(HTTPException) as conflict:
                start(ws.PromptBody(**{**payload, "prompt": "different"}))
            self.assertEqual(conflict.exception.status_code, 409)
            release.set()

            def completed(ident):
                for _ in range(100):
                    row = get(ident)
                    if row["status"] in ["completed", "failed"]:
                        return row
                    time.sleep(0.01)
                self.fail("worker did not complete")

            self.assertEqual(completed(first["id"])["status"], "completed")
            self.assertEqual(start(ws.PromptBody(**payload))["id"], first["id"])
            fresh = start(ws.PromptBody(**{**payload, "regenerate": True}))
            self.assertNotEqual(fresh["id"], first["id"])
            self.assertEqual(completed(fresh["id"])["status"], "completed")
            self.assertEqual(model.call_count, 2)


if __name__ == "__main__":
    unittest.main()
