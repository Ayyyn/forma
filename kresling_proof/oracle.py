"""Independent ring-vertex/face-normal geometry. No production model imports.

The same published constitutive assumption is checked, not independently
validated as a description of a real material.
"""
import math
import numpy as np
import mpmath as mp


def vertex_features(parameters,u,phi):
    n=parameters['n'];r=parameters['r_mm'];h=parameters['h0_mm']-u
    theta=math.radians(parameters['theta0_deg'])+phi;alpha=2*math.pi/n
    B=lambda i:np.array([r*math.cos(i*alpha),r*math.sin(i*alpha),0.])
    A=lambda i:np.array([r*math.cos(i*alpha+theta),r*math.sin(i*alpha+theta),h])
    normal=lambda x,y,z:np.cross(y-x,z-x)
    angle=lambda a,b:math.atan2(np.linalg.norm(np.cross(a,b)),float(np.dot(a,b)))
    top=normal(B(0),A(0),A(1));bottom=normal(B(0),A(1),B(1))
    previous=normal(B(-1),A(0),B(0))
    if min(np.linalg.norm(v) for v in (top,bottom,previous))<1e-14:
        raise ValueError('Degenerate reference triangle')
    return np.array([np.linalg.norm(A(0)-B(0)),np.linalg.norm(A(1)-B(0)),
                     angle(top,np.array([0.,0.,1.])),math.pi-angle(top,previous),math.pi-angle(top,bottom)])


def vertex_energy(parameters,u,phi,spring=None):
    f=vertex_features(parameters,u,phi);f0=vertex_features(parameters,0.,0.)
    n=parameters['n'];r=parameters['r_mm'];ks=parameters['ks_N'];kr=parameters['kr_per_length']
    a0=np.linalg.norm(np.array([r,0])-np.array([r*math.cos(2*math.pi/n),r*math.sin(2*math.pi/n)]))
    k=np.array([n*ks/f0[0],n*ks/f0[1],2*n*kr*a0,n*kr*f0[0],n*kr*f0[1]])
    value=float(sum(.5*k*(f-f0)**2))
    if spring and spring['enabled']:value+=.5*spring['stiffness_N_per_mm']*(spring['offset_mm']-u)**2
    return value


def mp_energy(parameters,q0,q1,spring=None):
    """Arbitrary precision, unsimplified source equations, scalar dimensionless energy."""
    p={k:mp.mpf(str(v)) for k,v in parameters.items() if k!='n'}
    n=parameters['n'];r=p['r_mm'];H=p['h0_mm'];t=p['theta0_deg']*mp.pi/180;a=mp.pi/n
    def f(u,phi):
        h=H-u;theta=t+phi
        b=mp.sqrt(h*h+(2*r*mp.sin(theta/2))**2)
        c=mp.sqrt(h*h+(2*r*mp.sin(theta/2+a))**2)
        da=mp.atan(h/(2*r*mp.sin(theta/2+a)*mp.sin(theta/2)))
        e=(r*(mp.cos(theta+a)-mp.cos(a)))**2
        db=mp.pi-mp.acos((h*h*mp.cos(theta+2*a)-e)/(h*h+e))
        dc=mp.pi-mp.acos((h*h*mp.cos(theta)-e)/(h*h+e))
        return [b,c,da,db,dc]
    initial=f(0,0);now=f(q0*r,q1);ks=p['ks_N'];kr=p['kr_per_length']
    weights=[n*ks/initial[0],n*ks/initial[1],2*n*kr*2*r*mp.sin(a),n*kr*initial[0],n*kr*initial[1]]
    value=sum(w*(v-v0)**2/2 for w,v,v0 in zip(weights,now,initial))
    if spring and spring['enabled']:
        value+=mp.mpf(str(spring['stiffness_N_per_mm']))*(mp.mpf(str(spring['offset_mm']))-q0*r)**2/2
    return value/(ks*r)


def high_precision_jet(parameters,q,spring=None,dps=70):
    with mp.workdps(dps):
        at=tuple(mp.mpf(str(x)) for x in q)
        f=lambda a,b:mp_energy(parameters,a,b,spring)
        gradient=[mp.diff(f,at,(1,0)),mp.diff(f,at,(0,1))]
        hessian=[[mp.diff(f,at,(2,0)),mp.diff(f,at,(1,1))],
                 [mp.diff(f,at,(1,1)),mp.diff(f,at,(0,2))]]
        return float(f(*at)),np.array(gradient,dtype=float),np.array(hessian,dtype=float)
