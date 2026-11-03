"""Offline audit of a retained, UNSELECTED Muse guide candidate.

No model request, visual acknowledgement or finish_design is fabricated.
The original candidate and its failed predecessor remain unchanged.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path

from crate_studio.design_tools import DesignSession
from crate_studio.workspace_agent import RUNS
from crate_studio.workspace_geometry import build_document
from crate_studio.motion_probe import translation_probe
from research.audit_size_states import direct_pose, run as audit_states


def run(run_id, candidate_id, destination):
    destination.mkdir(parents=True, exist_ok=False)
    candidate = json.loads(
        (RUNS / run_id / "candidates.json").read_text(encoding="utf-8")
    )[candidate_id]
    document = candidate["document"]
    reference = document["metadata"]["design_review"]
    source = {
        "source_kind": "unselected_model_candidate_with_offline_audit",
        "proposal": {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "document": document,
        },
        "target_reference": reference,
    }
    source_path = destination / "source.json"
    source_path.write_text(json.dumps(source, indent=2), encoding="utf-8")
    audit_states(source_path, destination / "independent-states")
    session = DesignSession(
        document,
        "Offline native audit only; no model selection or physical approval",
        destination / "native-tools",
    )
    native = {
        name: session.call(name, {"candidate_id": "base"})
        for name in ("check_interference", "verify_exports", "render_views")
    }
    spec = document["metadata"]["design_mechanism"]
    state_views = {
        s["name"]: session.call(
            "render_state",
            {"candidate_id": "base", "mechanism_spec": spec, "state_name": s["name"]},
        )
        for s in spec["states"]
    }
    built = build_document(document)
    state = next(s for s in spec["states"] if s["name"] == "large")
    posed = direct_pose(built["parts"], spec, state["values"])
    pair = [p for p in posed if p["id"] in ("body_001", "body_002")]
    directions = {
        "plus_y": [0, 1, 0],
        "minus_y": [0, -1, 0],
        "plus_z": [0, 0, 1],
        "minus_z": [0, 0, -1],
        "plus_x": [1, 0, 0],
        "minus_x": [-1, 0, 0],
    }
    probes = {
        name: translation_probe(pair, ["body_002"], axis, 2, 17)
        for name, axis in directions.items()
    }
    # Diagnose this actual SW/SE pair independently of the other corners.
    # Other walls/floors can obstruct a probe without manufacturing a guide.
    baseline = deepcopy(document)
    baseline["features"] = baseline["features"][:14]
    base_parts = direct_pose(build_document(baseline)["parts"], spec, state["values"])
    base_pair = [p for p in base_parts if p["id"] in ("body_001", "body_002")]
    baseline_escape = translation_probe(base_pair, ["body_002"], [0, 0, 1], 10, 21)
    assembly_values = {**state["values"], "se_x": 120}
    assembly_pair = [
        p
        for p in direct_pose(built["parts"], spec, assembly_values)
        if p["id"] in ("body_001", "body_002")
    ]
    insertion = translation_probe(assembly_pair, ["body_002"], [-1, 0, 0], 96, 41)
    report = {
        "source_run_id": run_id,
        "source_candidate_id": candidate_id,
        "fresh_model_call": False,
        "model_selected": False,
        "native_checks": native,
        "native_state_views": state_views,
        "pair_scope": "SW/SE guide pair in large state, isolated from other corners",
        "pair_probes": probes,
        "baseline_upward_escape": baseline_escape,
        "sampled_pair_insertion": insertion,
        "local_guide_checks_passed": baseline_escape["path_clear_at_samples"]
        and all(
            probes[n]["initial_pose_clear"] and not probes[n]["path_clear_at_samples"]
            for n in ("plus_y", "minus_y", "plus_z", "minus_z")
        )
        and all(probes[n]["path_clear_at_samples"] for n in ("plus_x", "minus_x"))
        and insertion["path_clear_at_samples"],
        "physical_validation": False,
        "global_retention_verified": False,
        "locking_verified": False,
        "unresolved": [
            "Two other physical guide interfaces",
            "Physical end stops and positive releasable locks",
            "Global and rotational retention",
            "Full assembly sequence and continuous path proof",
            "Stepped-floor usability, print/material/tolerance/load tests",
            "Model has not reviewed final state images or selected this candidate",
        ],
    }
    (destination / "audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "local_guide_checks_passed": report["local_guide_checks_passed"],
                "native_checks": {
                    k: (
                        {
                            "rendered": v.get("rendered"),
                            "delivered_to_model": v.get("image_delivered_to_model"),
                        }
                        if k == "render_views"
                        else v.get("passed")
                    )
                    for k, v in native.items()
                },
                "probes": {
                    k: {
                        "clear": v["path_clear_at_samples"],
                        "first_blocked_sample_mm": v["first_blocked_sample_mm"],
                    }
                    for k, v in probes.items()
                },
                "sampled_pair_insertion_clear": insertion["path_clear_at_samples"],
                "model_selected": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("candidate_id")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    run(args.run_id, args.candidate_id, args.destination)
