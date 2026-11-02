"""Offline development export audit. Never loads benchmark prompts or calls AI."""

import argparse
import hashlib
import json
from pathlib import Path
import time

import cadquery as cq
import ezdxf
import trimesh

from crate_studio.workspace_drawing import export_drawings
from crate_studio.workspace_geometry import build_document, export_document, _bounds


def audit(document_path, destination):
    raw = json.loads(Path(document_path).read_text(encoding="utf-8"))
    doc = raw.get("document", raw)
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Use a new destination; original evidence is preserved")
    destination.mkdir(parents=True)
    results = []
    for number in range(2):
        folder = destination / f"repeat-{number + 1}"
        start = time.perf_counter()
        built = build_document(doc)
        exported = export_document(doc, None, folder)
        if not exported["checks"]["passed"]:
            raise ValueError(exported["checks"])
        drawing = export_drawings(doc, built["parts"], folder)
        dxf = ezdxf.readfile(folder / "drawing.dxf")
        mesh = trimesh.load(folder / "workspace.stl", force="mesh")
        step = cq.importers.importStep(str(folder / "workspace.step")).val()
        results.append(
            {
                "seconds": time.perf_counter() - start,
                "checks": exported["checks"],
                "brep_bounds_mm": built["metrics"]["bounds_mm"],
                "step_bounds_mm": _bounds(step),
                "stl_bounds_mm": mesh.bounds.tolist(),
                "drawing": drawing["measurements"],
                "dxf_units": dxf.units,
                "dxf_errors": dxf.audit().has_errors,
                "source_preserved": json.loads(
                    (folder / "drawing-source.json").read_text(encoding="utf-8")
                )
                == doc,
                "hashes": {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(folder.iterdir())
                },
            }
        )
        time.sleep(1.1)  # Expose timestamp-only nondeterminism between exports.
    same = {
        name: digest == results[1]["hashes"].get(name)
        for name, digest in results[0]["hashes"].items()
    }
    report = {
        "scope": "Offline development audit; two fresh builds, no AI calls",
        "input": str(document_path),
        "repeats": results,
        "byte_identical": same,
        "geometry_checks_passed": all(
            r["checks"]["passed"] and r["source_preserved"] and not r["dxf_errors"]
            for r in results
        ),
    }
    (destination / "audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return {
        "report": str(destination / "audit.json"),
        "geometry_checks_passed": report["geometry_checks_passed"],
        "byte_identical": same,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document")
    parser.add_argument("destination")
    args = parser.parse_args()
    print(json.dumps(audit(args.document, args.destination), indent=2))
