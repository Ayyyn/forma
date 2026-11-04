from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from crate_studio.handling_study import handling_study
from crate_studio.workspace_cache import cached_build
from crate_studio.design_tools import DesignSession
from crate_studio.mechanical_print import export_print_pack


def fixture(roof=False):
    features = [
        {
            "id": "base",
            "type": "box",
            "params": {"width": 10, "depth": 10, "height": 2},
        },
        {
            "id": "stop",
            "type": "box",
            "params": {
                "width": 1,
                "depth": 10,
                "height": 0.4,
                "cx": 3,
                "z": 2,
                "operation": "add",
                "target_part_id": "body_001",
            },
        },
    ]
    if roof:
        features += [
            {
                "id": "pillar",
                "type": "box",
                "params": {
                    "width": 10,
                    "depth": 2,
                    "height": 2.2,
                    "cy": 4,
                    "z": 2,
                    "operation": "add",
                    "target_part_id": "body_001",
                },
            },
            {
                "id": "roof",
                "type": "box",
                "params": {
                    "width": 10,
                    "depth": 10,
                    "height": 1,
                    "z": 3.2,
                    "operation": "add",
                    "target_part_id": "body_001",
                },
            },
        ]
    features += [
        {
            "id": "slider",
            "type": "box",
            "params": {
                "width": 2,
                "depth": 2,
                "height": 1,
                "z": 2,
                "operation": "new_body",
            },
        }
    ]
    spec = {
        "root": "body_001",
        "joints": [
            {
                "id": "slide",
                "parent": "body_001",
                "child": "body_002",
                "type": "prismatic",
                "axis": [1, 0, 0],
                "origin": [0, 0, 0],
                "limits": [-1, 6],
            }
        ],
        "states": [
            {"name": "open", "values": {"slide": 0}},
            {"name": "other", "values": {"slide": 1}},
        ],
        "connections": [],
        "samples_per_segment": 2,
    }
    paths = [
        {
            "name": "Lift then overrun",
            "state_name": "open",
            "joint_ids": ["slide"],
            "steps": [
                {"translation_mm": [0, 0, 0.4], "samples": 9},
                {"translation_mm": [6, 0, 0], "samples": 13},
            ],
        }
    ]
    return {
        "name": "Handling fixture",
        "features": features,
        "metadata": {
            "design_mechanism": spec,
            "native_study_targets": {"handling_paths": paths},
        },
    }, paths


class HandlingTests(unittest.TestCase):
    def test_small_lift_bypasses_stop_until_actual_roof_blocks_it(self):
        doc, paths = fixture()
        original = deepcopy(doc)
        bad = handling_study(doc, cached_build(doc), paths)
        self.assertFalse(bad["passed"])
        self.assertTrue(bad["cases"][0]["unwanted_path_clear"])
        self.assertEqual(len(bad["cases"][0]["steps"]), 2)
        self.assertEqual(doc, original)
        doc, paths = fixture(True)
        built = cached_build(doc)
        good = handling_study(doc, built, paths)
        self.assertTrue(good["passed"])
        self.assertFalse(good["cases"][0]["unwanted_path_clear"])
        self.assertEqual(len(good["cases"][0]["steps"]), 1)
        good["cases"][0]["passed"] = False
        self.assertTrue(handling_study(doc, built, paths)["cases"][0]["passed"])

    def test_finish_requires_the_exact_retained_path_not_a_different_blocked_probe(
        self,
    ):
        doc, paths = fixture(True)
        with tempfile.TemporaryDirectory(dir="output") as tmp:
            session = DesignSession(doc, "Rename fixture", tmp)
            drafted = session.call(
                "draft_candidate",
                {
                    "base_candidate_id": "base",
                    "plan": {
                        "summary": "Rename",
                        "status": "ready",
                        "operations": [
                            {
                                "action": "update",
                                "id": "base",
                                "name": "Renamed",
                                "params": {},
                            }
                        ],
                        "questions": [],
                        "evidence": [{"quote": "Rename fixture"}],
                    },
                },
            )
            self.assertTrue(drafted["ok"], drafted)
            cid = drafted["candidate_id"]
            self.assertTrue(
                session.call(
                    "check_motion",
                    {"candidate_id": cid, "spec": doc["metadata"]["design_mechanism"]},
                )["passed"]
            )
            for key in ("interference", "exports", "visual"):
                session.reports[cid][key] = {"passed": True}
            finish = {
                "candidate_id": cid,
                "summary": "Fixture only",
                "visual_review": "Native test fixture",
                "alternatives": ["Fixture"],
                "assumptions": [],
                "unresolved": ["Physical fit unknown"],
            }
            self.assertIn(
                "check_handling", session.call("finish_design", finish)["error"]
            )
            weak = deepcopy(paths)
            weak[0]["steps"][0]["translation_mm"][2] = 0.8
            self.assertTrue(
                session.call(
                    "check_handling", {"candidate_id": cid, "spec": {"paths": weak}}
                )["passed"]
            )
            self.assertIn(
                "check_handling", session.call("finish_design", finish)["error"]
            )
            self.assertTrue(
                session.call("check_handling", {"candidate_id": cid, "spec": {}})[
                    "passed"
                ]
            )

    def test_clear_handling_escape_blocks_print_release(self):
        doc, _ = fixture()
        with tempfile.TemporaryDirectory(dir="output") as tmp:
            with self.assertRaisesRegex(ValueError, "unwanted lift/pull"):
                export_print_pack(doc, Path(tmp))
