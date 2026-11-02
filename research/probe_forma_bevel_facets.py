"""Explicit conical planar-facet bevel prototype; not production/model output.

Uses cq_gears' spherical involute curves and a stated chord approximation.
No reference meshes, scoring profiles or task-specific geometry dispatch.
"""

import argparse
import math
from pathlib import Path
import shutil

import cadquery as cq
import numpy as np
from cq_gears import BevelGear

from crate_studio.mechanical_features import _simplify_polyline, bore, place
from research.run_forma_full17 import ROOT, container, dump, load


def faceted_bevel(p, tolerance=0.025):
    profile = BevelGear(
        p["module"],
        p["teeth"],
        p["cone_angle"],
        p["face_width"],
        pressure_angle=p.get("pressure_angle", 20),
        backlash=p.get("backlash", 0),
    )
    height = profile.gs_r * math.cos(profile.gamma_f)
    ratio = (profile.gs_r - profile.face_width) / profile.gs_r
    points = []
    for tooth in range(profile.z):
        angle = -math.tau * tooth / profile.z
        c, s = math.cos(angle), math.sin(angle)
        rotation = np.array([[c, -s], [s, c]])
        for curve in (
            profile.t_lflank_pts,
            profile.t_tip_pts,
            profile.t_rflank_pts,
            profile.t_root_pts,
        ):
            xy = curve[:, :2] * (height / curve[:, 2])[:, None]
            for point in _simplify_polyline(xy, tolerance) @ rotation.T:
                if not points or math.dist(points[-1], point) > 1e-8:
                    points.append(tuple(float(v) for v in point))
    if math.dist(points[0], points[-1]) < 1e-8:
        points.pop()
    # Spherical-profile coordinates point toward +Z. Reflect Y and Z together
    # (a proper half turn), matching the source library's aligned local gear.
    large = cq.Wire.makePolygon(
        [cq.Vector(x, -y, -height) for x, y in points], close=True
    )
    small = cq.Wire.makePolygon(
        [cq.Vector(x * ratio, -y * ratio, -height * ratio) for x, y in points],
        close=True,
    )
    shape = cq.Solid.makeLoft([large, small], ruled=True)
    if shape.Volume() < 0:
        shape = shape.reverse()
    alignment = -profile.mp_theta / 2 - math.pi / 2 + math.pi / profile.z
    shape = shape.rotate(
        (0, 0, 0), (0, 0, 1), math.degrees(alignment) + p.get("phase", 0)
    )
    bb = shape.BoundingBox()
    return place(bore(shape, p, bb.zmin - 1, bb.zlen + 2), p)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--task", required=True)
    a = parser.parse_args()
    out = a.output.resolve()
    out.relative_to(ROOT / "output")
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out / "prototype-source.py")
    shutil.copy2(a.document, out / "document.json")
    d = load(a.document)
    shapes = []
    for f in d["features"]:
        if f["type"] != "bevel_gear":
            raise ValueError("Expected independent bevel gears")
        s = faceted_bevel(f["params"])
        if not s.isValid() or len(s.Solids()) != 1:
            raise ValueError("Invalid prototype")
        shapes.append(s)
        print("BUILT", f["id"], flush=True)
    overlaps = [
        abs(shapes[i].intersect(shapes[j]).Volume())
        for i in range(len(shapes))
        for j in range(i + 1, len(shapes))
    ]
    dump(
        out / "checks.json",
        {
            "mode": "Manual public diagnostic prototype; not fresh inference or production promotion",
            "rest_intersection_mm3": overlaps,
            "chord_tolerance_mm": 0.025,
            "new_model_calls": 0,
        },
    )
    print("INTERSECTIONS", overlaps, flush=True)
    cq.exporters.export(cq.Compound.makeCompound(shapes), str(out / "candidate.step"))
    reread = cq.importers.importStep(str(out / "candidate.step")).solids().vals()
    if (
        not all(s.isValid() for s in reread)
        or len(reread) != len(shapes)
        or max(overlaps) > 1e-5
    ):
        raise ValueError(
            "Native geometry or disjointness check failed; no physics score claimed"
        )
    result = container("score", out, out / "verifier", a.task)
    dump(
        out / "result.json",
        {
            "id": a.task,
            "score": result.get("metrics", {}).get("overall_score", 0),
            "grading": result,
        },
    )
    print(result.get("metrics", {}), flush=True)


if __name__ == "__main__":
    main()
