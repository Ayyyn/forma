"""Reopen a real Studio export bundle and cross-check every representation offline."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile
from xml.etree import ElementTree as ET

import cadquery as cq
import ezdxf
import trimesh

from crate_studio.workspace_geometry import build_document, _bounds


def audit(revision, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with urllib.request.urlopen(
        f"http://127.0.0.1:8770/api/studio/documents/{revision}", timeout=60
    ) as response:
        snapshot = json.load(response)
    with urllib.request.urlopen(
        f"http://127.0.0.1:8770/api/studio/documents/{revision}/export/bundle",
        timeout=180,
    ) as response:
        content = response.read()
    (destination / "studio-bundle.zip").write_bytes(content)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if any(Path(n).name != n for n in archive.namelist()):
            raise ValueError("Unexpected path in bundle")
        archive.extractall(destination)
    load = lambda name: json.loads((destination / name).read_text(encoding="utf-8"))
    doc = snapshot["document"]
    built = build_document(doc)
    source = cq.Compound.makeCompound([p["shape"] for p in built["parts"]])
    step = cq.importers.importStep(str(destination / "workspace.step")).val()
    mesh = trimesh.load(destination / "workspace.stl", force="mesh")
    drawing = load("drawing-measurements.json")
    dxf = ezdxf.readfile(destination / "drawing.dxf")
    hashes = {
        name: hashlib.sha256((destination / name).read_bytes()).hexdigest() == expected
        for name, expected in load("sha256.json").items()
    }
    rows = list(
        csv.DictReader(
            (destination / "body-list.csv").open(encoding="utf-8", newline="")
        )
    )
    assertions = {
        "bundle_hashes": all(hashes.values()),
        "native_build": built["checks"]["passed"],
        "source_json_exact": load("drawing-source.json")
        == doc
        == load("workspace.json"),
        "portable_features_exact": load("project.json")["document"]["features"]
        == doc["features"],
        "step_valid": step.isValid(),
        "step_bounds": max(
            abs(a - b)
            for aa, bb in zip(_bounds(source), _bounds(step))
            for a, b in zip(aa, bb)
        )
        <= 1e-5,
        "step_volume": abs(step.Volume() - source.Volume())
        <= max(1e-6, source.Volume() * 1e-8),
        "stl_watertight": bool(mesh.is_watertight and mesh.is_winding_consistent),
        "drawing_bounds": max(
            abs(a - b)
            for a, b in zip(drawing["bbox_mm"]["size"], built["metrics"]["size_mm"])
        )
        <= 1e-5,
        "drawing_common_scale": len(
            {v["scale_px_per_mm"] for v in drawing["views"].values()}
        )
        == 1,
        "svg_parses": ET.parse(destination / "drawing.svg")
        .getroot()
        .tag.endswith("svg"),
        "pdf_signature": (destination / "drawing.pdf")
        .read_bytes()
        .startswith(b"%PDF-1.4"),
        "dxf_mm_and_valid": dxf.units == 4 and not dxf.audit().has_errors,
        "csv_body_count": len(rows) == len(built["parts"]),
        "csv_volume": abs(
            sum(float(row["volume_mm3"]) for row in rows) - source.Volume()
        )
        < 1e-5,
        "export_checks": load("verification.json")["passed"],
        "workflow_revision": load("workflow-report.json")["revision_id"] == revision,
        "manifest_revision": load("export-manifest.json")["revision_id"] == revision,
    }
    holes = []
    for feature in doc["features"]:
        if feature["type"] == "cut_hole" and not feature.get("suppressed"):
            p = feature["params"]
            lo, hi = _bounds(source)
            holes.append(
                {
                    "id": feature["id"],
                    "radius_mm": p["radius"],
                    "end_condition": p.get("end_condition", "blind"),
                    "sampled_through_brep": all(
                        not source.isInside(
                            (p.get("x", 0), p.get("y", 0), lo[2] + (hi[2] - lo[2]) * f)
                        )
                        for f in (0.001, 0.25, 0.5, 0.75, 0.999)
                    ),
                    "sampled_through_step": all(
                        not step.isInside(
                            (p.get("x", 0), p.get("y", 0), lo[2] + (hi[2] - lo[2]) * f)
                        )
                        for f in (0.001, 0.25, 0.5, 0.75, 0.999)
                    ),
                }
            )
    assertions["through_hole_intent"] = all(
        h["sampled_through_brep"] and h["sampled_through_step"]
        for h in holes
        if h["end_condition"] == "through_all"
    )
    report = {
        "revision": revision,
        "passed": all(assertions.values()),
        "checks": assertions,
        "bounds_mm": built["metrics"]["size_mm"],
        "volume_mm3": source.Volume(),
        "holes": holes,
        "hash_checks": hashes,
    }
    (destination / "audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision")
    parser.add_argument("destination")
    args = parser.parse_args()
    if not audit(args.revision, args.destination)["passed"]:
        raise SystemExit(1)
