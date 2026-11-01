"""Reproducible local backend timing; excludes startup, browser and model calls."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import statistics
import threading
import time
from datetime import datetime, timezone

from crate_studio.workspace_server import DEFAULT_DOCUMENT, built, projected, snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lock = threading.RLock()
    rows = []
    for name, cached in (("uncached_snapshot", False), ("cached_snapshot", True)):
        samples = []
        for _ in range(5):
            if not cached:
                projected.cache_clear()
                built.cache_clear()
            start = time.perf_counter()
            result = snapshot(deepcopy(DEFAULT_DOCUMENT), lock)
            if not result["passed"]:
                raise AssertionError("Timing fixture failed geometry validation")
            samples.append(round((time.perf_counter() - start) * 1000, 3))
        rows.append(
            {
                "case": name,
                "samples_ms": samples,
                "median_ms": statistics.median(samples),
                "max_ms": max(samples),
            }
        )
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Single-process default plate backend snapshot. Excludes Python startup, HTTP, browser rendering and AI. Five samples; no competitor speed claim.",
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
