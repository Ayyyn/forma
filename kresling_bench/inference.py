"""Identical Bayesian estimator and observation budget for every policy."""
from functools import lru_cache
import hashlib
import json
import numpy as np
from scipy.special import logsumexp
from numpy.polynomial.hermite import hermgauss


def entropy(logp,members=1):
    group_logp=logsumexp(logp.reshape(-1,members),axis=-1)
    p=np.exp(group_logp)
    return float(-np.sum(p*group_logp))


def update(logp,means,observation,noise):
    z=(np.asarray(observation)-means)/noise
    result=logp-.5*np.sum(z*z,axis=-1)
    return result-logsumexp(result)


@lru_cache(maxsize=4)
def quadrature(order):
    x,w=hermgauss(order)
    points=np.stack(np.meshgrid(x,x,indexing='ij'),axis=-1).reshape(-1,2)*np.sqrt(2)
    weights=np.outer(w,w).reshape(-1)/np.pi
    return points,weights


def expected_information(logp,means,noise,order=25,members=1):
    """Gaussian-mixture expected entropy reduction, deterministic 2D quadrature."""
    points,weights=quadrature(order)
    prior=np.exp(logp)
    active=np.flatnonzero(prior>1e-12)
    expected=0.
    # Bounded memory even with nuisance-calibration hypotheses. Information is
    # about the MECHANICAL model, marginalizing calibration rather than rewarding
    # gratuitous precision about an instrument offset.
    for start in range(0,len(active),12):
        indices=active[start:start+12]
        y=means[indices,None,:]+noise*points[None,:,:]
        z=(y[:,:,None,:]-means[None,None,:,:])/noise
        joint=logp[None,None,:]-.5*np.sum(z*z,axis=-1)
        posterior=joint-logsumexp(joint,axis=-1,keepdims=True)
        group_logp=logsumexp(posterior.reshape(len(indices),len(points),-1,members),axis=-1)
        conditional=-np.sum(np.exp(group_logp)*group_logp,axis=-1)
        expected+=np.sum(prior[indices,None]*weights[None,:]*conditional)
    return float(entropy(logp,members)-expected)


def information_scores(logp,all_means,noise,order=25,members=1):
    return np.array([expected_information(logp,all_means[:,i,:],noise,order,members) for i in range(all_means.shape[1])])


def potential_observation(mean,noise,case_token,seed,experiment_id,replicate):
    # Same potential outcome for the same experiment/replicate across policies.
    # Different selected experiments do not receive artificially identical noise.
    key=f'{case_token}|{seed}|{experiment_id}|{replicate}'.encode()
    rng=np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest()[:8],'big'))
    return np.asarray(mean)+noise*rng.normal(size=2)


class Laboratory:
    def __init__(self,data,truth_index,seed,calibration_index=0):
        self.data=data;self.truth_index=truth_index;self.seed=seed
        base=np.asarray(data['means']);self.noise=np.array(data['noise_std_F_T'])
        self.members=len(data['calibration_profiles']);self.calibration_index=calibration_index
        self.bias=np.array([c['offset_F_T'] for c in data['calibration_profiles']])
        self.means=(base[:,None,:,:]+self.bias[None,:,None,:]).reshape(-1,base.shape[1],2)
        self.logp=np.full(len(self.means),-np.log(len(self.means)))
        self.trace=[];self.replicates={};self.budget=data['measurement_budget']
        self.token=hashlib.sha256(json.dumps({'mechanical':data['hypotheses'][truth_index],
            'calibration':data['calibration_profiles'][calibration_index]},sort_keys=True).encode()).hexdigest()[:12]

    def measure(self,experiment_id):
        if len(self.trace)>=self.budget:raise ValueError('Measurement allowance exhausted')
        entry={'attempt':len(self.trace)+1,'experiment_id':experiment_id}
        self.trace.append(entry) # Charge invalid/repeated proposals too.
        ids=[e['id'] for e in self.data['experiments']]
        if experiment_id not in ids:
            entry.update(valid=False,error='Unknown experiment; slot consumed, no observation')
        else:
            ei=ids.index(experiment_id)
            replicate=self.replicates.get(experiment_id,0);self.replicates[experiment_id]=replicate+1
            truth=self.truth_index*self.members+self.calibration_index
            observation=potential_observation(self.means[truth,ei],self.noise,self.token,self.seed,experiment_id,replicate)
            self.logp=update(self.logp,self.means[:,ei,:],observation,self.noise)
            entry.update(valid=True,replicate=replicate,observation_F_T=observation.tolist())
        entry['posterior']=np.exp(self.logp).tolist()
        return entry

    def public_state(self):
        return {'measurements_remaining':self.budget-len(self.trace),'joint_posterior_mechanical_major_calibration_minor':np.exp(self.logp).tolist(),
                'mechanical_posterior':np.exp(self.logp).reshape(-1,self.members).sum(axis=1).tolist(),
                'history':self.trace}

    def metrics(self):
        snapshots=[np.array(x['posterior']).reshape(-1,self.members).sum(axis=1) for x in self.trace]
        current=np.exp(self.logp).reshape(-1,self.members).sum(axis=1)
        snapshots+= [current]*(self.budget-len(snapshots))
        # Failure/missing rounds retain the last belief; never fabricate observations.
        true_probs=[float(p[self.truth_index]) for p in snapshots]
        nll=[-np.log(max(p,1e-300)) for p in true_probs]
        final=current;choice=int(np.argmax(final))
        confidence=float(np.max(final));correct=choice==self.truth_index
        first=next((i+1 for i,p in enumerate(snapshots) if int(np.argmax(p))==self.truth_index and max(p)>=.9),None)
        held=np.asarray(self.data['heldout_means'])
        prediction=np.einsum('h,hed->ed',final,held)
        error=(prediction-held[self.truth_index])/self.noise
        return {'mean_nll_over_four_steps':float(np.mean(nll)),'step_nll':list(map(float,nll)),
                'final_nll':float(nll[-1]),'final_correct':bool(correct),'final_confidence':confidence,
                'confident_wrong':bool(confidence>=.9 and not correct),'correct_90_percent_by_step':first,
                'heldout_standardized_rmse':float(np.sqrt(np.mean(error**2))),
                'valid_measurements':sum(x['valid'] for x in self.trace),'charged_attempts':len(self.trace),
                'final_hypothesis_id':self.data['hypotheses'][choice]['id']}
