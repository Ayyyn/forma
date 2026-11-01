"""One live Meta task: global thickness propagation in the shared Studio workflow."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import time

from .verify_forma_workflow import call, ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    task = {
        "prompt": "Change every enclosure panel from 3 mm to 4 mm, preserving the internal dimensions and every requirement. Keep the project brief.",
        "expected_thickness_mm": 4,
        "scope": "One constructed live integration task, not an external benchmark.",
    }
    (args.output / "task.json").write_text(json.dumps(task, indent=2), encoding="utf-8")
    pointer = ROOT / "output/forma/studio/current.json"
    original = pointer.read_bytes() if pointer.exists() else None
    owned = []
    try:
        spec = {
            "name": "QA live shared enclosure",
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
        preview = call(
            "/enclosure/preview",
            {
                "document": {
                    "name": "QA live",
                    "features": [],
                    "metadata": {"brief": "Small enclosure for a physical fit mockup."},
                },
                "spec": spec,
                "requirements": req,
            },
        )
        base = call(
            "/documents",
            {"document": preview["document"], "label": "QA live workflow base"},
        )
        owned.append(base["id"])
        job = call("/agent", {"document_id": base["id"], "prompt": task["prompt"]})
        deadline = time.monotonic() + 300
        while job["status"] in ("queued", "running"):
            if time.monotonic() > deadline:
                raise TimeoutError(
                    "Live job still running; inspect the retained job ID before making another request"
                )
            time.sleep(1)
            job = call("/jobs/" + job["id"])
            (args.output / "job.json").write_text(
                json.dumps(job, indent=2), encoding="utf-8"
            )
        if job["status"] != "completed":
            raise AssertionError(job.get("error", job["status"]))
        proposal = job["proposal"]
        doc = proposal.get("document", {})
        meta = doc.get("metadata", {})
        before = base["document"]["metadata"]
        checks = {
            "ready": proposal["status"] == "ready",
            "thickness_updated": meta.get("source_spec", {}).get("thickness_mm") == 4,
            "dimensions_preserved": all(
                meta.get("source_spec", {}).get(k) == spec[k]
                for k in ("inner_width_mm", "inner_depth_mm", "inner_height_mm")
            ),
            "requirements_preserved": meta.get("source_requirements")
            == before["source_requirements"],
            "brief_preserved": meta.get("brief") == before["brief"],
            "qualification_current": proposal.get("snapshot", {})
            .get("requirements_state", {})
            .get("status")
            == "current",
        }
        if all(checks.values()):
            applied = call("/proposals/" + job["id"] + "/apply", {})
            owned.append(applied["id"])
            checks["revision_applied"] = (
                applied["parent_id"] == base["id"]
                and applied["document"]["metadata"]["source_spec"]["thickness_mm"] == 4
            )
        report = {
            "passed": all(checks.values()),
            "checks": checks,
            "job_id": job["id"],
            "model": proposal.get("model"),
            "estimated_cost_usd": proposal.get("estimated_cost_usd"),
            "response_ids": proposal.get("response_ids"),
            "scope": task["scope"],
        }
        (args.output / "results.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report))
        if not report["passed"]:
            raise AssertionError("Live task failed; see saved results")
    finally:
        if (
            original is not None
            and pointer.exists()
            and json.loads(pointer.read_text())["id"] in owned
        ):
            pointer.write_bytes(original)


if __name__ == "__main__":
    main()
