"""Revision-bound sampled rigid assembly from separated parts to an exact pose.

No gravity, contact forces, elastic snap fits or continuous swept-volume proof.
"""

from copy import deepcopy
import itertools
import json
import math

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from .workspace_geometry import _bounds
from .workspace_workflow import geometry_signature
from .mechanism_study import moved_parts, pose_matrices, validate_spec
from .folding import collisions


def _vector(raw, key, default=None):
    value = raw.get(key, default)
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(
            type(x) not in (int, float)
            or not math.isfinite(x)
            or abs(x) > (360 if key == "rotation" else 1000)
            for x in value
        )
    ):
        raise ValueError(
            f"{key} requires three finite numbers in mm/degrees within workspace limits"
        )
    return list(map(float, value))


def _placement(raw):
    if (
        not isinstance(raw, dict)
        or set(raw) - {"translation", "rotation"}
        or "translation" not in raw
    ):
        raise ValueError(
            "Placement requires translation:[x,y,z] and optional rotation:[rx,ry,rz]"
        )
    return {
        "translation": _vector(raw, "translation"),
        "rotation": _vector(raw, "rotation", [0, 0, 0]),
    }


def matrix(placement):
    result = np.eye(4)
    result[:3, :3] = Rotation.from_euler(
        "xyz", placement["rotation"], degrees=True
    ).as_matrix()
    result[:3, 3] = placement["translation"]
    return result


def specification(raw, ids):
    if not isinstance(raw, dict) or set(raw) - {
        "initial_placements",
        "steps",
        "target_state",
        "step_mm",
        "step_deg",
    }:
        raise ValueError("Unsupported assembly fields")
    first = raw.get("initial_placements")
    if not isinstance(first, dict) or set(first) != set(ids):
        raise ValueError(
            "Initial placements must explicitly position every native body separately"
        )
    steps = raw.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
        raise ValueError("Assembly requires one to twenty named insertion steps")
    normalized = []
    names = set()
    for step in steps:
        if (
            not isinstance(step, dict)
            or set(step) != {"name", "placements"}
            or not isinstance(step["name"], str)
            or not 1 <= len(step["name"]) <= 80
            or step["name"] in names
        ):
            raise ValueError("Each assembly step needs a unique name and placements")
        values = step["placements"]
        if not isinstance(values, dict) or not values or set(values) - set(ids):
            raise ValueError(
                "Assembly step placements must identify existing bodies; omitted bodies keep their previous placement"
            )
        names.add(step["name"])
        normalized.append(
            {
                "name": step["name"],
                "placements": {key: _placement(value) for key, value in values.items()},
            }
        )
    precision = {}
    for key, default, lower, upper in (("step_mm", 1, 0.1, 2), ("step_deg", 3, 0.5, 5)):
        value = raw.get(key, default)
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not lower <= value <= upper
        ):
            raise ValueError(f"{key} must be within {lower}..{upper}")
        precision[key] = float(value)
    target = raw.get("target_state")
    if target is not None and (not isinstance(target, str) or not target):
        raise ValueError(
            "target_state must be null (original native pose) or a declared mechanism state"
        )
    return {
        "initial_placements": {key: _placement(value) for key, value in first.items()},
        "steps": normalized,
        "target_state": target,
        **precision,
    }


def assembly_study(document, built, raw):
    if not built["checks"]["passed"] or not 2 <= len(built["parts"]) <= 24:
        raise ValueError(
            "Assembly study requires two to twenty-four valid native bodies"
        )
    parts = built["parts"]
    ids = [p["id"] for p in parts]
    spec = specification(raw, ids)
    target = {key: np.eye(4) for key in ids}
    if spec["target_state"] is not None:
        mechanism = validate_spec(
            document.get("metadata", {}).get("design_mechanism"), ids
        )
        state = next(
            (s for s in mechanism["states"] if s["name"] == spec["target_state"]), None
        )
        if state is None:
            raise ValueError("Unknown assembly target mechanism state")
        target = pose_matrices(mechanism, state["values"])
    from .workspace_cache import identity_for_build
    from .motion_cache import native_motion_cache

    identity = identity_for_build(built)
    key = (
        None
        if identity is None
        else (
            "assembly-v2",
            identity,
            geometry_signature(document),
            json.dumps(spec, sort_keys=True, allow_nan=False),
            json.dumps(
                {k: v.tolist() for k, v in target.items()},
                sort_keys=True,
                allow_nan=False,
            ),
        )
    )
    return native_motion_cache.compute(
        key, lambda: _calculate_assembly(document, parts, ids, spec, target)
    )


def _calculate_assembly(document, parts, ids, spec, target):
    initial = {key: matrix(value) for key, value in spec["initial_placements"].items()}
    initial_parts = moved_parts(parts, initial)
    separations = [
        {
            "parts": [a["id"], b["id"]],
            "distance_mm": float(a["shape"].distance(b["shape"])),
        }
        for a, b in itertools.combinations(initial_parts, 2)
    ]
    separated = all(row["distance_mm"] >= 2 - 1e-7 for row in separations)
    radii = {
        p["id"]: max(
            np.linalg.norm(point)
            for point in itertools.product(*zip(*_bounds(p["shape"])))
        )
        for p in parts
    }
    segments = []
    current = initial
    total = 1
    for step in spec["steps"]:
        end = {
            **current,
            **{key: matrix(value) for key, value in step["placements"].items()},
        }
        distances = []
        angles = []
        for key in ids:
            angle = float(
                Rotation.from_matrix(
                    current[key][:3, :3].T @ end[key][:3, :3]
                ).magnitude()
            )
            distance = float(np.linalg.norm(end[key][:3, 3] - current[key][:3, 3]))
            distances.append(distance + radii[key] * angle)
            angles.append(math.degrees(angle))
        count = max(
            1,
            math.ceil(max(distances) / spec["step_mm"]),
            math.ceil(max(angles) / spec["step_deg"]),
        )
        total += count
        if total > 2001:
            raise ValueError(
                "Assembly exceeds 2001 sampled poses; use shorter staged insertions or supported sampling precision"
            )
        segments.append((step["name"], current, end, count))
        current = end
    target_error = max(float(np.max(np.abs(current[key] - target[key]))) for key in ids)
    frames = []
    pair_cache = {}
    native_pairs = 0
    cache_hits = 0

    def sample(name, fraction, matrices, segment=-1):
        nonlocal native_pairs, cache_hits
        posed = moved_parts(parts, matrices)
        overlaps = []
        for i, j in itertools.combinations(range(len(ids)), 2):
            relative = np.linalg.solve(matrices[ids[i]], matrices[ids[j]])
            key = (ids[i], ids[j], relative.tobytes())
            if key in pair_cache:
                found = pair_cache[key]
                cache_hits += 1
            else:
                found = collisions([posed[i], posed[j]], details=True)["overlaps"]
                pair_cache[key] = found
                native_pairs += 1
            overlaps.extend(found)
        bounds = [_bounds(p["shape"]) for p in posed]
        low = np.min([b[0] for b in bounds], axis=0)
        high = np.max([b[1] for b in bounds], axis=0)
        frames.append(
            {
                "step": name,
                "segment": segment,
                "fraction": float(fraction),
                "pose_matrices": {
                    key: value.tolist() for key, value in matrices.items()
                },
                "overlaps": deepcopy(overlaps),
                "extent_mm": (high - low).tolist(),
                "bounds_mm": [low.tolist(), high.tolist()],
            }
        )

    sample("Separated parts", 0, initial)
    for segment, (name, start, end, count) in enumerate(segments):
        if frames[-1]["overlaps"]:
            break
        rotations = {
            key: Slerp(
                [0, 1],
                Rotation.from_matrix(np.array([start[key][:3, :3], end[key][:3, :3]])),
            )
            for key in ids
        }
        for index in range(1, count + 1):
            t = index / count
            matrices = {}
            for key in ids:
                value = np.eye(4)
                value[:3, :3] = rotations[key]([t]).as_matrix()[0]
                value[:3, 3] = (1 - t) * start[key][:3, 3] + t * end[key][:3, 3]
                matrices[key] = value
            sample(name, t, matrices, segment)
            if frames[-1]["overlaps"]:
                break
    for i, frame in enumerate(frames):
        frame["progress_pct"] = 100 * i / (total - 1)
    failures = [frame for frame in frames if frame["overlaps"]]
    return {
        "geometry_signature": geometry_signature(document),
        "spec": spec,
        "frames": frames,
        "sample_count": len(frames),
        "planned_sample_count": total,
        "sampling_complete": len(frames) == total,
        "sampling_policy": "Rejected paths stop at the first collision; passing paths check every planned pose.",
        "collision_sample_count": len(failures),
        "initial_separation_passed": separated,
        "initial_separations": separations,
        "target_pose_passed": target_error <= 1e-6,
        "target_matrix_error": target_error,
        "target_pose_matrices": {key: value.tolist() for key, value in target.items()},
        "passed": separated and target_error <= 1e-6 and not failures,
        "native_pair_checks": native_pairs,
        "exact_pair_cache_hits": cache_hits,
        "continuous_motion_proven": False,
        "physical_validation": False,
        "scope": "Rigid assembly from individually separated printed bodies to the exact source/named pose. Translation interpolates linearly and rotation uses shortest-path quaternion interpolation. Finite-volume overlap checked at declared spatial/angular samples. No elastic snap fit, gravity, handling, support removal, friction, force, continuous swept-volume or physical fit qualification.",
    }
