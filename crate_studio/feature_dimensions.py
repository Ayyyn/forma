"""Conservative source-parameter dimensions; never fit parameters to a mesh."""

from copy import deepcopy
import math


def _pose(point, p):
    x, y, z = point
    a, b, c = [math.radians(v) for v in p.get("rotation", [0, 0, 0])]
    y, z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
    x, z = x * math.cos(b) + z * math.sin(b), -x * math.sin(b) + z * math.cos(b)
    x, y = x * math.cos(c) - y * math.sin(c), x * math.sin(c) + y * math.cos(c)
    return [v + t for v, t in zip((x, y, z), p.get("translation", [0, 0, 0]))]


def feature_dimensions(document, result):
    """Propagate known feature anchors through supported rigid history only.

    Body correspondence is retained only for append or known count-preserving
    operations. Merges, splits, patterns and mates discard affected bindings.
    A source feature dimension is not necessarily a final body envelope.
    """
    rows, count = [], 0
    for f, status in zip(document["features"], result["features"]):
        if status["status"] != "ok":
            continue
        p, kind = f["params"], f["type"]
        after = status["body_count"]
        target = p.get("target_part_id")
        ids = [f"body_{i + 1:03d}" for i in range(count)]
        affected = {target} if target else set(ids)

        if kind == "transform" and after == count:
            for row in rows:
                if row["part_id"] in affected:
                    for key in ("a", "b", "fromA", "fromB"):
                        row[key] = _pose(row[key], p)
            continue

        primitive = kind in ("box", "cylinder", "sketch_extrude")
        appended = primitive and (
            (p.get("operation", "add") == "new_body" and after == count + 1)
            or (count == 0 and after == 1 and p.get("operation", "add") == "add")
        )
        stable_cut = (
            kind in ("cut_hole", "fillet", "chamfer", "face_offset")
            and after == count
            and (target is not None or count == 1)
        )
        if kind == "import_step" and after >= count:
            count = after
            continue
        if not appended and not stable_cut:
            rows = (
                [r for r in rows if r["part_id"] not in affected]
                if after == count and target
                else []
            )

        def add(key, label, a, b, offset, multiplier=1, symbol=""):
            if key not in p:
                return
            pid = f"body_{count + 1:03d}" if appended else target or "body_001"
            rows.append(
                {
                    "id": f"{f['id']}:{key}",
                    "feature_id": f["id"],
                    "feature_name": f.get("name", kind),
                    "part_id": pid,
                    "key": key,
                    "label": label,
                    "value_mm": p[key] * multiplier,
                    "multiplier": multiplier,
                    "symbol": symbol,
                    "fromA": list(a),
                    "fromB": list(b),
                    "a": [v + o for v, o in zip(a, offset)],
                    "b": [v + o for v, o in zip(b, offset)],
                }
            )

        if appended:
            x, y, z = (
                p.get("cx", p.get("x", 0)),
                p.get("cy", p.get("y", 0)),
                p.get("z", 0),
            )
            h = p["height"]
            style = p.get("shape", "rectangle") if kind == "sketch_extrude" else kind
            if style in ("box", "rectangle"):
                w, d = p["width"], p["depth"]
                gap = max(2, min(12, max(w, d, h) * 0.15))
                add(
                    "width",
                    "Width",
                    [x - w / 2, y - d / 2, z + h],
                    [x + w / 2, y - d / 2, z + h],
                    [0, -gap, 0],
                )
                add(
                    "depth",
                    "Depth",
                    [x + w / 2, y - d / 2, z + h],
                    [x + w / 2, y + d / 2, z + h],
                    [gap, 0, 0],
                )
                add(
                    "height",
                    "Height",
                    [x + w / 2, y + d / 2, z],
                    [x + w / 2, y + d / 2, z + h],
                    [gap, gap, 0],
                )
            elif style in ("cylinder", "circle"):
                r = p["radius"]
                add(
                    "radius",
                    "Diameter",
                    [x - r, y, z + h],
                    [x + r, y, z + h],
                    [0, 0, 0],
                    2,
                    "Ø",
                )
                add(
                    "height",
                    "Height",
                    [x + r, y, z],
                    [x + r, y, z + h],
                    [max(2, r * 0.3), 0, 0],
                )
            elif style == "polyline":
                x0, y0 = p["points"][0]
                add(
                    "height",
                    "Extrusion height",
                    [x + x0, y + y0, z],
                    [x + x0, y + y0, z + h],
                    [3, 3, 0],
                )
        if stable_cut and kind == "cut_hole":
            n = p.get("direction", [0, 0, 1])
            # A diameter lies perpendicular to the actual drill direction.
            basis = (
                [1, 0, 0] if abs(n[0]) < 0.9 * math.dist(n, [0, 0, 0]) else [0, 1, 0]
            )
            cross = [
                n[1] * basis[2] - n[2] * basis[1],
                n[2] * basis[0] - n[0] * basis[2],
                n[0] * basis[1] - n[1] * basis[0],
            ]
            length = math.dist(cross, [0, 0, 0])
            u = [v / length for v in cross]
            centre = [p.get(k, 0) for k in ("x", "y", "z")]
            r = p["radius"]
            add(
                "radius",
                "Hole diameter",
                [v - r * t for v, t in zip(centre, u)],
                [v + r * t for v, t in zip(centre, u)],
                [0, 0, 0],
                2,
                "Ø",
            )
        count = after
    valid_ids = {part["id"] for part in result["parts"]}
    return [row for row in rows if row["part_id"] in valid_ids]


def edit_dimension(document, dimensions, dimension_id, value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 < value <= 1e6
    ):
        raise ValueError(
            "Dimension must be a finite positive millimetre value, at most 1000000"
        )
    row = next((d for d in dimensions if d["id"] == dimension_id), None)
    if row is None:
        raise ValueError(
            "This dimension has no supported source parameter on this revision"
        )
    updated = deepcopy(document)
    f = next(f for f in updated["features"] if f["id"] == row["feature_id"])
    f["params"][row["key"]] = value / row["multiplier"]
    return updated, row
