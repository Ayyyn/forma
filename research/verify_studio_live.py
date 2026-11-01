"""Frozen live integration tasks for human-reviewed feature-tree editing."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
import urllib.request
from crate_studio.workspace_server import DEFAULT_DOCUMENT

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8770/api/studio"
TASKS = [
    {
        "id": "dimension_edit",
        "prompt": "Set the base plate width to 160 mm. Set both mounting-hole radii to 10 mm. Keep the fillet radius, thickness, hole positions and all other features unchanged.",
        "expected": "ready",
    },
    {
        "id": "unsupported_analysis",
        "prompt": "Give me a certified fatigue safety factor for this part, with a nonlinear simulation.",
        "expected": "clarify",
    },
]


def dump(p, v):
    p.write_text(
        json.dumps(v, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )


def api(path, data=None):
    request = urllib.request.Request(
        BASE + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def prepare(folder):
    folder.mkdir(parents=True, exist_ok=False)
    dump(folder / "tasks.json", TASKS)
    dump(folder / "base-document.json", DEFAULT_DOCUMENT)
    paths = [
        ROOT / "crate_studio" / name
        for name in [
            "workspace_agent.py",
            "workspace_geometry.py",
            "workspace_server.py",
        ]
    ]
    dump(
        folder / "protocol.json",
        {
            "origin": "Constructed application integration tasks, not real designer cases or external benchmark",
            "model": "muse-wonder-1.0",
            "maximum_calls": 4,
            "apply": "Explicit API approval only after comparing changed parameters and preserved state",
            "physical_validation": False,
        },
    )
    dump(
        folder / "source-hashes.json",
        {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
        },
    )


def run(folder, resume=False):
    if (folder / "started.json").exists() and not resume:
        raise ValueError(
            "Previous run already started; resume reuses saved responses without repeating paid calls"
        )
    for name, digest in json.loads((folder / "source-hashes.json").read_text()).items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Source changed after freeze")
    if not resume:
        dump(folder / "started.json", {"started": True})
    base = json.loads((folder / "base-document.json").read_text())
    if resume and (folder / "dimension_edit.json").exists():
        prior = json.loads((folder / "dimension_edit.json").read_text())
        seed = api("/documents/" + prior["document_id"])
    else:
        seed = api(
            "/documents", {"document": base, "label": "Live Meta integration fixture"}
        )
    results = []
    for task in json.loads((folder / "tasks.json").read_text()):
        if (folder / (task["id"] + ".json")).exists():
            observed = json.loads((folder / (task["id"] + ".json")).read_text())
            job = {"id": observed["id"]}
        else:
            job = api("/agent", {"document_id": seed["id"], "prompt": task["prompt"]})
            deadline = time.monotonic() + 250
            while time.monotonic() < deadline:
                observed = api("/jobs/" + job["id"])
                if observed["status"] in ["completed", "failed"]:
                    break
                time.sleep(0.8)
        dump(folder / (task["id"] + ".json"), observed)
        errors = []
        proposal = observed.get("proposal", {})
        if (
            observed["status"] != "completed"
            or proposal.get("status") != task["expected"]
        ):
            errors.append(
                "Unexpected disposition: "
                + str(observed.get("error") or proposal.get("status"))
            )
        applied = None
        if task["id"] == "dimension_edit" and proposal.get("status") == "ready":
            expected = deepcopy(base)
            expected["features"][0]["params"]["width"] = 160
            expected["features"][2]["params"]["radius"] = 10
            expected["features"][3]["params"]["radius"] = 10
            if proposal["document"] != expected:
                errors.append(
                    "Unexpected modification outside the requested parameter changes"
                )
            if not proposal["snapshot"]["passed"]:
                errors.append("Proposed BREP fails verification")
            if not errors:
                applied = api("/proposals/" + job["id"] + "/apply", {})
                again = api("/proposals/" + job["id"] + "/apply", {})
                if applied["id"] != again["id"]:
                    errors.append("Approval is not idempotent")
                if not applied["passed"] or applied["document"] != expected:
                    errors.append("Saved approval differs from proposal")
        elif (
            task["id"] == "unsupported_analysis" and proposal.get("status") == "clarify"
        ):
            if proposal["document"] != base or not proposal.get("questions"):
                errors.append("Clarification changed document or omitted question")
        row = {
            "id": task["id"],
            "passed": not errors,
            "errors": errors,
            "job_id": job["id"],
            "status": proposal.get("status"),
            "calls": proposal.get("calls"),
            "response_ids": proposal.get("response_ids"),
            "estimated_cost_usd": proposal.get("estimated_cost_usd"),
            "applied_id": applied["id"] if applied else None,
        }
        results.append(row)
        dump(folder / "partial.json", results)
        print(json.dumps(row), flush=True)
    dump(
        folder / "results.json",
        {
            "passed": all(r["passed"] for r in results),
            "tasks": results,
            "scope": "Limited constructed feature-edit integration; no physical qualification or general model superiority claim.",
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["prepare", "run", "resume"])
    p.add_argument("--directory", required=True, type=Path)
    args = p.parse_args()
    if args.mode == "prepare":
        prepare(args.directory)
    else:
        run(args.directory, resume=args.mode == "resume")
