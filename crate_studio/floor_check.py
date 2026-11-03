"""Measure horizontal support coverage from actual native solid faces.

This checks projected support within a stated height band, including holes.
It does not establish a flat, liquid-tight, load-bearing or usable mechanism.
"""

import math

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from .workspace_geometry import _bounds


def _numbers(value, count):
    if (
        not isinstance(value, list)
        or len(value) != count
        or any(
            type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 10000
            for x in value
        )
    ):
        raise ValueError("Expected a bounded finite numeric array")
    return [float(x) for x in value]


def footprint_spec(raw):
    if not isinstance(raw, dict) or set(raw) != {"center_xy", "size_mm", "z_range_mm"}:
        raise ValueError("Floor footprint requires center_xy, size_mm and z_range_mm")
    center, size, band = (
        _numbers(raw["center_xy"], 2),
        _numbers(raw["size_mm"], 2),
        _numbers(raw["z_range_mm"], 2),
    )
    if min(size) <= 0 or band[0] >= band[1]:
        raise ValueError(
            "Floor dimensions must be positive and the height band ordered"
        )
    return {"center_xy": center, "size_mm": size, "z_range_mm": band}


def floor_coverage(parts, raw):
    spec = footprint_spec(raw)
    x, y = spec["center_xy"]
    width, depth = spec["size_mm"]
    low, high = spec["z_range_mm"]
    target = box(x - width / 2, y - depth / 2, x + width / 2, y + depth / 2)
    polygons, levels = [], []
    face_count, triangle_count = 0, 0
    curved_boundary = False
    for part in parts:
        for face in part["shape"].Faces():
            face_count += 1
            if face_count > 20000:
                raise ValueError("Floor check exceeds the native face limit")
            if face.geomType() != "PLANE" or face.normalAt().z < 1 - 1e-9:
                continue
            bounds = _bounds(face)
            z = face.Center().z
            if not low - 1e-7 <= z <= high + 1e-7:
                continue
            if (
                bounds[1][0] < target.bounds[0]
                or bounds[0][0] > target.bounds[2]
                or bounds[1][1] < target.bounds[1]
                or bounds[0][1] > target.bounds[3]
            ):
                continue
            # Full rectangular planes are exact; triangulating them adds no
            # information. Holes/concavities must use actual face tessellation.
            area = (bounds[1][0] - bounds[0][0]) * (bounds[1][1] - bounds[0][1])
            if (
                abs(face.Area() - area) < 1e-8
                and len(face.Edges()) == 4
                and all(edge.geomType() == "LINE" for edge in face.Edges())
            ):
                projected = box(bounds[0][0], bounds[0][1], bounds[1][0], bounds[1][1])
            else:
                curved_boundary |= any(
                    edge.geomType() != "LINE" for edge in face.Edges()
                )
                vertices, triangles = face.tessellate(0.01, 0.05)
                triangle_count += len(triangles)
                if triangle_count > 100000:
                    raise ValueError("Floor check exceeds the triangulation limit")
                points = [(v.x, v.y) for v in vertices]
                projected = unary_union(
                    [Polygon([points[i] for i in triangle]) for triangle in triangles]
                )
            clipped = projected.intersection(target)
            if clipped.area > 1e-10:
                polygons.append(clipped)
                levels.append(float(z))
    supported = unary_union(polygons) if polygons else Polygon()
    missing = target.difference(supported)
    islands = list(missing.geoms) if hasattr(missing, "geoms") else [missing]
    gaps = [
        {"area_mm2": float(p.area), "bounds_xy_mm": list(p.bounds)}
        for p in sorted(islands, key=lambda p: p.area, reverse=True)
        if p.area > 1e-10
    ]
    tolerance = max(1e-6, target.area * 1e-9)
    report = {
        "footprint": spec,
        "target_area_mm2": float(target.area),
        "supported_area_mm2": float(supported.area),
        "missing_area_mm2": float(missing.area),
        "coverage_fraction": float(supported.area / target.area),
        "passed": bool(polygons) and missing.area <= tolerance,
        "area_tolerance_mm2": tolerance,
        "missing_regions": gaps[:8],
        "support_levels_mm": sorted(set(round(z, 8) for z in levels)),
        "support_height_span_mm": max(levels) - min(levels) if levels else None,
        "curved_boundary_approximation": curved_boundary,
        "chord_deflection_mm": 0.01,
        "strength_verified": False,
        "flatness_verified": False,
        "scope": "Union of upward horizontal native faces within the requested Z band, projected onto the requested XY rectangle. Rectangular faces are exact; other face outlines use native 0.01 mm chord-deflection tessellation, including holes. Area tolerance is numeric, not an error bound on curved outlines. Coverage does not prove flatness, liquid tightness, vertical step usability, floor/wall attachment, strength or physical support under load.",
    }
    return report, target, supported, missing


def render_coverage(target, supported, missing, path, title):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path

    fig, ax = plt.subplots(figsize=(6, 5), facecolor="#f7f5f0")
    ax.set_facecolor("#f7f5f0")
    for geometry, color in ((supported, "#a0b9a7"), (missing, "#ce806e")):
        regions = list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]
        for region in regions:
            if region.is_empty or not hasattr(region, "exterior"):
                continue
            # Ring orientation retains holes in the coverage drawing.
            from shapely.geometry.polygon import orient

            region = orient(region)
            rings = [region.exterior, *region.interiors]
            points, codes = [], []
            for ring in rings:
                coords = list(ring.coords)
                points += coords
                codes += (
                    [Path.MOVETO] + [Path.LINETO] * (len(coords) - 2) + [Path.CLOSEPOLY]
                )
            ax.add_patch(
                PathPatch(
                    Path(points, codes),
                    facecolor=color,
                    edgecolor="#52635e",
                    linewidth=0.5,
                )
            )
    xs, ys = target.exterior.xy
    ax.plot(xs, ys, color="#263942", linewidth=1)
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_xlabel("X / mm")
    ax.set_ylabel("Y / mm")
    ax.set_title(title, fontsize=11)
    fig.subplots_adjust(bottom=0.19)
    fig.text(
        0.5,
        0.02,
        "Green: projected support | red: missing support | height band is declared",
        ha="center",
        fontsize=8,
    )
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
