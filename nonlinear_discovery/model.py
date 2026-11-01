"""Four nonlinear Kresling cells, fixed total length/additional end twist.

Published reduced-order cell energy is reused unchanged. Added ideal bilateral
axial/torsional springs connect ring pairs; their routing/joints are not modeled.
Six internal DOFs remain after two endpoint constraints; no lateral modes/contact.
"""
from itertools import combinations
import math
import numpy as np
from scipy.linalg import block_diag
from scipy.optimize import root
from kresling_proof.model import Cell,scaled_jet
from kresling_proof.oracle import vertex_energy

R=30.;SCALE=1500.;TOTAL=55.;SPANS=[(i,j) for i in range(5) for j in range(i+1,5) if (i,j)!=(0,4)]


def reference():
    return {'cells':[{'h0_mm':39.48,'theta0_deg':30.} for _ in range(4)],'handedness':[1,-1,1,-1],
            'springs':[{'type':'axial','rings':[0,2],'k':.01,'offset_A':45.,'offset_B':10.}],
            'note':'Conventional paper-inspired axial pre-stress reference, not a new invention.'}


def validate(d):
    if not isinstance(d,dict) or set(d)-{'cells','handedness','springs','note'}:raise ValueError('Unknown design fields')
    if len(d['cells'])!=4 or sorted(d['handedness'])!=[-1,-1,1,1] or any(type(v) is not int for v in d['handedness']):raise ValueError('Four cells with two positive/two negative handedness values required')
    for c in d['cells']:
        if set(c)!={'h0_mm','theta0_deg'} or not 36<=c['h0_mm']<=44 or not 28<=c['theta0_deg']<=34:raise ValueError('Cell parameter bounds')
        Cell(h0_mm=c['h0_mm'],theta0_deg=c['theta0_deg'])
    if not 1<=len(d['springs'])<=4:raise ValueError('One programmable spring and at most three fixed springs')
    for index,s in enumerate(d['springs']):
        fields={'type','rings','k','offset_A','offset_B'} if index==0 else {'type','rings','k','offset'}
        if set(s)!=fields or s['type'] not in ['axial','torsion'] or tuple(s['rings']) not in SPANS:raise ValueError('Invalid spring schema/ring span')
        if any(type(v) is not int for v in s['rings']):raise ValueError('Integer ring IDs required')
        if not np.isfinite(s['k']) or not 0<s['k']<=(.08 if s['type']=='axial' else 30.):raise ValueError('Spring stiffness bound')
        for key in ['offset_A','offset_B'] if index==0 else ['offset']:
            v=s[key]
            if not np.isfinite(v) or not ((-10<=v<=60) if s['type']=='axial' else (-1.5<=v<=1.5)):raise ValueError('Preload offset bound')
    return d


def mapping(d):
    B=np.zeros((8,6));B[:6]=np.eye(6);B[6,[0,2,4]]=-1
    B[7,[1,3,5]]=-d['handedness'][3]*np.array(d['handedness'][:3])
    q0=np.zeros(8);q0[6]=TOTAL/R
    return B,q0


def cells(d):return [Cell(h0_mm=c['h0_mm'],theta0_deg=c['theta0_deg']) for c in d['cells']]


def domain(d,q,margin=0.):
    for i,c in enumerate(cells(d)):
        if not (-.08<q[2*i]<(c.h0_mm-2)/R) or not (-.08<q[2*i+1]<c.phi_max-.0001):return False
    return True


def full_jet(d,q,setting):
    if not domain(d,q):raise ValueError('Outside declared interior state search domain')
    cc=cells(d);pieces=[scaled_jet(c,q[2*i:2*i+2]) for i,c in enumerate(cc)]
    energy=sum(p[0] for p in pieces);gradient=np.concatenate([p[1] for p in pieces]);hessian=block_diag(*[p[2] for p in pieces])
    for index,s in enumerate(d['springs']):
        a,b=s['rings'];w=np.zeros(8)
        for i in range(a,b):w[2*i if s['type']=='axial' else 2*i+1]=R if s['type']=='axial' else d['handedness'][i]
        offset=s['offset_'+setting] if index==0 else s['offset'];delta=float(w@q-offset);k=s['k']/SCALE
        energy+=.5*k*delta*delta;gradient+=k*delta*w;hessian+=k*np.outer(w,w)
    return energy,gradient,hessian


def jet(d,x,setting):
    B,q0=mapping(d);value,g,h=full_jet(d,B@x+q0,setting)
    return value,B.T@g,B.T@h@B


def independent_energy(d,x,setting):
    B,q0=mapping(d);q=B@x+q0;value=0.
    for i,c in enumerate(cells(d)):value+=vertex_energy(c.to_dict(),q[2*i]*R,q[2*i+1])
    for index,s in enumerate(d['springs']):
        a,b=s['rings'];deformation=sum(q[2*i]*R if s['type']=='axial' else d['handedness'][i]*q[2*i+1] for i in range(a,b))
        rest=s['offset_'+setting] if index==0 else s['offset'];value+=.5*s['k']*(deformation-rest)**2
    return value/SCALE


def seeds(d,count=16):
    B,q0=mapping(d);result=[]
    # Fixed, shared mode-oriented seeds plus seeded feasible interior samples.
    for folded in combinations(range(4),2):
        q=np.zeros(8)
        for i in folded:q[2*i]=TOTAL/(2*R);q[2*i+1]=.93
        x=np.linalg.lstsq(B,q-q0,rcond=None)[0]
        if domain(d,B@x+q0):result.append(x)
    rng=np.random.default_rng(30102026);attempts=0
    while len(result)<count and attempts<count*100:
        attempts+=1;u=rng.dirichlet([.7]*4)*TOTAL/R;q=np.zeros(8);q[::2]=u;q[1::2]=rng.uniform(.08,.95,4)
        x=q[:6];q=B@x+q0
        if domain(d,q):result.append(x)
    return result[:count]


def record(d,x,setting):
    B,q0=mapping(d);q=B@x+q0;value,g,h=jet(d,x,setting);eigen=np.linalg.eigvalsh((h+h.T)/2)
    _,fullg,_=full_jet(d,q,setting)
    constraints=np.zeros((2,8));constraints[0,::2]=1.;constraints[1,1::2]=d['handedness']
    multipliers=np.linalg.lstsq(constraints.T,fullg,rcond=None)[0]
    u=q[::2]*R;p=q[1::2];polarization=float((u[0]+u[1]-u[2]-u[3])/TOTAL)
    residual=float(abs(g).max())
    return {'x':x.tolist(),'q':q.tolist(),'cell_shortening_mm':u.tolist(),'cell_additional_twist_rad':p.tolist(),
            'energy_N_mm':value*SCALE,'gradient_residual_normalized':residual,'hessian_eigenvalues_normalized':eigen.tolist(),
            'classification':'minimum' if residual<1e-7 and eigen[0]>1e-7 else 'saddle_or_degenerate_or_unresolved',
            'polarization':polarization,'holding_axial_force_N':float(multipliers[0]*SCALE/R),
            'holding_torque_N_mm':float(multipliers[1]*SCALE),'total_shortening_mm':float(sum(u)),
            'additional_end_twist_rad':float(np.dot(d['handedness'],p))}


def equilibria(d,setting,count=16):
    found=[];failed=0;attempts=0
    for x0 in seeds(d,count):
        attempts+=1
        try:
            sol=root(lambda x:jet(d,x,setting)[1],x0,jac=lambda x:jet(d,x,setting)[2],method='hybr',options={'xtol':1e-9,'maxfev':150})
            x=sol.x;B,q0=mapping(d)
            if not domain(d,B@x+q0):raise ValueError('Out of bounds')
            r=record(d,x,setting)
            if r['gradient_residual_normalized']>1e-7:raise ValueError('Residual')
            if any(np.linalg.norm(x-np.array(p['x']))<1e-4 for p in found):continue
            found.append(r)
        except (ValueError,FloatingPointError,OverflowError,np.linalg.LinAlgError):failed+=1
    return {'states':sorted(found,key=lambda r:r['energy_N_mm']),'attempts':attempts,'failed_starts':failed,'exhaustive':False}


def evaluate(d,starts=16):
    validate(d);results={setting:equilibria(d,setting,starts) for setting in ['A','B']};details={};penalty=0.;biases=[];minimum_eigen=1.;maxforce=0.
    for setting,sign in [('A',1),('B',-1)]:
        minima=[s for s in results[setting]['states'] if s['classification']=='minimum']
        target=[s for s in minima if sign*s['polarization']>=.35];counter=[s for s in minima if sign*s['polarization']<=-.35]
        other=[s for s in minima if sign*s['polarization']<.35]
        if not target or not counter:penalty+=10;details[setting]={'minimum_count_found':len(minima),'target_and_counter_found':False};continue
        chosen=min(target,key=lambda s:s['energy_N_mm']);opposite=min(counter,key=lambda s:s['energy_N_mm']);competitor=min(other,key=lambda s:s['energy_N_mm'])
        bias=competitor['energy_N_mm']-chosen['energy_N_mm'];biases.append(bias)
        eig=min(chosen['hessian_eigenvalues_normalized'][0],opposite['hessian_eigenvalues_normalized'][0]);minimum_eigen=min(minimum_eigen,eig)
        force=max(abs(chosen['holding_axial_force_N']),abs(opposite['holding_axial_force_N']));maxforce=max(maxforce,force)
        penalty+=max(0.,(.5-bias)/.5)+max(0.,(2e-4-eig)/2e-4)+max(0.,(force-1.5)/1.5)
        details[setting]={'minimum_count_found':len(minima),'target_and_counter_found':True,'energy_bias_N_mm':bias,'target':chosen,'counter':opposite,'competitor':competitor}
    feasible=penalty<=1e-6
    return {'feasible':feasible,'violation':penalty,'worst_bias_N_mm':min(biases) if len(biases)==2 else None,
            'minimum_selected_hessian_eigenvalue':minimum_eigen if len(biases)==2 else None,'maximum_selected_holding_force_N':maxforce,
            'settings':results,'details':details,'starts_per_setting':starts,'scope':'Found local minima in six constrained internal DOFs; not exhaustive states, global preference, switching dynamics or physical validation.'}


def audit(d,result):
    checks=[]
    for setting in ['A','B']:
        for state in result['settings'][setting]['states']:
            if state['classification']!='minimum':continue
            x=np.array(state['x']);value,g,h=jet(d,x,setting);step=1e-4;eye=np.eye(6)*step;fd=np.empty((6,6))
            f=lambda z:independent_energy(d,z,setting)
            for i in range(6):
                for j in range(6):
                    if i==j:fd[i,j]=(f(x+eye[i])-2*f(x)+f(x-eye[i]))/step**2
                    else:fd[i,j]=(f(x+eye[i]+eye[j])-f(x+eye[i]-eye[j])-f(x-eye[i]+eye[j])+f(x-eye[i]-eye[j]))/(4*step**2)
            err=float(abs(fd-h).max());checks.append({'setting':setting,'energy_error_normalized':abs(f(x)-value),'hessian_error_normalized':err,
                                                       'independent_min_eigenvalue':float(np.linalg.eigvalsh(fd)[0]),'passed':bool(abs(f(x)-value)<1e-9 and err<2e-5 and np.linalg.eigvalsh(fd)[0]>0)})
    return {'passed':bool(checks and all(c['passed'] for c in checks)),'checks':checks,'finite_difference_step':1e-4,'independent_geometry':'Published cell vertex/face-normal oracle plus explicit ideal ring-spring energy','physical_validation':False}


def mesh(d,state):
    q=np.array(state['q']);vertices=[];faces=[];base=0.;z=0.;n=6
    for i,c in enumerate(cells(d)):
        sign=d['handedness'][i];theta=c.theta0+q[2*i+1];h=c.h0_mm-q[2*i]*R;first=len(vertices)
        for upper in [0,1]:
            for j in range(n):
                a=base+sign*(2*math.pi*j/n+(theta if upper else 0));vertices.append([R*math.cos(a),R*math.sin(a),z+upper*h])
        for j in range(n):
            nxt=(j+1)%n;faces.extend([[first+j,first+n+j,first+n+nxt],[first+j,first+n+nxt,first+nxt]])
        base+=sign*theta;z+=h
    return {'vertices_mm':vertices,'triangles':faces,'springs':d['springs'],'ring_heights_mm':[0.]+np.cumsum([c.h0_mm-q[2*i]*R for i,c in enumerate(cells(d))]).tolist(),
            'note':'Geometric configuration at a computed equilibrium. Flat triangular panels visualize the reduced-model mesh; material strain/contact/fabricated joints are not rendered.'}
