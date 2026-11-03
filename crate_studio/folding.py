"""Editable rigid-panel mechanisms with real hinge barrels and removable pins.

Miura coordinates follow Schenk & Guest (2013), doi:10.1073/pnas.1217998110.
Other families are explicitly generated hinge trees, not a general origami solver.
Facet surfaces are offset from their ideal crease planes; clearances are checked
on the actual finite-thickness BREP, not inferred from an ideal animation.
"""

from functools import lru_cache
import itertools
import json
import math

import cadquery as cq
import numpy as np
from OCP.gp import gp_Trsf
from shapely.geometry import Polygon

FAMILIES = ("miura", "concertina", "radial_fan", "triangle_strip", "cube_net")
DEFAULT_LIMITS = dict(
    miura=65, concertina=110, radial_fan=55, triangle_strip=70, cube_net=90
)
ABSOLUTE_LIMITS = dict(
    miura=88, concertina=160, radial_fan=120, triangle_strip=140, cube_net=90
)
DEFAULTS = dict(
    family="miura",
    columns=3,
    rows=3,
    count=8,
    panel_width=40.0,
    panel_height=44.0,
    sector_angle=60.0,
    thickness=1.6,
    pin_diameter=2.0,
    radial_clearance=0.25,
    axial_clearance=0.35,
    hinge_radius=2.2,
    panel_inset=5.0,
    fold_angle=0.0,
)


def specification(raw):
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
        raise ValueError("Unsupported folding parameters")
    p = {**DEFAULTS, **raw}
    if p["family"] not in FAMILIES:
        raise ValueError("Unsupported folding family")
    for key in ("columns", "rows", "count"):
        if type(p[key]) is not int or not 2 <= p[key] <= (4 if key != "count" else 12):
            raise ValueError(
                f"{key} must be an integer from 2 to {4 if key != 'count' else 12}"
            )
    for key in set(DEFAULTS) - {"family", "columns", "rows", "count"}:
        value = p[key]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{key} must be finite numeric data")
        p[key] = float(value)
    for key in ("panel_width", "panel_height"):
        if not 24 <= p[key] <= 70:
            raise ValueError(f"{key} must be from 24 to 70 mm for this hinge system")
    if not 35 <= p["sector_angle"] <= 80:
        raise ValueError("Miura sector angle must be from 35 to 80 degrees")
    if not 0.8 <= p["thickness"] <= 4:
        raise ValueError("Panel thickness must be from 0.8 to 4 mm")
    if not 1.6 <= p["pin_diameter"] <= 4:
        raise ValueError("Pin diameter must be from 1.6 to 4 mm")
    if (
        not 0.15 <= p["radial_clearance"] <= 0.6
        or not 0.2 <= p["axial_clearance"] <= 0.8
    ):
        raise ValueError(
            "Radial clearance must be 0.15–0.6 mm and axial clearance 0.2–0.8 mm"
        )
    hole_radius = p["pin_diameter"] / 2 + p["radial_clearance"]
    if not hole_radius + 0.8 <= p["hinge_radius"] <= 5:
        raise ValueError(
            "Hinge barrel needs at least 0.8 mm wall around its clearance bore"
        )
    if p["thickness"] > 2 * p["hinge_radius"] - 0.5:
        raise ValueError("Panel thickness exceeds the hinge system envelope")
    if not p["hinge_radius"] + 0.3 <= p["panel_inset"] <= 8:
        raise ValueError("Panel inset must exceed the barrel radius by at least 0.3 mm")
    if not 0 <= p["fold_angle"] <= ABSOLUTE_LIMITS[p["family"]]:
        raise ValueError("Preview fold angle is outside the family's supported domain")
    return p


def _ccw(points):
    a = np.asarray(points)
    area = np.sum(a[:, 0] * np.roll(a[:, 1], -1) - a[:, 1] * np.roll(a[:, 0], -1))
    return points if area > 0 else list(reversed(points))


def pattern(p):
    """Return one connected flat crease graph; coordinates describe hinge axes."""
    p = specification(p)
    family, w, h = p["family"], p["panel_width"], p["panel_height"]
    polygons = []
    if family == "miura":
        offset, spacing = h * math.cos(math.radians(p["sector_angle"])), h * math.sin(
            math.radians(p["sector_angle"])
        )
        for j in range(p["rows"]):
            for i in range(p["columns"]):
                polygons.append(
                    [
                        (ii * w + (jj % 2) * offset, jj * spacing)
                        for ii, jj in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
                    ]
                )
    elif family == "concertina":
        polygons = [
            [(i * w, 0), ((i + 1) * w, 0), ((i + 1) * w, h), (i * w, h)]
            for i in range(p["count"])
        ]
    elif family == "triangle_strip":
        vertices = [(i * w / 2, (i % 2) * h) for i in range(p["count"] + 2)]
        polygons = [_ccw(vertices[i : i + 3]) for i in range(p["count"])]
    elif family == "radial_fan":
        # An open annular half-fan. No unmodeled seam/closed-vertex constraint.
        inner, outer = w, w + h
        for i in range(p["count"]):
            a, b = math.pi * i / p["count"], math.pi * (i + 1) / p["count"]
            polygons.append(
                [
                    (r * math.cos(t), r * math.sin(t))
                    for r, t in ((inner, a), (outer, a), (outer, b), (inner, b))
                ]
            )
    else:
        polygons = [
            [
                (x * w, y * w),
                ((x + 1) * w, y * w),
                ((x + 1) * w, (y + 1) * w),
                (x * w, (y + 1) * w),
            ]
            for x, y in ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0), (0, 2))
        ]
    vertices, lookup, faces = [], {}, []
    for poly in polygons:
        face = []
        for point in _ccw(poly):
            key = tuple(round(float(v), 9) for v in point)
            if key not in lookup:
                lookup[key] = len(vertices)
                vertices.append([float(point[0]), float(point[1]), 0.0])
            face.append(lookup[key])
        faces.append(face)
    owners = {}
    for i, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            owners.setdefault(tuple(sorted((a, b))), []).append(i)
    if any(len(value) > 2 for value in owners.values()):
        raise ValueError("Non-manifold crease graph")
    hinges = [
        dict(edge=list(edge), faces=adjacent)
        for edge, adjacent in owners.items()
        if len(adjacent) == 2
    ]
    # Stable, simple numbering independent of boundary edge count.
    for i, hinge in enumerate(hinges):
        hinge["id"] = f"hinge_{i+1:03d}"
    return dict(
        vertices=vertices,
        faces=faces,
        hinges=hinges,
        boundary_edges=[
            list(edge) for edge, adjacent in owners.items() if len(adjacent) == 1
        ],
    )


def _rotation(axis, angle):
    a = np.asarray(axis, dtype=float)
    a /= np.linalg.norm(a)
    x, y, z = a
    c = math.cos(angle)
    s = math.sin(angle)
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return c * np.eye(3) + (1 - c) * np.outer(a, a) + s * cross


def _about(a, b, angle):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    value = np.eye(4)
    value[:3, :3] = _rotation(b - a, angle)
    value[:3, 3] = a - value[:3, :3] @ a
    return value


def _basis(points):
    a, b, c = np.asarray(points[:3])
    x = b - a
    x /= np.linalg.norm(x)
    z = np.cross(x, c - a)
    z /= np.linalg.norm(z)
    y = np.cross(z, x)
    return np.column_stack((x, y, z))


def transforms(p, graph, angle):
    p = specification({**p, "fold_angle": angle})
    vertices = np.asarray(graph["vertices"], dtype=float)
    flat = vertices.copy()
    flat[:, 2] = p["hinge_radius"]
    faces = graph["faces"]
    if p["family"] == "miura":
        theta, gamma = math.radians(angle), math.radians(p["sector_angle"])
        q = math.sqrt(1 - math.sin(theta) ** 2 * math.sin(gamma) ** 2)
        L = p["panel_width"] * q
        S = p["panel_height"] * math.sin(gamma) * math.cos(theta) / q
        V = p["panel_height"] * math.cos(gamma) / q
        H = p["panel_width"] * math.sin(theta) * math.sin(gamma)
        folded = []
        flat_offset = p["panel_height"] * math.cos(gamma)
        flat_spacing = p["panel_height"] * math.sin(gamma)
        for x, y, z in vertices:
            j = round(y / flat_spacing)
            i = round((x - (j % 2) * flat_offset) / p["panel_width"])
            folded.append([i * L + (j % 2) * V, j * S, (i % 2) * H + p["hinge_radius"]])
        folded = np.asarray(folded)
        poses = []
        for face in faces:
            original = flat[face]
            current = folded[face]
            r = _basis(current) @ _basis(original).T
            m = np.eye(4)
            m[:3, :3] = r
            m[:3, 3] = current[0] - r @ original[0]
            poses.append(m)
        return poses
    adjacency = {i: [] for i in range(len(faces))}
    for i, hinge in enumerate(graph["hinges"]):
        a, b = hinge["faces"]
        adjacency[a].append((b, i))
        adjacency[b].append((a, i))
    poses = {0: np.eye(4)}
    queue = [0]
    while queue:
        parent = queue.pop(0)
        for child, index in adjacency[parent]:
            if child in poses:
                continue
            hinge = graph["hinges"][index]
            a, b = flat[hinge["edge"]]
            centroid = flat[faces[child]].mean(axis=0)
            side = np.sign(np.cross(b - a, centroid - a)[2])
            if p["family"] == "cube_net":
                drive = (
                    max(0.0, (angle - 60) * 3) if child == 5 else min(90.0, angle * 1.5)
                )
            else:
                drive = angle * ((-1) ** index)
            poses[child] = poses[parent] @ _about(a, b, math.radians(side * drive))
            queue.append(child)
    if len(poses) != len(faces) or len(graph["hinges"]) != len(faces) - 1:
        raise ValueError("This family requires a connected hinge tree")
    return [poses[i] for i in range(len(faces))]


def moved(shape, matrix):
    matrix = np.asarray(matrix)
    t = gp_Trsf()
    t.SetValues(*[float(v) for v in matrix[:3, :].ravel()])
    return shape.moved(cq.Location(t))


def _prism(points, height):
    return (
        cq.Workplane("XY")
        .polyline([tuple(x) for x in points])
        .close()
        .extrude(height)
        .val()
    )


def _native_bounds(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, box, False, False)
    values = box.Get()
    return np.asarray(values[:3]), np.asarray(values[3:])


@lru_cache(maxsize=12)
def _flat_cached(key):
    p = json.loads(key)
    graph = pattern(p)
    vertices = np.asarray(graph["vertices"])
    r, t, inset = p["hinge_radius"], p["thickness"], p["panel_inset"]
    panels = []
    for index, face in enumerate(graph["faces"]):
        polygon = Polygon(vertices[face, :2]).buffer(-inset, join_style="mitre")
        if polygon.is_empty or polygon.geom_type != "Polygon" or polygon.area < 15:
            raise ValueError(
                "Panel inset removes a facet; increase facet dimensions or reduce the hinge size"
            )
        panels.append(_prism(list(polygon.exterior.coords)[:-1], t))
    additions = {i: [] for i in range(len(panels))}
    bores = {i: [] for i in range(len(panels))}
    pins = []
    joints = []
    hole = p["pin_diameter"] / 2 + p["radial_clearance"]
    for hinge in graph["hinges"]:
        a, b = vertices[hinge["edge"]]
        a = a.copy()
        b = b.copy()
        a[2] = b[2] = r
        axis = b - a
        length = float(np.linalg.norm(axis))
        axis /= length
        pad = max(2 * r + p["axial_clearance"], inset * 2.5)
        active = length - 2 * pad
        if active < 6:
            raise ValueError(
                f"{hinge['id']} is too short for three printable knuckles; increase facet dimensions"
            )
        segment = active / 3
        gap = p["axial_clearance"]
        for number in range(3):
            owner = hinge["faces"][number % 2]
            start = pad + number * segment + gap / 2
            end = pad + (number + 1) * segment - gap / 2
            origin = a + axis * start
            barrel = cq.Solid.makeCylinder(
                r, end - start, cq.Vector(*origin), cq.Vector(*axis)
            )
            midpoint = (a + b) / 2
            center = vertices[graph["faces"][owner]].mean(axis=0)
            normal = np.array([-axis[1], axis[0], 0.0])
            if np.dot(center - midpoint, normal) < 0:
                normal = -normal
            corners = [
                a + axis * start,
                a + axis * end,
                a + axis * end + normal * (inset + 1.5),
                a + axis * start + normal * (inset + 1.5),
            ]
            tab = _prism([q[:2] for q in corners], t)
            additions[owner].extend([barrel, tab])
        tool = cq.Solid.makeCylinder(
            hole, active + 2, cq.Vector(*(a + axis * (pad - 1))), cq.Vector(*axis)
        )
        for owner in hinge["faces"]:
            bores[owner].append(tool)
        pin_start = a + axis * (pad - gap)
        pin_length = active + 2 * gap
        pin = cq.Solid.makeCylinder(
            p["pin_diameter"] / 2, pin_length, cq.Vector(*pin_start), cq.Vector(*axis)
        )
        head = cq.Solid.makeCylinder(
            hole + 0.55, 1.2, cq.Vector(*(pin_start - axis * 1.2)), cq.Vector(*axis)
        )
        pin = pin.fuse(head).clean()
        pins.append(
            dict(
                id="pin_" + hinge["id"],
                name="Pin " + hinge["id"],
                shape=pin,
                face=hinge["faces"][0],
                joint_faces=hinge["faces"],
                kind="pin",
                axis=axis.tolist(),
                start=pin_start.tolist(),
                length_mm=pin_length + 1.2,
            )
        )
        joints.append(
            {
                **hinge,
                "axis_flat": axis.tolist(),
                "axis_start_mm": a.tolist(),
                "axis_end_mm": b.tolist(),
                "pin_diameter_mm": p["pin_diameter"],
                "bore_diameter_mm": 2 * hole,
                "barrel_diameter_mm": 2 * r,
                "axial_gap_mm": gap,
                "pin_length_mm": pin_length + 1.2,
            }
        )
    parts = []
    for i, shape in enumerate(panels):
        if additions[i]:
            shape = shape.fuse(*additions[i]).clean()
        if bores[i]:
            shape = shape.cut(*bores[i]).clean()
        if not shape.isValid() or len(shape.Solids()) != 1:
            raise ValueError(
                f"Panel {i+1} has disconnected hinge hardware or invalid geometry"
            )
        parts.append(
            dict(
                id=f"panel_{i+1:03d}",
                name=f"Panel {i+1}",
                shape=shape,
                face=i,
                kind="panel",
            )
        )
    parts.extend(pins)
    if len(parts) > 50:
        raise ValueError("Folding assembly exceeds 50 independent parts")
    return dict(spec=p, graph=graph, parts=parts, joints=joints)


def flat_assembly(raw):
    p = specification(raw)
    p["fold_angle"] = 0.0
    return _flat_cached(json.dumps(p, sort_keys=True))


def assembly(raw, angle=None):
    p = specification(raw)
    value = flat_assembly(p)
    poses = transforms(p, value["graph"], p["fold_angle"] if angle is None else angle)
    parts = [
        {**part, "shape": moved(part["shape"], poses[part["face"]])}
        for part in value["parts"]
    ]
    return {**value, "parts": parts, "poses": [m.tolist() for m in poses]}


def closure(graph, poses, hinge_height):
    vertices = np.asarray(graph["vertices"], dtype=float)
    vertices[:, 2] = hinge_height
    error = 0.0
    for hinge in graph["hinges"]:
        points = np.column_stack((vertices[hinge["edge"]], np.ones(2)))
        a, b = [(np.asarray(poses[i]) @ points.T).T[:, :3] for i in hinge["faces"]]
        error = max(error, float(np.max(np.linalg.norm(a - b, axis=1))))
    return error


def collisions(
    parts, tolerance_mm3=1e-5, measure_clearance=False, pair_cache=None, details=False
):
    bounds = [_native_bounds(p["shape"]) for p in parts]
    found = []
    tested = 0
    minimum = float("inf")
    closest = None
    native_distances = 0
    reused = 0
    for i, j in itertools.combinations(range(len(parts)), 2):
        a, b = parts[i], parts[j]
        invariant = (
            a.get("face") is not None and a.get("face") == b.get("face")
        ) or any(
            pin.get("kind") == "pin"
            and panel.get("kind") == "panel"
            and panel.get("face") in pin.get("joint_faces", [])
            for pin, panel in ((a, b), (b, a))
        )
        key = (a["id"], b["id"])
        if (
            invariant
            and pair_cache is not None
            and not measure_clearance
            and not details
            and key in pair_cache
        ):
            volume = pair_cache[key]
            reused += 1
            if volume > tolerance_mm3:
                found.append(dict(parts=list(key), volume_mm3=volume))
            continue
        lo = np.maximum(bounds[i][0], bounds[j][0])
        hi = np.minimum(bounds[i][1], bounds[j][1])
        if measure_clearance:
            lower = float(np.linalg.norm(np.maximum(lo - hi, 0)))
            if lower > minimum + 1e-7:
                continue
            distance = parts[i]["shape"].distance(parts[j]["shape"])
            native_distances += 1
            if distance < minimum:
                minimum = distance
                closest = [parts[i]["id"], parts[j]["id"]]
            if distance > 1e-7:
                continue
        if np.any(hi - lo <= 1e-7):
            if invariant and pair_cache is not None:
                pair_cache[key] = 0.0
            continue
        tested += 1
        intersection = parts[i]["shape"].intersect(parts[j]["shape"])
        volume = abs(intersection.Volume())
        if invariant and pair_cache is not None:
            pair_cache[key] = volume
        if volume > tolerance_mm3:
            record = dict(parts=[parts[i]["id"], parts[j]["id"]], volume_mm3=volume)
            if details:
                record["bounds_mm"] = [v.tolist() for v in _native_bounds(intersection)]
            found.append(record)
    return dict(
        overlaps=found,
        native_pair_checks=tested,
        reused_pair_checks=reused,
        native_distance_checks=native_distances,
        minimum_clearance_mm=None if not math.isfinite(minimum) else minimum,
        closest_pair=closest,
        tolerance_mm3=tolerance_mm3,
    )


def describe(raw):
    p = specification(raw)
    value = flat_assembly(p)
    return {
        "family": p["family"],
        "panel_count": len(value["graph"]["faces"]),
        "hinge_count": len(value["joints"]),
        "part_count": len(value["parts"]),
        "joints": value["joints"],
        "spec": p,
        "scope": "Rigid panels, explicit revolute axes, real barrels and removable headed pins. Native solid interference checks are sampled. No friction, force, fatigue, pin retention or physical validation is implied.",
    }
