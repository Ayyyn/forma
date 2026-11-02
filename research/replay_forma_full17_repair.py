"""Failure-driven engine ablation: fixed threads, identical original model plans.

This is explicitly NOT a fresh inference run. Other features use identical
original STEP bytes and scoring records. No task, plan or grader is edited.
"""

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from crate_studio.workspace_geometry import export_document
from research.run_forma_full17 import container, digest, dump, load, summarize, ROOT

INITIAL = ROOT / "output/forma/evaluation/full17-v1/forma"
OUT = ROOT / "output/forma/evaluation/full17-thread-repair/forma"
FREEZE = ROOT / "evaluation/forma-full17-thread-repair"


def function_asts(path):
    tree = ast.parse(path.read_text(encoding="utf8"))
    return {
        n.name: ast.dump(n, include_attributes=False)
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    }


def main():
    tasks = load(ROOT / "evaluation/forma-full17-v1/tasks.json")
    old = (
        ROOT
        / "output/forma/evaluation/full17-v1/source-snapshot/crate_studio/mechanical_features.py"
    )
    new = ROOT / "crate_studio/mechanical_features.py"
    a, b = function_asts(old), function_asts(new)
    changed = [k for k in a.keys() | b.keys() if a.get(k) != b.get(k)]
    if changed != ["threaded_shaft"]:
        raise ValueError("Repair must affect only threaded_shaft: " + str(changed))
    protocol = {
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "Post-failure deterministic engine replay, not fresh inference or held-out validation",
        "tasks": 17,
        "original_protocol": "evaluation/forma-full17-v1",
        "changes": changed,
        "rationale": "First run exposed discarded helical crests. Native sweep and fuse-before-trim repair; validate core retention and ridge volume.",
        "no_plan_changes": True,
        "no_new_model_calls": True,
        "unchanged_tasks": "Reuse identical original STEP bytes and unmodified grader records, with hashes and explicit origin. No synthetic success values.",
        "regraded_types": ["threaded_body", "socket_head_screw"],
        "inputs": {t["id"]: digest(INITIAL / t["id"] / "proposal.json") for t in tasks},
        "sources": {
            p.relative_to(ROOT).as_posix(): digest(p)
            for p in sorted((ROOT / "crate_studio").rglob("*"))
            if p.is_file() and p.suffix in (".py", ".js", ".html", ".css")
        },
    }
    if not FREEZE.exists():
        FREEZE.mkdir(parents=True)
        dump(FREEZE / "protocol.json", protocol)
        dump(
            FREEZE / "manifest.json",
            {"protocol.json": digest(FREEZE / "protocol.json")},
        )
        snap = OUT.parent / "source-snapshot"
        for name in protocol["sources"]:
            p = snap / name
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, p)
    else:
        frozen = load(FREEZE / "protocol.json")
        if (
            frozen["inputs"] != protocol["inputs"]
            or frozen["sources"] != protocol["sources"]
        ):
            raise ValueError("Repair freeze changed; use a new named experiment")
    OUT.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        ident = task["id"]
        src = INITIAL / ident
        dest = OUT / ident
        dest.mkdir(exist_ok=True)
        if (dest / "result.json").exists():
            continue
        proposal = load(src / "proposal.json")
        affected = any(
            f["type"] in ("threaded_body", "socket_head_screw")
            for f in proposal["document"]["features"]
        )
        if not affected:
            if not (src / "result.json").exists():
                continue
            shutil.copy2(src / "candidate.step", dest / "candidate.step")
            row = load(src / "result.json")
            row["engine_replay"] = {
                "source": str(src.relative_to(ROOT)),
                "identical_step_sha256": digest(src / "candidate.step"),
                "grader_reused": True,
                "reason": "Thread repair does not affect these feature types; unchanged function ASTs checked.",
            }
            dump(dest / "result.json", row)
        else:
            print("REBUILD", ident, flush=True)
            exported = export_document(proposal["document"], None, dest / "exports")
            dump(dest / "export.json", exported)
            if exported.get("checks", {}).get("step_roundtrip", {}).get("passed"):
                shutil.copy2(dest / "exports/workspace.step", dest / "candidate.step")
                graded = container("score", dest, dest / "verifier", ident)
            else:
                graded = {"error": "Repaired export failed"}
            row = {
                "id": ident,
                "difficulty": task["difficulty"],
                "score": float(graded.get("metrics", {}).get("overall_score", 0)),
                "generation": load(src / "generation.json"),
                "grading": graded,
                "engine_replay": {
                    "source": str(src.relative_to(ROOT)),
                    "original_plan_sha256": digest(src / "proposal.json"),
                    "grader_reused": False,
                    "new_model_calls": 0,
                },
            }
            dump(dest / "result.json", row)
            print("REPAIRED RESULT", ident, row["score"], flush=True)
    summarize(OUT, tasks)


if __name__ == "__main__":
    main()
