"""Freeze/run the synthetic Kresling experiment-selection test; no overwritten cells."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from .design import catalogue,oracle_check,SEEDS,QUADRATURE
from .inference import Laboratory,information_scores
from .policies import InformationPolicy,space_filling,meta_choice,MODEL

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'benchmarks/kresling-selection-v1'


def dumps(data):return json.dumps(data,indent=2,allow_nan=False)


def source_hashes():
    paths=list((ROOT/'kresling_bench').glob('*.py'))+[ROOT/'kresling_proof/model.py',ROOT/'kresling_proof/oracle.py',ROOT/'scripts/api_preflight.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def freeze(directory):
    if (directory/'manifest.json').exists():raise ValueError('Existing protocol is immutable; choose a new version for changes')
    data=catalogue();audit=oracle_check(data)
    if not audit['passed']:raise RuntimeError('Independent prediction oracle disagreement')
    lab=Laboratory(data,0,0);means=lab.means;noise=lab.noise
    priors=[np.full(len(means),1/len(means)),np.random.default_rng(628).dirichlet(np.ones(len(means)))]
    focused=np.full(len(means),1e-9);focused[5*lab.members+4]=.6;focused[6*lab.members+4]=.4;focused/=focused.sum();priors.append(focused)
    convergence=[]
    for prior in priors:
        a=information_scores(np.log(prior),means,noise,QUADRATURE,lab.members)
        b=information_scores(np.log(prior),means,noise,35,lab.members)
        regret=float(max(b)-b[int(np.argmax(a))]);error=float(max(abs(a-b)))
        convergence.append({'posterior':prior.tolist(),'order25':a.tolist(),'order35':b.tolist(),
                            'max_error_nats':error,'selection_regret_at35_nats':regret,
                            'passed':bool(error<.005 and regret<.002)})
    if not all(x['passed'] for x in convergence):raise RuntimeError('EIG quadrature audit failed; do not run scored tests')
    cases=[]
    for hi,h in enumerate(data['hypotheses']):
        for si,seed in enumerate(SEEDS):
            token=hashlib.sha256(f"{h['id']}|{seed}".encode()).hexdigest()[:12]
            cases.append({'case_id':token,'truth_index':hi,'noise_seed':seed,'calibration_index':(hi*3+si*4)%9})
    manifest={'version':1,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'task':'closed-world virtual model discrimination',
       'case_count':len(cases),'hypothesis_clusters':16,'noise_seeds':SEEDS,'measurement_budget':4,
       'paired_readouts_per_measurement':2,'nuisance_calibration_profiles':9,'joint_latent_hypotheses':144,
       'methods':['bayes_eig','space_filling','meta'],
       'primary_metric':'mean true-hypothesis negative log probability over measurement steps 1..4 (nats; lower better)',
       'secondary_metrics':['final identification accuracy','confident wrong rate at 90%','held-out response RMSE standardized by declared noise','correct 90% attainment','latency','token usage'],
       'decision_gate':{'relative_primary_loss_reduction_at_least':.10,'paired_cluster_bootstrap_difference_lower_bound_above':0,
                        'confidence_level':.95,'final_accuracy_not_worse':True,'max_invalid_decision_fraction':.05,
                        'minimum_transport_complete_fraction':.95},
       'fairness':['Same prior, full predicted means, noise likelihood, public history, posterior estimator and measurement allowance.',
         'Independent uniform mechanical and nuisance-calibration priors. One fixed unknown calibration profile adds a constant F/T offset throughout each case; the objective marginalizes calibration.',
         'Each observation records F and T together at a pose with both coordinates constrained; repeats cost one slot and have independent noise.',
         'Counterfactual observation noise keyed by hidden case, noise seed, experiment ID and replicate; same query/replicate gives same potential observation across policies.',
         'True identity, noise outcomes and held-out prediction scores never enter Meta requests.',
         'No API retry, silent policy fallback or best-of resampling. Invalid actions consume slots. Transport failures retain the last belief for missing rounds and are reported separately.',
         'Common numerical catalogue cost is separate. Measurement counts are equal; compute/time/API expenditure is measured, not claimed equal.',
         'All 16 true model identities are represented with 3 noise seeds each; these are 16 task clusters, not 48 independent physics families.'],
       'meta':{'model':MODEL,'tool_choice':'auto','reasoning_effort':'medium','temperature':.2,'max_output_tokens_per_decision':8192,'timeout_seconds':180,'calls_per_case_max':4},
       'baseline':{'type':'greedy Bayesian expected information gain','quadrature_nodes_per_channel':QUADRATURE,
                   'search':'all 12 experiments, repeats allowed','tie_break':'first listed ID','information_gain_is_not_sent_to_Meta':True,
                   'limitation':'one-step expected information maximization, not a globally optimal four-step policy'},
       'cost_estimate_rates':{'input_per_million_usd':1.25,'cached_input_per_million_usd':.15,'output_per_million_usd':4.25,
                              'source':'https://www.baseten.co/library/muse-spark-open/','actual_hackathon_charges_unverified':True},
       'source_sha256':source_hashes(),'cases':cases,'independent_prediction_audit':audit,'quadrature_audit':convergence,
       'scope':'Synthetic observations generated by the same declared reduced model and known noise. No material experiments, unseen-physics generalization or new invention claims.'}
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'catalogue.json').write_text(dumps(data),encoding='utf-8')
    manifest['catalogue_sha256']=hashlib.sha256((directory/'catalogue.json').read_bytes()).hexdigest()
    (directory/'manifest.json').write_text(dumps(manifest),encoding='utf-8')
    print(dumps({'frozen':str(directory),'cases':len(cases),'audit':audit,'quadrature_passed':True}))


def load_frozen(directory):
    m=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if m['source_sha256']!=source_hashes():raise RuntimeError('Source drift: frozen run rejected')
    raw=(directory/'catalogue.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=m['catalogue_sha256']:raise RuntimeError('Catalogue drift')
    return m,json.loads(raw)


def run_cell(directory,data,case,method,information_policy):
    target=directory/'runs'/f"{method}-{case['case_id']}.json"
    if target.exists():return {'method':method,'case':case['case_id'],'status':'already_saved'}
    lab=Laboratory(data,case['truth_index'],case['noise_seed'],case['calibration_index'])
    events=[];started=time.perf_counter();transport_failed=False;invalid=0
    for turn in range(lab.budget):
        before=time.perf_counter()
        if method=='bayes_eig':choice,event=information_policy.choose(lab)
        elif method=='space_filling':choice,event=space_filling(lab)
        elif method=='meta':
            choice,event=meta_choice(lab)
            if event['transport'].get('http_status')!=200:
                transport_failed=True;events.append({'turn':turn+1,**event});break
        else:raise ValueError('Unknown policy')
        event['policy_seconds']=time.perf_counter()-before
        if choice is None or choice not in [e['id'] for e in data['experiments']]:invalid+=1
        observation=lab.measure(choice or '__invalid__')
        events.append({'turn':turn+1,**event,'outcome':observation})
    record={'method':method,'case_id':case['case_id'],'truth_hypothesis_id':data['hypotheses'][case['truth_index']]['id'],
            'noise_seed':case['noise_seed'],'truth_calibration_id':data['calibration_profiles'][case['calibration_index']]['id'],
            'status':'transport_incomplete' if transport_failed else 'completed',
            'elapsed_seconds':time.perf_counter()-started,'invalid_decisions':invalid,'metrics':lab.metrics(),
            'trace':events,'physical_data':False,'actual_model_calls':len(events) if method=='meta' else 0}
    target.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive create: never overwrite an inconvenient scored outcome.
    with target.open('x',encoding='utf-8') as f:f.write(dumps(record))
    return {'method':method,'case':case['case_id'],'status':record['status'],'metrics':record['metrics']}


def run(directory,methods,workers):
    manifest,data=load_frozen(directory);policy=InformationPolicy()
    # Cache only a deterministic computation common to every initial public state.
    if 'bayes_eig' in methods:
        initial=Laboratory(data,0,0);setup=time.perf_counter();policy.choose(initial)
        setup={'baseline_common_prior_setup_seconds':time.perf_counter()-setup,'policy':'cache exact deterministic initial-state scores only'}
        if not (directory/'setup.json').exists():(directory/'setup.json').write_text(dumps(setup),encoding='utf-8')
    jobs=[(case,method) for case in manifest['cases'] for method in methods if not (directory/'runs'/f"{method}-{case['case_id']}.json").exists()]
    print(f'Running {len(jobs)} missing cells; workers={workers}',flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(run_cell,directory,data,case,method,policy):(case,method) for case,method in jobs}
        for i,f in enumerate(as_completed(futures),1):
            result=f.result()
            print(dumps({'saved':i,'of':len(jobs),'method':result['method'],'case':result['case'],'status':result['status']}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['freeze','run','summarize'])
    parser.add_argument('--directory',type=Path,default=DEFAULT)
    parser.add_argument('--methods',nargs='+',choices=['bayes_eig','space_filling','meta'],default=['bayes_eig','space_filling','meta'])
    parser.add_argument('--workers',type=int,choices=[1,2],default=2)
    args=parser.parse_args()
    if args.command=='freeze':freeze(args.directory)
    elif args.command=='run':run(args.directory,args.methods,args.workers)
    else:
        from .summary import summarize
        summarize(args.directory)


if __name__=='__main__':main()
