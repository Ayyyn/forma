"""Collect reproducible Forma evidence without making model calls."""
from datetime import datetime,timezone
import hashlib
import html
import io
import json
from pathlib import Path
import unittest
from crate_studio import agent
from crate_studio.engine import DEFAULT_SPEC,DEFAULT_REQUIREMENTS,evaluate,optimize
from crate_studio.evaluation import offline_report
from research.verify_forma_live import score

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'/'forma'

def dump(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_crate_*.py')
    tested=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (OUT/'test-output.txt').write_text(stream.getvalue(),encoding='utf-8')
    unit={'tests':tested.testsRun,'passed':tested.wasSuccessful(),'failures':len(tested.failures),'errors':len(tested.errors),'independent_seeded_geometry_cases':384}
    dump(OUT/'tests.json',unit);dump(OUT/'offline-evaluation.json',offline_report())
    frozen=OUT/'acceptance-v1';cases=json.loads((frozen/'cases.json').read_text());replay=[]
    for c in cases:
        p=json.loads((frozen/(c['id']+'.json')).read_text());events=[json.loads(x) for x in (agent.RUNS/p['run_id']/'events.jsonl').read_text().splitlines()]
        try:
            plan=agent.parse_plan(events[-1]['public_response']);current=agent.apply_plan({'spec':DEFAULT_SPEC,'requirements':DEFAULT_REQUIREMENTS},plan,c['prompt']);replayed=score(c,current)
        except Exception as error:replayed={'id':c['id'],'passed':False,'errors':[str(error)]}
        replay.append(replayed)
    dump(OUT/'current-source-replay.json',{'passed':all(x['passed'] for x in replay),'cases':replay,'model_calls':0,'scope':'Replays saved actual model plans through the current deterministic implementation; not a new live or held-out trial.'})
    events=[]
    for path in agent.RUNS.glob('*/events.jsonl'):
        for line in path.read_text().splitlines():events.append(json.loads(line))
    live={'requests':len(events),'http_200':sum(e['transport'].get('http_status')==200 for e in events),'unique_response_ids':len({e['response_id'] for e in events if e['response_id']}),'estimated_cost_usd':sum(e['budget_charge_usd'] for e in events),'billing_verified':False}
    http=json.loads((OUT/'http-verification.json').read_text())
    props=[]
    for folder in agent.RUNS.iterdir():
        path=folder/'proposal.json'
        if path.exists():
            p=json.loads(path.read_text());props.append({'run_id':folder.name,'status':p['status'],'model':p['model'],'calls':p['calls'],'spec':p['spec'],'requirements':p['requirements'],'metrics':p['result']['metrics']})
    sources=[*sorted((ROOT/'crate_studio').glob('*.py')),*sorted((ROOT/'crate_studio/web').glob('*.*'))]
    source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    report={'generated_utc':datetime.now(timezone.utc).isoformat(),'unit_tests':unit,'live_api':live,'frozen_acceptance':json.loads((frozen/'results.json').read_text()),'current_source_replay_passed':all(x['passed'] for x in replay),'http_checks':{'passed':http['passed'],'count':len(http['checks'])},'source_hashes':source_hashes,'proposals':props,'limitations':['Restricted rectangular butt-joint panel family.','Material constants and stock lists are reference assumptions, not supplier qualification.','Idealized linear floor screening is not a safe load rating or physical validation.','Acceptance inputs are constructed app tests; no external CAD benchmark or customer time-saving result.','No verified competitive advantage or winning probability.']}
    dump(OUT/'verification-summary.json',report)
    esc=lambda s:html.escape(str(s))
    rows=''.join(f'<tr><td>{esc(r["id"])}</td><td>{"Pass" if r["passed"] else "Fail"}</td><td>{esc(r.get("status",""))}</td><td>{esc(r.get("calls",""))}</td></tr>' for r in report['frozen_acceptance']['results'])
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Forma — verification record</title><style>body{{font:15px/1.65 system-ui;color:#243348;background:#f7f8fb;max-width:1050px;margin:40px auto;padding:25px}}h1{{font-size:35px;letter-spacing:-1px}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.card,section{{background:white;padding:22px;border:1px solid #e0e5ef;border-radius:8px;margin:14px 0}}.card strong{{display:block;font-size:28px;color:#4265c5}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #e5e8ef}}a{{color:#4265c5}}.scope{{border-left:3px solid #d3aa5e;padding:12px 18px;background:#fff9ee}}code{{font:12px ui-monospace,monospace}}@media(max-width:650px){{.cards{{grid-template-columns:1fr}}}}</style>
    <p>FORMA / ENGINEERING EVIDENCE</p><h1>Intent → design → checked artifacts</h1><p>A local Meta-assisted design system for one explicit panel-enclosure family.</p>
    <div class="cards"><div class="card"><strong>{unit['tests']}</strong>passing tests, including 384 seeded independent geometry checks</div><div class="card"><strong>{report['frozen_acceptance']['passed']}/8</strong>frozen live integration cases accepted</div><div class="card"><strong>{len(http['checks'])}</strong>real HTTP and export checks passed</div></div>
    <p class="scope">These are engineering/application verification results. They do not establish physical safety, customer time savings or general CAD benchmark performance.</p>
    <section><h2>Actual Meta calls</h2><p>{live['requests']} requests; {live['http_200']} HTTP 200 responses; {live['unique_response_ids']} unique response IDs. Provisional estimated cost ${live['estimated_cost_usd']:.4f}. Billing and remaining credits unverified.</p><p>The eight-case acceptance run uses first proposals plus optional checker feedback. Other calls are interactive end-to-end demonstrations. No comparison claiming equal inference budgets or numerical optimizer superiority is made.</p><table><tr><th>Acceptance task</th><th>Result</th><th>Disposition</th><th>Calls</th></tr>{rows}</table></section>
    <section><h2>What is checked</h2><p>Independent envelope-minus-cavity arithmetic, exact stock enumeration, capacity/envelope/mass limits, idealized floor-deflection math, BREP validity, cavity intrusion, panel intersections, STEP round trips, watertight STL round trips and editable-source regeneration after a parameter change.</p><p>UI verification includes manual preview/save, live Meta request/preview/apply, retained requirements in a follow-up conversation, responsive drawers, drawing and export workflows.</p></section>
    <section><h2>Evidence files</h2><p><a href="verification-summary.json">Complete summary and source hashes</a> · <a href="test-output.txt">Unit-test output</a> · <a href="http-verification.json">HTTP checks</a> · <a href="acceptance-v1/results.json">Frozen live results</a> · <a href="current-source-replay.json">Current-source replay</a> · <a href="offline-evaluation.json">Independent analytic scenarios</a></p><h2>Limits</h2><ul>{''.join('<li>'+esc(x)+'</li>' for x in report['limitations'])}</ul></section></html>'''
    (OUT/'verification.html').write_text(page,encoding='utf-8')
    print(json.dumps({'tests':unit,'live':live,'http_checks':len(http['checks']),'report':str(OUT/'verification.html')},indent=2))
    if not tested.wasSuccessful() or not all(x['passed'] for x in replay):raise SystemExit(1)

if __name__=='__main__':main()
