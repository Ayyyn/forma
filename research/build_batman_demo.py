"""Create a local editable bat emblem from a brief; verify actual app exports.

The silhouette is explicitly authored geometry, not a claimed Meta model result.
No network service or model call is used beyond the running local Forma app.
"""

from copy import deepcopy
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

import cadquery as cq
import ezdxf
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "output/forma/batman-logo"
BASE = "http://127.0.0.1:8770"


def dump(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def outline():
    # Right half: head, ears, upper wing, outer tip, three scallops, central tail.
    # Symmetry is exact in the persisted source; curved regions are sampled
    # cubic Beziers, retained as editable straight sketch segments in Forma.
    half = [[0, 7.3], [2.4, 7.3], [4, 14], [5.6, 4.6]]

    def curve(c1, c2, end, n=10):
        start = half[-1]
        for i in range(1, n + 1):
            t = i / n
            half.append(
                [
                    round(
                        (1 - t) ** 3 * start[j]
                        + 3 * (1 - t) ** 2 * t * c1[j]
                        + 3 * (1 - t) * t * t * c2[j]
                        + t**3 * end[j],
                        6,
                    )
                    for j in range(2)
                ]
            )

    curve([9, 3.1], [11, 5.8], [16, 8])
    curve([24, 12.1], [31, 13.5], [38.1, 13])
    curve([34.8, 7.2], [32.7, 2.6], [32, -4])
    curve([28.1, -0.7], [24.7, -0.6], [22, -7])
    curve([18.5, -3.1], [13.6, -4.5], [11, -10])
    curve([7.5, -7], [3.3, -11.7], [0, -17])
    return half + [[-x, y] for x, y in reversed(half[1:-1])]


def verify_exports(ident):
    DEST.mkdir(parents=True, exist_ok=True)
    row = json.loads(request(f"/api/studio/documents/{ident}"))
    document = row["document"]
    payload = request(f"/api/studio/documents/{ident}/export/bundle")
    (DEST / "batman-logo-package.zip").write_bytes(payload)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        hashes = json.loads(archive.read("sha256.json"))
        assert all(
            hashlib.sha256(archive.read(name)).hexdigest() == digest
            for name, digest in hashes.items()
        )
        # All names come from our local exporter, but still validate containment.
        for name in archive.namelist():
            target = (DEST / name).resolve()
            assert target.is_relative_to(DEST.resolve())
            target.write_bytes(archive.read(name))
    points = np.array(document["features"][0]["params"]["points"], dtype=float)
    thickness = float(document["features"][0]["params"]["height"])
    area = (
        abs(
            np.dot(points[:, 0], np.roll(points[:, 1], -1))
            - np.dot(points[:, 1], np.roll(points[:, 0], -1))
        )
        / 2
    )
    expected_size = [76.2, 31, 3]
    mesh = trimesh.load(DEST / "workspace.stl", force="mesh", process=True)
    step = cq.importers.importStep(str(DEST / "workspace.step")).solids().vals()
    measurements = json.loads(
        (DEST / "drawing-measurements.json").read_text(encoding="utf-8")
    )
    portable = json.loads((DEST / "project.json").read_text(encoding="utf-8"))
    drawing_doc = json.loads((DEST / "drawing-source.json").read_text(encoding="utf-8"))
    dxf = ezdxf.readfile(DEST / "drawing.dxf")
    audited = dxf.audit()
    drawing_svg = (DEST / "drawing.svg").read_text(encoding="utf-8")
    checks = {
        "app_geometry_valid": row["passed"],
        "app_size_exact_mm": bool(
            np.allclose(row["metrics"]["size_mm"], expected_size, atol=1e-7, rtol=0)
        ),
        "three_inches_is_76_2_mm": abs(row["metrics"]["size_mm"][0] / 25.4 - 3) < 1e-9,
        "one_connected_closed_mesh": mesh.is_watertight
        and mesh.is_winding_consistent
        and mesh.is_volume
        and len(mesh.split()) == 1,
        "stl_dimensions_mm": bool(
            np.allclose(mesh.extents, expected_size, atol=1e-5, rtol=0)
        ),
        "sits_flat_at_z_zero": abs(float(mesh.bounds[0][2])) < 1e-8,
        "independent_shoelace_volume": abs(
            row["metrics"]["volume_mm3"] - area * thickness
        )
        < 1e-6,
        "stl_volume_matches_analytic": abs(float(mesh.volume) - area * thickness)
        < 0.001,
        "step_valid_single_solid": len(step) == 1 and step[0].isValid(),
        "step_volume_matches_analytic": abs(
            sum(s.Volume() for s in step) - area * thickness
        )
        < 1e-6,
        "outline_mirror_symmetry": set(map(tuple, points))
        == {(-x, y) for x, y in points},
        "drawing_measured_same_geometry": bool(
            np.allclose(
                measurements["bbox_mm"]["size"], expected_size, atol=1e-7, rtol=0
            )
        ),
        "three_brep_orthographic_views": set(measurements["views"])
        == {"front", "top", "right"}
        and all(
            label in drawing_svg
            for label in ["Front (X / Z)", "Top (X / Y)", "Right (Y / Z)"]
        ),
        "dxf_audit_and_native_dimensions": not audited.has_errors
        and len(list(dxf.modelspace().query("DIMENSION"))) >= 6,
        "editable_source_roundtrip": portable["document"] == document
        and drawing_doc == document,
        "export_hashes_match": True,
        "exporter_roundtrips_pass": json.loads(
            (DEST / "verification.json").read_text()
        )["passed"],
    }
    checks = {name: bool(value) for name, value in checks.items()}
    assert all(checks.values()), checks
    results = {
        "document_id": ident,
        "url": f"{BASE}/studio?document={ident}&view=model",
        "drawing_url": f"{BASE}/studio?document={ident}&view=drawing",
        "size_mm": row["metrics"]["size_mm"],
        "outline_points": len(points),
        "area_mm2": float(area),
        "volume_mm3": float(mesh.volume),
        "triangles": len(mesh.faces),
        "checks": checks,
        "passed": all(checks.values()),
        "model_calls": 0,
        "authorship": "Explicitly authored symmetric bat silhouette from the user's brief; no Meta generation claimed.",
        "physical_print": "Not yet printed or sliced for a specific printer. STL units are millimetres; import at 100%. Flat lower face at Z=0.",
        "package_sha256": hashlib.sha256(payload).hexdigest(),
    }
    dump(DEST / "results.json", results)
    (ROOT / "examples/forma-batman-logo.json").write_bytes(
        (DEST / "project.json").read_bytes()
    )
    (DEST / "batman-logo.stl").write_bytes((DEST / "workspace.stl").read_bytes())
    (DEST / "batman-logo.step").write_bytes((DEST / "workspace.step").read_bytes())
    (DEST / "batman-logo.pdf").write_bytes((DEST / "drawing.pdf").read_bytes())
    print(json.dumps(results, indent=2))
    return results


def main():
    if DEST.exists() and any(DEST.iterdir()):
        raise FileExistsError(
            "Preserve the existing demo; verify_exports can recheck it."
        )
    DEST.mkdir(parents=True, exist_ok=True)
    doc = {
        "name": "Batman logo · 3 inch",
        "features": [],
        "annotations": [],
        "display": {"color": "#343943", "body_names": {"body_001": "Batman emblem"}},
        "metadata": {
            "brief": "Make a 3D-printable Batman bat silhouette approximately 3 inches wide. Use a symmetric, solid silhouette without an oval border, a flat underside and editable CAD. Deliver measured orthographic drawings and STL. Design decision: 76.2 mm overall width, 31 mm overall height and 3 mm thickness, printed flat; no hanging hole requested.",
            "design_origin": "Explicitly authored outline from brief; no external model call.",
            "print_orientation": "XY flat, Z=0 on bed, thickness along +Z. Import STL in millimetres at 100%.",
        },
    }
    brief = json.loads(
        request(
            "/api/studio/documents",
            {"document": doc, "label": "01 · brief and print dimensions"},
        )
    )
    doc = deepcopy(doc)
    doc["features"] = [
        {
            "id": "bat-outline",
            "name": "Bat silhouette · 3 mm extrusion",
            "type": "sketch_extrude",
            "suppressed": False,
            "params": {
                "shape": "polyline",
                "points": outline(),
                "height": 3,
                "cx": 0,
                "cy": 0,
                "z": 0,
                "operation": "add",
            },
        }
    ]
    doc["annotations"] = [
        {
            "id": "print-note",
            "type": "text",
            "view": "sheet",
            "x": 55,
            "y": 625,
            "text": "76.2 mm = 3 in overall width | 3 mm thick | print flat, Z=0 | STL units: mm",
            "color": "#343943",
        }
    ]
    saved = json.loads(
        request(
            "/api/studio/documents",
            {
                "document": doc,
                "parent_id": brief["id"],
                "label": "02 · editable symmetric outline and extrusion",
            },
        )
    )
    dump(DEST / "history.json", {"brief_id": brief["id"], "cad_id": saved["id"]})
    verify_exports(saved["id"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        metavar="DOCUMENT_ID",
        help="Recheck an existing saved revision without creating a project",
    )
    args = parser.parse_args()
    if args.verify:
        verify_exports(args.verify)
    else:
        main()
