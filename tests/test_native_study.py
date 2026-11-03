"""Human/native rechecks must retain targets, reject stale proof and avoid AI."""

from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from crate_studio import workspace_agent as wa
from crate_studio.native_study import recheck, native_review_state, study_identity
from crate_studio.design_tools import review_identity
from tests.test_mechanism_study import document, specification


def fixture():
    doc = document()
    doc["metadata"] = {
        "design_mechanism": specification(10),
        "design_review": {
            "reports": {
                "floor:state:start": {
                    "footprint": {
                        "center_xy": [-20, 0],
                        "size_mm": [4, 4],
                        "z_range_mm": [0, 2],
                    }
                },
                "floor:state:end": {
                    "footprint": {
                        "center_xy": [-10, 0],
                        "size_mm": [4, 4],
                        "z_range_mm": [0, 2],
                    }
                },
            },
            "unresolved": ["Physical qualification remains open"],
        },
    }
    return doc


class NativeStudyTests(unittest.TestCase):
    def test_native_recheck_has_no_model_calls_and_does_not_claim_visual_approval(self):
        original = fixture()
        with tempfile.TemporaryDirectory(dir="output") as root, patch.object(
            wa, "request", side_effect=AssertionError("No network")
        ), patch.object(wa, "paid_chat", side_effect=AssertionError("No paid call")):
            checked, report = recheck(original, Path(root))
        self.assertTrue(report["passed"])
        self.assertEqual(report["model_calls"], 0)
        self.assertFalse(report["visual_review_performed"])
        self.assertFalse(report["physical_validation"])
        self.assertNotIn("native_study_review", original["metadata"])
        self.assertEqual(checked["features"], original["features"])
        self.assertEqual(review_identity(checked), review_identity(original))
        self.assertEqual(
            checked["metadata"]["design_review"], original["metadata"]["design_review"]
        )
        self.assertEqual(native_review_state(checked)["status"], "current")
        self.assertTrue(native_review_state(checked)["passed"])
        self.assertNotIn("frames", report["reports"]["motion"])

    def test_changed_source_or_retained_targets_invalidates_recheck(self):
        with tempfile.TemporaryDirectory(dir="output") as root:
            doc, _ = recheck(fixture(), Path(root))
        changed = deepcopy(doc)
        changed["features"][1]["params"]["width"] = 3
        self.assertEqual(native_review_state(changed)["status"], "stale")
        self.assertIsNone(native_review_state(changed)["passed"])
        changed = deepcopy(doc)
        changed["metadata"]["design_review"]["reports"]["floor:state:end"]["footprint"][
            "size_mm"
        ][0] = 5
        self.assertEqual(native_review_state(changed)["status"], "stale")

    def test_failed_floor_stays_failed_without_relaxing_target(self):
        doc = fixture()
        doc["features"][1]["params"]["width"] = 3
        with tempfile.TemporaryDirectory(dir="output") as root:
            checked, report = recheck(doc, Path(root))
        self.assertFalse(report["passed"])
        self.assertFalse(native_review_state(checked)["passed"])
        floor = report["reports"]["floor:state:start"]
        self.assertEqual(floor["footprint"]["size_mm"], [4, 4])
        self.assertAlmostEqual(floor["coverage_fraction"], 0.75)
        self.assertIn("floor:state:start", report["failures"])
        missing = fixture()
        del missing["metadata"]["design_review"]["reports"]["floor:state:end"]
        with self.assertRaisesRegex(ValueError, "Missing retained"):
            study_identity(missing)

    def test_native_route_saves_new_revision_with_parent_and_zero_call_provenance(self):
        from crate_studio import workspace_server as ws

        with tempfile.TemporaryDirectory(dir="output") as root, patch.object(
            ws, "DATA", Path(root)
        ), patch.object(ws, "DOCS", Path(root) / "documents"), patch.object(
            wa, "request", side_effect=AssertionError("No model transport")
        ):
            routes = {
                r.path: r.endpoint for r in ws.create_router(threading.RLock()).routes
            }
            parent = routes["/api/studio/documents"](ws.SaveBody(document=fixture()))
            result = routes["/api/studio/study/recheck"](
                ws.SaveBody(document=parent["document"], parent_id=parent["id"])
            )
            self.assertNotEqual(result["id"], parent["id"])
            self.assertEqual(result["parent_id"], parent["id"])
            self.assertEqual(result["native_study_state"]["status"], "current")
            self.assertTrue(result["native_study_state"]["passed"])
            self.assertEqual(result["provenance"]["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
