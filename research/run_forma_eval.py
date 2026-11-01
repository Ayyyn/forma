"""Frozen live evaluation, deterministic scoring and retained failure evidence."""

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import statistics
import shutil
import subprocess
import sys
import time

from crate_studio import workspace_agent as wa
from crate_studio.workspace_geometry import build_document, export_document
from crate_studio.workspace_requirements import requirement_state
from crate_studio.evaluation import analytic_geometry, DENSITIES

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "evaluation/forma-v1"


def dump(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_freeze():
    for name, sha in load(FROZEN / "manifest.json").items():
        if digest(FROZEN / name) != sha:
            raise ValueError("Frozen file changed: " + name)
    protocol = load(FROZEN / "protocol.json")
    vendor = ROOT / "research/vendor/cad-bench"
    for name, sha in protocol["upstream_file_hashes"].items():
        if digest(vendor / name) != sha:
            raise ValueError("Upstream task changed: " + name)
    return protocol


def normalized(doc):
    # Optional explicit false is semantically identical to omitted suppression.
    doc = deepcopy(doc)
    for f in doc["features"]:
        f["suppressed"] = bool(f.get("suppressed", False))
    return doc


def revision_score(task, proposal, output):
    checks = {"disposition": proposal.get("status") == task["expected"]["status"]}
    doc = proposal.get("document", {})
    if task["expected"]["status"] == "clarify":
        checks.update(
            unchanged=doc == task["document"], questions=bool(proposal.get("questions"))
        )
        return {"passed": all(checks.values()), "checks": checks}
    if not checks["disposition"]:
        return {"passed": False, "checks": checks}
    result = build_document(doc)
    checks["brep_valid"] = result["checks"]["passed"]
    if task["kind"] == "add_hole":
        expected = task["expected"]
        features = doc.get("features", [])
        checks["preserved_features"] = (
            features[: len(expected["preserved_features"])]
            == expected["preserved_features"]
        )
        extras = features[len(expected["preserved_features"]) :]
        checks["one_new_hole"] = (
            len(extras) == 1 and extras[0].get("type") == "cut_hole"
        )
        if checks["one_new_hole"]:
            p = extras[0].get("params", {})
            target = expected["new_hole"]
            checks["hole_location_size"] = all(
                abs(float(p.get(k, 0)) - v) < 1e-7 for k, v in target.items()
            )
            z = float(p.get("z", 0))
            checks["through_depth"] = z <= 0 and z + float(p.get("depth", 0)) >= 10
        before = build_document(task["document"])["metrics"]["volume_mm3"]
        checks["removed_volume"] = (
            abs(
                before
                - result["metrics"]["volume_mm3"]
                - expected["removed_volume_mm3"]
            )
            < 1e-5
        )
        # Only generated feature ID/name may vary; the rest of project stays intact.
        checks["preserved_project"] = all(
            doc.get(k) == v for k, v in task["document"].items() if k != "features"
        )
    else:
        reference = task["expected"]["document"]
        checks["exact_requested_state"] = normalized(doc) == normalized(reference)
        expected_geometry = build_document(reference)["metrics"]
        checks["expected_bounds"] = all(
            abs(a - b) < 1e-6
            for aa, bb in zip(
                result["metrics"]["bounds_mm"], expected_geometry["bounds_mm"]
            )
            for a, b in zip(aa, bb)
        )
        checks["expected_volume"] = (
            abs(result["metrics"]["volume_mm3"] - expected_geometry["volume_mm3"])
            < 1e-5
        )
        if task["kind"] == "enclosure":
            state = requirement_state(doc)
            checks["requirements_current"] = state["status"] == "current" and state.get(
                "passed", False
            )
            s = reference["metadata"]["source_spec"]
            independent = analytic_geometry(s, DENSITIES[s["material"]])
            checks["independent_shell_volume"] = (
                abs(result["metrics"]["volume_mm3"] - independent["solid_volume_mm3"])
                < 1e-5
            )
    if output is not None:
        exported = export_document(doc, None, output)
        checks["step_stl_readback"] = exported["checks"]["passed"]
    return {"passed": all(checks.values()), "checks": checks}


def public_score(task, proposal, output):
    if proposal.get("status") != "ready":
        return {
            "passed": False,
            "error": "No ready geometry proposal",
            "overall_score": 0.0,
        }
    result = export_document(proposal["document"], None, output)
    if not result["checks"]["passed"]:
        return {
            "passed": False,
            "error": "STEP/STL export failed",
            "overall_score": 0.0,
        }
    score_path = output / "upstream-score.json"
    cmd = [
        str(ROOT / "research/vendor/cadbench-runtime/Scripts/python.exe"),
        str(ROOT / "research/cadbench_score.py"),
        "--task",
        task["id"],
        "--step",
        str((output / "workspace.step").resolve()),
        "--output",
        str(score_path.resolve()),
    ]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=150)
    (output / "evaluator-stdout.txt").write_text(run.stdout, encoding="utf-8")
    (output / "evaluator-stderr.txt").write_text(run.stderr, encoding="utf-8")
    if run.returncode or not score_path.exists():
        return {"passed": False, "overall_score": 0.0, "error": run.stderr[-1500:]}
    score = load(score_path)["metrics"]
    return {
        "passed": score.get("build_success") == 1
        and score.get("overall_score", 0) >= 0.95,
        "overall_score": score.get("overall_score", 0),
        "metrics": score,
    }


def summarize(folder):
    rows = [load(p) for p in sorted(folder.glob("*/result.json"))]
    groups = {}
    for group in ("revision", "public"):
        selected = [r for r in rows if r["group"] == group]
        times = [r["elapsed_s"] for r in selected]
        groups[group] = {
            "count": len(selected),
            "first_pass_success": sum(r["first_pass"]["passed"] for r in selected),
            "verified_success": sum(r["verified"]["passed"] for r in selected),
            "failures": [r["id"] for r in selected if not r["verified"]["passed"]],
            "median_latency_s": statistics.median(times) if times else None,
            "max_latency_s": max(times) if times else None,
            "estimated_model_cost_usd": sum(
                r.get("estimated_cost_usd", 0) for r in selected
            ),
        }
        if group == "public":
            groups[group]["mean_upstream_overall_score"] = (
                statistics.mean(r["verified"].get("overall_score", 0) for r in selected)
                if selected
                else None
            )
    result = {
        "groups": groups,
        "completed": len(rows),
        "expected": 31,
        "rows": rows,
        "scope": "Frozen public development subset plus constructed revisions; no held-out/physical/official leaderboard claim.",
    }
    dump(folder / "results.json", result)
    return result


def run(folder, group, limit, live, ids=None, context_mode=None, reasoning_effort=None):
    protocol = verify_freeze()
    folder.mkdir(parents=True, exist_ok=True)
    source_hashes = {p.name: digest(p) for p in (ROOT / "crate_studio").glob("*.py")}
    if (folder / "run-manifest.json").exists() and load(folder / "run-manifest.json")[
        "source_hashes"
    ] != source_hashes:
        raise ValueError(
            "Application source changed: retain this run and use a new run name"
        )
    if (folder / "run-manifest.json").exists():
        manifest = load(folder / "run-manifest.json")
        if manifest.get("context_mode") != (
            context_mode or wa.DEFAULT_CONTEXT_MODE
        ) or manifest.get("reasoning_effort") != (
            reasoning_effort or wa.DEFAULT_REASONING_EFFORT
        ):
            raise ValueError("Planner policy changed; use a new run name")
    if not (folder / "run-manifest.json").exists():
        dump(
            folder / "run-manifest.json",
            {
                "protocol_sha256": digest(FROZEN / "protocol.json"),
                "source_hashes": source_hashes,
                "runner_sha256": digest(Path(__file__)),
                "start_conservative_spend_usd": wa.estimated_spend(),
                "maximum_calls_per_task": 2,
                "context_mode": context_mode or wa.DEFAULT_CONTEXT_MODE,
                "reasoning_effort": reasoning_effort or wa.DEFAULT_REASONING_EFFORT,
                "exact_proposal_cache_bypassed": True,
                "requested_task_ids": ids,
                "task_payload": "Only frozen synthetic revision documents and public CAD task geometry instructions; no user project data.",
            },
        )
    tasks = []
    for name in ("revision", "public"):
        if group in ("all", name):
            tasks.extend(
                (name, t)
                for t in load(
                    FROZEN
                    / (
                        "revision-tasks.json"
                        if name == "revision"
                        else "public-tasks.json"
                    )
                )
            )
    count = 0
    for name, task in tasks:
        if ids is not None and task["id"] not in ids:
            continue
        dest = folder / task["id"]
        if (dest / "result.json").exists():
            continue
        if limit is not None and count >= limit:
            break
        dest.mkdir(parents=True, exist_ok=True)
        if (dest / "proposal.json").exists():
            proposal = load(dest / "proposal.json")
            elapsed = load(dest / "timing.json")["elapsed_s"]
        else:
            if not live:
                raise ValueError("Generation requires explicit --live")
            if (dest / "started.json").exists():
                raise ValueError(
                    "Interrupted request: inspect existing receipts before retrying "
                    + task["id"]
                )
            runid = "eval-" + folder.name + "-" + task["id"]
            dump(dest / "started.json", {"run_id": runid})
            start = time.monotonic()
            proposal = wa.propose_document(
                task["document"],
                task["prompt"],
                run_id=runid,
                selection_context=task.get("selection", {}),
                context_mode=context_mode,
                reasoning_effort=reasoning_effort,
                use_cache=False,
            )
            elapsed = time.monotonic() - start
            dump(dest / "timing.json", {"elapsed_s": elapsed})
            dump(dest / "proposal.json", proposal)
        first = {"status": "invalid", "document": task["document"], "questions": []}
        events_path = wa.RUNS / proposal["run_id"] / "events.jsonl"
        events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
        ]
        responses = [e for e in events if e["kind"] == "response"]
        if responses:
            try:
                first = wa.apply_plan(
                    task["document"],
                    wa.parse_plan(responses[0]["public_response"]),
                    task["prompt"],
                )
            except (ValueError, TypeError, KeyError) as error:
                first["error"] = str(error)
        dump(dest / "first-pass-proposal.json", first)
        scorer = revision_score if name == "revision" else public_score
        first_score = scorer(task, first, dest / "first-pass")
        reused_score = all(
            first.get(k) == proposal.get(k) for k in ("status", "document", "questions")
        )
        if reused_score:
            verified = deepcopy(first_score)
            if (dest / "first-pass").exists():
                shutil.copytree(
                    dest / "first-pass", dest / "verified", dirs_exist_ok=True
                )
        else:
            verified = scorer(task, proposal, dest / "verified")
        row = {
            "id": task["id"],
            "group": name,
            "calls": proposal.get("calls", 0),
            "response_ids": proposal.get("response_ids", []),
            "estimated_cost_usd": proposal.get("estimated_cost_usd", 0),
            "elapsed_s": elapsed,
            "first_pass": first_score,
            "verified": verified,
            "identical_first_final_scoring_reused": reused_score,
        }
        dump(dest / "result.json", row)
        count += 1
        summarize(folder)
        print(
            json.dumps(
                {
                    "task": task["id"],
                    "passed": verified["passed"],
                    "calls": row["calls"],
                    "elapsed_s": round(elapsed, 2),
                    "score": verified.get("overall_score"),
                }
            ),
            flush=True,
        )
        if not proposal.get("calls"):
            raise ValueError("No live response; stop to inspect app cap or credentials")
    summary = summarize(folder)
    print(
        json.dumps({"completed": summary["completed"], "groups": summary["groups"]}),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=("all", "revision", "public"), default="all")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--context-mode", choices=("full", "compact", "focused"))
    parser.add_argument("--reasoning-effort", choices=("low", "medium"))
    args = parser.parse_args()
    run(
        args.output,
        args.group,
        args.limit,
        args.live,
        args.ids,
        args.context_mode,
        args.reasoning_effort,
    )


if __name__ == "__main__":
    main()
