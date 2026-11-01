"""Exact, axis-aligned panel geometry. These checks do not qualify strength."""

from __future__ import annotations

import math
import cadquery as cq


def normalize_spec(spec):
    out = dict(spec)
    for key in ("inner_width_mm", "inner_depth_mm", "inner_height_mm", "thickness_mm"):
        value = spec.get(key)
        if isinstance(value, bool):
            raise ValueError(f"{key} must be a number in millimetres")
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be a number in millimetres") from None
        if not math.isfinite(value) or not 0 < value <= 10000:
            raise ValueError(f"{key} must be finite and between 0 and 10000 mm")
        out[key] = value
    if out["thickness_mm"] >= min(
        out[k] for k in ("inner_width_mm", "inner_depth_mm", "inner_height_mm")
    ):
        raise ValueError("Thickness must be smaller than every internal dimension")
    if not isinstance(spec.get("lid", False), bool):
        raise ValueError("lid must be a boolean")
    out["lid"] = spec.get("lid", False)
    out["material"] = str(spec.get("material", "unspecified"))[:100]
    out["name"] = str(spec.get("name", "Panel crate"))[:100]
    return out


def build_parts(spec):
    s = normalize_spec(spec)
    w, d, h, t = (
        s[k]
        for k in ("inner_width_mm", "inner_depth_mm", "inner_height_mm", "thickness_mm")
    )
    definitions = [
        ("base", "Base", (w + 2 * t, d + 2 * t, t), (0, 0, t / 2)),
        ("front", "Front", (w + 2 * t, t, h), (0, -(d + t) / 2, t + h / 2)),
        ("back", "Back", (w + 2 * t, t, h), (0, (d + t) / 2, t + h / 2)),
        ("left", "Left", (t, d, h), (-(w + t) / 2, 0, t + h / 2)),
        ("right", "Right", (t, d, h), ((w + t) / 2, 0, t + h / 2)),
    ]
    if s["lid"]:
        definitions.append(
            ("lid", "Lid", (w + 2 * t, d + 2 * t, t), (0, 0, h + 1.5 * t))
        )
    return [
        dict(
            id=pid,
            name=name,
            size_mm=list(size),
            center_mm=list(center),
            shape=cq.Workplane("XY").box(*size).translate(center).val(),
        )
        for pid, name, size, center in definitions
    ]


def mesh_data(parts, tolerance=0.1):
    result = []
    for p in parts:
        vertices, triangles = p["shape"].tessellate(tolerance)
        result.append(
            dict(
                id=p["id"],
                name=p["name"],
                size_mm=p["size_mm"],
                center_mm=p["center_mm"],
                vertices=[v for point in vertices for v in point.toTuple()],
                triangles=[v for face in triangles for v in face],
            )
        )
    return result


def compound(parts):
    return cq.Compound.makeCompound([p["shape"] for p in parts])


def verify_geometry(spec, parts):
    s = normalize_spec(spec)
    w, d, h, t = (
        s[k]
        for k in ("inner_width_mm", "inner_depth_mm", "inner_height_mm", "thickness_mm")
    )
    expected = (
        2 * t * d * h
        + 2 * t * (w + 2 * t) * h
        + (1 + int(s["lid"])) * (w + 2 * t) * (d + 2 * t) * t
    )
    actual = sum(p["shape"].Volume() for p in parts)
    tolerance = max(1e-6, expected * 1e-9)
    collisions = []
    for i, a in enumerate(parts):
        for b in parts[i + 1 :]:
            volume = a["shape"].intersect(b["shape"]).Volume()
            if volume > tolerance:
                collisions.append(dict(parts=[a["id"], b["id"]], volume_mm3=volume))
    cavity = cq.Workplane("XY").box(w, d, h).translate((0, 0, t + h / 2)).val()
    intrusion = sum(p["shape"].intersect(cavity).Volume() for p in parts)
    bounds = compound(parts).BoundingBox()
    expected_outer = [w + 2 * t, d + 2 * t, h + t * (1 + int(s["lid"]))]
    actual_outer = [bounds.xlen, bounds.ylen, bounds.zlen]
    valid = all(p["shape"].isValid() for p in parts)
    dimensions_ok = all(abs(a - b) < 1e-6 for a, b in zip(actual_outer, expected_outer))
    passed = (
        valid
        and dimensions_ok
        and not collisions
        and intrusion <= tolerance
        and abs(actual - expected) <= tolerance
        and len(parts) == 5 + int(s["lid"])
    )
    return dict(
        passed=passed,
        brep_valid=valid,
        part_count=len(parts),
        panel_overlap_collisions=collisions,
        cavity_intrusion_mm3=intrusion,
        expected_volume_mm3=expected,
        actual_volume_mm3=actual,
        expected_outer_mm=expected_outer,
        actual_outer_mm=actual_outer,
        internal_clear_mm=[w, d, h],
        volume_tolerance_mm3=tolerance,
        scope="Geometry only. No strength, joint, load, fabrication tolerance, or material qualification.",
    )
