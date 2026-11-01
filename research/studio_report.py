"""Refresh CAD Studio evidence from local tests and retained real API receipts."""

from datetime import datetime, timezone
import hashlib
import html
import io
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/forma/studio"


def main():
    stream = io.StringIO()
    suite = unittest.TestSuite()
    for pattern in ("test_crate_*.py", "test_workspace_*.py"):
        suite.addTests(
            unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern)
        )
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (OUT / "test-output.txt").write_text(stream.getvalue(), encoding="utf-8")
    http = json.loads((OUT / "http-v4/results.json").read_text())
    live = json.loads((OUT / "live-v1/results.json").read_text())
    responses = []
    for receipt in sorted((OUT / "agent").glob("*/events.jsonl")):
        responses.extend(
            event
            for line in receipt.read_text().splitlines()
            if (event := json.loads(line)).get("kind") == "response"
        )
    sources = [
        p
        for p in (ROOT / "crate_studio").rglob("*")
        if p.is_file()
        and p.suffix in (".py", ".js", ".css", ".html")
        and "vendor" not in p.parts
        and "__pycache__" not in p.parts
    ]
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "passed": result.wasSuccessful() and http["passed"] and live["passed"],
        "unit_tests": {
            "count": result.testsRun,
            "passed": result.wasSuccessful(),
            "failures": len(result.failures),
            "errors": len(result.errors),
        },
        "http_checks": http,
        "live_integration": live,
        "browser_verification": json.loads(
            (OUT / "browser-verification.json").read_text()
        ),
        "actual_studio_responses": len(responses),
        "unique_response_ids": len({r["response_id"] for r in responses}),
        "estimated_studio_cost_usd": sum(
            r.get("estimated_cost_usd", 0) for r in responses
        ),
        "billing_verified": False,
        "source_hashes": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(sources)
        },
        "scope": "Constructed application integration and CAD regression tests. Not external benchmark, physical validation, customer study, or evidence of AutoCAD/SolidWorks feature parity.",
        "retained_attempts": {
            "http-v1": "Imported filleted plate face offset failed: fixed shared-shape cleanup mutation, regression added.",
            "http-v2": "CAD checks passed until harness used GET for a POST-only conversion route. Harness corrected.",
            "http-v3": "33 checks passed before added CSV and DXF unit checks.",
            "live-v1": "Two actual model responses. Initial apply harness used GET; resumed retained response with POST, without another paid request.",
        },
        "limitations": [
            "General XY sketch constraint solving, curved-face deformation, native SLDPRT/DWG history, GD&T, nonlinear FEA, CAM and PLM are not implemented.",
            "Ordinal topology references can require reselection after upstream changes.",
            "Planar assembly alignment is sequential, not a simultaneous mate solver.",
            "Studio edits do not automatically requalify enclosure requirements.",
            "PDF text uses Latin-1 Helvetica; SVG and project JSON retain Unicode.",
            "No physical prototype or independent CAD benchmark result is claimed.",
        ],
    }
    (OUT / "verification-summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    esc = lambda value: html.escape(str(value))
    rows = "".join(
        f'<tr><td>{esc(c["check"])}</td><td>{"Pass" if c["passed"] else "Fail"}</td></tr>'
        for c in http["checks"]
    )
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Forma CAD Studio verification</title>
<style>body{{font:15px/1.65 system-ui;color:#263348;background:#f7f8fa;max-width:1050px;margin:40px auto;padding:24px}}h1{{font-size:34px}}section{{background:white;border:1px solid #dde3eb;padding:24px;margin:20px 0;border-radius:8px}}.metrics{{display:flex;gap:36px;flex-wrap:wrap}}strong{{font-size:30px;color:#4265c5}}td{{padding:8px;border-bottom:1px solid #e5e8ef}}table{{width:100%;border-collapse:collapse}}a{{color:#4265c5}}</style>
<p>FORMA / CAD STUDIO</p><h1>Editable design, checked geometry</h1><p>{esc(report["scope"])}</p>
<section class="metrics"><div><strong>{result.testsRun}</strong><br>passing unit tests</div><div><strong>{len(http["checks"])}</strong><br>passing HTTP checks</div><div><strong>{sum(c["passed"] for c in live["tasks"])}/2</strong><br>real Meta integration tasks</div></section>
<section><h2>Human control</h2><p>Editable feature history, direct planar-face edits, selected-edge treatments, dimensional properties, 3D translation handles, suppression, revisions, configurations and movable drawing notes. Model proposals require explicit Apply.</p><p>Neutral STEP solids and portable project JSON serve different purposes: feature history is retained in project JSON.</p></section>
<section><h2>Evidence</h2><p><a href="verification-summary.json">Summary and current source hashes</a> · <a href="test-output.txt">Unit-test output</a> · <a href="http-v4/results.json">HTTP results</a> · <a href="live-v1/results.json">Retained live results</a> · <a href="browser-verification.json">Browser workflow checks</a> · <a href="../verification.html">Earlier enclosure evidence</a></p><p>{len(responses)} actual Studio model responses; provisional estimated cost ${report["estimated_studio_cost_usd"]:.5f}. Billing is unverified. Mocked unit-test responses are excluded. Frozen live-task source hashes identify the earlier evaluated version; current hashes are recorded separately.</p><table>{rows}</table></section>
<section><h2>Limits</h2><ul>{''.join('<li>'+esc(x)+'</li>' for x in report['limitations'])}</ul><h2>Retained attempts</h2><ul>{''.join('<li>'+esc(k)+': '+esc(v)+'</li>' for k,v in report['retained_attempts'].items())}</ul></section></html>"""
    (OUT / "verification.html").write_text(page, encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "unit_tests": result.testsRun,
                "http_checks": len(http["checks"]),
                "live_responses": len(responses),
                "report": str(OUT / "verification.html"),
            },
            indent=2,
        )
    )
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
