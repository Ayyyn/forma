"""Restore exactly one remaining repair per null-content baseline failure."""

from pathlib import Path
import shutil
import time
from research.run_forma_full17 import ROOT, baseline, container, load, dump, summarize


def main():
    tasks = load(ROOT / "evaluation/forma-full17-v1/tasks.json")
    folder = ROOT / "output/forma/evaluation/full17-v1/build123d"
    archive = ROOT / "output/forma/evaluation/full17-baseline-client-failure"
    archive.mkdir(exist_ok=True)
    for name in ("summary.json", "aggregate.json", "rewards.jsonl"):
        if not (archive / name).exists():
            shutil.copy2(folder / name, archive / name)
    for task in tasks:
        dest = folder / task["id"]
        old = load(dest / "generation.json")
        if old.get("error") != "'NoneType' object has no attribute 'strip'":
            continue
        saved = archive / task["id"]
        if saved.exists():
            raise ValueError("Repair already started; inspect receipts")
        shutil.copytree(dest, saved)
        ident = old["receipt_run_id"]
        shutil.copytree(
            ROOT / "output/forma/studio/agent" / ident, saved / "original-receipts"
        )
        print("RESTORE SECOND ATTEMPT", task["id"], flush=True)
        started = time.monotonic()
        generation = baseline(task["prompt"], dest, ident, resume_empty=True)
        generation.update(
            elapsed_s=old["elapsed_s"] + time.monotonic() - started,
            receipt_run_id=ident,
            harness_repair="Null public content is handled as empty code; original first response and failed client run retained separately.",
        )
        dump(dest / "generation.json", generation)
        graded = (
            container("score", dest, dest / "verifier-after-client-fix", task["id"])
            if (dest / "candidate.step").exists()
            else {"error": "No valid STEP candidate"}
        )
        row = {
            "id": task["id"],
            "difficulty": task["difficulty"],
            "score": float(graded.get("metrics", {}).get("overall_score", 0)),
            "generation": generation,
            "grading": graded,
        }
        dump(dest / "result.json", row)
        summarize(folder, tasks)
        print("RESULT", task["id"], row["score"], generation["calls"], flush=True)
    summarize(folder, tasks)


if __name__ == "__main__":
    main()
