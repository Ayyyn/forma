"""Verified exploratory pilot: python -m structure_lab verify / freeze / run / report."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
from .design import task_cases,public_geometry
from .search import Laboratory,numerical_portfolio,ranked,render_geometry
from .agent import run_meta,MODEL,MAX_TURNS,RENDER_LOCK
from .verification import verify

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'benchmarks/structure-pilot-v3'


def save(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')


def sources():
    paths=sorted((ROOT/'structure_lab').glob('*.py'))+[ROOT/'scripts/api_preflight.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def freeze(directory):
    if (directory/'manifest.json').exists():raise ValueError('Preserve existing version; use another directory for a changed pilot')
    gate=verify()
    if not gate['passed']:raise RuntimeError('Mechanics gate failed')
    manifest={'status':'exploratory development pilot; not held-out confirmatory evidence','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
      'version_note':'v3 retains the v2 ordering correction and adds a strict adapter for observed native/XML/single-plan-JSON tool encodings. Plan length is bounded by the same 96-slot search budget, removing the arbitrary eight-item limit. v1/v2 remain diagnostic archives; full matrix rerun, never pooled.',
      'tasks':task_cases(),'seeds':[101,202],'methods':['numerical','single_pass','tool_agent'],
      'charged_search_budget':96,'common_final_oracle_checks_max':1,
      'invalid_new_design_costs_one_slot':True,'identical_design_cache_hits_are_free_and_logged':True,
      'derivative_work':'Every production solve factors the same frame and solves two RHS; analytic adjoint sensitivities use those solutions, not extra sampled candidates.',
      'model':MODEL,'reasoning_effort_requested':'medium','maximum_output_tokens_per_request':8192,
      'maximum_agent_requests':MAX_TURNS,'single_pass_requests':1,'temperature':.2,'timeout_seconds':180,
      'fairness':['Same exact task, geometry, graph language, feature/linearity limits, derivative optimizer, cache and final oracle.',
          'Numerical control screens conventional topology width extremes, prioritizes constrained gradient sizing, and mutates graph members beyond templates.',
          'Single-pass Meta chooses one optimizer portfolio without model feedback. The tool agent can edit edges, optimize, inspect sensitivities and request actual geometry images.',
          'Primary reporting: verified feasibility, minimum beam-volume proxy, first feasible charged/actual solve count, actual solver work, latency and API usage.',
          'Search may finish before using its allowance. No requirement changes, hidden feasible initial design, outcome replacement, or API transport retries.',
          'Invalid/truncated model decisions can consume a slot and receive explicit feedback within the fixed request cap; every request is retained.',
          'All tasks are public development cases whose numerical feasibility was checked before freezing. This is not an unseen-task benchmark or evidence of clinical applicability.'],
      'limitations':['Only linear in-plane rigid-jointed frames on a fixed 9-node/18-edge ground graph; no arbitrary structures or global-optimum guarantee.',
          'Beam-volume proxy double-counts overlaps at ideal joints; it is not exact CAD material volume.',
          'No large motion, fracture, plasticity, joint concentrations, fatigue, contact or loaded buckling certification.',
          'All coefficients/requirements are synthetic; no physical experiments, prototype savings, patient data or medical advice.',
          'Two seeds on four development tasks do not establish statistical superiority or new-to-science structures.'],
      'source_sha256':sources(),'verification':gate}
    directory.mkdir(parents=True,exist_ok=True);save(directory/'manifest.json',manifest)
    for rel,expected in manifest['source_sha256'].items():
        raw=(ROOT/rel).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise RuntimeError('Source changed during freeze')
        target=directory/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(raw)
    print(json.dumps({'frozen':str(directory),'cells':len(manifest['tasks'])*len(manifest['seeds'])*3,'verification':gate},indent=2))


def load(directory):
    m=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if m['source_sha256']!=sources():raise RuntimeError('Pilot source drift; retain this version and freeze another')
    return m


def cell(directory,task,seed,method):
    name=f"{task['id']}-{seed}-{method}";target=directory/'runs'/f'{name}.json'
    if target.exists():return {'cell':name,'status':'already_saved'}
    assets=directory/'assets'/name;assets.mkdir(parents=True,exist_ok=True)
    lab=Laboratory(task);start=time.perf_counter()
    if method=='numerical':numerical_portfolio(lab,seed);model={'actual_api_calls':0,'events':[]}
    else:model=run_meta(lab,seed,assets,planner=method=='single_pass')
    elapsed=time.perf_counter()-start;certificate=lab.final_verify();best=lab.best
    feasible=bool(best and best.get('feasible') and certificate['passed'] and certificate.get('independent_constraints_feasible'))
    first=next((r for r in lab.records if r.get('feasible')),None)
    record={'cell':name,'method':method,'task_id':task['id'],'seed':seed,'physical_data':False,
        'elapsed_seconds':elapsed,'charged_search_slots':len(lab.records),'actual_frame_assemblies':lab.physics_solves,
        'cache_hits':lab.cache_hits,'best':best,'verified_feasible':feasible,
        'first_feasible_charged_index':first['attempt'] if first else None,
        'first_feasible_frame_solve_index':first.get('physics_solve_index') if first else None,
        'certificate':certificate,'model':model,'candidates':lab.records,'optimizer_calls':lab.optimizer_calls}
    if best:
        with RENDER_LOCK:render_geometry(task,best,assets/'selected.png')
    target.parent.mkdir(exist_ok=True)
    with target.open('x',encoding='utf-8') as f:json.dump(record,f,indent=2,allow_nan=False)
    return {'cell':name,'verified_feasible':feasible,'slots':len(lab.records),'volume':best.get('volume_mm3') if best else None,'calls':model['actual_api_calls']}


def run(directory,methods,workers):
    m=load(directory)
    jobs=[(t,s,method) for t in m['tasks'] for s in m['seeds'] for method in methods
           if not (directory/'runs'/f"{t['id']}-{s}-{method}.json").exists()]
    print(f'{len(jobs)} missing pilot cells; {workers} workers',flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(cell,directory,*job) for job in jobs]
        for i,future in enumerate(as_completed(futures),1):print(json.dumps({'saved':i,'of':len(jobs),**future.result()}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['verify','freeze','run','report'])
    p.add_argument('--directory',type=Path,default=DEFAULT);p.add_argument('--workers',type=int,choices=[1,2],default=2)
    p.add_argument('--methods',nargs='+',choices=['numerical','single_pass','tool_agent'],default=['numerical','single_pass','tool_agent'])
    a=p.parse_args()
    if a.command=='verify':print(json.dumps(verify(),indent=2))
    elif a.command=='freeze':freeze(a.directory)
    elif a.command=='run':run(a.directory,a.methods,a.workers)
    else:
        from .report import report
        report(a.directory)


if __name__=='__main__':main()
