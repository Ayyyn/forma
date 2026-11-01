"""Independent spatial strain-energy quadrature, no production imports.

For circular members an independently chosen transverse basis is equivalent.
Reconstructs axial/torsional strains and two Hermite curvatures in global DOFs.
"""
import numpy as np
from scipy.linalg import solve as linear_solve
from numpy.polynomial.legendre import leggauss


def stiffness(a,b,r,E,nu):
    tangent=np.asarray(b,dtype=float)-a;L=np.linalg.norm(tangent);tangent/=L
    # Different transverse orientation from the direct-stiffness implementation.
    seed=np.array([.371,.619,.899]);normal=np.cross(tangent,seed)
    if np.linalg.norm(normal)<.01:normal=np.cross(tangent,[1.,0.,0.])
    normal/=np.linalg.norm(normal);other=np.cross(tangent,normal)
    Q=np.zeros((12,12))
    for node in range(2):
        for block in range(2):
            j=6*node+3*block;Q[j:j+3,j:j+3]=np.vstack([tangent,normal,other])
    A=np.pi*r*r;I=np.pi*r**4/4;J=2*I;G=E/(2*(1+nu));K=np.zeros((12,12))
    axial=np.zeros(12);axial[[0,6]]=[-1/L,1/L]
    twist=np.zeros(12);twist[[3,9]]=[-1/L,1/L]
    K+=L*(E*A*np.outer(axial,axial)+G*J*np.outer(twist,twist))
    points,weights=leggauss(3)
    for t,w in zip((points+1)/2,weights*L/2):
        curve=np.array([(-6+12*t)/L**2,(-4+6*t)/L,(6-12*t)/L**2,(-2+6*t)/L])
        by=np.zeros(12);bz=np.zeros(12);by[[1,5,7,11]]=curve;bz[[2,4,8,10]]=curve*[1,-1,1,-1]
        K+=w*E*I*(np.outer(by,by)+np.outer(bz,bz))
    return Q.T@K@Q


def solve(nodes,edges,radii,clamped,loads,E=2000.,nu=.3,springs=()):
    n=6*len(nodes);K=np.zeros((n,n));active=set()
    for (a,b),r in zip(edges,radii):
        active.update([a,b]);d=[6*v+j for v in [a,b] for j in range(6)]
        piece=stiffness(nodes[a],nodes[b],r,E,nu)
        for i,row in enumerate(d):
            for j,col in enumerate(d):K[row,col]+=piece[i,j]
    for dof,k in springs:K[dof,dof]+=k
    free=[6*v+j for v in sorted(active) if v not in clamped for j in range(6)]
    F=np.asarray(loads,dtype=float)
    if F.ndim==1:F=F[:,None]
    U=np.zeros_like(F);U[free]=linear_solve(K[np.ix_(free,free)],F[free],assume_a='pos')
    return U
