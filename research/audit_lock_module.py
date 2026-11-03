"""Offline diagnosis of retained unselected lock CAD and model motion proposals.

Never promotes the draft or silently treats a prose motion suggestion as a
previously executed model tool call. Original CAD is kept unchanged.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from crate_studio.workspace_agent import RUNS
from crate_studio.workspace_geometry import build_document
from crate_studio.mechanism_study import mechanism_study, validate_spec
from crate_studio.motion_probe import prismatic_pair_probe
from crate_studio.design_tools import DesignSession
from crate_studio.floor_check import floor_coverage
from research.audit_size_states import direct_pose


def run(cad_run, candidate_id, motion_run, destination, proposed_pin_lock=None):
    destination.mkdir(parents=True, exist_ok=False)
    cad_source = RUNS / cad_run / "candidates.json"
    document = json.loads(cad_source.read_text(encoding="utf-8"))[candidate_id][
        "document"
    ]
    events = [
        json.loads(line)
        for line in (RUNS / motion_run / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    last = next(
        e
        for e in reversed(events)
        if e.get("kind") == "tool" and e.get("tool") == "check_motion"
    )
    original = last["arguments"]["spec"]
    built = build_document(document)
    variants = {"last_executed_model_spec": original}
    if proposed_pin_lock is not None:
        suggested = deepcopy(original)
        pin = next(j for j in suggested["joints"] if j["id"] == "pin_z")
        old = pin["limits"][0]
        pin["limits"][0] = proposed_pin_lock
        for state in suggested["states"]:
            if state["values"]["pin_z"] == old:
                state["values"]["pin_z"] = proposed_pin_lock
        variants["prose_suggested_pin_value_offline_interpretation"] = suggested
    studies, floors = {}, {}
    reference = document["metadata"]["design_review"]["reports"]
    for name, raw in variants.items():
        spec = validate_spec(raw, [p["id"] for p in built["parts"]])
        study = mechanism_study(document, built, spec)
        (destination / (name + ".json")).write_text(
            json.dumps(study, indent=2), encoding="utf-8"
        )
        studies[name] = {
            "passed": study["passed"],
            "samples": study["sample_count"],
            "collision_poses": study["collision_sample_count"],
            "failed_samples": [
                {k: f[k] for k in ("segment", "fraction", "values", "overlaps")}
                for f in study["frames"]
                if f["overlaps"]
            ][:6],
        }
        floors[name] = []
        for state in spec["states"]:
            key = (
                "rectangular"
                if state["name"].startswith("rect")
                else state["name"].split("_")[0]
            )
            target = reference["floor:state:" + key]["footprint"]
            report, *_ = floor_coverage(
                direct_pose(built["parts"], spec, state["values"]), target
            )
            floors[name].append(
                {
                    "state": state["name"],
                    "passed": report["passed"],
                    "missing_area_mm2": report["missing_area_mm2"],
                }
            )
    stops = {
        state: prismatic_pair_probe(built["parts"], original, "se_x", state, 2, 17)
        for state in ("small_unlocked", "large_unlocked")
    }
    session = DesignSession(
        document,
        "Offline unselected locking-module audit",
        destination / "native-tools",
    )
    exports = session.call("verify_exports", {"candidate_id": "base"})
    session.call("render_views", {"candidate_id": "base"})
    report = {
        "cad_run": cad_run,
        "candidate": candidate_id,
        "cad_ledger_sha256": hashlib.sha256(cad_source.read_bytes()).hexdigest(),
        "motion_run": motion_run,
        "fresh_model_call": False,
        "model_selected": False,
        "proposed_pin_lock": proposed_pin_lock,
        "motion_variants": studies,
        "floor_checks": floors,
        "isolated_stop_probes": stops,
        "exports_passed": exports.get("passed", False),
        "exports": exports,
        "physical_validation": False,
        "global_retention_verified": False,
        "locking_verified": False,
        "scope": "Unchanged model CAD. Original tool-called motion retained separately from an explicitly supplied interpretation of its later prose pin value. Native pose/mesh diagnostics only; failed full-path checks prevent lock qualification even when endpoint stops obstruct local overtravel.",
    }
    (destination / "audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "motion": studies,
                "exports_passed": report["exports_passed"],
                "small_negative_stop": stops["small_unlocked"]["directions"][
                    "axial_negative"
                ],
                "large_positive_stop": stops["large_unlocked"]["directions"][
                    "axial_positive"
                ],
                "model_selected": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cad_run")
    parser.add_argument("candidate_id")
    parser.add_argument("motion_run")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--proposed-pin-lock", type=float)
    args = parser.parse_args()
    run(
        args.cad_run,
        args.candidate_id,
        args.motion_run,
        args.destination,
        args.proposed_pin_lock,
    )
