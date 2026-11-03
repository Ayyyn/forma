"""BREP-derived orthographic review drawings and editable drawing source.

OpenCascade performs hidden-line removal. Curved projected edges are discretized
to 0.02 mm chord deflection for all three exports. Native overall dimensions are
measured from the BREP; user dimensions are always explicitly reference notes.
The source JSON retains model features and sheet-coordinate annotations.
"""

from __future__ import annotations

from copy import deepcopy
import html
import base64
import csv
import io
import json
import math
import hashlib
from pathlib import Path
import re

import cadquery as cq
import ezdxf
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .workspace_geometry import _bounds as exact_bounds_mm
from .motion_cache import ExactMotionCache
from OCP.BRepLib import BRepLib
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape

SHEET_WIDTH, SHEET_HEIGHT = 1200, 800
# Preserve saved annotation coordinates. The logical sheet occupies 420 x 280 mm
# centred on A3 landscape; PDF and SVG use the same physical drawing scale.
SHEET_UNITS_PER_MM = SHEET_WIDTH / 420
PDF_POINTS_PER_UNIT = 72 / 25.4 / SHEET_UNITS_PER_MM
PDF_WIDTH, PDF_HEIGHT = 420 * 72 / 25.4, 297 * 72 / 25.4
CURVE_DEFLECTION_MM = 0.02
FONT_PATH = Path(__file__).with_name("web") / "vendor" / "FormaSans.ttf"
pdfmetrics.registerFont(TTFont("FormaSans", str(FONT_PATH)))
VIEWS = {
    "front": ((0, -1, 0), (1, 0, 0), (0, 2), "Front (X / Z)"),
    "top": ((0, 0, 1), (1, 0, 0), (0, 1), "Top (X / Y)"),
    "right": ((1, 0, 0), (0, 1, 0), (1, 2), "Right (Y / Z)"),
}
_owned_projections = ExactMotionCache(max_entries=12, max_bytes=16 * 1024 * 1024)


def _projection(shape, direction, x_direction, native_key=None):
    if native_key is None:
        return _project(shape, direction, x_direction)
    return _owned_projections.compute(
        (native_key, tuple(direction), tuple(x_direction)),
        lambda: _project(shape, direction, x_direction),
    )


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


def _drawing_context(doc, context):
    result = {
        "revision_id": "UNSAVED / WORKING DRAFT",
        "pose": "Saved CAD pose; motion playback is separate",
        "material": "Not specified",
        "tolerances": "Not specified",
        **(context or {}),
    }
    result["geometry_hash"] = hashlib.sha256(
        json.dumps(doc.get("features", []), sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    if any(not isinstance(value, str) or len(value) > 200 for value in result.values()):
        raise ValueError(
            "Drawing identity and manufacturing notes must be bounded text"
        )
    return result


def section_page(doc, parts, index, context=None):
    """Render only the requested native cut, avoiding unrelated HLR work."""
    from .drawing_sections import specifications, section_data, section_scene

    specs = specifications(doc.get("metadata", {}).get("drawing_sections", []))
    if type(index) is not int or not 0 <= index < len(specs):
        raise ValueError("Unknown section page")
    base = {
        "name": str(doc.get("name", "Untitled drawing"))[:120],
        "drawing_context": _drawing_context(doc, context),
        "sheet": {"scale_label": "NTS"},
        "feature_parameters": [
            {
                "id": f.get("id"),
                "type": f.get("type"),
                "name": f.get("name", f.get("type")),
                "suppressed": f.get("suppressed", False),
                "params": f.get("params", {}),
            }
            for f in doc.get("features", [])
        ],
    }
    base["page_count"] = 1 + len(specs) + len(_parameter_scenes(base))
    base["sheet_number"] = index + 2
    section = section_data(parts, specs[index])
    section["tag"] = chr(65 + index) + "-" + chr(65 + index)
    scene, measurements = section_scene(section, base)
    return {"scene": scene, "measurements": measurements}


def drawing_data(doc, parts, context=None, native_build=None):
    """Return measured geometry and view layout; annotation coordinates are pixels."""
    if not isinstance(doc, dict):
        raise ValueError("Drawing document must be an object")
    annotations = validate_annotations(doc)
    shapes = _shapes(parts)
    native_key = None
    if (
        native_build is not None
        and len(parts) == len(native_build["parts"])
        and all(a is b for a, b in zip(parts, native_build["parts"], strict=True))
    ):
        from .workspace_cache import identity_for_build

        native_key = identity_for_build(native_build)
    combined = cq.Compound.makeCompound(shapes)
    minimum, maximum = exact_bounds_mm(combined)
    dimensions = [maximum[i] - minimum[i] for i in range(3)]
    if not all(math.isfinite(x) and x > 1e-8 for x in dimensions):
        raise ValueError("Drawing requires a nondegenerate 3D BREP")
    views = {}
    layout = doc.get("metadata", {}).get(
        "drawing_layout", "legacy-v1" if annotations else "aligned-v1"
    )
    if layout not in ("legacy-v1", "aligned-v1"):
        raise ValueError("Unknown drawing layout")
    fit = (
        min(
            280 / max(dimensions[0], dimensions[1]),
            360 / max(dimensions[1], dimensions[2]),
        )
        / SHEET_UNITS_PER_MM
    )
    if layout == "aligned-v1":
        fit = (
            min(
                360 / dimensions[0],
                210 / dimensions[1],
                160 / dimensions[2],
                300 / dimensions[1],
            )
            / SHEET_UNITS_PER_MM
        )
    # Engineering scales, shared across views. Never enlarge one view silently.
    exponent = math.floor(math.log10(fit))
    ratio = max(
        m * 10**exponent for m in (0.1, 0.2, 0.5, 1, 2, 5) if m * 10**exponent <= fit
    )
    scale = ratio * SHEET_UNITS_PER_MM
    scale_label = f"{ratio:g}:1" if ratio >= 1 else f"1:{1 / ratio:g}"
    for index, (key, (direction, x_dir, axes, label)) in enumerate(VIEWS.items()):
        width, height = [dimensions[i] for i in axes]
        x, y = 55 + 390 * index, 150
        if layout == "aligned-v1":
            x, y = {"front": (70, 410), "top": (70, 135), "right": (550, 410)}[key]
        views[key] = {
            **_projection(combined, direction, x_dir, native_key),
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
            "axis_names": {"front": ("W", "H"), "top": ("W", "D"), "right": ("D", "H")}[
                key
            ],
        }
    from .component_library import instances

    drawing_context = _drawing_context(doc, context)

    data = {
        "name": str(doc.get("name", "Untitled drawing"))[:120],
        "library_components": instances(doc),
        "body_rows": [
            {
                "id": part.get("id", f"body_{i + 1:03d}")
                if isinstance(part, dict)
                else f"body_{i + 1:03d}",
                "size_mm": [hi - lo for lo, hi in zip(*exact_bounds_mm(shape))],
            }
            for i, (part, shape) in enumerate(zip(parts, shapes, strict=True))
        ],
        "layout": layout,
        "drawing_context": drawing_context,
        "isometric": _projection(combined, (1, -1, 1), (1, 1, 0), native_key)
        if layout == "aligned-v1"
        else None,
        "views": views,
        "annotations": annotations,
        "bbox_mm": {"min": minimum, "max": maximum, "size": dimensions},
        "projection": "OpenCascade orthographic hidden-line removal from actual BREP",
        "curve_chord_deflection_mm": CURVE_DEFLECTION_MM,
        "sheet": {
            "pdf_size_mm": [420, 297],
            "content_size_mm": [420, 280],
            "model_scale": ratio,
            "scale_label": scale_label,
            "logical_units_per_paper_mm": SHEET_UNITS_PER_MM,
            "print_instruction": "A3 landscape, actual size / 100%; disable fit to page",
        },
        "annotation_coordinate_system": "1200 x 800 sheet SVG pixels; view is a grouping tag",
        "user_dimension_policy": "All user dimensions are REF annotations; they do not change or measure model geometry",
        "feature_parameters": [
            {
                "id": f.get("id"),
                "type": f.get("type"),
                "name": f.get("name", f.get("type")),
                "suppressed": f.get("suppressed", False),
                "params": f.get("params", {}),
            }
            for f in doc.get("features", [])
        ],
    }
    from .drawing_sections import specifications, section_data, section_scene

    specs = specifications(doc.get("metadata", {}).get("drawing_sections", []))
    data["section_specs"] = specs
    data["page_count"] = 1 + len(specs) + len(_parameter_scenes(data))
    normalized_parts = [
        {"id": row["id"], "shape": shape}
        for row, shape in zip(data["body_rows"], shapes, strict=True)
    ]
    data["section_pages"] = []
    for index, spec in enumerate(specs):
        section = section_data(normalized_parts, spec)
        section["tag"] = chr(65 + index) + "-" + chr(65 + index)
        scene, measurements = section_scene(
            section, {**data, "sheet_number": index + 2}
        )
        data["section_pages"].append({"scene": scene, "measurements": measurements})
    return data


def _annotation_label(a):
    if a["type"] != "dimension":
        return a["text"]
    value = f"{a['value_mm']:g} mm" if "value_mm" in a else "Reference annotation"
    return f"{value} REF" + (f" - {a['text']}" if a["text"] else "")


def _scene(data):
    if data.get("layout") == "aligned-v1":
        from .drawing_layout import aligned_scene

        return aligned_scene(data)
    return _legacy_scene(data)


def _legacy_scene(data):
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

    title_size = min(
        25, 25 * 1120 / max(1120, pdfmetrics.stringWidth(data["name"], "FormaSans", 25))
    )
    text(40, 45, data["name"], title_size)
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
        line(
            [[x, yy], [x + width, yy]],
            role="native-dimension",
            view=key,
            axis="horizontal",
            value_mm=v["width_mm"],
        )
        xx = x + width + 18
        line([[xx - 7, y], [xx + 7, y]])
        line([[xx - 7, y + height], [xx + 7, y + height]])
        line(
            [[xx, y], [xx, y + height]],
            role="native-dimension",
            view=key,
            axis="vertical",
            value_mm=v["height_mm"],
        )
        text(x, yy + 23, f"Overall width: {v['width_mm']:.6g} mm", 13)
        text(x, yy + 43, f"Overall height: {v['height_mm']:.6g} mm", 13)
        text(
            x,
            yy + 64,
            f"Scale {data['sheet']['scale_label']} | same scale in every view",
            11,
            "#697b83",
        )
    text(835, 615, "Print at 100% / A3 landscape", 12)
    text(835, 635, "50 mm on paper", 11)
    ruler = 50 * SHEET_UNITS_PER_MM
    line([[835, 650], [835 + ruler, 650]], role="paper-calibration")
    line([[835, 645], [835, 655]])
    line([[835 + ruler, 645], [835 + ruler, 655]])
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


def _svg(data, embed_font=False, scene=None):
    font_url = (
        "data:font/ttf;base64," + base64.b64encode(FONT_PATH.read_bytes()).decode()
        if embed_font
        else "/assets/vendor/FormaSans.ttf"
    )
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" data-layout="{data.get("layout", "legacy-v1")}" width="420mm" height="280mm" viewBox="0 0 1200 800">',
        "<metadata>"
        + html.escape(
            FONT_PATH.with_name("FormaSans-LICENSE.txt").read_text(encoding="utf-8")
        )
        + "</metadata>",
        '<rect width="1200" height="800" fill="white"/>',
        f'<style>@font-face{{font-family:FormaSans;src:url("{font_url}")}}</style>',
        '<g font-family="FormaSans,Arial,sans-serif">',
    ]
    for item in _scene(data) if scene is None else scene:
        annotation = (
            f' data-annotation-id="{html.escape(item["annotation_id"], quote=True)}"'
            if "annotation_id" in item
            else ""
        )
        if item["type"] == "text":
            transform = (
                f' transform="rotate({item["rotation"]} {item["x"]} {item["y"]})"'
                if item.get("rotation")
                else ""
            )
            out.append(
                f'<text x="{item["x"]:g}" y="{item["y"]:g}" font-size="{item["size"]}" fill="{item["color"]}"{transform}{annotation}>{html.escape(item["text"])}</text>'
            )
        else:
            points = " ".join(f"{x:.8g},{y:.8g}" for x, y in item["points"])
            dash = ' stroke-dasharray="5 4"' if item["hidden"] else ""
            role = f' data-role="{item["role"]}"' if "role" in item else ""
            out.append(
                f'<polyline points="{points}" fill="none" stroke="{item["color"]}" stroke-width="{item["width"]}"{dash}{role}{annotation}/>'
            )
    return "\n".join(out + ["</g></svg>"])


def drawing_svg(doc, parts, context=None, native_build=None):
    data = drawing_data(doc, parts, context, native_build)
    return _svg(data)


def _pdf(data):
    appendix = _parameter_scenes(data)
    section_pages = [page["scene"] for page in data.get("section_pages", [])]
    data = {**data, "page_count": 1 + len(section_pages) + len(appendix)}
    for i, scene in enumerate(appendix):
        scene.append(
            dict(
                type="text",
                x=1090,
                y=770,
                text=f"{i + 2 + len(section_pages)} / {data['page_count']}",
                size=10,
                color="#243942",
            )
        )
    return _pdf_scenes([_scene(data), *section_pages, *appendix])


def _pdf_scene(scene):
    return _pdf_scenes([scene])


def _pdf_scenes(scenes):
    """Shared vector scene, embedded Unicode font and invariant PDF metadata."""
    output = io.BytesIO()
    canvas = Canvas(
        output,
        pagesize=(PDF_WIDTH, PDF_HEIGHT),
        invariant=1,
        pageCompression=1,
        pdfVersion=(1, 4),
    )
    canvas.setCreator("Forma Studio / deterministic native drawings")
    for scene in scenes:
        canvas.saveState()
        canvas.translate(0, (PDF_HEIGHT - SHEET_HEIGHT * PDF_POINTS_PER_UNIT) / 2)
        canvas.scale(PDF_POINTS_PER_UNIT, PDF_POINTS_PER_UNIT)
        for item in scene:
            color = [int(item["color"][i : i + 2], 16) / 255 for i in (1, 3, 5)]
            if item["type"] == "text":
                canvas.setFillColorRGB(*color)
                canvas.setFont("FormaSans", item["size"])
                for row, value in enumerate(item["text"].splitlines() or [""]):
                    canvas.saveState()
                    canvas.translate(
                        item["x"], 800 - item["y"] - row * item["size"] * 1.2
                    )
                    canvas.rotate(-item.get("rotation", 0))
                    canvas.drawString(0, 0, value)
                    canvas.restoreState()
            else:
                canvas.setStrokeColorRGB(*color)
                canvas.setLineWidth(item["width"])
                canvas.setDash([5, 4] if item["hidden"] else [])
                path = canvas.beginPath()
                for i, (x, y) in enumerate(item["points"]):
                    (path.moveTo if i == 0 else path.lineTo)(x, 800 - y)
                canvas.drawPath(path, stroke=1, fill=0)
        canvas.restoreState()
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def _parameter_rows(data):
    for feature in data.get("feature_parameters", []):
        for key, value in feature["params"].items():
            inactive = (
                feature["type"] == "cut_hole"
                and feature["params"].get("end_condition") == "through_all"
                and key in ("depth", "z")
            )
            if feature["type"] == "folding_assembly":
                family = feature["params"].get("family", "miura")
                inactive = (
                    key in ("rows", "columns", "sector_angle")
                    and family != "miura"
                    or key == "count"
                    and family in ("miura", "cube_net")
                    or key == "panel_height"
                    and family == "cube_net"
                )
            if key in (
                "rotation",
                "sector_angle",
                "fold_angle",
                "pressure_angle",
                "phase",
                "cone_angle",
                "bore_angle",
            ):
                unit = "deg; driver" if key == "fold_angle" else "deg"
            elif key in (
                "count",
                "rows",
                "columns",
                "teeth",
                "starts",
                "addendum_coeff",
                "dedendum_coeff",
                "face_index",
                "source_face",
                "target_face",
                "target",
                "tool",
            ):
                unit = "dimensionless / index"
            elif feature["type"] in ("spur_gear", "bevel_gear") and key in (
                "clearance",
                "backlash",
            ):
                unit = "coefficient"
            elif isinstance(value, (bool, str, dict)) or value is None:
                unit = "source value"
            else:
                unit = (
                    "mm; nominal hinge pitch"
                    if key in ("panel_width", "panel_height")
                    else "mm"
                )
            inactive_reason = (
                "through all"
                if feature["type"] == "cut_hole"
                else "unused in this family"
            )
            meaning = (
                f"inactive ({inactive_reason}); "
                if inactive
                else "suppressed; "
                if feature["suppressed"]
                else ""
            ) + unit
            yield (
                feature,
                key,
                json.dumps(value, ensure_ascii=False, allow_nan=False),
                meaning,
            )
    for record in data.get("library_components", []):
        feature = {
            "id": record["feature_id"],
            "type": "library component",
            "name": record["feature_name"],
            "suppressed": record["suppressed"],
        }
        params = record.get("parameters", {})
        if not isinstance(params, dict):
            params = {}
        for key, value in {
            **params,
            "source": record.get("source"),
            "license": record.get("license"),
        }.items():
            yield (
                feature,
                "library." + key,
                json.dumps(value, ensure_ascii=False, allow_nan=False),
                ("suppressed; " if feature["suppressed"] else "")
                + ("mm; catalogue" if key == "length" else "catalogue / provenance"),
            )


def _parameter_scenes(data):
    rows = list(_parameter_rows(data))
    if not rows:
        return []
    scenes = []
    scene = []
    y, column = 0, 0

    def text(x, y, value, size=12):
        scene.append(
            dict(type="text", x=x, y=y, text=value, size=size, color="#243942")
        )

    def page():
        nonlocal scene, y, column
        if scene:
            scenes.append(scene)
        scene = []
        heading = "FEATURE PARAMETERS / " + data["name"]
        text(
            40,
            45,
            heading,
            min(
                20,
                20 * 1120 / max(1120, pdfmetrics.stringWidth(heading, "FormaSans", 20)),
            ),
        )
        text(
            40,
            77,
            "Editable source values. Overall dimensions on page 1 are measured from native geometry.",
            13,
        )
        text(
            40,
            100,
            "Nominal hinge pitch, profile coordinates and explicit clearances are not interchangeable with the solid envelope.",
            12,
        )
        text(
            40,
            770,
            "Full editable feature history, annotations and project metadata: drawing-source.json / project.json",
            11,
        )
        column, y = 0, 140
        column_heading()

    def column_heading():
        nonlocal y
        x = 40 + column * 580
        for dx, title in (
            (0, "Parameter"),
            (155, "Source value"),
            (345, "Units / meaning"),
        ):
            text(x + dx, y, title, 10)
        y += 25

    def next_column():
        nonlocal column, y
        if column == 0:
            column, y = 1, 140
            column_heading()
        else:
            page()

    widths = {}

    def wrapped(value, width, size=10.5):
        lines, line, length = [], "", 0
        for char in value:
            token = (size, char)
            if token not in widths:
                widths[token] = pdfmetrics.stringWidth(char, "FormaSans", size)
            extent = widths[token]
            if line and length + extent > width:
                lines.append(line)
                line, length = "", 0
            line += char
            length += extent
        return lines + [line]

    def feature_heading(feature, continued=False):
        nonlocal y
        label = (
            feature["id"]
            + " / "
            + feature["type"]
            + (" (continued)" if continued else "")
        )
        for line in wrapped(label, 540, 11.5):
            text(40 + column * 580, y, line, 11.5)
            y += 14
        y += 7

    page()
    active = None
    for feature, key, value, meaning in rows:
        if feature["id"] != active:
            if y + 50 > 735:
                next_column()
            feature_heading(feature)
            active = feature["id"]
        cells = [wrapped(key, 145), wrapped(value, 180), wrapped(meaning, 195)]
        count, offset = max(map(len, cells)), 0
        while offset < count:
            capacity = int((735 - y) // 13) + 1
            if capacity <= 0:
                next_column()
                feature_heading(feature, True)
                continue
            chunk = min(capacity, count - offset)
            for dx, lines in zip((0, 155, 345), cells):
                for index in range(chunk):
                    if offset + index < len(lines):
                        text(
                            40 + column * 580 + dx,
                            y + 13 * index,
                            lines[offset + index],
                            10.5,
                        )
            y += 13 * chunk + 4
            offset += chunk
            if offset < count:
                next_column()
                feature_heading(feature, True)
        y += 3
    if scene:
        scenes.append(scene)
    return scenes


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
    for index, page in enumerate(data.get("section_pages", [])):
        section = page["measurements"]
        factor = section["model_scale"] * SHEET_UNITS_PER_MM
        width, height = section["size_mm"]
        for role, suffix, color in (
            ("section-contour", "CONTOUR", 7),
            ("section-hatch", "HATCH", 8),
        ):
            layer = f"SECTION_{index + 1}_{suffix}"
            doc.layers.new(layer, dxfattribs={"color": color})
            for item in page["scene"]:
                if item.get("role") == role:
                    space.add_lwpolyline(
                        [
                            (x_offset + (x - 70) / factor, height - (y - 155) / factor)
                            for x, y in item["points"]
                        ],
                        dxfattribs={"layer": layer},
                    )
        spec = section["plane"]
        space.add_text(
            f"SECTION {section['tag']} / {spec['name']} / {spec['axis']}={spec['offset_mm']:g} mm",
            dxfattribs={"height": text_height, "insert": (x_offset, height + gap / 2)},
        )
        space.add_linear_dim(
            base=(x_offset, -gap / 3),
            p1=(x_offset, 0),
            p2=(x_offset + width, 0),
            angle=0,
            override={
                "dimtxt": text_height * 0.7,
                "dimasz": text_height * 0.5,
                "dimdec": 3,
            },
        ).render()
        space.add_linear_dim(
            base=(x_offset + width + gap / 3, 0),
            p1=(x_offset + width, 0),
            p2=(x_offset + width, height),
            angle=90,
            override={
                "dimtxt": text_height * 0.7,
                "dimasz": text_height * 0.5,
                "dimdec": 3,
            },
        ).render()
        x_offset += width + gap * 2
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


def export_drawings(doc, parts, folder, context=None):
    """Export shared measured projections plus the full editable document source."""
    doc = deepcopy(doc)
    from .folding import specification as folding_specification

    for feature in doc.get("features", []):
        if feature.get("type") == "folding_assembly":
            feature["params"] = folding_specification(feature.get("params", {}))
    data = drawing_data(doc, parts, context)
    source = json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "FONT-LICENSE.txt").write_bytes(
        FONT_PATH.with_name("FormaSans-LICENSE.txt").read_bytes()
    )
    (folder / "drawing.svg").write_text(_svg(data, embed_font=True), encoding="utf-8")
    (folder / "drawing.pdf").write_bytes(_pdf(data))
    section_files = []
    for index, page in enumerate(data.get("section_pages", [])):
        name = f"section-{index + 1}.svg"
        (folder / name).write_text(
            _svg(data, embed_font=True, scene=page["scene"]), encoding="utf-8"
        )
        section_files.append(name)
    _dxf(data, folder / "drawing.dxf")
    (folder / "drawing-source.json").write_text(source, encoding="utf-8")
    metadata = {
        key: value
        for key, value in data.items()
        if key not in ("views", "isometric", "section_pages")
    }
    metadata["section_pages"] = [
        page["measurements"] for page in data.get("section_pages", [])
    ]
    metadata["isometric"] = (
        {"scale": "NTS", "projection": "Native BREP hidden-line projection"}
        if data.get("isometric")
        else None
    )
    metadata["views"] = {
        key: {k: v for k, v in view.items() if k not in ("visible", "hidden")}
        for key, view in data["views"].items()
    }
    metadata["pdf_text_encoding"] = (
        "Embedded DejaVu Sans; Unicode text and engineering symbols; full source values in the parameter appendix and JSON"
    )
    with (folder / "design-parameters.csv").open(
        "w", newline="", encoding="utf-8"
    ) as output:
        writer = csv.writer(output)
        writer.writerow(
            ["feature_id", "feature_type", "parameter", "source_value", "meaning"]
        )

        def safe(value):
            value = str(value)
            return (
                "'" + value
                if value.startswith(("=", "+", "-", "@", "\t", "\r", "\n"))
                else value
            )

        for feature, key, value, meaning in _parameter_rows(data):
            writer.writerow(
                [safe(feature["id"]), safe(feature["type"]), safe(key), value, meaning]
            )
    (folder / "drawing-measurements.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "files": [
            "design-parameters.csv",
            "drawing.svg",
            "drawing.pdf",
            "drawing.dxf",
            "drawing-source.json",
            "drawing-measurements.json",
            *section_files,
        ],
        "measurements": metadata,
    }
