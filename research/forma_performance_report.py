"""Separate, hashed performance report. Never replaces original eval evidence."""

import hashlib
import html
import json
import os
import zipfile
from scripts.api_preflight import load_env
from crate_studio import workspace_agent as wa
from .run_forma_eval import ROOT, load, dump

BASE = ROOT / "output/forma/evaluation"
DEST = BASE / "performance"


def ids(directory):
    return [load(path)["run_id"] for path in directory.glob("*/proposal.json")]


def usage(run_ids):
    totals = dict(
        responses=0,
        input_tokens=0,
        output_tokens=0,
        cached_tokens=0,
        reasoning_tokens=0,
    )
    for ident in set(run_ids):
        for line in (
            (wa.RUNS / ident / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ):
            event = json.loads(line)
            if event.get("kind") != "response":
                continue
            u = event["transport"]["usage"]
            totals["responses"] += 1
            totals["input_tokens"] += u["prompt_tokens"]
            totals["output_tokens"] += u["completion_tokens"]
            totals["cached_tokens"] += (u.get("prompt_tokens_details") or {}).get(
                "cached_tokens", 0
            )
            totals["reasoning_tokens"] += (
                u.get("completion_tokens_details") or {}
            ).get("reasoning_tokens", 0)
    totals["repriced_estimate_usd"] = (
        (totals["input_tokens"] - totals["cached_tokens"]) * 4e-6
        + totals["cached_tokens"] * 0.2e-6
        + totals["output_tokens"] * 20e-6
    )
    return totals


def main():
    old = load(BASE / "v1/results.json")
    trial = load(BASE / "perf-focused-low/results.json")
    live = load(DEST / "live-cache/results.json")
    extra = load(DEST / "candidate/results.json")
    replay = load(DEST / "replay/results.json")
    original_usage = usage(ids(BASE / "v1"))
    candidate_usage = usage(ids(BASE / "perf-focused-low"))
    all_ids = (
        ids(BASE / "perf-focused-low")
        + ids(BASE / "perf-focused-medium-check")
        + ids(BASE / "perf-catalogue-fix")
        + [r["run_id"] for r in extra["rows"]]
        + [live["source_run_id"], live["warm_run_id"]]
    )
    summary = {
        "production_policy": {
            "context_mode": wa.DEFAULT_CONTEXT_MODE,
            "reasoning_effort": wa.DEFAULT_REASONING_EFFORT,
        },
        "live_reuse": live,
        "offline_replay": {k: v for k, v in replay.items() if k != "rows"},
        "historical_baseline": {
            "groups": old["groups"],
            "usage_repriced": original_usage,
        },
        "experimental_focused_low": {
            "groups": trial["groups"],
            "usage": candidate_usage,
            "promoted": False,
        },
        "candidate_selection_cases": extra,
        "medium_material_check": load(BASE / "perf-focused-medium-check/results.json")[
            "groups"
        ]["revision"],
        "catalogue_fix_targeted": load(BASE / "perf-catalogue-fix/results.json")[
            "groups"
        ]["revision"],
        "new_live_usage": usage(all_ids),
        "offline_checks": 88,
        "billing_verified": False,
        "limits": [
            "Historical baseline is not a concurrent randomized control.",
            "Original cost estimates ignored cached-token discounts; this report reprices both variants consistently. Original receipts and conservative guard charges are untouched.",
            "The planned paired six-case control was not run after the complete candidate suite failed the per-task quality gate. Six added cases are candidate-only.",
            "No complete fresh model suite after the catalogue fix. Targeted rerun is not 20/20.",
            "Exact repeat speed is not novel-generation speed. No physical or aesthetic validation.",
        ],
    }
    dump(DEST / "summary.json", summary)
    rows = "".join(
        f'<tr><td>{html.escape(r["id"])}</td><td>{"Pass" if r["verified"]["passed"] else "Fail"}</td><td>{r["elapsed_s"]:.2f}s</td><td>${r["estimated_cost_usd"]:.5f}</td></tr>'
        for r in trial["rows"]
    )
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forma · Performance verification</title><style>body{{margin:0;background:#f6f4ef;color:#263140;font:15px/1.6 system-ui}}main{{max-width:1050px;margin:45px auto;padding:0 24px}}a{{color:#425aa4}}h1{{font-size:34px;letter-spacing:-1px}}h2{{font-size:21px;margin-top:34px}}.muted{{color:#627080}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:15px}}.card,section{{background:white;border:1px solid #deded8;border-radius:12px;padding:22px}}.card strong{{display:block;font-size:29px}}.notice{{border-left:4px solid #ad7628;padding:14px 20px;background:#fff7e9}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #e7e7e2}}button{{padding:8px 12px;border:1px solid #ccd0d5;background:white;border-radius:6px;cursor:pointer}}</style><main>
<p class="muted">FORMA / PERFORMANCE VERIFICATION · NOVEMBER 2, 2026</p><h1>Faster reuse. Quality gates retained.</h1><p>Exact caching is active. Full context and medium reasoning remain production defaults.</p><p><a href="/studio">Studio</a> · <a href="/performance-evidence">Download hashed evidence</a> · <a href="/evaluation">Original frozen evaluation</a></p>
<h2>Measured live reuse</h2><div class="cards"><div class="card"><strong>{live['cold_end_to_end_s']:.2f}s → {live['warm_end_to_end_s']:.3f}s</strong>Cold request versus exact reuse on another saved revision</div><div class="card"><strong>0 extra model calls</strong>Identical CAD, revalidated, with source provenance</div><div class="card"><strong>31/31</strong>Cached / uncached retained-plan replay equivalence</div><div class="card"><strong>88 passed</strong>Offline unit checks</div></div><p class="muted">One synthetic box edit, including HTTP, job polling and validation. Cold estimate ${live['cold_estimated_model_cost_usd']:.5f}; warm model cost $0. Novel generation is not guaranteed this speed.</p>
<h2>Experimental policy: not promoted</h2><div class="notice">Focused context + low reasoning scored <strong>19/20 revisions and 11/11 public geometry tasks</strong>, but regressed the steel-material change. Six selected-face, edge, mate, missing-selection, dense-profile and pattern cases passed. Medium reasoning with the same incomplete stock context also failed the steel task. Exposing all per-material stock catalogues restored that one task under full context/medium reasoning. A complete post-fix model suite has not been rerun.</div>
<h2>Cost and latency</h2><section><p>Historical 31-task baseline, consistently repriced for cached input: <strong>${original_usage['repriced_estimate_usd']:.5f}</strong>. Experimental trial: <strong>${candidate_usage['repriced_estimate_usd']:.5f}</strong>. Original receipts and guard charges remain unchanged; billing unverified.</p><p>Revision median: {old['groups']['revision']['median_latency_s']:.2f}s → {trial['groups']['revision']['median_latency_s']:.2f}s. Public geometry median: {old['groups']['public']['median_latency_s']:.2f}s → {trial['groups']['public']['median_latency_s']:.2f}s. These historical comparisons combine context, reasoning and cache differences.</p><p>New live responses: {summary['new_live_usage']['responses']}; combined estimated cost ${summary['new_live_usage']['repriced_estimate_usd']:.5f}.</p></section>
<h2>All fresh trial tasks</h2><button id="filter">Show failures only</button><table><thead><tr><th>Task</th><th>Outcome</th><th>Proposal latency</th><th>Estimate</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Reuse rules</h2><p>Keys bind the complete document, instruction, selection, model settings, validator sources, CAD library versions and imported-file bytes. Cached plans are validated again. A New proposal button bypasses reuse. No approximate prompt matching.</p><p class="muted">{html.escape(' '.join(summary['limits']))}</p><p><a href="https://dev.meta.ai/docs/prompt-caching">Meta caching docs</a> · <a href="https://dev.meta.ai/docs/pricing-rate-limits">Rate reference</a></p></main><script>let filtered=false;document.querySelector('#filter').onclick=()=>{{filtered=!filtered;for(const row of document.querySelectorAll('tbody tr'))row.hidden=filtered&&row.cells[1].textContent!=='Fail';document.querySelector('#filter').textContent=filtered?'Show all tasks':'Show failures only';}};</script></html>"""
    (DEST / "review.html").write_text(page, encoding="utf-8")
    files = {}
    for directory in [
        DEST,
        BASE / "perf-focused-low",
        BASE / "perf-focused-medium-check",
        BASE / "perf-catalogue-fix",
    ]:
        for path in directory.rglob("*"):
            if any(part.startswith("package-check") for part in path.parts) or "__pycache__" in path.parts:
                continue
            if path.is_file() and path.name not in (
                "evidence.zip",
                "evidence-receipt.json",
            ):
                files[path.relative_to(BASE).as_posix()] = path
    for ident in set(all_ids):
        for path in (wa.RUNS / ident).glob("*"):
            if path.is_file():
                files["model-receipts/" + ident + "/" + path.name] = path
    load_env()
    secrets = [
        os.environ[n].encode()
        for n in ("MODEL_API_KEY", "META_API_KEY", "BASETEN_API_KEY")
        if os.environ.get(n)
    ]
    hashes = {}
    for name, path in files.items():
        data = path.read_bytes()
        if any(secret in data for secret in secrets):
            raise ValueError("Credential detected; evidence not packaged")
        hashes[name] = hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(DEST / "evidence.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, name)
        archive.writestr("sha256.json", json.dumps(hashes, indent=2))
    receipt = {
        "files": len(files),
        "credential_scan_passed": True,
        "sha256": hashlib.sha256((DEST / "evidence.zip").read_bytes()).hexdigest(),
    }
    dump(DEST / "evidence-receipt.json", receipt)
    print(
        json.dumps(
            {"new_live_usage": summary["new_live_usage"], "evidence": receipt}, indent=2
        )
    )


if __name__ == "__main__":
    main()
