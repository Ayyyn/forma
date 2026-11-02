"""Freeze all public prompts and a matched Meta-only comparison before inference."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "evaluation/forma-full17-v1"
VENDOR = ROOT / "research/vendor/cad-bench"
BASELINE_SYSTEM = """You are a mechanical CAD engineer using Python 3.11 and Build123D 0.10.0. Return only a complete Python program, optionally in a single Python code fence. Define the completed Build123D object in top-level variable part. Only build123d, math and numpy are available. Do not read files, reference solutions or external assets, write files, access the network, render or call show_object. The harness exports your part to STEP and checks solid validity. Use independent solids for moving assembly components. Follow every geometric requirement and reason about dimensions, meshing, orientation and fit. You may receive actual build errors for one repair. There is no grader feedback during generation."""


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(p, x):
    p.write_text(
        json.dumps(x, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf8",
    )


def main():
    DEST.mkdir(parents=True, exist_ok=False)
    tasks = []
    for path in VENDOR.glob("dataset/*/contract.toml"):
        meta = tomllib.loads(path.read_text(encoding="utf8"))
        text = path.with_name("instruction.md").read_text(encoding="utf8")
        geometry = text.split("Submission contract")[0].strip()
        if geometry == text.strip():
            raise ValueError("Missing submission footer")
        tasks.append(
            {
                "id": meta["task_id"],
                "order": meta["order"],
                "difficulty": meta["difficulty"],
                "prompt": geometry,
            }
        )
    tasks.sort(key=lambda t: t["order"])
    assert len(tasks) == 17 and [t["order"] for t in tasks] == list(range(1, 18))
    from crate_studio import workspace_agent as wa

    dump(DEST / "tasks.json", tasks)
    dump(
        DEST / "protocol.json",
        {
            "frozen_utc": datetime.now(timezone.utc).isoformat(),
            "name": "Forma full public CAD-bench development evaluation v1",
            "upstream_commit": subprocess.check_output(
                ["git", "-C", str(VENDOR), "rev-parse", "HEAD"], text=True
            ).strip(),
            "upstream_url": "https://github.com/CAD-bench/cad-bench",
            "task_count": 17,
            "task_selection": "Every public task in manifest order. No exclusions. Missing/failed/clarify/timeout scores zero.",
            "model": wa.MODEL,
            "arms": ["forma", "build123d"],
            "max_calls_per_task": 2,
            "max_tokens_per_response": 8192,
            "temperature": 0.15,
            "reasoning_effort": "medium",
            "request_timeout_s": 120,
            "retries": "One repair only for schema/native CAD build errors. Never grader feedback. No best-of selection. First valid candidate or last failed attempt retained.",
            "cache": "Disabled for all generations; no prior model responses reused.",
            "forma_system": wa.SYSTEM,
            "baseline_system": BASELINE_SYSTEM,
            "geometry_instructions": "Identical original geometry text. Only the submission footer is replaced by the arm-specific JSON or Python contract.",
            "submission_adaptation": "Both arms export genuine BREP STEP; same unmodified TaskModuleSpec.evaluate_step grader, reference gates and Blender simulation. Adapted STEP evaluation, not an official Harbor final.py run.",
            "resources": {
                "grader_cpus": 4,
                "grader_memory_mb": 4096,
                "grader_timeout_s": 7200,
                "network": "none",
                "build123d_timeout_s": 600,
                "build123d_memory_mb": 4096,
                "forma_runtime": "Windows Python 3.12 CadQuery 2.8 / OCP 7.9.3",
                "grader_runtime": "Linux Python 3.11 original upstream Dockerfiles, locally built dependencies",
            },
            "success_threshold": 0.95,
            "dependency_compatibility": "Original agent and verifier Dockerfiles plus research/cadbench_compat.Dockerfile, pinning ocp_gordon=0.1.17 for OCP 7.8 compatibility. No evaluator changes. Base-image dependency failure retained separately.",
            "aggregate": "Unmodified dataset/metric.py, tier means weighted easy=1 medium=2 hard=3 insane=4. All 17 entries, failures zero.",
            "disclosure": "Public tasks inspected while developing generic product features. Development evaluation, no held-out claim or training. Historical other-model results differ in revision/harness/budget and are contextual only.",
            "upstream_hashes": {
                p.relative_to(VENDOR).as_posix(): digest(p)
                for base in ("dataset", "verifier", "images")
                for p in sorted((VENDOR / base).rglob("*"))
                if p.is_file() and "__pycache__" not in p.parts
            },
            "source_hashes": {
                p.relative_to(ROOT).as_posix(): digest(p)
                for base in ("crate_studio",)
                for p in sorted((ROOT / base).rglob("*"))
                if p.is_file() and p.suffix in (".py", ".js", ".html", ".css")
            },
        },
    )
    dump(
        DEST / "manifest.json", {p.name: digest(p) for p in sorted(DEST.glob("*.json"))}
    )
    print(DEST)


if __name__ == "__main__":
    main()
