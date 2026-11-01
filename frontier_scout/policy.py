"""Same numerical inference/acquisition for raw, domain and Meta features.

Model output is a bounded feature DSL; no arbitrary Python is executed.
Policies receive public X and already-revealed observations only.
"""
import warnings
import numpy as np
from scipy.stats import norm
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel,Matern,WhiteKernel
from sklearn.ensemble import RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
OPS={'square':1,'abs':1,'log1p_abs':1,'sqrt_abs':1,'sin_deg':1,'cos_deg':1,'product':2,'ratio':2,'difference':2,'sum':2,'annular_area':2,'annular_inertia':2}

def validate_plan(plan,dimensions):
    if not isinstance(plan,dict) or set(plan)!={'hypothesis','features'} or not isinstance(plan['hypothesis'],str) or len(plan['hypothesis'])>3000 or not isinstance(plan['features'],list) or len(plan['features'])>6:raise ValueError('Invalid feature-plan schema')
    for i,feature in enumerate(plan['features']):
        if set(feature)!={'name','op','inputs','rationale'} or not isinstance(feature['name'],str) or len(feature['name'])>80 or not isinstance(feature['rationale'],str) or len(feature['rationale'])>1000:raise ValueError('Invalid feature fields')
        op=feature['op'];indices=feature['inputs']
        if op not in OPS or not isinstance(indices,list) or len(indices)!=OPS[op] or any(type(k) is not int or not 0<=k<dimensions+i for k in indices):raise ValueError('Invalid bounded feature operation/index')
    return plan

def expand(X,features):
    values=[np.array(v,float) for v in np.asarray(X).T]
    for f in features:
        args=[values[k] for k in f['inputs']];a=args[0];op=f['op']
        if op=='square':v=a*a
        elif op=='abs':v=abs(a)
        elif op=='log1p_abs':v=np.log1p(abs(a))
        elif op=='sqrt_abs':v=np.sqrt(abs(a))
        elif op=='sin_deg':v=np.sin(np.deg2rad(a))
        elif op=='cos_deg':v=np.cos(np.deg2rad(a))
        elif op=='product':v=a*args[1]
        elif op=='difference':v=a-args[1]
        elif op=='sum':v=a+args[1]
        elif op in ['annular_area','annular_inertia']:
            t=args[1]
            if np.any(t<0) or np.any(a<t):raise ValueError('Annular feature requires radius >= thickness >= 0 across public pool')
            v=np.pi*(a*a-(a-t)**2) if op=='annular_area' else np.pi/4*(a**4-(a-t)**4)
        elif op=='ratio':
            b=args[1];floor=max(float(np.ptp(b))*1e-3,1e-8);v=a/np.sqrt(b*b+floor*floor)
        else:raise ValueError('Unknown feature operation')
        if not np.isfinite(v).all() or abs(v).max()>1e12:raise ValueError('Nonfinite/overflowing feature')
        values.append(v)
    result=np.array(values).T;low=result.min(0);span=np.ptp(result,axis=0);keep=span>1e-12
    return (result[:,keep]-low[keep])/span[keep]

def domain_features(name):
    def f(label,op,*indices):return {'name':label,'op':op,'inputs':list(indices),'rationale':'Prewritten shared domain-informed numerical control; not a fitted constitutive law.'}
    if name=='crossed_barrel':
        return [f('annular_area','annular_area',2,3),f('total_annular_area','product',0,4),f('annular_inertia','annular_inertia',2,3),f('relative_wall','ratio',3,2),f('sin_twist','sin_deg',1),f('cos_twist','cos_deg',1)]
    if name=='printing':return [f('abs_offset_x','abs',2),f('abs_offset_y','abs',3),f('offset_x_squared','square',2),f('offset_y_squared','square',3),f('prime_speed','product',0,1)]
    if name=='perovskite':return [f('Cs_FA','product',0,1),f('Cs_MA','product',0,2),f('FA_MA','product',1,2),f('Cs_squared','square',0),f('FA_squared','square',1),f('MA_squared','square',2)]
    raise ValueError('Unknown case')

def expected_improvement(mu,sigma,best,xi=.01):
    sigma=np.maximum(sigma,1e-10);improvement=mu-best-xi;z=improvement/sigma
    return np.maximum(improvement*norm.cdf(z)+sigma*norm.pdf(z),0.)

def choose(X,history,direction,features=None,forest=False):
    # All observed labels are explicitly passed here. No Dataset/global oracle.
    features=features or [];Z=expand(X,features);indices=np.array([h['index'] for h in history]);y=direction*np.array([h['mean'] for h in history]);scale=max(float(y.std()),1e-9);center=float(y.mean());target=(y-center)/scale
    alpha=np.array([h['sample_variance']/h['historical_replicates'] for h in history])/scale**2+1e-5
    if forest:
        estimator=RandomForestRegressor(n_estimators=128,min_samples_leaf=1,max_features=1.,bootstrap=True,random_state=50102026,n_jobs=1);estimator.fit(Z[indices],target)
        predictions=np.array([tree.predict(Z) for tree in estimator.estimators_]);mu=predictions.mean(0);sigma=np.sqrt(predictions.var(0)+float(np.mean(alpha)));warning_count=0
    else:
        kernel=ConstantKernel(1.,(1e-2,1e2))*Matern(np.full(Z.shape[1],.4),(.03,30.),nu=2.5)+WhiteKernel(.02,(1e-6,.5))
        estimator=GaussianProcessRegressor(kernel=kernel,alpha=alpha,n_restarts_optimizer=1,normalize_y=False,random_state=50102026)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',ConvergenceWarning);estimator.fit(Z[indices],target);mu,sigma=estimator.predict(Z,return_std=True)
        warning_count=len(caught)
    scores=expected_improvement(mu,sigma,float(target.max()));scores[indices]=-np.inf;index=int(np.argmax(scores))
    return index,{'predicted_mean':float(direction*(mu[index]*scale+center)),'predicted_sigma':float(sigma[index]*scale),'EI_standardized':float(scores[index]),'surrogate_dimensions':Z.shape[1],'fit_warnings':warning_count,'surrogate_fit_count':1,'scope':'GP predictive uncertainty or RF tree-spread heuristic, not a calibrated coverage guarantee.'}
