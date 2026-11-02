"""Bounded parametric BREP workspace. Data is interpreted, never executed as code.

All lengths are mm, rotations degrees, boxes are XY-centred with bottom at z=0.
Topology IDs are deterministic ordinal IDs, not persistent naming across topology edits.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cadquery as cq
import trimesh
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

MAX_FEATURES = 60
MAX_BODIES = 50


def _bounds(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, box, False, False)
    values = box.Get()
    return [list(values[:3]), list(values[3:])]


def _number(p, key, default=None, positive=False, limit=10000):
    value = p.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be numeric")
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{key} must be numeric") from None
    if not math.isfinite(value) or abs(value) > limit or (positive and value <= 0):
        raise ValueError(
            f"{key} must be finite, "
            + ("positive, " if positive else "")
            + f"and at most {limit} in magnitude"
        )
    return value


def _vector(p, key, default=(0, 0, 0)):
    value = p.get(key, default)
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{key} must have three numbers")
    return tuple(
        _number({"v": x}, "v", limit=360000 if key == "rotation" else 10000)
        for x in value
    )


def _flag(p, key, default=False):
    value = p.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def _compound(shapes):
    return cq.Compound.makeCompound(shapes)


def _union(shapes):
    if not shapes:
        raise ValueError("Operation needs an existing body")
    return _safe_clean(shapes[0].fuse(*shapes[1:])) if len(shapes) > 1 else shapes[0]


def _solids(shape):
    solids = list(shape.Solids())
    if not solids:
        raise ValueError("Operation produced no solid bodies")
    return solids


def _safe_clean(shape):
    """Unifying same-domain faces may corrupt imported fillet/hole intersections.

    Retain the valid Boolean result if optional simplification changes its volume,
    validity or solid count. Simplification is cosmetic, never a correctness gate.
    """
    try:
        # OCCT cleanup can mutate shared underlying geometry: deep-copy first so
        # the exact Boolean fallback cannot itself be damaged by simplification.
        simplified = shape.copy().clean()
        if (
            simplified.isValid()
            and len(simplified.Solids()) == len(shape.Solids())
            and abs(simplified.Volume() - shape.Volume())
            <= max(1e-7, abs(shape.Volume()) * 1e-8)
        ):
            return simplified
    except Exception:
        pass
    return shape


def _subtract(target, tool):
    """Reject a missed/tangent cutting tool instead of silently accepting a no-op."""
    before = float(target.Volume())
    result = _safe_clean(target.cut(tool))
    removed = before - float(result.Volume())
    if removed <= max(1e-8, before * 1e-10):
        raise ValueError(
            "NoIntersection: cutting tool removes no measurable volume from the target"
        )
    return _solids(result)


def _checked(shapes):
    if len(shapes) > MAX_BODIES:
        raise ValueError(f"At most {MAX_BODIES} bodies are allowed")
    for shape in shapes:
        if (
            not shape.isValid()
            or not math.isfinite(shape.Volume())
            or shape.Volume() <= 1e-9
        ):
            raise ValueError("Operation produced invalid or zero-volume geometry")
        b = shape.BoundingBox()
        if max(abs(x) for x in (b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax)) > 1e6:
            raise ValueError("Geometry exceeds workspace coordinate limits")
    return shapes


def _apply(kind, p, shapes, asset_loader):
    if kind in ("spur_gear", "bevel_gear", "threaded_body", "socket_head_screw"):
        from .mechanical_features import apply_mechanical

        return apply_mechanical(kind, p, shapes)
    if kind in ("box", "cylinder", "sketch_extrude"):
        style = p.get("shape", "rectangle") if kind == "sketch_extrude" else kind
        height = _number(p, "height", positive=True)
        if style in ("box", "rectangle"):
            tool = (
                cq.Workplane("XY")
                .box(
                    _number(p, "width", positive=True),
                    _number(p, "depth", positive=True),
                    height,
                    centered=(True, True, False),
                )
                .val()
            )
        elif style in ("cylinder", "circle"):
            tool = (
                cq.Workplane("XY")
                .circle(_number(p, "radius", positive=True))
                .extrude(height)
                .val()
            )
        elif style == "polyline":
            points = p.get("points")
            if not isinstance(points, list) or not 3 <= len(points) <= 500:
                raise ValueError("Polyline requires 3 to 500 finite [x,y] points")
            checked = []
            for point in points:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise ValueError("Each polyline point must be [x,y]")
                checked.append(tuple(_number({"v": v}, "v") for v in point))
            if checked[0] == checked[-1]:
                checked.pop()
            if len(set(checked)) < 3:
                raise ValueError("Polyline needs three distinct points")
            tool = cq.Workplane("XY").polyline(checked).close().extrude(height).val()
        else:
            raise ValueError("Sketch shape must be rectangle, circle or polyline")
        tool = tool.translate(
            (
                _number(p, "cx", p.get("x", 0)),
                _number(p, "cy", p.get("y", 0)),
                _number(p, "z", 0),
            )
        )
        operation = p.get("operation", "add")
        if operation == "add":
            return _solids(_union(shapes + [tool]))
        if operation == "cut":
            return _subtract(_union(shapes), tool)
        if operation == "new_body":
            return shapes + [tool]
        raise ValueError("operation must be add, cut or new_body")
    if kind == "import_step":
        asset_id = p.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError("import_step requires asset_id")
        if asset_loader is None:
            raise ValueError("STEP asset loader unavailable")
        path = asset_loader(asset_id)
        if not isinstance(path, (str, Path)):
            raise ValueError("Asset loader must return a local STEP path")
        imported = cq.importers.importStep(str(path))
        return shapes + list(imported.solids().vals())
    if not shapes:
        raise ValueError("Operation needs an existing body")
    if kind == "cut_hole":
        tool = (
            cq.Workplane("XY")
            .circle(_number(p, "radius", positive=True))
            .extrude(_number(p, "depth", positive=True))
            .translate(tuple(_number(p, k, 0) for k in ("x", "y", "z")))
            .val()
        )
        return _subtract(_union(shapes), tool)
    if kind == "face_offset":
        ids = [f"body_{i+1:03d}" for i in range(len(shapes))]
        part_id = p.get("part_id")
        if part_id not in ids:
            raise ValueError("part_id must identify a current body")
        body_index = ids.index(part_id)
        body = shapes[body_index]
        face_index = p.get("face_index")
        if (
            isinstance(face_index, bool)
            or not isinstance(face_index, int)
            or not 0 <= face_index < len(body.Faces())
        ):
            raise ValueError("face_index must be a valid zero-based face index")
        face = body.Faces()[face_index]
        if face.geomType() != "PLANE":
            raise ValueError("Face offset only supports planar faces")
        distance = _number(p, "distance")
        if distance == 0:
            raise ValueError("Face offset distance must be nonzero")
        tool = cq.Solid.extrudeLinear(
            face.outerWire(),
            face.innerWires(),
            face.normalAt().normalized().multiply(distance),
        )
        if distance < 0:
            replacements = _subtract(body, tool)
        else:
            updated = _safe_clean(body.fuse(tool))
            if updated.Volume() - body.Volume() <= max(1e-8, body.Volume() * 1e-10):
                raise ValueError("Face offset adds no measurable volume")
            replacements = _solids(updated)
        result = list(shapes)
        result[body_index : body_index + 1] = replacements
        return result
    if kind in ("fillet", "chamfer"):
        selector = p.get("selector", "vertical")
        if selector not in ("vertical", "all"):
            raise ValueError("Edge selector must be vertical or all")
        amount = _number(p, "radius" if kind == "fillet" else "distance", positive=True)
        explicit = "edge_indices" in p
        selected_body = None
        if explicit:
            ids = [f"body_{i+1:03d}" for i in range(len(shapes))]
            if p.get("part_id") not in ids:
                raise ValueError("Explicit edges require a current part_id")
            selected_body = ids.index(p["part_id"])
            indices = p["edge_indices"]
            if not isinstance(indices, list) or not 1 <= len(indices) <= 500:
                raise ValueError(
                    "edge_indices must contain 1 to 500 unique edge ordinals"
                )
            if any(
                isinstance(i, bool)
                or not isinstance(i, int)
                or not 0 <= i < len(shapes[selected_body].Edges())
                for i in indices
            ):
                raise ValueError("edge_indices contains an invalid edge ordinal")
            if len(set(indices)) != len(indices):
                raise ValueError("edge_indices must be unique")
        elif "part_id" in p:
            raise ValueError("part_id requires explicit edge_indices")
        result = []
        for body_index, shape in enumerate(shapes):
            if explicit and body_index != selected_body:
                result.append(shape)
                continue
            selected = (
                [shape.Edges()[i] for i in indices]
                if explicit
                else cq.Workplane("XY")
                .newObject([shape])
                .edges("|Z" if selector == "vertical" else None)
                .vals()
            )
            if not selected:
                raise ValueError("Selector matched no edges")
            if len(selected) > 500:
                raise ValueError("Too many edges selected")
            updated = (
                shape.fillet(amount, selected)
                if kind == "fillet"
                else shape.chamfer(amount, None, selected)
            )
            result.extend(_solids(updated))
        return result
    if kind == "transform":
        shift = _vector(p, "translation")
        angles = _vector(p, "rotation")
        target = p.get("target_part_id")
        ids = [f"body_{i+1:03d}" for i in range(len(shapes))]
        if target is not None and target not in ids:
            raise ValueError("target_part_id does not identify a current body")
        result = []
        for index, shape in enumerate(shapes):
            if target is not None and ids[index] != target:
                result.append(shape)
                continue
            for axis, angle in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), angles):
                if angle:
                    shape = shape.rotate((0, 0, 0), axis, angle)
            result.append(shape.translate(shift))
        return result
    if kind == "mate":
        ids = [f"body_{i+1:03d}" for i in range(len(shapes))]
        source = p.get("source_part_id")
        target = p.get("target_part_id")
        if source not in ids or target not in ids or source == target:
            raise ValueError("Mate requires two different current body IDs")
        si, ti = ids.index(source), ids.index(target)
        selected = []
        for key, body in [("source_face", shapes[si]), ("target_face", shapes[ti])]:
            index = p.get(key)
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or not 0 <= index < len(body.Faces())
            ):
                raise ValueError(f"{key} must be a valid zero-based face index")
            face = body.Faces()[index]
            if face.geomType() != "PLANE":
                raise ValueError("Mate only supports planar faces")
            selected.append(face)
        sf, tf = selected
        center = sf.Center()
        target_normal = tf.normalAt().normalized()
        original = sf.normalAt().normalized()
        desired = target_normal.multiply(-1)
        axis = original.cross(desired)
        dot = max(-1, min(1, original.dot(desired)))
        shape = shapes[si]
        if axis.Length < 1e-10 and dot < 0:
            axis = original.cross(
                cq.Vector(1, 0, 0) if abs(original.x) < 0.8 else cq.Vector(0, 1, 0)
            )
        if axis.Length > 1e-10:
            shape = shape.rotate(
                center, center + axis.normalized(), math.degrees(math.acos(dot))
            )
        mode = p.get("mode", "coincident")
        offset = _number(p, "offset", 0)
        if mode == "coincident":
            shape = shape.translate(
                tf.Center() + target_normal.multiply(offset) - center
            )
        elif mode == "parallel":
            if offset != 0:
                raise ValueError(
                    "Parallel alignment rotates only; use coincident for an offset"
                )
        else:
            raise ValueError("Mate mode must be coincident or parallel")
        result = list(shapes)
        result[si] = shape
        return result
    if kind == "linear_pattern":
        count = _number(p, "count", positive=True, limit=50)
        if count != int(count):
            raise ValueError("Pattern count must be an integer")
        count = int(count)
        if count * len(shapes) > MAX_BODIES:
            raise ValueError("Pattern exceeds 50 body limit")
        step = _vector(p, "spacing")
        if count > 1 and all(x == 0 for x in step):
            raise ValueError("Pattern spacing cannot be zero")
        result = [
            shape.translate(tuple(i * x for x in step))
            for i in range(count)
            for shape in shapes
        ]
        return _solids(_union(result)) if _flag(p, "fuse") else result
    if kind == "mirror":
        plane = p.get("plane", "YZ")
        if plane not in ("XY", "XZ", "YZ"):
            raise ValueError("Mirror plane must be XY, XZ or YZ")
        result = [s.mirror(plane) for s in shapes]
        if _flag(p, "keep_original", True):
            result = shapes + result
        return result
    if kind in ("union", "boolean_union"):
        return _solids(_union(shapes))
    if kind in ("cut", "boolean_cut"):
        target = p.get("target", 0)
        tool = p.get("tool", 1)
        if (
            isinstance(target, bool)
            or isinstance(tool, bool)
            or not isinstance(target, int)
            or not isinstance(tool, int)
        ):
            raise ValueError("Boolean target/tool must be body indices")
        if target == tool or min(target, tool) < 0 or max(target, tool) >= len(shapes):
            raise ValueError(
                "Boolean target/tool indices must identify different existing bodies"
            )
        result = _subtract(shapes[target], shapes[tool])
        return [s for i, s in enumerate(shapes) if i not in (target, tool)] + result
    raise ValueError(f"Unsupported feature type: {kind}")


def _mesh(shape):
    vertices, triangles = shape.tessellate(0.15, 0.1)
    return {
        "vertices": [float(x) for v in vertices for x in v.toTuple()],
        "triangles": [int(x) for t in triangles for x in t],
    }


def inspect_shape(shape, part_id="body_001"):
    """Metadata and per-face tessellation; ordinal topology IDs are deterministic."""
    bounds = _bounds(shape)
    faces = []
    edges = []
    if len(shape.Faces()) > 5000:
        raise ValueError("Body exceeds 5000 face inspection limit")
    for i, face in enumerate(shape.Faces()):
        entry = {
            "id": f"{part_id}:face_{i:04d}",
            "part_id": part_id,
            "face_index": i,
            "geom_type": face.geomType(),
            "center": list(face.Center().toTuple()),
            "area_mm2": float(face.Area()),
            "type": face.geomType(),
            **_mesh(face),
        }
        try:
            entry["normal"] = list(face.normalAt().toTuple())
        except Exception:
            entry["normal"] = None
        faces.append(entry)
    for i, edge in enumerate(shape.Edges()):
        if edge.geomType() == "LINE":
            polyline = [
                list(edge.startPoint().toTuple()),
                list(edge.endPoint().toTuple()),
            ]
        else:
            sampled, _ = edge.sample(64)
            polyline = [list(point.toTuple()) for point in sampled]
            if edge.IsClosed() and polyline:
                polyline.append(list(polyline[0]))
        edges.append(
            {
                "id": f"{part_id}:edge_{i:04d}",
                "part_id": part_id,
                "edge_index": i,
                "length_mm": float(edge.Length()),
                "center": list(edge.Center().toTuple()),
                "start": list(edge.startPoint().toTuple()),
                "end": list(edge.endPoint().toTuple()),
                "type": edge.geomType(),
                "polyline_points": polyline,
            }
        )
    return {
        "face_meshes": faces,
        "edge_meta": edges,
        "volume_mm3": float(shape.Volume()),
        "area_mm2": float(shape.Area()),
        "bounds_mm": bounds,
        "valid": bool(shape.isValid()),
    }


def build_document(doc, asset_loader=None):
    statuses = []
    shapes = []
    failed = False
    error = None
    result = {
        "parts": [],
        "mesh": [],
        "face_meshes": [],
        "edge_meta": [],
        "metrics": {},
        "features": statuses,
        "checks": {
            "passed": False,
            "scope": "BREP geometry only; no strength, material or manufacturing qualification.",
            "assembly_scope": "Mates sequentially align planar faces; no simultaneous constraint solver or collision qualification.",
            "topology_ids": "Deterministic ordinal IDs; only stable while body order and topology are unchanged.",
        },
    }
    if not isinstance(doc, dict) or not isinstance(doc.get("features"), list):
        result["checks"]["error"] = "Document must contain a features array"
        return result
    features = doc["features"]
    if len(features) > MAX_FEATURES:
        result["checks"]["error"] = "At most 60 features are allowed"
        return result
    seen = set()
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            failed = True
            statuses.append(
                {
                    "id": f"invalid_{index}",
                    "status": "error",
                    "error": "Feature must be an object",
                }
            )
            continue
        fid = feature.get("id")
        kind = feature.get("type")
        entry = {"id": fid, "type": kind, "name": feature.get("name", kind)}
        if failed:
            entry["status"] = "blocked"
            statuses.append(entry)
            continue
        try:
            if not isinstance(fid, str) or not fid or fid in seen:
                raise ValueError("Feature IDs must be nonempty unique strings")
            seen.add(fid)
            if _flag(feature, "suppressed"):
                entry["status"] = "suppressed"
                statuses.append(entry)
                continue
            params = feature.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("Feature params must be an object")
            shapes = _checked(_apply(kind, params, shapes, asset_loader))
            entry.update(
                status="ok",
                body_count=len(shapes),
                volume_mm3=sum(s.Volume() for s in shapes),
            )
        except Exception as exc:
            failed = True
            error = f"{type(exc).__name__}: {str(exc)[:400]}"
            entry.update(status="error", error=error)
        statuses.append(entry)
    try:
        for index, shape in enumerate(shapes):
            pid = f"body_{index+1:03d}"
            name = f"Body {index+1}"
            info = inspect_shape(shape, pid)
            result["parts"].append({"id": pid, "name": name, "shape": shape})
            result["mesh"].append({"id": pid, "name": name, **_mesh(shape)})
            result["face_meshes"].extend(info["face_meshes"])
            result["edge_meta"].extend(info["edge_meta"])
        if shapes:
            combined = _compound(shapes)
            bounds = _bounds(combined)
            result["metrics"] = {
                "body_count": len(shapes),
                "solid_count": len(shapes),
                "volume_mm3": sum(float(s.Volume()) for s in shapes),
                "area_mm2": sum(float(s.Area()) for s in shapes),
                "surface_area_mm2": sum(float(s.Area()) for s in shapes),
                "bounds_mm": bounds,
                "size_mm": [bounds[1][i] - bounds[0][i] for i in range(3)],
                "face_count": len(result["face_meshes"]),
                "edge_count": len(result["edge_meta"]),
            }
        result["checks"].update(
            passed=bool(shapes) and not failed,
            brep_valid=all(s.isValid() for s in shapes),
            error=error if failed else (None if shapes else "No active solid geometry"),
        )
    except Exception as exc:
        result["checks"].update(
            passed=False, error=f"Inspection failed: {str(exc)[:400]}"
        )
    return result


def export_document(doc, asset_loader, folder):
    result = build_document(doc, asset_loader)
    if not result["checks"]["passed"]:
        return {"files": [], "checks": result["checks"], "features": result["features"]}
    dest = Path(folder)
    dest.mkdir(parents=True, exist_ok=True)
    shapes = [p["shape"] for p in result["parts"]]
    checks = dict(result["checks"])
    try:
        cq.exporters.export(_compound(shapes), str(dest / "workspace.step"))
        step = cq.importers.importStep(str(dest / "workspace.step")).solids().vals()
        expected = result["metrics"]["volume_mm3"]
        tol = max(1e-6, expected * 1e-8)
        volume_difference = abs(sum(s.Volume() for s in step) - expected)
        step_valid = len(step) == len(shapes) and all(s.isValid() for s in step)
        geometric_difference = None
        bounds_difference = None
        # STEP can rewrite NURBS surfaces with a different numerical volume
        # integral. In that case prove coincident geometry by symmetric Boolean
        # difference at the SAME tolerance, with an independent bounds check.
        # This is deliberately not a relaxed volume threshold.
        if step_valid and volume_difference > tol:
            source = _compound(shapes)
            imported = _compound(step)
            geometric_difference = abs(source.cut(imported).Volume()) + abs(
                imported.cut(source).Volume()
            )
            bounds_difference = max(
                abs(a - b)
                for aa, bb in zip(_bounds(source), _bounds(imported))
                for a, b in zip(aa, bb)
            )
        checks["step_roundtrip"] = {
            "solid_count": len(step),
            "volume_mm3": sum(s.Volume() for s in step),
            "integrated_volume_difference_mm3": volume_difference,
            "volume_tolerance_mm3": tol,
            "symmetric_difference_mm3": geometric_difference,
            "bounds_difference_mm": bounds_difference,
            "passed": step_valid
            and (
                volume_difference <= tol
                or (
                    geometric_difference is not None
                    and geometric_difference <= tol
                    and bounds_difference <= 1e-5
                )
            ),
        }
        union = _union(shapes)
        cq.exporters.export(union, str(dest / "workspace.stl"))
        mesh = trimesh.load(str(dest / "workspace.stl"), force="mesh", process=True)
        union_volume = union.Volume()
        stl_tol = max(1e-5, union_volume * 0.01)
        bounds = result["metrics"]["bounds_mm"]
        bounds_error = max(
            abs(float(mesh.bounds[i][j]) - bounds[i][j])
            for i in range(2)
            for j in range(3)
        )
        # Curved surfaces are tessellated; allow 1% volume error, unlike exact panel meshes.
        checks["stl_roundtrip"] = {
            "watertight": bool(mesh.is_watertight),
            "winding_consistent": bool(mesh.is_winding_consistent),
            "volume_mm3": float(mesh.volume),
            "union_brep_volume_mm3": union_volume,
            "volume_tolerance_mm3": stl_tol,
            "bounds_error_mm": bounds_error,
            "bounds_tolerance_mm": 0.3,
            "representation": "Geometric union mesh; overlapping independent bodies are fused for STL only.",
            "passed": bool(
                mesh.is_watertight
                and mesh.is_winding_consistent
                and mesh.is_volume
                and abs(mesh.volume - union_volume) <= stl_tol
                and bounds_error <= 0.3
            ),
        }
        checks["passed"] = (
            checks["step_roundtrip"]["passed"] and checks["stl_roundtrip"]["passed"]
        )
        (dest / "workspace.json").write_text(
            json.dumps(doc, indent=2, allow_nan=False), encoding="utf-8"
        )
        (dest / "verification.json").write_text(
            json.dumps(checks, indent=2, allow_nan=False), encoding="utf-8"
        )
        return {
            "files": (
                [
                    "workspace.step",
                    "workspace.stl",
                    "workspace.json",
                    "verification.json",
                ]
                if checks["passed"]
                else []
            ),
            "checks": checks,
            "metrics": result["metrics"],
        }
    except Exception as exc:
        checks.update(passed=False, error=f"Export failed: {str(exc)[:400]}")
        return {"files": [], "checks": checks}
