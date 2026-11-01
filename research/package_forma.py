"""Curated source handoff. No credentials, runtimes or unrelated experiments."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile
from scripts.api_preflight import load_env

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/forma"


def main(name="forma-source.zip"):
    if Path(name).name != name or not name.endswith(".zip"):
        raise ValueError("Source package name must be a ZIP filename")
    files = [
        p
        for p in (ROOT / "crate_studio").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ]
    files += list((ROOT / "tests").glob("test_crate_*.py"))
    files += list((ROOT / "tests").glob("test_workspace_*.py"))
    files += [
        ROOT / "tests/test_forma_eval.py",
        ROOT / "requirements-cadbench-lock.txt",
        ROOT / "examples/forma-instrument-case.json",
    ]
    files += [p for p in (ROOT / "evaluation/forma-v1").rglob("*") if p.is_file()]
    protocol = json.loads(
        (ROOT / "evaluation/forma-v1/protocol.json").read_text(encoding="utf-8")
    )
    files += [
        ROOT / "research/vendor/cad-bench" / name
        for name in protocol["upstream_file_hashes"]
    ]
    files += [ROOT / "research/vendor/cad-bench/LICENSE"]
    files += list((ROOT / "examples").glob("forma-batman-*.json"))
    files += [
        ROOT / name
        for name in [
            "docs/FORMA_PERFORMANCE.md",
            "docs/FORMA_BATMAN_DEMO.md",
            "research/forma_performance.py",
            "research/forma_performance_report.py",
            "research/verify_forma_cache_http.py",
            "research/verify_forma_cache_replay.py",
            "research/build_batman_demo.py",
            "research/verify_batman_attachment.py",
        ]
    ]
    files += [
        ROOT / p
        for p in [
            "docs/FORMA_STUDIO.md",
            "research/verify_studio_http.py",
            "research/verify_studio_live.py",
            "research/fetch_studio_assets.py",
            "research/studio_report.py",
            "research/profile_forma.py",
            "research/verify_forma_workflow.py",
            "research/verify_forma_workflow_live.py",
            "docs/FORMA_BUILD_PLAN.md",
            "docs/FORMA_PROGRESS.md",
            "docs/FORMA_WORKFLOW.md",
            "docs/FORMA_EVALUATION.md",
            "docs/FORMA_DEMO_SCRIPT.md",
            "research/freeze_forma_eval.py",
            "research/run_forma_eval.py",
            "research/cadbench_score.py",
            "research/verify_cadbench_oracles.py",
            "research/verify_slot_interpretation.py",
            "research/build_forma_demo.py",
            "research/forma_eval_report.py",
            "research/verify_eval_release.py",
        ]
    ]
    files += [
        ROOT / p
        for p in [
            "requirements-forma.txt",
            "requirements-forma-lock.txt",
            "scripts/api_preflight.py",
            "docs/FORMA_DEMO.md",
            "research/verify_forma_live.py",
            "research/verify_forma_http.py",
            "research/forma_report.py",
            "research/package_forma.py",
            "research/crate_studio_evaluation_sources.json",
            "research/forma_resolved_issues.json",
        ]
    ]
    load_env()
    secrets = [
        v.encode()
        for k, v in os.environ.items()
        if k
        in ["MODEL_API_KEY", "META_API_KEY", "BASETEN_API_KEY", "MODAL_TOKEN_SECRET"]
        and v
    ]
    hashes = {}
    for p in files:
        if p.name.startswith(".env"):
            raise ValueError("Environment files must not enter source package")
        data = p.read_bytes()
        if any(secret in data for secret in secrets):
            raise ValueError("Credential value detected; source package not created")
        hashes[p.relative_to(ROOT).as_posix()] = hashlib.sha256(data).hexdigest()
    destination = OUT / name
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):
            z.write(p, p.relative_to(ROOT).as_posix())
        z.writestr(
            "README.md",
            "# Forma CAD\n\nCreate a Python 3.12 environment, install requirements-forma.txt and run `python -m crate_studio`. Open http://127.0.0.1:8770/studio. Import examples/forma-instrument-case.json for the editable demo without model calls.\n\nRead docs/FORMA_WORKFLOW.md, docs/FORMA_DEMO_SCRIPT.md and docs/FORMA_EVALUATION.md. Frozen evaluation tasks, scoring controls and selected upstream CAD-bench verifier/reference files are included. Use a SEPARATE environment with requirements-cadbench-lock.txt for external STEP scoring; its OpenCascade version differs from Forma. Evidence is a separate download; model reruns require credentials and make paid requests.\n\nRun `python -m unittest discover -s tests -p test_*.py -v` for offline checks. Third-party browser assets and CAD-bench sources retain their bundled MIT licenses. Previous-work attribution is in crate_studio/README.md.\n",
        )
        z.writestr(
            ".gitignore",
            ".env\n.env.*\n!.env.example\n__pycache__/\n.venv*/\noutput/\nresearch/vendor/\n",
        )
        z.writestr(".env.example", "MODEL_API_KEY=\n")
        z.writestr("source-sha256.json", json.dumps(hashes, indent=2))
    receipt = {
        "files": len(files),
        "credential_scan_passed": True,
        "bytes": destination.stat().st_size,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "path": str(destination),
        "published": False,
    }
    receipt_path = OUT / (
        "source-package.json"
        if name == "forma-source.zip"
        else destination.stem + "-receipt.json"
    )
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="forma-source.zip")
    main(parser.parse_args().name)
