"""Independent full-matrix inference check; does not call the production updater."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.special import logsumexp
from scipy.stats import multivariate_normal

ROOT=Path(__file__).resolve().parents[1]


def main():
    directory=ROOT/'benchmarks/kresling-selection-v1'
    manifest=json.loads((directory/'manifest.json').read_bytes())
    data=json.loads((directory/'catalogue.json').read_bytes())
    base=np.asarray(data['means']);bias=np.asarray([x['offset_F_T'] for x in data['calibration_profiles']])
    means=(base[:,None,:,:]+bias[None,:,None,:]).reshape(-1,base.shape[1],2)
    covariance=np.diag(np.asarray(data['noise_std_F_T'])**2);ids=[x['id'] for x in data['experiments']]
    maximum={'posterior':0.,'step_nll':0.,'mean_nll':0.,'heldout_rmse':0.};count=0;observations=0;raw_hashes={}
    for case in manifest['cases']:
        for method in manifest['methods']:
            path=directory/'runs'/f"{method}-{case['case_id']}.json";raw=path.read_bytes();r=json.loads(raw)
            raw_hashes[path.name]=hashlib.sha256(raw).hexdigest()
            logp=np.full(len(means),-np.log(len(means)));step=[]
            for event in r['trace']:
                if 'outcome' not in event:continue
                out=event['outcome']
                if out['valid']:
                    # Common covariance permits density of (y - mean) at zero.
                    residual=np.asarray(out['observation_F_T'])-means[:,ids.index(out['experiment_id']),:]
                    logp+=multivariate_normal.logpdf(residual,mean=np.zeros(2),cov=covariance)
                    logp-=logsumexp(logp);observations+=1
                posterior=np.exp(logp);maximum['posterior']=max(maximum['posterior'],float(max(abs(posterior-np.asarray(out['posterior'])))))
                marginal=posterior.reshape(16,9).sum(axis=1)
                step.append(float(-np.log(max(marginal[case['truth_index']],1e-300))))
            marginal=np.exp(logp).reshape(16,9).sum(axis=1)
            last=float(-np.log(max(marginal[case['truth_index']],1e-300)))
            step += [last]*(4-len(step));m=r['metrics']
            maximum['step_nll']=max(maximum['step_nll'],float(max(abs(np.asarray(step)-m['step_nll']))))
            maximum['mean_nll']=max(maximum['mean_nll'],abs(float(np.mean(step))-m['mean_nll_over_four_steps']))
            predicted=np.tensordot(marginal,np.asarray(data['heldout_means']),axes=1)
            error=(predicted-np.asarray(data['heldout_means'])[case['truth_index']])/np.asarray(data['noise_std_F_T'])
            maximum['heldout_rmse']=max(maximum['heldout_rmse'],abs(float(np.sqrt(np.mean(error**2)))-m['heldout_standardized_rmse']))
            if bool(np.argmax(marginal)==case['truth_index'])!=m['final_correct']:raise AssertionError('Independent final identity mismatch')
            count+=1
    result={'passed':all(x<1e-10 for x in maximum.values()),'cells':count,'valid_observations':observations,
            'max_abs_errors':maximum,'method':'scipy.stats.multivariate_normal log densities; independent full-matrix posterior and metric calculation',
            'manifest_sha256':hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(),
            'audit_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'raw_cell_sha256':raw_hashes}
    (directory/'independent-posterior-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='raw_cell_sha256'},indent=2))
    if not result['passed']:raise AssertionError('Independent inference audit failed')


if __name__=='__main__':main()
