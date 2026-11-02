"""Explicit helical-contact research probe; not a production feature or model run."""

import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import shutil

import cadquery as cq
from cq_gears import SpurGear

from crate_studio.mechanical_features import bore, place
from research.run_forma_full17 import ROOT, container, dump, load, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--helix-angle", type=float, default=25)
    args = parser.parse_args()
    if not 0 < abs(args.helix_angle) <= 35:
        raise ValueError("Bounded helix angle required")
    out = args.output.resolve()
    out.relative_to(ROOT / "output")
    out.mkdir(parents=True, exist_ok=False)
    document = load(args.document)
    shutil.copy2(args.document, out / "source-document.json")
    shutil.copy2(__file__, out / "prototype-source.py")
    shapes = []
    parameters = []
    for i, feature in enumerate(document["features"]):
        if feature["type"] != "spur_gear":
            raise ValueError("Only independent spur train prototypes are supported")
        p = feature["params"]
        beta = args.helix_angle * (-1) ** i
        backlash = p.get("backlash", 0.05) + 0.08 / (
            p["module"] * math.tan(math.radians(p.get("pressure_angle", 20)))
        )
        profile = SpurGear(
            p["module"],
            p["teeth"],
            p["thickness"],
            pressure_angle=p.get("pressure_angle", 20),
            helix_angle=beta,
            backlash=backlash,
            addendum_coeff=p.get("addendum_coeff", 1),
            dedendum_coeff=p.get("dedendum_coeff", 1.25),
        )
        shape = profile.build().rotate((0, 0, 0), (0, 0, 1), p.get("phase", 0))
        bb = shape.BoundingBox()
        shape = place(bore(shape, p, bb.zmin - 1, bb.zlen + 2), p)
        if not shape.isValid() or len(shape.Solids()) != 1:
            raise ValueError("Invalid prototype solid")
        shapes.append(shape)
        parameters.append({**p, "helix_angle": beta, "tangential_backlash_mm": 0.08})
        print("BUILT", feature["id"], flush=True)
    checks = {"brep_valid": True, "rest_intersection_mm3": []}
    for i in range(len(shapes) - 1):
        volume = abs(shapes[i].intersect(shapes[i + 1]).Volume())
        checks["rest_intersection_mm3"].append(volume)
        print("PAIR", i, volume, flush=True)
    dump(
        out / "development.json",
        {
            "mode": "Manual public diagnostic helical prototype; no inference or production promotion",
            "utc": datetime.now(timezone.utc).isoformat(),
            "parameters": parameters,
            "checks": checks,
            "original_document_sha256": digest(args.document),
            "new_model_calls": 0,
        },
    )
    cq.exporters.export(cq.Compound.makeCompound(shapes), str(out / "candidate.step"))
    step = cq.importers.importStep(str(out / "candidate.step")).solids().vals()
    checks["step_valid"] = len(step) == len(shapes) and all(s.isValid() for s in step)
    dump(out / "checks.json", checks)
    if not checks["step_valid"] or max(checks["rest_intersection_mm3"]) > 1e-5:
        raise ValueError("Prototype failed native assembly or STEP checks")
    graded = container("score", out, out / "verifier", args.task)
    dump(
        out / "result.json",
        {
            "id": args.task,
            "score": graded.get("metrics", {}).get("overall_score", 0),
            "grading": graded,
        },
    )
    print(graded.get("metrics", {}), flush=True)


if __name__ == "__main__":
    main()
