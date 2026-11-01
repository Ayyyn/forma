"""Linear 2D rigid-jointed Euler-Bernoulli frames, N and mm.

Classical element formulation, independently implemented. See TU Delft's
computational-modelling beam chapter. Small strains/rotations; no contact,
joint compliance, shear deformation, plasticity or loaded buckling analysis.
"""
import numpy as np


def local_stiffness(E,A,I,L):
    a=E*A/L;b=12*E*I/L**3;c=6*E*I/L**2;d=4*E*I/L;e=2*E*I/L
    return np.array([[a,0,0,-a,0,0],[0,b,c,0,-b,c],[0,c,d,0,-c,e],
                     [-a,0,0,a,0,0],[0,-b,-c,0,b,-c],[0,c,e,0,-c,d]])


def element(x1,x2,E,depth,width):
    dx=np.asarray(x2)-x1;L=float(np.linalg.norm(dx));c,s=dx/L
    R=np.array([[c,s,0],[-s,c,0],[0,0,1.]])
    T=np.zeros((6,6));T[:3,:3]=R;T[3:,3:]=R
    A=depth*width;I=depth*width**3/12
    kl=local_stiffness(E,A,I,L)
    derivative=local_stiffness(E,depth,depth*width**2/4,L)
    return T.T@kl@T,T.T@derivative@T,T,kl,L


def solve_frame(nodes,edges,widths,clamped,output,E=2000.,depth=3.,sensitivities=True):
    nodes=np.asarray(nodes,dtype=float);edges=[tuple(x) for x in edges];widths=np.asarray(widths,dtype=float)
    if len(edges)!=len(widths) or np.any(widths<=0):raise ValueError('One positive in-plane width per edge required')
    active=sorted(set([output]+[int(v) for e in edges for v in e]))
    adjacency={n:set() for n in active}
    for i,j in edges:
        if i==j:raise ValueError('Zero-length edge')
        adjacency[i].add(j);adjacency[j].add(i)
    reached={output};queue=[output]
    while queue:
        for n in adjacency[queue.pop()]-reached:reached.add(n);queue.append(n)
    if reached!=set(active) or not reached.intersection(clamped):raise ValueError('Disconnected or unsupported structure')
    dofs=np.array([3*n+d for n in active for d in range(3) if n not in clamped],dtype=int)
    ndof=3*len(nodes);K=np.zeros((ndof,ndof));parts=[]
    for (i,j),w in zip(edges,widths):
        kg,dk,T,kl,L=element(nodes[i],nodes[j],E,depth,float(w))
        ed=np.r_[np.arange(3*i,3*i+3),np.arange(3*j,3*j+3)]
        K[np.ix_(ed,ed)]+=kg;parts.append((ed,dk,T,kl,L))
    F=np.zeros((ndof,2));F[3*output,0]=1.;F[3*output+1,1]=1.
    Kf=K[np.ix_(dofs,dofs)];eig=np.linalg.eigvalsh(Kf)
    if eig[0]<=max(eig[-1]*1e-13,1e-12):raise ValueError('Singular or ill-conditioned unloaded frame')
    U=np.zeros_like(F);U[dofs]=np.linalg.solve(Kf,F[dofs])
    C=F.T@U;gradient=[];stress=[];lengths=[]
    for (i,j),w,(ed,dk,T,kl,L) in zip(edges,widths,parts):
        ue=U[ed];gradient.append(-ue.T@dk@ue);lengths.append(L)
        end=kl@T@ue;A=depth*w;I=depth*w**3/12
        # Nominal member-end normal stress only; excludes joint concentrations.
        stress.append((np.abs(end[[0,3]])/A+np.abs(end[[2,5]])*(w/2)/I).max(axis=0).tolist())
    residual=K@U-F
    return {'compliance':C,'compliance_gradient':np.stack(gradient) if sensitivities else None,
            'volume_mm3':float(depth*np.dot(widths,lengths)),'volume_gradient':depth*np.asarray(lengths),
            'displacements_per_unit_load':U,'nominal_stress_per_unit_load':np.asarray(stress),
            'free_residual_inf':float(abs(residual[dofs]).max()),
            'unloaded_stiffness_condition':float(eig[-1]/eig[0]),
            'internal_strain_energy_per_unit_load':.5*np.sum(U*(K@U),axis=0),
            'support_reactions_per_unit_load':residual,'lengths_mm':np.asarray(lengths)}
