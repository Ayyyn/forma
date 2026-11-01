"""Torque-free Kresling response from the unchanged published cell model.

Parallel units require independent ideal rotational bearings. Search is sampled
in the declared twist sector; no global root-completeness theorem is claimed.
"""
from functools import lru_cache
import numpy as np
from scipy.optimize import brentq
from kresling_proof.model import Cell,energy,jet
from kresling_proof.oracle import vertex_energy

@lru_cache(maxsize=8192)
def point(radius,height_ratio,travel,scan=49):
    c=Cell(r_mm=radius,h0_mm=radius*height_ratio)
    if c.h0_mm-travel<=2.:raise ValueError('Kresling ring-separation bound')
    lo=-.04;hi=c.phi_max-.0001;angles=np.linspace(lo,hi,scan);values=energy(c,travel,angles);roots=[]
    for i in range(1,len(angles)-1):
        if values[i]<=values[i-1] and values[i]<=values[i+1]:
            a,b=angles[i-1],angles[i+1]
            try:
                phi=brentq(lambda p:jet(c,travel,p)[1][1],a,b,xtol=1e-11);value,g,h=jet(c,travel,phi)
                if h[1,1]>1e-6 and not any(abs(phi-r['phi_rad'])<1e-6 for r in roots):roots.append({'phi_rad':float(phi),'energy_N_mm':value,'force_N':float(g[0]),'tangent_N_mm':float(h[0,0]-h[0,1]**2/h[1,1]),'torque_residual_N_mm':float(abs(g[1])),'twist_hessian_N_mm':float(h[1,1])})
            except ValueError:continue
    if len(roots)!=1:raise ValueError('Kresling twist minima absent or ambiguous in sampled sector')
    p=roots[0]
    if min(values[0],values[-1])<p['energy_N_mm']-1e-7:raise ValueError('Kresling interior minimum loses to sector boundary')
    return p

def curve(design,travels,scan=49):
    r,h,scale,background=design['parameters'];n=design['parallel_count'];out=[]
    for u in travels:
        p=point(float(r),float(h),float(u),scan);out.append({'travel_mm':float(u),'energy_N_mm':n*(scale*p['energy_N_mm']+.5*background*u*u),'force_N':n*(scale*p['force_N']+background*u),'tangent_N_mm':n*(scale*p['tangent_N_mm']+background),'phi_rad':p['phi_rad'],'force_balance_residual_N':0.,'internal_hessian_eigenvalues_N_mm':[scale*p['twist_hessian_N_mm']]*n,'torque_residual_N_mm':scale*p['torque_residual_N_mm'],'internal_dofs':n,'classification':'sampled torque-free local minima under imposed axial travel; no root-completeness proof'})
    return out

def audit(design,points):
    r,h,scale,background=design['parameters'];n=design['parallel_count'];c=Cell(r_mm=r,h0_mm=r*h);checks=[]
    for p in points:
        u=p['travel_mm'];phi=p['phi_rad'];f=lambda x:vertex_energy(c.to_dict(),x,phi);step=1e-4;E=n*(scale*f(u)+.5*background*u*u);force=n*(scale*(f(u+step)-f(u-step))/(2*step)+background*u);checks.append({'travel_mm':u,'vertex_energy_error_N_mm':abs(E-p['energy_N_mm']),'vertex_force_error_N':abs(force-p['force_N']),'passed':bool(abs(E-p['energy_N_mm'])<1e-7 and abs(force-p['force_N'])<2e-5)})
    return {'passed':all(c['passed'] for c in checks),'checks':checks,'scope':'Independent published ring-vertex energy; fixed-twist partial derivative at zero-torque stationary states. No hardware validation.'}
