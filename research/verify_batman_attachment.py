"""Verify and apply the retained Meta-designed attachment without editing its CAD."""

from copy import deepcopy
import hashlib
import io
import json
import math
import zipfile

import cadquery as cq
import ezdxf
import numpy as np
import trimesh
from OCP.BRepAdaptor import BRepAdaptor_Surface

from crate_studio.workspace_geometry import build_document
from .build_batman_demo import ROOT, request, dump

SOURCE = ROOT / "output/forma/batman-logo/ring-attachment/meta-design"
DEST = ROOT / "output/forma/batman-logo/keyring"


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    response = json.loads((SOURCE / "response.json").read_text(encoding="utf-8"))
    proposal = response["proposal"]
    base = json.loads(request("/api/studio/documents/" + response["document_id"]))
    doc = proposal["document"]
    built = build_document(doc)
    original = build_document(base["document"])
    original_solid = original["parts"][0]["shape"]
    solid = built["parts"][0]["shape"]
    additions = doc["features"][len(base["document"]["features"]) :]
    hole = next(f for f in additions if f["type"] == "cut_hole")["params"]
    lug = next(f for f in additions if f["params"].get("shape") == "circle")["params"]
    neck_feature = next(f for f in additions if f["params"].get("shape") == "rectangle")
    neck = neck_feature["params"]
    height = base["metrics"]["size_mm"][2]
    hole_tool = (
        cq.Workplane("XY")
        .circle(hole["radius"])
        .extrude(hole["depth"])
        .translate((hole["x"], hole["y"], hole["z"]))
        .val()
    )
    neck_doc = {"features": [neck_feature]}
    neck_solid = build_document(neck_doc)["parts"][0]["shape"]
    pre_hole = deepcopy(doc)
    pre_hole["features"] = [f for f in doc["features"] if f["type"] != "cut_hole"]
    pre_hole_volume = build_document(pre_hole)["metrics"]["volume_mm3"]
    original_other = {k: v for k, v in base["document"].items() if k != "features"}
    proposed_other = {k: v for k, v in doc.items() if k != "features"}
    open_points = [
        (hole["x"] + radius * math.cos(angle), hole["y"] + radius * math.sin(angle), z)
        for radius in (0, hole["radius"] * 0.99)
        for angle in np.linspace(0, 2 * math.pi, 24, endpoint=False)
        for z in (0.01, height / 2, height - 0.01)
    ]
    wall_points = [
        (
            hole["x"] + (hole["radius"] + 0.25) * math.cos(angle),
            hole["y"] + (hole["radius"] + 0.25) * math.sin(angle),
            height / 2,
        )
        for angle in np.linspace(0, 2 * math.pi, 48, endpoint=False)
    ]
    checks = {
        "ready_in_one_meta_response": proposal["status"] == "ready"
        and proposal["calls"] == 1,
        "original_feature_unchanged": doc["features"][
            : len(base["document"]["features"])
        ]
        == base["document"]["features"],
        "original_brief_notes_display_unchanged": original_other == proposed_other,
        "valid_single_connected_brep": built["checks"]["passed"]
        and len(built["parts"]) == 1
        and len(solid.Solids()) == 1,
        "no_original_bat_material_removed": original_solid.cut(solid).Volume() < 1e-7,
        "original_width_preserved": abs(
            built["metrics"]["size_mm"][0] - base["metrics"]["size_mm"][0]
        )
        < 1e-7,
        "flat_bed_and_original_thickness": abs(built["metrics"]["bounds_mm"][0][2])
        < 1e-8
        and abs(built["metrics"]["size_mm"][2] - height) < 1e-8,
        "neck_has_positive_volume_joint_to_bat": neck_solid.intersect(
            original_solid
        ).Volume()
        > 1e-6,
        "hole_outside_original_bat": hole_tool.intersect(original_solid).Volume()
        < 1e-8,
        "hole_removed_full_cylinder_volume": abs(
            pre_hole_volume - solid.Volume() - math.pi * hole["radius"] ** 2 * height
        )
        < 1e-6,
        "sampled_bore_clear_through_thickness": all(
            not solid.isInside(cq.Vector(*p), 1e-7) for p in open_points
        ),
        "sampled_material_surrounds_hole": all(
            solid.isInside(cq.Vector(*p), 1e-7) for p in wall_points
        ),
    }
    if not all(checks.values()):
        dump(DEST / "pre-apply-failure.json", checks)
        raise AssertionError(checks)
    # The API must persist exactly the unedited model output, with provenance.
    saved_path = DEST / "applied.json"
    if saved_path.exists():
        saved = json.loads(
            request("/api/studio/documents/" + json.loads(saved_path.read_text())["id"])
        )
    else:
        saved = json.loads(
            request("/api/studio/proposals/" + response["id"] + "/apply", {})
        )
        dump(saved_path, {k: saved[k] for k in ("id", "parent_id", "provenance")})
    checks["applied_exact_model_document"] = (
        saved["document"] == doc and saved["parent_id"] == base["id"]
    )
    data = request("/api/studio/documents/" + saved["id"] + "/export/bundle")
    (DEST / "batman-keyring-package.zip").write_bytes(data)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        hashes = json.loads(archive.read("sha256.json"))
        checks["export_hashes_match"] = all(
            hashlib.sha256(archive.read(name)).hexdigest() == digest
            for name, digest in hashes.items()
        )
        for name in archive.namelist():
            path = (DEST / name).resolve()
            assert path.is_relative_to(DEST.resolve())
            path.write_bytes(archive.read(name))
    mesh = trimesh.load(DEST / "workspace.stl", force="mesh", process=True)
    step = cq.importers.importStep(str(DEST / "workspace.step")).solids().vals()
    cylinders = [
        BRepAdaptor_Surface(f.wrapped).Cylinder().Radius()
        for f in step[0].Faces()
        if f.geomType() == "CYLINDER"
    ]
    measurements = json.loads(
        (DEST / "drawing-measurements.json").read_text(encoding="utf-8")
    )
    dxf = ezdxf.readfile(DEST / "drawing.dxf")
    checks.update(
        {
            "exporter_step_and_stl_checks_pass": json.loads(
                (DEST / "verification.json").read_text()
            )["passed"],
            "watertight_consistent_single_mesh": mesh.is_watertight
            and mesh.is_winding_consistent
            and mesh.is_volume
            and len(mesh.split()) == 1,
            "mesh_has_one_through_hole": mesh.euler_number == 0,
            "stl_bounds_match_cad": np.allclose(
                mesh.bounds, built["metrics"]["bounds_mm"], atol=0.03, rtol=0
            ),
            "stl_volume_within_point_one_percent": abs(mesh.volume - solid.Volume())
            / solid.Volume()
            < 0.001,
            "step_valid_single_solid": len(step) == 1 and step[0].isValid(),
            "step_volume_matches_cad": abs(step[0].Volume() - solid.Volume()) < 1e-6,
            "step_retains_analytic_hole_and_lug_radii": any(
                abs(r - hole["radius"]) < 1e-8 for r in cylinders
            )
            and any(abs(r - lug["radius"]) < 1e-8 for r in cylinders),
            "all_three_drawing_views_measured_from_same_cad": set(measurements["views"])
            == {"front", "top", "right"}
            and np.allclose(
                measurements["bbox_mm"]["size"],
                built["metrics"]["size_mm"],
                atol=1e-8,
                rtol=0,
            ),
            "dxf_audit_and_native_dimensions": not dxf.audit().has_errors
            and len(list(dxf.modelspace().query("DIMENSION"))) >= 6,
            "portable_and_drawing_source_exact": json.loads(
                (DEST / "project.json").read_text(encoding="utf-8")
            )["document"]
            == doc
            and json.loads((DEST / "drawing-source.json").read_text(encoding="utf-8"))
            == doc,
        }
    )
    checks = {name: bool(value) for name, value in checks.items()}
    for source, target in [
        ("workspace.stl", "batman-keyring.stl"),
        ("workspace.step", "batman-keyring.step"),
        ("drawing.pdf", "batman-keyring.pdf"),
    ]:
        (DEST / target).write_bytes((DEST / source).read_bytes())
    (ROOT / "examples/forma-batman-keyring-meta.json").write_bytes(
        (DEST / "project.json").read_bytes()
    )
    report = {
        "passed": all(checks.values()),
        "checks": checks,
        "document_id": saved["id"],
        "base_document_id": base["id"],
        "url": "http://127.0.0.1:8770/studio?document=" + saved["id"] + "&view=model",
        "model": proposal["model"],
        "response_ids": proposal["response_ids"],
        "model_calls": proposal["calls"],
        "estimated_cost_usd": proposal["estimated_cost_usd"],
        "meta_summary": proposal["summary"],
        "model_geometry_manually_edited": False,
        "model_chosen_dimensions": {
            "lug_outer_diameter_mm": 2 * lug["radius"],
            "hole_diameter_mm": 2 * hole["radius"],
            "lug_center_xy_mm": [lug["cx"], lug["cy"]],
            "neck_width_mm": neck["width"],
            "neck_length_mm": neck["depth"],
            "thickness_mm": height,
        },
        "overall_size_mm": built["metrics"]["size_mm"],
        "neck_bat_joint_intersection_mm3": neck_solid.intersect(
            original_solid
        ).Volume(),
        "stl_volume_mm3": float(mesh.volume),
        "stl_triangles": len(mesh.faces),
        "package_sha256": hashlib.sha256(data).hexdigest(),
        "scope": "One delegated dimension-selection demonstration, not a held-out benchmark. BREP, sampled hole clearance and export checks do not validate ring fit or load strength. Physical test pending. No geometry correction by Codex.",
    }
    dump(DEST / "results.json", report)
    assert report["passed"], checks
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
