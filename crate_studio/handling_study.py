"""Retained unwanted staged translations with virtual constraints released."""

from copy import deepcopy
import json
import math
import cadquery as cq
import numpy as np
from .mechanism_study import validate_spec, pose_matrices, moved_parts
from .motion_probe import translation_probe
from .folding import collisions


def specification(raw, mechanism):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 12:
        raise ValueError("Declare one to twelve unwanted handling paths")
    joints = {j["id"] for j in mechanism["joints"]}
    states = {s["name"] for s in mechanism["states"]}
    result = deepcopy(raw)
    names = set()
    for case in result:
        if not isinstance(case, dict) or set(case) != {
            "name",
            "state_name",
            "joint_ids",
            "steps",
        }:
            raise ValueError(
                "A handling path requires name, state_name, joint_ids and steps"
            )
        if (
            not isinstance(case["name"], str)
            or not 1 <= len(case["name"]) <= 80
            or case["name"] in names
        ):
            raise ValueError("Handling paths require unique bounded names")
        names.add(case["name"])
        if not isinstance(case["state_name"], str) or case["state_name"] not in states:
            raise ValueError("Unknown handling state")
        ids = case["joint_ids"]
        if (
            not isinstance(ids, list)
            or not ids
            or len(ids) > 4
            or any(not isinstance(j, str) or j not in joints for j in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Choose unique existing joints; descendants move together")
        if not isinstance(case["steps"], list) or not 1 <= len(case["steps"]) <= 4:
            raise ValueError("Use one to four staged world translations")
        for step in case["steps"]:
            if not isinstance(step, dict) or set(step) != {"translation_mm", "samples"}:
                raise ValueError(
                    "Each handling step requires translation_mm and samples"
                )
            v = step["translation_mm"]
            if (
                not isinstance(v, list)
                or len(v) != 3
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
                or not 0 < float(np.linalg.norm(v)) <= 100
            ):
                raise ValueError(
                    "Handling translations require three finite numbers and length in (0,100] mm"
                )
            if type(step["samples"]) is not int or not 2 <= step["samples"] <= 41:
                raise ValueError("Handling steps require 2..41 samples")
            step["translation_mm"] = list(map(float, v))
    return result


def handling_study(document, built, raw, mechanism=None):
    if not built["checks"]["passed"]:
        raise ValueError("Handling checks require valid native solids")
    if len(built["parts"]) > 24:
        raise ValueError("Handling checks support at most 24 native bodies")
    spec = validate_spec(
        mechanism or document.get("metadata", {}).get("design_mechanism"),
        [p["id"] for p in built["parts"]],
    )
    targets = specification(raw, spec)
    from .workspace_cache import identity_for_build
    from .motion_cache import native_motion_cache

    identity = identity_for_build(built)
    key = (
        None
        if identity is None
        else (
            "handling-v1",
            identity,
            json.dumps([targets, spec], sort_keys=True, allow_nan=False),
        )
    )
    return native_motion_cache.compute(
        key, lambda: _calculate(built["parts"], spec, targets)
    )


def _calculate(parts, spec, targets):
    children = {}
    joints = {j["id"]: j for j in spec["joints"]}
    for joint in spec["joints"]:
        children.setdefault(joint["parent"], []).append(joint["child"])

    def descendants(body):
        found = {body}
        for child in children.get(body, []):
            found |= descendants(child)
        return found

    cases = []
    for target in targets:
        ids = set()
        for name in target["joint_ids"]:
            ids |= descendants(joints[name]["child"])
        state = next(s for s in spec["states"] if s["name"] == target["state_name"])
        posed = moved_parts(parts, pose_matrices(spec, state["values"]))
        initial = not collisions(posed)["overlaps"]
        steps = []
        blocked = False
        if initial:
            for step in target["steps"]:
                vector = step["translation_mm"]
                report = translation_probe(
                    posed,
                    sorted(ids),
                    vector,
                    float(np.linalg.norm(vector)),
                    step["samples"],
                )
                steps.append(report)
                if not report["initial_pose_clear"]:
                    initial = False
                    break
                if not report["path_clear_at_samples"]:
                    blocked = True
                    break
                posed = [
                    {
                        **p,
                        "shape": p["shape"].moved(cq.Location(cq.Vector(*vector)))
                        if p["id"] in ids
                        else p["shape"],
                    }
                    for p in posed
                ]
        cases.append(
            {
                "name": target["name"],
                "state_name": target["state_name"],
                "moving_part_ids": sorted(ids),
                "initial_pose_clear": initial,
                "unwanted_path_clear": initial and not blocked,
                "passed": initial and blocked,
                "steps": steps,
            }
        )
    return {
        "spec": targets,
        "mechanism_spec": spec,
        "case_count": len(cases),
        "passed": all(c["passed"] for c in cases),
        "cases": cases,
        "physical_validation": False,
        "scope": "Specified unwanted staged rigid WORLD translations with virtual constraints released. A fully clear sampled path disproves capture; a positive-offset obstruction blocks this path only. No global captivity, rotations, force, friction or physical-fit proof.",
    }
