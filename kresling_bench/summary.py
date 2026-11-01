"""Replay every saved decision, report paired cluster uncertainty and honest gates."""
import csv
import hashlib
import json
from collections import Counter
import numpy as np
from .inference import Laboratory


def replay(data,case,record):
    from .policies import build_payload
    lab=Laboratory(data,case['truth_index'],case['noise_seed'],case['calibration_index'])
    for event in record['trace']:
        if record['method']=='meta':
            digest=hashlib.sha256(json.dumps(build_payload(lab),sort_keys=True).encode()).hexdigest()
            if digest!=event['request_sha256']:raise AssertionError('Public API request does not replay')
        if 'outcome' not in event:
            if record['status']!='transport_incomplete':raise AssertionError('Missing charged outcome')
            continue
        saved=event['outcome']
        if record['method']=='meta':
            choice=(event.get('selection') or {}).get('experiment_id') or '__invalid__'
            if choice!=saved['experiment_id']:raise AssertionError('Tool selection and charged action differ')
        elif record['method']=='bayes_eig':
            best=int(np.argmax(event['expected_information_nats']))
            if data['experiments'][best]['id']!=saved['experiment_id']:raise AssertionError('Baseline action not greedy EIG')
        elif record['method']=='space_filling':
            if data['experiments'][[0,11,2,9][len(lab.trace)]]['id']!=saved['experiment_id']:raise AssertionError('Fixed control changed')
        actual=lab.measure(saved['experiment_id'])
        if actual.keys()!=saved.keys():raise AssertionError('Observation fields changed')
        for key in actual:
            if isinstance(actual[key],list):np.testing.assert_allclose(actual[key],saved[key],rtol=1e-12,atol=1e-14)
            elif actual[key]!=saved[key]:raise AssertionError(f'Replay disagreement: {key}')
    expected=lab.metrics()
    for key,value in expected.items():
        saved=record['metrics'][key]
        if isinstance(value,(float,list)):np.testing.assert_allclose(value,saved,rtol=1e-12,atol=1e-14)
        elif value!=saved:raise AssertionError(f'Metric replay disagreement: {key}')
    if len(lab.trace)>4:raise AssertionError('Overspent budget')
    if record['method']=='meta':
        if record['actual_model_calls']!=len(record['trace']):raise AssertionError('Call ledger disagreement')
        for event in record['trace']:
            if event['transport'].get('http_status')==200 and not event.get('response_id'):
                raise AssertionError('Successful API response lacks provider identity')
    return {'charged':len(lab.trace),'valid':sum(x['valid'] for x in lab.trace)}


def cluster_interval(differences,clusters,repetitions=10000):
    unique=sorted(set(clusters))
    means=np.array([np.mean([v for v,c in zip(differences,clusters) if c==h]) for h in unique])
    rng=np.random.default_rng(28102026)
    bootstrap=np.mean(means[rng.integers(0,len(means),size=(repetitions,len(means)))],axis=1)
    return {'estimate':float(np.mean(means)), 'lower95':float(np.quantile(bootstrap,.025)),
            'upper95':float(np.quantile(bootstrap,.975)),'clusters':len(unique),
            'bootstrap_repetitions':repetitions,'seed':28102026,
            'scope':'conditional on this fixed synthetic catalogue and nuisance/noise design'}


def usage_totals(records,rates):
    total=Counter();ids=[];reasoning_calls=0;priced_calls=0;estimated=0.
    for record in records:
        for e in record['trace']:
            if record['method']!='meta':continue
            if e.get('response_id'):ids.append(e['response_id'])
            u=e['transport'].get('usage') or {}
            inp=u.get('prompt_tokens',u.get('input_tokens',0)) or 0
            out=u.get('completion_tokens',u.get('output_tokens',0)) or 0
            cached=(u.get('prompt_tokens_details') or {}).get('cached_tokens',0) or 0
            reasoning=(u.get('completion_tokens_details') or {}).get('reasoning_tokens',0) or 0
            total.update(input_tokens=inp,output_tokens=out,cached_input_tokens=cached,reasoning_tokens=reasoning)
            reasoning_calls+=int(reasoning>0);priced_calls+=int(bool(u))
            estimated+=((inp-cached)*rates['input_per_million_usd']+cached*rates['cached_input_per_million_usd']+out*rates['output_per_million_usd'])/1e6
    return {**dict(total),'actual_api_calls':sum(r['actual_model_calls'] for r in records),
            'responses_with_usage':priced_calls,'responses_reporting_reasoning_tokens':reasoning_calls,
            'provider_response_ids':ids,'estimated_usd_for_reported_usage':estimated,
            'billing_note':'Published generic rates; actual hackathon credit deductions and unreported timeout usage are unverified.'}


def summarize(directory):
    from .__main__ import load_frozen,dumps
    manifest,data=load_frozen(directory)
    cells={};rows=[];audit={'passed':True,'cells':0,'charged':0,'valid':0}
    missing=[]
    for case in manifest['cases']:
        for method in manifest['methods']:
            path=directory/'runs'/f"{method}-{case['case_id']}.json"
            if not path.exists():missing.append(str(path));continue
            record=json.loads(path.read_text(encoding='utf-8'))
            if record['method']!=method or record['case_id']!=case['case_id']:raise AssertionError('Wrong saved cell identity')
            checked=replay(data,case,record)
            audit['cells']+=1;audit['charged']+=checked['charged'];audit['valid']+=checked['valid']
            cells[(case['case_id'],method)]=record
            rows.append({'case_id':case['case_id'],'truth':record['truth_hypothesis_id'],'noise_seed':case['noise_seed'],
                         'method':method,'status':record['status'],'elapsed_seconds':record['elapsed_seconds'],
                         'invalid_decisions':record['invalid_decisions'],**record['metrics']})
    if missing:raise RuntimeError(f'Incomplete matrix: {len(missing)} missing cells. No selectively complete summary allowed.')
    aggregate={}
    for method in manifest['methods']:
        rr=[r for r in rows if r['method']==method]
        aggregate[method]={'cases':len(rr),'mean_nll_over_four_steps':float(np.mean([r['mean_nll_over_four_steps'] for r in rr])),
             'mean_step_nll':np.mean([r['step_nll'] for r in rr],axis=0).tolist(),
             'final_correct':sum(r['final_correct'] for r in rr),
             'confident_wrong':sum(r['confident_wrong'] for r in rr),
             'correct_90_percent_by_final':sum(r['correct_90_percent_by_step'] is not None for r in rr),
             'mean_heldout_standardized_rmse':float(np.mean([r['heldout_standardized_rmse'] for r in rr])),
             'transport_complete':sum(r['status']=='completed' for r in rr),
             'invalid_decisions':sum(r['invalid_decisions'] for r in rr),
             'valid_measurements':sum(r['valid_measurements'] for r in rr),
             'median_case_seconds':float(np.median([r['elapsed_seconds'] for r in rr])),
             'sum_case_seconds':sum(r['elapsed_seconds'] for r in rr)}
    differences=[];clusters=[];paired=[]
    for case in manifest['cases']:
        b=cells[(case['case_id'],'bayes_eig')];m=cells[(case['case_id'],'meta')]
        diff=b['metrics']['mean_nll_over_four_steps']-m['metrics']['mean_nll_over_four_steps']
        differences.append(diff);clusters.append(b['truth_hypothesis_id'])
        paired.append({'case_id':case['case_id'],'truth':b['truth_hypothesis_id'],'baseline_minus_meta_loss':diff})
    interval=cluster_interval(differences,clusters)
    b=aggregate['bayes_eig'];m=aggregate['meta'];n=m['cases']
    reduction=(b['mean_nll_over_four_steps']-m['mean_nll_over_four_steps'])/b['mean_nll_over_four_steps']
    gates={'relative_loss_reduction_at_least_10_percent':bool(reduction>=.1),
           'cluster95_lower_bound_above_zero':bool(interval['lower95']>0),
           'final_accuracy_not_worse':bool(m['final_correct']>=b['final_correct']),
           'invalid_decisions_at_most_5_percent':bool(m['invalid_decisions']/(n*4)<=.05),
           'transport_complete_at_least_95_percent':bool(m['transport_complete']/n>=.95)}
    verdict=('GO: demonstrated selection value within this synthetic benchmark' if all(gates.values()) else
             'INCONCLUSIVE: transport completion below 95%; no capability verdict' if not gates['transport_complete_at_least_95_percent'] else
             'NO-GO: Meta selection advantage not demonstrated; retain the deterministic solver')
    usage=usage_totals(list(cells.values()),manifest['cost_estimate_rates'])
    report={'verdict':verdict,'aggregate':aggregate,'baseline_minus_meta_primary_loss':interval,
            'meta_relative_primary_loss_reduction':float(reduction),'decision_gates':gates,'replay_audit':audit,
            'usage':usage,'baseline_setup':json.loads((directory/'setup.json').read_text(encoding='utf-8')),
            'manifest_sha256':hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(),
            'limitations':['Closed-world synthetic model discrimination, not physical validation.',
              '16 fixed mechanical-model clusters with 3 noise seeds, not broad mechanism or material coverage.',
              'One frozen prompt/model/medium-effort configuration; results do not prove all AI approaches fail or succeed.',
              'EIG is greedy one-step information gain, not a globally optimal four-measurement policy.',
              'Common model predictions and posterior arithmetic supplied to both policies; no measured advantage for generating physics.',
              'Calibration and measurement noise are declared synthetic observation assumptions, not experimentally calibrated sensors.']}
    (directory/'summary.json').write_text(dumps(report),encoding='utf-8')
    for filename,records in [('cells.csv',rows),('paired.csv',paired)]:
        with (directory/filename).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    plot(directory,aggregate,differences,clusters)
    table='\n'.join(f"| {name} | {v['mean_nll_over_four_steps']:.4f} | {v['final_correct']}/{v['cases']} | {v['confident_wrong']} | {v['median_case_seconds']:.2f} |" for name,v in aggregate.items())
    text=f'''# Kresling virtual experiment-selection benchmark

**{verdict}.**

Real Meta API calls: {usage['actual_api_calls']}; reported-usage estimated cost: ${usage['estimated_usd_for_reported_usage']:.3f}. Actual credit deductions are unverified.

Each method gets four paired force/torque observations from the same reduced mechanical model, with unknown fixed calibration offset and fresh Gaussian noise. All 48 matched cases and all failed/invalid rounds are retained. Measurements are virtual; no physical data were collected.

| Policy | Mean step-1..4 true-model NLL (lower better) | Final correct | Confident wrong | Median seconds/case |
|---|---:|---:|---:|---:|
{table}

Meta relative primary loss reduction: {100*reduction:.2f}%. Baseline-minus-Meta loss: {interval['estimate']:.4f} nats, paired mechanical-cluster bootstrap 95% interval [{interval['lower95']:.4f}, {interval['upper95']:.4f}], 16 clusters. Positive differences favor Meta. The predeclared gate requires at least 10% loss reduction, a positive interval lower bound, no lower final accuracy, at most 5% invalid actions, and at least 95% transport-complete cases.

Replay: {audit['cells']} cells, {audit['charged']} charged actions, {audit['valid']} valid observations; all saved observations, Bayesian posteriors and metrics reproduced. Successful API records retain provider response identities, public tool arguments and usage; private reasoning text and keys are not saved.

The baseline exhaustively evaluates the expected one-step information gain of all 12 possible tests, integrating measurement uncertainty and marginalizing nine nuisance calibration profiles. It targets the mechanical model, not instrument-offset identification. It is a strong greedy baseline, not an optimal four-step policy. The four-corner space-filling policy is a secondary control. Meta receives the same predicted mechanical responses, calibration prior, likelihood and public Bayesian state, but not the baseline's information scores, hidden model, noise realizations, held-out scores or previous cases.

The experiment is conditional on this fixed synthetic catalogue: 16 effective mechanical hypotheses, three noise seeds each, discrete calibration profiles and known noise levels. It does not establish behavior on unknown real materials, model discrepancy or new mechanism families. The independent vertex-energy oracle checks numerical implementation of the same published reduced model, not the model's physical truth. This is a new hackathon-built benchmark of established Kresling mechanics and established experiment-design methods; no invention of Kresling inverse design, multistability or Bayesian design is claimed.

Reproduce: `python -m kresling_bench summarize`. Offline tests: `python -m unittest discover -s tests`. The frozen manifest, catalogue and raw `runs/` cells are retained. Re-running `run` skips saved cells and never substitutes better outcomes. A fresh API run needs a new explicitly versioned freeze and incurs charges.

See `docs/KRESLING_BENCHMARK_PROTOCOL.md`, `summary.json`, `cells.csv`, `paired.csv` and `comparison.png` for protocol, uncertainty, usage and detailed limits.
'''
    (directory/'README.md').write_text(text,encoding='utf-8')
    print(dumps({k:report[k] for k in ['verdict','aggregate','baseline_minus_meta_primary_loss','meta_relative_primary_loss_reduction','decision_gates','replay_audit']}))


def plot(directory,aggregate,differences,clusters):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'bayes_eig':'#276b56','space_filling':'#92918b','meta':'#bb653d'}
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    for name,v in aggregate.items():axes[0].plot(range(1,5),v['mean_step_nll'],'o-',label=name,color=colors[name])
    axes[0].set(xlabel='Virtual paired measurements',ylabel='Mean true-model NLL (nats)',title='Earlier identification is better',xticks=[1,2,3,4]);axes[0].legend(fontsize=8)
    unique=sorted(set(clusters));values=[np.mean([d for d,c in zip(differences,clusters) if c==h]) for h in unique]
    axes[1].bar(unique,values,color=['#bb653d' if x>0 else '#276b56' for x in values]);axes[1].axhline(0,color='black',lw=.8)
    axes[1].set(ylabel='Baseline loss minus Meta loss (nats)',title='Positive favors Meta');axes[1].tick_params(axis='x',labelrotation=90,labelsize=7)
    names=list(aggregate);axes[2].bar(names,[aggregate[x]['median_case_seconds'] for x in names],color=[colors[x] for x in names]);axes[2].set(ylabel='Median seconds per four-test case',title='Selection + inference time');axes[2].tick_params(axis='x',labelrotation=20,labelsize=8)
    fig.suptitle('Synthetic Kresling experiment selection • 48 matched cases / 16 mechanical clusters',fontsize=11)
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.savefig(directory/'comparison.png',dpi=180);fig.savefig(directory/'comparison.svg');plt.close(fig)
