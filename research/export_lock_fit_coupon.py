"""Extract a short, unchanged guide/pin cross-section for physical print-fit QA.

Developer-authored test fixture from existing model CAD, not a new model design
or proof of friction. The full box and its editable feature history are retained.
"""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import cadquery as cq

from crate_studio.workspace_geometry import build_document, _mesh
from crate_studio.component_exports import export_components
from crate_studio.mechanism_study import moved_parts, pose_matrices, mechanism_study
from crate_studio.motion_probe import translation_probe


def run(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    raw = json.loads(source.read_text(encoding="utf-8"))
    document = raw.get("document", raw)
    spec = document["metadata"]["design_mechanism"]
    state = next(state for state in spec["states"] if state["name"] == "medium_locked")
    built = build_document(document)
    posed = moved_parts(built["parts"], pose_matrices(spec, state["values"]))
    pin_joint = next(joint for joint in spec["joints"] if joint["id"] == "pin_z")
    slide_joint = next(joint for joint in spec["joints"] if joint["id"] == "se_x")
    ids = [slide_joint["parent"], slide_joint["child"], pin_joint["child"]]
    pin = next(part["shape"] for part in posed if part["id"] == pin_joint["child"])
    box = pin.BoundingBox()
    center = [(box.xmin + box.xmax) / 2, (box.ymin + box.ymax) / 2]
    # The receiver's lips join its wall through the end web. A short central
    # crop disconnects them; retain that real web instead of adding a brace.
    clip_size = [114, 32, 50]
    clip = cq.Workplane("XY").box(*clip_size, centered=(True, True, False)).translate((*center, 0)).val()
    parts = [{"id": part["id"], "name": part.get("name", part["id"]),
              "shape": part["shape"].intersect(clip)} for part in posed if part["id"] in ids]
    if any(len(part["shape"].Solids()) != 1 or not part["shape"].isValid() for part in parts):
        raise ValueError("Coupon clipping did not retain exactly one valid solid per component")
    # Coupon source coordinates are the model's medium-locked posed coordinates.
    coupon_spec = {"root": ids[0], "joints": [
        {"id": "slide", "parent": ids[0], "child": ids[1], "type": "prismatic",
         "axis": [1, 0, 0], "origin": [0, 0, 0], "limits": [-1, 1]},
        {"id": "pin", "parent": ids[1], "child": ids[2], "type": "prismatic",
         "axis": [0, 0, 1], "origin": [0, 0, 0], "limits": [0, 5.5]}],
        "states": [{"name": name, "values": {"slide": slide, "pin": pin}}
                   for name, slide, pin in [("locked", 0, 0), ("unlocked", 0, 5.5),
                     ("slide_positive", 1, 5.5), ("return_unlocked", 0, 5.5), ("relocked", 0, 0)]],
        "connections": [], "samples_per_segment": 19}
    probes = []
    for state_name in ("locked", "unlocked"):
        for sign in (-1, 1):
            report = translation_probe(parts, ids[1:], [sign, 0, 0], 1, 21, coupon_spec, state_name)
            if not report["initial_pose_clear"] or report["path_clear_at_samples"] != (state_name == "unlocked"):
                raise ValueError("Clipped fixture does not retain the model's lock/unlock contrast")
            probes.append({key: value for key, value in report.items() if key != "mechanism_spec"})
    study = mechanism_study(document, {"parts": parts, "checks": {"passed": True}}, coupon_spec)
    if not study["passed"]:
        raise ValueError("Clipped fixture has a failed unlock-slide-relock path")
    components = export_components({"parts": parts, "checks": {"passed": True},
                                    "mesh": [{"id": part["id"], **_mesh(part["shape"])} for part in parts]}, destination)
    with zipfile.ZipFile(destination / "components.zip") as meshes:
        for row in components["parts"]:
            (destination / row["file"]).write_bytes(meshes.read(row["file"]))
    assembly = cq.Compound.makeCompound([part["shape"] for part in parts])
    cq.exporters.export(assembly, str(destination / "coupon.step"))
    reopened = cq.importers.importStep(str(destination / "coupon.step")).val()
    if len(reopened.Solids()) != 3 or abs(reopened.Volume() - assembly.Volume()) > 1e-5:
        raise ValueError("Coupon STEP readback differs from native CAD")
    report = {"source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "cad_author": "Muse Wonder", "fixture_author": "Developer native extraction",
              "extraction_state": "medium_locked", "clip_center_xy_mm": center,
              "clip_size_mm": clip_size, "parts": components,
              "coupon_spec": coupon_spec, "motion_samples": study["sample_count"],
              "motion_passed": study["passed"], "probes": probes,
              "friction_verified": False, "physical_validation": False,
              "scope": "Clipped source solids with original guide/slot/pin clearances. Three separate parts, short local travel only. Does not test full-box stroke, other axes, end stops, material, supports, friction, pin captivity, force or structural strength."}
    (destination / "coupon-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (destination / "source-project.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    (destination / "README.txt").write_text(
        "FORMA / MODEL GUIDE-AND-PIN FIT COUPON\n\n"
        "Three separate STL parts, mm units. Original assembly coordinates are retained.\n"
        "body-001.stl: stationary guide; body-002.stl: receiver; body-003.stl: lock pin.\n"
        "Arrange each component separately in a slicer; do not print the assembly as one object.\n"
        "Use the planned box material and settings. Inspect orientation/support needs; flat floor\n"
        "faces and the pin's flat head are useful bed faces. Printer/material fit is unverified.\n\n"
        "1. Record printer, nozzle, layer height, material, orientation and support cleanup.\n"
        "2. Assemble the two guide sections from an open end and insert the pin at the detent.\n"
        "3. Raise the pin 5.5 mm; check at least 1 mm sliding in both directions without binding.\n"
        "4. Lower the pin fully; check that size motion is positively obstructed. Do not force it.\n"
        "5. Record free sliding force with a force gauge if available, play, stick-slip and wear.\n"
        "6. Repeat cycles and inspect pin retention before moving to the full box.\n\n"
        "This is a developer-extracted short section of Muse's actual medium-size mechanism.\n"
        "It preserves geometry; it is not a new AI design, full-box test or measured friction model.\n"
        "Do not infer a friction coefficient from sliding force without knowing contact preload.\n",
        encoding="utf-8")
    with zipfile.ZipFile(destination / "fit-coupon.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(destination.iterdir()):
            if path.is_file() and path.name not in ("fit-coupon.zip", "components.zip"):
                archive.write(path, path.name)
    print(json.dumps({"parts": len(components["parts"]), "exports_passed": components["passed"],
                      "motion_samples": study["sample_count"], "matched_controls": len(probes),
                      "physical_validation": False}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    run(args.source, args.destination)
