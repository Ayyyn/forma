"""Native plane intersections with material-aware section hatching, in mm."""

import math

import cadquery as cq
import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.BRepLib import BRepLib
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.gp import gp_Pln, gp_Pnt, gp_Dir
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union

from .workspace_geometry import _bounds
from .drawing_layout import aligned_scene


def specifications(raw):
    if not isinstance(raw, list) or len(raw) > 6:
        raise ValueError("Use at most six section planes")
    result = []
    names = set()
    for row in raw:
        if (
            not isinstance(row, dict)
            or set(row) - {"name", "axis", "offset_mm", "part_ids"}
            or not {"name", "axis", "offset_mm"} <= set(row)
        ):
            raise ValueError(
                "Section requires name, axis X/Y/Z and offset_mm; optional part_ids"
            )
        name = row["name"]
        offset = row["offset_mm"]
        if not isinstance(name, str) or not 1 <= len(name) <= 50 or name in names:
            raise ValueError("Section names must be unique and contain 1–50 characters")
        if (
            row["axis"] not in ("X", "Y", "Z")
            or type(offset) not in (int, float)
            or not math.isfinite(offset)
            or abs(offset) > 10000
        ):
            raise ValueError("Invalid section axis or plane position")
        ids = row.get("part_ids")
        if ids is not None and (
            not isinstance(ids, list)
            or not ids
            or len(ids) > 50
            or any(not isinstance(k, str) or len(k) > 100 for k in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Section part_ids must identify unique native bodies")
        names.add(name)
        result.append(
            {
                "name": name,
                "axis": row["axis"],
                "offset_mm": float(offset),
                "part_ids": ids,
            }
        )
    return result


def section_data(parts, raw):
    spec = specifications([raw])[0]
    ids = {p["id"] for p in parts}
    if spec["part_ids"] and not set(spec["part_ids"]) <= ids:
        raise ValueError("Section references a missing body; select its bodies again")
    axis = "XYZ".index(spec["axis"])
    axes = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]
    origin = [0.0, 0.0, 0.0]
    origin[axis] = spec["offset_mm"]
    normal = [0, 0, 0]
    normal[axis] = 1
    plane = gp_Pln(gp_Pnt(*origin), gp_Dir(*normal))
    contours = []
    regions = []
    native_bounds = []
    for part in parts:
        if spec["part_ids"] and part["id"] not in spec["part_ids"]:
            continue
        cut = BRepAlgoAPI_Section(part["shape"].wrapped, plane, False)
        cut.Build()
        if not cut.IsDone():
            raise ValueError("Native section intersection failed")
        raw_shape = cut.Shape()
        if raw_shape.IsNull():
            continue
        BRepLib.BuildCurves3d_s(raw_shape, 1e-6)
        shape = cq.Shape.cast(raw_shape)
        edges = shape.Edges()
        if not edges:
            continue
        bounds = _bounds(shape)
        native_bounds.append(
            [[bounds[0][i] for i in axes], [bounds[1][i] for i in axes]]
        )
        paths = []
        for edge in edges:
            curve = edge._geomAdaptor()
            points = GCPnts_QuasiUniformDeflection(
                curve, 0.02, curve.FirstParameter(), curve.LastParameter()
            )
            if not points.IsDone():
                raise ValueError("Section curve discretization failed")
            path = []
            for i in range(1, points.NbPoints() + 1):
                xyz = points.Value(i).Coord()
                path.append([float(xyz[j]) for j in axes])
            if len(path) >= 2:
                paths.append(path)
                contours.append({"part_id": part["id"], "points": path})
        network = unary_union(
            [
                LineString([(round(p[0], 7), round(p[1], 7)) for p in path])
                for path in paths
            ]
        )
        for polygon in polygonize(network):
            point = polygon.representative_point()
            xyz = list(origin)
            xyz[axes[0]] = point.x
            xyz[axes[1]] = point.y
            if polygon.area > 1e-8 and part["shape"].isInside(cq.Vector(*xyz), 1e-6):
                regions.append({"part_id": part["id"], "polygon": polygon})
    if not native_bounds or not regions:
        raise ValueError(
            "No closed material section at this plane; move the section inside a solid"
        )
    lower = np.min([b[0] for b in native_bounds], axis=0)
    upper = np.max([b[1] for b in native_bounds], axis=0)
    size = upper - lower
    if np.min(size) <= 1e-8:
        raise ValueError("Section is degenerate at this plane")
    return {
        "spec": spec,
        "axes": list(axes),
        "bounds_mm": [lower.tolist(), upper.tolist()],
        "size_mm": size.tolist(),
        "contours": contours,
        "regions": regions,
        "scope": "Exact native plane intersection, with curves drawn at0.02mm chord deflection. Hatching is clipped to polygonized cut material and excludes voids; no tolerance, stress or manufacturing qualification.",
    }


def section_scene(data, base):
    lower, upper = data["bounds_mm"]
    width, height = data["size_mm"]
    fit = min(1000 / width, 425 / height) / (1200 / 420)
    exponent = math.floor(math.log10(fit))
    ratio = max(
        m * 10**exponent for m in (0.1, 0.2, 0.5, 1, 2, 5) if m * 10**exponent <= fit
    )
    scale = ratio * 1200 / 420
    label = f"{ratio:g}:1" if ratio >= 1 else f"1:{1 / ratio:g}"
    frame = {
        **base,
        "views": {},
        "isometric": None,
        "body_rows": [],
        "annotations": [],
        "sheet": {**base["sheet"], "scale_label": label},
        "name": base["name"] + " / " + data["spec"]["name"],
    }
    scene = aligned_scene(frame)

    def text(x, y, value, size=11, rotation=0):
        scene.append(
            dict(
                type="text",
                x=x,
                y=y,
                text=value,
                size=size,
                rotation=rotation,
                color="#243942",
            )
        )

    def line(points, width=0.7, color="#243942", role="section-detail"):
        scene.append(
            dict(
                type="polyline",
                points=points,
                width=width,
                color=color,
                hidden=False,
                role=role,
            )
        )

    def sheet(point):
        return [70 + (point[0] - lower[0]) * scale, 155 + (upper[1] - point[1]) * scale]

    spec = data["spec"]
    name = (
        spec["name"]
        if spec["name"].startswith(data.get("tag", spec["name"]))
        else data.get("tag", "") + " / " + spec["name"]
    )
    text(
        70,
        121,
        f"SECTION {name} / {spec['axis']} = {spec['offset_mm']:g} mm / cut material hatched",
        12,
    )
    # Each part alternates hatch direction; native material regions exclude bores.
    part_ids = list(dict.fromkeys(row["part_id"] for row in data["regions"]))
    spacing = 4 / scale
    for row in data["regions"]:
        polygon = row["polygon"]
        lo_x, lo_y, hi_x, hi_y = polygon.bounds
        sign = 1 if part_ids.index(row["part_id"]) % 2 == 0 else -1
        span = max(width, height) * 2 + 1
        c_min = min(lo_y - sign * lo_x, lo_y - sign * hi_x) - spacing
        c_max = max(hi_y - sign * lo_x, hi_y - sign * hi_x) + spacing
        for c in np.arange(math.floor(c_min / spacing) * spacing, c_max, spacing):
            hatch = polygon.intersection(
                LineString(
                    [
                        (lo_x - span, sign * (lo_x - span) + c),
                        (hi_x + span, sign * (hi_x + span) + c),
                    ]
                )
            )
            for segment in getattr(hatch, "geoms", [hatch]):
                if segment.geom_type == "LineString" and not segment.is_empty:
                    line(
                        [sheet(p) for p in segment.coords],
                        0.35,
                        "#8b999e",
                        "section-hatch",
                    )
    for row in data["contours"]:
        line([sheet(p) for p in row["points"]], 1, role="section-contour")
    yy = 155 + height * scale + 28
    xx = 70 + width * scale + 28
    line([[70, yy], [70 + width * scale, yy]], role="section-dimension")
    line([[xx, 155], [xx, 155 + height * scale]], role="section-dimension")
    for x in (70, 70 + width * scale):
        line([[x, 155 + height * scale + 3], [x, yy + 5]], 0.5)
        direction = 1 if x == 70 else -1
        line([[x + direction * 7, yy - 2], [x, yy], [x + direction * 7, yy + 2]], 0.8)
    for y in (155, 155 + height * scale):
        line([[70 + width * scale + 3, y], [xx + 5, y]], 0.5)
        direction = 1 if y == 155 else -1
        line([[xx - 2, y + direction * 7], [xx, y], [xx + 2, y + direction * 7]], 0.8)
    text(70 + width * scale / 2 - 22, yy - 5, f"{width:.6g}", 11)
    text(xx - 5, 155 + height * scale / 2 + 18, f"{height:.6g}", 11, rotation=-90)
    return scene, {
        "tag": data.get("tag"),
        "scale_label": label,
        "model_scale": ratio,
        "size_mm": data["size_mm"],
        "bounds_mm": data["bounds_mm"],
        "plane": spec,
        "material_region_count": len(data["regions"]),
    }
