"""Build an auditable 173-entry documentation scan, without competitor execution."""
from collections import Counter
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research/competition-2026"
OUT = ROOT / "output/forma/competition-2026"
DIRECT = {41, 129, 144}
ENGINEERING = {7, 58, 77, 114, 138, 153}
PHYSICAL = {3, 8, 15, 20, 23, 29, 31, 32, 42, 51, 62, 74, 75, 78, 81, 93, 105, 108, 109, 113, 124, 143, 150, 159, 162, 167, 173}
EVALUATION = {4, 9, 12, 13, 14, 19, 26, 30, 33, 34, 35, 37, 38, 40, 47, 55, 56, 57, 60, 61, 65, 66, 82, 83, 89, 98, 102, 110, 120, 125, 128, 130, 135, 136, 139, 141, 145, 146, 154, 158, 171}


def group(i):
    if i in (1, 100):
        return "Primary source unavailable"
    if i in DIRECT:
        return "Direct CAD"
    if i in ENGINEERING:
        return "Adjacent engineering design"
    if i in PHYSICAL:
        return "Physical systems / science"
    if i in EVALUATION:
        return "Evaluation / model systems"
    return "Agents / infrastructure / products"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    roster = json.loads((DATA / "roster.json").read_text(encoding="utf-8"))
    digests = json.loads((DATA / "documentation-digests.json").read_text(encoding="utf-8"))
    notes = json.loads((DATA / "analyst-notes.json").read_text(encoding="utf-8"))
    collection = json.loads((DATA / "collection.json").read_text(encoding="utf-8"))
    assert len(roster) == len(digests) == len(notes) == 173
    assert set(notes) == {str(i) for i in range(1, 174)}
    records = []
    for row, digest in zip(roster, digests):
        i = digest["index"]
        assert row["full_name"] == digest["repository"]
        folder = DATA / "repositories" / row["full_name"].replace("/", "__")
        source = folder / "README.source.txt"
        records.append({**digest, "focus_group": group(i), "analyst_note": notes[str(i)], "readme_saved_sha256": hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None, "review_level": "Directory metadata + bounded README excerpts; primary repository page only if no README; no code execution.", "directory_rank_for_reference_only": row["rank"], "directory_track_label": row["track"]})
    coverage = dict(Counter(r["documentation_status"] for r in records))
    signals = {k: sum(bool(r[k]) for r in roster) for k in ("has_tests", "has_ci", "has_live_deploy", "has_video_demo", "open_weights_tuning", "meta_api_verified")}
    summary = {
        "reviewed_ist": datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
        "scope": "Coverage-tracked public-documentation scan of every entry in the supplied unofficial directory's 173-entry Track 2 snapshot. Not a full source-code audit, independent benchmark reproduction, or official submission verification.",
        "directory_sha256": collection["directory_sha256"],
        "entries_accounted_for": len(records),
        "entries_with_individual_analyst_notes": len(notes),
        "primary_source_coverage": coverage,
        "additional_linked_repositories_attempted": collection["additional_linked_repositories"],
        "focus_groups": dict(Counter(r["focus_group"] for r in records)),
        "directory_reported_signals_unverified": signals,
        "competitor_software_executed": 0,
        "competitor_live_demos_tested": 0,
        "external_benchmarks_reproduced": 0,
        "method": ["Freeze the JSON roster and normalize both Track 2 label variants; filtering only exact 'Push the Frontier' misses one entry.", "Retrieve public root READMEs as inert text; inspect repository-page text when root README cannot be found. Preserve source URLs, collection times, attempts and hashes.", "Read each directory summary, introductory documentation excerpt and selected evidence/limitation excerpts; record an individual analyst note for all 173 entries.", "Read the complete retrieved root READMEs for Drafty, Inkbench, Photo-CAD and Hull Forge. Other entries receive a documentation screen, not a complete line-by-line README or source audit.", "Use excerpt selection for coverage, not scoring. Its keyword heuristic can miss important sections; missing excerpts are not evidence of absent functionality.", "Report repository claims as claims. Do not transform CI/test/deployment flags, commit volume or tracker scores into an official rank or winning probability."],
        "data_quality_notes": ["173 indexed entries are not independently confirmed final submissions or distinct teams.", "Expectrail and Nightshift expose the same workflow/README; related FrontierSight/SceneProof projects share an owner. No automatic disqualification or official deduplication is inferred.", "Some READMEs name Build for Your World although the directory labels them Track 2 (including entries 118, 125, 165). The frozen roster is retained rather than silently altered.", "Some directory summaries are stale or inaccurate: Coresight, MuseLaunch and Thalvi differ materially in their current README descriptions.", "Two primary repositories returned 404 at collection time. This does not prove they never existed or were disqualified.", "Linked repositories for the unavailable ta-amps bundle were attempted; they also returned 404."],
        "forma_assessment": ["The verified local implementation is a useful base, but this scan does not establish a strong winning probability.", "General agentic CAD, geometry checks, human approval and repair loops already appear in direct competitors. These are not a sufficient unique frontier claim.", "Drafty documents real BREP/meshing/FEA and constrained thickness search; Inkbench documents assembly/stability checks; Photo-CAD documents calibrated photo-to-editable-part reconstruction.", "A stronger submission needs one distinct technical hypothesis and a matched-budget, frozen, unseen-task evaluation showing its contribution. More generic CAD features are a lower priority.", "Several non-CAD projects document substantive held-out evaluations, physical experiments, formal checking or model training. They compete for the same track even when their domains differ."],
    }
    (OUT / "review-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "all-173-review.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    with (OUT / "all-173-review.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = ["index", "repository", "url", "focus_group", "documentation_status", "readme_lines", "analyst_note", "review_level"]
        writer = csv.DictWriter(stream, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    esc = lambda x: html.escape(str(x))
    status_names = {"readme_fetched": "README retrieved", "repository_page_only": "Repository page only", "unavailable": "Primary source unavailable"}
    rows = []
    for r in records:
        i = r["index"]
        evidence = "".join(f'<blockquote><a href="{esc(r["documentation_url"])}">Source line {e["line"]}</a>: {esc(e["text"][:180])}</blockquote>' for e in r["evidence_excerpts"][:2])
        detail = f'<p>{esc(r["intro_excerpt"][:240])}</p>{evidence}' if r["readme_lines"] else '<p>No root README text was available in this scan. Consult the analyst note and collection record.</p>'
        signals_text = ", ".join(label for key, label in (("has_tests", "tests"), ("has_ci", "CI"), ("has_live_deploy", "live link"), ("has_video_demo", "video link"), ("open_weights_tuning", "tuning flag")) if r["directory_reported_signals"][key]) or "No selected flags"
        rows.append(f'<tr data-group="{esc(r["focus_group"])}" data-status="{esc(r["documentation_status"])}"><td>{i:03}</td><td><a href="{esc(r["url"])}">{esc(r["repository"])}</a><small>{esc(r["focus_group"])}</small></td><td><span class="status {r["documentation_status"]}">{status_names[r["documentation_status"]]}</span><small>{r["readme_lines"]} README lines · no code executed</small></td><td>{esc(r["analyst_note"])}<details><summary>Documentation excerpts and tracker flags</summary>{detail}<p class="muted">Unverified tracker flags: {esc(signals_text)}. Quoted text is a repository claim, not a reproduced result.</p></details></td></tr>')
    options = ''.join(f'<option>{esc(g)}</option>' for g in summary['focus_groups'])
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>All 173 Track 2 entries — documentation scan</title>
<style>body{{font:15px/1.6 system-ui,sans-serif;background:#f5f6f8;color:#253248;margin:0}}main{{max-width:1480px;margin:auto;padding:36px 28px}}h1{{font-size:34px;line-height:1.2;letter-spacing:-1px}}h2{{font-size:20px}}a{{color:#3559ac}}.muted,small{{color:#647086}}small{{display:block;font-size:12px;margin-top:6px}}section{{background:#fff;padding:24px;border:1px solid #dde3eb;border-radius:8px;margin:20px 0}}.metrics{{display:flex;gap:36px;flex-wrap:wrap}}.metrics strong{{font-size:30px;display:block}}.scope{{border-left:4px solid #b68a3e;background:#fff9ed;padding:16px}}.controls{{display:flex;gap:12px;flex-wrap:wrap;position:sticky;top:0;background:#f5f6f8;padding:16px 0;z-index:2}}input,select{{font:inherit;padding:10px;border:1px solid #bbc7d8;border-radius:5px}}input{{flex:1;min-width:240px}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:14px 12px;border-bottom:1px solid #e0e5ed;text-align:left;vertical-align:top}}th{{font-size:12px;text-transform:uppercase;color:#647086}}td:nth-child(2){{width:25%;overflow-wrap:anywhere}}td:nth-child(3){{width:17%}}blockquote{{font-size:13px;margin:14px 0;padding-left:12px;border-left:2px solid #c8d2e5}}details{{margin-top:10px;font-size:13px}}summary{{cursor:pointer;color:#3559ac}}.status{{font-size:12px}}.unavailable{{color:#9b4b27}}.repository_page_only{{color:#8a6a28}}.readme_fetched{{color:#27664f}}@media(max-width:800px){{main{{padding:20px 12px}}.table-wrap{{overflow:auto}}table{{min-width:920px}}}}</style></head><body><main>
<p class="muted">FORMA / COMPETITION REVIEW · {esc(summary['reviewed_ist'])}</p><h1>Every entry in the 173-project Track 2 roster</h1><p class="scope">{esc(summary['scope'])}</p>
<section class="metrics"><div><strong>173 / 173</strong>entries with individual notes</div><div><strong>169</strong>READMEs retrieved</div><div><strong>2 + 2</strong>page-only + unavailable</div><div><strong>0</strong>competitor programs executed</div></section>
<section><h2>What changed in the assessment</h2><ul>{''.join('<li>'+esc(x)+'</li>' for x in summary['forma_assessment'])}</ul><p><a href="https://github.com/ybedoyab/drafty-meta">Drafty</a> · <a href="https://github.com/Anthony-Sin/inkbench">Inkbench</a> · <a href="https://github.com/TheKingOfMoney09/Photo-CAD">Photo-CAD</a> · <a href="https://github.com/SrishtiDesai/hull-ultimax">Hull Forge</a></p></section>
<section><h2>Coverage and interpretation</h2><ol>{''.join('<li>'+esc(x)+'</li>' for x in summary['method'])}</ol><h2>Directory caveats</h2><ul>{''.join('<li>'+esc(x)+'</li>' for x in summary['data_quality_notes'])}</ul><p><a href="all-173-review.csv">All 173 rows as CSV</a> · <a href="all-173-review.json">Structured review and source excerpts</a> · <a href="review-summary.json">Method and coverage</a> · <a href="https://artifacts.watt-mind.com/meta-hackathon-2026/">Unofficial directory</a></p></section>
<div class="controls"><input id="search" aria-label="Search all projects and analyst notes" placeholder="Search projects, ideas, evidence, limitations…"><select id="group" aria-label="Filter by review focus"><option value="">All focus groups</option>{options}</select><select id="status" aria-label="Filter by source access"><option value="">All source access</option><option value="readme_fetched">README retrieved</option><option value="repository_page_only">Repository page only</option><option value="unavailable">Primary source unavailable</option></select></div><p id="count" aria-live="polite">Showing 173 of 173 entries</p>
<div class="table-wrap"><table><thead><tr><th>Row</th><th>Repository</th><th>Source coverage</th><th>Individual assessment</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<script>const rows=[...document.querySelectorAll('tbody tr')];function filter(){{let n=0;const q=document.querySelector('#search').value.toLowerCase(),g=document.querySelector('#group').value,s=document.querySelector('#status').value;for(const r of rows){{const show=(!q||r.textContent.toLowerCase().includes(q))&&(!g||r.dataset.group===g)&&(!s||r.dataset.status===s);r.hidden=!show;n+=show;}}document.querySelector('#count').textContent=`Showing ${{n}} of 173 entries`;}}for(const id of ['search','group','status'])document.querySelector('#'+id).addEventListener('input',filter);</script></main></body></html>'''
    assert page.count('<tr data-group=') == 173
    (OUT / "review.html").write_text(page, encoding="utf-8")
    print(json.dumps({"entries": len(records), "coverage": coverage, "focus_groups": summary["focus_groups"], "report": str(OUT / "review.html"), "unverified_directory_flags": signals}, indent=2))


if __name__ == "__main__":
    main()
