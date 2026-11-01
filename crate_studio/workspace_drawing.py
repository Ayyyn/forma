"""BREP-derived orthographic review drawings and editable drawing source.

OpenCascade performs hidden-line removal. Curved projected edges are discretized
to 0.02 mm chord deflection for all three exports. Native overall dimensions are
measured from the BREP; user dimensions are always explicitly reference notes.
The source JSON retains model features and sheet-coordinate annotations.
"""

from __future__ import annotations

from copy import deepcopy
import html
import json
import math
from pathlib import Path
import re

import cadquery as cq
import ezdxf
from .workspace_geometry import _bounds as exact_bounds_mm
from OCP.BRepLib import BRepLib
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape

SHEET_WIDTH, SHEET_HEIGHT = 1200, 800
CURVE_DEFLECTION_MM = 0.02
VIEWS = {
    "front": ((0, -1, 0), (1, 0, 0), (0, 2), "Front (X / Z)"),
    "top": ((0, 0, 1), (1, 0, 0), (0, 1), "Top (X / Y)"),
    "right": ((1, 0, 0), (0, 1, 0), (1, 2), "Right (Y / Z)"),
}


def _number(value, field, bound=100000):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or abs(value) > bound
    ):
        raise ValueError(f"{field} must be a finite number within +/-{bound}")
    return float(value)


def validate_annotations(doc):
    items = doc.get("annotations", [])
    if not isinstance(items, list) or len(items) > 500:
        raise ValueError("annotations must be a list of at most 500 entries")
    result, ids = [], set()
    allowed = {"id", "type", "view", "x", "y", "x2", "y2", "text", "value_mm", "color"}
    for raw in items:
        if not isinstance(raw, dict) or set(raw) - allowed:
            raise ValueError("Unsupported drawing annotation fields")
        a = deepcopy(raw)
        if (
            not isinstance(a.get("id"), str)
            or not 1 <= len(a["id"]) <= 100
            or a["id"] in ids
        ):
            raise ValueError("Annotation ids must be unique nonempty strings")
        ids.add(a["id"])
        if a.get("type") not in ("text", "dimension", "line") or a.get(
            "view", "sheet"
        ) not in (*VIEWS, "sheet"):
            raise ValueError("Unsupported annotation type or view")
        a.setdefault("view", "sheet")
        for key in ("x", "y") + (("x2", "y2") if a["type"] != "text" else ()):
            a[key] = _number(a.get(key), key)
        if not isinstance(a.get("text", ""), str) or len(a.get("text", "")) > 500:
            raise ValueError("Annotation text must contain at most 500 characters")
        a.setdefault("text", "")
        a.setdefault("color", "#245b78")
        if not isinstance(a["color"], str) or not re.fullmatch(
            r"#[0-9a-fA-F]{6}", a["color"]
        ):
            raise ValueError("Annotation color must be a six-digit hex color")
        if "value_mm" in a:
            a["value_mm"] = _number(a["value_mm"], "value_mm", 1e9)
            if a["value_mm"] < 0:
                raise ValueError("Reference dimension cannot be negative")
        result.append(a)
    return result


def _shapes(parts):
    if not isinstance(parts, (list, tuple)) or not parts:
        raise ValueError("At least one BREP part is required")
    result = []
    for part in parts:
        shape = part.get("shape") if isinstance(part, dict) else part
        if isinstance(shape, cq.Workplane):
            shape = shape.val()
        if not isinstance(shape, cq.Shape) or not shape.isValid():
            raise ValueError("Drawing requires valid CadQuery BREP shapes")
        result.append(shape)
    return result


def _project(shape, direction, x_direction):
    algorithm = HLRBRep_Algo()
    algorithm.Add(shape.wrapped)
    axes = gp_Ax2(gp_Pnt(), gp_Dir(*direction), gp_Dir(*x_direction))
    algorithm.Projector(HLRAlgo_Projector(axes))
    algorithm.Update()
    algorithm.Hide()
    projected = HLRBRep_HLRToShape(algorithm)
    result = {"visible": [], "hidden": []}
    groups = {
        "visible": ("VCompound", "Rg1LineVCompound", "OutLineVCompound"),
        "hidden": ("HCompound", "OutLineHCompound"),
    }
    for group, methods in groups.items():
        for method in methods:
            raw = getattr(projected, method)()
            if raw.IsNull():
                continue
            BRepLib.BuildCurves3d_s(raw, 1e-6)
            for edge in cq.Shape.cast(raw).Edges():
                curve = edge._geomAdaptor()
                points = GCPnts_QuasiUniformDeflection(
                    curve,
                    CURVE_DEFLECTION_MM,
                    curve.FirstParameter(),
                    curve.LastParameter(),
                )
                if not points.IsDone():
                    raise ValueError("Could not discretize a projected BREP edge")
                polyline = [
                    (points.Value(i).X(), points.Value(i).Y())
                    for i in range(1, points.NbPoints() + 1)
                ]
                if len(polyline) >= 2:
                    result[group].append(polyline)
    return result


def drawing_data(doc, parts):
    """Return measured geometry and view layout; annotation coordinates are pixels."""
    if not isinstance(doc, dict):
        raise ValueError("Drawing document must be an object")
    annotations = validate_annotations(doc)
    shapes = _shapes(parts)
    combined = cq.Compound.makeCompound(shapes)
    minimum, maximum = exact_bounds_mm(combined)
    dimensions = [maximum[i] - minimum[i] for i in range(3)]
    if not all(math.isfinite(x) and x > 1e-8 for x in dimensions):
        raise ValueError("Drawing requires a nondegenerate 3D BREP")
    views = {}
    for index, (key, (direction, x_dir, axes, label)) in enumerate(VIEWS.items()):
        width, height = [dimensions[i] for i in axes]
        scale = min(280 / width, 360 / height)
        x, y = 55 + 390 * index, 150
        views[key] = {
            **_project(combined, direction, x_dir),
            "label": label,
            "origin_px": [x, y],
            "scale_px_per_mm": scale,
            "bounds_mm": [
                minimum[axes[0]],
                minimum[axes[1]],
                maximum[axes[0]],
                maximum[axes[1]],
            ],
            "width_mm": width,
            "height_mm": height,
        }
    return {
        "name": str(doc.get("name", "Untitled drawing"))[:120],
        "views": views,
        "annotations": annotations,
        "bbox_mm": {"min": minimum, "max": maximum, "size": dimensions},
        "projection": "OpenCascade orthographic hidden-line removal from actual BREP",
        "curve_chord_deflection_mm": CURVE_DEFLECTION_MM,
        "annotation_coordinate_system": "1200 x 800 sheet SVG pixels; view is a grouping tag",
        "user_dimension_policy": "All user dimensions are REF annotations; they do not change or measure model geometry",
    }


def _annotation_label(a):
    if a["type"] != "dimension":
        return a["text"]
    value = f'{a["value_mm"]:g} mm' if "value_mm" in a else "Reference annotation"
    return f"{value} REF" + (f' - {a["text"]}' if a["text"] else "")


def _scene(data):
    scene = []

    def text(x, y, value, size=14, color="#243942", **extra):
        scene.append(
            {
                "type": "text",
                "x": x,
                "y": y,
                "text": value,
                "size": size,
                "color": color,
                **extra,
            }
        )

    def line(points, color="#243942", width=1, hidden=False, **extra):
        scene.append(
            {
                "type": "polyline",
                "points": points,
                "color": color,
                "width": width,
                "hidden": hidden,
                **extra,
            }
        )

    text(40, 45, data["name"], 25)
    text(
        40, 76, "Orthographic BREP projections | dimensions in mm | review drawing", 15
    )
    text(
        40,
        101,
        "Dashed: hidden edges. User annotations marked REF are not measured model dimensions.",
        13,
    )
    for key, v in data["views"].items():
        x, y = v["origin_px"]
        scale = v["scale_px_per_mm"]
        xmin, _, _, ymax = v["bounds_mm"]

        def sheet(point):
            return [x + (point[0] - xmin) * scale, y + (ymax - point[1]) * scale]

        text(x, y - 20, v["label"], 18)
        for hidden in (True, False):
            for path in v["hidden" if hidden else "visible"]:
                line(
                    [sheet(p) for p in path],
                    "#94a0a5" if hidden else "#243942",
                    1,
                    hidden,
                    role="projected-edge",
                    view=key,
                )
        width, height = v["width_mm"] * scale, v["height_mm"] * scale
        # Native overall dimensions derive exclusively from actual BREP bounds.
        yy = y + height + 22
        line([[x, yy - 7], [x, yy + 7]])
        line([[x + width, yy - 7], [x + width, yy + 7]])
        line([[x, yy], [x + width, yy]], role="native-dimension", view=key)
        text(x, yy + 23, f'Overall width: {v["width_mm"]:.6g} mm', 13)
        text(x, yy + 43, f'Overall height: {v["height_mm"]:.6g} mm', 13)
        text(x, yy + 64, f"Display scale: {scale:.4g} px/mm", 11, "#697b83")
    line([[40, 665], [1160, 665]], "#bec8cd")
    text(
        40,
        691,
        "Native dimensions: actual axis-aligned BREP envelope. Curves: 0.02 mm chord-deflection polylines.",
        13,
    )
    text(
        40,
        716,
        "Editable notes and reference dimensions are stored in drawing-source.json; they never override geometry.",
        13,
    )
    text(
        40,
        741,
        "No tolerances, GD&T, material strength, joining details or manufacturing qualification are implied.",
        13,
    )
    text(40, 770, "FORMA / GEOMETRY REVIEW", 12)
    for a in data["annotations"]:
        if a["type"] in ("line", "dimension"):
            line(
                [[a["x"], a["y"]], [a["x2"], a["y2"]]],
                a["color"],
                1.5,
                role="reference-annotation",
                annotation_id=a["id"],
            )
        if a["type"] == "dimension":
            text(
                (a["x"] + a["x2"]) / 2,
                (a["y"] + a["y2"]) / 2 - 8,
                _annotation_label(a),
                13,
                a["color"],
                annotation_id=a["id"],
            )
        elif a["text"]:
            text(
                a["x"],
                a["y"] - 5 if a["type"] == "line" else a["y"],
                _annotation_label(a),
                14,
                a["color"],
                annotation_id=a["id"],
            )
    return scene


def _svg(data):
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET_WIDTH}" height="{SHEET_HEIGHT}" viewBox="0 0 1200 800">',
        '<rect width="1200" height="800" fill="white"/>',
        '<g font-family="Arial,sans-serif">',
    ]
    for item in _scene(data):
        annotation = (
            f' data-annotation-id="{html.escape(item["annotation_id"],quote=True)}"'
            if "annotation_id" in item
            else ""
        )
        if item["type"] == "text":
            out.append(
                f'<text x="{item["x"]:g}" y="{item["y"]:g}" font-size="{item["size"]}" fill="{item["color"]}"{annotation}>{html.escape(item["text"])}</text>'
            )
        else:
            points = " ".join(f"{x:.8g},{y:.8g}" for x, y in item["points"])
            dash = ' stroke-dasharray="5 4"' if item["hidden"] else ""
            role = f' data-role="{item["role"]}"' if "role" in item else ""
            out.append(
                f'<polyline points="{points}" fill="none" stroke="{item["color"]}" stroke-width="{item["width"]}"{dash}{role}{annotation}/>'
            )
    return "\n".join(out + ["</g></svg>"])


def drawing_svg(doc, parts):
    return _svg(drawing_data(doc, parts))


def _pdf(data):
    # Shared vector scene, Helvetica selectable text; no SVG raster conversion.
    def escape(text):
        return (
            text.encode("latin1", "replace")
            .decode("latin1")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

    commands = []
    for item in _scene(data):
        color = [int(item["color"][i : i + 2], 16) / 255 for i in (1, 3, 5)]
        rgb = " ".join(f"{c:.5f}" for c in color)
        if item["type"] == "text":
            commands.append(
                f'{rgb} rg BT /F1 {item["size"]} Tf {item["x"]:g} {800-item["y"]:g} Td ({escape(item["text"])}) Tj ET'
            )
        else:
            commands.append(
                f'{rgb} RG {item["width"]} w '
                + ("[5 4] 0 d" if item["hidden"] else "[] 0 d")
            )
            commands.append(
                " ".join(
                    f'{x:.8g} {800-y:.8g} {"m" if i==0 else "l"}'
                    for i, (x, y) in enumerate(item["points"])
                )
                + " S"
            )
    stream = "\n".join(commands).encode("latin1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 1200 800] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )
    return bytes(out)


def _dxf(data, path):
    doc = ezdxf.new("R2010")
    doc.units = 4
    doc.linetypes.new(
        "PROJECT_HIDDEN",
        dxfattribs={"description": "Hidden BREP edges", "pattern": [6, 3, -3]},
    )
    space = doc.modelspace()
    offsets = {}
    x_offset = 0
    size = max(data["bbox_mm"]["size"])
    gap, text_height = max(20, size * 0.15), max(2, size * 0.025)
    for key, v in data["views"].items():
        xmin, ymin, _, _ = v["bounds_mm"]
        offsets[key] = x_offset
        for group in ("hidden", "visible"):
            layer = f"{key.upper()}_{group.upper()}"
            doc.layers.new(
                layer,
                dxfattribs={
                    "linetype": "PROJECT_HIDDEN" if group == "hidden" else "CONTINUOUS",
                    "color": 8 if group == "hidden" else 7,
                },
            )
            for polyline in v[group]:
                space.add_lwpolyline(
                    [(x - xmin + x_offset, y - ymin) for x, y in polyline],
                    dxfattribs={"layer": layer},
                )
        space.add_text(
            v["label"],
            dxfattribs={
                "height": text_height,
                "insert": (x_offset, v["height_mm"] + gap / 2),
            },
        )
        space.add_linear_dim(
            base=(x_offset, -gap / 3),
            p1=(x_offset, 0),
            p2=(x_offset + v["width_mm"], 0),
            override={
                "dimtxt": text_height * 0.7,
                "dimasz": text_height * 0.5,
                "dimdec": 3,
            },
        ).render()
        space.add_linear_dim(
            base=(x_offset + v["width_mm"] + gap / 3, 0),
            p1=(x_offset + v["width_mm"], 0),
            p2=(x_offset + v["width_mm"], v["height_mm"]),
            angle=90,
            override={
                "dimtxt": text_height * 0.7,
                "dimasz": text_height * 0.5,
                "dimdec": 3,
            },
        ).render()
        x_offset += v["width_mm"] + gap * 2
    doc.layers.new("USER_REFERENCE", dxfattribs={"color": 5})
    for a in data["annotations"]:
        v = data["views"].get(a["view"])

        def mapped(x, y):
            if v:
                sx, sy = v["origin_px"]
                scale = v["scale_px_per_mm"]
                return (
                    (x - sx) / scale + offsets[a["view"]],
                    v["height_mm"] - (y - sy) / scale,
                )
            # Sheet annotations in a separate paper-style band, 1 px = 1 mm.
            return (x, -gap * 3 - y)

        attrs = {"layer": "USER_REFERENCE"}
        if a["type"] != "text":
            space.add_line(
                mapped(a["x"], a["y"]), mapped(a["x2"], a["y2"]), dxfattribs=attrs
            )
        label = _annotation_label(a)
        if label:
            space.add_text(
                label,
                dxfattribs={
                    **attrs,
                    "height": text_height * 0.8,
                    "insert": mapped(a["x"], a["y"]),
                },
            )
    space.add_text(
        "Model projections 1:1 mm; user dimensions REF; curves approximated within 0.02 mm chord deflection.",
        dxfattribs={"height": text_height * 0.65, "insert": (0, -gap * 1.5)},
    )
    doc.saveas(path)


def export_drawings(doc, parts, folder):
    """Export shared measured projections plus the full editable document source."""
    data = drawing_data(doc, parts)
    source = json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "drawing.svg").write_text(_svg(data), encoding="utf-8")
    (folder / "drawing.pdf").write_bytes(_pdf(data))
    _dxf(data, folder / "drawing.dxf")
    (folder / "drawing-source.json").write_text(source, encoding="utf-8")
    metadata = {key: value for key, value in data.items() if key != "views"}
    metadata["views"] = {
        key: {k: v for k, v in view.items() if k not in ("visible", "hidden")}
        for key, view in data["views"].items()
    }
    metadata["pdf_text_encoding"] = (
        "Helvetica Latin-1; unsupported glyphs replaced with ?. Full Unicode preserved in SVG and source JSON."
    )
    (folder / "drawing-measurements.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "files": [
            "drawing.svg",
            "drawing.pdf",
            "drawing.dxf",
            "drawing-source.json",
            "drawing-measurements.json",
        ],
        "measurements": metadata,
    }
