"""Independent element construction by Hermite strain-energy quadrature.

No production mechanics imports. Agreement verifies the same linear model;
it does not validate a material, joint, manufactured part or patient device.
"""
import numpy as np
from scipy.linalg import solve
from numpy.polynomial.legendre import leggauss


def energy_element(a,b,E,depth,width):
    delta=np.array(b)-a;length=np.sqrt(delta@delta);direction=delta/length
    # Direct maps from global node DOFs to local extension/transverse/rotation.
    Q=np.zeros((6,6))
    for shift in [0,3]:
        Q[shift,shift:shift+2]=direction
        Q[shift+1,shift:shift+2]=[-direction[1],direction[0]]
        Q[shift+2,shift+2]=1
    strain=np.array([-1,0,0,1,0,0])/length
    K=E*depth*width*length*np.outer(strain,strain)
    x,w=leggauss(3)
    for t,weight in zip((x+1)/2,w*length/2):
        curvature=np.array([0,(-6+12*t)/length**2,(-4+6*t)/length,
                            0,(6-12*t)/length**2,(-2+6*t)/length])
        K+=weight*E*depth*width**3/12*np.outer(curvature,curvature)
    return Q.T@K@Q


def oracle_solve(nodes,edges,widths,clamped,output,E=2000.,depth=3.):
    n=3*len(nodes);matrix=np.zeros((n,n));active=set()
    for (a,b),width in zip(edges,widths):
        active.update([a,b]);d=[3*v+j for v in [a,b] for j in [0,1,2]]
        piece=energy_element(nodes[a],nodes[b],E,depth,width)
        for i,row in enumerate(d):
            for j,col in enumerate(d):matrix[row,col]+=piece[i,j]
    free=[3*v+j for v in sorted(active) if v not in clamped for j in [0,1,2]]
    loading=np.zeros((n,2));loading[3*output,0]=1;loading[3*output+1,1]=1
    displacement=np.zeros_like(loading)
    displacement[free]=solve(matrix[np.ix_(free,free)],loading[free],assume_a='pos')
    return loading.T@displacement
