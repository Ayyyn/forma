"""Verify every saved ledger and generate the prespecified benchmark report and plot."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from continuum.benchmark import Ledger, rank
from continuum.geometry import Requirements


def cost_and_usage(run,rates):
    totals={'calls':0,'prompt_tokens':0,'cached_prompt_tokens':0,'completion_tokens':0,'reasoning_tokens':0,'reasoning_requests':0,'estimated_usd':0.,'missing_usage':0}
    for event in run['trace']:
        if 'transport' not in event:continue
        totals['calls']+=1
        usage=event['transport'].get('usage')
        if usage is None:totals['missing_usage']+=1;continue
        prompt=usage.get('prompt_tokens',0);output=usage.get('completion_tokens',0)
        cached=usage.get('prompt_tokens_details',{}).get('cached_tokens',0)
        totals['prompt_tokens']+=prompt;totals['cached_prompt_tokens']+=cached;totals['completion_tokens']+=output
        thinking=usage.get('completion_tokens_details',{}).get('reasoning_tokens',0)
        totals['reasoning_tokens']+=thinking;totals['reasoning_requests']+=int(thinking>0)
        totals['estimated_usd']+=((prompt-cached)*rates['input_per_million_usd']+cached*rates['cached_input_per_million_usd']+output*rates['output_per_million_usd'])/1e6
    return totals


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--version',type=int,default=5);args=parser.parse_args()
    root=Path('benchmarks');manifest_path=root/f'protocol-v{args.version}.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'));manifest_hash=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    runs=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((root/f'runs-v{args.version}').glob('*.json'))]
    expected={(t['id'],seed,m) for t in manifest['tasks'] for seed in manifest['seeds'] for m in manifest['methods']}
    observed={(r['task_id'],r['seed'],r['method']) for r in runs}
    assert len(runs)==len(expected) and expected==observed,'Missing or duplicate benchmark cells'
    by_key={(r['task_id'],r['seed'],r['method']):r for r in runs}
    oracle_count=0;invalid_count=0;max_delta=0.;replayed=0
    for run in runs:
        assert 'harness_error' not in run,run
        assert run['manifest_sha256']==manifest_hash
        assert 0<run['attempts_used']<=manifest['budget'] and run['attempts_used']==len(run['ledger'])
        assert run['ledger'][0]['proposal']==manifest['shared_initial_candidate']
        replay=Ledger(Requirements(**run['requirements']),run['objective'],run['budget'])
        for entry in run['ledger']:
            actual=replay.evaluate(entry['proposal'],entry['origin']);replayed+=1
            assert actual['valid']==entry['valid'] and actual['duplicate']==entry['duplicate']
            if actual['valid']:
                assert actual['result']==entry['result'],'Saved metrics do not reproduce'
                assert actual['independent_audit']['passed'] and entry['independent_audit']['passed']
                max_delta=max(max_delta,actual['independent_audit']['max_extent_delta_mm']);oracle_count+=1
            else:invalid_count+=1
        assert replay.best()==run['best']
        assert run['success']==bool(run['best'] and run['best']['feasible'])
        for event in run['trace']:
            if 'transport' in event and event.get('response_model') is not None:assert event['response_model']==manifest['model']
    feasible_ids=[t['id'] for t in manifest['tasks'] if t['expected_feasible']]
    impossible_ids=[t['id'] for t in manifest['tasks'] if not t['expected_feasible']]
    methods={}
    for method in manifest['methods']:
        selected=[r for r in runs if r['method']==method]
        feasible=[r for r in selected if r['task_id'] in feasible_ids]
        usage=[cost_and_usage(r,manifest['cost_estimate_rates']) for r in selected]
        methods[method]={
            'feasible_instances':len(feasible),'feasible_attained':sum(r['success'] for r in feasible),
            'feasibility_rate':sum(r['success'] for r in feasible)/len(feasible),
            'runs':len(selected),'completed':sum(r['completed'] for r in selected),'attempts_total':sum(r['attempts_used'] for r in selected),
            'attempts_min':min(r['attempts_used'] for r in selected),'attempts_max':max(r['attempts_used'] for r in selected),
            'valid_proposals':sum(r['valid_proposals'] for r in selected),'unique_proposals':sum(r['unique_valid_proposals'] for r in selected),
            'duplicate_attempts':sum(r['duplicate_attempts'] for r in selected),
            'median_runtime_seconds':statistics.median(r['latency_ms']/1000 for r in selected),
            'false_feasible_on_impossible':sum(r['success'] for r in selected if r['task_id'] in impossible_ids),
            **{key:sum(u[key] for u in usage) for key in usage[0]}}
    paired={}
    for other in ['deterministic','single_pass']:
        counts=Counter();quality=Counter();primary_quality=Counter();deltas=[];task_differences=[]
        for task_id in feasible_ids:
            differences=[]
            for seed in manifest['seeds']:
                a,b=by_key[task_id,seed,'agent'],by_key[task_id,seed,other]
                differences.append(int(a['success'])-int(b['success']))
                counts['agent_only_feasible' if a['success'] and not b['success'] else 'other_only_feasible' if b['success'] and not a['success'] else 'both_feasible' if a['success'] else 'neither_feasible']+=1
                if a['success'] and b['success']:
                    ka,kb=rank(a['best'],a['objective']),rank(b['best'],b['objective'])
                    quality['agent_better' if ka<kb else 'other_better' if kb<ka else 'tie']+=1
                    metric='crease_segments' if a['objective']=='creases' else 'material_area_mm2'
                    av,bv=a['best']['metrics'][metric],b['best']['metrics'][metric]
                    primary_quality['agent_better' if av<bv else 'other_better' if bv<av else 'tie']+=1
                    deltas.append((b['best']['metrics'][metric]-a['best']['metrics'][metric])/b['best']['metrics'][metric])
            task_differences.append(sum(differences)/len(differences))
        rng=np.random.default_rng(20261027)
        bootstrap=np.mean(rng.choice(task_differences,size=(10000,len(task_differences)),replace=True),axis=1)
        paired['agent_vs_'+other]={'feasibility_pairs':dict(counts),'quality_when_both_feasible':dict(quality),
            'primary_metric_only_when_both_feasible':dict(primary_quality),
            'feasibility_rate_difference':float(np.mean(task_differences)),
            'task_cluster_bootstrap_95_interval':np.percentile(bootstrap,[2.5,97.5]).tolist(),
            'conditional_mean_primary_objective_improvement_fraction':statistics.mean(deltas) if deltas else None,
            'uncertainty_limit':'Only five feasible task clusters; interval is descriptive and unreliable for broad generalization.'}
    per_task=[]
    for task in manifest['tasks']:
        row={'task_id':task['id'],'expected_feasible':task['expected_feasible'],'objective':task['objective']}
        for method in manifest['methods']:
            chosen=[by_key[task['id'],s,method] for s in manifest['seeds']]
            row[method]={'successes':sum(r['success'] for r in chosen),'per_seed':[{
                'seed':r['seed'],'success':r['success'],'attempts':r['attempts_used'],
                'primary':r['best']['metrics']['crease_segments' if task['objective']=='creases' else 'material_area_mm2'] if r['success'] else None} for r in chosen]}
        per_task.append(row)
    common_complete=[(task_id,seed) for task_id in feasible_ids for seed in manifest['seeds']
                     if all(by_key[task_id,seed,m]['attempts_used']==manifest['budget'] for m in manifest['methods'])]
    sensitivity={'label':'Post-hoc full-budget sensitivity check, not the primary analysis; incomplete runs remain in primary results.',
                 'matched_feasible_instances':len(common_complete),'solved':{m:sum(by_key[t,s,m]['success'] for t,s in common_complete) for m in manifest['methods']}}
    replay_report={'status':'passed','cells':len(runs),'attempts_replayed':replayed,'valid_oracle_agreements':oracle_count,
                   'invalid_attempts_replayed':invalid_count,'max_oracle_extent_delta_mm':max_delta,'budget_overspends':0,
                   'saved_best_matches_recomputed_best':True,'manifest_sha256':manifest_hash}
    impossible_predictions={}
    for method in ('single_pass','agent'):
        predictions=[]
        for run in runs:
            if run['method']==method and run['task_id'] in impossible_ids:
                flags=[e['expected_feasible'] for e in run['trace'] if 'expected_feasible' in e]
                predictions.append(flags[-1] if flags else None)
        impossible_predictions[method]={'claimed_feasible':predictions.count(True),'claimed_infeasible':predictions.count(False),'unknown':predictions.count(None)}
    summary={'protocol_version':args.version,'manifest_sha256':manifest_hash,'methods':methods,'paired':paired,'per_task':per_task,'replay':replay_report,'full_budget_sensitivity':sensitivity,
             'model_predictions_on_impossible':impossible_predictions,
             'incomplete_runs':[{'task_id':r['task_id'],'seed':r['seed'],'method':r['method'],'attempts_used':r['attempts_used'],
                 'errors':[e.get('error') for e in r['trace'] if e.get('error')]} for r in runs if not r['completed']]}
    (root/f'summary-v{args.version}.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    with (root/f'cells-v{args.version}.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.writer(handle);writer.writerow(['task','seed','method','success','completed','attempts','valid','unique','best_creases','best_area_mm2','latency_ms','estimated_usd'])
        for r in runs:
            m=r['best']['metrics'] if r['success'] else {}
            writer.writerow([r['task_id'],r['seed'],r['method'],r['success'],r['completed'],r['attempts_used'],r['valid_proposals'],r['unique_valid_proposals'],m.get('crease_segments'),m.get('material_area_mm2'),r['latency_ms'],cost_and_usage(r,manifest['cost_estimate_rates'])['estimated_usd']])
    make_plot(summary,root/f'comparison-v{args.version}.png')
    make_report(summary,manifest,root/f'RESULTS-v{args.version}.md')
    print(json.dumps({'methods':methods,'paired':paired,'replay':replay_report,'full_budget_sensitivity':sensitivity},indent=2))


def make_plot(summary,path):
    labels=['Deterministic\nadaptive search','Single-pass\nMeta planner','Feedback\nMeta agent']
    colors=['#607254','#c0a780','#8197a1']
    methods=list(summary['methods'])
    fig,(ax,heat)=plt.subplots(1,2,figsize=(11,4.8),gridspec_kw={'width_ratios':[1,1.4]},layout='constrained')
    fig.set_facecolor('#faf9f3');ax.set_facecolor('#faf9f3');heat.set_facecolor('#faf9f3')
    values=[summary['methods'][m]['feasible_attained'] for m in methods]
    bars=ax.bar(labels,values,color=colors,width=.62)
    ax.set_ylim(0,16.5);ax.set_ylabel('Feasible instances solved / 15');ax.set_yticks([0,3,6,9,12,15]);ax.spines[['top','right']].set_visible(False)
    for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value+.25,f'{value}/15',ha='center',fontweight='bold')
    data=np.array([[row[m]['successes'] for m in methods] for row in summary['per_task']])
    heat.imshow(data,vmin=0,vmax=3,cmap='YlGn',aspect='auto')
    heat.set_xticks(range(3),['Deterministic','Single pass','Agent']);heat.set_yticks(range(len(data)),[r['task_id'].replace('_',' ') for r in summary['per_task']])
    for i in range(len(data)):
        for j in range(3):heat.text(j,i,f'{data[i,j]}/3',ha='center',va='center',color='#f8faee' if data[i,j]>=3 else '#253526')
    heat.set_title('Feasibility by task (impossible task expects 0/3)',fontsize=10,pad=12)
    fig.suptitle('Equal-budget panel search: 64 candidate attempts per run',fontsize=14,fontweight='bold')
    fig.savefig(path,dpi=180,facecolor=fig.get_facecolor());plt.close(fig)


def make_report(summary,manifest,path):
    m=summary['methods'];version=summary['protocol_version']
    lines=[f'# Equal-budget benchmark results — protocol v{version}',
        '',f"Frozen manifest SHA-256: `{summary['manifest_sha256']}`.",'',
        'This is a small, real API benchmark of search planning inside an ideal Miura/accordion domain. It is not a test of physical fabrication or unrestricted invention.',
        '', '| Method | Feasible instances solved | Completed runs | Evaluation attempts/run | Median runtime | Model cost estimate |',
        '|---|---:|---:|---:|---:|---:|']
    for method,label in [('deterministic','Deterministic adaptive search'),('single_pass','Single-pass Meta planner'),('agent','Feedback Meta agent')]:
        v=m[method];lines.append(f"| {label} | {v['feasible_attained']}/15 | {v['completed']}/18 | {v['attempts_min']}–{v['attempts_max']} | {v['median_runtime_seconds']:.3f} s | ${v['estimated_usd']:.4f} |")
    lines+=['','The denominators exclude the three repeated impossible-task instances from feasibility attainment, but include them in completion, runtime and cost totals. Cost uses reported token usage and the public Baseten generic Muse Spark Open rates; actual hackathon-slug charges and credit balances are unverified. Numerical baseline infrastructure cost is not monetized.',
        '', '| Task | Deterministic | Single pass | Agent |','|---|---:|---:|---:|']
    for row in summary['per_task']:lines.append('| '+row['task_id']+' | '+' | '.join(str(row[method]['successes'])+'/3' for method in manifest['methods'])+' |')
    if version==5:
        lines+=['','## Interpretation','',
                'Reasoning-enabled Meta search planning improved feasibility attainment over this numerical baseline on these tasks. The extra feedback loop did not improve attainment over the simpler one-pass planner. Single pass won 12/15 lexicographic objective comparisons against the agent; on the primary metric alone it won 8, lost 1 and tied 6. These are paired observations in this narrow benchmark, not proof of broad model superiority.',
                '', 'For the current parameter-search role, the evidence favors testing one-pass planning plus deterministic verification as the default. A feedback agent needs a more clearly justified recovery or hypothesis-generation responsibility before adding its complexity. A larger, independent task set and stronger alternative numerical optimizers remain necessary.']
    sensitivity=summary['full_budget_sensitivity']
    lines+=['',f"Full-budget sensitivity check: in the {sensitivity['matched_feasible_instances']} matched feasible instances where all methods actually spent all 64 attempts, solved counts are {json.dumps(sensitivity['solved'])}. This secondary, post-hoc subset separates unused-budget effects; it does not replace the primary analysis that retains every failure.",
            '',f"Reported reasoning-token telemetry: single pass {m['single_pass']['reasoning_tokens']} tokens across {m['single_pass']['reasoning_requests']}/{m['single_pass']['calls']} requests; agent {m['agent']['reasoning_tokens']} tokens across {m['agent']['reasoning_requests']}/{m['agent']['calls']} requests. Raw private reasoning is not retained."]
    lines+=['','The impossible task requires deployed width 220 mm from a flat blank no wider than 190 mm. Its zero success count is the correct evaluator outcome, not a search failure. A model predicting feasibility does not override this certificate.',
        '', 'Final model feasibility forecasts on that impossible task: '+json.dumps(summary['model_predictions_on_impossible'])+'. These are forecasts, not accepted outcomes. The independently checked evaluator accepted no impossible design.',
        '', '## Paired comparisons','']
    for name,value in summary['paired'].items():
        lines+=[f"- {name}: {json.dumps(value['feasibility_pairs'])}; objective comparison when both feasible: {json.dumps(value['quality_when_both_feasible'])}.",
                f"  Primary metric alone, before material/packed-area tie-breaks: {json.dumps(value['primary_metric_only_when_both_feasible'])}.",
                f"  Feasibility-rate difference {100*value['feasibility_rate_difference']:.1f} percentage points; task-cluster bootstrap interval [{100*value['task_cluster_bootstrap_95_interval'][0]:.1f}, {100*value['task_cluster_bootstrap_95_interval'][1]:.1f}]. Only five feasible task clusters; this is descriptive uncertainty, not a general capability claim."]
    lines+=['','An interval of [0, 0] for two methods that succeeded on every observed instance is a degenerate resampling result. It does not demonstrate equivalence of their unknown success probabilities or predict success on unseen tasks.']
    replay=summary['replay']
    lines+=['','## Verification and limits','',
        f"All {replay['cells']} saved ledgers were replayed: {replay['attempts_replayed']} attempts, {replay['valid_oracle_agreements']} valid proposals independently checked, {replay['budget_overspends']} budget overspends. Every saved best candidate matched recomputation. Maximum independent extent discrepancy: {replay['max_oracle_extent_delta_mm']:.3g} mm.",
        '', 'The separate geometry audit compares 70-digit published equations, a nonlinear geometric constraint solve, polygon-union overlap, and six deliberate result corruptions. See `audit-geometry.json`. It supports mathematical correctness of the implemented ideal model; it cannot establish paper thickness clearance, strength, stability or experimental correspondence.',
        '', 'All methods share the inverse dimension construction and numerical sampler. The single pass chooses one region without feedback; the agent gets three planning turns. Both use the same Meta model, declared knowledge and maximum total output-token allowance. Evaluator-best selection is used for every method, so model claims cannot count as success. Duplicate and invalid proposals consume attempts. Prior demo solutions and task-construction witnesses are not supplied to any method.',
        '', 'The v2 pilot exposed an accordion tool-schema mismatch, corrected in v3 with a full rerun. All v3 forced-tool responses reported zero reasoning tokens. Unscored transport probes found reasoning present with automatic tool choice and established a sufficient output allowance. V4 therefore uses automatic tool choice, requests medium effort, and gives both model methods the same 49,152-token total output ceiling (one single-pass call, or three agent calls capped at 16,384 each). Optional explanation text no longer invalidates otherwise valid search parameters merely for exceeding a small character limit. All earlier versions remain separate; no cells are cherry-picked or pooled. The task definitions, sampler, evaluator, objectives and numerical baseline remain the same. Hosted-model variation and bundled configuration changes prevent attributing version-to-version performance differences to reasoning alone.',
        '', 'V4 was interrupted by 32 DNS failures and three timeouts; its capability comparison is inconclusive. V5 is a complete new retry of the same reasoning configuration with a 180-second per-request timeout and two concurrent workers. No v4 cells are substituted into v5. Final-batch cost estimates do not include diagnostic requests or unreported charges on timed-out requests.',
        '', 'These tasks and search controls were designed by the project developer in a domain already explored during prototyping. Seeds change sampler outcomes but do not create independent task families; repeated model responses are not guaranteed reproducible. The numerical baseline is constructive, family-aware and adaptive, but is not an exhaustive global optimizer. Results establish only how these particular policies performed under this protocol.',
        '', 'The brief tests deployed bounding extent, not useful load-bearing surface or enclosed capacity. No model narrative is accepted as a numerical result; public rationales may contain mistakes even when the independently checked ledger is correct. Failed or incomplete cells are listed in the machine-readable summary.',
        '', '## Reproduce','', '```powershell','python scripts/audit_geometry.py',f'python scripts/summarize_benchmark.py --version {version}',
        '# Existing cell files are never overwritten. Running the command below resumes missing cells only:',
        'python scripts/run_benchmark.py --run --workers 3','```',
        '',f'Raw cells: `runs-v{version}/`. Per-instance metrics: `cells-v{version}.csv`. Machine-readable summary: `summary-v{version}.json`. Plot: `comparison-v{version}.png`.',
        '', 'Public pricing source: https://www.baseten.co/library/muse-spark-open/ . Geometry source: https://doi.org/10.1073/pnas.1217998110 .']
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':main()
