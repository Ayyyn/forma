"""Create a reviewable demo history using a retained, verified real Meta response."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
import urllib.request

from crate_studio.engine import optimize
from crate_studio.workspace_server import save_document
from crate_studio.workspace_workflow import revise_enclosure, motion_study
from .run_forma_eval import FROZEN, load, dump

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "output/forma/demo-v1"


def main():
    DEST.mkdir(parents=True, exist_ok=False)
    task = next(
        t
        for t in load(FROZEN / "revision-tasks.json")
        if t["id"] == "r11_panel_thickness"
    )
    source = ROOT / "output/forma/evaluation/v1/r11_panel_thickness"
    result = load(source / "result.json")
    proposal = load(source / "proposal.json")
    if not result["verified"]["passed"]:
        raise ValueError("Retained Meta revision did not pass")
    if proposal["document"] != task["expected"]["document"]:
        raise ValueError("Proposal differs from approved expected revision")
    lock = threading.RLock()
    stages = []

    def save(doc, label, parent=None, provenance=None):
        row = save_document(
            doc, lock, parent_id=parent, label=label, provenance=provenance
        )
        stages.append(
            {
                "id": row["id"],
                "label": label,
                "parent_id": parent,
                "geometry_signature": row["geometry_signature"],
            }
        )
        return row

    base = save(task["document"], "Demo 01 · brief, requirements and 3 mm panels")
    meta = task["document"]["metadata"]
    options = optimize(meta["source_spec"], meta["source_requirements"])
    dump(DEST / "design-options.json", options)
    ai = save(
        proposal["document"],
        "Demo 02 · Meta: 3 → 4 mm, requirements preserved",
        base["id"],
        {
            "model": proposal["model"],
            "run_id": proposal["run_id"],
            "response_ids": proposal["response_ids"],
            "source": "Retained real frozen-evaluation response, applied to its exact approved base. No additional model call.",
        },
    )
    doc = deepcopy(ai["document"])
    doc["metadata"][
        "brief"
    ] = "A small folding instrument-case mockup. Preserve at least 0.2 L usable capacity and a 160 × 120 × 80 mm closed envelope. Compare stock thicknesses, retain human editing, and inspect prescribed wall motion before preparing separate panel components. Virtual hinge hardware and load qualification remain to be designed."
    doc = revise_enclosure(
        doc,
        {
            **doc["metadata"]["source_spec"],
            "name": "Foldable instrument case",
            "inner_height_mm": 50,
        },
        doc["metadata"]["source_requirements"],
    )
    human = save(doc, "Demo 03 · human: 50 mm clear height and project brief", ai["id"])
    study = motion_study(doc)
    dump(DEST / "motion-study.json", study)
    doc["metadata"]["motion"] = study["config"]
    final = save(
        doc, "Demo 04 · motion checked and fabrication package ready", human["id"]
    )
    with urllib.request.urlopen(
        f"http://127.0.0.1:8770/api/studio/documents/{final['id']}/export/bundle",
        timeout=120,
    ) as response:
        data = response.read()
    (DEST / "instrument-case-package.zip").write_bytes(data)
    manifest = {
        "stages": stages,
        "final_document_id": final["id"],
        "url": f"http://127.0.0.1:8770/studio?document={final['id']}&view=canvas",
        "real_meta_response_ids": proposal["response_ids"],
        "model_calls_added_by_demo": 0,
        "source_evaluation_task": "r11_panel_thickness",
        "feasible_design_options": len(options["candidates"]),
        "top_three_specs": [c["spec"] for c in options["candidates"][:3]],
        "closed_envelope_mm": study["frames"][0]["extent_mm"],
        "flat_envelope_mm": study["frames"][-1]["extent_mm"],
        "motion_overlap_free_at_samples": study["sampled_overlap_free"],
        "package_sha256": hashlib.sha256(data).hexdigest(),
        "physical_validation": "pending",
    }
    dump(DEST / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
