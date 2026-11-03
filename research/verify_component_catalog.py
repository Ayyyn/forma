"""Native component-source acceptance audit. No model calls.

The optional electronics pass downloads only pinned public KiCad STEP assets.
"""

import argparse
import hashlib
import json
from pathlib import Path
import time

from crate_studio import component_library as lib
from crate_studio.workspace_geometry import build_document, _bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--electronics", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    assets = args.output / "assets"
    assets.mkdir(exist_ok=True)

    def store(data):
        key = hashlib.sha256(data).hexdigest()
        (assets / (key + ".step")).write_bytes(data)
        return key

    rows = []
    for row in lib.catalog():
        if row["category"] == "Electronics" and not args.electronics:
            continue
        variants = [
            {"size": size}
            for size in row["parameters"].get("size", {}).get("choices", [])
        ] or [{}]
        for parameters in variants:
            start = time.perf_counter()
            result = {"id": row["id"], "parameters": parameters}
            try:
                record = lib.materialize(
                    row["id"], parameters, args.output / "cache", store
                )
                doc, _ = lib.insert(
                    {"name": "Component acceptance", "features": []},
                    record,
                    (15, 20, 25),
                    (90, 0, 30),
                )
                built = build_document(doc, lambda key: assets / (key + ".step"))
                result.update(
                    passed=built["checks"]["passed"],
                    provenance=record,
                    bodies=[
                        {
                            "bounds_mm": _bounds(p["shape"]),
                            "volume_mm3": p["shape"].Volume(),
                            "valid": p["shape"].isValid(),
                        }
                        for p in built["parts"]
                    ],
                )
            except Exception as error:
                result.update(passed=False, error=str(error))
            result["elapsed_s"] = time.perf_counter() - start
            rows.append(result)
            print(
                row["id"],
                parameters,
                result["passed"],
                result.get("error", ""),
                flush=True,
            )
    report = {
        "actor": "native_tools",
        "model_calls": 0,
        "passed": all(row["passed"] for row in rows),
        "scope": "Pinned source, valid solids, STEP readback and placement. Not electrical, print-fit, friction or strength qualification.",
        "cases": rows,
    }
    (args.output / "audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
