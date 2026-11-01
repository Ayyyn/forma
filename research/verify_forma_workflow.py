"""End-to-end shared-project, motion, revision and export checks; no model calls."""

import argparse
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8770/api/studio"


def call(path, data=None):
    req = urllib.request.Request(
        BASE + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = response.read()
        return (
            json.loads(raw)
            if "json" in response.headers.get("Content-Type", "")
            else raw
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    pointer = ROOT / "output/forma/studio/current.json"
    original = pointer.read_bytes() if pointer.exists() else None
    created = []
    checks = []

    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})
        (args.output / "partial.json").write_text(
            json.dumps(checks, indent=2), encoding="utf-8"
        )
        if not condition:
            raise AssertionError(name)

    spec = {
        "name": "QA shared folding enclosure",
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
        "payload_kg": 0,
        "lock_inner_dimensions": True,
        "objective": "minimize_mass",
        "max_floor_deflection_mm": 3,
    }
    doc = {
        "name": "QA workflow",
        "features": [],
        "metadata": {"brief": "A small portable enclosure; preserve clear dimensions."},
    }
    timings = []
    try:
        t = time.perf_counter()
        a = call(
            "/enclosure/preview", {"document": doc, "spec": spec, "requirements": req}
        )
        timings.append(
            {
                "operation": "initial_enclosure_preview",
                "ms": (time.perf_counter() - t) * 1000,
            }
        )
        check(
            "enclosure_brep_and_requirement_binding",
            a["passed"] and a["requirements_state"]["status"] == "current",
        )
        a = call(
            "/documents", {"document": a["document"], "label": "QA workflow baseline"}
        )
        created.append(a["id"])
        b = call(
            "/enclosure/preview",
            {
                "document": a["document"],
                "spec": {**spec, "thickness_mm": 4},
                "requirements": req,
            },
        )
        check(
            "thickness_updates_volume",
            b["metrics"]["volume_mm3"] > a["metrics"]["volume_mm3"],
        )
        check(
            "brief_and_requirement_preserved",
            b["document"]["metadata"]["brief"] == doc["metadata"]["brief"]
            and b["document"]["metadata"]["source_requirements"]["min_capacity_l"]
            == 0.2,
        )
        check("drawing_regenerated", b["drawing_svg"] != a["drawing_svg"])
        b = call(
            "/documents",
            {
                "document": b["document"],
                "parent_id": a["id"],
                "label": "QA thickness 4 mm",
            },
        )
        created.append(b["id"])
        check("revision_lineage", b["parent_id"] == a["id"])
        options = call(
            "/enclosure/options",
            {
                "document": b["document"],
                "spec": {**spec, "thickness_mm": 4},
                "requirements": req,
            },
        )
        check(
            "feasible_options_preserve_contract",
            bool(options["candidates"])
            and all(
                c["passed"]
                and c["requirements"]
                == b["document"]["metadata"]["source_requirements"]
                for c in options["candidates"]
            ),
        )
        t = time.perf_counter()
        study = call("/motion", {"document": b["document"]})
        timings.append(
            {"operation": "motion_37_samples", "ms": (time.perf_counter() - t) * 1000}
        )
        check(
            "finite_thickness_motion",
            study["sampled_overlap_free"]
            and abs(study["frames"][-1]["extent_mm"][2] - 8) < 1e-7,
        )
        check(
            "study_bound_to_geometry",
            study["geometry_signature"] == b["geometry_signature"],
        )
        configured = deepcopy(b["document"])
        configured["metadata"]["motion"] = study["config"]
        c = call(
            "/documents",
            {"document": configured, "parent_id": b["id"], "label": "QA attach motion"},
        )
        created.append(c["id"])
        check(
            "motion_settings_persist",
            call("/documents/" + c["id"])["document"]["metadata"]["motion"]
            == study["config"],
        )
        changed = deepcopy(configured)
        changed["features"][0]["params"]["width"] += 1
        stale = call("/preview", {"document": changed})
        check(
            "custom_edit_invalidates_requirement_results",
            stale["requirements_state"]["status"] == "stale"
            and not stale["requirements_state"]["checks"],
        )
        for route, payload in (
            ("/motion", {"document": changed}),
            (
                "/enclosure/preview",
                {"document": changed, "spec": spec, "requirements": req},
            ),
        ):
            try:
                call(route, payload)
                blocked = False
            except urllib.error.HTTPError as error:
                blocked = error.code == 422
            check("reject_stale_" + route.replace("/", "_"), blocked)
        restored = call(
            "/enclosure/preview",
            {
                "document": changed,
                "spec": spec,
                "requirements": req,
                "replace_geometry": True,
            },
        )
        check(
            "explicit_rebuild_restores_qualification",
            restored["requirements_state"]["status"] == "current",
        )
        undo = call("/undo", {"current_id": b["id"]})
        check(
            "undo_restores_thickness_and_binding",
            undo["id"] == a["id"]
            and undo["document"]["metadata"]["source_spec"]["thickness_mm"] == 3
            and undo["requirements_state"]["status"] == "current",
        )
        data = call("/documents/" + c["id"] + "/export/bundle")
        (args.output / "workflow-bundle.zip").write_bytes(data)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            report = json.loads(z.read("workflow-report.json"))
            hashes = json.loads(z.read("sha256.json"))
            check(
                "export_binds_report_to_revision",
                report["revision_id"] == c["id"]
                and report["geometry_signature"] == study["geometry_signature"],
            )
            check(
                "export_contains_current_motion",
                report["motion"]["status"] == "current"
                and report["motion"]["study"]["sampled_overlap_free"],
            )
            check(
                "bundle_hashes_match",
                all(
                    hashlib.sha256(z.read(name)).hexdigest() == digest
                    for name, digest in hashes.items()
                ),
            )
            panels = json.loads(z.read("panel-pack.json"))
            check(
                "separate_flat_panel_files",
                len(panels["panels"]) == 5
                and all(
                    p["stl_verified"]
                    and p["flat_size_mm"][2] == 4
                    and all(name in z.namelist() for name in p["files"])
                    for p in panels["panels"]
                ),
            )
            portable = json.loads(z.read("project.json"))
            check(
                "portable_project_retains_context",
                portable["document"]["metadata"] == configured["metadata"],
            )
        receipt = {
            "passed": all(c["passed"] for c in checks),
            "count": len(checks),
            "checks": checks,
            "timings": timings,
            "revision_ids": created,
        }
        (args.output / "results.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {"passed": receipt["passed"], "checks": len(checks), "timings": timings}
            )
        )
    finally:
        if (
            original is not None
            and pointer.exists()
            and json.loads(pointer.read_text())["id"] in created
        ):
            pointer.write_bytes(original)


if __name__ == "__main__":
    main()
