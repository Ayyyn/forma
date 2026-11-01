"""Frozen selection cases, paired live policies, and exact-reuse measurements."""

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from crate_studio import workspace_agent as wa
from crate_studio.workspace_geometry import build_document, export_document
from crate_studio.workspace_cache import cached_build, cache_clear
from .run_forma_eval import ROOT, dump, load, normalized, verify_freeze

DEST = ROOT / "output/forma/evaluation/performance"


def feature(ident, kind, **params):
    return {
        "id": ident,
        "type": kind,
        "name": ident,
        "params": params,
        "suppressed": False,
    }


def document(features):
    return {
        "name": "Synthetic selection fixture",
        "features": features,
        "metadata": {"brief": "Retain all unmentioned features and dimensions."},
        "annotations": [],
        "display": {},
    }


def prepare():
    DEST.mkdir(parents=True, exist_ok=False)
    cases = []
    box = document([feature("base", "box", width=40, depth=30, height=10)])
    r = build_document(box)
    top = next(f for f in r["face_meshes"] if f["normal"][2] > 0.99)
    edge = next(e for e in r["edge_meta"] if abs(e["start"][2] - e["end"][2]) > 9.9)

    def add(ident, doc, prompt, selection, extra=None, expected=None, status="ready"):
        target = deepcopy(expected or doc)
        if extra:
            target["features"].append(extra)
        cases.append(
            {
                "id": ident,
                "document": doc,
                "prompt": prompt,
                "selection": selection,
                "expected": {"status": status, "document": target},
                "added_feature": bool(extra),
            }
        )

    add(
        "selected-face",
        box,
        "Push the selected planar face outward by exactly 2 mm. Preserve the existing box feature; append one face_offset feature using the supplied selected face ordinal.",
        {"topology_ids": [top["id"]]},
        feature(
            "expected",
            "face_offset",
            part_id="body_001",
            face_index=top["face_index"],
            distance=2,
        ),
    )
    add(
        "selected-edge",
        box,
        "Fillet only the selected edge with radius 1 mm. Preserve the original box and append one fillet feature using the supplied edge index, leaving every unselected edge untreated.",
        {"topology_ids": [edge["id"]]},
        feature(
            "expected",
            "fillet",
            part_id="body_001",
            edge_indices=[edge["edge_index"]],
            radius=1,
        ),
    )
    add(
        "missing-selection",
        box,
        "Push the selected planar face outward by 2 mm, but no face has been selected. Do not guess a face; ask me to select it.",
        {},
        status="clarify",
    )
    pair = document(
        [
            feature("fixed", "box", width=10, depth=10, height=10),
            feature(
                "moving",
                "box",
                width=10,
                depth=10,
                height=10,
                cx=30,
                operation="new_body",
            ),
        ]
    )
    faces = build_document(pair)["face_meshes"]
    source = next(
        f for f in faces if f["part_id"] == "body_002" and f["normal"][2] < -0.99
    )
    target = next(
        f for f in faces if f["part_id"] == "body_001" and f["normal"][2] > 0.99
    )
    add(
        "selected-mate",
        pair,
        "Add one coincident mate, zero offset, aligning the selected bottom face of moving body_002 onto the selected top face of fixed body_001. Move only body_002. Preserve both source box definitions.",
        {"topology_ids": [source["id"], target["id"]]},
        feature(
            "expected",
            "mate",
            source_part_id="body_002",
            source_face=source["face_index"],
            target_part_id="body_001",
            target_face=target["face_index"],
            offset=0,
            mode="coincident",
        ),
    )
    poly = document(
        [
            feature(
                "profile",
                "sketch_extrude",
                shape="polyline",
                points=[
                    [
                        round(20 * math.cos(i * math.tau / 128), 8),
                        round(20 * math.sin(i * math.tau / 128), 8),
                    ]
                    for i in range(128)
                ],
                height=3,
            )
        ]
    )
    expected = deepcopy(poly)
    expected["features"][0]["params"]["height"] = 5
    add(
        "dense-profile",
        poly,
        "Set the profile extrusion height to exactly 5 mm. Preserve every outline point, position and all other project data.",
        {"feature_id": "profile"},
        expected=expected,
    )
    pattern = document(
        [
            feature("seed", "box", width=10, depth=8, height=3),
            feature(
                "copies", "linear_pattern", count=3, spacing=[25, 0, 0], fuse=False
            ),
        ]
    )
    expected = deepcopy(pattern)
    expected["features"][0]["params"]["width"] = 12
    add(
        "dependency-pattern",
        pattern,
        "Set the seed box width to exactly 12 mm. Retain its depth and height, the existing three-copy pattern, its spacing and all other data.",
        {"feature_id": "seed"},
        expected=expected,
    )
    dump(DEST / "selection-cases.json", cases)
    for case in cases:
        assert (
            case["expected"]["status"] == "clarify"
            or build_document(case["expected"]["document"])["checks"]["passed"]
        )
    dump(
        DEST / "protocol.json",
        {
            "cases_sha256": hashlib.sha256(
                (DEST / "selection-cases.json").read_bytes()
            ).hexdigest(),
            "policies": {
                "control": {"context_mode": "full", "reasoning_effort": "medium"},
                "candidate": {"context_mode": "focused", "reasoning_effort": "low"},
            },
            "gate": "No per-task loss on six paired cases; no loss in counts on frozen 20 revision and 11 public tasks versus retained results. Original failures remain visible. No speed claim without measured live receipts. No aggregate counts invented for unrun policies.",
            "proposal_cache_bypassed": True,
            "scope": "Constructed development cases, not held out. No physical ring or strength evaluation.",
        },
    )
    snapshot = DEST / "source-snapshot"
    snapshot.mkdir()
    for path in (ROOT / "crate_studio").glob("*.py"):
        (snapshot / path.name).write_bytes(path.read_bytes())
    print({"prepared_cases": len(cases)}, flush=True)


def score(case, proposal, path):
    if case["expected"]["status"] == "clarify":
        checks = {
            "clarify": proposal["status"] == "clarify",
            "unchanged": proposal["document"] == case["document"],
            "questions": bool(proposal.get("questions")),
        }
    else:
        actual = deepcopy(proposal["document"])
        expected = case["expected"]["document"]
        if case["added_feature"] and len(actual["features"]) == len(
            expected["features"]
        ):
            actual["features"][-1]["id"] = expected["features"][-1]["id"]
            actual["features"][-1]["name"] = expected["features"][-1]["name"]
            # Only documented default mate offset/mode may be omitted.
            if actual["features"][-1]["type"] == "mate":
                actual["features"][-1]["params"].setdefault("offset", 0)
                actual["features"][-1]["params"].setdefault("mode", "coincident")
        checks = {
            "ready": proposal["status"] == "ready",
            "exact_feature_and_project_contract": normalized(actual)
            == normalized(expected),
        }
        if checks["ready"]:
            checks["step_stl_readback"] = export_document(
                proposal["document"], None, path
            )["checks"]["passed"]
    return {"passed": all(checks.values()), "checks": checks}


def run(variant):
    protocol = load(DEST / "protocol.json")
    assert (
        hashlib.sha256((DEST / "selection-cases.json").read_bytes()).hexdigest()
        == protocol["cases_sha256"]
    )
    for path in (DEST / "source-snapshot").glob("*.py"):
        assert (
            path.read_bytes() == (ROOT / "crate_studio" / path.name).read_bytes()
        ), "Source changed during comparison"
    policy = protocol["policies"][variant]
    rows = []
    for case in load(DEST / "selection-cases.json"):
        directory = DEST / variant / case["id"]
        directory.mkdir(parents=True, exist_ok=True)
        if (directory / "result.json").exists():
            rows.append(load(directory / "result.json"))
            continue
        if (directory / "proposal.json").exists():
            proposal = load(directory / "proposal.json")
            elapsed = load(directory / "timing.json")["elapsed_s"]
        else:
            assert not (
                directory / "started.json"
            ).exists(), "Inspect interrupted run rather than repeat paid call"
            run_id = "perf-" + variant + "-" + case["id"]
            dump(directory / "started.json", {"run_id": run_id})
            start = time.perf_counter()
            proposal = wa.propose_document(
                case["document"],
                case["prompt"],
                selection_context=case["selection"],
                run_id=run_id,
                use_cache=False,
                **policy
            )
            elapsed = time.perf_counter() - start
            dump(directory / "proposal.json", proposal)
            dump(directory / "timing.json", {"elapsed_s": elapsed})
        verdict = score(case, proposal, directory / "exports")
        row = {
            "id": case["id"],
            **verdict,
            "elapsed_s": elapsed,
            "estimated_cost_usd": proposal["estimated_cost_usd"],
            "calls": proposal["calls"],
            "run_id": proposal["run_id"],
        }
        rows.append(row)
        dump(directory / "result.json", row)
        print(json.dumps(row), flush=True)
        if not proposal["calls"]:
            raise ValueError("No response; inspect cap")
    summary = {
        "rows": rows,
        "passed": sum(r["passed"] for r in rows),
        "count": len(rows),
        "median_latency_s": statistics.median(r["elapsed_s"] for r in rows),
        "estimated_cost_usd": sum(r["estimated_cost_usd"] for r in rows),
    }
    dump(DEST / variant / "results.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--variant", choices=("control", "candidate"))
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        run(args.variant)
