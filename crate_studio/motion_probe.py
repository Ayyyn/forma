"""Sample unwanted translations on actual solids, without virtual constraints.

This is a local obstruction diagnostic, not proof of global captivity or forces.
"""

import math
import numpy as np
import cadquery as cq

from .folding import collisions
from .mechanism_study import validate_spec, pose_matrices, moved_parts


def translation_probe(
    parts, moving_ids, direction, distance, samples, spec=None, state=None
):
    ids = {p["id"] for p in parts}
    if (
        len(parts) > 24
        or not isinstance(moving_ids, list)
        or not moving_ids
        or any(not isinstance(x, str) for x in moving_ids)
        or len(set(moving_ids)) != len(moving_ids)
        or not set(moving_ids) < ids
    ):
        raise ValueError("Choose a nonempty proper subset of at most 24 native bodies")
    if (
        not isinstance(direction, list)
        or len(direction) != 3
        or any(type(x) not in (int, float) or not math.isfinite(x) for x in direction)
    ):
        raise ValueError("Direction requires three finite numbers")
    direction = np.array(direction, dtype=float)
    length = float(np.linalg.norm(direction))
    if not math.isfinite(length) or length < 1e-9:
        raise ValueError("Direction must be nonzero")
    direction /= length
    if (
        type(distance) not in (int, float)
        or not math.isfinite(distance)
        or not 0 < distance <= 100
    ):
        raise ValueError("Probe distance must be in (0, 100] mm")
    if type(samples) is not int or not 2 <= samples <= 41:
        raise ValueError("Use 2 to 41 sampled displacements")
    if (spec is None) != (state is None):
        raise ValueError("Supply both mechanism_spec and state_name, or neither")
    if spec is not None:
        spec = validate_spec(spec, list(ids))
        named = next((s for s in spec["states"] if s["name"] == state), None)
        if named is None:
            raise ValueError("Choose an existing named state")
        parts = moved_parts(parts, pose_matrices(spec, named["values"]))
    moving = set(moving_ids)
    frames = []
    # Only moving-versus-stationary intersections matter. Existing internal
    # contacts within either rigid group cannot obstruct its translation.
    for offset in np.linspace(0, distance, samples):
        posed = [
            {
                "id": p["id"],
                "shape": (
                    p["shape"].moved(cq.Location(cq.Vector(*(direction * offset))))
                    if p["id"] in moving
                    else p["shape"]
                ),
            }
            for p in parts
        ]
        overlaps = []
        for mobile in (p for p in posed if p["id"] in moving):
            for stationary in (p for p in posed if p["id"] not in moving):
                overlaps.extend(
                    collisions([mobile, stationary], details=True)["overlaps"]
                )
        frames.append({"displacement_mm": float(offset), "overlaps": overlaps})
        if overlaps:
            break
    blocked = frames[-1] if frames[-1]["overlaps"] else None
    return {
        "moving_part_ids": moving_ids,
        "direction_world": direction.tolist(),
        "requested_distance_mm": distance,
        "sample_step_mm": distance / (samples - 1),
        "sample_count": len(frames),
        "state_name": state,
        "mechanism_spec": spec,
        "initial_pose_clear": not frames[0]["overlaps"],
        "path_clear_at_samples": blocked is None,
        "first_blocked_sample_mm": blocked["displacement_mm"] if blocked else None,
        "frames": frames,
        "global_retention_verified": False,
        "physical_validation": False,
        "scope": "Rigid translation of a selected body group in WORLD coordinates with virtual joint constraints released. Exact positive-volume native intersections at sampled offsets only, stopping at first obstruction. A clear path reveals an unblocked sampled direction; an obstruction does not prove global captivity, continuous clearance, rotational retention, assembly, lock function or strength.",
    }


def prismatic_pair_probe(parts, raw_spec, joint_id, state_name, distance, samples):
    """Six independent directions on the actual posed parent/child pair.

    Isolate the interface so an unrelated floor cannot masquerade as a guide.
    This deliberately does not claim global retention of the whole assembly.
    """
    spec = validate_spec(raw_spec, [p["id"] for p in parts])
    joint = next((j for j in spec["joints"] if j["id"] == joint_id), None)
    state = next((s for s in spec["states"] if s["name"] == state_name), None)
    if joint is None or joint["type"] != "prismatic" or state is None:
        raise ValueError("Choose an existing prismatic joint and named state")
    matrices = pose_matrices(spec, state["values"])
    posed = moved_parts(parts, matrices)
    pair = [p for p in posed if p["id"] in (joint["parent"], joint["child"])]
    axial = matrices[joint["parent"]][:3, :3] @ np.array(joint["axis"])
    reference = np.eye(3)[int(np.argmin(np.abs(axial)))]
    cross_a = np.cross(axial, reference)
    cross_a /= np.linalg.norm(cross_a)
    cross_b = np.cross(axial, cross_a)
    directions = {"axial": axial, "transverse_1": cross_a, "transverse_2": cross_b}
    results = {}
    for name, axis in directions.items():
        for suffix, sign in (("positive", 1), ("negative", -1)):
            result = translation_probe(
                pair, [joint["child"]], (sign * axis).tolist(), distance, samples
            )
            results[name + "_" + suffix] = {
                k: v
                for k, v in result.items()
                if k not in ("frames", "scope", "mechanism_spec")
            }
            results[name + "_" + suffix]["first_obstruction"] = (
                result["frames"][-1] if not result["path_clear_at_samples"] else None
            )
    return {
        "joint_id": joint_id,
        "state_name": state_name,
        "parent": joint["parent"],
        "child": joint["child"],
        "spec": spec,
        "directions": results,
        "global_retention_verified": False,
        "physical_validation": False,
        "scope": "Actual parent/child interface only, other bodies excluded. Native sampled translations in the current parent-rotated axial and two orthogonal transverse directions, with virtual constraints released. Blockage can come from existing walls or floors; it does not prove guide engagement, rotational/global captivity, assembly, locks or strength. Axial motion may legitimately be stopped by end-stop hardware at a travel limit.",
    }
