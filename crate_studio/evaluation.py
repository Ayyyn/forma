"""Independent analytic checks for a restricted rectangular crate family.

These are constructed engineering development fixtures, not customer cases,
external CAD benchmark results, or evidence of material/structural qualification.
This module never performs network requests or starts paid model runs.
"""

from __future__ import annotations

from decimal import Decimal


def analytic_geometry(spec: dict, density_kg_m3: float) -> dict:
    """Compute a rectangular shell by envelope-minus-cavity, independently.

    Assumptions: uniform stock thickness, full-width/depth bottom, optional
    full-width/depth lid, walls reaching the clear internal height. No gaps,
    joints, fasteners, holes, tolerances or material deformation are represented.
    """

    def number(key):
        value = spec[key]
        if isinstance(value, bool):
            raise ValueError(f"{key} must be a finite positive number")
        result = Decimal(str(value))
        if not result.is_finite() or result <= 0:
            raise ValueError(f"{key} must be a finite positive number")
        return result

    w, d, h, t = (
        number(k)
        for k in ("inner_width_mm", "inner_depth_mm", "inner_height_mm", "thickness_mm")
    )
    if type(spec.get("lid")) is not bool:
        raise ValueError("lid must be boolean")
    density = Decimal(str(density_kg_m3))
    if not density.is_finite() or density <= 0:
        raise ValueError("density must be finite and positive")
    ow, od, oh = w + 2 * t, d + 2 * t, h + t * (2 if spec["lid"] else 1)
    cavity = w * d * h
    solid = ow * od * oh - cavity
    return {
        "outer_width_mm": float(ow),
        "outer_depth_mm": float(od),
        "outer_height_mm": float(oh),
        "capacity_l": float(cavity / Decimal(1_000_000)),
        "solid_volume_mm3": float(solid),
        "mass_kg": float(solid * density / Decimal(1_000_000_000)),
    }


def independent_constraints(
    spec: dict, requirements: dict, density_kg_m3: float
) -> dict:
    """Check explicit engineering limits without consulting engine verdicts."""
    values = analytic_geometry(spec, density_kg_m3)
    checks = {}
    for axis in ("width", "depth", "height"):
        key = f"max_outer_{axis}_mm"
        if requirements.get(key) is not None:
            checks[key] = values[f"outer_{axis}_mm"] <= float(requirements[key]) + 1e-8
    if requirements.get("min_capacity_l") is not None:
        checks["min_capacity_l"] = values["capacity_l"] + 1e-8 >= float(
            requirements["min_capacity_l"]
        )
    if requirements.get("max_mass_kg") is not None:
        checks["max_mass_kg"] = (
            values["mass_kg"] <= float(requirements["max_mass_kg"]) + 1e-8
        )
    return {"metrics": values, "checks": checks, "feasible": all(checks.values())}


DENSITIES = {
    "birch_plywood": 650,
    "polypropylene": 905,
    "aluminum": 2700,
    "steel": 7850,
}
STOCK = {
    "birch_plywood": [6, 9, 12, 15, 18, 21],
    "polypropylene": [3, 4, 5, 6, 8, 10, 12, 15, 20],
    "aluminum": [1, 1.5, 2, 3, 4, 5, 6],
    "steel": [0.8, 1, 1.2, 1.5, 2, 3, 4],
}


def scenarios() -> list[dict]:
    """Fixed, transparent fixtures; these are not statistically held-out tasks."""
    spec = dict(
        name="Analytic crate",
        inner_width_mm=600,
        inner_depth_mm=400,
        inner_height_mm=300,
        thickness_mm=12,
        material="birch_plywood",
        lid=False,
    )
    req = dict(
        min_capacity_l=72,
        max_outer_width_mm=650,
        max_outer_depth_mm=450,
        max_outer_height_mm=350,
        max_mass_kg=100,
        max_floor_deflection_mm=3,
        payload_kg=0,
        lock_inner_dimensions=True,
        objective="minimize_mass",
    )
    definitions = [
        ("open_stock", {}, {}, True, "Ordinary open box with exact clear capacity"),
        ("closed_stock", {"lid": True}, {}, True, "Lid adds one outer-footprint panel"),
        (
            "pp_revision",
            {"material": "polypropylene", "thickness_mm": 8},
            {},
            True,
            "Material revision preserves clear dimensions",
        ),
        (
            "envelope_impossible",
            {},
            {"max_outer_width_mm": 610},
            False,
            "Even thinnest plywood stock exceeds outer width",
        ),
        (
            "capacity_locked_impossible",
            {},
            {"min_capacity_l": 73},
            False,
            "Locked dimensions cannot gain capacity",
        ),
        (
            "mass_impossible",
            {},
            {"max_mass_kg": 0.01},
            False,
            "All listed stock exceeds mass budget",
        ),
        (
            "exact_envelope",
            {},
            {
                "max_outer_width_mm": 612,
                "max_outer_depth_mm": 412,
                "max_outer_height_mm": 306,
            },
            True,
            "Only 6 mm plywood fits exact outer limits",
        ),
        (
            "steel_stock",
            {"material": "steel", "thickness_mm": 2},
            {},
            True,
            "Enumerate steel stock without changing cavity",
        ),
    ]
    return [
        dict(
            id=ident,
            spec={**spec, **delta},
            requirements={**req, **limits},
            expected_optimizer_feasible=expected,
            rationale=rationale,
        )
        for ident, delta, limits, expected, rationale in definitions
    ]


def offline_report() -> dict:
    """Run only deterministic implementation against independent arithmetic."""
    from .engine import evaluate, optimize

    rows = []
    for case in scenarios():
        initial = evaluate(case["spec"], case["requirements"])
        solution = optimize(case["spec"], case["requirements"])
        expected = analytic_geometry(case["spec"], DENSITIES[case["spec"]["material"]])
        errors = {
            key: initial["metrics"][key] - expected[key]
            for key in (
                "outer_width_mm",
                "outer_depth_mm",
                "outer_height_mm",
                "capacity_l",
                "mass_kg",
            )
        }
        best = solution.get("best")
        preserved = best is None or all(
            best["spec"][f"inner_{axis}_mm"] == case["spec"][f"inner_{axis}_mm"]
            for axis in ("width", "depth", "height")
        )
        rows.append(
            {
                "id": case["id"],
                "rationale": case["rationale"],
                "metric_errors": errors,
                "dimensions_preserved": preserved,
                "expected_optimizer_feasible": case["expected_optimizer_feasible"],
                "observed_optimizer_status": solution["status"],
                "passed": all(abs(v) < 1e-8 for v in errors.values())
                and preserved
                and (
                    (solution["status"] == "feasible")
                    == case["expected_optimizer_feasible"]
                ),
            }
        )
    return {
        "protocol": STUDY_PROTOCOL,
        "cases": rows,
        "passed": all(row["passed"] for row in rows),
        "model_results": None,
    }


def score_proposals(case: dict, proposals: list[dict]) -> dict:
    """Score saved model designs against frozen requirements, never model claims.

    No model may relax requirements or change the selected material/lid. Direct
    and feedback arms receive identical deterministic final-candidate selection.
    Caller records actual provider tokens, costs and latency separately.
    """
    from .engine import evaluate

    if len(proposals) > STUDY_PROTOCOL["model_arm_caps"]["calls_per_case"]:
        raise ValueError("Proposal count exceeds the frozen comparison cap")
    accepted, attempts = [], []
    for proposal in proposals:
        try:
            spec = proposal.get("spec", proposal)
            if (
                spec.get("material") != case["spec"]["material"]
                or spec.get("lid") != case["spec"]["lid"]
            ):
                raise ValueError("Proposal changed a fixed material or lid requirement")
            if case["requirements"].get("lock_inner_dimensions", True):
                if any(
                    spec.get(f"inner_{axis}_mm") != case["spec"][f"inner_{axis}_mm"]
                    for axis in ("width", "depth", "height")
                ):
                    raise ValueError("Proposal changed locked clear dimensions")
            result = evaluate(spec, case["requirements"])
            independent = independent_constraints(
                result["spec"],
                case["requirements"],
                DENSITIES[result["spec"]["material"]],
            )
            passed = result["passed"] and independent["feasible"]
            attempts.append(
                {
                    "passed": passed,
                    "checks": result["checks"],
                    "metrics": result["metrics"],
                }
            )
            if passed:
                accepted.append(result)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            attempts.append({"passed": False, "error": str(exc)})
    if case["requirements"].get("objective", "minimize_mass") == "minimize_mass":
        accepted.sort(key=lambda item: item["metrics"]["mass_kg"])
    else:
        accepted.sort(
            key=lambda item: (
                -item["metrics"]["capacity_l"],
                item["metrics"]["mass_kg"],
            )
        )
    return {
        "case_id": case["id"],
        "attempts": attempts,
        "best": accepted[0] if accepted else None,
        "feasible_proposal_found": bool(accepted),
        "note": "No feasible proposal is not proof of infeasibility.",
    }


STUDY_PROTOCOL = {
    "status": "offline_only_no_model_results",
    "case_origin": "constructed engineering development fixtures",
    "customer_validation": False,
    "physical_validation": False,
    "arms": ["deterministic_stock_search", "meta_direct", "meta_checker_feedback"],
    "model_arm_caps": {
        "calls_per_case": 2,
        "direct_max_calls": 1,
        "feedback_max_calls": 2,
        "max_output_tokens_per_call": 4096,
    },
    "direct_arm": "One proposal without checker feedback; current agent behavior.",
    "feedback_arm": "First proposal and optional deterministic checker feedback revision; current agent stops early on ready/clarify.",
    "fairness": "Current agent arms do NOT have equal inference budgets. A future equal-budget comparison requires a separate frozen runner (e.g. two independent direct proposals versus two feedback turns). No such comparative results are claimed. Report actual tokens, latency, calls and cost. Deterministic search uses no model calls.",
    "claims": "Feasibility, geometry accuracy and dimension preservation within the supported family only. No general Meta advantage, customer time saving, strength or manufacturing readiness claim.",
}


if __name__ == "__main__":
    import json

    print(json.dumps(offline_report(), indent=2, allow_nan=False))
