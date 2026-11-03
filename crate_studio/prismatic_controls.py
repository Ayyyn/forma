"""Matched physical lock/travel/end-stop controls on native body groups."""

from copy import deepcopy
import json
import numpy as np
from .mechanism_study import validate_spec, pose_matrices
from .motion_probe import translation_probe


def specification(raw, mechanism):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 4:
        raise ValueError("Declare one to four prismatic modes")
    joints = {j["id"]: j for j in mechanism["joints"]}
    states = {s["name"] for s in mechanism["states"]}
    result = deepcopy(raw)
    for mode in result:
        if not isinstance(mode, dict) or set(mode) != {
            "joint_ids",
            "joint_limits",
            "state_pairs",
            "distance_mm",
            "samples",
        }:
            raise ValueError(
                "A mode requires joint_ids, joint_limits, state_pairs, distance_mm and samples"
            )
        ids = mode["joint_ids"]
        if (
            not isinstance(ids, list)
            or not 1 <= len(ids) <= 4
            or any(
                not isinstance(v, str)
                or v not in joints
                or joints[v]["type"] != "prismatic"
                for v in ids
            )
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Choose existing unique prismatic joint IDs")
        if (
            not isinstance(mode["joint_limits"], dict)
            or set(mode["joint_limits"]) != set(ids)
            or any(mode["joint_limits"][key] != joints[key]["limits"] for key in ids)
        ):
            raise ValueError(
                "Retained travel limits differ from the current mechanism; do not weaken the acceptance contract"
            )
        pairs = mode["state_pairs"]
        if not isinstance(pairs, list) or not 1 <= len(pairs) <= 6:
            raise ValueError("Use one to six explicit locked/unlocked state pairs")
        for pair in pairs:
            if (
                not isinstance(pair, dict)
                or set(pair) != {"locked", "unlocked", "position"}
                or any(
                    not isinstance(pair[k], str) or pair[k] not in states
                    for k in ("locked", "unlocked")
                )
                or pair["locked"] == pair["unlocked"]
            ):
                raise ValueError(
                    "Choose distinct existing locked and unlocked state names"
                )
            position = pair["position"]
            if (
                not isinstance(position, list)
                or len(position) != len(ids)
                or any(
                    type(v) not in (int, float) or not np.isfinite(v) for v in position
                )
            ):
                raise ValueError(
                    "Retain the explicit matched adjustment position for every selected joint"
                )
        if (
            type(mode["distance_mm"]) not in (int, float)
            or not 0 < mode["distance_mm"] <= 10
        ):
            raise ValueError("Control displacement must be in (0,10] mm")
        mode["distance_mm"] = float(mode["distance_mm"])
        if type(mode["samples"]) is not int or not 2 <= mode["samples"] <= 41:
            raise ValueError("Use 2..41 control samples")
    return result


def prismatic_controls(document, built, raw, mechanism=None):
    if not built["checks"]["passed"]:
        raise ValueError("Controls require valid native geometry")
    parts = built["parts"]
    spec = validate_spec(
        mechanism or document.get("metadata", {}).get("design_mechanism"),
        [p["id"] for p in parts],
    )
    targets = specification(raw, spec)
    from .workspace_cache import identity_for_build
    from .motion_cache import native_motion_cache

    identity = identity_for_build(built)
    key = (
        None
        if identity is None
        else (
            "prismatic-controls-v1",
            identity,
            json.dumps([targets, spec], sort_keys=True, allow_nan=False),
        )
    )
    return native_motion_cache.compute(key, lambda: _calculate(parts, spec, targets))


def _calculate(parts, spec, targets):
    states = {s["name"]: s for s in spec["states"]}
    joints = {j["id"]: j for j in spec["joints"]}
    rows = []
    for mode in targets:
        selected = [joints[key] for key in mode["joint_ids"]]
        moving = {j["child"] for j in selected}
        for joint in spec["joints"]:
            if joint["parent"] in moving:
                moving.add(joint["child"])
        for pair in mode["state_pairs"]:
            locked, unlocked = (states[pair[k]] for k in ("locked", "unlocked"))
            if any(
                locked["values"][j["id"]] != unlocked["values"][j["id"]]
                for j in selected
            ):
                raise ValueError(
                    "Matched controls must keep adjustment positions identical"
                )
            if any(
                locked["values"][j["id"]] != pair["position"][i]
                for i, j in enumerate(selected)
            ):
                raise ValueError(
                    "Named adjustment positions differ from retained targets"
                )
            matrices = pose_matrices(spec, locked["values"])
            directions = [
                matrices[j["parent"]][:3, :3] @ np.asarray(j["axis"]) for j in selected
            ]
            if any(np.linalg.norm(v - directions[0]) > 1e-8 for v in directions[1:]):
                raise ValueError("Coupled modes require parallel equally directed axes")
            for sign in (-1, 1):
                distance = mode["distance_mm"]
                allowed = all(
                    j["limits"][0] - 1e-9
                    <= unlocked["values"][j["id"]] + sign * distance
                    <= j["limits"][1] + 1e-9
                    for j in selected
                )
                axis = (sign * directions[0]).tolist()
                a = translation_probe(
                    parts,
                    sorted(moving),
                    axis,
                    distance,
                    mode["samples"],
                    spec,
                    pair["locked"],
                )
                b = translation_probe(
                    parts,
                    sorted(moving),
                    axis,
                    distance,
                    mode["samples"],
                    spec,
                    pair["unlocked"],
                )

                def trim(r):
                    return {
                        k: v
                        for k, v in r.items()
                        if k not in ("frames", "mechanism_spec")
                    }

                rows.append(
                    {
                        "joint_ids": mode["joint_ids"],
                        "locked_state": pair["locked"],
                        "unlocked_state": pair["unlocked"],
                        "sign": sign,
                        "within_travel": allowed,
                        "locked": trim(a),
                        "unlocked": trim(b),
                        "passed": a["initial_pose_clear"]
                        and b["initial_pose_clear"]
                        and not a["path_clear_at_samples"]
                        and b["path_clear_at_samples"] == allowed,
                    }
                )
    return {
        "spec": targets,
        "mechanism_spec": spec,
        "cases": rows,
        "case_count": len(rows),
        "passed": all(r["passed"] for r in rows),
        "failed_cases": [r for r in rows if not r["passed"]],
        "physical_validation": False,
        "scope": "Native finite translations with virtual constraints released. Locks must obstruct, legal unlocked travel must clear, and out-of-range directions must meet a physical stop within the stated probe distance. No friction, force, continuous-motion or global-captivity proof.",
    }
