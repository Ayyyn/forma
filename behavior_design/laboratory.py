"""Same bounded numerical tools for every controller; failed attempts are charged."""
import hashlib,json,time
import numpy as np
from scipy.optimize import least_squares
from scipy.stats import qmc
from .model import ARCHITECTURES,bounds,design,evaluate

class BudgetExhausted(Exception):pass

class Laboratory:
    def __init__(self,task,budget=240):
        self.task=task;self.budget=budget;self.records=[];self.cache={};self.events=[];self.started=time.monotonic()
    @property
    def remaining(self):return self.budget-len(self.records)
    def event(self,name,data):self.events.append({'type':name,'elapsed_seconds':time.monotonic()-self.started,**data})
    def summary(self,r):
        keys=['id','architecture','parameters','normalized_RMS_error','normalized_max_error','mechanical_screen_passed','target_passed','margins','geometry_budget','error','elapsed_seconds']
        return {k:r[k] for k in keys if k in r}
    def best(self):
        valid=[r for r in self.records if 'result' in r]
        return min(valid,key=lambda r:(not r['mechanical_screen_passed'],r['normalized_RMS_error'])) if valid else None
    def context(self):
        library=[]
        for name,spec in ARCHITECTURES.items():
            box=bounds(name,self.task);library.append({'name':name,'motif':spec,'parameter_names':['radius_mm','height_ratio','published_stiffness_scale','background_N_mm'] if spec.get('family')=='kresling' else ['half_span_mm','rise_mm','axial_k_N_mm','return_margin_N_mm'],'bounds':box.tolist() if box is not None else None})
        return {'task':self.task,'library':library,'ledger':{'candidate_limit':self.budget,'new_candidate_queries':len(self.records),'remaining':self.remaining,'cached_inspections_free':True,'all_optimizer_inner_candidates_charged':True},'best':self.summary(self.best()) if self.best() else None,'screen':'Ideal quasi-static displacement control. Positive tangent screen; constrained internal stability differs from free-state stability. Declared packaging envelope is not complete hardware CAD. Kresling roots are sampled, not exhaustive.','tools':'fit_architecture uses the SAME normalized-parameter bounded least-squares fitter for every controller. It optimizes RMS curve residual plus negative mechanical-margin penalties. Same architecture repeat starts at its best candidate, otherwise midpoint; optional start_parameters permits a restart. 240 candidate allowance per task, no equal-CPU claim. Invalid candidates count. Exact cached repeats are free.'}
    def evaluate(self,name,x):
        x=[float(v) for v in x];key=json.dumps([name,x],separators=(',',':'))
        if key in self.cache:return self.cache[key]
        if not self.remaining:raise BudgetExhausted('Candidate allowance exhausted')
        start=time.monotonic();r={'id':f'c{len(self.records)+1:03d}','architecture':name,'parameters':x}
        try:
            result=evaluate(design(name,x),self.task);r.update({k:v for k,v in result.items() if k not in ('points','design')});r['result']=result
        except (ValueError,TypeError,FloatingPointError,np.linalg.LinAlgError) as e:r['error']=str(e)
        r['elapsed_seconds']=time.monotonic()-start;self.records.append(r);self.cache[key]=r
        return r
    def residual(self,r):
        m=len(self.task['fit_travel_mm'])
        if 'result' not in r:return np.full(m+6,100.)
        result=r['result'];error=(np.array([p['force_N'] for p in result['points']])-self.task['target_force_N'])/max(self.task['target_force_N']);margins=result['margins'];penalty=[max(0.,-margins.get(k,0.)) for k in ['width','height','minimum_tangent','nonnegative_force','link_travel','link_force']]
        return np.r_[error,5*np.asarray(penalty)]
    def fit(self,name,maximum_evaluations=40,start_parameters=None):
        if name not in ARCHITECTURES:raise ValueError('Unknown architecture')
        box=bounds(name,self.task)
        if box is None:raise ValueError('Architecture has no public packaging domain')
        if type(maximum_evaluations)!=int or not 1<=maximum_evaluations<=240:raise ValueError('Fit budget must be integer 1..240')
        allowance=min(maximum_evaluations,self.remaining);start_count=len(self.records)
        existing=[r for r in self.records if r['architecture']==name and 'result' in r]
        x=np.array(start_parameters if start_parameters is not None else min(existing,key=lambda r:np.linalg.norm(self.residual(r)))['parameters'] if existing else box.mean(axis=1));span=box[:,1]-box[:,0]
        if x.shape!=(4,) or np.any(x<box[:,0]) or np.any(x>box[:,1]):raise ValueError('Start parameters outside bounds')
        def fun(z):
            candidate=box[:,0]+span*z;key=json.dumps([name,candidate.tolist()],separators=(',',':'))
            if len(self.records)-start_count>=allowance and key not in self.cache:raise BudgetExhausted('Local fitter allowance exhausted')
            return self.residual(self.evaluate(name,candidate))
        status='converged'
        try:least_squares(fun,np.clip((x-box[:,0])/span,1e-9,1-1e-9),bounds=(np.zeros(4),np.ones(4)),ftol=1e-10,xtol=1e-10,gtol=1e-10,max_nfev=1000)
        except BudgetExhausted:status='budget_stop'
        existing=[r for r in self.records if r['architecture']==name and 'result' in r]
        best=min(existing,key=lambda r:(not r['mechanical_screen_passed'],r['normalized_RMS_error'])) if existing else None
        result={'architecture':name,'new_queries':len(self.records)-start_count,'status':status,'best':self.summary(best) if best else None,'remaining':self.remaining};self.event('fit',result);return result

def numerical(lab):
    """Enumerate every feasible motif, then exploit the best with a Sobol restart."""
    names=[name for name in ARCHITECTURES if bounds(name,lab.task) is not None]
    for name in names:lab.fit(name,24)
    while lab.remaining:
        best=lab.best()
        if best is None:break
        name=best['architecture'];before=len(lab.records);lab.fit(name,min(32,lab.remaining))
        if len(lab.records)==before or lab.remaining>24 and best['normalized_RMS_error']<1e-5:
            box=bounds(name,lab.task);index=len(lab.events)%8;z=qmc.Sobol(4,scramble=False).random_base2(3)[index];lab.fit(name,min(32,lab.remaining),(box[:,0]+(box[:,1]-box[:,0])*(.1+.8*z)).tolist())
        if len(lab.records)==before:break
    return {'actual_API_calls':0,'estimated_USD':0.,'billing_verified':False}
