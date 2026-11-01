"""Guided two-axial-spring linkage and convex series/parallel assemblies.

The two-bar/von-Mises geometry is established. Springs are ideal bilateral
linear axial elements with pins; no bar buckling/contact/material claims.
"""
import numpy as np

def primitive(a,H,k,b,u,orientation=-1,convex=True):
    """Energy [Nmm], drive force [N], drive tangent [N/mm]. u positive down."""
    q=orientation*H-np.asarray(u);rest=np.hypot(a,H);length=np.sqrt(a*a+q*q)
    critical=2*k*(rest/a-1) if orientation==1 and convex else 0.
    return_k=b+critical
    delta=length-rest;energy=k*delta**2+.5*return_k*np.asarray(u)**2
    force=-2*k*delta*q/length+return_k*np.asarray(u)
    tangent=2*k*(1-rest*a*a/length**3)+return_k
    return energy,force,tangent,{'q_mm':q,'length_mm':length,'rest_length_mm':rest,'link_travel_mm':abs(delta),'link_axial_force_N':abs(k*delta),'return_k_N_mm':return_k}

def vertex_oracle(stage,u):
    """Independent 3D endpoints, explicit link forces and spring work."""
    a,H,k,b=stage['a_mm'],stage['H_mm'],stage['k_N_mm'],stage['b_N_mm'];sign=stage['orientation'];rest=np.linalg.norm([a,H,0.]);apex=np.array([0.,sign*H-u,0.]);energy=0.;force=0.
    for x in [-a,a]:
        vector=apex-np.array([x,0.,0.]);length=np.linalg.norm(vector);extension=length-rest;energy+=.5*k*extension**2;force+=(-k*extension*vector/length)[1]
    return_k=b+(2*k*(rest/a-1) if sign==1 else 0.)
    return stage['count']*(energy+.5*return_k*u*u),stage['count']*(force+return_k*u)

def stage_jet(stage,u):
    e,f,h,detail=primitive(stage['a_mm'],stage['H_mm'],stage['k_N_mm'],stage['b_N_mm'],u,stage['orientation']);n=stage['count']
    return float(n*e),float(n*f),float(n*h),{k:float(v) for k,v in detail.items()}

def equilibrium(stages,total,previous=None):
    S=len(stages)
    if not S or not np.isfinite(total) or total<0:raise ValueError('Nonempty stages and finite nonnegative travel required')
    if any(s['b_N_mm']<=0 or s['k_N_mm']<=0 or s['a_mm']<=0 or s['H_mm']<=0 or s['count']<1 or s['orientation'] not in (-1,1) for s in stages):raise ValueError('Convex production stages require positive geometry/stiffness/count and orientation +/-1')
    if total==0:motions=np.zeros(S)
    elif S==1:motions=np.array([total])
    else:
        motions=np.full(S,total/S) if previous is None else np.asarray(previous)*total/max(sum(previous),1e-12)
        if np.min(motions)<=0:motions[:]=total/S
        for iteration in range(40):
            pieces=[stage_jet(s,u) for s,u in zip(stages,motions)];f=np.array([p[1] for p in pieces]);t=np.array([p[2] for p in pieces]);g=f[:-1]-f[-1]
            if max(abs(g))<1e-9:break
            h=np.diag(t[:-1])+t[-1]*np.ones((S-1,S-1));direction=np.linalg.solve(h,-g);full=np.r_[direction,-sum(direction)];old=sum(p[0] for p in pieces);accepted=False
            for step in [.5**i for i in range(18)]:
                trial=motions+step*full
                if min(trial)<=0 or max(trial)>=total:continue
                new=sum(stage_jet(s,u)[0] for s,u in zip(stages,trial))
                if new<=old+1e-4*step*np.dot(g,direction)+1e-14:motions=trial;accepted=True;break
            if not accepted:raise ValueError('Unresolved load-distribution line search')
        else:raise ValueError('Unresolved load-distribution iteration limit')
    pieces=[stage_jet(s,u) for s,u in zip(stages,motions)];forces=np.array([p[1] for p in pieces]);tangents=np.array([p[2] for p in pieces]);residual=float(np.ptp(forces)) if S>1 else 0.
    h=np.diag(tangents[:-1])+tangents[-1]*np.ones((S-1,S-1)) if S>1 else np.zeros((0,0));eigen=np.linalg.eigvalsh(h).tolist()
    if residual>1e-7 or (eigen and eigen[0]<=1e-8):raise ValueError('Not a verified stable internal equilibrium')
    return {'travel_mm':float(total),'stage_travels_mm':motions.tolist(),'energy_N_mm':sum(p[0] for p in pieces),'force_N':float(forces.mean()),'tangent_N_mm':float(1/sum(1/tangents)),'force_balance_residual_N':residual,'internal_hessian_eigenvalues_N_mm':eigen,'internal_dofs':S-1,'classification':'unique constrained internal minimum (strictly convex stage laws)' if S>1 else 'prescribed configuration; no internal DOFs','stage_details':[p[3] for p in pieces]}

def curve(stages,travels):
    points=[];previous=None
    for u in travels:
        point=equilibrium(stages,float(u),previous);points.append(point);previous=point['stage_travels_mm']
    return points

def audit(stages,points):
    checks=[]
    for point in points:
        U=point['travel_mm'];motions=point['stage_travels_mm'];parts=[vertex_oracle(s,u) for s,u in zip(stages,motions)];energy=sum(p[0] for p in parts);force=float(np.mean([p[1] for p in parts]));energy_error=abs(energy-point['energy_N_mm']);force_error=abs(force-point['force_N']);step=1e-4
        plus=equilibrium(stages,U+step,motions);minus=equilibrium(stages,U-step,motions) if U>step else None
        if minus:
            oracle_e=lambda p:sum(vertex_oracle(s,u)[0] for s,u in zip(stages,p['stage_travels_mm']));fd=(oracle_e(plus)-oracle_e(minus))/(2*step);fd_error=abs(fd-force)
        else:fd_error=None
        checks.append({'travel_mm':U,'vertex_energy_error_N_mm':energy_error,'vertex_force_error_N':force_error,'energy_derivative_force_error_N':fd_error,'passed':bool(energy_error<1e-8 and force_error<1e-8 and (fd_error is None or fd_error<2e-5))})
    return {'passed':all(c['passed'] for c in checks),'checks':checks,'scope':'Independent endpoint/axial-force oracle and re-equilibrated energy derivative; same ideal law, no hardware.'}
