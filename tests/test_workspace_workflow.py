"""Cross-check finite panel motion against independently transformed CAD solids."""

from copy import deepcopy
import itertools
import math
import unittest

import cadquery as cq
import numpy as np

from crate_studio.engine import DEFAULT_SPEC, DEFAULT_REQUIREMENTS, evaluate
from crate_studio.workspace_requirements import requirement_state
from crate_studio.workspace_workflow import (
    revise_enclosure,
    motion_study,
    wall_definitions,
    wall_frame,
    interior_overlap,
    validate_motion,
    geometry_signature,
)
from crate_studio.workspace_geometry import build_document


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.spec = {
            **DEFAULT_SPEC,
            "inner_width_mm": 90,
            "inner_depth_mm": 60,
            "inner_height_mm": 45,
            "thickness_mm": 3,
            "material": "polypropylene",
        }
        self.req = {**DEFAULT_REQUIREMENTS, "min_capacity_l": 0.2, "payload_kg": 0}
        self.doc = revise_enclosure(
            {"features": [], "metadata": {"brief": "Portable mockup"}},
            self.spec,
            self.req,
        )

    def test_thickness_revision_updates_panels_and_requirements(self):
        revised = revise_enclosure(self.doc, {**self.spec, "thickness_mm": 4}, self.req)
        result = build_document(revised)
        expected = evaluate({**self.spec, "thickness_mm": 4}, self.req)
        self.assertTrue(result["checks"]["passed"])
        self.assertEqual(requirement_state(revised)["status"], "current")
        self.assertEqual(revised["metadata"]["brief"], "Portable mockup")
        volume = sum(p["shape"].Volume() for p in result["parts"])
        self.assertAlmostEqual(
            volume, expected["metrics"]["material_volume_mm3"], places=6
        )
        self.assertNotEqual(geometry_signature(self.doc), geometry_signature(revised))

    def test_signature_survives_browser_numeric_roundtrip(self):
        doc = deepcopy(self.doc)
        doc["features"][0]["params"]["width"] = int(
            doc["features"][0]["params"]["width"]
        )
        self.assertEqual(geometry_signature(self.doc), geometry_signature(doc))

    def test_custom_edits_require_explicit_replacement(self):
        self.doc["features"][0]["params"]["width"] += 3
        with self.assertRaisesRegex(ValueError, "custom geometry"):
            revise_enclosure(self.doc, self.spec, self.req)
        restored = revise_enclosure(self.doc, self.spec, self.req, True)
        self.assertEqual(requirement_state(restored)["status"], "current")

    def test_motion_refuses_stale_geometry_and_lid(self):
        self.doc["features"].pop()
        with self.assertRaises(ValueError):
            motion_study(self.doc)
        lid = revise_enclosure(self.doc, {**self.spec, "lid": True}, self.req, True)
        with self.assertRaisesRegex(ValueError, "top panel"):
            motion_study(lid)

    def test_motion_limits_reject_invalid_settings(self):
        for config in (
            {"max_angle_deg": float("nan")},
            {"max_angle_deg": -1},
            {"samples": 10000},
            {"samples": True},
            {"family": "arbitrary"},
            {"unused": 1},
        ):
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_motion(config)

    def test_closed_and_flat_envelopes_have_expected_thickness(self):
        study = motion_study(self.doc)
        self.assertTrue(study["sampled_overlap_free"])
        self.assertEqual(study["geometry_signature"], geometry_signature(self.doc))
        np.testing.assert_allclose(
            study["frames"][0]["extent_mm"], [96, 66, 48], atol=1e-8
        )
        np.testing.assert_allclose(
            study["frames"][-1]["extent_mm"], [186, 156, 6], atol=1e-8
        )

    def test_obb_collision_catches_overlap_and_allows_contact(self):
        a = {"center": np.zeros(3), "half": np.ones(3), "axes": np.eye(3)}
        for distance, expected in ((0, True), (1.9, True), (2, False), (2.1, False)):
            b = {**a, "center": np.array([distance, 0, 0])}
            self.assertEqual(interior_overlap(a, b), expected)

    def test_motion_bounds_and_overlap_match_opencascade(self):
        definitions = wall_definitions(self.spec)
        for angle in (0, 7.5, 30, 67.5, 90):
            with self.subTest(angle=angle):
                solids = []
                for p in definitions:
                    x, y, z = p["size_mm"]
                    shape = (
                        cq.Workplane("XY")
                        .box(x, y, z)
                        .val()
                        .translate(tuple(p["center_mm"]))
                    )
                    if p["direction"]:
                        pivot = p["pivot_mm"]
                        tip = list(pivot)
                        tip[0 if p["axis"] == "x" else 1] += 1
                        shape = shape.rotate(
                            tuple(pivot), tuple(tip), angle * p["direction"]
                        )
                    solids.append((p["id"], shape))
                boxes = [s.BoundingBox() for _, s in solids]
                low = [min(getattr(b, a + "min") for b in boxes) for a in "xyz"]
                high = [max(getattr(b, a + "max") for b in boxes) for a in "xyz"]
                frame = wall_frame(definitions, angle)
                np.testing.assert_allclose(frame["bounds_min_mm"], low, atol=1e-6)
                np.testing.assert_allclose(frame["bounds_max_mm"], high, atol=1e-6)
                overlaps = [
                    [a[0], b[0]]
                    for a, b in itertools.combinations(solids, 2)
                    if a[1].intersect(b[1]).Volume() > 1e-5
                ]
                self.assertEqual(frame["overlaps"], overlaps)

    def test_collision_detector_rejects_wrong_hinge_location(self):
        definitions = wall_definitions(self.spec)
        # Deliberately put each axis through the wall bottom center: thickness
        # then penetrates the base. This guards against a decorative animation.
        for p in definitions:
            if p["direction"]:
                p["pivot_mm"] = [*p["center_mm"][:2], self.spec["thickness_mm"]]
        self.assertTrue(wall_frame(definitions, 30)["overlaps"])

    def test_ai_global_thickness_regenerates_contract(self):
        from crate_studio.workspace_agent import apply_plan

        plan = {
            "status": "ready",
            "summary": "Change panel thickness",
            "questions": [],
            "operations": [{"action": "enclosure", "spec": {"thickness_mm": 4}}],
            "evidence": [{"quote": "all panels to 4 mm"}],
        }
        result = apply_plan(self.doc, plan, "Change all panels to 4 mm")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            result["document"]["metadata"]["source_spec"]["thickness_mm"], 4
        )
        self.assertEqual(requirement_state(result["document"])["status"], "current")
        self.assertEqual(
            result["document"]["metadata"]["source_requirements"],
            self.doc["metadata"]["source_requirements"],
        )
        plan["operations"][0]["spec"] = {"thickness_mm": 3.5}
        with self.assertRaisesRegex(ValueError, "retained requirements"):
            apply_plan(self.doc, plan, "Change all panels to 4 mm")


if __name__ == "__main__":
    unittest.main()
