"""Deterministic aligned review sheet. Native geometry supplies every dimension."""

import math
from reportlab.pdfbase import pdfmetrics


def aligned_scene(data):
    scene = []

    def text(x, y, value, size=11, rotation=0, **extra):
        scene.append(
            dict(
                type="text",
                x=x,
                y=y,
                text=str(value),
                size=size,
                rotation=rotation,
                color="#243942",
                **extra,
            )
        )

    def line(points, width=0.7, hidden=False, color="#243942", **extra):
        scene.append(
            dict(
                type="polyline",
                points=points,
                width=width,
                hidden=hidden,
                color=color,
                **extra,
            )
        )

    def arrow(x, y, dx, dy):
        line(
            [
                [x + dx * 7 - dy * 2.2, y + dy * 7 + dx * 2.2],
                [x, y],
                [x + dx * 7 + dy * 2.2, y + dy * 7 - dx * 2.2],
            ],
            width=0.8,
            role="dimension-arrow",
        )

    def fit_text(x, y, value, max_width, size=11):
        extent = pdfmetrics.stringWidth(str(value), "FormaSans", size)
        text(x, y, value, min(size, size * max_width / max(extent, 1)))

    line([[24, 20], [1176, 20], [1176, 780], [24, 780], [24, 20]], width=1)
    fit_text(44, 52, data["name"], 1100, 23)
    text(
        44,
        76,
        "NATIVE CAD DRAWING  /  all dimensions in mm  /  dashed lines: hidden edges",
        11,
    )
    line([[44, 90], [1156, 90]], color="#a9b3b6")
    for key, view in data["views"].items():
        x, y = view["origin_px"]
        scale = view["scale_px_per_mm"]
        xmin, _, _, ymax = view["bounds_mm"]
        text(x, y - 19, view["label"], 13)
        for hidden in (True, False):
            for path in view["hidden" if hidden else "visible"]:
                line(
                    [
                        [x + (p[0] - xmin) * scale, y + (ymax - p[1]) * scale]
                        for p in path
                    ],
                    width=0.65 if hidden else 1,
                    hidden=hidden,
                    color="#98a4a8" if hidden else "#243942",
                    role="projected-edge",
                    view=key,
                )
        width, height = view["width_mm"] * scale, view["height_mm"] * scale
        yy = y + height + 28
        xx = x + width + 28
        for endpoint in (x, x + width):
            line(
                [[endpoint, y + height + 3], [endpoint, yy + 5]],
                width=0.5,
                role="dimension-extension",
            )
        line(
            [[x, yy], [x + width, yy]],
            role="native-dimension",
            view=key,
            axis="horizontal",
            value_mm=view["width_mm"],
        )
        arrow(x, yy, 1, 0)
        arrow(x + width, yy, -1, 0)
        label = f"{view['axis_names'][0]} {view['width_mm']:.6g}"
        extent = pdfmetrics.stringWidth(label, "FormaSans", 10.5)
        text(x + width / 2 - extent / 2, yy - 5, label, 10.5)
        for endpoint in (y, y + height):
            line(
                [[x + width + 3, endpoint], [xx + 5, endpoint]],
                width=0.5,
                role="dimension-extension",
            )
        line(
            [[xx, y], [xx, y + height]],
            role="native-dimension",
            view=key,
            axis="vertical",
            value_mm=view["height_mm"],
        )
        arrow(xx, y, 0, 1)
        arrow(xx, y + height, 0, -1)
        label = f"{view['axis_names'][1]} {view['height_mm']:.6g}"
        extent = pdfmetrics.stringWidth(label, "FormaSans", 10.5)
        text(xx - 5, y + height / 2 + extent / 2, label, 10.5, rotation=-90)
    for index, spec in enumerate(data.get("section_specs", [])):
        axis = "XYZ".index(spec["axis"])
        tag = chr(65 + index) + "-" + chr(65 + index)
        for key, view in data["views"].items():
            axes = {"front": (0, 2), "top": (0, 1), "right": (1, 2)}[key]
            if axis not in axes:
                continue
            coordinate = axes.index(axis)
            lo = view["bounds_mm"][coordinate]
            hi = view["bounds_mm"][coordinate + 2]
            if not lo <= spec["offset_mm"] <= hi:
                continue
            x, y = view["origin_px"]
            scale = view["scale_px_per_mm"]
            w = view["width_mm"] * scale
            h = view["height_mm"] * scale
            direction = -1 if axis in (0, 2) else 1
            if coordinate == 0:
                xx = x + (spec["offset_mm"] - lo) * scale
                points = [[xx, y - 12], [xx, y + h + 12]]
                for yy in (y - 12, y + h + 12):
                    arrow(xx, yy, -direction, 0)
                text(xx + 12, y - 3, tag, 8)
                text(xx + 12, y + h + 9, tag, 8)
            else:
                yy = y + (hi - spec["offset_mm"]) * scale
                points = [[x - 12, yy], [x + w + 12, yy]]
                for xx in (x - 12, x + w + 12):
                    arrow(xx, yy, 0, direction)
                text(x - 24, yy - 8, tag, 8)
                text(x + w + 15, yy - 8, tag, 8)
            line(points, width=1.1, hidden=True, role="cutting-plane")
    iso = data.get("isometric")
    if iso:
        text(825, 127, "ISOMETRIC  /  NTS", 12)
        points = [p for path in iso["visible"] for p in path]
        if points:
            lo = [min(p[i] for p in points) for i in (0, 1)]
            hi = [max(p[i] for p in points) for i in (0, 1)]
            ratio = min(310 / max(hi[0] - lo[0], 1e-8), 220 / max(hi[1] - lo[1], 1e-8))
            for path in iso["visible"]:
                line(
                    [
                        [825 + (p[0] - lo[0]) * ratio, 150 + (hi[1] - p[1]) * ratio]
                        for p in path
                    ],
                    width=0.8,
                    role="isometric-edge",
                )
    bodies = data.get("body_rows", [])
    if 1 < len(bodies) <= 12:
        text(825, 423, "SOURCE PARTS", 11)
        text(825, 442, "ITEM     BODY                 QTY     ENVELOPE / mm", 8)
        line([[825, 448], [1152, 448]], color="#a9b3b6")
        for i, body in enumerate(bodies):
            y = 465 + i * 12
            text(825, y, f"P{i + 1:02d}", 9)
            text(867, y, body["id"], 8.5)
            text(947, y, "1", 9)
            fit_text(972, y, " × ".join(f"{v:.5g}" for v in body["size_mm"]), 178, 8.5)
    # The end view is on the left, adjacent to the small end of the frustum.
    # Text declaration accompanies the third-angle symbol, without claiming a
    # complete ISO/ASME manufacturing drawing or inventing approval signatures.
    for radius in (7, 13):
        line(
            [
                [
                    67 + radius * math.cos(t * math.pi / 24),
                    626 + radius * math.sin(t * math.pi / 24),
                ]
                for t in range(49)
            ],
            width=0.7,
        )
    line([[92, 619], [132, 613], [132, 639], [92, 633], [92, 619]], width=0.8)
    line([[48, 626], [142, 626]], width=0.4)
    text(153, 630, "THIRD-ANGLE PROJECTION", 10)
    text(
        44,
        655,
        "W = width (X)   D = depth (Y)   H = height (Z). Orthographic views share the stated scale.",
        10,
    )
    line([[24, 670], [1176, 670]], width=1)
    for x in (410, 800):
        line([[x, 670], [x, 780]], width=0.7)
    for y in (706, 742):
        line([[24, y], [1176, y]], width=0.7)
    context = data["drawing_context"]
    text(40, 685, "SOURCE REVISION", 8)
    fit_text(40, 701, context["revision_id"], 355, 11)
    text(426, 685, "FEATURE SOURCE", 8)
    text(426, 701, context["geometry_hash"][:24], 10)
    text(816, 685, "SHEET / SCALE", 8)
    text(
        816,
        701,
        f"{data.get('sheet_number', 1)} / {data.get('page_count', '-')}   A3   {data['sheet']['scale_label']} (ORTHO)",
        10,
    )
    text(40, 721, "POSE", 8)
    fit_text(40, 737, context["pose"], 355, 10)
    text(426, 721, "MATERIAL / PROCESS", 8)
    fit_text(426, 737, context["material"], 355, 10)
    text(816, 721, "TOLERANCES / FIT", 8)
    fit_text(816, 737, context["tolerances"], 340, 10)
    text(40, 758, "STATUS", 8)
    text(40, 774, "GEOMETRY REVIEW / physical validation pending", 9)
    text(426, 758, "PRINT AT 100% / A3 LANDSCAPE", 8)
    ruler = 50 * 1200 / 420
    line([[426, 770], [426 + ruler, 770]], role="paper-calibration")
    line([[426, 766], [426, 774]])
    line([[426 + ruler, 766], [426 + ruler, 774]])
    text(426 + ruler + 10, 773, "50 mm", 9)
    text(816, 758, "NOTES", 8)
    text(816, 774, "REF annotations do not control geometry", 9)
    for a in data["annotations"]:
        if a["type"] in ("line", "dimension"):
            line(
                [[a["x"], a["y"]], [a["x2"], a["y2"]]],
                width=1.5,
                color=a["color"],
                role="reference-annotation",
                annotation_id=a["id"],
            )
        if a["type"] == "dimension":
            label = (
                f"{a['value_mm']:g} mm REF"
                if "value_mm" in a
                else "Reference annotation"
            ) + (" - " + a["text"] if a["text"] else "")
            text(
                (a["x"] + a["x2"]) / 2,
                (a["y"] + a["y2"]) / 2 - 8,
                label,
                12,
                annotation_id=a["id"],
            )
        elif a.get("text"):
            text(a["x"], a["y"], a["text"], 12, annotation_id=a["id"])
    return scene
