"""Constructive ZERO-THICKNESS four-state box feasibility baseline.

One fixed 200 mm sheet and shared facet/crease graph. Sequential corner tucks
align the upper wall-band axes before the rectangular mode folds its taller
wall bands down. A bounded azimuth search selects that compatible corner pose.

The original four-slit baseline is retained separately. The current candidate
is uncut; neither version is a claimed novel crease pattern.
It is NOT a printable mechanism: thickness, layer stacking, hinges, latches,
forces, self-contact and released-state stability are not qualified here.
No model/API calls. Existing production folding families remain unchanged.
"""

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import polygonize, unary_union


@dataclass(frozen=True)
class Target:
    name: str
    length: float
    width: float


TARGETS = (
    Target("small", 70, 70),
    Target("medium", 100, 100),
    Target("large", 130, 130),
    Target("rectangular", 130, 70),
)
SHEET = 200.0
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def dimensions(target, sheet=SHEET):
    if not 0 < target.width <= target.length < sheet:
        raise ValueError("Require 0 < width <= length < sheet")
    a, b = (sheet - target.length) / 2, (sheet - target.width) / 2
    if b > 2 * a:
        raise ValueError("The folded tall-wall band would project below the floor")
    return a, b


def pattern(targets=TARGETS, sheet=SHEET, release_slits=False):
    half = sheet / 2
    border = box(-half, -half, half, half)
    lines = [border.exterior]
    cuts = []
    for target in targets:
        a, b = dimensions(target, sheet)
        for sx in (-1, 1):
            lines.append(
                LineString(
                    [(sx * target.length / 2, -half), (sx * target.length / 2, half)]
                )
            )
        for sy in (-1, 1):
            lines.append(
                LineString(
                    [(-half, sy * target.width / 2), (half, sy * target.width / 2)]
                )
            )
        for sx in (-1, 1):
            for sy in (-1, 1):
                corner = (sx * target.length / 2, sy * target.width / 2)
                lines.append(
                    LineString([corner, (corner[0] + sx * a, corner[1] + sy * a)])
                )
                if b > a + 1e-9:
                    cut = LineString(
                        [
                            (corner[0], sy * (target.width / 2 + a)),
                            (corner[0], sy * half),
                        ]
                    )
                    cuts.append(cut)
                    lines.append(cut)
        if b > a + 1e-9:
            for sy in (-1, 1):
                lines.append(
                    LineString(
                        [
                            (-half, sy * (target.width / 2 + a)),
                            (half, sy * (target.width / 2 + a)),
                        ]
                    )
                )
    # Every state must retain a continuous floor, including after the permanent
    # slits for other states have been introduced.
    for target in targets:
        floor = box(
            -target.length / 2, -target.width / 2, target.length / 2, target.width / 2
        ).buffer(-1e-7)
        if any(cut.intersects(floor) for cut in (cuts if release_slits else [])):
            raise ValueError(
                "A permanent release slit crosses another state's usable floor"
            )
    polygons = sorted(
        polygonize(unary_union(lines)), key=lambda p: (p.centroid.y, p.centroid.x)
    )
    faces = [
        np.asarray(orient(p, sign=1.0).exterior.coords[:-1], dtype=float)
        for p in polygons
        if p.area > 1e-8
    ]
    owners = {}
    for index, face in enumerate(faces):
        for p, q in zip(face, np.roll(face, -1, axis=0)):
            key = tuple(sorted((tuple(np.round(p, 9)), tuple(np.round(q, 9)))))
            owners.setdefault(key, []).append(index)
    edges = []
    for points, adjacent in owners.items():
        edge = LineString(points)
        cut = release_slits and any(
            edge.difference(line.buffer(1e-7)).length < 1e-7 for line in cuts
        )
        edges.append(dict(points=points, faces=adjacent, cut=cut))
    adjacency = {i: [] for i in range(len(faces))}
    for edge in edges:
        if len(edge["faces"]) == 2 and not edge["cut"]:
            a, b = edge["faces"]
            adjacency[a].append(b)
            adjacency[b].append(a)
    seen = {0}
    queue = [0]
    while queue:
        for child in adjacency[queue.pop()]:
            if child not in seen:
                seen.add(child)
                queue.append(child)
    if len(seen) != len(faces):
        raise ValueError("Sheet is disconnected after the release cuts")
    return dict(
        faces=faces, edges=edges, cuts=cuts if release_slits else [], sheet=sheet
    )


def _kind(face, target, sheet):
    x, y = face.mean(axis=0)
    u = abs(x) - target.length / 2
    v = abs(y) - target.width / 2
    a, b = dimensions(target, sheet)
    if u < 1e-8 and v < 1e-8:
        return "floor"
    if v < 1e-8:
        return "wall_x"
    if u < 1e-8:
        return "wall_y_upper" if b > a + 1e-8 and v > a + 1e-8 else "wall_y"
    if b > a + 1e-8 and v > a + 1e-8:
        return "corner_upper"
    return "corner_u" if u > v else "corner_v"


def mapped(
    face,
    target,
    wall_angle,
    band_angle=0.0,
    sheet=SHEET,
    gussets=(45.0, 45.0, 45.0, 45.0),
):
    """One face's continuous isometry; cuts deliberately have separate banks."""
    if not 0 <= wall_angle <= 90 or not 0 <= band_angle <= 180:
        raise ValueError("Angles outside this constructive path")
    if band_angle and wall_angle != 90:
        raise ValueError("Finish wall folding before folding the tall wall band")
    a, b = dimensions(target, sheet)
    kind = _kind(face, target, sheet)
    theta, phi = map(math.radians, (wall_angle, band_angle))
    c, s = math.cos(theta), math.sin(theta)
    # Solve the shared corner diagonal from the three original edge lengths.
    # The positive branch keeps the gusset outside the usable rectangular floor.
    q = (c + math.sqrt(2) * s * s) / (1 + s * s)
    z = s * (2 - math.sqrt(2) * c) / (1 + s * s)
    A = np.array([c, 0, s])
    B = np.array([0, c, s])
    C = np.array([q, q, z])
    D = np.array([2**-0.5, 2**-0.5, 0.0])
    sx, sy = np.sign(face.mean(axis=0))
    points = []
    if kind.startswith("corner"):
        corner_index = {(1, 1): 0, (-1, 1): 1, (-1, -1): 2, (1, -1): 3}[
            int(sx), int(sy)
        ]
        azimuth = math.radians(gussets[corner_index])
        if wall_angle != 90 and gussets[corner_index] != 45:
            raise ValueError("Corner tucks require upright walls")
        if wall_angle == 90:
            D = np.array([math.cos(azimuth), math.sin(azimuth), 0.0])
            C = D + np.array([0.0, 0.0, 1.0])
    for x, y in face:
        u, v = abs(x) - target.length / 2, abs(y) - target.width / 2
        if kind == "floor":
            point = [x, y, 0.0]
        elif kind == "wall_x":
            point = [sx * (target.length / 2 + u * c), y, u * s]
        elif kind == "wall_y":
            point = [x, sy * (target.width / 2 + v * c), v * s]
        elif kind == "wall_y_upper":
            if not band_angle:
                point = [x, sy * (target.width / 2 + v * c), v * s]
            else:
                point = [
                    x,
                    sy * (target.width / 2 + (v - a) * math.sin(phi)),
                    a + (v - a) * math.cos(phi),
                ]
        else:
            if kind == "corner_u":
                local = (u - v) * A + v * C
            elif kind == "corner_v":
                local = (v - u) * B + u * C
            elif not band_angle:
                local = v * B + u * (C - B)
            else:
                rotated_z = np.cross(D, [0.0, 0.0, 1.0]) * math.sin(phi) + np.array(
                    [0.0, 0.0, math.cos(phi)]
                )
                local = np.array([0.0, 0.0, a]) + u * D + (v - a) * rotated_z
            point = [
                sx * (target.length / 2 + local[0]),
                sy * (target.width / 2 + local[1]),
                local[2],
            ]
        points.append(point)
    return np.asarray(points)


def pose_checks(
    graph,
    target,
    wall_angle,
    band_angle=0.0,
    respect_cuts=True,
    gussets=(45.0, 45.0, 45.0, 45.0),
):
    moved = [
        mapped(face, target, wall_angle, band_angle, graph["sheet"], gussets)
        for face in graph["faces"]
    ]
    isometry = 0.0
    closure = 0.0
    planarity = 0.0
    for flat, pose in zip(graph["faces"], moved):
        before = np.linalg.norm(flat[:, None, :] - flat[None, :, :], axis=-1)
        after = np.linalg.norm(pose[:, None, :] - pose[None, :, :], axis=-1)
        isometry = max(isometry, float(np.max(np.abs(before - after))))
        singular = np.linalg.svd(pose - pose.mean(axis=0), compute_uv=False)
        if len(singular) == 3:
            planarity = max(planarity, float(singular[-1]))
    for edge in graph["edges"]:
        if len(edge["faces"]) != 2 or respect_cuts and edge["cut"]:
            continue
        banks = []
        for i in edge["faces"]:
            face = graph["faces"][i]
            banks.append(
                np.array(
                    [
                        moved[i][
                            np.argmin(np.linalg.norm(face - np.asarray(point), axis=1))
                        ]
                        for point in edge["points"]
                    ]
                )
            )
        closure = max(
            closure, float(np.max(np.linalg.norm(banks[0] - banks[1], axis=1)))
        )
    return dict(
        max_facet_distance_error_mm=isometry,
        max_panel_planarity_error_mm=planarity,
        max_uncut_edge_closure_error_mm=closure,
        min_surface_z_mm=float(min(p[:, 2].min() for p in moved)),
    )


def solve_tuck_azimuth(graph):
    """Bounded design search: avoid tearing the common upper-band hinge loops."""
    trials = []
    for angle in np.linspace(45, 180, 136):
        check = pose_checks(graph, TARGETS[-1], 90, 90, gussets=(float(angle),) * 4)
        trials.append(
            dict(
                angle_deg=float(angle),
                closure_error_mm=check["max_uncut_edge_closure_error_mm"],
            )
        )
    best = min(trials, key=lambda t: t["closure_error_mm"])
    return dict(
        best=best,
        candidates=trials,
        scope="Bounded corner-axis alignment search inside this authored construction; not new-pattern discovery",
    )


def prescribed_path(target, samples=91, azimuth=180.0):
    a, b = dimensions(target)
    path = [(float(angle), 0.0, (45.0,) * 4) for angle in np.linspace(0, 90, samples)]
    current = [45.0] * 4
    for corner in range(4):
        for angle in np.linspace(45, azimuth, samples)[1:]:
            current[corner] = float(angle)
            path.append((90.0, 0.0, tuple(current)))
    if b > a + 1e-8:
        path.extend(
            (90.0, float(angle), tuple(current))
            for angle in np.linspace(0, 180, samples)[1:]
        )
    return path


def surface_crossings(polygons, tolerance=1e-7):
    """Proper transverse intersection of convex zero-thickness faces.

    Coplanar stacked paper contact is allowed here, not finite-solid clearance.
    Each polygon must straddle the other plane and share a positive-length
    interior intersection interval. Edge/vertex contacts are not crossings.
    """
    lows = np.array([p.min(axis=0) for p in polygons])
    highs = np.array([p.max(axis=0) for p in polygons])
    centers = [p.mean(axis=0) for p in polygons]
    normals = [
        np.linalg.svd(p - p.mean(axis=0), full_matrices=False)[2][-1] for p in polygons
    ]
    candidates = np.argwhere(
        np.triu(
            np.all(
                np.minimum(highs[:, None, :], highs[None, :, :])
                - np.maximum(lows[:, None, :], lows[None, :, :])
                >= -tolerance,
                axis=-1,
            ),
            1,
        )
    )

    def section(poly, distances, direction):
        points = []
        for i, p in enumerate(poly):
            j = (i + 1) % len(poly)
            a, b = distances[i], distances[j]
            if abs(a) <= tolerance:
                points.append(p)
            if a * b < 0:
                points.append(p + (poly[j] - p) * a / (a - b))
        projected = np.array(points) @ direction
        return float(projected.min()), float(projected.max())

    found = []
    for i, j in candidates:
        direction = np.cross(normals[i], normals[j])
        length = np.linalg.norm(direction)
        if length < 1e-9:
            continue
        di = (polygons[i] - centers[j]) @ normals[j]
        dj = (polygons[j] - centers[i]) @ normals[i]
        if not (
            di.min() < -tolerance
            and di.max() > tolerance
            and dj.min() < -tolerance
            and dj.max() > tolerance
        ):
            continue
        direction /= length
        ai, bi = section(polygons[i], di, direction)
        aj, bj = section(polygons[j], dj, direction)
        if min(bi, bj) - max(ai, aj) > tolerance:
            found.append([int(i), int(j)])
    return found


def audit(graph, samples=31):
    rows = []
    search = solve_tuck_azimuth(graph)
    for target in TARGETS:
        a, b = dimensions(target, graph["sheet"])
        path = prescribed_path(target, samples, search["best"]["angle_deg"])
        checks = [
            pose_checks(graph, target, wall, band, gussets=angles)
            for wall, band, angles in path
        ]
        crossings = []
        for index, (wall, band, angles) in enumerate(path):
            found = surface_crossings(
                [
                    mapped(face, target, wall, band, graph["sheet"], angles)
                    for face in graph["faces"]
                ]
            )
            if found:
                crossings.append(
                    dict(
                        pose=index,
                        pairs=found,
                        wall_angle=wall,
                        band_angle=band,
                        gussets=angles,
                    )
                )
        maxima = {
            key: max(row[key] for row in checks)
            for key in checks[0]
            if key.startswith("max_")
        }
        minima = min(row["min_surface_z_mm"] for row in checks)
        floor = unary_union(
            [
                Polygon(face)
                for face in graph["faces"]
                if _kind(face, target, graph["sheet"]) == "floor"
            ]
        )
        expected = box(
            -target.length / 2, -target.width / 2, target.length / 2, target.width / 2
        )
        floor_difference = float(floor.symmetric_difference(expected).area)
        maximum_z = max(
            mapped(
                face,
                target,
                90,
                180 if b > a + 1e-8 else 0,
                graph["sheet"],
                (search["best"]["angle_deg"],) * 4,
            )[:, 2].max()
            for face in graph["faces"]
        )
        row = dict(
            name=target.name,
            internal_floor_mm=[target.length, target.width],
            height_mm=a,
            floor_area_mm2=floor.area,
            floor_region_error_mm2=floor_difference,
            poses=len(path),
            minimum_surface_z_mm=minima,
            final_rim_height_mm=float(maximum_z),
            **maxima,
            sampled_surface_crossings=crossings,
            ideal_isometry_and_connections_passed=max(maxima.values()) < 1e-7
            and minima >= -1e-7
            and floor_difference < 1e-7,
        )
        row["ideal_sampled_path_passed"] = (
            row["ideal_isometry_and_connections_passed"] and not crossings
        )
        rows.append(row)
    return dict(
        format="forma-adjustable-box-ideal-study/v2",
        implementation_sha256=IMPLEMENTATION_SHA256,
        sheet_mm=[graph["sheet"], graph["sheet"]],
        facets=len(graph["faces"]),
        release_slits=len(graph["cuts"]),
        total_slit_length_mm=sum(c.length for c in graph["cuts"]),
        states=rows,
        corner_alignment_search=search,
        finite_thickness_qualified=False,
        collision_qualified=False,
        locks_implemented=False,
        physical_stability_qualified=False,
        print_export_available=False,
        discovery_claim=False,
        scope="Constructive uncut zero-thickness baseline; one fixed sheet/facet graph across four modes. Sequential corner tucks precede wall-band folding. Facet rigidity, edge closure, sampled transverse surface crossings and floor geometry checked. Coplanar layer stacking is allowed in this ideal model and requires finite-thickness redesign. No forces/latches/physical proof or novelty claim.",
    )


def write_artifacts(folder, samples=31):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    graph = pattern()
    result = audit(graph, samples)
    result["negative_control_uncut_rectangle_mm"] = pose_checks(
        graph, TARGETS[-1], 90, 90, respect_cuts=False
    )["max_uncut_edge_closure_error_mm"]
    (folder / "verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    source = dict(
        sheet_mm=graph["sheet"],
        facets=[p.tolist() for p in graph["faces"]],
        edges=graph["edges"],
    )
    (folder / "shared-sheet.json").write_text(
        json.dumps(source, indent=2), encoding="utf-8"
    )
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-115 -130 230 260" width="230mm" height="260mm">',
        '<rect x="-115" y="-130" width="230" height="260" fill="white"/>',
        '<text x="-105" y="-117" font-size="4" font-family="sans-serif">IDEAL FOUR-STATE SHEET / NOT A PRINTABLE MECHANISM</text>',
    ]
    for edge in graph["edges"]:
        (x, y), (xx, yy) = edge["points"]
        color = (
            "#bb4f3e"
            if edge["cut"]
            else "#354f62" if len(edge["faces"]) == 1 else "#9eafb9"
        )
        svg.append(
            f'<path d="M{x},{-y} L{xx},{-yy}" stroke="{color}" stroke-width="{.8 if edge["cut"] else .25}" fill="none"/>'
        )
    svg.append(
        '<text x="-105" y="112" font-size="3.6" font-family="sans-serif">Uncut candidate crease network; four ordered corner-tuck stages.</text>'
    )
    svg.append(
        '<text x="-105" y="120" font-size="3.6" font-family="sans-serif">Thickness, layer stacking, hinge materials and locks remain unresolved.</text></svg>'
    )
    (folder / "crease-network.svg").write_text("\n".join(svg), encoding="utf-8")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(15, 11), facecolor="#f5f3ed")
    for i, target in enumerate(TARGETS):
        ax = fig.add_subplot(2, 2, i + 1, projection="3d")
        ax.set_facecolor("#f5f3ed")
        a, b = dimensions(target)
        polys = []
        colors = []
        for face in graph["faces"]:
            polys.append(
                mapped(
                    face,
                    target,
                    90,
                    180 if b > a + 1e-8 else 0,
                    gussets=(result["corner_alignment_search"]["best"]["angle_deg"],)
                    * 4,
                )
            )
            kind = _kind(face, target, graph["sheet"])
            colors.append(
                "#d4bb8c"
                if kind == "floor"
                else "#7099aa" if kind.startswith("wall") else "#8fb5a5"
            )
        ax.add_collection3d(
            Poly3DCollection(
                polys, facecolors=colors, edgecolors="#536b76", linewidths=0.15, alpha=1
            )
        )
        ax.set(xlim=(-120, 120), ylim=(-120, 120), zlim=(-10, 110))
        ax.set_box_aspect([2, 2, 1])
        ax.view_init(elev=36, azim=-55)
        ax.set_axis_off()
        ax.set_title(
            f"{target.name.title()}: {target.length:g} × {target.width:g} × {a:g} mm",
            fontsize=14,
        )
    fig.suptitle("One fixed sheet / four ideal open-box configurations", fontsize=20)
    fig.text(
        0.5,
        0.035,
        "Ideal uncut sheet · zero thickness and stacked layers · latches and printable joints still required",
        ha="center",
        fontsize=11,
    )
    fig.savefig(folder / "four-states.png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=31)
    args = parser.parse_args()
    if not 5 <= args.samples <= 721:
        parser.error("samples must be from 5 to 721")
    print(json.dumps(write_artifacts(args.output, args.samples), indent=2))
