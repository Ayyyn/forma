"""Directed minimum finding, admissible escape paths and sampled tolerances.

No new constitutive physics: retains the old ideal guided nonlinear cell model.
Escape energies are sampled path heights, never certified retention bounds.
Tolerance continuation tests persistence, not exhaustive robustness.
"""
from copy import deepcopy
import json
import numpy as np
from scipy.optimize import root
from nonlinear_discovery import model as old


def polish(d,x,setting):
    try:
        sol=root(lambda q:old.jet(d,q,setting)[1],x,jac=lambda q:old.jet(d,q,setting)[2],options={'xtol':1e-10,'maxfev':120})
        r=old.record(d,sol.x,setting)
        if r['gradient_residual_normalized']>1e-7:return None
        return r
    except (ValueError,FloatingPointError,OverflowError,np.linalg.LinAlgError):return None


def descend(d,x,setting,maximum=100):
    """Energy-decreasing numerical minimization, not physical time dynamics."""
    x=np.array(x,float);path=[]
    def finish(r):
        if not r or r['classification']!='minimum' or np.linalg.norm(np.array(r['x'])-x)>1e-3:return {'converged':False,'path':path,'reason':'unresolved_endpoint'}
        endpoint=np.array(r['x']);last=path[-1]['energy_N_mm'] if path else float('inf')
        for fraction in np.linspace(0,1,17):
            q=(1-fraction)*x+fraction*endpoint
            try:e=old.jet(d,q,setting)[0]*old.SCALE
            except (ValueError,FloatingPointError):return {'converged':False,'path':path,'reason':'endpoint_domain'}
            if e>last+1e-8:return {'converged':False,'path':path,'reason':'endpoint_energy_jump'}
            path.append({'x':q.tolist(),'energy_N_mm':e});last=e
        return {'converged':True,'minimum':r,'path':path}
    for iteration in range(maximum):
        try:f,g,h=old.jet(d,x,setting)
        except (ValueError,FloatingPointError):return {'converged':False,'path':path,'reason':'domain'}
        path.append({'x':x.tolist(),'energy_N_mm':f*old.SCALE});eig,V=np.linalg.eigh((h+h.T)/2)
        if abs(g).max()<1e-8 and eig[0]>1e-7:
            r=polish(d,x,setting)
            return finish(r)
        H=(V*np.maximum(abs(eig),.02))@V.T;direction=-np.linalg.solve(H,g)
        norm=np.linalg.norm(direction)
        if norm>.12:direction*=.12/norm
        if np.linalg.norm(direction)<1e-12:break
        accepted=False
        for step in [.5**j for j in range(16)]:
            trial=x+step*direction
            try:new=old.jet(d,trial,setting)[0]
            except (ValueError,FloatingPointError):continue
            if new<=f+1e-4*step*np.dot(g,direction):x=trial;accepted=True;break
        if not accepted:break
    r=polish(d,x,setting)
    if r and r['classification']=='minimum':return finish(r)
    return {'converged':False,'path':path,'reason':'iteration_or_line_search_limit'}


def state_search(d,setting,starts=24,directed_limit=12):
    result=old.equilibria(d,setting,starts);states=list(result['states']);attempts=0;connections=[]
    saddles=[s for s in states if sum(e<-1e-7 for e in s['hessian_eigenvalues_normalized'])==1]
    for saddle in sorted(saddles,key=lambda s:s['energy_N_mm'])[:directed_limit]:
        x=np.array(saddle['x']);_,g,h=old.jet(d,x,setting);eig,V=np.linalg.eigh(h);direction=V[:,0];branches=[]
        for sign in [-1,1]:
            start=x+sign*.005*direction;branch=descend(d,start,setting);attempts+=1
            branch['initial_sign']=sign
            if branch.get('converged'):
                r=branch['minimum']
                if not any(np.linalg.norm(np.array(s['x'])-r['x'])<1e-4 for s in states):states.append(r)
            branches.append(branch)
        if all(b.get('converged') for b in branches):
            a,b=[v['minimum'] for v in branches]
            distinct=np.linalg.norm(np.array(a['x'])-b['x'])>1e-3
            # Verify the short segments attaching the saddle to each descent.
            segment_max=saddle['energy_N_mm'];segment_valid=True
            for sign in [-1,1]:
                for fraction in np.linspace(0,1,17):
                    try:segment_max=max(segment_max,old.jet(d,x+fraction*sign*.005*direction,setting)[0]*old.SCALE)
                    except (ValueError,FloatingPointError):segment_valid=False
            maximum=max([segment_max]+[p['energy_N_mm'] for branch in branches for p in branch['path']])
            connections.append({'saddle':saddle,'branches':branches,'distinct_endpoints':bool(distinct),'segments_in_domain':segment_valid,
                                'path_maximum_energy_N_mm':maximum,'path_is_energy_monotone_away_from_saddle':all(all(v['energy_N_mm']<=u['energy_N_mm']+1e-9 for u,v in zip(branch['path'],branch['path'][1:])) for branch in branches),
                                'scope':'Maximum sampled energy along a constructed path in six constrained model coordinates. Not a certified continuous barrier bound, minimum-energy path, or physical switching dynamics.'})
    result.update(states=sorted(states,key=lambda s:s['energy_N_mm']),directed_minimizations=attempts,connections=connections)
    return result


def summarize(d,settings):
    details={};penalty=0.;gaps=[];maxforce=0.;maxtorque=0.;mineig=1.
    for setting,sign in [('A',1),('B',-1)]:
        minima=[s for s in settings[setting]['states'] if s['classification']=='minimum'];target=[s for s in minima if sign*s['polarization']>=.35];counter=[s for s in minima if sign*s['polarization']<=-.35];other=[s for s in minima if sign*s['polarization']<.35]
        if not target or not counter:details[setting]={'states_found':len(minima),'target_and_counter_found':False};penalty+=10.;continue
        a=min(target,key=lambda s:s['energy_N_mm']);b=min(counter,key=lambda s:s['energy_N_mm']);competitor=min(other,key=lambda s:s['energy_N_mm']);gap=competitor['energy_N_mm']-a['energy_N_mm'];gaps.append(gap)
        force=max(abs(s['holding_axial_force_N']) for s in [a,b]);torque=max(abs(s['holding_torque_N_mm']) for s in [a,b]);eig=min(s['hessian_eigenvalues_normalized'][0] for s in [a,b]);maxforce=max(maxforce,force);maxtorque=max(maxtorque,torque);mineig=min(mineig,eig)
        upper=[]
        for link in settings[setting].get('connections',[]):
            if not link['distinct_endpoints'] or not link['segments_in_domain'] or not link['path_is_energy_monotone_away_from_saddle']:continue
            for end in link['branches']:
                for label,s in [('target',a),('counter',b)]:
                    if np.linalg.norm(np.array(end['minimum']['x'])-s['x'])<1e-3:upper.append({'mode':label,'sampled_escape_path_height_N_mm':link['path_maximum_energy_N_mm']-s['energy_N_mm']})
        low=min([p['sampled_escape_path_height_N_mm'] for p in upper],default=None)
        covered=all(any(p['mode']==label for p in upper) for label in ['target','counter'])
        penalty+=max(0.,(.5-gap)/.5)+max(0.,(force-1.5)/1.5)+max(0.,(torque-5.)/5.)+max(0.,(2e-4-eig)/2e-4)
        if low is not None:penalty+=max(0.,(.5-low)/.5)
        if not covered:penalty+=1.
        details[setting]={'minimum_count_found':len(minima),'target_and_counter_found':True,'target':a,'counter':b,'competitor':competitor,'energy_bias_N_mm':gap,'identified_sampled_escape_paths':upper,'minimum_sampled_escape_path_height_N_mm':low,'selected_modes_have_constructed_paths':covered}
    # Missing paths do not certify retention. They are explicitly unresolved.
    return {'passes_nominal_screen':penalty<=1e-6,'violation':penalty,'worst_bias_N_mm':min(gaps) if len(gaps)==2 else None,
            'max_axial_force_N':maxforce,'max_holding_torque_N_mm':maxtorque,'min_hessian_eigenvalue':mineig,
            'details':details,'scope':'Both selected modes must have constructed paths; no found competing state or sampled low-energy escape violates the screen. Global retention remains unresolved; passing is not certification.'}


def tolerance_check(d,nominal,trials=8):
    rng=np.random.default_rng(10302026);out=[]
    for trial in range(trials):
        perturbed=deepcopy(d)
        for c in perturbed['cells']:c['h0_mm']*=1+rng.uniform(-.01,.01);c['theta0_deg']+=rng.uniform(-.25,.25)
        for i,s in enumerate(perturbed['springs']):
            s['k']*=1+rng.uniform(-.05,.05)
            for key in ['offset_A','offset_B'] if i==0 else ['offset']:s[key]+=rng.uniform(-.25,.25) if s['type']=='axial' else rng.uniform(-.01,.01)
        modes=[]
        for setting in ['A','B']:
            detail=nominal['details'].get(setting,{})
            for label in ['target','counter']:
                previous=detail.get(label);state=polish(perturbed,np.array(previous['x']),setting) if previous else None
                passes=bool(state and state['classification']=='minimum' and abs(state['holding_axial_force_N'])<=1.5 and abs(state['holding_torque_N_mm'])<=5. and state['hessian_eigenvalues_normalized'][0]>=2e-4)
                if state and previous:passes=passes and np.linalg.norm(np.array(state['x'])-previous['x'])<.25 and (1 if label=='target' else -1)*(1 if setting=='A' else -1)*state['polarization']>=.35
                modes.append({'setting':setting,'role':label,'passed':bool(passes),'state':state})
        out.append({'trial':trial,'perturbed_design':perturbed,'modes':modes,'passed':all(m['passed'] for m in modes)})
    return {'trials':out,'passed_trials':sum(r['passed'] for r in out),'total_trials':trials,
            'scope':'Fixed seeded tolerance samples and local continuation of four nominal modes only. No new global state enumeration, escape/retention certification, or manufactured-part validation. Nominal design bounds are proposal ranges; uncertainty may extend beyond them.'}


def evaluate(d,starts=24,tolerances=False):
    old.validate(d);settings={k:state_search(d,k,starts) for k in ['A','B']};summary=summarize(d,settings)
    out={'design':d,'settings':settings,'summary':summary}
    if tolerances and all(summary['details'].get(k,{}).get('target_and_counter_found') for k in ['A','B']):out['tolerance']=tolerance_check(d,summary)
    return out
