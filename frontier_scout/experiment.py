"""Frozen exploratory comparison on experimental tables, not a physical lab."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib,json,platform,shutil,time
from pathlib import Path
import numpy as np
import scipy,sklearn
from threadpoolctl import threadpool_limits
from .data import ROOT,VENDOR,CASES,Dataset,audit
from .policy import choose,domain_features
from .meta import Budget,propose

SEEDS=[31,47,71,97]
METHODS=['random','gp_raw','rf_ei','gp_domain','meta_features']

def hashes():
    files=list((ROOT/'frontier_scout').glob('*.py'))+[ROOT/'docs/FRONTIER_MATERIALS_PROTOCOL.md',ROOT/'scripts/api_preflight.py',ROOT/'structure_lab/tool_protocol.py',VENDOR/'LICENSE',VENDOR/'README.md',VENDOR/'download-receipt.json']+[VENDOR/'datasets'/c['file'] for c in CASES.values()]
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def freeze(directory):
    directory.mkdir(parents=True,exist_ok=False);source=hashes();tasks=[]
    for case in CASES:
        d=Dataset(case)
        for seed in SEEDS:tasks.append({'case':case,'seed':seed,'initial_indices':np.random.default_rng(seed).choice(len(d.X),8,replace=False).tolist(),'budget':32})
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'source_hashes':source,'tasks':tasks,'methods':METHODS,'dataset_audit':audit(),'model':'muse-wonder-1.0','max_API_calls':36,'estimated_API_phase_cap_USD':12.,'API_rates_per_million':{'input':4,'cached':.2,'output':20},'runtime':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__},'scope':'Exploratory measured-data replay; not untouched discovery data, a hardware campaign or population proof. No new structure or prototype savings claim.'}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
    for name in source:
        target=directory/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    print('Frozen',directory,flush=True)

def load(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['source_hashes']!=hashes():raise ValueError('Source mismatch; preserve this run and create a new version')
    return manifest

def episode(task,method,directory,budget):
    target=directory/'runs'/task['case']/str(task['seed'])/method
    target.mkdir(parents=True,exist_ok=False);d=Dataset(task['case']);history=[d.observe(i) for i in task['initial_indices']];trace=[];plans=[];features=domain_features(d.name) if method=='gp_domain' else [];previous=None;diagnostics=[];t=time.monotonic()
    rng=np.random.default_rng(task['seed']+990000)
    while len(history)<task['budget']:
        if method=='meta_features' and len(history) in [8,16,24]:
            previous,event=propose(d,history,previous,diagnostics,target,budget);features=previous['features'];plans.append({'at_observations':len(history),'plan':previous,'actual_API_call':event['actual_API_call'],'accepted_feature_plan':event.get('accepted_feature_plan',False)})
        if method=='random':
            remaining=np.setdiff1d(np.arange(len(d.X)),[h['index'] for h in history]);index=int(rng.choice(remaining));prediction={'surrogate_fit_count':0}
        else:index,prediction=choose(d.X,history,d.info['direction'],features,forest=method=='rf_ei')
        if index in [h['index'] for h in history]:raise ValueError('Repeated experiment')
        observation=d.observe(index);history.append(observation);record={'query':len(history),'observation':observation,'prediction_before_reveal':prediction};trace.append(record)
        if 'predicted_mean' in prediction:diagnostics.append({'x':observation['x'],'observed_mean':observation['mean'],'predicted_mean':prediction['predicted_mean'],'predicted_sigma':prediction['predicted_sigma'],'absolute_standardized_error':abs(observation['mean']-prediction['predicted_mean'])/max(prediction['predicted_sigma'],1e-9)})
    result={'method':method,'case':d.name,'seed':task['seed'],'history':history,'trace':trace,'plans':plans,'metrics':d.score(history),'seconds':time.monotonic()-t,'work':{'surrogate_fits':sum(r['prediction_before_reveal']['surrogate_fit_count'] for r in trace),'GP_optimizer_restarts_per_fit':1 if method.startswith('gp') or method=='meta_features' else 0,'design_group_reveals':len(history),'actual_model_requests':sum(p['actual_API_call'] for p in plans)},'physical_experiments':0}
    (target/'result.json').write_text(json.dumps(result,indent=2));print('Completed',method,d.name,task['seed'],'regret',round(result['metrics']['post_initial_mean_regret'],4),flush=True);return result

def run(directory,mode):
    manifest=load(directory);methods=[m for m in METHODS if m!='meta_features'] if mode=='numerical' else ['meta_features'];budget=Budget();results=[]
    # Three workers; all BLAS pools capped at one. Timing is not a speed claim.
    with threadpool_limits(limits=1),ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(episode,t,m,directory,budget) for t in manifest['tasks'] for m in methods]
        for f in as_completed(futures):results.append(f.result())
    (directory/(mode+'-run-receipt.json')).write_text(json.dumps({'episodes':len(results),'API':budget.state(),'physical_experiments':0},indent=2))

def report(directory):
    manifest=load(directory);rows=[]
    for path in sorted((directory/'runs').glob('*/*/*/result.json')):
        result=json.loads(path.read_text());rows.append({k:result[k] for k in ['case','seed','method','metrics','work','seconds']})
    expected=len(manifest['tasks'])*len(METHODS)
    if len(rows)!=expected:raise ValueError(f'Incomplete study: {len(rows)} / {expected} episodes')
    methods={}
    for method in METHODS:
        selected=[r for r in rows if r['method']==method];methods[method]={'episodes':len(selected),'mean_post_initial_regret':float(np.mean([r['metrics']['post_initial_mean_regret'] for r in selected])),'median_post_initial_regret':float(np.median([r['metrics']['post_initial_mean_regret'] for r in selected])),'final_top5_hit_episodes':sum(r['metrics']['top5_first_query'] is not None for r in selected),'revealed_historical_rows':sum(r['metrics']['revealed_historical_rows'] for r in selected)}
    paired={}
    for control in ['gp_raw','rf_ei','gp_domain']:
        comparisons=[]
        for task in manifest['tasks']:
            case,seed=task['case'],task['seed'];a=next(r for r in rows if (r['case'],r['seed'],r['method'])==(case,seed,'meta_features'));b=next(r for r in rows if (r['case'],r['seed'],r['method'])==(case,seed,control));x=a['metrics']['post_initial_mean_regret'];y=b['metrics']['post_initial_mean_regret'];comparisons.append({'case':case,'seed':seed,'Meta_regret':x,'control_regret':y,'relative_reduction':float((y-x)/max(y,1e-12)),'Meta_better':bool(x<y-1e-10)})
        paired[control]={'cases':comparisons,'wins':sum(c['Meta_better'] for c in comparisons),'median_relative_regret_reduction':float(np.median([c['relative_reduction'] for c in comparisons]))}
    events=[json.loads(line) for path in (directory/'runs').glob('*/*/meta_features/api-events.jsonl') for line in path.read_text().splitlines()]
    transport_valid=bool(len(events)==36 and all(e['transport'].get('http_status')==200 and e['provider_response_id'] and e['transport'].get('usage') for e in events))
    gate=transport_valid and all(v['wins']>=8 and v['median_relative_regret_reduction']>=.15 for v in paired.values())
    summary={'scope':manifest['scope'],'methods':methods,'paired_controls':paired,'transport_valid_for_Meta_comparison':transport_valid,'exploratory_continuation_gate_passed':gate,'gate_note':'Predeclared directional research gate, not a statistical significance or general discovery claim. Three public datasets/four seeds; historical/pretraining contamination cannot be excluded. A transport-failed batch establishes no Meta reasoning-performance conclusion. Invalid feature plans after valid inference remain explicit system failures/fallbacks.','api':{'actual_calls':len(events),'HTTP_200':sum(e['transport'].get('http_status')==200 for e in events),'distinct_provider_response_ids':len({e['provider_response_id'] for e in events if e['provider_response_id']}),'accepted_feature_commands':sum(e['accepted_feature_plan'] for e in events),'estimated_USD':sum(e['estimated_USD'] for e in events),'billing_verified':False},'episodes':rows,'physical_experiments':0}
    (directory/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k not in ['episodes','paired_controls']},indent=2))

