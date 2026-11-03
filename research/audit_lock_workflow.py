"""Independent finite-solid audit of a model's declared lock/adjustment sequence.

Rebuilds unchanged model CAD, refines the model's own path, and releases virtual
constraints to compare locked obstruction with unlocked travel. No force solver,
coefficient of friction, physical retention or print-fit claim is made.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np

from crate_studio.workspace_agent import RUNS
from crate_studio.workspace_geometry import build_document
from crate_studio.mechanism_study import mechanism_study, validate_spec, pose_matrices
from crate_studio.motion_probe import translation_probe
from crate_studio.floor_check import floor_coverage
from crate_studio.design_tools import DesignSession
from research.audit_size_states import direct_pose


def run(source_run, candidate_id, destination, axes, locked_states, coupled_axes=None):
    destination.mkdir(parents=True, exist_ok=False)
    folder = RUNS / source_run
    ledger = folder / "candidates.json"
    document = json.loads(ledger.read_text(encoding="utf-8"))[candidate_id]["document"]
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()]
    motion = next(event for event in reversed(events)
                  if event.get("kind") == "tool" and event.get("tool") == "check_motion"
                  and event["arguments"]["candidate_id"] == candidate_id)
    raw = deepcopy(motion["arguments"]["spec"])
    # Independent native build deliberately bypasses the owned geometry/motion cache.
    built = build_document(document)
    raw["samples_per_segment"] = min(73, 1 + 360 // (len(raw["states"]) - 1))
    spec = validate_spec(raw, [part["id"] for part in built["parts"]])
    study = mechanism_study(document, built, spec)
    (destination / "refined-motion.json").write_text(json.dumps(study, indent=2), encoding="utf-8")
    states = {state["name"]: state for state in spec["states"]}
    targets = document["metadata"]["design_review"]["reports"]
    floors = []
    for name, state in states.items():
        size = "rectangular" if name.startswith("rect") else name.split("_")[0]
        footprint = targets["floor:state:" + size]["footprint"]
        report, *_ = floor_coverage(direct_pose(built["parts"], spec, state["values"]), footprint)
        floors.append({"state": name, "passed": report["passed"],
                       "footprint": footprint, "missing_area_mm2": report["missing_area_mm2"]})

    rows, stops = [], []
    modes = [(ident, [ident]) for ident in axes]
    if coupled_axes:
        modes.append(("+".join(coupled_axes), coupled_axes))
    for ident, joint_ids in modes:
        joints = [next(joint for joint in spec["joints"] if joint["id"] == name) for name in joint_ids]
        if any(joint["type"] != "prismatic" for joint in joints):
            raise ValueError("This audit probes prismatic adjustment axes only")
        moving = {joint["child"] for joint in joints}
        for descendant in spec["joints"]:  # Validated root-first order.
            if descendant["parent"] in moving:
                moving.add(descendant["child"])
        for name in locked_states:
            locked = states[name]
            unlocked_name = name.replace("_locked", "_unlocked")
            unlocked = states[unlocked_name]
            if any(locked["values"][joint["id"]] != unlocked["values"][joint["id"]] for joint in joints):
                raise ValueError("Locked/unlocked controls must keep the same adjustment position")
            matrices = pose_matrices(spec, locked["values"])
            directions = [matrices[joint["parent"]][:3, :3] @ np.array(joint["axis"]) for joint in joints]
            direction = directions[0]
            if any(np.linalg.norm(other - direction) > 1e-8 for other in directions[1:]):
                raise ValueError("A coupled translation requires parallel, equally oriented axes")
            for sign in (-1, 1):
                axis = (direction * sign).tolist()
                obstructed = translation_probe(built["parts"], sorted(moving), axis, 1, 21, spec, name)
                allowed = all(joint["limits"][0] <= locked["values"][joint["id"]] + sign <= joint["limits"][1]
                              for joint in joints)
                control = translation_probe(built["parts"], sorted(moving), axis, 1, 21, spec, unlocked_name)
                trim = lambda report: {key: val for key, val in report.items() if key != "mechanism_spec"}
                row = {"joint": ident, "coupled_joint_ids": joint_ids, "state": name, "sign": sign,
                       "unlocked_direction_within_declared_travel": allowed,
                       "locked": trim(obstructed), "unlocked_control": trim(control),
                       "passed": obstructed["initial_pose_clear"] and not obstructed["path_clear_at_samples"]
                           and control["initial_pose_clear"] and (control["path_clear_at_samples"] if allowed else True)}
                rows.append(row)
                if not allowed:
                    stops.append({"joint": ident, "state": unlocked_name, "sign": sign,
                                  "passed": control["initial_pose_clear"] and not control["path_clear_at_samples"],
                                  "first_obstruction_mm": control["first_blocked_sample_mm"]})

    session = DesignSession(document, "Independent native lock-workflow audit; no model calls", destination / "native-tools")
    exports = session.call("verify_exports", {"candidate_id": "base"})
    passed = (built["checks"]["passed"] and study["passed"] and all(row["passed"] for row in floors)
              and all(row["passed"] for row in rows) and all(row["passed"] for row in stops)
              and exports.get("ok") and exports.get("passed"))
    report = {"source_run": source_run, "candidate_id": candidate_id,
              "ledger_sha256": hashlib.sha256(ledger.read_bytes()).hexdigest(),
              "fresh_model_call": False, "model_selected": False,
              "features": len(document["features"]), "bodies": len(built["parts"]),
              "original_model_motion_samples": motion["result"].get("sample_count"),
              "refined_motion_samples": study["sample_count"], "motion_passed": study["passed"],
              "collision_poses": study["collision_sample_count"], "spec": spec,
              "adjustment_modes": modes,
              "floors": floors, "locked_unlocked_controls": rows, "end_stops": stops,
              "exports": exports, "geometric_lock_workflow_passed": bool(passed),
              "friction_verified": False, "actuation_force_verified": False,
              "physical_validation": False, "rotational_retention_verified": False,
              "scope": "Unchanged model CAD, independent native path refinement, floor coverage, whole-descendant-group axial obstruction and unlocked travel controls plus sampled endpoint stops. Does not qualify continuous motion, pin captivity, friction, loads, strength, wear, material, assembly access or physical printer fit."}
    (destination / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("source_run", "candidate_id", "features", "bodies",
                     "refined_motion_samples", "motion_passed", "collision_poses", "geometric_lock_workflow_passed")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_run")
    parser.add_argument("candidate_id")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--axes", nargs="+", required=True)
    parser.add_argument("--locked-states", nargs="+", required=True)
    parser.add_argument("--coupled-axes", nargs="+", default=[])
    args = parser.parse_args()
    run(args.source_run, args.candidate_id, args.destination, args.axes, args.locked_states, args.coupled_axes)
