"""Prepare and hash evaluation tasks before any new model generations."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

from crate_studio.workspace_server import DEFAULT_DOCUMENT
from crate_studio.workspace_workflow import revise_enclosure

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "evaluation/forma-v1"
UPSTREAM = ROOT / "research/vendor/cad-bench"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main():
    DEST.mkdir(parents=True, exist_ok=False)
    plate = deepcopy(DEFAULT_DOCUMENT)
    spec = {
        "name": "Synthetic QA enclosure",
        "inner_width_mm": 90,
        "inner_depth_mm": 60,
        "inner_height_mm": 45,
        "thickness_mm": 3,
        "material": "polypropylene",
        "lid": False,
    }
    req = {
        "min_capacity_l": 0.2,
        "max_outer_width_mm": 160,
        "max_outer_depth_mm": 120,
        "max_outer_height_mm": 80,
        "max_mass_kg": 1,
        "lock_inner_dimensions": True,
        "objective": "minimize_mass",
        "payload_kg": 0,
        "max_floor_deflection_mm": 3,
    }
    enclosure = revise_enclosure(
        {
            "name": "QA",
            "features": [],
            "metadata": {
                "brief": "Synthetic small portable enclosure. Preserve clear dimensions."
            },
        },
        spec,
        req,
    )
    tasks = []

    def add(ident, prompt, base, expected, kind="features", selection=None):
        tasks.append(
            {
                "id": ident,
                "prompt": prompt,
                "document": deepcopy(base),
                "expected": expected,
                "kind": kind,
                "selection": selection or {},
            }
        )

    changes = [
        (
            "r01_width",
            "Set the base plate width to 160 mm. Preserve every other feature and parameter.",
            "plate",
            "width",
            160,
        ),
        (
            "r02_relative",
            "Increase the base plate width by 20 mm. Preserve every other feature and parameter.",
            "plate",
            "width",
            140,
        ),
        (
            "r03_holes",
            "Set both mounting-hole radii to 10 mm. Preserve hole positions and all other features and parameters.",
            "both",
            "radius",
            10,
        ),
        (
            "r04_fillet",
            "Change the corner fillet radius to 2 mm. Preserve all other features and parameters.",
            "corners",
            "radius",
            2,
        ),
        (
            "r05_hole_position",
            "Move the left mounting-hole center to X=-30 mm, Y=0 mm. Preserve its size and every other feature and parameter.",
            "left-hole",
            "x",
            -30,
        ),
        (
            "r06_units",
            "Set the base plate width to 6 inches. Convert to millimetres. Preserve all other features and parameters.",
            "plate",
            "width",
            152.4,
        ),
        (
            "r07_thickness",
            "Set the base plate thickness to 12 mm. Preserve the width, depth, hole radii, hole positions, fillet radius and every other feature parameter.",
            "plate",
            "height",
            12,
        ),
    ]
    for ident, prompt, target, key, value in changes:
        expected = deepcopy(plate)
        for f in expected["features"]:
            if f["id"] == target or (target == "both" and f["type"] == "cut_hole"):
                f["params"][key] = value
        add(ident, prompt, plate, {"status": "ready", "document": expected})
    expected = deepcopy(plate)
    expected["features"][0]["name"] = "Instrument base"
    add(
        "r08_rename",
        "Rename the base plate feature to Instrument base. Change nothing else.",
        plate,
        {"status": "ready", "document": expected},
    )
    expected = deepcopy(plate)
    expected["features"][3]["suppressed"] = True
    add(
        "r09_suppress",
        "Suppress the right mounting hole only. Preserve every other feature and parameter.",
        plate,
        {"status": "ready", "document": expected},
    )
    expected = deepcopy(plate)
    expected["features"].pop()
    add(
        "r10_delete",
        "Delete the right mounting-hole feature. Preserve every other feature and parameter.",
        plate,
        {"status": "ready", "document": expected},
    )
    for ident, prompt, patch in [
        (
            "r11_panel_thickness",
            "Change every enclosure panel from 3 mm to 4 mm. Preserve clear dimensions, requirements and brief.",
            {"thickness_mm": 4},
        ),
        (
            "r12_material",
            "Change the enclosure material to steel and all panel thicknesses to 2 mm. Preserve clear dimensions, requirements and brief.",
            {"material": "steel", "thickness_mm": 2},
        ),
        (
            "r13_height",
            "Set the enclosure internal clear height to 60 mm. Preserve every other specification field, all requirements and the brief.",
            {"inner_height_mm": 60},
        ),
        (
            "r14_lid",
            "Add the enclosure top panel. Preserve the existing clear dimensions, thickness, material, requirements and brief.",
            {"lid": True},
        ),
    ]:
        expected = revise_enclosure(enclosure, {**spec, **patch}, req)
        add(
            ident,
            prompt,
            enclosure,
            {"status": "ready", "document": expected},
            "enclosure",
        )
    for ident, prompt, base in [
        (
            "r15_nonstock",
            "Change all enclosure panel thicknesses to exactly 3.5 mm. Preserve all requirements, including configured stock. Do not substitute another thickness.",
            enclosure,
        ),
        (
            "r16_conflict",
            "Set enclosure internal clear width to 300 mm while preserving every existing requirement. Do not change the outside envelope limit.",
            enclosure,
        ),
        (
            "r17_unsupported",
            "Give me a certified fatigue safety factor for this part, using a nonlinear simulation.",
            plate,
        ),
        (
            "r18_ambiguous",
            "Make the enclosure better; choose the new dimensions for me. I have not decided what better means.",
            enclosure,
        ),
    ]:
        add(
            ident,
            prompt,
            base,
            {"status": "clarify", "document": deepcopy(base)},
            "clarify",
        )
    custom = deepcopy(enclosure)
    custom["features"].append(
        {
            "id": "custom-hole",
            "type": "cut_hole",
            "name": "Custom bottom hole",
            "params": {"radius": 2, "depth": 5, "x": 0, "y": 0, "z": -1},
            "suppressed": False,
        }
    )
    add(
        "r19_preserve_custom",
        "Change all enclosure panel thicknesses to 4 mm while preserving the custom hole and all requirements. Do not replace or discard custom geometry.",
        custom,
        {"status": "clarify", "document": deepcopy(custom)},
        "clarify",
    )
    add(
        "r20_add_hole",
        "Add a centered 6 mm diameter through-hole at X=0 mm, Y=0 mm along +Z through the base plate. Preserve all existing features and parameters.",
        plate,
        {
            "status": "ready",
            "preserved_features": deepcopy(plate["features"]),
            "new_hole": {"radius": 3, "x": 0, "y": 0},
            "removed_volume_mm3": 90 * 3.141592653589793,
        },
        "add_hole",
    )
    dump(DEST / "revision-tasks.json", tasks)
    selected = []
    excluded = []
    excludes = {
        "spur_gear_m1_z16_t6_bore5": "No involute gear feature; excluded before generation.",
        "m3x6_socket_head_zminus": "Threaded fastener/reference asset outside current declarative feature set.",
        "custom_threaded_pair_nonstandard": "Custom threads outside supported features.",
        "compound_gearbox_functional": "Blender functional simulation and gear mechanisms unavailable in this local subset.",
        "compound_right_angle_gearbox_reverse": "Blender functional simulation and gear mechanisms unavailable in this local subset.",
        "gearbox_functional_collision_trim": "Blender functional simulation and gear mechanisms unavailable in this local subset.",
    }
    upstream_files = {}
    for source in (UPSTREAM / "verifier").rglob("*.py"):
        upstream_files[source.relative_to(UPSTREAM).as_posix()] = digest(source)
    for folder in sorted((UPSTREAM / "dataset").iterdir()):
        if not folder.is_dir():
            continue
        if folder.name in excludes:
            excluded.append({"id": folder.name, "reason": excludes[folder.name]})
            continue
        raw = (folder / "instruction.md").read_text(encoding="utf-8")
        prompt = (
            raw.split("Submission contract")[0].strip()
            + "\n\nConstruct this geometry using Forma's declarative feature editor. Preserve all specified dimensions and placement. Return the editor's JSON proposal; do not write Python code."
        )
        contract = tomllib.loads((folder / "contract.toml").read_text(encoding="utf-8"))
        selected.append(
            {
                "id": folder.name,
                "prompt": prompt,
                "original_instruction": raw,
                "difficulty": contract["difficulty"],
                "document": {
                    "name": folder.name.replace("_", " ")[:100],
                    "features": [],
                    "metadata": {},
                },
                "expected": contract["expected"],
                "reference_geometry_gate": contract.get(
                    "reference_geometry_gate", False
                ),
            }
        )
        for name in ("instruction.md", "contract.toml", "solution/gold.py"):
            p = folder / name
            upstream_files[p.relative_to(UPSTREAM).as_posix()] = digest(p)
    dump(DEST / "public-tasks.json", selected)
    (DEST / "CAD-BENCH-LICENSE.txt").write_text(
        (UPSTREAM / "LICENSE").read_text(), encoding="utf-8"
    )
    protocol = {
        "version": "forma-eval-v1",
        "constructed_revision_tasks": 20,
        "public_geometry_tasks": len(selected),
        "upstream_total_public_tasks": 17,
        "excluded": excluded,
        "upstream_repo": "https://github.com/CAD-bench/cad-bench",
        "upstream_commit": subprocess.check_output(
            ["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"]
        )
        .decode()
        .strip(),
        "upstream_file_hashes": upstream_files,
        "selection_rule": "All 11 static primitive/profile geometry tasks; exclude six gear/thread/Blender functional tasks before generations. No result-based exclusions.",
        "adaptation": "Original geometric instructions retained; replace Build123D final.py submission footer with Forma JSON editor format. Export STEP and invoke unmodified upstream evaluate_step, including reference geometry gates. Local Windows Python 3.12 instead of Linux Python 3.11/Harbor; not an official full benchmark score.",
        "model": "muse-wonder-1.0",
        "temperature": 0.15,
        "max_tokens": 4096,
        "maximum_calls_per_task": 2,
        "first_pass": "Derived from the same initial response, independently scored before any repair; not an independently sampled baseline.",
        "budget": "Existing shared $5 conservative application cap, no automatic increase.",
        "revision_success": "Expected disposition; clarified tasks leave document unchanged with questions. Ready tasks preserve unrequested state and match independent expected BREP bounds/volume, then pass STEP/STL readback. Add-hole permits generated feature ID/name but checks preservation, location, through depth and removed volume.",
        "public_success": "Unmodified upstream overall_score >= 0.95 with build_success=1.0, reported alongside continuous score. Threshold fixed before generations. Scores do not establish physical suitability.",
        "contamination": "Public development tasks, inspected for compatibility. Not held out. Reference code and expected answers are not sent to the model. No training is performed.",
        "reruns": "Keep every response and failure. Never overwrite a run. Repairs after inspecting failures are labeled development reruns; no held-out claim.",
    }
    dump(DEST / "protocol.json", protocol)
    files = [p for p in DEST.iterdir() if p.is_file()]
    dump(DEST / "manifest.json", {p.name: digest(p) for p in files})
    print(
        json.dumps(
            {
                "revision_tasks": len(tasks),
                "public_tasks": len(selected),
                "directory": str(DEST),
            }
        )
    )


if __name__ == "__main__":
    main()
