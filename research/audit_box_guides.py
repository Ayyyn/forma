"""Offline independent all-state audit of a selected model guide proposal.

The earlier model-authored un-guided source is a control, not a fresh AI run.
"""

import argparse
import hashlib
import json
from pathlib import Path

from crate_studio.workspace_geometry import build_document
from crate_studio.motion_probe import prismatic_pair_probe
from research.audit_size_states import run as audit_states


def run(source, baseline, destination):
    destination.mkdir(parents=True, exist_ok=False)
    proposal = json.loads(source.read_text(encoding="utf-8"))["proposal"]
    old = json.loads(baseline.read_text(encoding="utf-8"))["proposal"]
    if proposal["status"] != "ready":
        raise ValueError(
            "A selected model proposal is required; do not fabricate selection"
        )
    document = proposal["document"]
    spec = document["metadata"]["design_mechanism"]
    audit_states(source, destination / "states")
    parts = build_document(document)["parts"]
    old_parts = build_document(old["document"])["parts"]
    rows = []
    for joint in spec["joints"]:
        if joint["type"] != "prismatic":
            continue
        for state in spec["states"]:
            current = prismatic_pair_probe(
                parts, spec, joint["id"], state["name"], 2, 17
            )
            control = prismatic_pair_probe(
                old_parts, spec, joint["id"], state["name"], 2, 17
            )
            transverse = {
                k: v
                for k, v in current["directions"].items()
                if k.startswith("transverse")
            }
            upward = next(
                k
                for k, v in current["directions"].items()
                if max(abs(x - y) for x, y in zip(v["direction_world"], [0, 0, 1]))
                < 1e-8
            )
            rows.append(
                {
                    "joint": joint["id"],
                    "state": state["name"],
                    "current": current,
                    "baseline_upward": control["directions"][upward],
                    "all_four_transverse_locally_blocked": all(
                        v["initial_pose_clear"] and not v["path_clear_at_samples"]
                        for v in transverse.values()
                    ),
                    "upward_escape_removed_against_control": control["directions"][
                        upward
                    ]["path_clear_at_samples"]
                    and not current["directions"][upward]["path_clear_at_samples"],
                }
            )
    states = json.loads(
        (destination / "states/verification.json").read_text(encoding="utf-8")
    )
    report = {
        "source_run_id": proposal["run_id"],
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "baseline_source_run_id": old["run_id"],
        "baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest(),
        "fresh_model_call": False,
        "states_passed": states["passed"],
        "pairs_checked": len(rows),
        "pair_checks_passed": all(
            r["all_four_transverse_locally_blocked"]
            and r["upward_escape_removed_against_control"]
            for r in rows
        ),
        "rows": rows,
        "physical_validation": False,
        "global_retention_verified": False,
        "locking_verified": False,
        "scope": "Independent source rebuild and direct per-joint native state/ray controls, plus isolated parent/child six-direction probes at0.125 mm sample spacing over2 mm. Former no-guide model source is a control for upward escape. Local obstruction is not rotational/global captivity, end-stop/lock function, continuous motion, strength or print fit.",
    }
    (destination / "audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    run(args.source, args.baseline, args.destination)
