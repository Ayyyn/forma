from copy import deepcopy
import tempfile
import unittest
from crate_studio.retention_study import retention_study, specification
from crate_studio.workspace_geometry import build_document
from crate_studio.design_tools import DesignSession


def fixture(open_roof=False):
    features = [
        {
            "id": "cage",
            "type": "box",
            "params": {"width": 10, "depth": 10, "height": 10},
        },
        {
            "id": "void",
            "type": "box",
            "params": {
                "width": 6,
                "depth": 6,
                "height": 6,
                "z": 2,
                "operation": "cut",
                "target_part_id": "body_001",
            },
        },
    ]
    if open_roof:
        features.append(
            {
                "id": "entry",
                "type": "box",
                "params": {
                    "width": 6,
                    "depth": 6,
                    "height": 3,
                    "z": 8,
                    "operation": "cut",
                    "target_part_id": "body_001",
                },
            }
        )
    features.append(
        {
            "id": "pellet",
            "type": "box",
            "params": {
                "width": 2,
                "depth": 2,
                "height": 2,
                "z": 4,
                "operation": "new_body",
            },
        }
    )
    mechanism = {
        "root": "body_001",
        "joints": [
            {
                "id": "held",
                "parent": "body_001",
                "child": "body_002",
                "type": "fixed",
                "axis": [0, 0, 1],
                "origin": [0, 0, 0],
                "limits": [0, 0],
            }
        ],
        "states": [
            {"name": "locked", "values": {"held": 0}},
            {"name": "unlocked", "values": {"held": 0}},
        ],
        "connections": [],
        "samples_per_segment": 2,
    }
    target = {
        "part_ids": ["body_002"],
        "state_names": ["locked", "unlocked"],
        "distance_mm": 4,
        "samples": 17,
    }
    doc = {
        "name": "Capture control",
        "features": features,
        "metadata": {
            "design_mechanism": mechanism,
            "native_study_targets": {"retention": target},
        },
    }
    return doc, target


class RetentionTests(unittest.TestCase):
    def test_open_entry_escape_is_not_masked_by_fixed_joint(self):
        closed, target = fixture()
        report = retention_study(closed, build_document(closed), target)
        self.assertTrue(report["passed"])
        self.assertEqual(report["case_count"], 12)
        opened, target = fixture(True)
        bad = retention_study(opened, build_document(opened), target)
        self.assertFalse(bad["passed"])
        self.assertEqual(len(bad["escapes"]), 2)
        self.assertTrue(
            all(r["direction_world"] == [0.0, 0.0, 1.0] for r in bad["escapes"])
        )
        self.assertFalse(bad["global_retention_verified"])

    def test_finish_rejects_missing_or_weaker_retention_contract(self):
        doc, target = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            session = DesignSession(doc, "Test name", tmp)
            draft = session.call(
                "draft_candidate",
                {
                    "base_candidate_id": "base",
                    "plan": {
                        "status": "ready",
                        "summary": "Rename cage",
                        "operations": [
                            {
                                "action": "update",
                                "id": "cage",
                                "name": "Renamed cage",
                                "params": {},
                            }
                        ],
                        "questions": [],
                        "evidence": [{"quote": "Test name"}],
                    },
                },
            )
            self.assertTrue(draft["ok"], draft)
            cid = draft["candidate_id"]
            session.call(
                "check_motion",
                {"candidate_id": cid, "spec": doc["metadata"]["design_mechanism"]},
            )
            for gate in ["interference", "exports", "visual"]:
                session.reports[cid][gate] = {"passed": True}
            finish = {
                "candidate_id": cid,
                "summary": "Fixture acceptance test",
                "visual_review": "Fixture only, no model review",
                "alternatives": ["Fixture control"],
                "assumptions": [],
                "unresolved": ["Physical fit remains unknown"],
            }
            self.assertIn(
                "check_retention", session.call("finish_design", finish)["error"]
            )
            weak = deepcopy(target)
            weak["state_names"] = ["locked"]
            self.assertTrue(
                session.call("check_retention", {"candidate_id": cid, "spec": weak})[
                    "passed"
                ]
            )
            self.assertIn(
                "check_retention", session.call("finish_design", finish)["error"]
            )
            self.assertTrue(
                session.call("check_retention", {"candidate_id": cid, "spec": {}})[
                    "passed"
                ]
            )
            self.assertTrue(session.call("finish_design", finish)["ok"])

    def test_invalid_or_missing_retention_identifiers_fail(self):
        doc, target = fixture()
        for key, value in [
            ("part_ids", ["missing"]),
            ("state_names", ["missing"]),
            ("distance_mm", float("nan")),
            ("samples", True),
        ]:
            with self.assertRaises(ValueError):
                specification(
                    {**target, key: value}, ["body_002"], ["locked", "unlocked"]
                )
