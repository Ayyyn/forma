"""Small-displacement 3D Euler--Bernoulli frames, N/mm/radian.

Six DOFs per node: ux,uy,uz,rx,ry,rz. Circular sections; rigid joints.
No shear deformation, geometric stiffness, contact or active material law.
Classical direct-stiffness formulation, implemented independently here.
"""
import numpy as np
from scipy.linalg import cho_factor, cho_solve


def section(radius):
    return np.pi*radius**2, np.pi*radius**4/4, np.pi*radius**4/2


def local_matrix(E,G,A,Iy,Iz,J,L):
    K=np.zeros((12,12))
    for ids,value in [([0,6],E*A/L),([3,9],G*J/L)]:
        K[np.ix_(ids,ids)]+=value*np.array([[1.,-1.],[-1.,1.]])
    for ids,I,sign in [([1,5,7,11],Iz,1.),([2,4,8,10],Iy,-1.)]:
        block=E*I/L**3*np.array([[12,6*L,-12,6*L],[6*L,4*L**2,-6*L,2*L**2],
                                [-12,-6*L,12,-6*L],[6*L,2*L**2,-6*L,4*L**2]])
        S=np.diag([1.,sign,1.,sign]);K[np.ix_(ids,ids)]+=S@block@S
    return K


def element(a,b,radius,E,G):
    delta=np.asarray(b,dtype=float)-a;L=float(np.linalg.norm(delta))
    if L<=1e-10:raise ValueError('Zero-length member')
    x=delta/L;ref=np.eye(3)[np.argmin(abs(x))]
    y=ref-x*np.dot(x,ref);y/=np.linalg.norm(y);z=np.cross(x,y)
    R=np.array([x,y,z]);T=np.kron(np.eye(4),R)
    A,I,J=section(radius);kl=local_matrix(E,G,A,I,I,J,L)
    derivative=local_matrix(E,G,2*A/radius,4*I/radius,4*I/radius,4*J/radius,L)
    return T.T@kl@T,T.T@derivative@T,T,kl,L


def solve(nodes,edges,radii,clamped,loads,E=2000.,nu=.3,springs=(),sensitivities=False):
    nodes=np.asarray(nodes,dtype=float);radii=np.asarray(radii,dtype=float)
    if nodes.ndim!=2 or nodes.shape[1]!=3 or not np.isfinite(nodes).all():raise ValueError('Finite Nx3 nodes required')
    if len(edges)!=len(radii) or not len(edges) or not np.isfinite(radii).all() or np.any(radii<=0):raise ValueError('Positive radius per member required')
    if not np.isfinite(E) or E<=0 or not -1<nu<.5:raise ValueError('Invalid elastic coefficients')
    n=6*len(nodes);F=np.array(loads,dtype=float)
    if F.ndim==1:F=F[:,None]
    if F.shape[0]!=n or not np.isfinite(F).all():raise ValueError('Finite loads with six DOFs per node required')
    edge_set=set();active=set();adj={}
    for a,b in edges:
        if type(a) is not int or type(b) is not int or not 0<=a<len(nodes) or not 0<=b<len(nodes) or a==b:raise ValueError('Invalid member nodes')
        key=tuple(sorted((a,b)))
        if key in edge_set:raise ValueError('Duplicate member')
        edge_set.add(key);active.update([a,b]);adj.setdefault(a,set()).add(b);adj.setdefault(b,set()).add(a)
    if any(type(v) is not int or not 0<=v<len(nodes) for v in clamped):raise ValueError('Invalid clamp')
    reached=set(active.intersection(clamped));queue=list(reached)
    while queue:
        for v in adj[queue.pop()]-reached:reached.add(v);queue.append(v)
    if reached!=active:raise ValueError('Unsupported connected component')
    if any(np.any(F[6*v:6*v+6]) for v in set(range(len(nodes)))-active):raise ValueError('Load at inactive node')
    K=np.zeros((n,n));parts=[];G=E/(2*(1+nu))
    for (a,b),r in zip(edges,radii):
        kg,dk,T,kl,L=element(nodes[a],nodes[b],r,E,G)
        dofs=np.r_[np.arange(6*a,6*a+6),np.arange(6*b,6*b+6)]
        K[np.ix_(dofs,dofs)]+=kg;parts.append((dofs,dk,T,kl,L))
    Kbeam=K.copy()
    for dof,k in springs:
        if type(dof) is not int or not 0<=dof<n or dof//6 not in active or not np.isfinite(k) or k<0:raise ValueError('Invalid grounded spring')
        K[dof,dof]+=k
    free=np.array([6*v+j for v in sorted(active) if v not in clamped for j in range(6)],dtype=int)
    if not len(free):raise ValueError('No free DOFs')
    Kf=K[np.ix_(free,free)]
    # Equilibrate mixed translation/rotation units before the numerical SPD gate.
    scaling=1/np.sqrt(np.diag(Kf));scaled=scaling[:,None]*Kf*scaling[None,:]
    ev=np.linalg.eigvalsh(scaled)
    if ev[0]<=max(1e-13*ev[-1],1e-14):raise ValueError('Singular or ill-conditioned unloaded stiffness')
    factor=cho_factor(scaled)
    def inverse(rhs):return scaling[:,None]*cho_solve(factor,scaling[:,None]*rhs)
    U=np.zeros_like(F);U[free]=inverse(F[free]);grad=[];end_forces=[]
    for dofs,dk,T,kl,L in parts:
        end_forces.append(kl@T@U[dofs])
        if sensitivities:
            rhs=np.zeros_like(F);rhs[dofs]=-dk@U[dofs]
            dU=np.zeros_like(F);dU[free]=inverse(rhs[free]);grad.append(dU)
    residual=K@U-F
    return {'u':U,'du_dr':np.array(grad) if sensitivities else None,'K':K,'Kbeam':Kbeam,
            'end_forces':np.array(end_forces),'lengths':np.array([p[-1] for p in parts]),
            'volume':float(sum(np.pi*r*r*p[-1] for r,p in zip(radii,parts))),
            'dvolume_dr':np.array([2*np.pi*r*p[-1] for r,p in zip(radii,parts)]),
            'free_residual_inf':float(abs(residual[free]).max()),'reactions':residual,
            'scaled_unloaded_condition':float(ev[-1]/ev[0]),'parts':parts,
            'beam_energy':.5*np.sum(U*(Kbeam@U),axis=0),
            'spring_energy':.5*np.sum(U*((K-Kbeam)@U),axis=0),
            'input_ramp_work':.5*np.sum(F*U,axis=0)}
