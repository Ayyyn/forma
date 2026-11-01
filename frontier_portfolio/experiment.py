from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib,json,platform,shutil,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from frontier_scout.data import ROOT,VENDOR,CASES,Dataset
from frontier_scout.policy import choose,domain_features
from .engine import reset_meta_weight,update_weights,predictions,select
from .meta import Budget,propose,MODELS
METHODS=['random','gp_raw','rf_ei','gp_domain','portfolio','meta_wonder','meta_spark'];SEEDS=[106,137,193,239]

def hashes():
    paths=list((ROOT/'frontier_portfolio').glob('*.py'))+list((ROOT/'frontier_scout').glob('*.py'))+[ROOT/'docs/FRONTIER_PORTFOLIO_PROTOCOL.md',ROOT/'scripts/api_preflight.py',ROOT/'structure_lab/tool_protocol.py',VENDOR/'LICENSE',VENDOR/'README.md',VENDOR/'download-receipt.json']+[VENDOR/'datasets'/v['file'] for v in CASES.values()]
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

def freeze(directory):
    directory.mkdir(parents=True,exist_ok=False);source=hashes();tasks=[]
    for case in CASES:
        for seed in SEEDS:tasks.append({'case':case,'seed':seed,'initial_indices':np.random.default_rng(seed).choice(len(Dataset(case).X),8,replace=False).tolist(),'budget':32})
    m={'created_utc':datetime.now(timezone.utc).isoformat(),'source_hashes':source,'tasks':tasks,'methods':METHODS,'models':MODELS,'API_cap_USD':15.,'max_API_requests':72,'scope':'Exploratory algorithm revision on public experimental tables, fresh initial seeds. Not untouched datasets or independent population evidence; not a causal v2/v3 ablation because initial seeds differ.','physical_experiments':0,'python':platform.python_version()}
    (directory/'manifest.json').write_text(json.dumps(m,indent=2))
    for name in source:
        target=directory/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    print('Frozen',directory,flush=True)

def load(directory):
    m=json.loads((directory/'manifest.json').read_text())
    if m['source_hashes']!=hashes():raise ValueError('Source mismatch; preserve old study')
    return m

def episode(task,method,directory,budget):
    target=directory/'runs'/task['case']/str(task['seed'])/method;target.mkdir(parents=True,exist_ok=False);d=Dataset(task['case']);h=[d.observe(i) for i in task['initial_indices']];trace=[];plans=[];meta_trace=[];features=[];weights=np.array([1/3,1/3,1/3,0.]);enabled=False;previous=None;t=time.monotonic();fits=0;rng=np.random.default_rng(task['seed']+990000)
    while len(h)<task['budget']:
        if method in MODELS and len(h) in [8,16,24]:
            previous,event=propose(d,h,previous,meta_trace,target,budget,method);features=previous['features'];enabled=bool(features);weights=reset_meta_weight(weights,enabled);plans.append({'at_observations':len(h),'plan':previous,'actual_API_call':event['actual_API_call'],'accepted':event.get('accepted_feature_plan',False),'enabled':enabled})
        if method=='random':
            remaining=np.setdiff1d(np.arange(len(d.X)),[v['index'] for v in h]);index=int(rng.choice(remaining));record={}
        elif method in ['gp_raw','rf_ei','gp_domain']:
            index,record=choose(d.X,h,d.info['direction'],domain_features(d.name) if method=='gp_domain' else [],method=='rf_ei');fits+=1
        else:
            forecasts=predictions(d,h,features,enabled);index=select(forecasts,h,weights);fits+=len(forecasts);record={'expert_weights_before_reveal':weights.tolist(),'expert_predictions_before_reveal':[{'mean':float(d.info['direction']*(v[0][index]*v[3]+v[2])),'sigma':float(v[1][index]*v[3])} for v in forecasts]}
        if index in [v['index'] for v in h]:raise ValueError('Repeat reveal')
        observation=d.observe(index)
        if method=='portfolio' or method in MODELS:
            standardized=(d.info['direction']*observation['mean']-forecasts[0][2])/forecasts[0][3];means=[v[0][index] for v in forecasts];sigmas=[v[1][index] for v in forecasts]
            if not enabled:means.append(0.);sigmas.append(1.)
            weights,loss=update_weights(weights,means,sigmas,standardized,[True,True,True,enabled]);record.update(expert_weights_after_reveal=weights.tolist(),clipped_prequential_losses=loss.tolist());meta_trace.append({'x':observation['x'],'observed_mean':observation['mean'],**record})
        h.append(observation);trace.append({'query':len(h),'observation':observation,**record})
    result={'case':d.name,'seed':task['seed'],'method':method,'history':h,'trace':trace,'plans':plans,'metrics':d.score(h),'work':{'surrogate_fits':fits,'revealed_groups':len(h),'API_requests':sum(p['actual_API_call'] for p in plans)},'seconds':time.monotonic()-t,'physical_experiments':0}
    (target/'result.json').write_text(json.dumps(result,indent=2));print('Finished portfolio study',method,d.name,task['seed'],round(result['metrics']['post_initial_mean_regret'],4),flush=True)

def run(directory,mode):
    m=load(directory);methods=[v for v in METHODS if v not in MODELS] if mode=='numerical' else list(MODELS);budget=Budget(cap=15.,maximum=72)
    with threadpool_limits(1),ThreadPoolExecutor(max_workers=3) as pool:
        jobs=[pool.submit(episode,t,method,directory,budget) for t in m['tasks'] for method in methods]
        for job in as_completed(jobs):job.result()
    (directory/(mode+'-receipt.json')).write_text(json.dumps({'API':budget.state(),'episodes':len(m['tasks'])*len(methods),'physical_experiments':0},indent=2))

def report(directory):
    m=load(directory);rows=[json.loads(p.read_text()) for p in (directory/'runs').glob('*/*/*/result.json')]
    if len(rows)!=len(m['tasks'])*len(METHODS):raise ValueError('Incomplete episodes')
    stats={name:{'mean_regret':float(np.mean([r['metrics']['post_initial_mean_regret'] for r in rows if r['method']==name])),'top5_hit_episodes':sum(r['metrics']['top5_first_query'] is not None for r in rows if r['method']==name),'surrogate_fits':sum(r['work']['surrogate_fits'] for r in rows if r['method']==name)} for name in METHODS};controls=[v for v in METHODS if v not in MODELS];paired={}
    for method in MODELS:
        pair={}
        for control in controls:
            differences=[]
            for task in m['tasks']:
                a=next(r for r in rows if (r['case'],r['seed'],r['method'])==(task['case'],task['seed'],method));b=next(r for r in rows if (r['case'],r['seed'],r['method'])==(task['case'],task['seed'],control));differences.append({'case':task['case'],'seed':task['seed'],'Meta_regret':a['metrics']['post_initial_mean_regret'],'control_regret':b['metrics']['post_initial_mean_regret'],'Meta_better':a['metrics']['post_initial_mean_regret']<b['metrics']['post_initial_mean_regret']-1e-10})
            pair[control]={'wins':sum(v['Meta_better'] for v in differences),'paired':differences,'pooled_mean_relative_regret_reduction':float((stats[control]['mean_regret']-stats[method]['mean_regret'])/max(stats[control]['mean_regret'],1e-12))}
        events=[json.loads(line) for path in (directory/'runs').glob('*/*/'+method+'/api-events.jsonl') for line in path.read_text().splitlines()];valid=bool(len(events)==36 and all(e['transport'].get('http_status')==200 and e['provider_response_id'] and e['transport'].get('usage') for e in events));passed=valid and all(v['wins']>=8 and v['pooled_mean_relative_regret_reduction']>=.15 for v in pair.values())
        paired[method]={'transport_valid':valid,'continuation_gate_passed':passed,'comparisons':pair,'API':{'calls':len(events),'HTTP200':sum(e['transport'].get('http_status')==200 for e in events),'unique_provider_ids':len({e['provider_response_id'] for e in events if e['provider_response_id']}),'accepted_plans':sum(e['accepted_feature_plan'] for e in events),'estimated_USD':sum(e['estimated_USD'] for e in events),'billing_verified':False}}
    out={'scope':m['scope'],'methods':stats,'paired':paired,'all_cases':[{'case':r['case'],'seed':r['seed'],'method':r['method'],'metrics':r['metrics'],'work':r['work']} for r in rows],'physical_experiments':0}
    (directory/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps({'methods':stats,'Meta_results':{k:{a:b for a,b in v.items() if a!='comparisons'} for k,v in paired.items()}},indent=2))
