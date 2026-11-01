"""Unscored offline feasibility probe; no Meta calls or physical measurements.

Two identical coaxial cells, free intermediate ring and end rotation, with ideal
imposed total shortening. Reflection changes physical twist sign, not cell energy.
No arm bending, contact, tendon routing or dynamic snap-through model is claimed.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.linalg import block_diag

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from kresling_proof.model import Cell,AxialSpring,jet,scaled_jet
from kresling_proof.statics import relax_phi
from kresling_proof.oracle import vertex_energy


def state(cell,total,spring):
    u=total/2;relaxed=relax_phi(cell,u,spring);p=relaxed['phi_rad']
    _,g,h=jet(cell,u,p,spring);_,gs,hs=scaled_jet(cell,[u/cell.r_mm,p],spring)
    # Free coordinates x=(u1/r,phi1,phi2), with u2/r=total/r-u1/r.
    B=np.array([[1.,0,0],[0,1,0],[-1,0,0],[0,0,1.]])
    reduced=B.T@block_diag(hs,hs)@B
    residual=B.T@np.r_[gs,gs]
    eig,vec=np.linalg.eigh(reduced)
    return {'total_shortening_mm':total,'cell_shortening_mm':u,'cell_twist_deg':math.degrees(p),
            'opposite_handed_additional_end_twist_deg':0.,'same_handed_additional_end_twist_deg':2*math.degrees(p),
            'external_axial_reaction_N':float(g[0]),'cell_torque_N_mm':float(g[1]),
            'constrained_gradient_inf':float(max(abs(residual))),
            'constrained_hessian_eigenvalues':eig.tolist(),
            'constrained_local_stability':'strict_local_minimum' if eig[0]>1e-7 else 'unstable' if eig[0]<-1e-7 else 'degenerate',
            'relaxed_single_cell_axial_stiffness_N_per_mm':float(h[0,0]-h[0,1]**2/h[1,1])},reduced,vec[:,0]


def independent_check(cell,total,spring,record,analytic,direction):
    p=math.radians(record['cell_twist_deg']);x=np.array([total/2/cell.r_mm,p,p])
    def f(q):
        return (vertex_energy(cell.to_dict(),q[0]*cell.r_mm,q[1],spring.to_dict())+
                vertex_energy(cell.to_dict(),total-q[0]*cell.r_mm,q[2],spring.to_dict()))/cell.energy_scale
    errors=[]
    for step in [1e-3,3e-4,1e-4,3e-5]:
        fd=np.empty((3,3));basis=np.eye(3)*step
        for i in range(3):
            for j in range(3):
                if i==j:fd[i,i]=(f(x+basis[i])-2*f(x)+f(x-basis[i]))/step**2
                else:fd[i,j]=(f(x+basis[i]+basis[j])-f(x+basis[i]-basis[j])-f(x-basis[i]+basis[j])+f(x-basis[i]-basis[j]))/(4*step**2)
        errors.append({'step_dimensionless':step,'max_abs_hessian_error':float(max(abs(fd-analytic).flat)),
                       'finite_difference_eigenvalues':np.linalg.eigvalsh(fd).tolist()})
    delta=1e-4
    changes=[float(f(x+s*delta*direction)-f(x)) for s in [-1,1]]
    expected_sign=1 if record['constrained_local_stability']=='strict_local_minimum' else -1
    return {'passed':bool(errors[2]['max_abs_hessian_error']<1e-5 and all(expected_sign*y>0 for y in changes)),
            'independent_energy':'sum of independently constructed vertex/face-normal cell energies',
            'hessian_step_study':errors,'energy_changes_along_smallest_mode_normalized':changes}


def main():
    cell=Cell();results=[];curves=[]
    for k in [0.,.25]:
        spring=AxialSpring(k>0,k,0.)
        record,h,direction=state(cell,20.,spring)
        audit=independent_check(cell,20.,spring,record,h,direction)
        curve=[state(cell,float(total),spring)[0] for total in np.linspace(0,20,21)]
        results.append({'spring':spring.to_dict(),'state':record,'independent_check':audit,
                        'minimum_sampled_constrained_eigenvalue_0_to_20_mm':min(x['constrained_hessian_eigenvalues'][0] for x in curve)})
        curves.append(curve)
    report={'unscored_development_probe':True,'physical_measurements':False,'meta_api_calls':0,
        'cell':cell.to_dict(),'cases':results,'curves':curves,
        'scope':'Ideal two-cell coaxial assembly at imposed total shortening, free internal shortening redistribution and free rotations. Local constrained stability only; no global-minimum, continuous-path certification, hardware or dynamic claims.',
        'assumptions':['Independent identical published reduced-model cell energies add, with no junction compliance or intercell contact.',
            'Ideal axial springs act on each cell; 0.25 N/mm is a declared numerical stabilizer, not a calibrated part.',
            'Reflection reverses additional global twist sign, while each cell uses its own positive local coordinate.',
            'The intermediate ring stays coaxial under an ideal guide; bending and off-axis modes are excluded.',
            'A prescribed global stroke represents an ideal actuator constraint; no motor, tendon routing, friction or payload model is validated.',
            'A positive Hessian certifies a local minimum within modeled coordinates, not globally preferred configuration or fabrication robustness.'],
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__),ROOT/'kresling_proof/model.py',ROOT/'kresling_proof/statics.py',ROOT/'kresling_proof/oracle.py']}}
    report['passed']=bool(all(x['independent_check']['passed'] for x in results)
       and results[0]['state']['constrained_local_stability']=='unstable'
       and results[1]['state']['constrained_local_stability']=='strict_local_minimum'
       and results[1]['minimum_sampled_constrained_eigenvalue_0_to_20_mm']>1e-7)
    out=ROOT/'research/actuator-assembly-probe';out.mkdir(exist_ok=True)
    (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4),layout='constrained')
    for k,curve in zip([0.,.25],curves):
        ax.plot([x['total_shortening_mm'] for x in curve],[x['constrained_hessian_eigenvalues'][0] for x in curve],label=f'Ideal spring k={k:g} N/mm per cell')
    ax.axhline(0,color='black',lw=.8);ax.set(xlabel='Imposed total shortening (mm)',ylabel='Smallest constrained Hessian eigenvalue',title='Twist cancellation does not guarantee assembly stability')
    ax.legend(fontsize=8);ax.spines[['top','right']].set_visible(False)
    fig.savefig(out/'stability.png',dpi=160);fig.savefig(out/'stability.svg');plt.close(fig)
    print(json.dumps({'passed':report['passed'],'cases':[{k:v for k,v in x.items() if k!='independent_check'} for x in results]},indent=2))
    if not report['passed']:raise RuntimeError('Offline assembly probe failed its numerical checks')


if __name__=='__main__':main()
