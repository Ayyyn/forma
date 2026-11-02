"""Independent aggregate, provenance, archive and live-route release checks."""

import hashlib
import io
import json
from pathlib import Path
import statistics
import urllib.request
import zipfile

from crate_studio import agent
from research.run_forma_full17 import ROOT, load, digest, dump


def main():
    checks = {}
    tasks = load(ROOT / "evaluation/forma-full17-v1/tasks.json")
    run = ROOT / "output/forma/evaluation/full17-v1"
    repair = ROOT / "output/forma/evaluation/full17-thread-repair/forma"
    checks["all_17_frozen"] = len(tasks) == 17 and [t["order"] for t in tasks] == list(
        range(1, 18)
    )
    for name, sha in load(ROOT / "evaluation/forma-full17-v1/manifest.json").items():
        assert digest(ROOT / "evaluation/forma-full17-v1" / name) == sha
    proto = load(ROOT / "evaluation/forma-full17-v1/protocol.json")
    checks["unchanged_upstream"] = all(
        digest(ROOT / "research/vendor/cad-bench" / n) == sha
        for n, sha in proto["upstream_hashes"].items()
    )
    checks["original_generation_snapshot"] = all(
        digest(run / "source-snapshot" / n) == sha
        for n, sha in proto["source_hashes"].items()
    )
    for label, folder in (
        ("forma", run / "forma"),
        ("build123d", run / "build123d"),
        ("repair", repair),
    ):
        rows = [load(folder / t["id"] / "result.json") for t in tasks]
        means = {
            tier: statistics.mean(r["score"] for r in rows if r["difficulty"] == tier)
            for tier in ("easy", "medium", "hard", "insane")
        }
        weighted = (
            sum(
                means[k] * w
                for k, w in (("easy", 1), ("medium", 2), ("hard", 3), ("insane", 4))
            )
            / 10
        )
        summary = load(folder / "summary.json")
        checks[label + "_complete"] = (
            summary["completed"] == 17 and summary["total"] == 17 and len(rows) == 17
        )
        checks[label + "_aggregate"] = (
            abs(weighted - summary["aggregate"]["benchmark_score"]) < 1e-12
        )
        checks[label + "_success_count"] = (
            sum(r["score"] >= 0.95 for r in rows) == summary["successes_at_095"]
        )
        checks[label + "_all_results_bounded"] = all(0 <= r["score"] <= 1 for r in rows)
    frozen = load(ROOT / "evaluation/forma-full17-thread-repair/protocol.json")
    checks["all_original_plans_retained"] = all(
        digest(run / "forma" / ident / "proposal.json") == sha
        for ident, sha in frozen["inputs"].items()
    )
    unchanged = []
    regraded = []
    for task in tasks:
        ident = task["id"]
        row = load(repair / ident / "result.json")
        origin = load(run / "forma" / ident / "result.json")
        if row["engine_replay"]["grader_reused"]:
            unchanged.append(ident)
            assert (
                digest(repair / ident / "candidate.step")
                == digest(run / "forma" / ident / "candidate.step")
                == row["engine_replay"]["identical_step_sha256"]
            )
            assert (
                row["score"] == origin["score"] and row["grading"] == origin["grading"]
            )
        else:
            regraded.append(ident)
    checks["replay_exact_origins"] = len(unchanged) == 15 and len(regraded) == 2
    responses = []
    expected_calls = 0
    for arm in ("forma", "build123d"):
        for task in tasks:
            g = load(run / arm / task["id"] / "generation.json")
            expected_calls += g["calls"]
            assert 1 <= g["calls"] <= 2
            events = [
                json.loads(l)
                for l in (
                    ROOT
                    / "output/forma/studio/agent"
                    / g["receipt_run_id"]
                    / "events.jsonl"
                )
                .read_text(encoding="utf8")
                .splitlines()
            ]
            responses.extend(e for e in events if e.get("kind") == "response")
    checks["only_meta_wonder"] = all(
        r["model"] == "muse-wonder-1.0" and r["returned_model"] == "muse-wonder-1.0"
        for r in responses
    )
    checks["all_receipts_retained"] = (
        len(responses) == expected_calls
        and len({r["response_id"] for r in responses}) == expected_calls
        and all(
            r["transport"].get("http_status") == 200 and r["usage_complete"]
            for r in responses
        )
    )
    checks["approved_cap"] = agent.CAP_USD == 25 and agent.estimated_spend() <= 25
    source = ROOT / "output/forma/forma-source-full17.zip"
    with zipfile.ZipFile(source) as z:
        hashes = json.loads(z.read("source-sha256.json"))
        checks["source_archive_hashes"] = all(
            hashlib.sha256(z.read(n)).hexdigest() == sha for n, sha in hashes.items()
        )
        extraction = ROOT / "output/forma/evaluation/full17-source-final-check"
        checked = [n for n in hashes if n.startswith(("crate_studio/", "tests/"))]
        checks["tested_source_matches_package"] = all(
            (extraction / n).read_bytes() == z.read(n) == (ROOT / n).read_bytes()
            for n in checked
        )
    text = (ROOT / "output/forma/mechanical-dev/source-extraction-tests.txt").read_text(
        encoding="utf8"
    )
    checks["fresh_source_98_tests"] = "Ran 98 tests" in text and text.strip().endswith(
        "OK"
    )
    checks["ui_exports"] = load(
        ROOT / "output/forma/mechanical-dev/ui-exports/checks.json"
    )["passed"]
    checks["original_user_document_preserved"] = (
        load(ROOT / "output/forma/studio/current.json")["id"] == "cad-3edbc1f21c22"
    )
    with urllib.request.urlopen("http://127.0.0.1:8770/full17", timeout=30) as r:
        report = r.read().decode()
    checks["report_http"] = (
        all(t["id"] in report for t in tasks)
        and "70.94%" in report
        and "66.35%" in report
        and "68.94%" in report
    )
    with urllib.request.urlopen(
        "http://127.0.0.1:8770/full17-evidence", timeout=120
    ) as r:
        raw = r.read()
    receipt = load(ROOT / "output/forma/evaluation/full17-evidence-receipt.json")
    checks["evidence_http"] = hashlib.sha256(raw).hexdigest() == receipt["sha256"]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        hashes = json.loads(z.read("artifact-sha256.json"))
        checks["all_evidence_hashes"] = z.testzip() is None and all(
            hashlib.sha256(z.read(n)).hexdigest() == sha for n, sha in hashes.items()
        )
    result = {
        "passed": all(checks.values()),
        "checks": checks,
        "estimated_new_inference_usd": sum(r["estimated_cost_usd"] for r in responses),
        "conservative_guard_usd": agent.estimated_spend(),
        "cap_usd": agent.CAP_USD,
    }
    dump(ROOT / "output/forma/evaluation/full17-release-verification.json", result)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
