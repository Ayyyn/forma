"""Deterministic design contract, panel layout and stock-size inverse design.

Millimetres, kilograms and litres throughout. A flat butt-joint panel family;
joining hardware, tolerances and material qualification require engineering review.
"""

from copy import deepcopy
import math

MATERIALS = {
    "birch_plywood": {
        "id": "birch_plywood",
        "name": "Birch plywood",
        "density_kg_m3": 650.0,
        "E_MPa": 10000.0,
        "stock_mm": [6, 9, 12, 15, 18, 21],
        "color": "#c7a67a",
    },
    "polypropylene": {
        "id": "polypropylene",
        "name": "Polypropylene",
        "density_kg_m3": 905.0,
        "E_MPa": 1300.0,
        "stock_mm": [3, 4, 5, 6, 8, 10, 12, 15, 20],
        "color": "#d8dedb",
    },
    "aluminum": {
        "id": "aluminum",
        "name": "Aluminum",
        "density_kg_m3": 2700.0,
        "E_MPa": 69000.0,
        "stock_mm": [1, 1.5, 2, 3, 4, 5, 6],
        "color": "#b1bdc8",
    },
    "steel": {
        "id": "steel",
        "name": "Steel",
        "density_kg_m3": 7850.0,
        "E_MPa": 210000.0,
        "stock_mm": [0.8, 1, 1.2, 1.5, 2, 3, 4],
        "color": "#81919e",
    },
}
DEFAULT_SPEC = {
    "name": "Field crate",
    "inner_width_mm": 600.0,
    "inner_depth_mm": 400.0,
    "inner_height_mm": 300.0,
    "thickness_mm": 12.0,
    "material": "birch_plywood",
    "lid": False,
}
DEFAULT_REQUIREMENTS = {
    "min_capacity_l": 72.0,
    "max_outer_width_mm": 650.0,
    "max_outer_depth_mm": 450.0,
    "max_outer_height_mm": 350.0,
    "max_mass_kg": 10.0,
    "lock_inner_dimensions": True,
    "objective": "minimize_mass",
    "payload_kg": 0.0,
    "max_floor_deflection_mm": 3.0,
}
DIMENSIONS = ["inner_width_mm", "inner_depth_mm", "inner_height_mm"]


def number(value, name, minimum=0.0, maximum=10000.0):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError(
            f"{name} must be a finite number from {minimum:g} to {maximum:g}"
        )
    return float(value)


def normalize_spec(spec):
    if not isinstance(spec, dict):
        raise ValueError("Design must be an object")
    if set(spec) - set(DEFAULT_SPEC):
        raise ValueError(
            "Unknown design fields: " + ", ".join(sorted(set(spec) - set(DEFAULT_SPEC)))
        )
    s = {**DEFAULT_SPEC, **spec}
    for key in DIMENSIONS:
        s[key] = number(s[key], key, 20, 3000)
    s["thickness_mm"] = number(s["thickness_mm"], "thickness_mm", 0.5, 30)
    if s["thickness_mm"] >= min(s[k] for k in DIMENSIONS):
        raise ValueError("Panel thickness must be smaller than every clear dimension")
    if s["material"] not in MATERIALS:
        raise ValueError("Select a supported material profile")
    if type(s["lid"]) is not bool:
        raise ValueError("lid must be true or false")
    if not isinstance(s["name"], str) or not s["name"].strip() or len(s["name"]) > 100:
        raise ValueError("Name must contain 1–100 characters")
    s["name"] = s["name"].strip()
    return s


def normalize_requirements(requirements=None):
    if requirements is not None and not isinstance(requirements, dict):
        raise ValueError("Requirements must be an object")
    r = {**DEFAULT_REQUIREMENTS, **(requirements or {})}
    if set(r) - set(DEFAULT_REQUIREMENTS):
        raise ValueError(
            "Unknown requirement fields: "
            + ", ".join(sorted(set(r) - set(DEFAULT_REQUIREMENTS)))
        )
    for key in [
        "min_capacity_l",
        "max_outer_width_mm",
        "max_outer_depth_mm",
        "max_outer_height_mm",
        "max_mass_kg",
        "max_floor_deflection_mm",
    ]:
        r[key] = number(r[key], key, 0.001, 1e7)
    r["payload_kg"] = number(r["payload_kg"], "payload_kg", 0, 10000)
    if type(r["lock_inner_dimensions"]) is not bool:
        raise ValueError("lock_inner_dimensions must be true or false")
    if r["objective"] not in ["minimize_mass", "maximize_capacity"]:
        raise ValueError("Unknown design objective")
    return r


def panel_layout(spec):
    s = normalize_spec(spec)
    w, d, h, t = [s[k] for k in [*DIMENSIONS, "thickness_mm"]]
    ow = w + 2 * t
    od = d + 2 * t

    def p(id, name, size, center):
        return {
            "id": id,
            "name": name,
            "size_mm": size,
            "center_mm": center,
            "material": s["material"],
        }

    panels = [
        p("base", "Base", [ow, od, t], [0, 0, t / 2]),
        p("front", "Front", [ow, t, h], [0, -(d + t) / 2, t + h / 2]),
        p("back", "Back", [ow, t, h], [0, (d + t) / 2, t + h / 2]),
        p("left", "Left", [t, d, h], [-(w + t) / 2, 0, t + h / 2]),
        p("right", "Right", [t, d, h], [(w + t) / 2, 0, t + h / 2]),
    ]
    if s["lid"]:
        panels.append(p("lid", "Lid", [ow, od, t], [0, 0, h + 1.5 * t]))
    return panels


def evaluate(spec, requirements=None):
    s = normalize_spec(spec)
    r = normalize_requirements(requirements)
    ps = panel_layout(s)
    w, d, h, t = [s[k] for k in [*DIMENSIONS, "thickness_mm"]]
    mat = MATERIALS[s["material"]]
    volume = sum(math.prod(p["size_mm"]) for p in ps)
    deflection = (
        5 * r["payload_kg"] * 9.80665 * w**3 / (32 * mat["E_MPa"] * d * t**3)
        if r["payload_kg"]
        else 0.0
    )
    metrics = {
        "outer_width_mm": w + 2 * t,
        "outer_depth_mm": d + 2 * t,
        "outer_height_mm": h + (2 if s["lid"] else 1) * t,
        "capacity_l": w * d * h / 1e6,
        "mass_kg": volume * mat["density_kg_m3"] / 1e9,
        "panel_count": len(ps),
        "material_volume_mm3": volume,
        "floor_deflection_mm": deflection,
    }
    checks = []

    def check(id, label, actual, limit, unit, lower=False, detail=""):
        ok = actual + 1e-7 >= limit if lower else actual <= limit + 1e-7
        checks.append(
            {
                "id": id,
                "label": label,
                "status": "pass" if ok else "fail",
                "actual": actual,
                "limit": limit,
                "unit": unit,
                "detail": detail,
            }
        )

    check(
        "capacity",
        "Clear capacity",
        metrics["capacity_l"],
        r["min_capacity_l"],
        "L",
        True,
    )
    for axis in ["width", "depth", "height"]:
        check(
            "envelope_" + axis,
            "Outside " + axis,
            metrics["outer_" + axis + "_mm"],
            r["max_outer_" + axis + "_mm"],
            "mm",
        )
    check(
        "mass",
        "Estimated empty mass",
        metrics["mass_kg"],
        r["max_mass_kg"],
        "kg",
        detail="Nominal profile density; excludes fasteners, adhesive and finish.",
    )
    stock = any(abs(t - x) < 1e-7 for x in mat["stock_mm"])
    checks.append(
        {
            "id": "stock",
            "label": "Configured stock thickness",
            "status": "pass" if stock else "fail",
            "actual": t,
            "limit": mat["stock_mm"],
            "unit": "mm",
            "detail": "Project stock catalogue, not verified supplier availability.",
        }
    )
    if r["payload_kg"]:
        check(
            "floor_deflection",
            "Floor deflection screening",
            deflection,
            r["max_floor_deflection_mm"],
            "mm",
            detail="UDL, linear elastic simply supported full-depth beam strip spanning inner width; ideal supports. Not a strength or assembly rating.",
        )
    notes = [
        "Butt-joint panel layout. Joining method, fasteners, tolerances and edge finishing require review.",
        "Geometry checks do not qualify strength, creep, impact, moisture, fire behavior or manufacturing readiness.",
        "Material densities, elastic moduli and stock sizes are configurable reference assumptions; no grade or supplier is implied.",
    ]
    return {
        "spec": s,
        "requirements": r,
        "metrics": metrics,
        "panels": ps,
        "checks": checks,
        "passed": all(c["status"] != "fail" for c in checks),
        "notes": notes,
    }


def resized_dimensions(spec, requirements, t, fill=False):
    """Isotropic scale with envelope clipping; solve monotone capacity by bisection."""
    s = normalize_spec(spec)
    r = normalize_requirements(requirements)
    caps = [
        r["max_outer_width_mm"] - 2 * t,
        r["max_outer_depth_mm"] - 2 * t,
        r["max_outer_height_mm"] - (2 if s["lid"] else 1) * t,
    ]
    if min(caps) < 20:
        return None
    if r["lock_inner_dimensions"]:
        dims = [s[k] for k in DIMENSIONS]
        return dims if min(dims) > t else None
    original = [s[k] for k in DIMENSIONS]
    minimum = max(20.0, t + 0.001)
    if fill:
        return [min(3000.0, x) for x in caps]
    target = r["min_capacity_l"] * 1e6
    if math.prod(min(3000.0, x) for x in caps) < target - 1e-6:
        return None
    lo = 0.0
    hi = max(c / o for c, o in zip(caps, original)) + 1
    for _ in range(100):
        mid = (lo + hi) / 2
        dims = [min(3000.0, c, max(minimum, o * mid)) for c, o in zip(caps, original)]
        if math.prod(dims) < target:
            lo = mid
        else:
            hi = mid
    dims = [
        round(min(3000.0, c, max(minimum, o * hi)), 8) for c, o in zip(caps, original)
    ]
    return dims if min(dims) > t else None


def optimize(spec, requirements=None):
    s = normalize_spec(spec)
    r = normalize_requirements(requirements)
    candidates = []
    all_candidates = []
    for t in MATERIALS[s["material"]]["stock_mm"]:
        dims = resized_dimensions(s, r, t, fill=r["objective"] == "maximize_capacity")
        if dims is None:
            continue
        if r["objective"] == "maximize_capacity" and not r["lock_inner_dimensions"]:
            # Search the uniform envelope-aspect family; mass and UDL deflection
            # increase monotonically with this scale. A full-envelope failure is
            # not proof that smaller candidates are infeasible.
            caps = dims
            lo = max(
                max(max(20.0, t + 0.001) / x for x in caps),
                (r["min_capacity_l"] * 1e6 / math.prod(caps)) ** (1 / 3),
            )
            if lo > 1 + 1e-10:
                continue

            def at(scale):
                return evaluate(
                    {
                        **s,
                        "thickness_mm": float(t),
                        **dict(zip(DIMENSIONS, [x * scale for x in caps])),
                    },
                    r,
                )

            small = at(min(1.0, lo))
            if not small["passed"]:
                all_candidates.append(small)
                continue
            hi = 1.0
            for _ in range(80):
                mid = (lo + hi) / 2
                if at(mid)["passed"]:
                    lo = mid
                else:
                    hi = mid
            dims = [x * lo for x in caps]
        candidate = {**s, "thickness_mm": float(t), **dict(zip(DIMENSIONS, dims))}
        value = evaluate(candidate, r)
        all_candidates.append(value)
        if value["passed"]:
            candidates.append(value)
    if r["objective"] == "minimize_mass":
        candidates.sort(
            key=lambda a: (a["metrics"]["mass_kg"], a["spec"]["thickness_mm"])
        )
    else:
        candidates.sort(
            key=lambda a: (-a["metrics"]["capacity_l"], a["metrics"]["mass_kg"])
        )
    return {
        "status": "feasible" if candidates else "infeasible",
        "best": candidates[0] if candidates else None,
        "candidates": candidates,
        "evaluated_count": len(all_candidates),
        "rejected": (
            all_candidates
            if not candidates
            else [x for x in all_candidates if not x["passed"]]
        ),
        "explanation": "Enumerates configured stock thicknesses for the selected material. Locked dimensions stay fixed; unlocked minimum-mass sizing follows the original proportional/clipped resize family; maximum-capacity sizing scales the envelope aspect ratio. No feasible candidate means none in this supported search family, not proof across arbitrary geometry.",
    }


def changes(before, after):
    out = []
    for section in ["spec", "requirements"]:
        for k, v in after.get(section, {}).items():
            previous = before.get(section, {}).get(k)
            if previous != v:
                out.append({"field": k, "before": previous, "after": v})
    return out
