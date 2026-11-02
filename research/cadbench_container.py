"""Trusted container entry points. Candidate code is executed ONLY in the agent image.

The agent image has no verifier, reference CAD, network, secrets or host project.
The separate verifier image grades STEP through upstream's unchanged API.
"""

import argparse
import json
from pathlib import Path
import time
import traceback


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["build", "score", "oracle"])
    p.add_argument("--task")
    args = p.parse_args()
    out = Path("/output")
    started = time.monotonic()
    try:
        if args.mode == "build":
            import build123d as b
            import math
            import numpy

            # OS/container isolation is the security boundary, not Python eval.
            namespace = {
                name: getattr(b, name) for name in dir(b) if not name.startswith("_")
            }
            namespace.update(build123d=b, b3d=b, math=math, np=numpy, numpy=numpy)
            exec(
                compile(Path("/input/final.py").read_text(), "final.py", "exec"),
                namespace,
                namespace,
            )
            part = namespace["part"]
            if hasattr(part, "part"):
                part = part.part
            solids = list(part.solids())
            if not solids or not all(s.is_valid and s.volume > 0 for s in solids):
                raise ValueError("Candidate has no valid positive-volume solids")
            b.export_step(part, out / "candidate.step")
            reread = b.import_step(out / "candidate.step")
            if len(reread.solids()) != len(solids) or not reread.is_valid:
                raise ValueError("STEP read-back failed")
            data = {
                "passed": True,
                "solid_count": len(solids),
                "volume_mm3": part.volume,
            }
        else:
            from tasks.specs import load_task_spec

            spec = load_task_spec(args.task)
            if args.mode == "oracle":
                # Developer calibration only. Never exposed to either model.
                code = spec.reference_solution_code
                result = spec.evaluate_code(
                    code, llm_generated=False, provenance_dir=out / "scoring"
                )
            else:
                result = spec.evaluate_step(
                    Path("/input/candidate.step"), provenance_dir=out / "scoring"
                )
            data = {"metrics": result.metrics, "raw": result.raw}
    except Exception as exc:
        data = {
            "passed": False,
            "error": str(exc)[:1500],
            "traceback": traceback.format_exc(),
        }
    data["elapsed_s"] = time.monotonic() - started
    (out / "result.json").write_text(
        json.dumps(data, indent=2, default=str, allow_nan=False)
    )
    print(json.dumps(data, default=str), flush=True)


if __name__ == "__main__":
    main()
