"""Native, task-independent gear assembly preflight.

These are discrete geometry/kinematics checks. They do not simulate contact,
friction, forces or dynamics and cannot certify a working transmission.
"""

import math

from .mechanical_features import n

VECTORS = {
    "+X": (1, 0, 0),
    "-X": (-1, 0, 0),
    "+Y": (0, 1, 0),
    "-Y": (0, -1, 0),
    "+Z": (0, 0, 1),
    "-Z": (0, 0, -1),
}
SCOPE = (
    "Independent native gear bodies only; spur outlines sampled from native faces "
    "with stated deflection, exact bevel Booleans and prescribed mesh poses. "
    "Near-contact uncertainty and continuous/dynamic transmission remain unqualified."
)


def _point(params):
    return tuple(n(params, key, 0) for key in ("cx", "cy", "z"))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _rotate(shape, point, axis, degrees):
    end = tuple(x + y for x, y in zip(point, axis))
    return shape.rotate(point, end, degrees)


def mesh_relation(first, second):
    """Recognize a candidate mesh from explicit feature geometry, never IDs."""
    a, b = first["params"], second["params"]
    ua, ub = VECTORS[a.get("axis", "+Z")], VECTORS[b.get("axis", "+Z")]
    pa, pb = _point(a), _point(b)
    delta = _sub(pb, pa)
    parallel = _dot(ua, ub)
    if first["type"] == second["type"] == "spur_gear" and abs(parallel) == 1:
        axial = _dot(delta, ua)
        radial_sq = max(0, _dot(delta, delta) - axial**2)
        distance = math.sqrt(radial_sq)
        width_a = n(a, "thickness", positive=True)
        end_b = axial + parallel * n(b, "thickness", positive=True)
        overlap = min(width_a, max(axial, end_b)) - max(0, min(axial, end_b))
        expected = (a["module"] * a["teeth"] + b["module"] * b["teeth"]) / 2
        if (
            overlap <= 0
            or abs(distance - expected) > min(a["module"], b["module"]) * 0.1
        ):
            return None
        return {
            "kind": "spur",
            "ratio": -a["teeth"] / b["teeth"] * parallel,
            "centre_distance_mm": distance,
            "pitch_distance_mm": expected,
        }
    if first["type"] == second["type"] == "bevel_gear" and parallel == 0:
        if math.dist(pa, pb) > 1e-5:
            return None
        expected_a = math.degrees(math.atan(a["teeth"] / b["teeth"]))
        return {
            "kind": "bevel",
            "ratio": -a["teeth"] / b["teeth"],
            "cone_angle_error_deg": max(
                abs(a["cone_angle"] - expected_a),
                abs(b["cone_angle"] - (90 - expected_a)),
            ),
        }
    return None


def _spur_section(shape, axis):
    import cadquery as cq
    from shapely.geometry import Polygon

    axial = "XYZ".index(axis[-1])
    plane = ((1, 2), (2, 0), (0, 1))[axial]
    face = cq.Workplane(obj=shape).faces(">" + axis[-1]).val()

    def points(wire):
        vectors, _ = wire.sample(0.0001)
        if len(vectors) > 50000:
            raise ValueError("Gear outline exceeds the bounded preflight point limit")
        return [tuple(v.toTuple()[i] for i in plane) for v in vectors]

    polygon = Polygon(points(face.outerWire()), [points(w) for w in face.innerWires()])
    if not polygon.is_valid:
        raise ValueError("Native gear outline sampling did not form a valid polygon")
    bounds = shape.BoundingBox()
    return (
        polygon,
        plane,
        (getattr(bounds, "xyz"[axial] + "min"), getattr(bounds, "xyz"[axial] + "max")),
    )


def analyze_gears(document, result, *, motion_samples=16):
    active = [f for f in document.get("features", []) if not f.get("suppressed")]
    report = {
        "checked": False,
        "passed": None,
        "scope": SCOPE,
        "pairs": [],
        "errors": [],
    }
    if len(active) < 2 or not any(
        f.get("type") in ("spur_gear", "bevel_gear") for f in active
    ):
        report["reason"] = "No independent gear assembly"
        return report
    if (
        len(active) > 8
        or len(result["parts"]) != len(active)
        or any(
            f.get("type") not in ("spur_gear", "bevel_gear")
            or f.get("params", {}).get("operation", "new_body") != "new_body"
            for f in active
        )
    ):
        report["reason"] = (
            "Mixed/modified histories or assemblies over eight gears require explicit inspection"
        )
        return report
    report["checked"] = True
    report["motion_samples_per_mesh"] = motion_samples
    shapes = [p["shape"] for p in result["parts"]]
    sections = {
        i: _spur_section(shape, active[i]["params"].get("axis", "+Z"))
        for i, shape in enumerate(shapes)
        if active[i]["type"] == "spur_gear"
    }
    for i, first in enumerate(active):
        a = first["params"]
        for j in range(i + 1, len(active)):
            second = active[j]
            b = second["params"]
            pair = {"features": [first["id"], second["id"]]}
            bounds_a, bounds_b = shapes[i].BoundingBox(), shapes[j].BoundingBox()
            intersects_bounds = all(
                getattr(bounds_a, axis + "max") >= getattr(bounds_b, axis + "min")
                and getattr(bounds_b, axis + "max") >= getattr(bounds_a, axis + "min")
                for axis in "xyz"
            )
            planar = (
                i in sections and j in sections and sections[i][1] == sections[j][1]
            )
            if planar:
                polygon_a, plane, span_a = sections[i]
                polygon_b, _, span_b = sections[j]
                height = max(0, min(span_a[1], span_b[1]) - max(span_a[0], span_b[0]))
                volume = (
                    polygon_a.intersection(polygon_b).area * height if height else 0.0
                )
                threshold = max(
                    1e-5, 2 * (polygon_a.length + polygon_b.length) * 0.0001 * height
                )
                pair.update(
                    method="Native face outlines / planar intersection",
                    outline_deflection_mm=0.0001,
                    uncertainty_screen_mm3=threshold,
                )
            else:
                volume = (
                    abs(shapes[i].intersect(shapes[j]).Volume())
                    if intersects_bounds
                    else 0.0
                )
                threshold = 1e-5
                pair["method"] = "Native Boolean intersection"
            pair["rest_intersection_mm3"] = volume
            if volume > threshold:
                report["errors"].append(
                    f"{first['id']} / {second['id']}: independent gears intersect at rest ({volume:.6g} mm3); correct orientation/phase/placement"
                )
            relation = mesh_relation(first, second)
            if relation:
                pair.update(relation)
                if (
                    abs(a["module"] - b["module"])
                    > max(a["module"], b["module"]) * 1e-6
                ):
                    report["errors"].append(
                        f"{first['id']} / {second['id']}: mating modules differ"
                    )
                if (
                    abs(a.get("pressure_angle", 20) - b.get("pressure_angle", 20))
                    > 1e-6
                ):
                    report["errors"].append(
                        f"{first['id']} / {second['id']}: mating pressure angles differ"
                    )
                if relation.get("cone_angle_error_deg", 0) > 0.05:
                    report["errors"].append(
                        f"{first['id']} / {second['id']}: cone angles must equal atan(teeth ratio) and its complement"
                    )
                if volume <= threshold:
                    maximum = volume
                    minimum_gap = (
                        polygon_a.distance(polygon_b)
                        if planar
                        else shapes[i].distance(shapes[j])
                    )
                    samples = motion_samples if planar else min(motion_samples, 4)
                    pair["motion_samples"] = samples
                    for k in range(1, samples):
                        angle = 360 / a["teeth"] * k / samples
                        if planar:
                            from shapely.affinity import rotate

                            sign_a, sign_b = sum(VECTORS[a.get("axis", "+Z")]), sum(
                                VECTORS[b.get("axis", "+Z")]
                            )
                            moved_a = rotate(
                                polygon_a,
                                angle * sign_a,
                                origin=tuple(_point(a)[v] for v in plane),
                            )
                            moved_b = rotate(
                                polygon_b,
                                angle * relation["ratio"] * sign_b,
                                origin=tuple(_point(b)[v] for v in plane),
                            )
                            maximum = max(
                                maximum, moved_a.intersection(moved_b).area * height
                            )
                            minimum_gap = min(minimum_gap, moved_a.distance(moved_b))
                        else:
                            moved_a = _rotate(
                                shapes[i],
                                _point(a),
                                VECTORS[a.get("axis", "+Z")],
                                angle,
                            )
                            moved_b = _rotate(
                                shapes[j],
                                _point(b),
                                VECTORS[b.get("axis", "+Z")],
                                angle * relation["ratio"],
                            )
                            maximum = max(
                                maximum, abs(moved_a.intersect(moved_b).Volume())
                            )
                            minimum_gap = min(minimum_gap, moved_a.distance(moved_b))
                    pair["sampled_intersection_max_mm3"] = maximum
                    pair["sampled_minimum_gap_mm"] = minimum_gap
                    if maximum > threshold:
                        report["errors"].append(
                            f"{first['id']} / {second['id']}: prescribed mesh motion interferes ({maximum:.6g} mm3 at sampled poses); correct tooth phase or clearance"
                        )
            report["pairs"].append(pair)
    report["passed"] = not report["errors"]
    return report
