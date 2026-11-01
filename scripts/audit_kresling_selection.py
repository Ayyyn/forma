"""Post-run audit: independent Gaussian-density inference and higher-order EIG.

This audit never changes selected actions, scored cells, prompts or protocols.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.special import logsumexp
from scipy.stats import norm

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from kresling_bench.__main__ import load_frozen
from kresling_bench.inference import information_scores


def audit(directory,baseline_only=False):
    manifest,data=load_frozen(directory)
    means=np.asarray(data['means']);offsets=np.array([c['offset_F_T'] for c in data['calibration_profiles']])
    means=(means[:,None,:,:]+offsets[None,:,None,:]).reshape(-1,len(data['experiments']),2)
    noise=np.asarray(data['noise_std_F_T']);members=len(offsets)
    ids=[e['id'] for e in data['experiments']]
    max_posterior_error=0.;max_nll_error=0.;max_rmse_error=0.;n_cells=0;n_obs=0
    cache={};regrets=[];score_errors=[];hashes={}
    for case in manifest['cases']:
        for method in (['bayes_eig'] if baseline_only else manifest['methods']):
            path=directory/'runs'/f"{method}-{case['case_id']}.json"
            raw=path.read_bytes();record=json.loads(raw);hashes[path.name]=hashlib.sha256(raw).hexdigest()
            logp=np.full(len(means),-np.log(len(means)));nll=[];valid=0
            for event in record['trace']:
                if 'outcome' not in event:continue
                out=event['outcome'];eid=out['experiment_id']
                if method=='bayes_eig':
                    key=logp.tobytes()
                    if key not in cache:cache[key]=information_scores(logp,means,noise,35,members)
                    scores=cache[key];chosen=ids.index(eid)
                    regrets.append(float(max(scores)-scores[chosen]))
                    score_errors.append(float(max(abs(scores-np.array(event['expected_information_nats'])))))
                if out['valid']:
                    # Independent use of normalized scipy.stats Gaussian densities,
                    # rather than the production updater's squared-residual formula.
                    log_likelihood=norm.logpdf(np.asarray(out['observation_F_T']),loc=means[:,ids.index(eid),:],scale=noise).sum(axis=1)
                    logp=logp+log_likelihood;logp-=logsumexp(logp);valid+=1;n_obs+=1
                error=float(max(abs(np.exp(logp)-np.array(out['posterior']))))
                max_posterior_error=max(max_posterior_error,error)
                p=np.exp(logp).reshape(-1,members).sum(axis=1)
                nll.append(float(-np.log(max(p[case['truth_index']],1e-300))))
            p=np.exp(logp).reshape(-1,members).sum(axis=1)
            last=-np.log(max(p[case['truth_index']],1e-300));nll += [float(last)]*(4-len(nll))
            max_nll_error=max(max_nll_error,float(max(abs(np.array(nll)-record['metrics']['step_nll']))))
            prediction=np.sum(p[:,None,None]*np.array(data['heldout_means']),axis=0)
            error=(prediction-np.array(data['heldout_means'])[case['truth_index']])/noise
            rmse=float(np.sqrt(np.mean(error**2)))
            max_rmse_error=max(max_rmse_error,abs(rmse-record['metrics']['heldout_standardized_rmse']))
            if bool(np.argmax(p)==case['truth_index'])!=record['metrics']['final_correct']:raise AssertionError('Independent identity disagrees')
            if valid!=record['metrics']['valid_measurements']:raise AssertionError('Observation counts disagree')
            n_cells+=1
    result={'passed':bool(max_posterior_error<1e-10 and max_nll_error<1e-10 and max_rmse_error<1e-10 and max(regrets)<.002 and max(score_errors)<.005),
       'scope':'baseline cells only' if baseline_only else 'all scored cells',
       'cells':n_cells,'observations':n_obs,'independent_posterior_max_abs_error':max_posterior_error,
       'independent_step_nll_max_abs_error':max_nll_error,'independent_prediction_rmse_max_abs_error':max_rmse_error,
       'baseline_decisions_checked_at_order35':len(regrets),'distinct_posteriors_checked_at_order35':len(cache),
       'max_order25_vs35_score_error_nats':max(score_errors),'max_order35_selection_regret_nats':max(regrets),
       'manifest_sha256':hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(),
       'audit_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'raw_cell_sha256':hashes,
       'note':'Independent inference checks computation for the declared synthetic likelihood, not physical validity. No scored outcomes or model settings were changed.'}
    target=directory/('baseline-numerical-audit.json' if baseline_only else 'independent-numerical-audit.json')
    target.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='raw_cell_sha256'},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'benchmarks/kresling-selection-v1')
    parser.add_argument('--baseline-only',action='store_true')
    args=parser.parse_args();audit(args.directory,args.baseline_only)
