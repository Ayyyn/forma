"""Real CAD Studio integration checks, no model requests."""

import base64
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import urllib.error
import urllib.request
import zipfile
import ezdxf
from crate_studio.workspace_server import DEFAULT_DOCUMENT

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8770"


def call(path, data=None):
    payload = None if data is None else json.dumps(data, allow_nan=False).encode()
    req = urllib.request.Request(
        BASE + path, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def json_call(path, data=None):
    status, raw = call(path, data)
    try:
        value = json.loads(raw)
    except ValueError:
        value = {"detail": raw.decode(errors="replace")[:500]}
    if status != 200:
        raise AssertionError(f"{path}: {status}: {value}")
    return value


def main(output=None):
    output = Path(output) if output else ROOT / "output/forma/studio/http-v1"
    output.mkdir(parents=True, exist_ok=False)
    checks = []

    def check(name, truth, detail=None):
        checks.append({"check": name, "passed": bool(truth), "detail": detail})
        (output / "partial.json").write_text(
            json.dumps(checks, indent=2), encoding="utf-8"
        )
        if not truth:
            raise AssertionError(name + ": " + str(detail))

    boot = json_call("/api/studio/bootstrap")
    initial = json_call(
        "/api/studio/documents",
        {"document": DEFAULT_DOCUMENT, "label": "Integration fixture · mounting plate"},
    )
    d = initial["document"]
    check(
        "bootstrap_valid_solid",
        initial["passed"] and initial["metrics"]["solid_count"] == 1,
    )
    changed = json.loads(json.dumps(d))
    changed["features"][0]["params"]["width"] += 20
    changed["annotations"] = [
        {
            "id": "review-note",
            "type": "text",
            "view": "sheet",
            "x": 60,
            "y": 750,
            "text": "Review <1> & retain holes",
        }
    ]
    preview = json_call("/api/studio/preview", {"document": changed})
    check(
        "edit_parameter_rebuilds_exact_volume",
        abs(preview["metrics"]["volume_mm3"] - initial["metrics"]["volume_mm3"] - 16000)
        < 1e-5,
    )
    check(
        "annotation_xml_escaped",
        "Review &lt;1&gt; &amp; retain holes" in preview["drawing_svg"],
    )
    saved = json_call(
        "/api/studio/documents",
        {
            "document": changed,
            "parent_id": initial["id"],
            "label": "Integration: width edit",
        },
    )
    check("revision_parent_preserved", saved["parent_id"] == initial["id"])
    old = json_call("/api/studio/undo", {"current_id": saved["id"]})
    check("undo_restores_previous_geometry", old["id"] == initial["id"])
    redone = json_call("/api/studio/redo", {"current_id": old["id"]})
    check("redo_restores_edited_geometry", redone["id"] == saved["id"])
    suppressed = json.loads(json.dumps(changed))
    suppressed["features"][-1]["suppressed"] = True
    suppressed_result = json_call("/api/studio/preview", {"document": suppressed})
    check(
        "suppress_hole_restores_material",
        abs(
            suppressed_result["metrics"]["volume_mm3"]
            - saved["metrics"]["volume_mm3"]
            - math.pi * 8**2 * 10
        )
        < 1e-5,
    )
    broken = json.loads(json.dumps(changed))
    broken["features"].append(
        {
            "id": "missed-hole",
            "type": "cut_hole",
            "params": {"radius": 2, "depth": 10, "x": 999, "y": 999, "z": 0},
        }
    )
    bad = json_call("/api/studio/preview", {"document": broken})
    check(
        "no_intersection_feature_fails",
        not bad["passed"] and bad["feature_results"][-1]["status"] == "error",
    )
    status, _ = call(
        "/api/studio/documents", {"document": broken, "parent_id": saved["id"]}
    )
    check("invalid_feature_not_committed", status == 422)
    faces = saved["geometry"]["face_meshes"]
    top = next(
        f
        for f in faces
        if f["normal"] and f["normal"][2] > 0.999 and abs(f["center"][2] - 10) < 1e-5
    )
    bottom = next(f for f in faces if f["normal"] and f["normal"][2] < -0.999)
    measures = json_call(
        "/api/studio/measure",
        {"document": changed, "selection": [top["id"], bottom["id"]]},
    )
    check("exact_face_distance", abs(measures["distance_mm"] - 10) < 1e-6, measures)
    check("exact_normal_angle", abs(measures["angle_degrees"] - 180) < 1e-6)
    pair = {
        "name": "Interference check",
        "features": [
            {
                "id": "one",
                "type": "box",
                "params": {
                    "width": 20,
                    "depth": 20,
                    "height": 10,
                    "operation": "new_body",
                },
            },
            {
                "id": "two",
                "type": "box",
                "params": {
                    "width": 20,
                    "depth": 20,
                    "height": 10,
                    "cx": 10,
                    "operation": "new_body",
                },
            },
        ],
    }
    collisions = json_call("/api/studio/interference", {"document": pair})
    check(
        "positive_volume_interference_detected",
        collisions["interference_count"] == 1
        and abs(collisions["pairs"][0]["volume_mm3"] - 2000) < 1e-6,
    )
    exports = {}
    for fmt in ["step", "stl", "json", "svg", "pdf", "dxf", "csv", "bundle"]:
        status, raw = call(f'/api/studio/documents/{saved["id"]}/export/{fmt}')
        check(
            "export_" + fmt,
            status == 200 and len(raw) > 100,
            {"bytes": len(raw), "status": status},
        )
        exports[fmt] = raw
    body_rows = list(csv.DictReader(io.StringIO(exports["csv"].decode())))
    check(
        "body_list_matches_geometry",
        len(body_rows) == 1
        and abs(float(body_rows[0]["volume_mm3"]) - saved["metrics"]["volume_mm3"])
        < 1e-5,
    )
    with zipfile.ZipFile(io.BytesIO(exports["bundle"])) as z:
        names = z.namelist()
        check(
            "package_contains_editable_source",
            all(
                n in names
                for n in [
                    "workspace.json",
                    "project.json",
                    "drawing-source.json",
                    "drawing-measurements.json",
                    "workspace.step",
                    "verification.json",
                    "body-list.csv",
                    "sha256.json",
                ]
            ),
        )
        hashes = json.loads(z.read("sha256.json"))
        check(
            "package_hashes_match",
            all(
                hashlib.sha256(z.read(n)).hexdigest() == digest
                for n, digest in hashes.items()
            ),
        )
        v = json.loads(z.read("verification.json"))
        check(
            "step_and_mesh_roundtrips",
            v["step_roundtrip"]["passed"] and v["stl_roundtrip"]["passed"],
        )
    imported = json_call(
        "/api/studio/import",
        {
            "filename": "editable.step",
            "content_base64": base64.b64encode(exports["step"]).decode(),
        },
    )
    check(
        "step_import_preserves_volume",
        abs(imported["metrics"]["volume_mm3"] - saved["metrics"]["volume_mm3"]) < 1e-5,
    )
    face = next(
        f
        for f in imported["geometry"]["face_meshes"]
        if f["normal"] and f["normal"][2] > 0.999 and abs(f["center"][2] - 10) < 1e-5
    )
    direct = json.loads(json.dumps(imported["document"]))
    direct["features"].append(
        {
            "id": "push-face",
            "type": "face_offset",
            "name": "Top face push",
            "params": {
                "part_id": face["part_id"],
                "face_index": face["face_index"],
                "distance": 2,
            },
        }
    )
    direct = json_call(
        "/api/studio/documents",
        {
            "document": direct,
            "parent_id": imported["id"],
            "label": "Integration: imported face push",
        },
    )
    check(
        "imported_face_edit_changes_dimensions",
        abs(direct["metrics"]["size_mm"][2] - 12) < 1e-6,
    )
    check(
        "imported_face_edit_preserves_holes",
        abs(direct["metrics"]["volume_mm3"] - saved["metrics"]["volume_mm3"] * 1.2)
        < 1e-5,
    )
    status, portable = call(f'/api/studio/documents/{direct["id"]}/export/json')
    check("portable_project_export", status == 200)
    reimported = json_call(
        "/api/studio/import",
        {
            "filename": "roundtrip.json",
            "content_base64": base64.b64encode(portable).decode(),
        },
    )
    check(
        "portable_json_reimport_preserves_editable_features",
        len(reimported["document"]["features"]) == 2
        and abs(reimported["metrics"]["volume_mm3"] - direct["metrics"]["volume_mm3"])
        < 1e-5,
    )
    dxf = ezdxf.new("R2010")
    dxf.units = 4
    dxf.modelspace().add_circle((0, 0, 3), 10)
    stream = io.StringIO()
    dxf.write(stream)
    profile = json_call(
        "/api/studio/import",
        {
            "filename": "circle-profile.dxf",
            "content_base64": base64.b64encode(stream.getvalue().encode()).decode(),
        },
    )
    check(
        "dxf_profile_extrudes_actual_geometry",
        abs(profile["metrics"]["volume_mm3"] - math.pi * 100 * 10) < 1e-5
        and abs(profile["metrics"]["bounds_mm"][0][2] - 3) < 1e-6,
    )
    dxf.units = 1
    stream = io.StringIO()
    dxf.write(stream)
    inch_profile = json_call(
        "/api/studio/import",
        {
            "filename": "inch-profile.dxf",
            "content_base64": base64.b64encode(stream.getvalue().encode()).decode(),
        },
    )
    check(
        "dxf_declared_inches_converted_to_mm",
        abs(inch_profile["metrics"]["size_mm"][0] - 508) < 1e-5
        and abs(inch_profile["metrics"]["bounds_mm"][0][2] - 76.2) < 1e-5,
    )
    dxf.units = 0
    stream = io.StringIO()
    dxf.write(stream)
    status, _ = call(
        "/api/studio/import",
        {
            "filename": "unitless.dxf",
            "content_base64": base64.b64encode(stream.getvalue().encode()).decode(),
        },
    )
    check("unitless_dxf_requires_explicit_units", status == 422)
    status, _ = call(
        "/api/studio/import",
        {"filename": "bad.json", "content_base64": base64.b64encode(b"[]").decode()},
    )
    check("nonobject_json_rejected", status == 422)
    status, _ = call(
        "/api/studio/import",
        {
            "filename": "native.sldprt",
            "content_base64": base64.b64encode(b"not-supported").decode(),
        },
    )
    check("unsupported_native_format_honest", status == 422)
    status, _ = call(
        "/api/studio/import",
        {
            "filename": "fake.json",
            "content_base64": base64.b64encode(
                json.dumps(
                    {
                        "document": d,
                        "assets": {"0" * 64: base64.b64encode(b"x").decode()},
                    }
                ).encode()
            ).decode(),
        },
    )
    check("asset_hash_mismatch_rejected", status == 422)
    base = json_call("/api/bootstrap")["project"]
    converted = json_call("/api/studio/from-crate/" + base["id"], {})
    check(
        "crate_converts_to_editable_bodies",
        converted["metrics"]["solid_count"] == base["metrics"]["panel_count"]
        and abs(
            converted["metrics"]["volume_mm3"] - base["metrics"]["material_volume_mm3"]
        )
        < 1e-4,
    )
    check(
        "converted_requirements_scope_explicit",
        any(c["id"] == "crate_scope" for c in converted["checks"]),
    )
    result = {
        "passed": all(c["passed"] for c in checks),
        "count": len(checks),
        "checks": checks,
        "source_document_id": saved["id"],
        "direct_edit_id": direct["id"],
        "converted_id": converted["id"],
        "model_calls": 0,
        "scope": "Constructed CAD application integration, not customer/physical validation",
    }
    (output / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "checks": len(checks),
                "source_document_id": saved["id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    main(args.directory)
