"""Source snapshots and live, persisted structured investigation runs."""
from datetime import datetime,timezone
import hashlib,json,shutil,threading,time,uuid
from pathlib import Path
from .laboratory import Laboratory
from .agent import run_meta
ROOT=Path(__file__).resolve().parents[1];RUNS=ROOT/'output/mechanical-workbench/runs'
def atomic_json(path,data):
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(data));temporary.replace(path)

def public_scenario(s):return {k:v for k,v in s.items() if not k.startswith('_')}

def run(scenario,policy='numerical',notify=None,run_id=None):
    if policy not in ['meta','numerical']:raise ValueError('Unknown controller')
    run_id=run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8];directory=RUNS/run_id;directory.mkdir(parents=True,exist_ok=False);snapshot={}
    paths=list((ROOT/'mechanical_workbench').glob('*.py'))+[ROOT/'spatial_actuator/mechanics.py',ROOT/'spatial_actuator/oracle.py',ROOT/'spatial_actuator/figures.py',ROOT/'scripts/api_preflight.py',ROOT/'structure_lab/tool_protocol.py']
    for p in paths:
        name=p.relative_to(ROOT).as_posix();snapshot[name]=hashlib.sha256(p.read_bytes()).hexdigest();target=directory/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    manifest={'id':run_id,'policy':policy,'created_utc':datetime.now(timezone.utc).isoformat(),'source_hashes':snapshot,'candidate_limit':32,'virtual_test_limit':3,'maximum_API_calls':4 if policy=='meta' else 0,'estimated_API_cap_USD':5 if policy=='meta' else 0,'scope':'Constructed development workflow, no unseen efficacy or physical-validation claim. Shared numerical sizing tools.','scenario':public_scenario(scenario)}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2));atomic_json(directory/'status.json',{'id':run_id,'status':'running','policy':policy,'created_utc':manifest['created_utc']})
    def emit(event):
        with (directory/'timeline.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event)+'\n')
        if notify:notify(event)
    lab=Laboratory(scenario,emit);started=time.monotonic();api=None
    try:
        lab.event('study','Investigation started',{'policy':policy,'node_count':len(scenario['design']['nodes_mm']),'member_count':len(scenario['design']['edges']),'source':scenario['source']})
        if policy=='numerical':lab.virtual_test('coupon_cantilever');lab.size(maximum_evaluations=16)
        else:api=run_meta(lab,directory)
        final=lab.finish();result={'id':run_id,'status':'complete','policy':policy,'seconds':time.monotonic()-started,'API':api,'virtual_tests':lab.tests,'revisions':lab.records,'final':final,'scenario':public_scenario(scenario)}
        atomic_json(directory/'result.json',result);atomic_json(directory/'status.json',{'id':run_id,'status':'complete','policy':policy,'accepted':final['accepted'],'created_utc':manifest['created_utc']});return result
    except Exception as error:
        result={'id':run_id,'status':'failed','policy':policy,'error':str(error),'API':api,'revisions':lab.records,'ledger':lab.ledger,'virtual_tests':lab.tests,'scenario':public_scenario(scenario)};atomic_json(directory/'result.json',result);atomic_json(directory/'status.json',{'id':run_id,'status':'failed','policy':policy,'error':str(error),'created_utc':manifest['created_utc']});raise

def list_runs():
    records=[json.loads(p.read_text()) for p in RUNS.glob('*/status.json')] if RUNS.exists() else []
    return sorted(records,key=lambda r:r.get('created_utc',r['id']),reverse=True)
