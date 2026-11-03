"""Native floor checks must reject real holes, seams and wrong poses."""

from copy import deepcopy
import math
import tempfile
import unittest

from crate_studio.floor_check import floor_coverage
from crate_studio.workspace_cache import cached_build
from crate_studio.design_tools import DesignSession
from tests.test_mechanism_study import document, specification


def footprint(width=20, depth=10, center=None, band=None):
    return {
        "center_xy": center or [0, 0],
        "size_mm": [width, depth],
        "z_range_mm": band or [0, 5],
    }


class FloorCheckTests(unittest.TestCase):
    def test_selected_candidate_cannot_mix_floor_and_motion_definitions(self):
        from tests.test_design_agent import finish

        doc = document()
        with tempfile.TemporaryDirectory(dir="output") as folder:
            session = DesignSession(doc, "Check floors", folder)
            draft = session.call(
                "draft_candidate",
                {
                    "base_candidate_id": "base",
                    "plan": {
                        "summary": "Inspect the retained motion geometry",
                        "status": "ready",
                        "operations": [],
                        "questions": [],
                        "evidence": [],
                    },
                },
            )
            ident = draft["candidate_id"]
            spec = specification(10)
            self.assertTrue(
                session.call("check_motion", {"candidate_id": ident, "spec": spec})[
                    "passed"
                ]
            )
            other = deepcopy(spec)
            other["joints"][0]["axis"] = [0, 1, 0]
            args = {
                "candidate_id": ident,
                "footprint": footprint(4, 4, [-20, 10]),
                "mechanism_spec": other,
                "state_name": "end",
            }
            self.assertTrue(session.call("check_floor", args)["passed"])
            for name in ("check_interference", "verify_exports", "render_views"):
                self.assertTrue(session.call(name, {"candidate_id": ident})["ok"])
            session.acknowledge_views(ident)
            blocked = session.call("finish_design", finish(ident))
            self.assertFalse(blocked["ok"])
            self.assertIn("different mechanism", blocked["error"])
            args.update(mechanism_spec=spec, footprint=footprint(4, 4, [-10, 0]))
            self.assertTrue(session.call("check_floor", args)["passed"])
            partial = session.call("finish_design", finish(ident))
            self.assertFalse(partial["ok"])
            self.assertIn("Missing floor coverage", partial["error"])
            args.update(state_name="start", footprint=footprint(4, 4, [-20, 0]))
            self.assertTrue(session.call("check_floor", args)["passed"])
            self.assertFalse(session.call("finish_design", finish(ident))["ok"])
            for state_name in ("start", "end"):
                view = session.call(
                    "render_state",
                    {
                        "candidate_id": ident,
                        "mechanism_spec": spec,
                        "state_name": state_name,
                    },
                )
                self.assertTrue(view["ok"])
                session.acknowledge_views(ident, view["visual_report_key"])
            self.assertEqual(view["metrics"]["size_mm"], [14, 4, 2])
            self.assertTrue(session.call("finish_design", finish(ident))["ok"])

    def test_native_plate_hole_is_not_filled_by_its_outline(self):
        doc = {
            "features": [
                {
                    "id": "floor",
                    "type": "box",
                    "params": {"width": 20, "depth": 10, "height": 2},
                }
            ]
        }
        solid = cached_build(doc)
        report, *_ = floor_coverage(solid["parts"], footprint())
        self.assertTrue(report["passed"])
        self.assertAlmostEqual(report["supported_area_mm2"], 200)
        doc["features"].append(
            {
                "id": "hole",
                "type": "cut_hole",
                "params": {"radius": 2, "end_condition": "through_all"},
            }
        )
        holed = cached_build(doc)
        report, *_ = floor_coverage(holed["parts"], footprint())
        self.assertFalse(report["passed"])
        self.assertAlmostEqual(report["missing_area_mm2"], math.pi * 4, delta=0.06)
        self.assertTrue(report["curved_boundary_approximation"])

    def test_thin_cross_seam_is_measured_and_wall_tops_are_excluded(self):
        doc = {
            "features": [
                {
                    "id": "left",
                    "type": "box",
                    "params": {"width": 10, "depth": 10, "height": 2, "cx": -5.2},
                },
                {
                    "id": "right",
                    "type": "box",
                    "params": {
                        "width": 10,
                        "depth": 10,
                        "height": 2,
                        "cx": 5.2,
                        "operation": "new_body",
                    },
                },
                {
                    "id": "high",
                    "type": "box",
                    "params": {
                        "width": 20.4,
                        "depth": 10,
                        "height": 2,
                        "z": 30,
                        "operation": "new_body",
                    },
                },
            ]
        }
        report, *_ = floor_coverage(cached_build(doc)["parts"], footprint(20.4))
        self.assertFalse(report["passed"])
        self.assertAlmostEqual(report["missing_area_mm2"], 4, places=6)
        self.assertEqual(report["support_levels_mm"], [2])

    def test_layered_projection_does_not_claim_flatness_or_strength(self):
        doc = {
            "features": [
                {
                    "id": "left",
                    "type": "box",
                    "params": {"width": 12, "depth": 10, "height": 2, "cx": -4},
                },
                {
                    "id": "right",
                    "type": "box",
                    "params": {
                        "width": 12,
                        "depth": 10,
                        "height": 2,
                        "cx": 4,
                        "z": 2.4,
                        "operation": "new_body",
                    },
                },
            ]
        }
        report, *_ = floor_coverage(cached_build(doc)["parts"], footprint())
        self.assertTrue(report["passed"])
        self.assertAlmostEqual(report["support_height_span_mm"], 2.4)
        self.assertFalse(report["strength_verified"])
        self.assertFalse(report["flatness_verified"])

    def test_named_pose_coverage_and_cached_failure_restore(self):
        doc = document()
        spec = specification(10)
        with tempfile.TemporaryDirectory(dir="output") as folder:
            session = DesignSession(doc, "Check floors", folder)
            args = {
                "candidate_id": "base",
                "footprint": footprint(4, 4, [-20, 0]),
                "mechanism_spec": spec,
                "state_name": "start",
            }
            self.assertTrue(session.call("check_floor", args)["passed"])
            bad = deepcopy(args)
            bad["state_name"] = "end"
            self.assertFalse(session.call("check_floor", bad)["passed"])
            good = deepcopy(bad)
            good["footprint"]["center_xy"] = [-10, 0]
            self.assertTrue(session.call("check_floor", good)["passed"])
            self.assertFalse(session.call("check_floor", bad)["passed"])
            self.assertTrue(session.events[-1]["cache_hit"])
            self.assertFalse(session.reports["base"]["floor:state:end"]["passed"])
            self.assertTrue(session.reports["base"]["floor:state:start"]["passed"])


if __name__ == "__main__":
    unittest.main()
