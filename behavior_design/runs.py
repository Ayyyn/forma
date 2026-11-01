"""Versioned protocol snapshots and immutable raw experiment directories."""
import argparse,hashlib,json,shutil,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from copy import deepcopy
import numpy as np
from .tasks import tasks,reference,audit_task,TEACHER
from .laboratory import Laboratory,numerical
from .model import evaluate,predict,independent_audit,geometry_budget
from .agent import run_meta

ROOT=Path(__file__).resolve().parents[1];OUTPUT=ROOT/'output/behavior-design'
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
def freeze():
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8];directory=OUTPUT/'studies'/name;directory.mkdir(parents=True)
    sources=sorted((ROOT/'behavior_design').glob('*.py'))+[ROOT/'kresling_proof/model.py',ROOT/'kresling_proof/oracle.py',ROOT/'scripts/api_preflight.py',ROOT/'structure_lab/tool_protocol.py',ROOT/'research/behavior_component_check.py']
    hashes={}
    for source in sources:
        relative=source.relative_to(ROOT);dest=directory/'source'/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);hashes[str(relative).replace('\\','/')]=hashlib.sha256(source.read_bytes()).hexdigest()
    protocol={'id':name,'candidate_allowance_per_task_policy':240,'policies':['numerical','single_pass','adaptive'],'tasks':['initial','compact_revision'],'primary_metric':'Held-out force RMS / full-stroke target maximum, subject to every mechanical screen and independent checks. No post-hoc target relaxation.','success_threshold':{'normalized_RMS':.05,'normalized_max':.10},'comparison':'Equal candidate allowance and same tools; different model-request budgets by controller definition. Not equal wall-clock or CPU; one development target, no general AI-efficacy claim.','reference_model':'Ideal bilateral axial springs + guides + return springs; published Kresling effective mechanics. No hardware or fabrication validation.','cost_cap':'Estimated $10 per Meta task/controller; 2 single-pass + at most12 adaptive calls, each4096 output tokens. Not an actual billing cap.','source_hashes':hashes,'dependencies':{'numpy':np.__version__}}
    write(directory/'manifest.json',protocol);write(directory/'tasks.json',tasks());write(directory/'reference.json',reference());return directory

def execute(directory,policy,task):
    path=directory/'runs'/f"{task['id']}-{policy}";path.mkdir(parents=True,exist_ok=False)
    lab=Laboratory(task);started=time.monotonic()
    try:
        receipt=numerical(lab) if policy=='numerical' else run_meta(lab,path,policy=='single_pass');best=lab.best();audit=None
        if best:
            d=best['result']['design'];ref=json.loads((directory/'reference.json').read_text());hidden=evaluate(d,audit_task(task,ref),dense=True);independent=independent_audit(d,hidden['points']);fit=best['result'];audit={'heldout':hidden,'independent':independent,'accepted':bool(hidden['target_passed'] and fit['target_passed'] and independent['passed']),'scope':'96 disjoint travel points, independent force/energy check and denser Kresling twist scan; offline auditing not policy-query work. Not a global stability proof or physical validation.'}
        result={'policy':policy,'task_id':task['id'],'seconds':time.monotonic()-started,'receipt':receipt,'candidate_queries':len(lab.records),'candidate_allowance':lab.budget,'first_nominal_success_query':next((i+1 for i,r in enumerate(lab.records) if r.get('target_passed')),None),'selected_candidate':best['id'] if best else None,'selected':lab.summary(best) if best else None,'audit':audit,'records':lab.records,'events':lab.events,'physical_validation':False}
        write(path/'result.json',result);print(json.dumps({'completed':path.name,'queries':result['candidate_queries'],'selected':result['selected'],'accepted':audit['accepted'] if audit else False,'seconds':result['seconds']}),flush=True);return result
    except Exception as e:
        write(path/'failure.json',{'error':str(e),'records':lab.records,'events':lab.events});raise

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--study');parser.add_argument('--policy',choices=['all','numerical','single_pass','adaptive'],default='numerical');args=parser.parse_args();directory=OUTPUT/'studies'/args.study if args.study else freeze();print('STUDY '+str(directory),flush=True)
    manifest=json.loads((directory/'manifest.json').read_text())
    for name,digest in manifest['source_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Live source changed since freeze: '+name)
    for task in json.loads((directory/'tasks.json').read_text()):
        for policy in manifest['policies'] if args.policy=='all' else [args.policy]:
            if (directory/'runs'/f"{task['id']}-{policy}").exists():continue
            execute(directory,policy,task)
if __name__=='__main__':main()
