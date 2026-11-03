"""Read-only paired HTTP timing of old/new Studio request patterns, no inference."""

import argparse
import json
from pathlib import Path
import statistics
import time
from urllib.parse import quote
from urllib.request import urlopen


def run(document_id, output):
    target = quote(document_id, safe="")
    patterns = {
        "startup_old": ["/bootstrap", "/documents/" + target],
        "startup_new": ["/bootstrap?document_id=" + target],
        "history_old": ["/bootstrap"],
        "history_new": ["/documents"],
    }
    rows = []
    for iteration in range(6):
        names = list(patterns) if iteration % 2 == 0 else list(reversed(patterns))
        for name in names:
            start, size, doc_id = time.perf_counter(), 0, None
            for path in patterns[name]:
                with urlopen(
                    "http://127.0.0.1:8770/api/studio" + path, timeout=60
                ) as response:
                    raw = response.read()
                value = json.loads(raw)
                size += len(raw)
                if isinstance(value, dict):
                    doc_id = value.get("id") or (value.get("document") or {}).get("id")
            rows.append(
                {
                    "iteration": iteration,
                    "warmup": iteration == 0,
                    "pattern": name,
                    "elapsed_s": time.perf_counter() - start,
                    "bytes": size,
                    "requests": len(patterns[name]),
                    "document_id": doc_id,
                }
            )
    report = {
        "scope": "Same localhost process and retained document; alternating old/new request patterns after one warmup. Includes HTTP/JSON transfer, excludes browser/GPU and inference. Native geometry/drawings still verified; no project edits.",
        "fresh_model_call": False,
        "rows": rows,
        "summary": {
            name: {
                "median_s": statistics.median(
                    r["elapsed_s"]
                    for r in rows
                    if r["pattern"] == name and not r["warmup"]
                ),
                "bytes": next(r["bytes"] for r in rows if r["pattern"] == name),
                "requests": len(paths),
            }
            for name, paths in patterns.items()
        },
        "requested_document_preserved": all(
            r["document_id"] == document_id
            for r in rows
            if r["pattern"].startswith("startup")
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.document_id, args.output)
