"""Credential-scanned, byte-hashed verification archive; preserve older releases."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import zipfile
from scripts.api_preflight import load_env

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/forma/evaluation"


def main():
    load_env()
    secrets = [
        v.encode()
        for k, v in os.environ.items()
        if ("API_KEY" in k or "TOKEN_SECRET" in k) and len(v) > 8
    ]
    roots = [
        ROOT / p
        for p in (
            "evaluation/forma-full17-v1",
            "evaluation/forma-full17-thread-repair",
            "evaluation/forma-full17-baseline-audit",
            "output/forma/evaluation/full17-v1",
            "output/forma/evaluation/full17-thread-repair",
            "output/forma/evaluation/full17-environment",
            "output/forma/evaluation/full17-environment-compatible",
            "output/forma/evaluation/full17-environment-final",
            "output/forma/evaluation/full17-baseline-client-failure",
            "output/forma/mechanical-dev/ui-exports",
        )
    ]
    files = [
        p
        for folder in roots
        for p in folder.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix not in (".pyc", ".zip")
    ]
    files += [
        ROOT / p
        for p in (
            "docs/FORMA_FULL17.md",
            "research/run_forma_full17.py",
            "research/freeze_forma_full17.py",
            "research/cadbench_container.py",
            "research/cadbench_compat.Dockerfile",
            "research/replay_forma_full17_repair.py",
            "research/forma_full17_report.py",
            "research/verify_forma_full17_release.py",
            "research/repair_forma_baseline_empty.py",
            "tests/test_forma_full17_harness.py",
            "tests/test_mechanical_features.py",
            "output/forma/mechanical-dev/regression-final.txt",
            "output/forma/mechanical-dev/source-extraction-tests.txt",
            "output/forma/mechanical-dev/ui-history-checks.json",
            "output/forma/evaluation/full17-release-verification.json",
            "output/forma/mechanical-dev/edited-gear-drawing.png",
        )
    ]
    receipts = []
    for arm in ("forma", "build123d"):
        for p in (OUT / "full17-v1" / arm).glob("*/generation.json"):
            receipts.append(json.loads(p.read_text(encoding="utf8"))["receipt_run_id"])
    files += [
        p
        for ident in receipts
        for p in (ROOT / "output/forma/studio/agent" / ident).rglob("*")
        if p.is_file()
    ]
    files = sorted(set(files))
    hashes = {}
    for p in files:
        if p.name.startswith(".env"):
            raise ValueError("Environment file in evidence")
        data = p.read_bytes()
        if any(s in data for s in secrets):
            raise ValueError("Credential detected: " + str(p))
        hashes[p.relative_to(ROOT).as_posix()] = hashlib.sha256(data).hexdigest()
    dest = OUT / "full17-evidence.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(ROOT).as_posix())
        z.writestr("artifact-sha256.json", json.dumps(hashes, indent=2))
        z.writestr(
            "README.txt",
            "All 17 public tasks, initial matched Meta-only run and explicitly labelled thread-engine replay. Original failures retained. See docs/FORMA_FULL17.md. Estimated usage is not provider-verified billing.\n",
        )
    receipt = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "files": len(files),
        "credential_scan_passed": True,
        "bytes": dest.stat().st_size,
        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        "path": str(dest),
        "published": False,
    }
    (OUT / "full17-evidence-receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf8"
    )
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
