"""Zang et al. JMPS 188 (2024) 105630, Eqs. 1-9, 14-15.

Two DOFs, rigid polygonal end rings, effective bar/hinge elasticity. This is
not shell FEA and does not enforce contact or represent material failure.
"""
from dataclasses import asdict, dataclass
from functools import lru_cache
import math
import numpy as np


@dataclass(frozen=True)
class Cell:
    n: int = 6
    r_mm: float = 30.0
    h0_mm: float = 39.48
    theta0_deg: float = 30.0
    ks_N: float = 50.0
    kr_per_length: float = 0.005

    def __post_init__(self):
        if isinstance(self.n,bool) or not isinstance(self.n,int) or self.n<3:
            raise ValueError('n must be an integer >=3')
        values=(self.r_mm,self.h0_mm,self.theta0_deg,self.ks_N,self.kr_per_length)
        if not all(math.isfinite(v) for v in values):raise ValueError('Parameters must be finite')
        if min(self.r_mm,self.h0_mm,self.ks_N)<=0 or self.kr_per_length<0:
            raise ValueError('Positive geometry/axial stiffness and nonnegative hinge stiffness required')
        if not 0<2*self.theta0<math.pi-2*math.pi/self.n:
            raise ValueError('Initial twist must give a positive additional folding range')

    @property
    def theta0(self):return math.radians(self.theta0_deg)
    @property
    def phi_max(self):return math.pi-2*math.pi/self.n-2*self.theta0
    @property
    def energy_scale(self):return self.ks_N*self.r_mm
    def to_dict(self):return asdict(self)


@dataclass(frozen=True)
class AxialSpring:
    enabled: bool = False
    stiffness_N_per_mm: float = 0.0
    offset_mm: float = 0.0

    def __post_init__(self):
        if not isinstance(self.enabled,bool):raise ValueError('Spring activation must be boolean')
        if not all(math.isfinite(v) for v in (self.stiffness_N_per_mm,self.offset_mm)) or self.stiffness_N_per_mm<0:
            raise ValueError('Finite offset and nonnegative spring stiffness required')
    def to_dict(self):return asdict(self)


def _acos(value):
    value=np.asarray(value)
    if np.any(np.abs(value)>1+128*np.finfo(float).eps):
        raise ValueError('Nonphysical dihedral cosine, not a roundoff error')
    return np.arccos(np.clip(value,-1,1))


def features(cell, u_mm, phi_rad):
    """b, c, delta_a, delta_b, delta_c, including broadcast arrays."""
    h=cell.h0_mm-np.asarray(u_mm);theta=cell.theta0+np.asarray(phi_rad)
    if np.any(~np.isfinite(h)) or np.any(~np.isfinite(theta)) or np.any(h<0):
        raise ValueError('Nonfinite state or negative ring separation')
    if np.any(theta<=0) or np.any(theta>=math.pi-2*math.pi/cell.n):
        raise ValueError('State outside the declared twist sector')
    r=cell.r_mm;alpha=math.pi/cell.n
    b=np.sqrt(h*h+4*r*r*np.sin(theta/2)**2)
    c=np.sqrt(h*h+4*r*r*np.sin(theta/2+alpha)**2)
    da=np.arctan2(h,2*r*np.sin(theta/2+alpha)*np.sin(theta/2))
    e=r*r*(np.cos(theta+alpha)-math.cos(alpha))**2
    denom=h*h+e
    if np.any(denom<=0):raise ValueError('Degenerate facet')
    db=math.pi-_acos((h*h*np.cos(theta+2*alpha)-e)/denom)
    dc=math.pi-_acos((h*h*np.cos(theta)-e)/denom)
    return np.stack(np.broadcast_arrays(b,c,da,db,dc),axis=0)


def coefficients(cell):
    b0,c0,*_=features(cell,0.,0.)
    a0=2*cell.r_mm*math.sin(math.pi/cell.n)
    # n_a=2*n: edges of BOTH end polygons, not just one polygon.
    return np.array([cell.n*cell.ks_N/b0,cell.n*cell.ks_N/c0,
                     2*cell.n*cell.kr_per_length*a0,
                     cell.n*cell.kr_per_length*b0,cell.n*cell.kr_per_length*c0])


def energy_components(cell, u_mm, phi_rad, spring=AxialSpring()):
    value=features(cell,u_mm,phi_rad);rest=features(cell,0.,0.)
    shape=(5,)+(1,)*(value.ndim-1)
    terms=.5*coefficients(cell).reshape(shape)*(value-rest.reshape(shape))**2
    u,phi=np.broadcast_arrays(np.asarray(u_mm),np.asarray(phi_rad))
    extra=.5*spring.stiffness_N_per_mm*(spring.offset_mm-u)**2 if spring.enabled else np.zeros_like(u)
    return np.concatenate((terms,np.asarray(extra)[None,...]),axis=0)


def energy(cell,u_mm,phi_rad,spring=AxialSpring()):
    return np.sum(energy_components(cell,u_mm,phi_rad,spring),axis=0)


@lru_cache(maxsize=1)
def _feature_derivatives():
    """Automatic derivatives of geometry; the constitutive chain rule is explicit."""
    import sympy as s
    u,p,r,H,t,a=s.symbols('u p r H t a',real=True)
    h=H-u;theta=t+p
    e=r**2*(s.cos(theta+a)-s.cos(a))**2
    f=s.Matrix([s.sqrt(h**2+4*r**2*s.sin(theta/2)**2),
                s.sqrt(h**2+4*r**2*s.sin(theta/2+a)**2),
                s.atan2(h,2*r*s.sin(theta/2+a)*s.sin(theta/2)),
                s.pi-s.acos((h**2*s.cos(theta+2*a)-e)/(h**2+e)),
                s.pi-s.acos((h**2*s.cos(theta)-e)/(h**2+e))])
    args=(u,p,r,H,t,a)
    jac=f.jacobian([u,p])
    hess=[s.hessian(v,[u,p]) for v in f]
    return (s.lambdify(args,jac,'numpy',cse=True),
            s.lambdify(args,hess,'numpy',cse=True))


def jet(cell,u_mm,phi_rad,spring=AxialSpring()):
    """Energy, physical gradient [N,N mm/rad], physical Hessian."""
    current=features(cell,u_mm,phi_rad)
    if np.ndim(u_mm) or np.ndim(phi_rad):raise ValueError('jet requires a scalar state')
    if cell.h0_mm-u_mm<1e-8*cell.r_mm:raise ValueError('Flat boundary: use energy, not an interior derivative')
    jac_fn,hess_fn=_feature_derivatives()
    args=(u_mm,phi_rad,cell.r_mm,cell.h0_mm,cell.theta0,math.pi/cell.n)
    with np.errstate(invalid='raise',divide='raise'):
        jac=np.asarray(jac_fn(*args),dtype=float)
        hs=np.asarray(hess_fn(*args),dtype=float)
    difference=current-features(cell,0.,0.);k=coefficients(cell)
    gradient=jac.T@(k*difference)
    hessian=np.einsum('i,ij,ik->jk',k,jac,jac)+np.einsum('i,ijk->jk',k*difference,hs)
    if spring.enabled:
        gradient[0]+=spring.stiffness_N_per_mm*(u_mm-spring.offset_mm)
        hessian[0,0]+=spring.stiffness_N_per_mm
    if not np.all(np.isfinite(gradient)) or not np.all(np.isfinite(hessian)):
        raise ValueError('Nonfinite interior derivative')
    return float(energy(cell,u_mm,phi_rad,spring)),gradient,hessian


def scaled_jet(cell,q,spring=AxialSpring()):
    """q=(u/r,phi radians), U* = U/(ks*r); comparable residual/Hessian units."""
    value,g,h=jet(cell,float(q[0])*cell.r_mm,float(q[1]),spring)
    scale=np.array([cell.r_mm,1.])
    return value/cell.energy_scale,g*scale/cell.energy_scale,h*scale[:,None]*scale[None,:]/cell.energy_scale
