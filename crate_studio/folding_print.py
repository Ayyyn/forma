"""Verified component plates, fit coupon and assembly maps for rigid folding.

STL/STEP are millimetres. No machine-specific G-code is generated: printer
profiles and actual material/fit have to be confirmed on the user's machine.
"""

import hashlib
import json
import math
from pathlib import Path
import zipfile

import cadquery as cq
import numpy as np
import trimesh

from .folding import (
    specification,
    flat_assembly,
    transforms,
    _native_bounds,
)
from .folding_study import folding_feature, folding_study
from .workspace_drawing import drawing_data, _pdf, _pdf_scene

SETTINGS = dict(
    bed_width_mm=220.0,
    bed_depth_mm=220.0,
    bed_height_mm=220.0,
    nozzle_mm=0.4,
    layer_height_mm=0.2,
    material="PLA",
    printer_name="Unspecified",
)


def print_settings(raw=None):
    if raw is None:
        raw = {}
    if not isinstance(raw, dict) or set(raw) - set(SETTINGS):
        raise ValueError("Unsupported print settings")
    p = {**SETTINGS, **raw}
    for key in (
        "bed_width_mm",
        "bed_depth_mm",
        "bed_height_mm",
        "nozzle_mm",
        "layer_height_mm",
    ):
        value = p[key]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{key} must be finite numeric data")
        p[key] = float(value)
    if any(
        not 50 <= p[k] <= 1000
        for k in ("bed_width_mm", "bed_depth_mm", "bed_height_mm")
    ):
        raise ValueError("Printer dimensions must be from 50 to 1000 mm")
    if (
        not 0.2 <= p["nozzle_mm"] <= 1
        or not 0.08 <= p["layer_height_mm"] <= p["nozzle_mm"] * 0.8
    ):
        raise ValueError("Confirm nozzle 0.2–1 mm and layer height 0.08–0.8 x nozzle")
    for key in ("material", "printer_name"):
        if not isinstance(p[key], str) or not 1 <= len(p[key]) <= 100:
            raise ValueError(f"{key} must contain 1–100 characters")
    return p


def _oriented(part):
    shape = part["shape"].copy()
    if part.get("kind") == "pin":
        axis = np.asarray(part["axis"])
        rotation_axis = np.cross(axis, [0, 0, 1])
        shape = shape.rotate((0, 0, 0), tuple(rotation_axis), 90)
    lo, hi = _native_bounds(shape)
    return shape.translate(tuple(-lo))


def arrange(parts, settings):
    """First-fit decreasing shelves; every independent solid remains separate."""
    margin, gap = 5.0, 4.0
    prepared = []
    for part in parts:
        shape = _oriented(part)
        lo, hi = _native_bounds(shape)
        size = hi - lo
        if size[2] > settings["bed_height_mm"] - margin:
            raise ValueError(f"{part['name']} exceeds the selected printer height")
        prepared.append({**part, "shape": shape, "size": size.tolist()})
    plates = []
    for part in sorted(prepared, key=lambda p: max(p["size"][:2]), reverse=True):
        width, depth, _ = part["size"]
        placed = False
        for plate in plates:
            for shelf in plate["shelves"]:
                for rotate, (w, d) in ((False, (width, depth)), (True, (depth, width))):
                    if (
                        d <= shelf["height"] + 1e-7
                        and shelf["x"] + w <= settings["bed_width_mm"] - margin
                    ):
                        x, y = shelf["x"], shelf["y"]
                        shelf["x"] += w + gap
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                y = margin + sum(s["height"] + gap for s in plate["shelves"])
                choices = [(False, width, depth), (True, depth, width)]
                choices.sort(key=lambda item: item[2])
                for rotate, w, d in choices:
                    if (
                        w <= settings["bed_width_mm"] - 2 * margin
                        and y + d <= settings["bed_depth_mm"] - margin
                    ):
                        x = margin
                        plate["shelves"].append(dict(x=x + w + gap, y=y, height=d))
                        placed = True
                        break
            if placed:
                break
        if not placed:
            choices = sorted(
                [(False, width, depth), (True, depth, width)], key=lambda item: item[2]
            )
            for rotate, w, d in choices:
                if (
                    w <= settings["bed_width_mm"] - 2 * margin
                    and d <= settings["bed_depth_mm"] - 2 * margin
                ):
                    x = y = margin
                    plate = dict(parts=[], shelves=[dict(x=x + w + gap, y=y, height=d)])
                    plates.append(plate)
                    placed = True
                    break
        if not placed:
            raise ValueError(
                f"{part['name']} does not fit the selected bed in either flat orientation"
            )
        shape = part["shape"]
        if rotate:
            shape = shape.rotate((0, 0, 0), (0, 0, 1), 90)
            lo, hi = _native_bounds(shape)
            shape = shape.translate(tuple(-lo))
        plate["parts"].append(
            {
                **part,
                "shape": shape.translate((x, y, 0)),
                "placement_mm": [x, y, 0],
                "rotation_z_deg": 90 if rotate else 0,
            }
        )
    return plates


def _check_stl(shape, path, expected_components):
    cq.exporters.export(shape, str(path), tolerance=0.02, angularTolerance=0.1)
    mesh = trimesh.load(str(path), force="mesh", process=True)
    lo, hi = _native_bounds(shape)
    volume = shape.Volume()
    r = dict(
        watertight=bool(mesh.is_watertight),
        winding_consistent=bool(mesh.is_winding_consistent),
        components=len(mesh.split(only_watertight=False)),
        expected_components=expected_components,
        native_volume_mm3=volume,
        mesh_volume_mm3=float(mesh.volume),
        relative_volume_error=abs(float(mesh.volume) - volume) / volume,
        bounds_error_mm=float(np.max(np.abs(np.asarray([lo, hi]) - mesh.bounds))),
    )
    r["passed"] = (
        r["watertight"]
        and r["winding_consistent"]
        and r["components"] == expected_components
        and r["relative_volume_error"] <= 0.01
        and r["bounds_error_mm"] <= 0.05
    )
    if not r["passed"]:
        raise ValueError(f"Print STL verification failed: {path.name}: {r}")
    return r


def fold_interchange(p, graph, target):
    """FOLD describes the ideal hinge-axis surface, not the offset solid bodies."""
    poses = transforms(p, graph, target)
    vertices = np.asarray(graph["vertices"])
    edges = [*graph["boundary_edges"], *[h["edge"] for h in graph["hinges"]]]
    assignments = ["B"] * len(graph["boundary_edges"])
    angles = [0.0] * len(assignments)
    for hinge in graph["hinges"]:
        a, b = hinge["faces"]
        face = graph["faces"][a]
        directed = next(
            (i, j)
            for i, j in zip(face, face[1:] + face[:1])
            if set((i, j)) == set(hinge["edge"])
        )
        tangent = vertices[directed[1]] - vertices[directed[0]]
        tangent /= np.linalg.norm(tangent)
        tangent = np.asarray(poses[a])[:3, :3] @ tangent
        normals = [
            np.asarray(poses[i])[:3, :3] @ np.array([0.0, 0.0, 1.0]) for i in (a, b)
        ]
        angle = -math.degrees(
            math.atan2(np.dot(tangent, np.cross(*normals)), np.dot(*normals))
        )
        angles.append(angle)
        assignments.append("F" if abs(angle) < 1e-7 else "M" if angle < 0 else "V")
    return {
        "file_spec": 1.2,
        "file_creator": "Forma Studio",
        "file_classes": ["singleModel"],
        "frame_classes": ["creasePattern"],
        "frame_unit": "mm",
        "vertices_coords": graph["vertices"],
        "faces_vertices": graph["faces"],
        "edges_vertices": edges,
        "edges_assignment": assignments,
        "edges_foldAngle": angles,
        "forma:spec": p,
        "forma:driver_target_deg": target,
        "forma:representation": "Ideal hinge-axis surface; finite-thickness offset panels and real hardware are separate native solids in STEP/STL",
    }


def _guide(document, template, settings, study, plate_count):
    scene = []

    def text(x, y, value, size=12):
        scene.append(
            dict(type="text", x=x, y=y, text=value, size=size, color="#243942")
        )

    def line(points, color="#596d76", width=1, dashed=False):
        scene.append(
            dict(
                type="polyline", points=points, color=color, width=width, hidden=dashed
            )
        )

    p = template["spec"]
    text(
        40,
        45,
        "FORMA / " + p["family"].replace("_", " ").upper() + " / ASSEMBLY GUIDE",
        24,
    )
    text(
        40,
        77,
        f"{len(template['graph']['faces'])} panels | {len(template['joints'])} removable pins | {plate_count} build plate(s) | units mm",
        14,
    )
    text(
        40,
        108,
        "1. Print hinge-coupon.stl first. Check pin insertion and free rotation before printing a full structure.",
        13,
    )
    text(
        40,
        134,
        f"2. Slice plates with your printer profile: {settings['nozzle_mm']:g} mm nozzle, {settings['layer_height_mm']:g} mm layers, {settings['material']}; 3 perimeters suggested.",
        13,
    )
    text(
        40,
        160,
        "3. Match panel IDs below. Align two outer knuckles with one middle knuckle; insert the headed pin.",
        13,
    )
    text(
        40,
        186,
        f"4. Fold gradually through the checked driver range 0 to {study['config']['max_angle_deg']:g} degrees. Driver angle is not every hinge's dihedral.",
        13,
    )
    target = fold_interchange(p, template["graph"], study["config"]["max_angle_deg"])
    folds = list(zip(target["edges_assignment"], target["edges_foldAngle"]))[
        -len(template["joints"]) :
    ]
    for x, title in (
        (40, "HINGE"),
        (175, "PANEL A"),
        (285, "PANEL B"),
        (395, "PIN LENGTH"),
        (515, "TARGET DIHEDRAL"),
    ):
        text(x, 220, title, 10)
    for i, joint in enumerate(template["joints"]):
        a, b = joint["faces"]
        assignment, angle = folds[i]
        for x, value in (
            (40, joint["id"]),
            (175, str(a + 1)),
            (285, str(b + 1)),
            (395, f"{joint['pin_length_mm']:.2f} mm"),
            (515, f"{assignment} {abs(angle):.1f}°"),
        ):
            text(x, 244 + i * 16, value, 11)
    graph = template["graph"]
    v = np.asarray(graph["vertices"])
    lo = v[:, :2].min(axis=0)
    size = np.ptp(v[:, :2], axis=0)
    scale = min(420 / max(size[0], 1), 335 / max(size[1], 1))

    def mapped(point):
        return [
            710 + (point[0] - lo[0]) * scale,
            265 + (lo[1] + size[1] - point[1]) * scale,
        ]

    text(710, 220, "ASSEMBLY MAP / NOMINAL HINGE AXES", 12)
    text(
        710,
        240,
        "M: negative / red. V: positive / blue dashed. Use Motion for direction.",
        9,
    )
    text(710, 255, "Nominal axes; physical setbacks and barrels are in CAD/STL.", 9)
    for i, face in enumerate(graph["faces"]):
        points = [mapped(v[k]) for k in face]
        line(points + [points[0]])
        center = np.mean(points, axis=0)
        text(center[0] - 3.6 * len(str(i + 1)), center[1] + 4, str(i + 1), 12)
    for joint, (assignment, angle) in zip(graph["hinges"], folds):
        a, b = [mapped(v[k]) for k in joint["edge"]]
        line(
            [a, b],
            "#ae5d4b" if assignment == "M" else "#3e7c9a",
            1.5,
            assignment == "V",
        )
        midpoint = (np.asarray(a) + np.asarray(b)) / 2
        hinge_label = "H" + str(int(joint["id"].split("_")[-1]))
        if p["family"] == "concertina":
            text(
                midpoint[0] - 2.4 * len(hinge_label),
                max(a[1], b[1]) + 15,
                hinge_label,
                8,
            )
        else:
            text(midpoint[0] + 3, midpoint[1] - 3, hinge_label, 8)
    text(
        40,
        665,
        f"Pin diameter {p['pin_diameter']:g}; bore {p['pin_diameter']+2*p['radial_clearance']:g}; radial gap {p['radial_clearance']:g}; knuckle end gap {p['axial_clearance']:g}.",
        13,
    )
    text(
        40,
        690,
        f"Native solid interference checked at {len(study['frames'])} poses; hinge-axis closure max {study['max_axis_closure_error_mm']:.2g} mm.",
        12,
    )
    text(
        40,
        715,
        "Use plate maps to identify parts. Check bore bridging on the coupon; use a removable brim for the thin upright pins.",
        12,
    )
    text(
        40,
        740,
        "Geometry and prescribed motion verified. Friction, axial pin retention, loads, fatigue and actual printer fit are not qualified.",
        12,
    )
    text(
        40,
        770,
        "Print parts, not the assembled-pose STL. No printer-specific G-code is included.",
        12,
    )
    return _pdf_scene(scene)


def _plate_map(plate, settings, number):
    scene = []

    def text(x, y, value, size=12):
        scene.append(
            dict(type="text", x=x, y=y, text=value, size=size, color="#243942")
        )

    def line(points, color="#708791", width=0.7):
        scene.append(
            dict(type="polyline", points=points, color=color, width=width, hidden=False)
        )

    text(40, 45, f"PRINT PLATE {number} / PART IDENTIFICATION", 24)
    text(
        40,
        77,
        "P1 = panel_001.stl; H1 = pin_hinge_001.stl. Labels match the assembly guide.",
        13,
    )
    text(
        40,
        101,
        "Source plate positions in millimetres; slicers may recenter the group. Identification map, not a cutting template.",
        12,
    )
    scale = min(1080 / settings["bed_width_mm"], 600 / settings["bed_depth_mm"])
    x0 = (1200 - settings["bed_width_mm"] * scale) / 2
    y0 = 125

    def mapped(x, y):
        return [x0 + x * scale, y0 + (settings["bed_depth_mm"] - y) * scale]

    corners = [
        mapped(0, 0),
        mapped(settings["bed_width_mm"], 0),
        mapped(settings["bed_width_mm"], settings["bed_depth_mm"]),
        mapped(0, settings["bed_depth_mm"]),
    ]
    line(corners + [corners[0]], "#bbc6cc")
    data = drawing_data({"name": "Plate map"}, plate["parts"])
    for path in data["views"]["top"]["visible"]:
        line([mapped(x, y) for x, y in path])
    for part in plate["parts"]:
        lo, hi = _native_bounds(part["shape"])
        center = (lo + hi) / 2
        x, y = mapped(center[0], center[1])
        label = ("H" if part["kind"] == "pin" else "P") + str(
            int(part["id"].split("_")[-1])
        )
        if part["kind"] == "pin":
            radius = max(hi[:2] - lo[:2]) * scale / 2
            line([[x, y - radius - 1], [x, y - radius - 5]], "#708791", 0.5)
            text(x - len(label) * 2.4, y - radius - 7, label, 8)
        else:
            text(x - len(label) * 2.4, y + 2, label, 11)
    text(
        40,
        770,
        f"Configured bed: {settings['bed_width_mm']:g} x {settings['bed_depth_mm']:g} mm. Print hinge-coupon.stl before the full plate.",
        12,
    )
    return _pdf_scene(scene)


def export_print_pack(document, folder, asset_loader=None):
    from .workspace_geometry import build_document

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    settings = print_settings(document.get("metadata", {}).get("print_settings"))
    feature = folding_feature(document)
    if feature is None:
        raise ValueError(
            "Articulated print packs require a supported folding assembly; other solids can be exported as STL"
        )
    p = specification(feature["params"])
    template = flat_assembly(p)
    wall = p["hinge_radius"] - p["pin_diameter"] / 2 - p["radial_clearance"]
    if (
        wall < settings["nozzle_mm"] * 2
        or p["pin_diameter"] < settings["nozzle_mm"] * 3
        or p["thickness"] < settings["layer_height_mm"] * 3
    ):
        raise ValueError(
            "Hinge walls, pins or panel layers are too small for the selected nozzle/layer height; revise geometry or print settings"
        )
    study = folding_study(document)
    if not study["passed"]:
        raise ValueError(
            "Resolve the reported folding trajectory collisions before exporting a print pack"
        )
    plates = arrange(template["parts"], settings)
    checks = {}
    manifest_parts = []
    for part in template["parts"]:
        shape = _oriented(part)
        name = part["id"] + ".stl"
        checks[name] = _check_stl(shape, folder / name, 1)
        manifest_parts.append(
            dict(
                id=part["id"],
                name=part["name"],
                file=name,
                kind=part["kind"],
                volume_mm3=shape.Volume(),
            )
        )
    layout = []
    for i, plate in enumerate(plates):
        bounds = [_native_bounds(part["shape"]) for part in plate["parts"]]
        for a in range(len(bounds)):
            for b in range(a):
                overlap = np.minimum(bounds[a][1], bounds[b][1]) - np.maximum(
                    bounds[a][0], bounds[b][0]
                )
                if np.all(overlap > 1e-7):
                    raise ValueError("Print layout contains overlapping part envelopes")
        native = cq.Compound.makeCompound([part["shape"] for part in plate["parts"]])
        name = f"plate-{i+1}.stl"
        checks[name] = _check_stl(native, folder / name, len(plate["parts"]))
        lo, hi = _native_bounds(native)
        if (
            np.any(lo < -0.00001)
            or hi[0] > settings["bed_width_mm"]
            or hi[1] > settings["bed_depth_mm"]
            or hi[2] > settings["bed_height_mm"]
        ):
            raise ValueError(
                "A generated print plate exceeds the configured build volume"
            )
        cq.exporters.export(native, str(folder / f"plate-{i+1}.step"))
        reopened = cq.importers.importStep(str(folder / f"plate-{i+1}.step")).val()
        if (
            len(reopened.Solids()) != len(plate["parts"])
            or not reopened.isValid()
            or abs(reopened.Volume() - native.Volume()) > native.Volume() * 1e-8
        ):
            raise ValueError("Print-plate STEP roundtrip failed")
        data = drawing_data(
            {"name": f"{p['family']} / print plate {i+1}"}, plate["parts"]
        )
        (folder / f"plate-{i+1}.pdf").write_bytes(_pdf(data))
        (folder / f"plate-{i+1}-map.pdf").write_bytes(
            _plate_map(plate, settings, i + 1)
        )
        layout.append(
            dict(
                plate=i + 1,
                bounds_mm=[lo.tolist(), hi.tolist()],
                parts=[
                    {
                        k: v
                        for k, v in part.items()
                        if k in ("id", "name", "placement_mm", "rotation_z_deg")
                    }
                    for part in plate["parts"]
                ],
            )
        )
    coupon = flat_assembly(
        {
            **p,
            "family": "concertina",
            "columns": 2,
            "rows": 2,
            "count": 2,
            "panel_width": max(26, 2 * p["panel_inset"] + 10),
            "panel_height": max(34, 5 * p["panel_inset"] + 9),
            "fold_angle": 0,
        }
    )
    coupon_plates = arrange(coupon["parts"], settings)
    if len(coupon_plates) != 1:
        raise ValueError("The hinge fit coupon does not fit the selected printer bed")
    coupon_shape = cq.Compound.makeCompound(
        [part["shape"] for part in coupon_plates[0]["parts"]]
    )
    checks["hinge-coupon.stl"] = _check_stl(
        coupon_shape, folder / "hinge-coupon.stl", 3
    )
    (folder / "assembly-guide.pdf").write_bytes(
        _guide(document, template, settings, study, len(plates))
    )
    (folder / "FONT-LICENSE.txt").write_bytes(
        Path(__file__)
        .with_name("web")
        .joinpath("vendor/FormaSans-LICENSE.txt")
        .read_bytes()
    )
    (folder / "crease-pattern.fold").write_text(
        json.dumps(
            fold_interchange(p, template["graph"], study["config"]["max_angle_deg"]),
            indent=2,
        ),
        encoding="utf-8",
    )
    # Retain the complete source, including units, editable parameters and print
    # layout transforms. Never pretend that a mesh/STEP contains this history.
    (folder / "source-project.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest = dict(
        format="forma-folding-print/v1",
        family=p["family"],
        units="mm",
        effective_parameters=p,
        settings=settings,
        parts=manifest_parts,
        layout=layout,
        joints=template["joints"],
        checks=checks,
        nominal_minimum_barrel_wall_mm=wall,
        motion={
            k: v
            for k, v in study.items()
            if k not in ("parts", "graph", "frames", "panels")
        },
        geometric_print_preflight_passed=all(v["passed"] for v in checks.values()),
        printer_profile_verified=False,
        physical_fit_verified=False,
        instructions="Print the fit coupon first. Slice plate-N.stl with your actual printer/material profile. Component STLs are separate, flat/vertical oriented parts. Assemble according to assembly-guide.pdf; assembled-pose workspace.stl is a geometry export, not the prepared build plate.",
    )
    (folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.iterdir())
        if p.is_file() and p.suffix != ".zip" and p.name != "sha256.json"
    }
    (folder / "sha256.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    archive = folder / "print-pack.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix != ".zip":
                entry = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                output.writestr(entry, path.read_bytes())
    return dict(file=archive.name, manifest=manifest)
