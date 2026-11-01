"""Check all selected upstream reference programs with the unchanged scorer."""

import json
from pathlib import Path
import sys
from .cadbench_score import main as score


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "output/forma/evaluation/oracles"
    output.mkdir(parents=True, exist_ok=True)
    tasks = json.loads((root / "evaluation/forma-v1/public-tasks.json").read_text())
    rows = []
    for task in tasks:
        target = output / (task["id"] + ".json")
        if not target.exists():
            sys.argv = [
                "cadbench_score",
                "--task",
                task["id"],
                "--oracle",
                "--output",
                str(target),
            ]
            score()
        row = json.loads(target.read_text())
        rows.append(
            {
                "id": task["id"],
                "score": row["metrics"].get("overall_score"),
                "error": row["metrics"].get("error_message"),
            }
        )
        (output / "results.json").write_text(
            json.dumps(rows, indent=2), encoding="utf-8"
        )
    print(json.dumps({"count": len(rows), "rows": rows}), flush=True)


if __name__ == "__main__":
    main()
