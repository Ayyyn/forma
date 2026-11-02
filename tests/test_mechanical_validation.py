import math
import unittest

import cadquery as cq

from crate_studio.mechanical_design import design_spur_train
from crate_studio.mechanical_features import gear
from crate_studio.mechanical_validation import analyze_gears, mesh_relation
from crate_studio.workspace_geometry import build_document
from crate_studio.workspace_agent import apply_plan


class MechanicalDesignTests(unittest.TestCase):
    def test_integer_design_matches_distances_and_target_on_varied_layouts(self):
        for centers, speed in [
            ([[0, 0], [20, 0], [50, 0]], 55),
            ([[5, 7], [5, 31], [5, 67]], 50),
            ([[0, 0], [40, 0]], -60),
        ]:
            features, proof = design_spur_train(
                dict(centers=centers, input_rpm=120, output_rpm=speed, thickness=6)
            )
            self.assertLessEqual(abs(proof["kinematic_output_rpm"] / speed - 1), 0.05)
            for a, b in zip(features, features[1:]):
                pa, pb = a["params"], b["params"]
                self.assertAlmostEqual(
                    math.dist([pa["cx"], pa["cy"]], [pb["cx"], pb["cy"]]),
                    pa["module"] * (pa["teeth"] + pb["teeth"]) / 2,
                )
            self.assertGreaterEqual(min(proof["teeth"]), 18)

    def test_fixed_module_and_wrong_direction_are_not_silently_relaxed(self):
        base = dict(
            centers=[[0, 0], [40, 0]], input_rpm=120, output_rpm=-60, thickness=4
        )
        with self.assertRaisesRegex(ValueError, "direction"):
            design_spur_train({**base, "output_rpm": 60})
        with self.assertRaisesRegex(ValueError, "No integer"):
            design_spur_train({**base, "module": 9})
        features, _ = design_spur_train({**base, "module": 4 / 3})
        self.assertTrue(
            all(abs(f["params"]["module"] - 4 / 3) < 1e-8 for f in features)
        )

    def test_stub_tooth_design_uses_derived_undercut_limit_and_explicit_clearance(self):
        features, proof = design_spur_train(
            dict(
                centers=[[0, 0], [20, 0], [50, 0]],
                input_rpm=120,
                output_rpm=55,
                thickness=6,
                addendum_coeff=0.8,
                dedendum_coeff=1,
                tangential_backlash=0.2,
            )
        )
        minimum = math.ceil(1.6 / math.sin(math.radians(20)) ** 2)
        self.assertGreaterEqual(min(proof["teeth"]), minimum)
        self.assertLessEqual(abs(proof["kinematic_output_rpm"] / 55 - 1), 0.05)
        body = gear("spur_gear", features[0]["params"])
        self.assertTrue(body.isValid())
        self.assertEqual(features[0]["params"]["tangential_backlash"], 0.2)

    def test_invalid_solver_inputs_rejected(self):
        base = dict(
            centers=[[0, 0], [40, 0]], input_rpm=120, output_rpm=-60, thickness=4
        )
        for patch in (
            {"centers": [[0, 0], [0, 0]]},
            {"input_rpm": 0},
            {"max_teeth": True},
            {"centers": [[True, 0], [40, 0]]},
            {"prefix": "../bad"},
            {"unknown": 1},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                design_spur_train({**base, **patch})

    def test_chordal_native_profile_preserves_material_bore_and_bounds(self):
        p = dict(module=1, teeth=18, thickness=4, bore_diameter=4)
        smooth = gear("spur_gear", p)
        chordal = gear("spur_gear", {**p, "outline_tolerance": 0.025})
        self.assertTrue(chordal.isValid())
        self.assertEqual(len(chordal.Solids()), 1)
        difference = abs(smooth.cut(chordal).Volume()) + abs(
            chordal.cut(smooth).Volume()
        )
        self.assertLess(difference / smooth.Volume(), 0.01)
        self.assertLess(
            abs(smooth.BoundingBox().xlen - chordal.BoundingBox().xlen), 0.05
        )
        self.assertLess(
            chordal.intersect(cq.Solid.makeCylinder(1.99, 4)).Volume(), 1e-7
        )
        with self.assertRaises(ValueError):
            gear("spur_gear", {**p, "outline_tolerance": 0.1})

    def test_preflight_rejects_real_tooth_intersection(self):
        features = [
            {
                "id": "a",
                "type": "spur_gear",
                "params": dict(module=1, teeth=18, thickness=3),
            },
            {
                "id": "b",
                "type": "spur_gear",
                "params": dict(module=1, teeth=18, thickness=3, cx=18),
            },
        ]
        result = build_document({"features": features})
        self.assertFalse(result["checks"]["passed"])
        report = result["checks"]["mechanical"]
        self.assertGreater(report["pairs"][0]["rest_intersection_mm3"], 0.01)
        self.assertIn("intersect", result["checks"]["error"])

    def test_train_action_expands_to_editable_gears_and_preserves_existing_work(self):
        plan = {
            "summary": "A direct train",
            "status": "ready",
            "questions": [],
            "evidence": [{"quote": "two gears"}],
            "operations": [
                {
                    "action": "spur_train",
                    "spec": {
                        "centers": [[0, 0], [40, 0]],
                        "input_rpm": 120,
                        "output_rpm": -60,
                        "thickness": 4,
                        "bore_diameter": 4,
                        "bore_flat": 1.5,
                        "module": 4 / 3,
                    },
                }
            ],
        }
        result = apply_plan({"features": []}, plan, "Create two gears")
        self.assertEqual(result["status"], "ready", result["result"]["checks"])
        features = result["document"]["features"]
        self.assertEqual([f["type"] for f in features], ["spur_gear", "spur_gear"])
        edited = {**features[0], "params": {**features[0]["params"], "thickness": 5}}
        self.assertTrue(build_document({"features": [edited]})["checks"]["passed"])
        with self.assertRaisesRegex(ValueError, "already exist"):
            apply_plan(result["document"], plan, "Create two gears")

    def test_bevel_relation_uses_supplied_axes_apex_and_tooth_ratio(self):
        a = {
            "type": "bevel_gear",
            "params": dict(module=1, teeth=18, cone_angle=45, axis="-Z"),
        }
        b = {
            "type": "bevel_gear",
            "params": dict(module=1, teeth=18, cone_angle=45, axis="-X"),
        }
        relation = mesh_relation(a, b)
        self.assertEqual(relation["ratio"], -1)
        self.assertEqual(relation["cone_angle_error_deg"], 0)
        b["params"]["cone_angle"] = 40
        self.assertEqual(mesh_relation(a, b)["cone_angle_error_deg"], 5)
        b["params"]["cx"] = 1
        self.assertIsNone(mesh_relation(a, b))

    def test_mixed_histories_are_explicitly_unchecked(self):
        report = analyze_gears(
            {"features": [{"type": "spur_gear"}, {"type": "cut_hole"}]},
            {"parts": [{}, {}]},
        )
        self.assertFalse(report["checked"])
        self.assertIsNone(report["passed"])


if __name__ == "__main__":
    unittest.main()
