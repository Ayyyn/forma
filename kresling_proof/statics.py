"""Bounded equilibrium search and explicitly displacement-controlled branches."""
import math
import numpy as np
from scipy.optimize import root, minimize_scalar, brentq
from .model import Cell, AxialSpring, energy, scaled_jet, jet


def state_record(cell,q,spring=AxialSpring(),residual_tolerance=1e-8):
    value,g,h=scaled_jet(cell,q,spring)
    eig=np.linalg.eigvalsh((h+h.T)/2)
    residual=float(np.max(np.abs(g)));tol=1e-7
    if residual>residual_tolerance:kind='not_equilibrium'
    elif eig[0]>tol:kind='minimum'
    elif eig[-1]<-tol:kind='maximum'
    elif eig[0]<-tol and eig[-1]>tol:kind='saddle'
    else:kind='degenerate'
    return {'u_mm':float(q[0]*cell.r_mm),'phi_rad':float(q[1]),'phi_deg':float(math.degrees(q[1])),
            'height_mm':float(cell.h0_mm-q[0]*cell.r_mm),'energy_N_mm':float(value*cell.energy_scale),
            'energy_normalized':float(value),'gradient_normalized':g.tolist(),'gradient_residual_inf':residual,
            'hessian_normalized':h.tolist(),'hessian_eigenvalues':eig.tolist(),'classification':kind,
            'in_published_loading_rectangle':bool(q[0]>=-1e-9 and q[1]>=-1e-9 and q[1]<=cell.phi_max+1e-9)}


def equilibria(cell,spring=AxialSpring(),grid=9):
    """Fixed multi-start stationary solve, not a claim of exhaustive root isolation.

    Expanded lower bounds permit small extensions/untwisting around the reference
    state instead of declaring a clamped boundary to be an unloaded minimum.
    """
    lower=np.array([-.25*cell.h0_mm/cell.r_mm,-.5*cell.theta0])
    upper=np.array([cell.h0_mm/cell.r_mm-1e-6,cell.phi_max])
    seeds=[np.array([u,p]) for u in np.linspace(lower[0],upper[0]*.98,grid)
           for p in np.linspace(lower[1],upper[1]*.98,grid)]
    seeds.append(np.array([0.,0.]))
    found=[];failures=0
    for seed in seeds:
        try:
            sol=root(lambda q:scaled_jet(cell,q,spring)[1],seed,
                     jac=lambda q:scaled_jet(cell,q,spring)[2],method='hybr',options={'xtol':1e-10})
            q=sol.x
            if np.any(q<lower-1e-9) or np.any(q>upper+1e-9):raise ValueError('Outside search bounds')
            record=state_record(cell,q,spring)
            if record['gradient_residual_inf']>1e-8:raise ValueError('Stationary residual failed')
            if any(np.linalg.norm(q-other)<1e-5 for other,_ in found):continue
            if min(np.min(q-lower),np.min(upper-q))<1e-5:
                record['classification']='search_boundary_unresolved'
            found.append((q,record))
        except (ValueError,FloatingPointError,OverflowError,ZeroDivisionError):failures+=1
    found.sort(key=lambda item:item[1]['u_mm'])
    return {'states':[r for _,r in found],'search':{'method':'fixed multi-start root / automatic Jacobian',
            'grid':grid,'attempts':len(seeds),'failed_attempts':failures,'bounds_q':[lower.tolist(),upper.tolist()],
            'exhaustive':False,'near_zero_hessian_threshold':1e-7}}


def relax_phi(cell,u_mm,spring=AxialSpring(),samples=257):
    """Find all sampled angular wells, refine them, compare with both boundaries."""
    phis=np.linspace(0,cell.phi_max,samples)
    values=energy(cell,u_mm,phis,spring)
    options=[(float(values[0]),float(phis[0]),'angular_boundary'),
             (float(values[-1]),float(phis[-1]),'angular_boundary')]
    # A well can lie between an endpoint and the first grid sample. Comparing
    # sampled energies alone misses it, even though the endpoint torque is not
    # zero. Always check those two edge intervals as well as sampled wells.
    intervals=[(phis[0],phis[1]),(phis[-2],phis[-1])]
    intervals.extend((phis[i-1],phis[i+1]) for i in range(1,samples-1)
                     if values[i]<=values[i-1] and values[i]<=values[i+1])
    for a,b in intervals:
        derivative=lambda p:jet(cell,u_mm,p,spring)[1][1]
        try:
            if derivative(a)*derivative(b)<=0:
                p=brentq(derivative,a,b,xtol=1e-13)
            else:
                continue
            if jet(cell,u_mm,p,spring)[2][1,1]<=0:continue
            options.append((float(energy(cell,u_mm,p,spring)),float(p),'transverse_minimum'))
        except (ValueError,FloatingPointError):continue
    value,p,kind=min(options,key=lambda item:item[0])
    _,g,h=jet(cell,u_mm,p,spring)
    return {'u_mm':float(u_mm),'phi_rad':p,'phi_deg':math.degrees(p),'energy_N_mm':value,
            'energy_normalized':value/cell.energy_scale,'force_N':float(g[0]),'torque_N_mm':float(g[1]),
            'transverse_curvature':float(h[1,1]),'kind':kind}


def axial_curve(cell,spring=AxialSpring(),samples=401):
    # Exact h=0 is a geometric boundary and is excluded from interior derivatives.
    return [relax_phi(cell,float(u),spring) for u in np.linspace(0,cell.h0_mm-1e-5*cell.r_mm,samples)]


def branch_barrier(cell,states,spring=AxialSpring()):
    minima=sorted((s for s in states if s['classification']=='minimum'),key=lambda s:s['u_mm'])
    saddles=[s for s in states if s['classification']=='saddle']
    if len(minima)!=2:return {'status':'unresolved','reason':'Exactly two interior minima were not found'}
    left,right=minima
    eligible=[s for s in saddles if left['u_mm']<s['u_mm']<right['u_mm']]
    if len(eligible)!=1:return {'status':'unresolved','reason':'A unique intermediate saddle was not found'}
    saddle=eligible[0]
    points=[relax_phi(cell,float(u),spring) for u in np.linspace(left['u_mm'],right['u_mm'],101)]
    if any(p['kind']!='transverse_minimum' and abs(p['torque_N_mm'])>1e-6 for p in points):
        return {'status':'unresolved','reason':'A branch reaches a non-torque-free angular boundary'}
    if max(abs(b['phi_rad']-a['phi_rad']) for a,b in zip(points,points[1:]))>.08:
        return {'status':'unresolved','reason':'Disconnected lower-envelope branch detected'}
    for state in [left,saddle,right]:
        p=relax_phi(cell,state['u_mm'],spring)
        if abs(p['phi_rad']-state['phi_rad'])>1e-5:
            return {'status':'unresolved','reason':'Stationary point is not on the tested transverse-minimum branch'}
    return {'status':'resolved_on_declared_branch','protocol':'monotonic axial displacement with free rotation',
            'scope':'branch barrier only; not a globally minimized transition barrier or dynamic switching threshold',
            'forward_N_mm':saddle['energy_N_mm']-left['energy_N_mm'],
            'reverse_N_mm':saddle['energy_N_mm']-right['energy_N_mm'],
            'saddle':saddle,'left_minimum':left,'right_minimum':right}
