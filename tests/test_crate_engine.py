"""Independent geometry and bounded stock-search checks; no physical validation."""

import math
import random
import unittest

from crate_studio.engine import evaluate, optimize
from crate_studio.evaluation import (
    DENSITIES,
    STOCK,
    analytic_geometry,
    offline_report,
    scenarios,
    score_proposals,
)


class CrateEngineeringTests(unittest.TestCase):
    def setUp(self):
        case = scenarios()[0]
        self.spec, self.req = case["spec"], case["requirements"]

    def test_independent_closed_and_open_shell_volumes(self):
        for material, density in DENSITIES.items():
            for lid in (False, True):
                with self.subTest(material=material, lid=lid):
                    spec = {
                        **self.spec,
                        "material": material,
                        "thickness_mm": STOCK[material][0],
                        "lid": lid,
                    }
                    actual = evaluate(spec, self.req)
                    expected = analytic_geometry(spec, density)
                    for key in (
                        "outer_width_mm",
                        "outer_depth_mm",
                        "outer_height_mm",
                        "capacity_l",
                        "mass_kg",
                    ):
                        self.assertAlmostEqual(
                            actual["metrics"][key], expected[key], places=8
                        )
                    self.assertAlmostEqual(
                        actual["metrics"]["material_volume_mm3"],
                        expected["solid_volume_mm3"],
                        places=6,
                    )
                    self.assertEqual(len(actual["panels"]), 6 if lid else 5)

    def test_panels_fill_shell_without_volume_overlap(self):
        result = evaluate(self.spec, self.req)
        volume = sum(math.prod(p["size_mm"]) for p in result["panels"])
        self.assertAlmostEqual(
            volume, analytic_geometry(self.spec, 650)["solid_volume_mm3"]
        )
        for i, first in enumerate(result["panels"]):
            for second in result["panels"][i + 1 :]:
                overlap = [
                    min(
                        first["center_mm"][a] + first["size_mm"][a] / 2,
                        second["center_mm"][a] + second["size_mm"][a] / 2,
                    )
                    - max(
                        first["center_mm"][a] - first["size_mm"][a] / 2,
                        second["center_mm"][a] - second["size_mm"][a] / 2,
                    )
                    for a in range(3)
                ]
                self.assertFalse(
                    all(length > 1e-8 for length in overlap),
                    (first["id"], second["id"]),
                )

    def test_material_change_does_not_change_clear_capacity(self):
        old = evaluate(self.spec, self.req)
        new = evaluate(
            {**self.spec, "material": "polypropylene", "thickness_mm": 8}, self.req
        )
        self.assertEqual(old["metrics"]["capacity_l"], new["metrics"]["capacity_l"])
        self.assertEqual(new["metrics"]["outer_width_mm"], 616)
        self.assertNotEqual(old["metrics"]["mass_kg"], new["metrics"]["mass_kg"])

    def test_exact_capacity_and_envelope_boundary(self):
        self.assertTrue(
            evaluate(
                self.spec,
                {
                    **self.req,
                    "max_outer_width_mm": 624,
                    "max_outer_depth_mm": 424,
                    "max_outer_height_mm": 312,
                },
            )["passed"]
        )
        self.assertFalse(
            evaluate(self.spec, {**self.req, "min_capacity_l": 72.001})["passed"]
        )
        self.assertFalse(
            evaluate(self.spec, {**self.req, "max_outer_width_mm": 623.999})["passed"]
        )

    def test_stock_optimizer_matches_independent_enumeration(self):
        for material in STOCK:
            with self.subTest(material=material):
                spec = {
                    **self.spec,
                    "material": material,
                    "thickness_mm": STOCK[material][-1],
                }
                result = optimize(spec, self.req)
                self.assertEqual(result["status"], "feasible")
                self.assertEqual(
                    result["best"]["spec"]["thickness_mm"], STOCK[material][0]
                )
                expected = min(
                    analytic_geometry({**spec, "thickness_mm": t}, DENSITIES[material])[
                        "mass_kg"
                    ]
                    for t in STOCK[material]
                )
                self.assertAlmostEqual(
                    result["best"]["metrics"]["mass_kg"], expected, places=8
                )
                for axis in ("width", "depth", "height"):
                    self.assertEqual(
                        result["best"]["spec"][f"inner_{axis}_mm"],
                        spec[f"inner_{axis}_mm"],
                    )

    def test_infeasible_returns_no_best(self):
        for changes in (
            {"min_capacity_l": 73},
            {"max_outer_width_mm": 610},
            {"max_mass_kg": 0.01},
        ):
            with self.subTest(changes=changes):
                result = optimize(self.spec, {**self.req, **changes})
                self.assertEqual(result["status"], "infeasible")
                self.assertIsNone(result["best"])

    def test_nonstock_thickness_cannot_be_cleared(self):
        self.assertFalse(evaluate({**self.spec, "thickness_mm": 7}, self.req)["passed"])

    def test_unlocked_capacity_search_can_stop_below_full_envelope(self):
        req = {
            **self.req,
            "lock_inner_dimensions": False,
            "objective": "maximize_capacity",
            "min_capacity_l": 1,
            "max_mass_kg": 2,
        }
        witness = {
            **self.spec,
            "inner_width_mm": 100,
            "inner_depth_mm": 100,
            "inner_height_mm": 100,
            "thickness_mm": 6,
        }
        self.assertTrue(evaluate(witness, req)["passed"])
        result = optimize(self.spec, req)
        self.assertEqual(result["status"], "feasible")
        self.assertGreaterEqual(result["best"]["metrics"]["capacity_l"], 1)
        self.assertLessEqual(result["best"]["metrics"]["mass_kg"], 2 + 1e-7)

    def test_invalid_dimensions_rejected(self):
        for value in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(value=value):
                with self.assertRaises((ValueError, TypeError)):
                    evaluate({**self.spec, "inner_width_mm": value}, self.req)

    def test_floor_screen_cubic_thickness_scaling(self):
        req = {**self.req, "payload_kg": 10}
        thin = evaluate({**self.spec, "thickness_mm": 6}, req)["metrics"][
            "floor_deflection_mm"
        ]
        thick = evaluate({**self.spec, "thickness_mm": 12}, req)["metrics"][
            "floor_deflection_mm"
        ]
        self.assertGreater(thin, 0)
        self.assertAlmostEqual(thin / thick, 8, places=8)

    def test_floor_screen_matches_independently_integrated_beam_equation(self):
        # E I y'''' = q, y(0)=y(L)=0, y''(0)=y''(L)=0.
        # Integrating gives y(x)=q*(x^4-2*L*x^3+L^3*x)/(24*E*I).
        # Millimetres and N/mm^2 keep the resulting displacement in mm.
        payload, span, breadth, thickness, modulus = 10, 600, 400, 12, 10000
        q = payload * 9.80665 / span
        inertia = breadth * thickness**3 / 12
        x = span / 2
        expected = q * (x**4 - 2 * span * x**3 + span**3 * x) / (24 * modulus * inertia)
        actual = evaluate(self.spec, {**self.req, "payload_kg": payload})["metrics"][
            "floor_deflection_mm"
        ]
        self.assertAlmostEqual(actual, expected, places=12)

    def test_constructed_scenario_report(self):
        report = offline_report()
        self.assertTrue(report["passed"], report["cases"])
        self.assertIsNone(report["model_results"])

    def test_model_cannot_change_frozen_constraints(self):
        case = scenarios()[0]
        proposal = {
            "spec": {**self.spec, "inner_width_mm": 601},
            "requirements": {**self.req, "lock_inner_dimensions": False},
        }
        self.assertFalse(score_proposals(case, [proposal])["feasible_proposal_found"])
        invalid = {
            "spec": {**self.spec, "thickness_mm": 7},
            "requirements": {**self.req, "max_mass_kg": 1000},
            "passed": True,
        }
        self.assertFalse(score_proposals(case, [invalid])["feasible_proposal_found"])
        self.assertTrue(
            score_proposals(case, [{**self.spec, "thickness_mm": 6}])[
                "feasible_proposal_found"
            ]
        )

    def test_model_proposal_budget_enforced(self):
        with self.assertRaises(ValueError):
            score_proposals(scenarios()[0], [self.spec] * 3)

    def test_seeded_geometry_against_decimal_oracle(self):
        rng = random.Random(20261031)
        # Development/property checks, not independent benchmark samples.
        for material, stock in STOCK.items():
            for lid in (False, True):
                for index in range(48):
                    dims = [rng.uniform(20, 3000) for _ in range(3)]
                    if index == 0:
                        dims = [20, 20, 20]
                    elif index == 1:
                        dims = [3000, 3000, 3000]
                    t = rng.choice([value for value in stock if value < min(dims)])
                    spec = {
                        **self.spec,
                        "material": material,
                        "lid": lid,
                        "thickness_mm": t,
                        **dict(
                            zip(
                                ("inner_width_mm", "inner_depth_mm", "inner_height_mm"),
                                dims,
                            )
                        ),
                    }
                    with self.subTest(material=material, lid=lid, index=index):
                        actual = evaluate(spec, self.req)["metrics"]
                        expected = analytic_geometry(spec, DENSITIES[material])
                        for key in (
                            "outer_width_mm",
                            "outer_depth_mm",
                            "outer_height_mm",
                            "capacity_l",
                            "mass_kg",
                        ):
                            self.assertTrue(math.isfinite(actual[key]))
                            self.assertTrue(
                                math.isclose(
                                    actual[key],
                                    expected[key],
                                    rel_tol=2e-12,
                                    abs_tol=1e-8,
                                ),
                                key,
                            )
                        self.assertTrue(
                            math.isclose(
                                actual["material_volume_mm3"],
                                expected["solid_volume_mm3"],
                                rel_tol=2e-12,
                                abs_tol=1e-6,
                            )
                        )

    def test_small_dimensions_reject_or_skip_invalid_stock(self):
        small = {
            **self.spec,
            "inner_width_mm": 20,
            "inner_depth_mm": 20,
            "inner_height_mm": 20,
            "thickness_mm": 6,
        }
        for t in (20, 21):
            with self.subTest(t=t), self.assertRaises(ValueError):
                evaluate({**small, "thickness_mm": t}, self.req)
        req = {
            **self.req,
            "min_capacity_l": 0.008,
            "max_outer_width_mm": 70,
            "max_outer_depth_mm": 70,
            "max_outer_height_mm": 70,
        }
        for locked in (True, False):
            for objective in ("minimize_mass", "maximize_capacity"):
                with self.subTest(locked=locked, objective=objective):
                    result = optimize(
                        small,
                        {
                            **req,
                            "lock_inner_dimensions": locked,
                            "objective": objective,
                        },
                    )
                    self.assertEqual(result["status"], "feasible")
                    for row in result["candidates"]:
                        s = row["spec"]
                        self.assertLess(
                            s["thickness_mm"],
                            min(
                                s[f"inner_{a}_mm"] for a in ("width", "depth", "height")
                            ),
                        )
                    if locked:
                        self.assertNotIn(
                            21,
                            [
                                row["spec"]["thickness_mm"]
                                for row in result["candidates"]
                            ],
                        )

    def test_unlocked_max_capacity_dominates_independent_feasible_scale_grid(self):
        moduli = {
            "birch_plywood": 10000,
            "polypropylene": 1300,
            "aluminum": 69000,
            "steel": 210000,
        }
        req = {
            **self.req,
            "lock_inner_dimensions": False,
            "objective": "maximize_capacity",
            "min_capacity_l": 1,
            "max_mass_kg": 2,
            "payload_kg": 10,
            "max_floor_deflection_mm": 0.3,
        }
        for material in STOCK:
            for lid in (False, True):
                with self.subTest(material=material, lid=lid):
                    spec = {
                        **self.spec,
                        "material": material,
                        "lid": lid,
                        "thickness_mm": STOCK[material][0],
                    }
                    feasible_capacity = []
                    for t in STOCK[material]:
                        caps = [650 - 2 * t, 450 - 2 * t, 350 - t * (2 if lid else 1)]
                        for step in range(1, 101):
                            dims = [c * step / 100 for c in caps]
                            if min(dims) < max(20, t + 0.001):
                                continue
                            candidate = {
                                **spec,
                                "thickness_mm": t,
                                **dict(
                                    zip(
                                        (
                                            "inner_width_mm",
                                            "inner_depth_mm",
                                            "inner_height_mm",
                                        ),
                                        dims,
                                    )
                                ),
                            }
                            metrics = analytic_geometry(candidate, DENSITIES[material])
                            w, d, _ = dims
                            inertia = d * t**3 / 12
                            q = req["payload_kg"] * 9.80665 / w
                            displacement = (
                                5 * q * w**4 / (384 * moduli[material] * inertia)
                            )
                            if (
                                metrics["capacity_l"] >= 1
                                and metrics["mass_kg"] <= 2
                                and displacement <= 0.3
                            ):
                                feasible_capacity.append(metrics["capacity_l"])
                    self.assertTrue(
                        feasible_capacity,
                        "Test configuration must contain an independent feasible witness",
                    )
                    result = optimize(spec, req)
                    self.assertEqual(result["status"], "feasible")
                    metrics = result["best"]["metrics"]
                    self.assertGreaterEqual(
                        metrics["capacity_l"] + 1e-7, max(feasible_capacity)
                    )
                    self.assertLessEqual(metrics["mass_kg"], 2 + 1.01e-7)
                    self.assertLessEqual(metrics["floor_deflection_mm"], 0.3 + 1.01e-7)

    def test_unlocked_min_mass_preserves_capacity_and_screens_payload(self):
        req = {
            **self.req,
            "lock_inner_dimensions": False,
            "min_capacity_l": 10,
            "payload_kg": 10,
            "max_floor_deflection_mm": 0.2,
        }
        scale = (10 / 72) ** (1 / 3)
        expected_dims = [600 * scale, 400 * scale, 300 * scale]
        witnesses = []
        for t in STOCK["birch_plywood"]:
            candidate = {
                **self.spec,
                "thickness_mm": t,
                **dict(
                    zip(
                        ("inner_width_mm", "inner_depth_mm", "inner_height_mm"),
                        expected_dims,
                    )
                ),
            }
            metric = analytic_geometry(candidate, 650)
            w, d, _ = expected_dims
            deflection = 5 * (10 * 9.80665 / w) * w**4 / (384 * 10000 * (d * t**3 / 12))
            if deflection <= 0.2:
                witnesses.append((metric["mass_kg"], t))
        result = optimize(self.spec, req)
        self.assertEqual(result["status"], "feasible")
        self.assertAlmostEqual(result["best"]["metrics"]["capacity_l"], 10, places=7)
        self.assertEqual(result["best"]["spec"]["thickness_mm"], min(witnesses)[1])
        self.assertAlmostEqual(
            result["best"]["metrics"]["mass_kg"], min(witnesses)[0], places=7
        )


if __name__ == "__main__":
    unittest.main()
