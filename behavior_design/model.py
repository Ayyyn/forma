"""Public architecture grammar and fixed behavior-task evaluator."""
from copy import deepcopy
import numpy as np
from . import linkage,kresling

ARCHITECTURES={
 'single_hardening':dict(counts=[1],orientations=[-1],a=[1],h=[1],k=[1],b=[1]),
 'parallel_hardening':dict(counts=[2],orientations=[-1],a=[1],h=[1],k=[1],b=[1]),
 'series_hardening':dict(counts=[1,1],orientations=[-1,-1],a=[1,1],h=[1,1],k=[1,1],b=[1,1]),
 'graded_series_parallel':dict(counts=[2,1],orientations=[-1,-1],a=[1,1.2],h=[1,.6],k=[1,1.8],b=[1,1]),
 'consolidated_graded_series':dict(counts=[1,1],orientations=[-1,-1],a=[1,1.2],h=[1,.6],k=[2,1.8],b=[2,1]),
 'softening_hardening_stack':dict(counts=[1,1,1],orientations=[-1,1,-1],a=[.8,1,1.1],h=[.7,1,.8],k=[1,1,1],b=[1,1,1]),
 'kresling_parallel_1':dict(family='kresling',parallel_count=1),
 'kresling_parallel_2':dict(family='kresling',parallel_count=2),
}

def bounds(name,task):
    a=ARCHITECTURES[name];width=task['maximum_width_mm'];height=task['maximum_height_mm'];stroke=task['stroke_mm']
    if a.get('family')=='kresling':
        n=a['parallel_count'];rmax=min(30.,(width-4*(n-1))/(2*n),(height-4)/1.45)
        if rmax<14:return None
        return np.array([[14.,rmax],[1.15,1.45],[.2,3.],[0.,.6]])
    S=len(a['counts']);amax=min([28.]+[(width-4*(n-1))/(2*n*factor) for n,factor in zip(a['counts'],a['a'])]);hmax=min(10.,.55*12*min(x/y for x,y in zip(a['a'],a['h'])),(height-stroke-2*(S+1))/sum(a['h']))
    if amax<12 or hmax<1.5:return None
    return np.array([[12.,amax],[1.5,hmax],[.15,6/max(a['k'])],[.005,.25/max(a['b'])]])

def design(name,parameters):
    if name not in ARCHITECTURES:raise ValueError('Unknown architecture')
    x=np.asarray(parameters,float)
    if x.shape!=(4,) or not np.isfinite(x).all():raise ValueError('Four finite parameters required')
    a=ARCHITECTURES[name];out={'architecture':name,'parameters':x.tolist(),'family':a.get('family','linkage')}
    if out['family']=='kresling':out['parallel_count']=a['parallel_count']
    else:
        out['stages']=[{'count':n,'orientation':o,'a_mm':float(x[0]*af),'H_mm':float(x[1]*hf),'k_N_mm':float(x[2]*kf),'b_N_mm':float(x[3]*bf)} for n,o,af,hf,kf,bf in zip(a['counts'],a['orientations'],a['a'],a['h'],a['k'],a['b'])]
    return out

def geometry_budget(d,task):
    if d['family']=='kresling':
        r,h,_,_=d['parameters'];n=d['parallel_count'];return {'width_mm':2*r*n+4*(n-1),'height_mm':r*h+4,'module_count':n,'stages':1,'scope':'Zero-thickness rings/facets plus reserved 2mm plate allowances; independent ideal rotational bearings, hardware/contact unmodeled.'}
    stages=d['stages'];return {'width_mm':max(2*s['a_mm']*s['count']+4*(s['count']-1) for s in stages),'height_mm':sum(s['H_mm'] for s in stages)+task['stroke_mm']+2*(len(stages)+1),'module_count':sum(s['count'] for s in stages),'stages':len(stages),'scope':'Ideal guided stages and translation-preserving couplers. Declared travel envelope and reserved 2mm plates, not a manufactured assembly or collision-certified CAD.'}

def predict(d,travels,dense=False):
    return kresling.curve(d,travels,scan=193 if dense else 49) if d['family']=='kresling' else linkage.curve(d['stages'],travels)

def evaluate(d,task,travels=None,dense=False):
    box=bounds(d['architecture'],task);x=np.array(d['parameters'])
    if box is None or np.any(x<box[:,0]-1e-8) or np.any(x>box[:,1]+1e-8):raise ValueError('Outside public architecture/task bounds')
    grid=np.array(task['fit_travel_mm'] if travels is None else travels);points=predict(d,grid,dense);force=np.array([p['force_N'] for p in points]);target=np.interp(grid,task['target_travel_mm'],task['target_force_N']);normalizer=max(task['target_force_N']);error=float(np.sqrt(np.mean((force-target)**2))/normalizer);maxerror=float(max(abs(force-target))/normalizer);pack=geometry_budget(d,task)
    margins={'width':1-pack['width_mm']/task['maximum_width_mm'],'height':1-pack['height_mm']/task['maximum_height_mm'],'minimum_tangent':min(p['tangent_N_mm'] for p in points)/task['minimum_tangent_N_mm']-1,'nonnegative_force':float(min(force)/normalizer)}
    if d['family']=='linkage':
        margins.update(link_travel=1-max(v['link_travel_mm'] for p in points for v in p['stage_details'])/task['maximum_link_travel_mm'],link_force=1-max(v['link_axial_force_N'] for p in points for v in p['stage_details'])/task['maximum_link_force_N'])
    feasible=all(v>=-1e-6 for v in margins.values());return {'design':deepcopy(d),'points':points,'normalized_RMS_error':error,'normalized_max_error':maxerror,'margins':margins,'mechanical_screen_passed':feasible,'target_passed':bool(feasible and error<=task['maximum_normalized_RMS_error'] and maxerror<=task['maximum_normalized_max_error']),'geometry_budget':pack,'physical_validation':False,'force_protocol':'Quasistatic displacement control. No dynamic deployment, hysteresis or retention prediction.'}

def independent_audit(d,points):return kresling.audit(d,points) if d['family']=='kresling' else linkage.audit(d['stages'],points)
