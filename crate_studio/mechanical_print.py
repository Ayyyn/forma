"""Separate native parts, provisional plates and revision-bound assembly sheets.

Geometry and dimensions are deterministic. A printable mesh is not a qualified
printer profile, friction model, support strategy or physical assembly test.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import zipfile

import cadquery as cq
import numpy as np

from .workspace_cache import cached_build
from .workspace_geometry import _bounds
from .workspace_drawing import drawing_data, _scene, _pdf_scenes, FONT_PATH
from .folding_print import arrange, print_settings, _check_stl


def orient_part(part):
    """Choose the greatest actual planar bed contact among six axial poses."""
    choices = []
    for axis, angle in (
        ((1, 0, 0), 0),
        ((1, 0, 0), 90),
        ((1, 0, 0), -90),
        ((1, 0, 0), 180),
        ((0, 1, 0), 90),
        ((0, 1, 0), -90),
    ):
        shape = part["shape"].copy().rotate((0, 0, 0), axis, angle)
        low, high = np.asarray(_bounds(shape))
        contact = sum(
            face.Area()
            for face in shape.Faces()
            if face.geomType() == "PLANE"
            and abs(face.BoundingBox().zmax - low[2]) < 1e-6
        )
        choices.append((contact, -(high - low)[2], axis, angle, shape, low))
    contact, _, axis, angle, shape, low = max(choices, key=lambda row: row[:2])
    if contact <= 1e-6:
        raise ValueError(
            f"{part['id']} has no planar supporting face in an axial orientation; orient it explicitly in a slicer"
        )
    return {
        **part,
        "shape": shape.translate(tuple(-low)),
        "orientation": {
            "axis": list(axis),
            "angle_deg": angle,
            "translation_after_rotation_mm": (-low).tolist(),
            "planar_bed_contact_mm2": contact,
            "policy": "Largest planar bed contact among six axial poses; supports and adhesion require slicer review",
        },
    }


def _overview(document, parts, context, name=None):
    doc = deepcopy(document)
    if name:
        doc["name"] = name
    doc["annotations"] = []
    doc.setdefault("metadata", {})["drawing_layout"] = "aligned-v1"
    # Section sheets are added separately, never reinterpreted on posed bodies.
    doc["metadata"].pop("drawing_sections", None)
    return drawing_data(doc, parts, context)


def _notes_page(title, lines, context):
    import textwrap

    scene = [dict(type="text", x=44, y=55, text=title, size=24, color="#243942")]
    y = 100
    for line in lines:
        for row in textwrap.wrap(str(line), width=124) or [""]:
            scene.append(
                dict(type="text", x=44, y=y, text=row, size=12, color="#243942")
            )
            y += 19
        y += 8
    if y > 745:
        raise ValueError("Assembly guide text exceeds its sheet")
    scene.append(
        dict(
            type="text",
            x=44,
            y=775,
            text=f"SOURCE {context.get('revision_id', 'WORKING DRAFT')} / mm / physical validation pending",
            size=10,
            color="#243942",
        )
    )
    return scene


def _plate_scene(plate, settings, number, context):
    scene = _notes_page(
        f"BUILD PLATE {number} / PART IDENTIFICATION",
        [
            "Provisional bed layout / mm / identification map NTS. Confirm supports, adhesion and printer profile in your slicer.",
        ],
        context,
    )
    scale = min(1000 / settings["bed_width_mm"], 540 / settings["bed_depth_mm"])
    x0 = (1200 - settings["bed_width_mm"] * scale) / 2

    def point(x, y):
        return [x0 + x * scale, 155 + (settings["bed_depth_mm"] - y) * scale]

    def line(points, color="#708791"):
        scene.append(
            dict(type="polyline", points=points, width=0.7, hidden=False, color=color)
        )

    w, d = settings["bed_width_mm"], settings["bed_depth_mm"]
    line([point(0, 0), point(w, 0), point(w, d), point(0, d), point(0, 0)], "#bbc6cc")
    data = drawing_data({"name": "Plate identification"}, plate["parts"])
    for path in data["views"]["top"]["visible"]:
        line([point(*p) for p in path])
    for part in plate["parts"]:
        lo, hi = np.asarray(_bounds(part["shape"]))
        x, y = point(*((lo + hi) / 2)[:2])
        scene.append(
            dict(
                type="text", x=x - 24, y=y + 3, text=part["id"], size=9, color="#243942"
            )
        )
    return scene


def drawing_packet(document, parts, context, settings, layout, assembly=None):
    """Useful overview, state, part, section and actual assembly-step sheets.

    Complete source parameters live in JSON/CSV rather than filling the main
    assembly handbook with internal Boolean operation tables.
    """
    from .mechanism_study import validate_spec, pose_matrices, moved_parts

    scenes, measurements = [], []
    lines = [
        f"{len(parts)} separately printed parts / {len(layout)} provisional plate(s) on a {settings['bed_width_mm']:g} x {settings['bed_depth_mm']:g} mm bed.",
        "Confirm your actual printer, material, nozzle, layer height, supports and bed adhesion in your slicer. No G-code or reliable print-time estimate is supplied.",
        "Plate STLs contain separated parts in millimetres. Individual part STLs use the same bed orientation. The source-pose assembly STEP is for CAD inspection; do not print the assembled STL as a fused object.",
        "Print and measure the exact matching interface coupon before the full box where one is supplied. A coupon does not qualify every joint, full travel, strength, friction or fatigue.",
        "Remove supports and burrs from sliding interfaces. Dry-fit without force; stop if guides bind or a key cannot move. Do not scale one mating part independently.",
        "Assembly images show sampled rigid-body placements, not demonstrated hand access, gravity stability or elastic snap assembly. No untested interference fit is an approved snap fit.",
        "For adjustable mechanisms: release all relevant locks, move only the coupled groups prescribed by the design, align a supported state and relock. Inspect engagement before lifting or loading.",
        "Material, fit tolerances and load rating remain unspecified until physical testing. Keep fingers clear of sliding and locking gaps.",
        "Full editable features and parameters are retained in source-project.json and design-parameters.csv when supplied. Drawing dimensions below are measured from the native solids.",
    ]
    if assembly:
        lines.insert(
            1,
            f"Initial assembly: {len(assembly['spec']['steps'])} staged moves / {assembly['sample_count']} sampled poses / {assembly['collision_sample_count']} collision samples. Final target: {assembly['spec']['target_state'] or 'source construction pose'}.",
        )
    else:
        lines.insert(
            1,
            "No verified initial assembly plan is available for this model. Part sheets and plates alone do not establish assemblability.",
        )
    scenes.append(_notes_page("PRINT & ASSEMBLY / READ FIRST", lines, context))
    if assembly:
        rows = []
        for index, step in enumerate(assembly["spec"]["steps"]):
            moves = []
            for body, placement in step["placements"].items():
                vector = ", ".join(f"{v:g}" for v in placement["translation"])
                rotation = placement.get("rotation", [0, 0, 0])
                moves.append(
                    f"{body}: shift [{vector}] mm"
                    + (f"; XYZ rotation {rotation} deg" if any(rotation) else "")
                )
            rows.append(
                f"{index + 1:02d}. {step['name'].replace('_', ' ')} / "
                + " | ".join(moves)
            )
        for start in range(0, len(rows), 7):
            scenes.append(
                _notes_page(
                    "INITIAL ASSEMBLY / STAGED PLACEMENTS",
                    [
                        "Each shift below is absolute relative to source CAD coordinates, not cumulative. Omitted parts keep their previous placement. Match body IDs to part sheets and the following stage images.",
                        *rows[start : start + 7],
                        "Use the diagrams to identify approach directions. Hand access, support removal and physical insertion force still require a dry-fit trial.",
                    ],
                    context,
                )
            )
    for index, plate in enumerate(layout):
        scenes.append(_plate_scene(plate, settings, index + 1, context))
    data = _overview(document, parts, context)
    sheets = [(data, "source")]
    raw = document.get("metadata", {}).get("design_mechanism")
    if raw:
        spec = validate_spec(raw, [p["id"] for p in parts])
        for state in spec["states"]:
            if state["name"].endswith("_locked"):
                posed = moved_parts(parts, pose_matrices(spec, state["values"]))
                ctx = {**context, "pose": state["name"]}
                sheets.append(
                    (
                        _overview(
                            document,
                            posed,
                            ctx,
                            f"{document['name']} / {state['name']}",
                        ),
                        state["name"],
                    )
                )
    for part in parts:
        sheets.append(
            (
                _overview(
                    document,
                    [part],
                    {**context, "pose": f"{part['id']} / source coordinates"},
                    f"{part['id']} / {part.get('name', part['id'])}",
                ),
                part["id"],
            )
        )
    for item, key in sheets:
        scenes.append(_scene(item))
        measurements.append(
            {
                "sheet": key,
                "bounds_mm": [item["bbox_mm"]["min"], item["bbox_mm"]["max"]],
                "scale": item["sheet"]["scale_label"],
            }
        )
    if document.get("metadata", {}).get("drawing_sections"):
        sections = drawing_data(document, parts, context)
        for page in sections["section_pages"]:
            scenes.append(page["scene"])
            measurements.append({"section": page["measurements"]})
    if assembly:
        # End of each real tested segment; no reconstructed illustrative poses.
        ends = {}
        for frame in assembly["frames"][1:]:
            ends[frame["segment"]] = frame
        for index, frame in sorted(ends.items()):
            posed = moved_parts(
                parts, {k: np.asarray(v) for k, v in frame["pose_matrices"].items()}
            )
            label = f"Assembly {index + 1:02d} / {frame['step'].replace('_', ' ')}"
            item = _overview(document, posed, {**context, "pose": label}, label)
            scenes.append(_scene(item))
            measurements.append(
                {
                    "assembly_step": frame["step"],
                    "pose_matrices": frame["pose_matrices"],
                }
            )
    total = len(scenes)
    for i, scene in enumerate(scenes):
        # Replace old title-block count, keeping the calibrated scale string.
        for item in scene:
            if item["type"] == "text" and item.get("x") == 816 and item.get("y") == 701:
                suffix = item["text"].split("   A3   ", 1)[1]
                item["text"] = f"{i + 1} / {total}   A3   {suffix}"
        scene.append(
            dict(
                type="text",
                x=1090,
                y=797,
                text=f"{i + 1} / {total}",
                size=8,
                color="#243942",
            )
        )
    return _pdf_scenes(scenes), measurements


def export_print_pack(
    document,
    folder,
    asset_loader=None,
    settings=None,
    context=None,
    portable_source=None,
):
    """Fail closed on native, assembly, part and plate read-back errors."""
    from .assembly_study import assembly_study

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    settings = print_settings(
        settings
        if settings is not None
        else document.get("metadata", {}).get("print_settings")
    )
    context = context or {
        "revision_id": "WORKING DRAFT",
        "pose": "Source construction pose",
    }
    built = cached_build(document, asset_loader)
    if not built["checks"]["passed"] or not built["parts"]:
        raise ValueError("A print package requires valid native solid geometry")
    parts = built["parts"]
    plan = document.get("metadata", {}).get("assembly_plan")
    assembly = assembly_study(document, built, plan) if plan else None
    if assembly and not assembly["passed"]:
        raise ValueError(
            "The retained initial assembly plan fails on this exact geometry; repair it before exporting the print package"
        )
    retention_targets = (
        document.get("metadata", {}).get("native_study_targets", {}).get("retention")
    )
    retention = None
    if retention_targets is not None:
        from .retention_study import retention_study

        retention = retention_study(document, built, retention_targets)
        if not retention["passed"]:
            raise ValueError(
                "Retained parts have an escape path at a required state; repair capture before exporting the print package"
            )
    modes = (
        document.get("metadata", {})
        .get("native_study_targets", {})
        .get("prismatic_controls")
    )
    controls = None
    if modes is not None:
        from .prismatic_controls import prismatic_controls

        controls = prismatic_controls(document, built, modes)
        if not controls["passed"]:
            raise ValueError(
                "Lock/unlock/end-stop controls fail; repair the mechanism before print release"
            )
    handling_targets = (
        document.get("metadata", {})
        .get("native_study_targets", {})
        .get("handling_paths")
    )
    handling = None
    if handling_targets is not None:
        from .handling_study import handling_study

        handling = handling_study(document, built, handling_targets)
        if not handling["passed"]:
            raise ValueError(
                "An unwanted lift/pull handling path remains clear; repair capture before print release"
            )
    oriented = [orient_part(p) for p in parts]
    plates = arrange(oriented, settings)
    checks, rows = {}, []
    allowed = []

    def write_json(name, value):
        (folder / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        allowed.append(name)

    for part in oriented:
        name = f"{part['id']}.stl"
        checks[name] = _check_stl(part["shape"], folder / name, 1)
        allowed.append(name)
        rows.append(
            {
                "id": part["id"],
                "name": part.get("name", part["id"]),
                "file": name,
                "source_bounds_mm": _bounds(
                    next(p["shape"] for p in parts if p["id"] == part["id"])
                ),
                "orientation": part["orientation"],
                "native_volume_mm3": part["shape"].Volume(),
            }
        )
    layout = []
    for i, plate in enumerate(plates):
        shapes = [p["shape"] for p in plate["parts"]]
        bounds = [np.asarray(_bounds(s)) for s in shapes]
        for j, a in enumerate(bounds):
            if np.any(a[0] < -1e-6) or np.any(
                a[1]
                > [
                    settings[k]
                    for k in ("bed_width_mm", "bed_depth_mm", "bed_height_mm")
                ]
            ):
                raise ValueError("Print plate exceeds configured build volume")
            for b in bounds[:j]:
                if np.all(np.minimum(a[1], b[1]) - np.maximum(a[0], b[0]) > -1e-7):
                    raise ValueError("Print plate part envelopes touch or overlap")
        name = f"plate-{i + 1}.stl"
        checks[name] = _check_stl(
            cq.Compound.makeCompound(shapes), folder / name, len(shapes)
        )
        allowed.append(name)
        layout.append(
            {
                "plate": i + 1,
                "parts": [
                    {k: p[k] for k in ("id", "placement_mm", "rotation_z_deg")}
                    for p in plate["parts"]
                ],
            }
        )
    native = cq.Compound.makeCompound([p["shape"] for p in parts])
    cq.exporters.export(native, str(folder / "assembly.step"))
    reopened = cq.importers.importStep(str(folder / "assembly.step")).val()
    checks["assembly.step"] = {
        "passed": bool(
            reopened.isValid()
            and len(reopened.Solids()) == len(parts)
            and abs(reopened.Volume() - native.Volume())
            <= max(1e-6, native.Volume() * 1e-8)
            and np.max(
                np.abs(np.asarray(_bounds(reopened)) - np.asarray(_bounds(native)))
            )
            <= 1e-5
        )
    }
    if not checks["assembly.step"]["passed"]:
        raise ValueError("Assembly STEP read-back failed")
    allowed.append("assembly.step")
    pdf, measurements = drawing_packet(
        document, parts, context, settings, plates, assembly
    )
    (folder / "assembly-drawings.pdf").write_bytes(pdf)
    allowed.append("assembly-drawings.pdf")
    (folder / "FONT-LICENSE.txt").write_bytes(
        FONT_PATH.with_name("FormaSans-LICENSE.txt").read_bytes()
    )
    allowed.append("FONT-LICENSE.txt")
    write_json("source-project.json", portable_source or document)
    write_json("drawing-measurements.json", measurements)
    if assembly:
        write_json("assembly-verification.json", assembly)
    if retention:
        write_json("retention-verification.json", retention)
    if controls:
        write_json("lock-controls.json", controls)
    if handling:
        write_json("handling-verification.json", handling)
    manifest = {
        "format": "forma-mechanical-print/v1",
        "units": "mm (STL has no unit field)",
        "source_revision": context["revision_id"],
        "source_sha256": hashlib.sha256(
            json.dumps(document, sort_keys=True).encode()
        ).hexdigest(),
        "settings": settings,
        "settings_provisional": True,
        "parts": rows,
        "layout": layout,
        "checks": checks,
        "geometric_print_preflight_passed": all(c["passed"] for c in checks.values()),
        "initial_assembly_verified": bool(assembly and assembly["passed"]),
        "straight_translation_retention_verified": bool(
            retention and retention["passed"]
        ),
        "global_retention_verified": False,
        "printer_profile_verified": False,
        "physical_fit_verified": False,
        "physical_validation": False,
        "scope": "Native geometric read-back and separated build-plate layout only. Orientation maximizes planar bed contact; no overhang/support, friction, strength, gravity or physical-fit qualification.",
        "instructions": "Confirm actual printer/material/profile and supports in a slicer; inspect assembly-drawings.pdf. Use plate-N.stl or individual body STLs, not a fused assembly mesh. Do not force binding joints.",
    }
    write_json("manifest.json", manifest)
    write_json(
        "sha256.json",
        {
            name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
            for name in sorted(allowed)
        },
    )
    archive = folder / "print-pack.zip"
    # Explicit allowlist: receipts, logs, private metadata files and stale exports
    # in the output directory can never accidentally enter the handoff archive.
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for name in sorted(allowed):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            output.writestr(
                info, (folder / name).read_bytes(), compress_type=zipfile.ZIP_DEFLATED
            )
    return {"file": archive.name, "manifest": manifest}
