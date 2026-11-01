"""Coverage-tracked screen of ALL latest directory entries. No inferred ranking."""
import hashlib
from html import escape
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'research/competition-all-2026-11-01'
OUT=ROOT/'output/acoustic-foundry'

RELATED={
 'Anthony-Sin/inkbench':('CAD design/check loop','Shared agent/verification architecture; inspected documentation describes solid-part checks, not acoustic wave design.'),
 'ybedoyab/drafty-meta':('CAD and simulation','Parametric solids, structural FEA and thickness search. Adjacent engineering workflow; different governing physics and endpoint.'),
 'SrishtiDesai/hull-ultimax':('Engineering inverse design','Hull sizing and simplified physics constraints; related numerical-design workflow, not duct acoustics.'),
 'hkdebendo/autolab':('Scientific discovery','Meta hypotheses plus UMA materials simulation. Strong scientific comparison; different domain and fabrication requirements.'),
 'khatabx-king/spiralai':('Scientific design','Graphene energy-storage screening and deterministic checks. Shared design/check loop; no acoustic-filter claim in inspected sections.'),
 'rafael-sanchezf/hush-iq':('Noise application','Predicts apartment noise from city records. Addresses noise exposure, not fabrication or acoustic filter synthesis.'),
 'Marwichmisi/NIATOLIP':('Alternative circuit direction','Natural-language PCB design, verification and fabrication export. Direct reason not to select generic AI electronics design.'),
 'Fqrina/BenchTruth':('Alternative circuit direction','Hardware feasibility rules, corrected build and artifacts. Overlaps inventory-aware electronics assistant.'),
 'Erlansoo/Lunes':('Alternative circuit direction','Directory describes circuit-board inspection and selecting probes; primary documentation retrieved for follow-up.'),
 'danny121583/traceforge':('Alternative circuit direction','Directory describes simulated faulty-board diagnosis; primary documentation retrieved for follow-up.'),
 'raahimnawaz/workbench-copilot':('Hardware demonstration','Voice/vision electronics workbench and real robot arm evidence. Competes on physical execution and Meta integration.'),
 'abelxmendoza/RobotForge-Hackathon':('Engineering systems','Robot specs and simulated motion gates; shared validation workflow but different physical problem.'),
 'TheKingOfMoney09/Photo-CAD':('Fabrication workflow','Photo-to-part reconstruction; relevant CAD/fabrication usability, different functional objective.'),
 'thenguyentrong/skill-translator':('Physical behavior','Video-to-robot skill translation; strong competing demonstration/evaluation, not acoustic geometry design.'),
 'AdvayGujar/pixelphysicist':('System identification','Video-to-tested physical equations. Related inference from measurements, different measured modality and output.'),
 'ahaan001/twinfit':('Alternative motion direction','Video-to-mechanism simulation twin, according to directory. Adds overlap to the earlier motion proposal.'),
 'maikunari/physics-twin':('Alternative motion direction','Video-fitted ramp-ball physics, according to directory.'),
 'compiler-aditya/kepler':('Alternative motion direction','Video-to-physics simulation, according to directory.'),
 'Balu-SG/videolab':('Alternative motion direction','Calibrated phone motion measurements, according to directory.'),
 'Bignesh14/glimmer-m5-selftune':('Alternative kernel direction','Muse Glimmer/Metal inference optimization; direct overlap with previously suggested kernel-tuning idea.'),
 'IgnacioSearles/oqed':('Alternative optimizer direction','LLM assembly superoptimization with measurement; competes on independently measured performance gains.'),
 'smpark00/seismorescue':('Measured signals','Recovering earthquake traces from analog films; competing scientific data/evaluation depth.'),
 'StefanRohringer/muse-qc-cell':('Hardware demonstration','Real robot inspection and sorting; competes on physical proof, not acoustic design.'),
 'scoobydoobydrew/meta_ai_hackathon':('Scientific design','Model proposes cell-signalling rules with formal verification; common proposer/verifier pattern.'),
 'Farshadmhd/beampilot':('Scientific measurement','Laser beam M2 measurement on simulated apparatus; adjacent autonomous measurement workflow.'),
 'ngoldbla/cv-meta-hackathon-2026':('Optimization systems','Emergency-logistics scenario/policy co-design; competes on measured optimization value.'),
 'idrissa-gif/ObjectJEPA':('Model research','Object-motion representation learning; competes on model contribution and held-out evaluation.'),
 'vherediadepvops/ProofLab-AI':('Scientific evidence','Hypothesis tests against measurements, according to directory. Broad scientific workflow overlap.'),
 'vherediadepvops/prooflab-ai-meta-hackathon-2026':('Scientific evidence','Related ProofLab repository; directory entries are not necessarily independent submissions.'),
 'surucuonur/meta-hackathon':('Alternative kernel direction','Inference memory-bandwidth optimization, according to directory.'),
 'jcamiloaa/gridxray':('Physical system inference','Hidden utility wiring inference via meters and simulation; related experiment/inference loop.'),
}


def main():
    rows=json.loads((SOURCE/'directory.json').read_text(encoding='utf-8'))
    receipt=json.loads((SOURCE/'receipt.json').read_text())
    OUT.mkdir(exist_ok=True,parents=True)
    records=[]
    for i,row in enumerate(rows,1):
        name=row['full_name'];summary=row.get('summary') or ''
        unknown=not summary or any(t in summary.lower() for t in ['placeholder','no documented','minimal public','no defined','no implemented','no details','minimal metadata'])
        category,comparison=RELATED.get(name,('Insufficient detail' if unknown else 'Different listed application',
           'Insufficient public directory detail to rule out overlap.' if unknown else
           'The listed application addresses a different task from target-spectrum-to-passive-duct-filter design. This is a directory-level screen only.'))
        path=SOURCE/'repositories'/name.replace('/','__')/'receipt.json'
        doc=json.loads(path.read_text()) if path.exists() else None
        records.append({'index':i,'repository':name,'url':row['html_url'],'theme_label':row.get('track'),
           'summary':summary,'category':category,'comparison':comparison,
           'review_scope':'Directory title and summary reviewed; documentation receipt separately listed.',
           'primary_documentation_status':doc['status'] if doc else 'not_refetched_this_turn'})
    (OUT/'all-projects-comparison.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
    coverage={'source':receipt,'entries_screened':len(records),'distinct_casefold_repository_names':len({r['repository'].lower() for r in records}),
      'push_the_frontier_entries':sum('push the frontier' in r['theme_label'].lower() for r in records),
      'highlighted_adjacent_entries':sum(r['repository'] in RELATED for r in records),
      'insufficient_description_entries':sum(r['category']=='Insufficient detail' for r in records),
      'primary_readmes_retrieved_this_turn':sum(r['primary_documentation_status']=='readme_fetched' for r in records),
      'direct_acoustic_design_matches_identified_in_listed_descriptions':0,
      'scope':'All listed titles/summaries screened. Targeted primary documentation only; not a code audit of every repository or proof of uniqueness.',
      'decision':'Build Acoustic Foundry: target noise spectrum to editable passive duct-filter geometry, calibrated against physical measurements when available.',
      'reason':'Distinct physical output and audible/measurable demonstration; reuses existing CAD/runtime; small forward model runs on CPU.',
      'known_prior_art':'Helmholtz arrays and ML acoustic inverse design are established. Model/check/repair is not novel.',
      'remaining_gates':['Calibrate losses and end corrections with actual measurements.','Reproduce published/reference acoustics beyond internal equation checks.',
                         'Establish useful Meta contribution against numerical baselines.','Complete physical assembly and controlled acoustic measurement.'],
      'ranking':'No official rank, winning probability or global novelty claim.'}
    (OUT/'competition-coverage.json').write_text(json.dumps(coverage,indent=2),encoding='utf-8')
    body=[]
    ordered=sorted(records,key=lambda r:(r['repository'] not in RELATED,r['index']))
    for r in ordered:
        body.append(f'<tr><td>{r["index"]}</td><td><a href="{escape(r["url"],quote=True)}">{escape(r["repository"])}</a><small>{escape(r["theme_label"])}</small></td><td>{escape(r["summary"])}</td><td><b>{escape(r["category"])}</b><p>{escape(r["comparison"])}</p></td></tr>')
    html='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Acoustic Foundry · Decision and competition</title>
<style>body{font:15px system-ui;color:#203039;background:#f7f8f6;margin:0;padding:40px;max-width:1500px}h1{font-size:40px;letter-spacing:-1.5px}p{line-height:1.6;max-width:1050px}.lead{font-size:20px}section{padding:20px 24px;background:white;border:1px solid #dfe5df;border-radius:12px;margin:20px 0}.stats{display:flex;gap:35px}.stats strong{font-size:28px;display:block}input{padding:12px;width:calc(100% - 28px);border:1px solid #bbc8bd;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:15px 12px;text-align:left;border-bottom:1px solid #dfe5df;vertical-align:top}td:first-child{width:35px}td:nth-child(2){width:260px}td:nth-child(3){width:28%}small{display:block;color:#687870;margin-top:7px}a{color:#21664e}th{background:#e8eee8;position:sticky;top:0}.muted{color:#66766e}</style>
<h1>Acoustic Foundry</h1><p class="lead">Target noise spectrum → passive duct filter → editable prototype → measured calibration.</p>
<section><div class="stats"><div><strong>COUNT</strong>directory entries screened</div><div><strong>FRONTIER</strong>Push the Frontier entries</div><div><strong>RELATED</strong>adjacent entries highlighted</div></div>
<p>Decision: build the acoustic filter workflow. The directory screen found no direct acoustic-filter synthesis claim in the listed descriptions. This does not prove uniqueness or predict a win. Established acoustic inverse-design research is prior art.</p>
<p class="muted">Every listed title and summary was screened. Eleven selected root READMEs were retrieved; selected sections informed the comparisons. This is not a full source-code audit. Missing descriptions and stale directory summaries remain limitations. Duplicate repositories/teams may occur. Third-party scores are not official judging.</p></section>
<section><b>First milestone</b><p>A real Meta proposal and conventional numerical baseline on one constructed two-tone duct task. Independent wave-balance checks and split solid exports. Predictions use assumed losses, rigid walls and matched terminations. Physical measurements and AI superiority are not established.</p>
<p><a href="competition-coverage.json">Coverage and source hash</a> · <a href="all-projects-comparison.json">All comparison records</a> · <a href="development-v1/results.json">Development experiment</a></p></section>
<input id="q" placeholder="Search all projects, applications or comparisons" aria-label="Search projects"><p id="count">COUNT entries</p>
<table><thead><tr><th>#</th><th>Project</th><th>Listed idea</th><th>Comparison with our direction</th></tr></thead><tbody>ROWS</tbody></table>
<script>const q=document.getElementById('q'),rows=[...document.querySelectorAll('tbody tr')];q.addEventListener('input',()=>{let n=0;const s=q.value.toLowerCase();for(const r of rows){const show=r.textContent.toLowerCase().includes(s);r.hidden=!show;if(show)n++}document.getElementById('count').textContent=n+' entries'});</script>'''
    html=html.replace('COUNT',str(len(records))).replace('FRONTIER',str(coverage['push_the_frontier_entries'])).replace('RELATED',str(coverage['highlighted_adjacent_entries'])).replace('ROWS',''.join(body))
    (OUT/'competition.html').write_text(html,encoding='utf-8')
    assert html.count('<tr>')==len(rows)+1
    assert len(records)==receipt['entries']
    print(json.dumps(coverage,indent=2))


if __name__=='__main__':main()
