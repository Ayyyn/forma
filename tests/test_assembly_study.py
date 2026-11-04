"""Actual solids: insertion obstruction, staged detour and source-pose gates."""

import tempfile
import unittest
from crate_studio.assembly_study import assembly_study, matrix
from crate_studio.workspace_geometry import build_document
from crate_studio.design_tools import DesignSession


def fixture():
    doc = {
        "name": "Insertion fixture",
        "features": [
            {
                "id": "base",
                "type": "box",
                "params": {"width": 10, "depth": 10, "height": 2},
            },
            {
                "id": "peg",
                "type": "box",
                "params": {
                    "width": 2,
                    "depth": 2,
                    "height": 2,
                    "cx": 10,
                    "z": 0,
                    "operation": "new_body",
                },
            },
        ],
    }
    return doc, build_document(doc)


def path(detour=False):
    return {
        "initial_placements": {
            "body_001": {"translation": [0, 0, 0]},
            "body_002": {"translation": [-20, 0, 0]},
        },
        "steps": (
            [
                {
                    "name": "Lift",
                    "placements": {"body_002": {"translation": [-20, 0, 5]}},
                },
                {
                    "name": "Pass above base",
                    "placements": {"body_002": {"translation": [0, 0, 5]}},
                },
            ]
            if detour
            else []
        )
        + [{"name": "Insert", "placements": {"body_002": {"translation": [0, 0, 0]}}}],
        "target_state": None,
        "step_mm": 0.5,
        "step_deg": 3,
    }


class AssemblyTests(unittest.TestCase):
    def test_failed_path_stops_at_first_collision_and_passing_path_is_fully_sampled(
        self,
    ):
        doc, native = fixture()
        blocked = assembly_study(doc, native, path(False))
        self.assertFalse(blocked["passed"])
        self.assertEqual(blocked["collision_sample_count"], 1)
        self.assertFalse(blocked["sampling_complete"])
        self.assertLess(blocked["sample_count"], blocked["planned_sample_count"])
        self.assertLess(blocked["frames"][-1]["progress_pct"], 100)
        self.assertTrue(blocked["frames"][-1]["overlaps"])
        clear = assembly_study(doc, native, path(True))
        self.assertTrue(clear["passed"])
        self.assertTrue(clear["sampling_complete"])
        self.assertEqual(clear["sample_count"], clear["planned_sample_count"])
        self.assertEqual(clear["frames"][-1]["progress_pct"], 100)

    def test_driver_delivers_failed_pose_image_without_selecting_a_design(self):
        import json
        import os
        from pathlib import Path
        from unittest.mock import patch
        from crate_studio import design_agent as da, workspace_agent as wa

        phase = 0

        def provider(base, key, route, payload, timeout):
            nonlocal phase
            phase += 1
            if phase == 1:
                name = "record_strategy"
                args = {
                    "alternatives": [
                        {
                            "name": "Fixture",
                            "benefit": "Native diagnostic",
                            "risk": "No physical proof",
                        }
                    ],
                    "selected": "Fixture",
                    "assumptions": [],
                    "steps": ["Check insertion"],
                }
            elif phase == 2:
                name = "check_assembly"
                args = {"candidate_id": "base", "spec": path()}
            else:
                images = [
                    part
                    for message in payload["messages"]
                    if isinstance(message.get("content"), list)
                    for part in message["content"]
                    if part.get("type") == "image_url"
                ]
                self.assertTrue(images)
                self.assertTrue(
                    images[-1]["image_url"]["url"].startswith("data:image/png;base64,")
                )
                return {
                    "http_status": 200,
                    "usage": {"prompt_tokens": 100, "completion_tokens": 100},
                }, {
                    "id": "diagnostic-3",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "status": "incomplete",
                                        "summary": "Failed native insertion retained for repair.",
                                        "questions": [],
                                    }
                                ),
                            }
                        }
                    ],
                }
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"diagnostic-{phase}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                ],
            }
            return {
                "http_status": 200,
                "usage": {"prompt_tokens": 100, "completion_tokens": 100},
            }, {"id": f"diagnostic-response-{phase}", "choices": [{"message": message}]}

        doc, _ = fixture()
        with (
            tempfile.TemporaryDirectory(dir="output") as folder,
            patch.object(wa, "RUNS", Path(folder)),
            patch.object(wa, "load_env"),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline-secret"}),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.object(wa, "request", side_effect=provider),
        ):
            result = da.propose_design(
                doc,
                "Check a staged assembly",
                run_id="diagnostic-image-control",
                max_turns=3,
            )
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["calls"], 3)

    def test_exact_native_assembly_reuse_copies_report_and_invalidates_sampling(self):
        from unittest.mock import patch
        from crate_studio import assembly_study as module
        from crate_studio.workspace_cache import cached_build, cache_clear
        from crate_studio.motion_cache import native_motion_cache

        cache_clear()
        native_motion_cache.clear()
        doc, _ = fixture()
        native = cached_build(doc)
        with patch.object(module, "collisions", wraps=module.collisions) as checks:
            a = assembly_study(doc, native, path(True))
            count = checks.call_count
            b = assembly_study(doc, native, path(True))
            self.assertEqual(a, b)
            self.assertEqual(checks.call_count, count)
            a["frames"].clear()
            self.assertTrue(assembly_study(doc, native, path(True))["frames"])
            changed = path(True)
            changed["step_mm"] = 0.25
            assembly_study(doc, native, changed)
            self.assertGreater(checks.call_count, count)
        self.assertEqual(native_motion_cache.info().hits, 2)

    def test_staged_detour_passes_but_direct_insert_hits_actual_body(self):
        doc, built = fixture()
        blocked = assembly_study(doc, built, path())
        self.assertFalse(blocked["passed"])
        self.assertGreater(blocked["collision_sample_count"], 0)
        self.assertTrue(blocked["initial_separation_passed"])
        clear = assembly_study(doc, built, path(True))
        self.assertTrue(clear["passed"])
        self.assertEqual(
            clear["frames"][-1]["pose_matrices"]["body_002"],
            matrix({"translation": [0, 0, 0], "rotation": [0, 0, 0]}).tolist(),
        )
        self.assertGreater(clear["native_pair_checks"], 0)

    def test_assembly_cannot_start_assembled_or_finish_at_wrong_pose(self):
        doc, built = fixture()
        already = path()
        already["initial_placements"]["body_002"]["translation"] = [0, 0, 0]
        # They start 4mm apart in this particular original fixture, so use a
        # position 1mm from the base to exercise the independent separation gate.
        already["initial_placements"]["body_002"]["translation"] = [-3, 0, 0]
        self.assertFalse(
            assembly_study(doc, built, already)["initial_separation_passed"]
        )
        wrong = path(True)
        wrong["steps"][-1]["placements"]["body_002"]["translation"] = [1, 0, 0]
        result = assembly_study(doc, built, wrong)
        self.assertFalse(result["target_pose_passed"])
        self.assertFalse(result["passed"])

    def test_invalid_or_underspecified_and_overlong_paths_are_rejected(self):
        doc, built = fixture()
        for modify in (
            lambda p: p["initial_placements"].pop("body_001"),
            lambda p: p.update(step_mm=True),
            lambda p: p["steps"][0]["placements"].update(
                unknown={"translation": [0, 0, 0]}
            ),
            lambda p: p["initial_placements"]["body_001"].update(
                rotation=[float("nan"), 0, 0]
            ),
        ):
            raw = path()
            modify(raw)
            with self.assertRaises(ValueError):
                assembly_study(doc, built, raw)
        raw = path()
        raw["initial_placements"]["body_002"]["translation"] = [-1000, -1000, -1000]
        raw["step_mm"] = 0.1
        with self.assertRaisesRegex(ValueError, "2001"):
            assembly_study(doc, built, raw)

    def test_tool_retains_failure_and_reuses_and_restores_exact_plan(self):
        doc, _ = fixture()
        with tempfile.TemporaryDirectory(dir="output") as folder:
            session = DesignSession(doc, "Assembly check", folder)
            bad = session.call(
                "check_assembly", {"candidate_id": "base", "spec": path()}
            )
            self.assertTrue(bad["ok"])
            self.assertFalse(bad["passed"])
            from pathlib import Path

            self.assertTrue((Path(folder) / bad["failure_image_artifact"]).is_file())
            self.assertTrue(bad["collision_summary"])
            self.assertNotIn("visual", session.reports["base"])
            self.assertFalse(session.reports["base"]["assembly"]["passed"])
            clear = session.call(
                "check_assembly", {"candidate_id": "base", "spec": path(True)}
            )
            self.assertTrue(clear["passed"])
            self.assertIsNone(clear["failure_image_artifact"])
            import json

            self.assertFalse(
                json.loads(
                    (Path(folder) / bad["evidence"]).read_text(encoding="utf-8")
                )["passed"]
            )
            self.assertNotEqual(bad["evidence"], clear["evidence"])
            replay = session.call(
                "check_assembly", {"candidate_id": "base", "spec": path()}
            )
            self.assertEqual(bad, replay)
            self.assertFalse(session.reports["base"]["assembly"]["passed"])
            self.assertEqual(
                session.candidates["base"]["document"]["metadata"]["assembly_plan"],
                bad["spec"],
            )

    def test_named_assembly_target_tracks_checked_motion_and_invalidates_cached_pose(
        self,
    ):
        doc, _ = fixture()

        def mechanism(end):
            return {
                "root": "body_001",
                "joints": [
                    {
                        "id": "slide",
                        "parent": "body_001",
                        "child": "body_002",
                        "type": "prismatic",
                        "axis": [1, 0, 0],
                        "origin": [0, 0, 0],
                        "limits": [0, 20],
                    }
                ],
                "states": [
                    {"name": "start", "values": {"slide": 0}},
                    {"name": "end", "values": {"slide": end}},
                ],
                "connections": [],
                "samples_per_segment": 3,
            }

        doc["metadata"] = {"design_mechanism": mechanism(10)}
        plan = path(True)
        plan["target_state"] = "end"
        plan["steps"][-1]["placements"]["body_002"]["translation"] = [20, 0, 0]
        with tempfile.TemporaryDirectory(dir="output") as folder:
            session = DesignSession(doc, "Target binding control", folder)
            self.assertTrue(
                session.call(
                    "check_motion", {"candidate_id": "base", "spec": mechanism(20)}
                )["passed"]
            )
            first = session.call(
                "check_assembly", {"candidate_id": "base", "spec": plan}
            )
            self.assertTrue(first["passed"], first)
            self.assertEqual(first["target_pose_matrices"]["body_002"][0][3], 20)
            session.call(
                "check_motion", {"candidate_id": "base", "spec": mechanism(10)}
            )
            changed = session.call(
                "check_assembly", {"candidate_id": "base", "spec": plan}
            )
            self.assertFalse(session.events[-1]["cache_hit"])
            self.assertFalse(changed["passed"])
            self.assertEqual(changed["target_pose_matrices"]["body_002"][0][3], 10)


if __name__ == "__main__":
    unittest.main()
