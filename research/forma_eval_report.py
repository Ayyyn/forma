"""Build an honest local evaluation review and a credential-scanned evidence pack."""

import csv
import hashlib
import html
import json
import os
from pathlib import Path
import zipfile

from .run_forma_eval import ROOT, FROZEN, load, dump
from scripts.api_preflight import load_env


def main():
    output = ROOT / "output/forma/evaluation"
    initial = load(output / "v1/results.json")
    rerun = load(output / "v2-repair/results.json")
    demo = load(ROOT / "output/forma/demo-v1/manifest.json")
    ambiguity = load(output / "slot-clarification/results.json")
    protocol = load(FROZEN / "protocol.json")
    oracles = load(output / "oracles/results.json")
    rows = initial["rows"]
    calls = sum(r["calls"] for r in rows) + sum(r["calls"] for r in rerun["rows"])
    cost = sum(r["estimated_cost_usd"] for r in rows + rerun["rows"])
    public = initial["groups"]["public"]
    revision = initial["groups"]["revision"]
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "run",
                "group",
                "task",
                "first_pass",
                "final_pass",
                "upstream_overall_score",
                "calls",
                "proposal_brep_latency_s",
                "estimated_api_cost_usd",
            ]
        )
        for label, result in (("initial", initial), ("development-rerun", rerun)):
            for r in result["rows"]:
                writer.writerow(
                    [
                        label,
                        r["group"],
                        r["id"],
                        r["first_pass"]["passed"],
                        r["verified"]["passed"],
                        r["verified"].get("overall_score", ""),
                        r["calls"],
                        r["elapsed_s"],
                        r["estimated_cost_usd"],
                    ]
                )
    e = lambda x: html.escape(str(x))
    table = ""
    for r in rows:
        status = "pass" if r["verified"]["passed"] else "fail"
        data = {
            "first_pass": r["first_pass"],
            "verified": r["verified"],
            "response_ids": r["response_ids"],
        }
        table += f'<tr data-group="{r["group"]}" data-status="{status}" data-name="{e(r["id"])}"><td><span class="pill {status}">{"Pass" if status=="pass" else "Below threshold" if r["group"]=="public" else "Failed check"}</span></td><td><strong>{e(r["id"])}</strong><small>{r["group"]}</small></td><td>{"Pass" if r["first_pass"]["passed"] else "Fail"}</td><td>{format(r["verified"].get("overall_score",0),".4f") if r["group"]=="public" else "—"}</td><td>{r["calls"]}</td><td>{r["elapsed_s"]:.2f}s</td><td><details><summary>Evidence</summary><pre>{e(json.dumps(data,indent=2))}</pre></details></td></tr>'
    exclusions = "".join(
        f'<li><code>{e(x["id"])}</code> — {e(x["reason"])}</li>'
        for x in protocol["excluded"]
    )
    timeline = "".join(
        f'<a href="/studio?document={s["id"]}&view=model"><small>{i+1:02d}</small><strong>{e(s["label"].split("·",1)[-1].strip())}</strong><span>{e(s["id"])}</span></a>'
        for i, s in enumerate(demo["stages"])
    )
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forma · Evaluation & demonstration</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f2ec;color:#343c43;font:14px/1.6 Inter,Segoe UI,sans-serif}}header{{padding:20px 5%;display:flex;align-items:center;gap:20px;border-bottom:1px solid #ded8cc;background:#fffefa}}header b{{letter-spacing:3px}}header span{{color:#938774;font-size:12px}}nav{{margin-left:auto;display:flex;gap:18px}}a{{color:#5a7190;text-decoration:none}}main{{max-width:1260px;margin:auto;padding:48px 28px}}h1{{font-size:40px;line-height:1.15;letter-spacing:-1.5px;font-weight:500;margin:12px 0 20px}}h2{{font-weight:550;font-size:22px;margin:0 0 18px}}h3{{font-size:16px;margin:0 0 10px}}p{{max-width:850px;color:#737366}}.eyebrow{{font-size:10px;letter-spacing:2px;color:#9b896d}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:32px 0}}.card,section{{padding:24px;border:1px solid #ded8cc;border-radius:10px;background:#fffefa}}.card strong{{display:block;font-size:31px;font-weight:500}}.card span,.card small{{display:block;color:#87806f;font-size:11px}}section{{margin:22px 0}}.note{{border-left:3px solid #b49970;padding:4px 16px;color:#7a6a52}}.twocol{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}.timeline{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.timeline a{{display:flex;flex-direction:column;gap:12px;padding:18px;background:#f8f5ee;border:1px solid #e5ddcf;border-radius:7px;color:#4d5660}}.timeline small{{color:#9b896d}}.timeline span{{font:10px Consolas,monospace;color:#9b896d}}.pill{{font-size:10px;padding:4px 9px;border-radius:14px;white-space:nowrap}}.pass{{background:#eaf0e7;color:#55734f}}.fail{{background:#f6e9d4;color:#9a6d32}}.toolbar{{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-bottom:20px}}input,select{{padding:9px;border:1px solid #d8d4ca;border-radius:5px;background:white;color:#4d5660}}.table-scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{text-align:left;padding:14px 10px;border-bottom:1px solid #eee8dc;vertical-align:top}}th{{font-size:10px;color:#938774;text-transform:uppercase;letter-spacing:1px}}td small{{display:block;color:#9b896d}}td strong{{font-weight:500;white-space:nowrap}}pre{{max-width:420px;max-height:360px;overflow:auto;white-space:pre-wrap;font:10px/1.5 Consolas,monospace}}summary{{cursor:pointer;color:#657c93}}code{{font:11px Consolas,monospace}}li{{margin:9px 0;color:#7b7569}}footer{{padding:25px;color:#9b896d;font-size:11px}}.actions{{display:flex;gap:20px;margin:20px 0;flex-wrap:wrap}}.button{{display:inline-block;padding:10px 16px;background:#5d738a;color:white;border-radius:6px}}@media(max-width:850px){{.metrics,.timeline{{grid-template-columns:repeat(2,1fr)}}.twocol{{grid-template-columns:1fr}}main{{padding:28px 15px}}h1{{font-size:30px}}nav a:first-child{{display:none}}}}@media(max-width:500px){{.metrics,.timeline{{grid-template-columns:1fr}}header span{{display:none}}}}
</style></head><body><header><b>FORMA</b><span>ENGINEERING EVALUATION · 01 NOV 2026</span><nav><a href="/studio">Studio</a><a href="{e(demo["url"])}">Open demonstration ↗</a></nav></header><main><span class="eyebrow">FROZEN TASKS · RETAINED FAILURES · REAL MODEL RECEIPTS</span><h1>Editable CAD, measured.</h1><p>A fixed revision suite and a local STEP evaluation of CAD-bench's compatible public geometry tasks. Every model response, geometric check, failure and repair is retained.</p><div class="metrics"><div class="card"><strong>{revision["verified_success"]}/{revision["count"]}</strong><span>Frozen revision tasks, initial run</span><small>First pass: {revision["first_pass_success"]}/20 · failed task later passed a development rerun</small></div><div class="card"><strong>{public["verified_success"]}/{public["count"]}</strong><span>Public tasks above fixed 0.95 threshold</span><small>11 of 17 public tasks selected before generation</small></div><div class="card"><strong>{public["mean_upstream_overall_score"]:.4f}</strong><span>Mean upstream overall score</span><small>Arithmetic mean of selected tasks; not a full leaderboard score</small></div><div class="card"><strong>${cost:.3f}</strong><span>Estimated API cost, including rerun</span><small>{calls} actual responses · billing not independently verified</small></div></div>
<section><h2>The end-to-end demonstration</h2><p>Compare nine feasible stock options, inspect a real Meta thickness revision, make a human dimension edit, run wall motion and export separately printable panel components.</p><div class="timeline">{timeline}</div><div class="actions"><a class="button" href="{e(demo["url"])}">Open project canvas ↗</a><a href="/demo-package">Download fabrication package</a><a href="/evaluation-evidence">Download evaluation evidence</a></div><p class="note">The demo reuses the verified response from frozen task r11 against its exact base document, then adds explicit human revisions. It makes no additional model request. Closed envelope: 98 × 68 × 54 mm; outward-flat virtual motion envelope: 198 × 168 × 8 mm. Physical validation is pending.</p></section>
<div class="twocol"><section><h3>Repair failure → product fix</h3><p>Task r15 requested non-stock 3.5 mm panels while preserving stock requirements. The initial repair correctly asked for clarification but quoted validation feedback instead of the original instruction, so the provenance check rejected it.</p><p>The planner now receives the retained stock catalogue and explicit original-instruction citation rules. The unchanged failed task passed a <strong>single targeted development rerun</strong>, with no geometry change. This is not a fresh 20/20 suite run.</p></section><section><h3>Residual public-task ambiguity</h3><p>The 80 × 40 mm plate prompt specifies a 40 × 10 mm slot without naming the end profile. The model made rounded ends; the reference uses a rectangle. The strict upstream score remains <strong>0.8713</strong> and stays below our frozen success threshold.</p><p>Independent volume arithmetic confirms both interpretations. A separately labeled, explicit square-end human edit scores 1.0. It is excluded from the frozen aggregate.</p></section></div>
<section><h2>Task-level results</h2><div class="toolbar"><input id="search" placeholder="Find a task" aria-label="Find a task"><select id="group" aria-label="Task group"><option value="all">All tasks</option><option value="revision">Constructed revisions</option><option value="public">Public CAD-bench</option></select><label><input id="failures" type="checkbox"> Initial failures only</label><span id="row-count">31 tasks</span></div><div class="table-scroll"><table><thead><tr><th>Initial result</th><th>Task</th><th>First pass</th><th>Upstream score</th><th>Calls</th><th>Proposal + BREP</th><th>Provenance</th></tr></thead><tbody>{table}</tbody></table></div></section>
<section><h2>What was actually evaluated</h2><p>Model: Muse Wonder 1.0, temperature 0.15, at most two calls per task. First-pass and verified scores derive from the same initial response; they are not independent baseline samples. The initial revision median was {revision["median_latency_s"]:.2f}s; public geometry median was {public["median_latency_s"]:.2f}s. These timings include model inference and BREP verification, excluding export, external scoring and browser rendering.</p><p>Public source: <a href="https://github.com/CAD-bench/cad-bench">CAD-bench</a>, commit <code>{protocol["upstream_commit"]}</code>. The unchanged upstream STEP evaluator, including reference-geometry gates, runs in a separate Build123D 0.10.0 environment. All {len(oracles)} selected reference oracles scored effectively 1.0.</p><p>Adaptation: only the Python submission footer became Forma JSON editing instructions. Runtime: Windows Python 3.12 rather than Linux Python 3.11/Harbor. This is a local public-subset evaluation, not an official full benchmark run. Data is public development material, not held out. No training or competitor comparison was performed.</p><details><summary>Six tasks excluded before generation</summary><ul>{exclusions}</ul></details><p class="note">BREP validity and sampled wall overlap checks do not establish structural safety, engineered hinge behavior or manufacturing qualification. The remaining work includes physical measurements and broader evaluation.</p></section><footer>Frozen protocol and task hashes, exact source snapshots, response IDs, per-task scores, STEP/STL outputs and the failed attempts are included in the evidence download. Source license: upstream MIT, retained in the package.</footer></main><script>
const search=document.querySelector('#search'),group=document.querySelector('#group'),failures=document.querySelector('#failures');function filter(){{let count=0;document.querySelectorAll('tbody tr').forEach(row=>{{const show=row.dataset.name.includes(search.value.toLowerCase())&&(group.value==='all'||row.dataset.group===group.value)&&(!failures.checked||row.dataset.status==='fail');row.hidden=!show;if(show)count++;}});document.querySelector('#row-count').textContent=count+' tasks';}}[search,group,failures].forEach(x=>x.addEventListener('input',filter));</script></body></html>"""
    (output / "review.html").write_text(page, encoding="utf-8")
    files = [*FROZEN.rglob("*")]
    for folder in (
        output / "v1",
        output / "v2-repair",
        output / "oracles",
        output / "slot-clarification",
    ):
        files.extend(folder.rglob("*"))
    files.extend([output / "results.csv", ROOT / "output/forma/demo-v1/manifest.json"])
    for r in rows + rerun["rows"]:
        proposal = load(
            output / ("v1" if r in rows else "v2-repair") / r["id"] / "proposal.json"
        )
        files.extend(
            (ROOT / "output/forma/studio/agent" / proposal["run_id"]).glob("*.json*")
        )
    files = sorted(
        set(p for p in files if p.is_file() and "__pycache__" not in p.parts)
    )
    load_env()
    secrets = [
        v.encode()
        for k, v in os.environ.items()
        if any(s in k.upper() for s in ("API_KEY", "TOKEN_SECRET")) and len(v) > 15
    ]
    hashes = {}
    with zipfile.ZipFile(output / "evidence.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for path in files:
            data = path.read_bytes()
            if any(secret in data for secret in secrets):
                raise ValueError("Credential value found; evidence packaging blocked")
            name = path.relative_to(ROOT).as_posix()
            hashes[name] = hashlib.sha256(data).hexdigest()
            z.writestr(name, data)
        z.writestr("sha256.json", json.dumps(hashes, indent=2))
    summary = {
        "initial_revision": revision,
        "initial_public": public,
        "targeted_development_rerun": rerun["groups"]["revision"],
        "actual_model_responses": calls,
        "estimated_total_api_cost_usd": cost,
        "evidence_files": len(files),
        "evidence_sha256": hashlib.sha256(
            (output / "evidence.zip").read_bytes()
        ).hexdigest(),
        "credential_scan_passed": True,
    }
    dump(output / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
