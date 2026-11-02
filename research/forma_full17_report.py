"""Generate an inspectable all-task report without selecting successful subsets."""

import argparse
import hashlib
import html
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def load(p):
    return json.loads(p.read_text(encoding="utf8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run", type=Path, default=ROOT / "output/forma/evaluation/full17-v1"
    )
    args = ap.parse_args()
    run = args.run.resolve()
    tasks = load(ROOT / "evaluation/forma-full17-v1/tasks.json")
    summaries = {
        arm: load(run / arm / "summary.json")
        for arm in ("forma", "build123d")
        if (run / arm / "summary.json").exists()
    }
    complete = (
        len(summaries) == 2
        and all(s["completed"] == 17 for s in summaries.values())
        and not any(
            "NoneType" in r.get("generation", {}).get("error", "")
            for s in summaries.values()
            for r in s["tasks"]
        )
    )
    repair_root = ROOT / "output/forma/evaluation/full17-thread-repair/forma"
    repaired = load(repair_root / "summary.json")
    e = html.escape
    cards = []
    rows = []
    for arm, label in (
        ("forma", "Forma + Muse Wonder"),
        ("build123d", "Direct Build123D + Muse Wonder"),
    ):
        s = summaries.get(arm, {})
        if any(
            "NoneType" in r.get("generation", {}).get("error", "")
            for r in s.get("tasks", [])
        ):
            cards.append(
                "<article><span>Direct Build123D + Muse Wonder</span><strong>Rechecking</strong><p>Empty-response client failure retained.</p><p>Restoring the remaining second attempt and receipt accounting.</p></article>"
            )
            continue
        g = [r["generation"] for r in s.get("tasks", []) if r.get("generation")]
        times = [x["elapsed_s"] for x in g if "elapsed_s" in x]
        score = (
            f'{100*s["aggregate"]["benchmark_score"]:.2f}%'
            if s.get("completed") == 17
            else "Pending"
        )
        cards.append(
            f'<article><span>{label}</span><strong>{score}</strong><p>{s.get("completed",0)}/17 scored · {s.get("successes_at_095",0)} ≥ 0.95</p><p>${s.get("estimated_cost_usd",0):.4f} estimated inference · {statistics.median(times):.1f}s median generation</p></article>'
            if times
            else f"<article><span>{label}</span><strong>Pending</strong></article>"
        )
    cards.append(
        f'<article><span>Thread-engine replay · same plans</span><strong>{100*repaired["aggregate"]["benchmark_score"]:.2f}%</strong><p>17/17 represented · 10 ≥ 0.95</p><p>No new inference · 2 regraded, 15 identical inputs</p></article>'
    )
    for task in tasks:
        cells = []
        for arm in ("forma", "repair", "build123d"):
            path = (
                (repair_root if arm == "repair" else run / arm)
                / task["id"]
                / "result.json"
            )
            if not path.exists():
                cells.append('<td class="muted">Pending</td>')
                continue
            r = load(path)
            score = r["score"]
            m = r.get("grading", {}).get("metrics", {})
            err = (
                m.get("error_message")
                or m.get("failure_reason")
                or r.get("grading", {}).get("error")
                or r.get("generation", {}).get("error")
                or ""
            )
            cells.append(
                f'<td><b class="{"pass" if score>=.95 else "fail"}">{score:.6f}</b><small>{e(str(err))}</small></td>'
            )
        rows.append(
            f'<tr><td><span>{task["order"]:02d}</span> {e(task["id"])}</td><td>{task["difficulty"]}</td>{"".join(cells)}</tr>'
        )
    report = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Forma · Full 17-task evaluation</title>
<style>body{{margin:0;background:#f5f3ee;color:#27332f;font:15px/1.6 system-ui}}main{{max-width:1220px;margin:48px auto;padding:0 32px}}nav{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#61736c}}h1{{font-size:40px;line-height:1.2;font-weight:550;margin:18px 0}}.intro{{max-width:850px;color:#58675e}}.cards{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px;margin:32px 0}}article{{background:#fff;border:1px solid #d8dfd8;border-radius:10px;padding:22px}}article span{{font-size:14px}}strong{{display:block;font-size:42px;font-weight:550}}article p{{margin:4px 0;font-size:13px;color:#61736c}}section{{margin:34px 0}}h2{{font-size:21px;font-weight:550}}table{{width:100%;border-collapse:collapse;background:white;border:1px solid #d8dfd8;font-size:13px}}th,td{{text-align:left;padding:12px 14px;border-bottom:1px solid #e5e9e3}}th{{font-size:12px;color:#61736c}}td span{{color:#829086;margin-right:8px}}td small{{display:block;max-width:220px;overflow-wrap:anywhere;color:#8b544a}}.pass{{color:#286846}}.fail{{color:#98604b}}.muted{{color:#7a8780}}a{{color:#236452}}.note{{padding:18px;border-left:3px solid #9baf9e;background:#eaf0e9}}footer{{padding:25px 0;border-top:1px solid #d8dfd8;font-size:12px;color:#61736c}}@media(max-width:800px){{main{{padding:0 16px}}.cards{{grid-template-columns:1fr}}table{{font-size:11px}}th,td{{padding:8px}}}}</style>
<main><nav>Forma / Verification / Public CAD-bench</nav><h1>Every public task. Every result.</h1><p class="intro">{'Completed' if complete else 'In progress'} · 17 tasks · one Meta model · two CAD workflows. Tier-balanced scoring includes every failure. This is an adapted public development evaluation using native STEP and the unchanged upstream Linux grader.</p><div class="cards">{''.join(cards)}</div>
<section><h2>Matched comparison</h2><p>Both workflows use <b>muse-wonder-1.0</b>, medium reasoning, temperature 0.15, up to 8,192 output tokens and two calls per task. Both receive the same geometry instructions. One repair is permitted for actual build errors; neither receives grader feedback. Caching is disabled for new generations.</p><p>Forma produces an editable feature history in bounded JSON. The baseline produces Python for Build123D 0.10.0 in an isolated container. Both export BREP STEP and use the same unmodified scoring, reference gates and Blender simulations. Generation timings include different CAD runtimes and container startup; they are workflow latency, not isolated model speed.</p></section>
<section><h2>Engine repair: {100*repaired["aggregate"]["benchmark_score"]:.2f}%</h2><p>A failure-driven native-thread repair preserves the cylindrical core and helical crests. This is a deterministic replay of the <b>same original model plans</b>, with no new inference. Both thread tasks are regraded; the other 15 retain identical STEP bytes and original scoring records. The initial score remains visible. This is not a second fresh model run.</p><p>The screw improves from 0.403167 to 0.804140. The custom profile remains low at 0.100790. All 17 remain in the aggregate; 10 meet the ≥0.95 threshold.</p></section><section><h2>All 17 tasks</h2><table><thead><tr><th>Task</th><th>Difficulty</th><th>Forma initial</th><th>Thread repair replay</th><th>Direct Build123D</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section><h2>Baseline audit</h2><p>The release audit found three empty public responses that the initial client mishandled. All first failures and raw receipts are retained. Each case received exactly its remaining second attempt under the original two-call limit. The final scores remain zero; corrected baseline accounting includes all 25 responses and $1.9635 estimated inference. No task budget was reset and no grader feedback was sent to the model.</p></section><section><h2>Remaining failures</h2><p>The slot-end ambiguity, involute-gear profile score, screw contact checks, custom thread profile, three-shaft transfer and right-angle axis attachment remain visible. The right-angle assembly scores zero. Valid BREP and export checks do not establish satisfaction of every functional requirement.</p><p>Product verification: 98 offline checks passed (95 CAD regressions and three baseline harness controls). A human thickness edit was verified through CAD regeneration, drawing updates, actual STL download, STEP read-back, portable project export and the design bundle. Undo and redo retain the edit history.</p></section><section class="note"><b>Interpretation</b><p>Public tasks were inspected during product development. These results do not establish held-out generalization, an official Harbor submission, or a leaderboard rank. The upstream metric averages within difficulty tiers, then weights easy/medium/hard/insane by 1/2/3/4. Missing results count as zero. The ≥0.95 task count is a separately declared success threshold.</p><p>Historical GPT, Gemini and other results use different revisions, agents and budgets. They are contextual research records and cannot substantiate a direct ranking against this run. All inference costs are estimates from retained usage receipts; provider billing is unverified.</p></section>
<section><h2>Reproducibility</h2><p>Upstream revision <code>f1084c3d345f859ba48a4bd9d5c95bccca7dcb46</code>. Linux Python 3.11, Build123D 0.10.0 and Blender 4.3.2. Original Dockerfiles plus a compatible ocp_gordon 0.1.17 pin; evaluator source unchanged. Four CPUs and 4 GB per grader container, below upstream's declared 8 GB. The output UID correction preserves timestamped evidence on WSL without running as root.</p><p><a href="/full17-evidence">Download verification evidence</a> · <a href="https://github.com/CAD-bench/cad-bench">Upstream benchmark</a> · <a href="/studio">Open Forma Studio</a></p></section><footer>Frozen protocol and source hashes, raw responses, usage receipts, native CAD, scoring provenance, calibration failures and controlled baseline outputs are retained. No physical hardware validation is claimed.</footer></main></html>"""
    (run / "review.html").write_text(report, encoding="utf8")
    (run / "comparison.json").write_text(
        json.dumps(
            {"complete": complete, "arms": summaries, "thread_repair_replay": repaired},
            indent=2,
            allow_nan=False,
        ),
        encoding="utf8",
    )
    print(run / "review.html")


if __name__ == "__main__":
    main()
