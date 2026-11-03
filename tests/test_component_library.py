"""Actual native insertion/edit/placement and HTTP revision isolation, offline."""

from copy import deepcopy
import base64
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import cadquery as cq
from fastapi import HTTPException

from crate_studio import component_library as lib, workspace_server as ws
from crate_studio.workspace_geometry import build_document, export_document, _bounds
from crate_studio.design_tools import DesignSession


class LibraryTests(unittest.TestCase):
    def context(self, directory):
        root = Path(directory)

        def store(data):
            key = hashlib.sha256(data).hexdigest()
            (root / (key + ".step")).write_bytes(data)
            return key

        return store, lambda key: root / (key + ".step")

    def base(self):
        return ws.normalize_document(
            {
                "name": "Fixture",
                "features": [
                    {
                        "id": "plate",
                        "type": "box",
                        "params": {"width": 20, "depth": 20, "height": 2},
                    }
                ],
            }
        )

    def test_native_edit_placement_export_and_reuse_preserve_base(self):
        with tempfile.TemporaryDirectory(dir="output") as directory:
            store, loader = self.context(directory)
            record = lib.materialize("socket-screw", {"length": 12}, directory, store)
            base = self.base()
            original = deepcopy(base)
            doc, ident = lib.insert(base, record, (35, 0, 20), (90, 0, 0))
            built = build_document(doc, loader)
            self.assertTrue(built["checks"]["passed"])
            self.assertEqual(len(built["parts"]), 2)
            self.assertEqual(base, original)
            self.assertEqual(
                _bounds(built["parts"][0]["shape"]),
                [[-10.0, -10.0, 0.0], [10.0, 10.0, 2.0]],
            )
            bounds = _bounds(built["parts"][1]["shape"])
            source_bounds = _bounds(
                cq.importers.importStep(str(loader(record["asset_id"]))).val()
            )
            self.assertAlmostEqual(bounds[0][0], source_bounds[0][0] + 35, places=4)
            self.assertAlmostEqual(bounds[1][1], -source_bounds[0][2], places=4)
            from cq_warehouse import fastener

            with patch.object(
                fastener,
                "SocketHeadCapScrew",
                side_effect=AssertionError("Cache hit must not regenerate"),
            ):
                self.assertEqual(
                    lib.materialize("socket-screw", {"length": 12}, directory, store),
                    record,
                )
            longer = lib.materialize("socket-screw", {"length": 20}, directory, store)
            revised, same = lib.insert(doc, longer, (35, 0, 20), (90, 0, 0), ident)
            self.assertEqual(same, ident)
            self.assertEqual(revised["features"][0], original["features"][0])
            result = build_document(revised, loader)
            self.assertTrue(result["checks"]["passed"])
            self.assertAlmostEqual(
                _bounds(result["parts"][1]["shape"])[1][1] - bounds[1][1], 8, places=4
            )
            exported = export_document(revised, loader, Path(directory) / "exports")
            self.assertTrue(exported["checks"]["passed"], exported)

    def test_catalog_parameter_and_source_guards(self):
        row = lib.definition("socket-screw")
        for bad in (
            {"length": float("nan")},
            {"length": True},
            {"length": -4},
            {"size": "M3"},
            {"code": "run"},
        ):
            with self.assertRaises(ValueError):
                lib.parameters(row, bad)
        with tempfile.TemporaryDirectory(dir="output") as directory:
            store, _ = self.context(directory)
            pinned = lib.definition("usb-micro-b")
            (Path(directory) / (pinned["git_blob"] + ".step")).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "hash"):
                lib.materialize("usb-micro-b", {}, directory, store)

    def test_model_component_candidate_is_stable_and_isolated(self):
        with tempfile.TemporaryDirectory(dir="output") as directory:
            store, loader = self.context(directory)
            args = {
                "base_candidate_id": "base",
                "catalog_id": "hex-nut",
                "parameters": {},
                "translation": [30, 0, 0],
                "rotation": [0, 0, 0],
                "feature_id": None,
                "quote": "Add a nut",
            }
            session = DesignSession(
                self.base(),
                "Add a nut",
                Path(directory) / "run1",
                loader,
                component_store=store,
            )
            first = session.call("insert_component", args)
            self.assertTrue(first["ok"], first)
            self.assertEqual(len(session.candidates["base"]["document"]["features"]), 1)
            self.assertEqual(first, session.call("insert_component", args))
            replay = DesignSession(
                self.base(),
                "Add a nut",
                Path(directory) / "run2",
                loader,
                component_store=store,
            )
            self.assertEqual(
                replay.call("insert_component", args)["candidate_id"],
                first["candidate_id"],
            )
            self.assertFalse(
                replay.call(
                    "insert_component", {**args, "quote": "invented permission"}
                )["ok"]
            )

    def test_server_insert_edit_portable_and_file_append_are_revision_bound(self):
        with (
            tempfile.TemporaryDirectory(dir="output") as directory,
            patch.object(ws, "DATA", Path(directory)),
            patch.object(ws, "DOCS", Path(directory) / "documents"),
            patch.object(ws, "ASSETS", Path(directory) / "assets"),
        ):
            routes = {
                r.path: r.endpoint for r in ws.create_router(threading.RLock()).routes
            }
            saved = ws.save_document(self.base(), threading.RLock())
            insert = routes["/api/studio/components/insert"]
            payload = dict(
                document=saved["document"],
                parent_id=saved["id"],
                catalog_id="hex-nut",
                translation=[30, 0, 0],
            )
            result = insert(ws.ComponentBody(**payload))
            ident = result["selected_feature_id"]
            self.assertNotEqual(saved["id"], result["id"])
            self.assertEqual(
                len(
                    ws.read_document(saved["id"], threading.RLock())["document"][
                        "features"
                    ]
                ),
                1,
            )
            portable = ws.portable_document(result["document"])
            self.assertEqual(len(portable["assets"]), 1)
            self.assertIn(
                "license",
                portable["document"]["metadata"]["component_instances"][ident],
            )
            # The drawing cache must retain the same catalogue parameters and
            # attribution as the portable source, rather than dropping metadata.
            from crate_studio.workspace_drawing import drawing_data, _parameter_rows
            data = drawing_data(result["document"], ws.built(ws.build_key(result["document"]))["parts"])
            self.assertIn("library.size", [row[1] for row in _parameter_rows(data)])
            ws.projected.cache_clear()
            with patch.object(ws, "drawing_svg", wraps=ws.drawing_svg) as render:
                ws.projected(ws.drawing_key(result["document"]))
                projected_source = render.call_args.args[0]
                self.assertEqual(
                    projected_source["metadata"]["component_instances"],
                    result["document"]["metadata"]["component_instances"],
                )
            wrong_asset = deepcopy(result["document"])
            wrong_asset["features"][-1]["params"]["asset_id"] = "different"
            self.assertEqual(lib.instances(wrong_asset), [])
            altered = deepcopy(payload)
            altered["document"]["name"] = "Unsaved local edit"
            with self.assertRaises(HTTPException) as conflict:
                insert(ws.ComponentBody(**altered))
            self.assertEqual(conflict.exception.status_code, 409)
            source = next(iter(portable["assets"].values()))
            appended = routes["/api/studio/components/import"](
                ws.ComponentImportBody(
                    document=result["document"],
                    parent_id=result["id"],
                    filename="external.step",
                    content_base64=source,
                    translation=[50, 0, 0],
                )
            )
            self.assertEqual(len(appended["document"]["features"]), 3)
            self.assertEqual(
                appended["document"]["features"][:2], result["document"]["features"]
            )
            self.assertEqual(len(appended["geometry"]["parts"]), 3)


if __name__ == "__main__":
    unittest.main()
