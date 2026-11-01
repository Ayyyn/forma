"""Use CAD-bench's unmodified STEP evaluator in an isolated Build123D runtime."""

import argparse
import ast
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--step", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oracle", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    vendor = root / "research/vendor/cad-bench"
    os.environ["CAD_BENCH_TASKS_ROOT"] = str(vendor / "dataset")
    sys.path.insert(0, str(vendor / "verifier"))
    from tasks.specs import load_task_spec

    spec = load_task_spec(args.task)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.oracle:
        # Only upstream reference programs are executed; model output stays
        # declarative JSON and is never evaluated as Python.
        tree = ast.parse(spec.reference_solution_code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = (
                    [node.module]
                    if isinstance(node, ast.ImportFrom)
                    else [n.name for n in node.names]
                )
                if any(m not in ("build123d", "math", "numpy") for m in modules):
                    raise ValueError("Unexpected reference import")
        from tasks.utils import execute_candidate_code
        from build123d import export_step

        part = execute_candidate_code(spec.reference_solution_code)
        args.step = args.output.with_suffix(".step")
        export_step(part, args.step)
    if args.step is None:
        raise ValueError("STEP path required")
    evaluation = spec.evaluate_step(
        args.step.resolve(),
        provenance_dir=args.output.parent / (args.output.stem + "-provenance"),
    )
    data = {
        "task_id": args.task,
        "raw": evaluation.raw,
        "metrics": evaluation.metrics,
        "oracle": args.oracle,
    }
    args.output.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "task": args.task,
                "overall_score": data["metrics"].get("overall_score"),
                "error": data["metrics"].get("error_message"),
            }
        )
    )


if __name__ == "__main__":
    main()
