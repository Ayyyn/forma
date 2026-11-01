"""Replay candidates and summarize every development case, without significance claims."""
import csv
import hashlib
import json
from collections import Counter
import numpy as np
from .search import Laboratory,ranked
from .design import templates,geometry
from .oracle import oracle_solve


def replay(task,record):
    lab=Laboratory(task);max_error=0.;max_oracle_error=0.;oracle_calls=0
    for saved in record['candidates']:
        if saved['source']=='invalid_tool':actual=lab.charge_invalid(saved['error'])
        else:actual=lab.evaluate(saved['edge_ids'],saved['widths_mm'],saved['source'])
        for k in ['id','valid','feasible','attempt']:
            if actual[k]!=saved[k]:raise AssertionError(f'Replay mismatch: {k}')
        if actual['valid']:
            err=float(np.max(abs(np.array(actual['compliance_mm_per_N'])-saved['compliance_mm_per_N'])))
            max_error=max(max_error,err)
            for k in ['volume_mm3','violation','residual_inf']:
                if not np.isclose(actual[k],saved[k],rtol=1e-10,atol=1e-12):raise AssertionError('Metric changed: '+k)
            nodes,all_edges=geometry(task['length_mm'],task['height_mm'])
            independent=oracle_solve(nodes,[all_edges[i] for i in saved['edge_ids']],saved['widths_mm'],[0,1,2],7)
            oracle_error=float(abs(independent-np.array(saved['compliance_mm_per_N'])).max())
            max_oracle_error=max(max_oracle_error,oracle_error);oracle_calls+=1
            if oracle_error>1e-8*max(1.,float(abs(independent).max())):raise AssertionError('Independent candidate oracle disagreement')
    if len(lab.records)!=record['charged_search_slots'] or lab.physics_solves!=record['actual_frame_assemblies']:raise AssertionError('Budget ledger mismatch')
    if len(lab.records)>lab.budget:raise AssertionError('Overspent search budget')
    if (lab.best or {}).get('id')!=(record['best'] or {}).get('id'):raise AssertionError('Best candidate not shared ranking')
    check=lab.final_verify()
    if check['passed']!=record['certificate']['passed']:raise AssertionError('Final oracle mismatch')
    if max_error>1e-10:raise AssertionError('Compliance replay error')
    return {'maximum_replay_compliance_error':max_error,'candidates':len(lab.records),'oracle':check,
            'posthoc_independent_candidate_oracle_calls':oracle_calls,'maximum_candidate_oracle_error':max_oracle_error}


def report(directory):
    from .__main__ import load,save
    manifest=load(directory);records=[];rows=[];audits=[];missing=[]
    known={tuple(ids) for ids in templates().values()}
    for task in manifest['tasks']:
        for seed in manifest['seeds']:
            for method in manifest['methods']:
                path=directory/'runs'/f"{task['id']}-{seed}-{method}.json"
                if not path.exists():missing.append(str(path));continue
                r=json.loads(path.read_text(encoding='utf-8'));audits.append(replay(task,r));records.append(r)
                best=r['best'] or {};rows.append({'task':task['id'],'seed':seed,'method':method,
                   'verified_feasible':r['verified_feasible'],'volume_mm3':best.get('volume_mm3'),
                   'charged_slots':r['charged_search_slots'],'actual_frame_assemblies':r['actual_frame_assemblies'],
                   'first_feasible_slot':r['first_feasible_charged_index'],'first_feasible_frame_solve':r['first_feasible_frame_solve_index'],
                   'seconds':r['elapsed_seconds'],'model_calls':r['model']['actual_api_calls'],
                   'non_template_selected':bool(best.get('valid') and tuple(best['edge_ids']) not in known),
                   'independent_oracle_passed':r['certificate']['passed']})
    if missing:raise RuntimeError(f'Incomplete pilot: {len(missing)} missing cells; report will not select available successes')
    aggregate={}
    for method in manifest['methods']:
        rr=[r for r in rows if r['method']==method];feasible=[r for r in rr if r['verified_feasible']]
        aggregate[method]={'cases':len(rr),'verified_feasible':len(feasible),
            'mean_feasible_volume_mm3':float(np.mean([r['volume_mm3'] for r in feasible])) if feasible else None,
            'median_seconds':float(np.median([r['seconds'] for r in rr])),
            'total_charged_slots':sum(r['charged_slots'] for r in rr),'total_frame_assemblies':sum(r['actual_frame_assemblies'] for r in rr),
            'median_first_feasible_slot':float(np.median([r['first_feasible_slot'] for r in feasible])) if feasible else None,
            'non_template_selected':sum(r['non_template_selected'] for r in rr)}
    paired=[]
    for task in manifest['tasks']:
        for seed in manifest['seeds']:
            rr={r['method']:r for r in rows if r['task']==task['id'] and r['seed']==seed}
            b=rr['numerical'];a=rr['tool_agent'];s=rr['single_pass']
            paired.append({'task':task['id'],'seed':seed,
                'numerical_feasible':b['verified_feasible'],'single_pass_feasible':s['verified_feasible'],'agent_feasible':a['verified_feasible'],
                'agent_volume_reduction_vs_numerical_fraction':(b['volume_mm3']-a['volume_mm3'])/b['volume_mm3'] if b['verified_feasible'] and a['verified_feasible'] else None,
                'agent_volume_reduction_vs_single_pass_fraction':(s['volume_mm3']-a['volume_mm3'])/s['volume_mm3'] if s['verified_feasible'] and a['verified_feasible'] else None,
                'numerical_first_feasible_slot':b['first_feasible_slot'],'agent_first_feasible_slot':a['first_feasible_slot'],
                'numerical_volume':b['volume_mm3'],'single_pass_volume':s['volume_mm3'],'agent_volume':a['volume_mm3']})
    usage=Counter();finish=Counter();tool_counts=Counter();encodings=Counter();ids=[];api=0;images=0;transports=Counter()
    for r in records:
        api+=r['model']['actual_api_calls'];images+=r['model'].get('image_inputs_transmitted',0)
        for e in r['model']['events']:
            transports[str(e['transport'].get('http_status'))]+=1
            encodings[e.get('tool_encoding','native_or_unadapted')]+=1
            if e.get('response_id'):ids.append(e['response_id'])
            finish[str(e.get('finish_reason'))]+=1;u=e['transport'].get('usage') or {}
            usage.update(input_tokens=u.get('prompt_tokens',0),output_tokens=u.get('completion_tokens',0),
                cached_tokens=(u.get('prompt_tokens_details') or {}).get('cached_tokens',0),
                reasoning_tokens=(u.get('completion_tokens_details') or {}).get('reasoning_tokens',0))
            for t in e.get('tools',[]):tool_counts[t['name']]+=1
    if len(ids)!=len(set(ids)):raise AssertionError('Provider response IDs are not unique')
    estimate=((usage['input_tokens']-usage['cached_tokens'])*1.25+usage['cached_tokens']*.15+usage['output_tokens']*4.25)/1e6
    summary={'status':'exploratory development pilot; no held-out superiority claim','aggregate':aggregate,'paired':paired,
       'api':{'actual_calls':api,'distinct_response_ids':len(set(ids)),'http_statuses':dict(transports),
           'finish_reasons':dict(finish),'tool_calls':dict(tool_counts),'tool_encodings':dict(encodings),'image_inputs_transmitted':images,
           'usage':dict(usage),'estimated_reported_usage_usd':estimate,'actual_billing_unverified':True},
       'replay':{'passed':True,'cells':len(audits),'charged_candidates':sum(a['candidates'] for a in audits),
           'maximum_compliance_discrepancy':max(a['maximum_replay_compliance_error'] for a in audits),
           'maximum_independent_oracle_discrepancy':max(a['oracle'].get('maximum_compliance_discrepancy',0.) for a in audits)},
       'manifest_sha256':hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(),
       'physical_experiments':0,'physical_prototypes':0,'physical_prototypes_avoided':'not measured',
       'interpretation_limits':manifest['limitations']}
    summary['replay'].update(posthoc_independent_candidate_oracle_calls=sum(a['posthoc_independent_candidate_oracle_calls'] for a in audits),
                            maximum_candidate_oracle_error=max(a['maximum_candidate_oracle_error'] for a in audits),
                            posthoc_note='Additional offline audit work; never used to guide any search or added to online search budgets.')
    save(directory/'summary.json',summary)
    for name,items in [('cells.csv',rows),('paired.csv',paired)]:
        with (directory/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
    plot(directory,paired,aggregate)
    table='\n'.join(f"| {m} | {a['verified_feasible']}/{a['cases']} | {a['mean_feasible_volume_mm3']} | {a['median_first_feasible_slot']} | {a['median_seconds']:.3f} |" for m,a in aggregate.items())
    text=f'''# Cross-family non-folding structural design pilot

This is a development pilot on four known synthetic tasks and two seeds. It is not confirmatory held-out evidence, a medical-device design validation, or a world-first discovery claim.

| Policy | Verified feasible | Mean feasible volume proxy (mm^3) | Median first-feasible slot | Median seconds |
|---|---:|---:|---:|---:|
{table}

Means across different tasks should not decide a winner; inspect the paired per-task table for feasibility and volume. All methods have the same maximum 96 charged search slots, exact constraints, feature/clearance/linearity checks, analytic-gradient optimizer and final independent oracle. Cache hits are free/logged and optimizer internals are charged. A common final oracle solve is additional and separately counted. Early stopping retains unused allowance.

The numerical control screens eligible topology width extremes, sizes the best candidates with constrained SLSQP and mutates graph members. Single-pass Meta chooses a fixed optimizer portfolio with one request. Adaptive Meta can run that same optimizer, edit graphs, inspect computed sensitivities, and request geometry views. Raw records show which capabilities were actually used. This pilot has no ablation proving a separate effect of images or any particular tool.

Actual model calls: {api}; distinct saved response IDs: {len(set(ids))}. Estimated reported-usage cost: ${estimate:.3f}, using generic Baseten published rates ($1.25/M input, $0.15/M cached input, $4.25/M output); actual billing is unverified. All outcomes are retained; no transport retry or success replacement.

Every candidate replays; selected candidates have independent Hermite strain-energy compliance checks. Four synthetic task clusters and two seeds do not establish broad statistical superiority. The model is linear, in-plane, slender, rigid-jointed Euler-Bernoulli mechanics on a fixed 9-node/18-edge graph. The volume proxy sums beam volumes and double-counts ideal joint overlap. No nonlinear actuation, large motion, plasticity, loaded buckling, contact, fatigue or patient/clinical performance is validated.

Physical experiments: zero. Physical prototypes: zero. Prototypes avoided: **not measured**. Simulation-call differences cannot be relabeled as measured physical savings. A selected graph outside the conventional template list is only a new candidate within this grammar, not evidence of scientific novelty.

Reproduce offline: `python -m structure_lab verify`, `python -m unittest discover -s tests -p test_structure_lab.py`, and `python -m structure_lab report`. Raw cells are immutable under `runs/`; images are in `assets/`; protocol/source hashes are in `manifest.json`. A paid `run` skips saved cells. Source changes require a separately retained version.
'''
    (directory/'README.md').write_text(text,encoding='utf-8')
    print(json.dumps(summary,indent=2))


def plot(directory,paired,aggregate):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tasks=list(dict.fromkeys(p['task'] for p in paired));fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    x=np.arange(len(tasks));colors={'numerical':'#2a6954','single_pass':'#848582','tool_agent':'#bd693b'}
    for i,(name,key) in enumerate([('numerical','numerical_volume'),('single_pass','single_pass_volume'),('tool_agent','agent_volume')]):
        feasible_key={'numerical':'numerical_feasible','single_pass':'single_pass_feasible','tool_agent':'agent_feasible'}[name]
        vals=[]
        for task in tasks:
            good=[p[key] for p in paired if p['task']==task and p[feasible_key] and p[key] is not None]
            vals.append(float(np.mean(good)) if good else float('nan'))
        axes[0].bar(x+(i-1)*.24,vals,width=.24,color=colors[name],label=name)
    axes[0].set(xticks=x,xticklabels=tasks,ylabel='Selected beam-volume proxy (mm³)',title='Paired development tasks');axes[0].tick_params(axis='x',labelrotation=20,labelsize=8);axes[0].legend(fontsize=8)
    names=list(aggregate);axes[1].bar(names,[aggregate[n]['median_seconds'] for n in names],color=[colors[n] for n in names]);axes[1].set(ylabel='Median seconds per case',title='Search / model orchestration time');axes[1].tick_params(axis='x',labelrotation=20)
    fig.suptitle('Exploratory linear-frame design pilot • synthetic / no physical tests',fontsize=11)
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.savefig(directory/'comparison.png',dpi=160);fig.savefig(directory/'comparison.svg');plt.close(fig)
