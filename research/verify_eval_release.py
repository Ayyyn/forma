"""Read-only/local release checks for demo, benchmark receipts and downloads."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

from .run_forma_eval import ROOT, load, dump, verify_freeze


def request(path, data=None):
    req = urllib.request.Request(
        "http://127.0.0.1:8770" + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    checks = []

    def check(name, value):
        checks.append({"check": name, "passed": bool(value)})
        dump(args.output / "partial.json", checks)
        if not value:
            raise AssertionError(name)

    verify_freeze()
    check("frozen_tasks_and_upstream_unchanged", True)
    report = request("/evaluation").decode()
    check(
        "review_includes_initial_failures_and_scope",
        all(
            s in report
            for s in (
                "19/20",
                "10/11",
                "0.9883",
                "0.8713",
                "not a fresh 20/20",
                "not an official full benchmark",
            )
        ),
    )
    summary = load(ROOT / "output/forma/evaluation/summary.json")
    archive = request("/evaluation-evidence")
    check(
        "evidence_download_hash",
        hashlib.sha256(archive).hexdigest() == summary["evidence_sha256"],
    )
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        hashes = json.loads(z.read("sha256.json"))
        check(
            "all_evidence_file_hashes",
            all(
                hashlib.sha256(z.read(name)).hexdigest() == sha
                for name, sha in hashes.items()
            ),
        )
    demo = load(ROOT / "output/forma/demo-v1/manifest.json")
    docs = [
        json.loads(request("/api/studio/documents/" + s["id"])) for s in demo["stages"]
    ]
    check(
        "demo_history_lineage",
        len(docs) == 4
        and all(docs[i]["parent_id"] == docs[i - 1]["id"] for i in range(1, 4)),
    )
    check(
        "meta_thickness_revision_preserves_contract",
        docs[0]["document"]["metadata"]["source_spec"]["thickness_mm"] == 3
        and docs[1]["document"]["metadata"]["source_spec"]["thickness_mm"] == 4
        and docs[0]["document"]["metadata"]["source_requirements"]
        == docs[1]["document"]["metadata"]["source_requirements"],
    )
    final = docs[-1]
    check(
        "human_edit_and_qualification",
        final["document"]["metadata"]["source_spec"]["inner_height_mm"] == 50
        and final["requirements_state"]["status"] == "current"
        and final["requirements_state"]["passed"],
    )
    motion = json.loads(request("/api/studio/motion", {"document": final["document"]}))
    check(
        "demo_motion_and_flat_envelope",
        motion["sampled_overlap_free"]
        and all(
            abs(a - b) < 1e-6
            for a, b in zip(motion["frames"][-1]["extent_mm"], [198, 168, 8])
        ),
    )
    package = request("/demo-package")
    check(
        "demo_package_download_hash",
        hashlib.sha256(package).hexdigest() == demo["package_sha256"],
    )
    with zipfile.ZipFile(io.BytesIO(package)) as z:
        panel_pack = json.loads(z.read("panel-pack.json"))
        workflow = json.loads(z.read("workflow-report.json"))
        check(
            "five_flat_print_components",
            len(panel_pack["panels"]) == 5
            and all(
                p["stl_verified"] and p["flat_size_mm"][2] == 4
                for p in panel_pack["panels"]
            ),
        )
        check(
            "export_report_binds_revision_and_motion",
            workflow["revision_id"] == final["id"]
            and workflow["geometry_signature"] == final["geometry_signature"]
            and workflow["motion"]["status"] == "current",
        )
    initial = load(ROOT / "output/forma/evaluation/v1/results.json")
    rerun = load(ROOT / "output/forma/evaluation/v2-repair/results.json")
    check(
        "reported_counts_match_receipts",
        len(initial["rows"]) == 31
        and summary["actual_model_responses"]
        == sum(r["calls"] for r in initial["rows"] + rerun["rows"])
        == 33,
    )
    for label in ("v1", "v2-repair"):
        folder = ROOT / "output/forma/evaluation" / label
        manifest = load(folder / "run-manifest.json")
        check(
            "exact_source_snapshot_" + label,
            all(
                hashlib.sha256(
                    (folder / "source-snapshot" / name).read_bytes()
                ).hexdigest()
                == sha
                for name, sha in manifest["source_hashes"].items()
            ),
        )
    result = {
        "passed": all(c["passed"] for c in checks),
        "count": len(checks),
        "checks": checks,
        "model_calls": 0,
    }
    dump(args.output / "results.json", result)
    print(json.dumps({"passed": result["passed"], "checks": len(checks)}))


if __name__ == "__main__":
    main()
