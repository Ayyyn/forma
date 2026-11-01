"""Published fixtures and independent checks; never fit parameters to outcomes."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar
from .model import Cell,AxialSpring,features,energy,scaled_jet,jet
from .oracle import vertex_features,vertex_energy,high_precision_jet
from .statics import equilibria,relax_phi

REFERENCES=Path(__file__).resolve().parent/'references'


def reference_checks(cell,solved):
    fixture=json.loads((REFERENCES/'checkpoints.json').read_text(encoding='utf-8'))
    curve_ref=json.loads((REFERENCES/'figure5a_kr005.json').read_text(encoding='utf-8'))
    checks=[]
    def check(name,actual,expected,tolerance):
        checks.append({'name':name,'actual':float(actual),'reference':float(expected),'absolute_error':float(abs(actual-expected)),
                       'tolerance':tolerance,'passed':bool(abs(actual-expected)<=tolerance)})
    phi=relax_phi(cell,10.)['phi_deg']
    u=minimize_scalar(lambda u:float(energy(cell,u,math.radians(20))),bounds=(0,cell.h0_mm-1e-5),
                      method='bounded',options={'xatol':1e-12}).x
    check('Appendix A.3: phi at u=10 mm',phi,28.65,.1)
    check('Appendix A.3: u at phi=20 deg',u,6.33,.1)
    for expected in fixture['stationary']:
        matches=[s for s in solved['states'] if s['classification']==expected['classification']]
        if not matches:
            checks.append({'name':'Published '+expected['classification'],'passed':False,'reason':'No matching classification'})
            continue
        match=min(matches,key=lambda s:abs(s['u_mm']-expected['u_mm']))
        check('Stationary u near '+str(expected['u_mm']),match['u_mm'],expected['u_mm'],expected['tolerance_u_mm'])
        check('Stationary phi near '+str(expected['phi_deg']),match['phi_deg'],expected['phi_deg'],expected['tolerance_phi_deg'])
    second=[s for s in solved['states'] if s['classification']=='minimum' and s['u_mm']>1]
    if second:check('Table 1: second minimum U/(ks*r)',second[0]['energy_normalized'],.0041,.0002)
    ref_values=[];pred_values=[];rows=[]
    for item in curve_ref['samples']:
        prediction=relax_phi(cell,item['u_over_r']*cell.r_mm)['energy_normalized']
        ref_values.append(item['U_over_ks_r']);pred_values.append(prediction)
        rows.append({**item,'computed_U_over_ks_r':prediction,'residual':prediction-item['U_over_ks_r']})
    rmse=float(np.sqrt(np.mean((np.array(pred_values)-ref_values)**2)))
    nrmse=rmse/.014
    checks.append({'name':'Figure 5A source curve','sample_count':len(rows),'rmse_normalized_energy':rmse,
                   'nrmse_full_vertical_range':nrmse,'tolerance':.02,'passed':nrmse<=.02,
                   'source_reading_uncertainty':curve_ref['estimated_reading_uncertainty_U_over_ks_r']})
    return {'passed':all(c['passed'] for c in checks),'checks':checks,'curve_comparison':rows,
            'reference_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in REFERENCES.glob('*.json')}}


def independent_checks(cell,count=80):
    rng=np.random.default_rng(20261028);geometry_errors=[];energy_errors=[]
    for _ in range(count):
        u=rng.uniform(-.05*cell.h0_mm,.93*cell.h0_mm)
        phi=rng.uniform(-.15*cell.theta0,.96*cell.phi_max)
        f=features(cell,u,phi);other=vertex_features(cell.to_dict(),u,phi)
        geometry_errors.append(float(np.max(np.abs(f-other)/np.array([cell.r_mm,cell.r_mm,1,1,1]))))
        energy_errors.append(abs(float(energy(cell,u,phi))-vertex_energy(cell.to_dict(),u,phi))/cell.energy_scale)
    hp=[];step_study=[]
    for q in [[.1,.15],[.4,.55],[.9,.95],[1.15,.99]]:
        value,g,h=scaled_jet(cell,q)
        vo,go,ho=high_precision_jet(cell.to_dict(),q)
        hp.append({'q':q,'energy_absolute_error':abs(value-vo),'gradient_max_error':float(np.max(abs(g-go))),
                   'hessian_max_error':float(np.max(abs(h-ho)))})
        f=lambda x:float(energy(cell,x[0]*cell.r_mm,x[1])/cell.energy_scale)
        for step in [1e-3,1e-4,1e-5,1e-6]:
            estimate=[]
            for axis in range(2):
                d=np.eye(2)[axis]*step;x=np.array(q)
                estimate.append((-f(x+2*d)+8*f(x+d)-8*f(x-d)+f(x-2*d))/(12*step))
            step_study.append({'q':q,'step':step,'gradient_error_inf':float(np.max(np.abs(np.array(estimate)-g)))})
    passed=max(geometry_errors)<1e-10 and max(energy_errors)<1e-10 and all(
        x['energy_absolute_error']<1e-11 and x['gradient_max_error']<1e-9 and x['hessian_max_error']<1e-8 for x in hp)
    passed=passed and all(min(s['gradient_error_inf'] for s in step_study if s['q']==q)<1e-8 for q in [x['q'] for x in hp])
    return {'passed':bool(passed),'random_state_count':count,'seed':20261028,
            'max_scaled_vertex_geometry_error':max(geometry_errors),'max_normalized_vertex_energy_error':max(energy_errors),
            'high_precision_digits':70,'high_precision_comparisons':hp,'finite_difference_step_study':step_study,
            'scope':'independent numerical implementation of the same constitutive model, not material validation'}


def convergence_checks(cell):
    scans=[equilibria(cell,grid=n) for n in (5,7,9)]
    states=[s['states'] for s in scans]
    stable=all([x['classification'] for x in states[0]]==[x['classification'] for x in st] for st in states[1:])
    delta=0.
    if stable:
        for candidate in states[1:]:
            for a,b in zip(states[0],candidate):
                delta=max(delta,abs(a['u_mm']-b['u_mm'])/cell.r_mm,abs(a['phi_rad']-b['phi_rad']))
    else:delta=None
    angles=[]
    for n in (65,129,257,513):angles.append({'angular_samples':n,**relax_phi(cell,10.,samples=n)})
    angular_delta=max(abs(x['phi_rad']-angles[-1]['phi_rad']) for x in angles)
    return {'passed':bool(stable and delta is not None and delta<1e-4 and angular_delta<1e-4),
            'root_scan_grids':[5,7,9],'state_counts':[len(s) for s in states],
            'classifications_unchanged':stable,'max_scaled_stationary_discrepancy':delta,
            'angular_resolution_checks':angles,'max_angular_discrepancy_rad':angular_delta,
            'limitation':'finite multi-start agreement is evidence of convergence, not a proof of exhaustive equilibria'}
