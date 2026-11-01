import warnings
import numpy as np
from scipy.special import logsumexp
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel,Matern,WhiteKernel
from sklearn.ensemble import RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
from frontier_scout.policy import expand,domain_features,expected_improvement

def predict(X,history,direction,features,forest=False):
    Z=expand(X,features);indices=[h['index'] for h in history];y=direction*np.array([h['mean'] for h in history]);center=float(y.mean());scale=max(float(y.std()),1e-9);target=(y-center)/scale;alpha=np.array([h['sample_variance']/h['historical_replicates'] for h in history])/scale**2+1e-5
    if forest:
        model=RandomForestRegressor(n_estimators=128,min_samples_leaf=1,max_features=1.,bootstrap=True,random_state=50102026,n_jobs=1);model.fit(Z[indices],target);trees=np.array([t.predict(Z) for t in model.estimators_]);mu=trees.mean(0);sigma=np.sqrt(trees.var(0)+float(alpha.mean()))
    else:
        kernel=ConstantKernel(1.,(1e-2,1e2))*Matern(np.full(Z.shape[1],.4),(.03,30.),nu=2.5)+WhiteKernel(.02,(1e-6,.5));model=GaussianProcessRegressor(kernel=kernel,alpha=alpha,n_restarts_optimizer=1,normalize_y=False,random_state=50102026)
        with warnings.catch_warnings():warnings.simplefilter('ignore',ConvergenceWarning);model.fit(Z[indices],target);mu,sigma=model.predict(Z,return_std=True)
    return mu,sigma,center,scale,float(target.max())

def reset_meta_weight(weights,enabled):
    base=np.array(weights[:3],float,copy=True);base/=base.sum()
    return np.r_[base*.9,.1] if enabled else np.r_[base,0.]

def update_weights(weights,means,sigmas,observation,active):
    # These means/sigmas were frozen before the current outcome was revealed.
    sigma=np.maximum(np.asarray(sigmas,float),.05);loss=.5*np.log(2*np.pi*sigma*sigma)+.5*((observation-np.asarray(means))/sigma)**2;loss=np.clip(loss,-5.,20.)
    logs=np.log(np.maximum(weights,1e-300))-.2*loss;logs[~np.array(active,bool)]=-np.inf;new=np.exp(logs-logsumexp(logs));new[np.array(active,bool)]=np.maximum(new[np.array(active,bool)],.02);new[~np.array(active,bool)]=0.;new/=new.sum()
    return new,loss

def predictions(dataset,history,features,meta_enabled):
    specs=[([],False),([],True),(domain_features(dataset.name),False)]
    if meta_enabled:specs.append((features,False))
    output=[predict(dataset.X,history,dataset.info['direction'],f,forest) for f,forest in specs]
    return output

def select(output,history,weights):
    values=np.array([expected_improvement(mu,sigma,best) for mu,sigma,center,scale,best in output]);score=np.asarray(weights[:len(output)])@values;score[[h['index'] for h in history]]=-np.inf
    return int(np.argmax(score))
