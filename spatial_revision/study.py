"""Freeze, run and audit a small prospective parameter/revision study."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import time
import numpy as np
from .problem import generate_cases,development_task,compute
from .laboratory import Lab,numerical_control

ROOT=Path(__file__).resolve().parents[1]


def source_hashes():
    paths=[]
    for directory in ['spatial_revision','spatial_actuator']:paths+=list((ROOT/directory).glob('*.py'))
    paths +=[ROOT/'scripts/api_preflight.py',ROOT/'structure_lab/tool_protocol.py',ROOT/'research/spatial_external_check.py',ROOT/'docs/SPATIAL_REVISION_PROTOCOL.md']
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def freeze(directory):
    from spatial_actuator.verification import verify
    if not verify()['passed']:raise ValueError('Mechanics gate failed')
    external=json.loads((ROOT/'research/spatial-opensees-check.json').read_text())
    if not external['passed']:raise ValueError('External solver gate failed')
    directory.mkdir(parents=True,exist_ok=False)
    original=json.loads((ROOT/'artifacts/spatial-actuator-step1-v2/numerical.json').read_text())['state']['best_evaluated']
    starter={k:original[k] for k in ['edge_ids','radii_mm']}
    seed=secrets.randbits(63);hashes=source_hashes()
    manifest={'created_at_utc':datetime.now(timezone.utc).isoformat(),'status':'prospective generated revision screen; one model trajectory per instance',
              'case_generator_seed':seed,'cases':generate_cases(seed),'methods':['numerical','muse'],'algorithm_seed':101,
              'starter':starter,'previous_task':development_task(),'candidate_budget':256,'source_hashes':hashes,
              'model':'muse-wonder-1.0','max_api_requests_per_case':4,'maximum_output_tokens_per_request':6144,
              'expected_cells':16,'maximum_total_api_requests':32,
              'predeclared_gate':{'completion':'Muse verified-feasible case count must be at least numerical count',
                'quality_route':'Median paired feasible volume reduction >=10% and case-bootstrap 95% lower bound >0, with >=6 jointly feasible cases',
                'query_route':'Median first-feasible solve reduction >=25% and case-bootstrap 95% lower bound >0; at least 6 initially infeasible, jointly feasible cases and no >5% median final-volume worsening',
                'success':'Completion condition AND either quality or query route; a screening signal only, not confirmatory proof'},
              'external_gate_file_sha256':hashlib.sha256((ROOT/'research/spatial-opensees-check.json').read_bytes()).hexdigest(),
              'physical_experiments':0,'model_training':False,'remote_seed_guarantee':False}
    with (directory/'manifest.json').open('x',encoding='utf-8') as stream:json.dump(manifest,stream,indent=2)
    for name in hashes:
        destination=directory/'source'/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,destination)
    print(json.dumps({'directory':str(directory),'cases':len(manifest['cases']),'cells':16,'case_labels_evaluated_before_freeze':False,'max_api_requests':32}))


def load(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['source_hashes']!=source_hashes():raise ValueError('Source drift; use frozen snapshot or a fresh study version')
    return manifest


def run_cell(directory,manifest,case,method):
    target=directory/'runs'/case['id']/method
    if (target/'result.json').exists():return {'case':case['id'],'method':method,'skipped':True}
    if target.exists() and any(target.iterdir()):raise ValueError('Partial run preserved; no silent paid retry: '+str(target))
    target.mkdir(parents=True,exist_ok=True);lab=Lab(case,manifest['candidate_budget']);started=time.monotonic();model=None;error=None
    try:
        if method=='numerical':numerical_control(lab,manifest['starter'],manifest['algorithm_seed'])
        else:
            from .agent import run
            model=run(lab,manifest['starter'],manifest['previous_task'],target,manifest['algorithm_seed'])
    except Exception as exception:error=type(exception).__name__+': '+str(exception)
    seconds=time.monotonic()-started;check=lab.verify()
    result={'case_id':case['id'],'method':method,'elapsed_seconds':seconds,'records':lab.records,'state':lab.state(),
            'independent_final_check':check,'model':model,'error':error,'seed_label':manifest['algorithm_seed']}
    with (target/'result.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(f"Completed {case['id']} {method}: feasible={bool(lab.best and lab.best['feasible'] and check['passed'])}, candidates={len(lab.records)}, seconds={seconds:.1f}",flush=True)
    return {'case':case['id'],'method':method,'error':error}


def run(directory,workers=4):
    manifest=load(directory)
    # Loading keys happens only for real Muse runs; no model-dependent feasibility
    # selection or cross-case memory is shared between independent controllers.
    from scripts.api_preflight import load_env
    load_env()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(run_cell,directory,manifest,case,method) for case in manifest['cases'] for method in manifest['methods']]
        for future in as_completed(futures):future.result()


def confidence(values):
    if not values:return {'median':None,'ci95':[None,None],'n':0}
    values=np.array(values,float);rng=np.random.default_rng(10292026)
    med=np.median(values[rng.integers(0,len(values),(10000,len(values)))],axis=1)
    return {'median':float(np.median(values)),'ci95':[float(x) for x in np.quantile(med,[.025,.975])],'n':len(values)}


def report(directory):
    from spatial_actuator.oracle import solve as oracle
    from research.spatial_external_check import compare as external_compare
    manifest=load(directory);results=[];audits=[];table=[]
    for case in manifest['cases']:
        paired={}
        for method in manifest['methods']:
            folder=directory/'runs'/case['id']/method
            if not (folder/'result.json').exists():raise ValueError('Incomplete matrix; do not summarize selected cells')
            saved=json.loads((folder/'result.json').read_text());paired[method]=saved
            lab=Lab(case,manifest['candidate_budget']);maximum=0.;count=0
            for record in saved['records']:
                if not record.get('valid'):continue
                replay=compute(case,record['edge_ids'],record['radii_mm'])
                if record['feasible']!=replay['feasible']:raise ValueError('Replay feasibility changed')
                if any(abs(float(v)-float(replay['metrics'][key]))>1e-9 for key,v in record['metrics'].items() if v is not None):raise ValueError('Saved metric mismatch')
                truth=oracle(replay['nodes'],replay['edges'],record['radii_mm'],[0,1,2,3],replay['loads'],case['E_N_mm2'],case['nu'],replay['springs'])
                err=float(abs(replay['solved']['u']-truth).max());maximum=max(maximum,err);count+=1
                if err>1e-8*max(1.,abs(truth).max()):raise ValueError('Independent candidate oracle failed')
            best=saved['state']['best_evaluated'];external=None
            if best:
                replay=compute(case,best['edge_ids'],best['radii_mm'])
                external=external_compare(replay['nodes'],replay['edges'],best['radii_mm'],[0,1,2,3],replay['loads'],case['E_N_mm2'],case['nu'],replay['springs'])
                if not external['passed']:raise ValueError('Selected candidate external verification failed')
            audits.append({'case_id':case['id'],'method':method,'valid_candidates':count,'max_absolute_u_error':maximum,
                           'extra_candidate_audit_assemblies':2*count,'selected_external_check':external,
                           'selected_external_extra_production_assemblies':1 if best else 0,'selected_external_solves':1 if best else 0})
            feasible=bool(best and best['feasible'] and saved['independent_final_check']['passed'] and external and external['passed'])
            first=next((i+1 for i,r in enumerate(saved['records']) if r.get('feasible')),None)
            results.append({'case_id':case['id'],'revision_kind':case['revision_kind'],'method':method,'feasible':feasible,
                            'volume':best['metrics']['volume_proxy_mm3'] if best else None,'charged_candidates':len(saved['records']),
                            'actual_assemblies':saved['state']['actual_assemblies'],'first_feasible_candidate':first,
                            'elapsed_seconds':saved['elapsed_seconds'],'initial_feasible':bool(saved['records'] and saved['records'][0].get('feasible')),'error':saved['error']})
    paired_changes=[];query_changes=[]
    for case in manifest['cases']:
        n=next(r for r in results if r['case_id']==case['id'] and r['method']=='numerical');m=next(r for r in results if r['case_id']==case['id'] and r['method']=='muse')
        if n['feasible'] and m['feasible']:
            paired_changes.append(1-m['volume']/n['volume'])
            if not n['initial_feasible']:query_changes.append(1-m['first_feasible_candidate']/n['first_feasible_candidate'])
    quality=confidence(paired_changes);queries=confidence(query_changes);totals={}
    for method in manifest['methods']:
        cells=[r for r in results if r['method']==method]
        totals[method]={'verified_feasible':sum(r['feasible'] for r in cells),'case_count':len(cells),
                        'median_seconds':float(np.median([r['elapsed_seconds'] for r in cells])),
                        'charged_candidates':sum(r['charged_candidates'] for r in cells),'actual_assemblies':sum(r['actual_assemblies'] for r in cells),
                        'median_first_feasible_candidate':float(np.median([r['first_feasible_candidate'] for r in cells if r['feasible']])) if any(r['feasible'] for r in cells) else None}
    completion=totals['muse']['verified_feasible']>=totals['numerical']['verified_feasible']
    quality_gate=quality['n']>=6 and quality['median']>=.10 and quality['ci95'][0]>0
    query_gate=queries['n']>=6 and queries['median']>=.25 and queries['ci95'][0]>0 and quality['median']>=-.05
    events=[]
    for case in manifest['cases']:
        journal=directory/'runs'/case['id']/'muse'/'events.jsonl'
        if journal.exists():events.extend(json.loads(line) for line in journal.read_text().splitlines())
    usages=[e['transport'].get('usage') or {} for e in events];inp=sum(u.get('prompt_tokens',0) for u in usages);out=sum(u.get('completion_tokens',0) for u in usages);cached=sum((u.get('prompt_tokens_details') or {}).get('cached_tokens',0) for u in usages)
    summary={'results':results,'totals':totals,'paired_feasible_volume_reduction':quality,'initially_failed_query_reduction':queries,
             'predeclared_gate_passed':bool(completion and (quality_gate or query_gate)),
             'gate_components':{'completion':completion,'quality':quality_gate,'query':query_gate},
             'api':{'actual_requests':len(events),'http_200':sum(e['transport'].get('http_status')==200 for e in events),
                    'distinct_provider_ids':len({e['response_id'] for e in events if e.get('response_id')}),'input_tokens':inp,'cached_input_tokens':cached,'output_tokens':out,
                    'estimated_USD':(inp-cached)*4e-6+cached*.2e-6+out*20e-6,'billing_verified':False,
                    'image_inputs_including_history_repeats':sum(e['image_inputs_transmitted'] for e in events)},
             'audits':audits,'physical_experiments':0,'physical_prototypes_avoided_measured':False,
             'interpretation':'Eight generated instances, one stochastic model trajectory each. A prospective screening study, not confirmatory evidence or proof of infeasibility when searches fail.'}
    (directory/'summary.json').write_text(json.dumps(summary,indent=2));write_report(directory,manifest,summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['results','audits']},indent=2))
    return summary


def write_report(directory,manifest,summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    lines=['# Prospective spatial revision screen','',summary['interpretation'],'',
           '| Revision | Numerical feasible | Muse feasible | Numerical volume | Muse volume | Numerical/Muse candidates |',
           '|---|---|---|---:|---:|---:|']
    for case in manifest['cases']:
        n=next(r for r in summary['results'] if r['case_id']==case['id'] and r['method']=='numerical');m=next(r for r in summary['results'] if r['case_id']==case['id'] and r['method']=='muse')
        nv=f"{n['volume']:.3f}" if n['feasible'] else 'failed';mv=f"{m['volume']:.3f}" if m['feasible'] else 'failed'
        lines.append(f"| {case['revision_kind']} | {n['feasible']} | {m['feasible']} | {nv} | {mv} | {n['charged_candidates']}/{m['charged_candidates']} |")
    lines+=['',f"Predeclared screening gate passed: **{summary['predeclared_gate_passed']}**.",
            '',f"Totals: {summary['totals']}",'',f"Paired feasible volume reduction (positive favors Muse): {summary['paired_feasible_volume_reduction']}",'',f"Initially-failed query reduction: {summary['initially_failed_query_reduction']}",'',f"Actual API usage: {summary['api']}",'',
            'No feasibility filtering or post-score repairs were applied to the cases. Both methods share the original design, current exact task, graph language, optimizer and 256-candidate cap. Numerical control repairs a warm start, screens up to 80 members of a much wider geometric catalogue, sizes promising graphs and tries member removal. Ordinary optimizer internal samples consume the allowance. Different policies may leave allowance unused. Model inferences and image context have additional latency/cost, recorded separately.',
            '', 'Every valid candidate was reproduced and checked against independent strain-energy assembly offline; each selected candidate was also compared against OpenSees. Audit solves were not search feedback. These checks establish agreement on the same ideal linear model, not a manufactured part. Task changes are enforced by a structured contract; language-only requirements interpretation was not tested.',
            '', 'Failure means no accepted design found within this run, not proof no feasible design exists. Comparisons of volume exclude neither failures from completion counts nor initial failures from the result table. Conditional volume metrics apply only to jointly feasible cases. Bootstrap intervals are descriptive for eight generated instances and omit repeated-model and broader application uncertainty.',
            '', 'No active power-source model, large motion, contact, calibrated material/joint behavior, fatigue, physical prototype, avoided-prototype measurement, clinical claim or new mechanical principle. OpenSees is an optional local research validation dependency, installed separately and not redistributed or exposed as a service.',
            '', 'Frozen source/cases: manifest.json and source/. Raw candidates, received public model outputs and tool journals: runs/. Independent checks and resource/cost summary: summary.json. No private reasoning text or keys are saved.']
    (directory/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    fig,axes=plt.subplots(1,2,figsize=(11,4));xx=np.arange(8);width=.36
    for j,(method,color) in enumerate([('numerical','#385d85'),('muse','#c26842')]):
        rows=[next(r for r in summary['results'] if r['case_id']==case['id'] and r['method']==method) for case in manifest['cases']]
        axes[0].bar(xx+(j-.5)*width,[r['volume'] if r['feasible'] else 0 for r in rows],width,label=method,color=color)
        axes[1].bar(xx+(j-.5)*width,[r['actual_assemblies'] for r in rows],width,label=method,color=color)
        for i,r in enumerate(rows):
            if not r['feasible']:axes[0].text(i+(j-.5)*width,1,'FAIL',ha='center',rotation=90,fontsize=7,color=color)
    for ax in axes:ax.set_xticks(xx,[c['revision_kind'] for c in manifest['cases']],rotation=40,ha='right',fontsize=8);ax.legend();ax.grid(axis='y',alpha=.15)
    axes[0].set_ylabel('Verified feasible volume proxy (mm³)');axes[1].set_ylabel('Actual online frame assemblies')
    fig.suptitle('Prospectively generated revisions: all cases retained; failed designs have no quality bar',fontsize=11);fig.tight_layout();fig.savefig(directory/'comparison.png',dpi=160);fig.savefig(directory/'comparison.svg');plt.close(fig)
