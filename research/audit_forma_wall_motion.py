"""Cross-check every reported wall pose against independently transformed BREP."""

import argparse
import itertools
import json
from pathlib import Path

import cadquery as cq

from crate_studio.workspace_geometry import build_document, _bounds
from crate_studio.workspace_workflow import motion_study, geometry_signature


def audit(source, destination):
    raw = json.loads(Path(source).read_text(encoding="utf-8"))
    doc = raw.get("document", raw)
    built = build_document(doc)
    study = motion_study(doc)
    if not built["checks"]["passed"] or len(built["parts"]) != len(study["panels"]):
        raise ValueError("Requires a valid supported enclosure")
    poses = []
    for frame in study["frames"]:
        parts = []
        for definition, part in zip(study["panels"], built["parts"]):
            shape = part["shape"].copy()
            if definition["direction"]:
                pivot = definition["pivot_mm"]
                tip = list(pivot)
                tip[0 if definition["axis"] == "x" else 1] += 1
                shape = shape.rotate(
                    tuple(pivot),
                    tuple(tip),
                    frame["angle_deg"] * definition["direction"],
                )
            parts.append((definition["id"], shape))
        lo, hi = _bounds(cq.Compound.makeCompound([s for _, s in parts]))
        error = max(
            abs(a - b)
            for aa, bb in zip(
                (lo, hi), (frame["bounds_min_mm"], frame["bounds_max_mm"])
            )
            for a, b in zip(aa, bb)
        )
        intersections = [
            {"pair": [a[0], b[0]], "volume_mm3": abs(a[1].intersect(b[1]).Volume())}
            for a, b in itertools.combinations(parts, 2)
        ]
        actual = [x["pair"] for x in intersections if x["volume_mm3"] > 1e-5]
        poses.append(
            {
                "angle_deg": frame["angle_deg"],
                "bounds_error_mm": error,
                "reported_overlaps": frame["overlaps"],
                "brep_overlaps": actual,
                "largest_pair_overlap_mm3": max(x["volume_mm3"] for x in intersections),
                "passed": error < 1e-6 and actual == frame["overlaps"],
            }
        )
    report = {
        "revision_id": raw.get("id"),
        "passed": all(p["passed"] for p in poses),
        "geometry_signature": geometry_signature(doc),
        "sample_count": len(poses),
        "closed_extent_mm": study["frames"][0]["extent_mm"],
        "open_extent_mm": study["frames"][-1]["extent_mm"],
        "poses": poses,
        "scope": "All declared sampled poses checked with native BREP; not continuous swept volume, hinge hardware, elastic mechanics or physical validation",
    }
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Preserve original evidence: choose a new report path")
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "poses"}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    audit(args.source, args.destination)
