"""Explicit public-task development experiments; never a held-out evaluation.

Documents/patches are developer-authored inputs. Keep each experiment in a new
directory; preserve the original model plan, applied patch and source hashes.
This runner makes no model calls and never supplies grader data to production.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from crate_studio.workspace_geometry import export_document
from research.run_forma_full17 import ROOT, container, digest, dump, load


def run(task, output, *, document=None, patch=None):
    output = Path(output).resolve()
    output.relative_to(ROOT / "output")
    output.mkdir(parents=True, exist_ok=False)
    tasks = load(ROOT / "evaluation/forma-full17-v1/tasks.json")
    selected = next(t for t in tasks if t["id"] == task)
    source = ROOT / "output/forma/evaluation/full17-v1/forma" / task / "proposal.json"
    original = load(source)
    doc = deepcopy(document if document is not None else original["document"])
    for ident, changes in (patch or {}).items():
        feature = next(f for f in doc["features"] if f["id"] == ident)
        feature["params"].update(changes)
    dump(output / "document.json", doc)
    for path in sorted((ROOT / "crate_studio").glob("*.py")):
        target = output / "source-snapshot" / "crate_studio" / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    dump(
        output / "development.json",
        {
            "utc": datetime.now(timezone.utc).isoformat(),
            "mode": "Public diagnostic development; developer-authored edits, not fresh inference",
            "task": task,
            "difficulty": selected["difficulty"],
            "original_proposal_sha256": digest(source),
            "document_replaced": document is not None,
            "patch": patch or {},
            "new_model_calls": 0,
            "source_hashes": {
                p.relative_to(ROOT).as_posix(): digest(p)
                for p in sorted((ROOT / "crate_studio").glob("*.py"))
            },
        },
    )
    try:
        exported = export_document(doc, None, output / "exports")
        dump(output / "export.json", exported)
        if not exported["checks"].get("step_roundtrip", {}).get("passed"):
            raise ValueError(
                "Native export/preflight failed: "
                + str(exported["checks"].get("error", "STEP roundtrip failed"))
            )
        shutil.copy2(output / "exports/workspace.step", output / "candidate.step")
        graded = container("score", output, output / "verifier", task)
        result = {
            "id": task,
            "score": float(graded.get("metrics", {}).get("overall_score", 0)),
            "grading": graded,
        }
    except Exception as exc:
        result = {"id": task, "score": 0, "error": str(exc)}
    dump(output / "result.json", result)
    print(json.dumps(result), flush=True)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--patch", type=Path)
    p.add_argument("--document", type=Path)
    a = p.parse_args()
    run(
        a.task,
        a.output,
        document=load(a.document) if a.document else None,
        patch=load(a.patch) if a.patch else None,
    )


if __name__ == "__main__":
    main()
