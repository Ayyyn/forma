"""Independent native bodies as separate meshes; never union movable parts."""

import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import trimesh

from .workspace_geometry import _bounds


def export_components(built, destination):
    if not built["checks"]["passed"]:
        raise ValueError("Separate-body export requires valid native geometry")
    folder = Path(destination)
    folder.mkdir(parents=True, exist_ok=True)
    rows, payloads = [], {}
    for part, source in zip(built["parts"], built["mesh"], strict=True):
        if source["id"] != part["id"]:
            raise ValueError("Native body and cached mesh identities differ")
        # Reuse the native tessellation already built for inspection. Read the
        # serialized STL back and compare to the source BREP independently.
        mesh = trimesh.Trimesh(
            np.array(source["vertices"]).reshape(-1, 3),
            np.array(source["triangles"]).reshape(-1, 3),
            process=True,
        )
        filename = f"body-{len(rows) + 1:03d}.stl"
        payloads[filename] = mesh.export(file_type="stl")
        import io

        reopened = trimesh.load(
            io.BytesIO(payloads[filename]), file_type="stl", force="mesh", process=True
        )
        volume = float(part["shape"].Volume())
        bounds = _bounds(part["shape"])
        delta = float(np.max(np.abs(reopened.bounds - np.array(bounds))))
        volume_error = abs(float(reopened.volume) - volume)
        passed = bool(
            reopened.is_volume
            and reopened.is_watertight
            and reopened.is_winding_consistent
            and delta <= 0.3
            and volume_error <= max(1e-5, volume * 0.01)
        )
        rows.append(
            {
                "id": part["id"],
                "name": part.get("name", part["id"]),
                "file": filename,
                "sha256": hashlib.sha256(payloads[filename]).hexdigest(),
                "native_volume_mm3": volume,
                "bounds_mm": bounds,
                "bounds_error_mm": delta,
                "volume_error_mm3": volume_error,
                "bounds_tolerance_mm": 0.3,
                "volume_tolerance_mm3": max(1e-5, volume * 0.01),
                "watertight": bool(reopened.is_watertight),
                "passed": passed,
            }
        )
    manifest = {
        "format": "forma-components/v1",
        "units": "mm by convention; STL has no unit field",
        "passed": bool(rows) and all(r["passed"] for r in rows),
        "parts": rows,
        "source_pose": True,
        "print_ready": False,
        "scope": "Each native body remains a separate STL, including touching or overlapping bodies. Original coordinates are preserved; no build-plate layout, support/orientation, fit, assembly or printer/material qualification is implied. Separate and orient parts in a slicer; assembled workspace.stl is a geometric union and can fuse movable interfaces.",
    }
    (folder / "components.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    if not manifest["passed"]:
        raise ValueError("Separate-body STL read-back verification failed")
    with zipfile.ZipFile(
        folder / "components.zip", "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for name, data in payloads.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
        info = zipfile.ZipInfo("components.json", date_time=(1980, 1, 1, 0, 0, 0))
        archive.writestr(
            info,
            (folder / "components.json").read_bytes(),
            compress_type=zipfile.ZIP_DEFLATED,
        )
    return manifest
