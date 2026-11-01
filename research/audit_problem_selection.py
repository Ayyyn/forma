"""Independent ledger/provenance and arithmetic audit; no paid calls."""
import hashlib,json,math
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'output/problem-selection-v2-live'
inputs={r['id']:r['packet'] for r in json.loads((D/'inputs.json').read_text())}
gold={r['id']:r for r in json.loads((D/'gold.json').read_text())}
events=[json.loads(x) for x in (D/'api-events.jsonl').read_text(encoding='utf-8').splitlines()]
manifest=json.loads((D/'manifest.json').read_text())
for rel,want in manifest.items():assert hashlib.sha256((D/rel).read_bytes()).hexdigest()==want,rel
assert len(events)==26
assert len({e['response_id'] for e in events})==26
assert all(e['transport']['http_status']==200 and e['finish_reason']=='stop' for e in events)
assert len({(e['case_id'],e['stage']) for e in events})==26
core_correct={k:0 for k in ('single_pass','checker_feedback')}
for e in events:
    p=e['request'];packet=inputs[e['case_id']]
    encoded=json.dumps(p,ensure_ascii=False).encode('utf-8')
    assert hashlib.sha256(encoded).hexdigest()==e['request_sha256']
    assert json.loads(p['messages'][1]['content'])==packet
    assert 'gold_contract' not in json.dumps(p)
    assert 'gold.json' not in json.dumps(p)
    assert len(p['messages'])==(2 if e['stage']=='single_pass' else 4)
    if e['stage']=='checker_feedback':
        first=next(x for x in events if x['case_id']==e['case_id'] and x['stage']=='single_pass')
        assert p['messages'][2]==first['public_response']
        assert json.loads(p['messages'][3]['content'])['deterministic_check']==first['checks']
    parsed=json.loads(e['public_response']['content'])
    assert parsed==e['submission']
    c=parsed['contract'];g=gold[e['case_id']]['contract']
    core_correct[e['stage']]+=int(all(c[k]==g[k] if type(g[k]) not in (int,float) else c[k] is not None and math.isclose(c[k],g[k],abs_tol=1e-7,rel_tol=0) for k in ('width_mm','thickness_mm','material','min_opening_mm','basis')))
    m=packet['proposed_model'];w=Decimal(str(m['width_mm']));t=Decimal(str(m['thickness_mm']))
    opening=w-t-t
    assert abs(float(opening)-e['checks']['nominal_opening_mm'])<1e-10
    tol=m['tolerances_mm']
    if tol:
        dw=Decimal(str(tol['width']));dt=Decimal(str(tol['thickness']))
        independent=min(w+sw*dw-(t+s1*dt)-(t+s2*dt) for sw in (-1,1) for s1 in (-1,1) for s2 in (-1,1))
        assert abs(float(independent)-e['checks']['worst_case_opening_mm'])<1e-10
    for ref in parsed['evidence']:
        s=next(s for s in packet['sources'] if s['id']==ref['source_id'])
        assert ref['quote'] in s['text']
cost=sum(e['transport']['usage']['prompt_tokens']*4e-6+e['transport']['usage']['completion_tokens']*20e-6 for e in events)
out={'status':'passed','request_contexts_checked':len(events),'unique_HTTP_200_responses':26,'source_and_input_hashes_checked':len(manifest),
     'core_numeric_material_and_basis_fields_correct':core_correct,'cost_estimate_USD':cost,'billing_verified':False,
     'post_run_adjudication':{'case':'R02','frozen_result':'12/13 exact contracts and dispositions for each Meta mode; unchanged',
                             'observed':'All core dimensions, material and basis match frozen expectations in 13/13 for each mode. Only unresolved flag/disposition differs for supplier suggestion.',
                             'interpretation':'Clarify instead of block is defensible because the system instruction also says to flag an unapproved substitution. This is an ambiguous rubric/prompt boundary, not a demonstrated dimensional error. Do not tune the prompt and rescore the same cases as held out.',
                             'safety':'Both interpretations withhold clearance. Source substring checks do not prove semantic correctness.'},
     'scope':'Audit proves ledger consistency, synthetic expected-field comparisons and interval arithmetic, not customer usefulness, native CAD handling or semantic generalization.'}
(D/'independent-audit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
