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

    def test_custom_module_keeps_exact_ratio_and_smallest_safe_tooth_counts(self):
        features, proof = design_spur_train(
            dict(
                centers=[[0, 0], [20, 0], [50, 0]],
                input_rpm=120,
                output_rpm=55,
                thickness=10,
                pressure_angle=25,
                addendum_coeff=0.8,
                dedendum_coeff=1,
                tangential_backlash=0.2,
                module_policy="custom",
            )
        )
        self.assertAlmostEqual(proof["kinematic_output_rpm"], 55)
        self.assertEqual(proof["teeth"], [11, 15, 24])
        self.assertGreaterEqual(
            min(proof["teeth"]), math.ceil(1.6 / math.sin(math.radians(25)) ** 2)
        )
        for a, b in zip(features, features[1:]):
            self.assertAlmostEqual(
                math.dist([a["params"]["cx"], 0], [b["params"]["cx"], 0]),
                proof["module_mm"] * (a["params"]["teeth"] + b["params"]["teeth"]) / 2,
            )

    def test_compact_preset_preserves_explicit_profile_constraints(self):
        base = dict(
            centers=[[0, 0], [20, 0], [50, 0]],
            input_rpm=120,
            output_rpm=55,
            thickness=10,
            profile_preset="compact",
        )
        features, proof = design_spur_train(base)
        self.assertEqual(proof["teeth"], [11, 15, 24])
        self.assertEqual(features[0]["params"]["pressure_angle"], 25)
        constrained, _ = design_spur_train(
            {**base, "pressure_angle": 20, "addendum_coeff": 1, "outline_tolerance": 0}
        )
        self.assertEqual(constrained[0]["params"]["pressure_angle"], 20)
        self.assertEqual(constrained[0]["params"]["addendum_coeff"], 1)
        self.assertEqual(constrained[0]["params"]["outline_tolerance"], 0)

    def test_adaptive_profile_uses_complexity_budget_without_changing_explicit_geometry(
        self,
    ):
        base = dict(input_rpm=120, thickness=10, profile_preset="adaptive")
        two, proof = design_spur_train(
            {**base, "centers": [[0, 0], [40, 0]], "output_rpm": -60}
        )
        self.assertEqual(proof["teeth"], [12, 24])
        self.assertEqual(two[0]["params"]["addendum_coeff"], 1)
        three, proof = design_spur_train(
            {**base, "centers": [[0, 0], [20, 0], [50, 0]], "output_rpm": 55}
        )
        self.assertEqual(proof["teeth"], [11, 15, 24])
        self.assertEqual(three[0]["params"]["addendum_coeff"], 0.8)
        constrained, _ = design_spur_train(
            {
                **base,
                "centers": [[0, 0], [20, 0], [50, 0]],
                "output_rpm": 55,
                "addendum_coeff": 1,
            }
        )
        self.assertEqual(constrained[0]["params"]["addendum_coeff"], 1)

    def test_ratio_requirements_revalidate_after_target_change_and_suppression(self):
        from copy import deepcopy
        from crate_studio.workspace_cache import cached_build, cache_clear

        features, _ = design_spur_train(
            dict(
                centers=[[0, 0], [40, 0]],
                input_rpm=120,
                output_rpm=-60,
                thickness=4,
                module=4 / 3,
            )
        )
        target = dict(
            input_id=features[0]["id"],
            output_id=features[1]["id"],
            ratio=-0.5,
            tolerance=0.01,
            shaft_groups=[],
            quote="output -60 from input 120",
        )
        doc = {"features": features, "metadata": {"gear_targets": [target]}}
        cache_clear()
        good = cached_build(doc)
        self.assertTrue(good["checks"]["passed"], good["checks"])
        wrong = deepcopy(doc)
        wrong["metadata"]["gear_targets"][0]["ratio"] = 0.5
        bad = cached_build(wrong)
        self.assertFalse(bad["checks"]["passed"])
        self.assertIn("Signed", bad["checks"]["error"])
        self.assertTrue(good["checks"]["passed"])
        suppressed = deepcopy(doc)
        suppressed["features"][1]["suppressed"] = True
        self.assertFalse(cached_build(suppressed)["checks"]["passed"])

    def test_unknown_mechanical_policy_fails_before_inference(self):
        from crate_studio.workspace_agent import (
            propose_document,
            SYSTEM,
            MECHANICAL_SYSTEM,
        )

        self.assertNotIn('"action":"spur_train"', SYSTEM)
        self.assertIn('"action":"spur_train"', MECHANICAL_SYSTEM)
        with self.assertRaisesRegex(ValueError, "mechanical policy"):
            propose_document(
                {"features": []}, "Create gears", mechanical_policy="unknown"
            )

    def test_explicit_ratio_action_binds_source_and_rejects_wrong_direction(self):
        from copy import deepcopy

        features, _ = design_spur_train(
            dict(
                centers=[[0, 0], [40, 0]],
                input_rpm=120,
                output_rpm=-60,
                thickness=4,
                module=4 / 3,
            )
        )
        original = {"features": features}
        quote = "120 rpm input and -60 rpm output"
        operation = dict(
            action="gear_ratio",
            input_id=features[0]["id"],
            output_id=features[1]["id"],
            ratio=-0.5,
            tolerance=0.01,
            shaft_groups=[],
            quote=quote,
        )
        plan = dict(
            summary="Retain speed target",
            status="ready",
            questions=[],
            evidence=[{"quote": quote}],
            operations=[operation],
        )
        good = apply_plan(original, plan, quote)
        self.assertEqual(good["status"], "ready", good["result"]["checks"])
        wrong = deepcopy(plan)
        wrong["operations"][0]["ratio"] = 0.5
        self.assertEqual(apply_plan(original, wrong, quote)["status"], "invalid")
        fabricated = deepcopy(plan)
        fabricated["operations"][0]["quote"] = "validator message"
        with self.assertRaisesRegex(ValueError, "source quote"):
            apply_plan(original, fabricated, quote)
        self.assertNotIn("metadata", original)

    def test_compound_bevel_direction_accounts_for_explicit_shared_shaft_and_global_axes(
        self,
    ):
        from crate_studio.mechanical_validation import check_gear_targets

        features = []
        for fid, teeth, axis, point in [
            ("input", 14, "-Z", (12, 0, 18)),
            ("stage1", 20, "-X", (12, 0, 18)),
            ("stage2", 10, "+X", (40, 0, 18)),
            ("output", 14, "-Y", (40, 0, 18)),
        ]:
            features.append(
                dict(
                    id=fid,
                    type="bevel_gear",
                    params=dict(
                        teeth=teeth, axis=axis, cx=point[0], cy=point[1], z=point[2]
                    ),
                )
            )
        target = dict(
            input_id="input",
            output_id="output",
            ratio=-0.5,
            tolerance=0.01,
            shaft_groups=[["stage1", "stage2"]],
            quote="shared compound shaft",
        )
        doc = dict(features=features, metadata={"gear_targets": [target]})
        report = {
            "pairs": [
                dict(
                    features=["input", "stage1"],
                    ratio=-0.7,
                    sampled_minimum_gap_mm=0.01,
                ),
                dict(
                    features=["stage2", "output"],
                    ratio=-10 / 14,
                    sampled_minimum_gap_mm=0.01,
                ),
            ]
        }
        proof = check_gear_targets(doc, report)[0]
        self.assertTrue(proof["passed"])
        self.assertAlmostEqual(proof["actual_ratio"], -0.5)
        features[-1]["params"]["axis"] = "+Y"
        self.assertFalse(check_gear_targets(doc, report)[0]["passed"])

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
