"""Prescribed rigid-body mechanism paths on actual finite-volume Studio solids.

Joint trees generate poses; optional point/axis connections test closed loops.
The joints are kinematic declarations, not manufactured bearings or locks.
"""

from copy import deepcopy
import math

import cadquery as cq
import numpy as np
from OCP.gp import gp_Trsf

from .folding import collisions
from .workspace_geometry import _bounds
from .workspace_workflow import geometry_signature


def _number(value, limit=10000):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or abs(value) > limit
    ):
        raise ValueError("Expected a finite bounded number")
    return float(value)


def _vector(value, unit=False):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("Expected a three-number vector")
    v = np.array([_number(x) for x in value])
    if unit:
        length = float(np.linalg.norm(v))
        if length < 1e-9:
            raise ValueError("Joint/connection axis must be nonzero")
        v /= length
    return v


def validate_spec(raw, part_ids):
    if not isinstance(raw, dict) or set(raw) != {
        "root",
        "joints",
        "states",
        "connections",
        "samples_per_segment",
    }:
        raise ValueError(
            "Mechanism requires root, joints, states, connections and samples_per_segment"
        )
    spec = deepcopy(raw)
    ids = set(part_ids)
    if spec["root"] not in ids:
        raise ValueError("Unknown root body")
    n = spec["samples_per_segment"]
    if type(n) is not int or not 2 <= n <= 73:
        raise ValueError("samples_per_segment must be an integer from 2 to 73")
    if not isinstance(spec["joints"], list) or len(spec["joints"]) != len(ids) - 1:
        raise ValueError("Joint tree must connect every body exactly once")
    connected, names = {spec["root"]}, set()
    for joint in spec["joints"]:
        if not isinstance(joint, dict) or set(joint) != {
            "id",
            "parent",
            "child",
            "type",
            "axis",
            "origin",
            "limits",
        }:
            raise ValueError("Invalid joint fields")
        if (
            not isinstance(joint["id"], str)
            or not 0 < len(joint["id"]) <= 80
            or joint["id"] in names
        ):
            raise ValueError("Joint IDs must be nonempty and unique")
        if joint["parent"] not in connected or joint["child"] not in ids - connected:
            raise ValueError("Joints must form a root-first connected acyclic tree")
        if joint["type"] not in ("fixed", "revolute", "prismatic"):
            raise ValueError("Unsupported joint type")
        joint["axis"] = _vector(joint["axis"], unit=True).tolist()
        joint["origin"] = _vector(joint["origin"]).tolist()
        if not isinstance(joint["limits"], list) or len(joint["limits"]) != 2:
            raise ValueError("Joint limits require [lower, upper]")
        lo, hi = [_number(x) for x in joint["limits"]]
        if lo > hi or (joint["type"] == "fixed" and [lo, hi] != [0, 0]):
            raise ValueError("Invalid joint limits")
        joint["limits"] = [lo, hi]
        connected.add(joint["child"])
        names.add(joint["id"])
    if not isinstance(spec["states"], list) or not 2 <= len(spec["states"]) <= 12:
        raise ValueError("Supply 2 to 12 named states")
    state_names = set()
    for state in spec["states"]:
        if not isinstance(state, dict) or set(state) != {"name", "values"}:
            raise ValueError("State requires name and values")
        if (
            not isinstance(state["name"], str)
            or not 0 < len(state["name"]) <= 80
            or state["name"] in state_names
        ):
            raise ValueError("State names must be nonempty and unique")
        if not isinstance(state["values"], dict) or set(state["values"]) != names:
            raise ValueError("Every state must explicitly supply every joint value")
        for joint in spec["joints"]:
            q = _number(state["values"][joint["id"]])
            if not joint["limits"][0] <= q <= joint["limits"][1]:
                raise ValueError("State exceeds declared joint limits")
            state["values"][joint["id"]] = q
        state_names.add(state["name"])
    if not isinstance(spec["connections"], list) or len(spec["connections"]) > 50:
        raise ValueError("At most 50 loop connections are supported")
    for c in spec["connections"]:
        fields = {"type", "a", "b", "anchor_a", "anchor_b"}
        if not isinstance(c, dict) or c.get("type") not in ("point", "axis"):
            raise ValueError("Connection must be point or axis")
        if c["type"] == "axis":
            fields |= {"axis_a", "axis_b"}
        if (
            set(c) != fields
            or c["a"] not in ids
            or c["b"] not in ids
            or c["a"] == c["b"]
        ):
            raise ValueError("Invalid connection fields or bodies")
        for key in ("anchor_a", "anchor_b"):
            c[key] = _vector(c[key]).tolist()
        if c["type"] == "axis":
            for key in ("axis_a", "axis_b"):
                c[key] = _vector(c[key], unit=True).tolist()
    if (len(spec["states"]) - 1) * (n - 1) + 1 > 361:
        raise ValueError("Trajectory exceeds 361 sampled poses")
    return spec


def _joint_transform(joint, value):
    result = np.eye(4)
    axis = np.array(joint["axis"])
    if joint["type"] == "prismatic":
        result[:3, 3] = axis * value
    elif joint["type"] == "revolute":
        x, y, z = axis
        skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
        angle = math.radians(value)
        r = np.eye(3) + math.sin(angle) * skew + (1 - math.cos(angle)) * (skew @ skew)
        result[:3, :3] = r
        origin = np.array(joint["origin"])
        result[:3, 3] = origin - r @ origin
    return result


def pose_matrices(spec, values):
    matrices = {spec["root"]: np.eye(4)}
    for joint in spec["joints"]:
        matrices[joint["child"]] = matrices[joint["parent"]] @ _joint_transform(
            joint, values[joint["id"]]
        )
    return matrices


def _connection_errors(spec, matrices):
    position, angle = 0.0, 0.0
    for c in spec["connections"]:
        ma, mb = matrices[c["a"]], matrices[c["b"]]
        a = ma[:3, :3] @ np.array(c["anchor_a"]) + ma[:3, 3]
        b = mb[:3, :3] @ np.array(c["anchor_b"]) + mb[:3, 3]
        position = max(position, float(np.linalg.norm(a - b)))
        if c["type"] == "axis":
            a = ma[:3, :3] @ np.array(c["axis_a"])
            b = mb[:3, :3] @ np.array(c["axis_b"])
            angle = max(angle, math.degrees(math.acos(min(1.0, abs(float(a @ b))))))
    return position, angle


def moved_parts(parts, matrices):
    """Apply only rigid native locations; preserve finite solid geometry."""
    moved = []
    for part in parts:
        transform = gp_Trsf()
        transform.SetValues(*[float(x) for x in matrices[part["id"]][:3, :].ravel()])
        moved.append(
            {"id": part["id"], "shape": part["shape"].moved(cq.Location(transform))}
        )
    return moved


def mechanism_study(document, built, raw):
    if not built["checks"]["passed"]:
        raise ValueError("Mechanism study requires valid native solids")
    parts = built["parts"]
    if len(parts) > 24:
        raise ValueError("Generic mechanism study supports at most 24 native bodies")
    spec = validate_spec(raw, [p["id"] for p in parts])
    frames = []
    for segment, (start, end) in enumerate(zip(spec["states"], spec["states"][1:])):
        for index, alpha in enumerate(np.linspace(0, 1, spec["samples_per_segment"])):
            if segment and index == 0:
                continue
            values = {
                key: (1 - alpha) * start["values"][key] + alpha * end["values"][key]
                for key in start["values"]
            }
            matrices = pose_matrices(spec, values)
            moved = moved_parts(parts, matrices)
            check = collisions(moved, details=True)
            position, angle = _connection_errors(spec, matrices)
            bounds = _bounds(cq.Compound.makeCompound([p["shape"] for p in moved]))
            frames.append(
                {
                    "segment": segment,
                    "fraction": float(alpha),
                    "values": values,
                    "bounds_mm": bounds,
                    "overlaps": check["overlaps"],
                    "extent_mm": [bounds[1][i] - bounds[0][i] for i in range(3)],
                    "loop_position_error_mm": position,
                    "loop_axis_error_deg": angle,
                    "pose_matrices": {k: v.tolist() for k, v in matrices.items()},
                }
            )
    for index, frame in enumerate(frames):
        frame["progress_pct"] = 100 * index / (len(frames) - 1)
    return {
        "geometry_signature": geometry_signature(document),
        "spec": spec,
        "frames": frames,
        "passed": all(
            not f["overlaps"]
            and f["loop_position_error_mm"] <= 1e-6
            and f["loop_axis_error_deg"] <= 1e-5
            for f in frames
        ),
        "sample_count": len(frames),
        "collision_sample_count": sum(bool(f["overlaps"]) for f in frames),
        "max_loop_position_error_mm": max(f["loop_position_error_mm"] for f in frames),
        "sampling_resolution": {
            joint["id"]: {
                "max_step": max(
                    abs(b["values"][joint["id"]] - a["values"][joint["id"]])
                    / (spec["samples_per_segment"] - 1)
                    for a, b in zip(spec["states"], spec["states"][1:])
                ),
                "unit": "deg" if joint["type"] == "revolute" else "mm",
            }
            for joint in spec["joints"]
        },
        "continuous_motion_proven": False,
        "physical_joint_hardware_verified": False,
        "locking_verified": False,
        "physical_validation": False,
        "scope": "Prescribed root-first rigid-body tree, with optional declared loop point/axis constraints; axes/anchors use each body's original world coordinate frame. Revolute values are degrees, prismatic values mm; interpolate consecutive state values linearly. Every finite-volume body pair is checked at sampled poses. Tree joints are virtual constraints; hardware, support, retained engagement, locks, loads, fatigue and continuous swept volumes are not verified.",
    }
