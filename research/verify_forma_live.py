"""Frozen, explicit live integration acceptance cases; not customer validation.

Run --prepare first (no network). --run records actual Meta responses without
overwriting any earlier run. Cases test app capabilities, not general CAD skill.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
from crate_studio.engine import DEFAULT_SPEC,DEFAULT_REQUIREMENTS,evaluate
from crate_studio.agent import propose

ROOT=Path(__file__).resolve().parents[1]
CASES=[
 {'id':'material','prompt':'Switch to polypropylene at 8 mm. Keep all clear internal dimensions and existing requirements.','status':'ready','spec':{'material':'polypropylene','thickness_mm':8}},
 {'id':'minimum_mass','prompt':'Find the lightest stock thickness in birch plywood. Preserve all internal dimensions and existing requirements.','status':'ready','spec':{'material':'birch_plywood','thickness_mm':6}},
 {'id':'load_screen','prompt':'Keep birch plywood and all internal dimensions. Screen a uniformly distributed payload of 20 kg with floor deflection no more than 2 mm. Find the lightest stock thickness.','status':'ready','spec':{'thickness_mm':12},'requirements':{'payload_kg':20,'max_floor_deflection_mm':2}},
 {'id':'inverse_capacity','prompt':'Use polypropylene. Resize as needed to provide at least 80 litres within the existing outside envelope. Find the lightest stock-size design.','status':'ready','spec':{'material':'polypropylene','thickness_mm':3},'requirements':{'min_capacity_l':80,'lock_inner_dimensions':False}},
 {'id':'inch_conversion','prompt':'Set the clear internal width to 24 inches. Allow outside width up to 700 mm. Keep all other dimensions and requirements.','status':'ready','spec':{'inner_width_mm':609.6},'requirements':{'max_outer_width_mm':700}},
 {'id':'ambiguous_material','prompt':'Switch from plywood to plastic, keep everything else.','status':'clarify'},
 {'id':'unsupported_feature','prompt':'Add lifting handles and certify the crate safe for overhead lifting.','status':'clarify'},
 {'id':'infeasible_envelope','prompt':'Preserve the 600 mm internal width but make the outside width at most 590 mm. Keep everything else.','status':'withhold','requirements':{'max_outer_width_mm':590}},
]

def dump(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def prepare(folder):
    folder.mkdir(parents=True,exist_ok=False)
    dump(folder/'cases.json',CASES)
    dump(folder/'protocol.json',{'origin':'Constructed application integration acceptance tasks, not customer cases or external benchmark','created_at':datetime.now(timezone.utc).isoformat(),'inputs':{'spec':DEFAULT_SPEC,'requirements':DEFAULT_REQUIREMENTS},'model':'muse-wonder-1.0','max_calls':16,'max_output_tokens_per_call':4096,'app_total_estimated_budget_usd':5,'billing_verified':False,'scoring':'Frozen exact fields plus retained unchanged fields. Optimizer-generated dimensions assessed numerically. No commercial baseline or held-out generalization claim.'})
    src=folder/'source';src.mkdir()
    for name in ['engine.py','agent.py']:shutil.copyfile(ROOT/'crate_studio'/name,src/name)
    dump(folder/'manifest.json',{str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [folder/'cases.json',folder/'protocol.json',*src.glob('*.py')]})

def score(case,p):
    errors=[]
    if case['status']=='withhold':
        if p['status']=='ready':errors.append('Infeasible request cleared')
    elif p['status']!=case['status']:errors.append('Disposition '+p['status'])
    if case['status']=='ready':
        for section in ['spec','requirements']:
            for k,want in case.get(section,{}).items():
                got=p[section][k]
                if isinstance(want,(float,int)) and not isinstance(want,bool):ok=abs(got-want)<1e-5
                else:ok=got==want
                if not ok:errors.append(f'{section}.{k}: {got} != {want}')
        expected_req={**DEFAULT_REQUIREMENTS,**case.get('requirements',{})}
        if p['requirements']!=expected_req:errors.append('Retained requirement changed without expected authorization')
        if case['id']!='inverse_capacity':
            expected_spec={**DEFAULT_SPEC,**case.get('spec',{})}
            if p['spec']!=expected_spec:errors.append('Retained design field changed')
        if not evaluate(p['spec'],expected_req)['passed']:errors.append('Independent re-evaluation fails')
    elif case['status']=='clarify':
        if p['spec']!=DEFAULT_SPEC or p['requirements']!=DEFAULT_REQUIREMENTS:errors.append('Clarification changed design')
        if not p['questions']:errors.append('Missing clarification question')
    return {'id':case['id'],'passed':not errors,'errors':errors,'status':p['status'],'calls':p.get('calls'),'estimated_cost_usd':p.get('estimated_cost_usd'),'run_id':p.get('run_id')}

def run(folder):
    if (folder/'results.json').exists() or (folder/'started.json').exists():raise ValueError('Use a new directory; previous run is immutable')
    manifest=json.loads((folder/'manifest.json').read_text())
    for name,digest in manifest.items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen input/source changed')
    for name in ['agent.py','engine.py']:
        if (ROOT/'crate_studio'/name).read_bytes()!=(folder/'source'/name).read_bytes():raise ValueError('Live source differs from freeze')
    dump(folder/'started.json',{'utc':datetime.now(timezone.utc).isoformat()})
    cases=json.loads((folder/'cases.json').read_text());project={'spec':DEFAULT_SPEC,'requirements':DEFAULT_REQUIREMENTS};results=[]
    for c in cases:
        try:
            proposal=propose(project,c['prompt']);dump(folder/(c['id']+'.json'),proposal);row=score(c,proposal)
        except Exception as e:row={'id':c['id'],'passed':False,'errors':[str(e)]}
        results.append(row);print(json.dumps(row),flush=True);dump(folder/'partial-results.json',results)
        if row.get('errors') and any('request failed' in e.lower() or 'budget' in e.lower() for e in row['errors']):break
    dump(folder/'results.json',{'completed':len(results),'passed':sum(x['passed'] for x in results),'total':len(cases),'results':results,'limitation':'Constructed integration cases. No customer time saving, general CAD benchmark, physical qualification or unique Meta advantage established.'})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);p.add_argument('--directory',type=Path,required=True);args=p.parse_args()
    (prepare if args.mode=='prepare' else run)(args.directory)
