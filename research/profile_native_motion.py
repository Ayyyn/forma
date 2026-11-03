"""Offline paired timing: identical sampled CAD motion, direct versus exact reuse."""

import argparse
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from crate_studio import mechanism_study as ms
from crate_studio.workspace_cache import cached_build
from crate_studio.motion_cache import native_motion_cache


def run(source, output):
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    doc = data.get("document") or data.get("proposal", {}).get("document")
    if not doc:
        raise ValueError("Provide a retained Studio snapshot or model result")
    spec = ms.validate_spec(
        doc["metadata"]["design_mechanism"],
        [p["id"] for p in cached_build(doc)["parts"]],
    )
    built = cached_build(doc)
    rows, canonical = [], None
    native_motion_cache.clear()
    for mode in (
        "direct_uncached",
        "cache_cold",
        "cache_warm_1",
        "cache_warm_2",
        "cache_warm_3",
    ):
        with patch.object(ms, "collisions", wraps=ms.collisions) as native:
            start = time.perf_counter()
            report = (
                ms._calculate_study(doc, built["parts"], spec)
                if mode == "direct_uncached"
                else ms.mechanism_study(doc, built, spec)
            )
            elapsed = time.perf_counter() - start
            encoded = json.dumps(report, sort_keys=True, allow_nan=False)
            canonical = encoded if canonical is None else canonical
            rows.append(
                {
                    "mode": mode,
                    "elapsed_s": elapsed,
                    "native_pose_checks": native.call_count,
                    "report_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                    "identical_to_direct": encoded == canonical,
                }
            )
    output.parent.mkdir(exist_ok=True, parents=True)
    result = {
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "fresh_model_call": False,
        "scope": "One retained development CAD model, same process/code/native tessellation and exact sampled trajectory. Cache excludes fresh inference, browser/network time and changed studies. Independent direct computation compared to every full report byte after canonical JSON serialization.",
        "rows": rows,
        "cache_info": native_motion_cache.info()._asdict(),
        "all_reports_identical": all(r["identical_to_direct"] for r in rows),
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.source, args.output)
