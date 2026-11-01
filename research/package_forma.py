"""Curated source handoff. No credentials, runtimes or unrelated experiments."""

import hashlib
import json
import os
from pathlib import Path
import zipfile
from scripts.api_preflight import load_env

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/forma"


def main():
    files = [
        p
        for p in (ROOT / "crate_studio").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ]
    files += list((ROOT / "tests").glob("test_crate_*.py"))
    files += list((ROOT / "tests").glob("test_workspace_*.py"))
    files += [
        ROOT / p
        for p in [
            "docs/FORMA_STUDIO.md",
            "research/verify_studio_http.py",
            "research/verify_studio_live.py",
            "research/fetch_studio_assets.py",
            "research/studio_report.py",
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
    destination = OUT / "forma-source.zip"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):
            z.write(p, p.relative_to(ROOT).as_posix())
        z.writestr(
            "README.md",
            "# Forma\n\nStart with crate_studio/README.md. This source package contains the new local design app and checks. Create a Python 3.12 environment and install requirements-forma.txt. Run `python -m crate_studio`.\n\nThird-party Three.js assets retain their bundled MIT license. Earlier API transport is attributed in the app README. No provider credentials, Python runtime, or unrelated workspace studies are included.\n",
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
    (OUT / "source-package.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
