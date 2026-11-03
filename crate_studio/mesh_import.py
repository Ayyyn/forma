"""Bounded, unit-explicit mesh to faceted native solid conversion.

No remeshing, hole filling, texture access, code execution or guessed units.
Original bytes remain in the private source-asset store at the API boundary.
"""

import io
import hashlib
from pathlib import Path
from importlib.metadata import version as package_version

import cadquery as cq
import numpy as np
import trimesh
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid

MAX_FACES = 2500
UNIT_SCALE = {"mm": 1.0, "cm": 10.0, "inch": 25.4, "m": 1000.0}
CONVERSION_VERSION = hashlib.sha256(
    Path(__file__).read_bytes()
    + cq.__version__.encode()
    + trimesh.__version__.encode()
    + package_version("cadquery-ocp").encode()
).hexdigest()[:16]


def import_mesh(data, file_type, units):
    if file_type not in ("stl", "obj"):
        raise ValueError("Mesh import supports STL and OBJ")
    if units not in UNIT_SCALE:
        raise ValueError("Choose mesh units explicitly: mm, cm, inch or m")
    mesh = trimesh.load(
        io.BytesIO(data),
        file_type=file_type,
        force="mesh",
        process=True,
        skip_materials=True,
    )
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError("The file contains no triangle mesh")
    if len(mesh.faces) > MAX_FACES:
        raise ValueError(
            f"Mesh has {len(mesh.faces):,} triangles; the editable faceted-solid limit is {MAX_FACES:,}. Use STEP or simplify the mesh before import."
        )
    if not np.isfinite(mesh.vertices).all():
        raise ValueError("Mesh coordinates must be finite")
    mesh.apply_scale(UNIT_SCALE[units])
    if np.max(np.abs(mesh.vertices)) > 10000:
        raise ValueError(
            "Converted mesh exceeds the 10,000 mm coordinate limit; check units"
        )
    if not mesh.is_watertight or not mesh.is_winding_consistent or not mesh.is_volume:
        raise ValueError(
            "Import requires a closed, consistently oriented solid mesh. Open surfaces need repair before CAD conversion."
        )
    components = mesh.split(only_watertight=False)
    if len(components) > 50:
        raise ValueError("Mesh import supports at most 50 independent components")
    solids = []
    for component in components:
        # Sew each original connected component independently. A global sewer
        # can turn overlapping closed shells into one nominally valid solid;
        # volume alone then misses the component interference.
        sewing = BRepBuilderAPI_Sewing(1e-7)
        for triangle in component.triangles:
            wire = cq.Wire.makePolygon(
                [cq.Vector(*p) for p in [*triangle, triangle[0]]]
            )
            sewing.Add(cq.Face.makeFromWires(wire).wrapped)
        sewing.Perform()
        sewn = cq.Shape.cast(sewing.SewedShape())
        shells = sewn.Shells()
        if len(shells) != 1 or not shells[0].Closed():
            raise ValueError(
                "An original mesh component did not sew to exactly one closed shell"
            )
        shell = shells[0]
        maker = BRepBuilderAPI_MakeSolid(shell.wrapped)
        if not maker.IsDone():
            raise ValueError("Could not close the mesh shell as a CAD solid")
        solid = cq.Solid(maker.Solid())
        if solid.Volume() < 0:
            solid = cq.Solid(solid.wrapped.Reversed())
        if not solid.isValid() or solid.Volume() <= 0:
            raise ValueError(
                "Mesh does not form a valid non-self-intersecting CAD solid"
            )
        try:
            simplified = solid.copy().clean()
            if simplified.isValid() and abs(simplified.Volume() - solid.Volume()) < max(
                1e-6, solid.Volume() * 1e-8
            ):
                solid = simplified
        except Exception:
            pass
        solids.append(solid)
    for i, solid in enumerate(solids):
        for other in solids[:i]:
            a, b = solid.BoundingBox(), other.BoundingBox()
            if all(
                min(getattr(a, k + "max"), getattr(b, k + "max"))
                > max(getattr(a, k + "min"), getattr(b, k + "min")) + 1e-7
                for k in "xyz"
            ):
                if abs(solid.intersect(other).Volume()) > 1e-5:
                    raise ValueError(
                        "Mesh components overlap; provide disjoint solids or a properly united STEP model"
                    )
    # Nested cavity shells need signed-shell assembly, not independent positive
    # solids. Fail the independent mesh-volume check rather than fill cavities.
    volume = sum(s.Volume() for s in solids)
    if (
        not solids
        or len(solids) > 50
        or abs(volume - abs(mesh.volume)) > max(1e-5, abs(mesh.volume) * 1e-6)
    ):
        raise ValueError(
            "Mesh-to-solid volume mismatch; nested cavities or ambiguous shells require STEP"
        )
    bounds = np.asarray(
        [
            [
                min(s.BoundingBox().xmin for s in solids),
                min(s.BoundingBox().ymin for s in solids),
                min(s.BoundingBox().zmin for s in solids),
            ],
            [
                max(s.BoundingBox().xmax for s in solids),
                max(s.BoundingBox().ymax for s in solids),
                max(s.BoundingBox().zmax for s in solids),
            ],
        ]
    )
    if np.max(np.abs(bounds - mesh.bounds)) > 1e-5:
        raise ValueError("Mesh-to-solid bounds changed unexpectedly")
    return cq.Compound.makeCompound(solids), {
        "source_format": file_type,
        "source_units": units,
        "conversion_to_mm": UNIT_SCALE[units],
        "converter_version": CONVERSION_VERSION,
        "triangles": len(mesh.faces),
        "solid_count": len(solids),
        "volume_mm3": volume,
        "bounds_mm": bounds.tolist(),
        "representation": "Faceted native BREP from the exact supplied triangles; not recovered design history or smooth-surface reconstruction",
    }
