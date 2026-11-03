"""Sample straight-line escape with virtual joint limits released.

Blocking six axial translations is a useful control, not global captivity,
rotational retention, gravity equilibrium, strength or physical qualification.
"""

import json
from .mechanism_study import validate_spec
from .motion_probe import translation_probe


def specification(raw, body_ids, state_names):
    if not isinstance(raw, dict) or set(raw) != {
        "part_ids",
        "state_names",
        "distance_mm",
        "samples",
    }:
        raise ValueError(
            "Retention requires part_ids, state_names, distance_mm and samples"
        )
    for key, known, limit in [
        ("part_ids", body_ids, 8),
        ("state_names", state_names, 12),
    ]:
        values = raw[key]
        if (
            not isinstance(values, list)
            or not 1 <= len(values) <= limit
            or any(not isinstance(v, str) for v in values)
            or len(set(values)) != len(values)
            or not set(values) <= set(known)
        ):
            raise ValueError(f"Retention {key} requires unique existing identifiers")
    if (
        type(raw["distance_mm"]) not in (int, float)
        or not 0 < raw["distance_mm"] <= 100
    ):
        raise ValueError("Retention distance must be in (0,100] mm")
    if type(raw["samples"]) is not int or not 2 <= raw["samples"] <= 41:
        raise ValueError("Retention requires 2..41 samples per direction")
    return {**raw, "distance_mm": float(raw["distance_mm"])}


def retention_study(document, built, raw, mechanism=None):
    if not built["checks"]["passed"]:
        raise ValueError("Retention requires valid native solids")
    parts = built["parts"]
    spec = validate_spec(
        mechanism or document.get("metadata", {}).get("design_mechanism"),
        [p["id"] for p in parts],
    )
    targets = specification(
        raw, [p["id"] for p in parts], [s["name"] for s in spec["states"]]
    )
    from .workspace_cache import identity_for_build
    from .motion_cache import native_motion_cache

    identity = identity_for_build(built)
    key = (
        None
        if identity is None
        else (
            "retention-v1",
            identity,
            json.dumps([targets, spec], sort_keys=True, allow_nan=False),
        )
    )
    return native_motion_cache.compute(key, lambda: _calculate(parts, spec, targets))


def _calculate(parts, spec, targets):
    rows = []
    for name in targets["state_names"]:
        for body in targets["part_ids"]:
            for axis in range(3):
                for sign in (-1, 1):
                    direction = [0, 0, 0]
                    direction[axis] = sign
                    report = translation_probe(
                        parts,
                        [body],
                        direction,
                        targets["distance_mm"],
                        targets["samples"],
                        spec,
                        name,
                    )
                    rows.append(
                        {
                            k: v
                            for k, v in report.items()
                            if k not in ("frames", "mechanism_spec")
                        }
                    )
    return {
        "spec": targets,
        "mechanism_spec": spec,
        "cases": rows,
        "case_count": len(rows),
        "passed": all(
            r["initial_pose_clear"] and not r["path_clear_at_samples"] for r in rows
        ),
        "escapes": [r for r in rows if r["path_clear_at_samples"]],
        "global_retention_verified": False,
        "physical_validation": False,
        "scope": "Six world-axis straight translations at each requested state, virtual constraints released. An escape disproves axial capture; obstruction does not prove global/rotational captivity, force or physical fit.",
    }
