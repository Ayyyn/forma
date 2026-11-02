"""Freeze a named post-failure public diagnostic run, never a held-out suite."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

from crate_studio import workspace_agent as wa
from research.run_forma_full17 import ROOT, load, dump, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT / "output")
    freeze = output / "protocol"
    freeze.mkdir(parents=True, exist_ok=False)
    original = ROOT / "evaluation/forma-full17-v1"
    protocol = load(original / "protocol.json")
    for name, sha in protocol["upstream_hashes"].items():
        if digest(ROOT / "research/vendor/cad-bench" / name) != sha:
            raise ValueError("Original grader/task source changed: " + name)
    sources = {
        p.relative_to(ROOT).as_posix(): digest(p)
        for p in sorted((ROOT / "crate_studio").rglob("*"))
        if p.is_file() and p.suffix in (".py", ".js", ".html", ".css")
    }
    protocol.update(
        name="Forma public diagnostic development v2",
        frozen_utc=datetime.now(timezone.utc).isoformat(),
        arms=["forma"],
        forma_system=wa.SYSTEM,
        source_hashes=sources,
        retries="At most one schema/native geometry/mechanical preflight repair. No benchmark score feedback during this run.",
        disclosure="Post-failure public diagnostic development. Public instructions, grader and reference implementation inspected during development; not held-out, official rank or a new matched comparison. All 17 tasks retained. No copied reference CAD or benchmark task dispatch in production.",
    )
    dump(freeze / "protocol.json", protocol)
    shutil.copy2(original / "tasks.json", freeze / "tasks.json")
    dump(freeze / "manifest.json", {p.name: digest(p) for p in freeze.glob("*.json")})
    for name in sources:
        destination = output / "source-snapshot" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    for name in (
        "research/run_forma_full17.py",
        "research/freeze_forma_diagnostic.py",
        "research/cadbench_container.py",
    ):
        destination = output / "source-snapshot" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    print(freeze)


if __name__ == "__main__":
    main()
