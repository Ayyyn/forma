"""Independent OpenSeesPy elasticBeamColumn comparison, no copied solver code.

Optional isolated runtime: research/vendor/opensees-runtime (not redistributed).
Both solvers use linear coordinates, Euler--Bernoulli beams, rigid joints,
circular sections and identical externally prescribed loads/grounded springs.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def runtime():
    folder=ROOT/'research/vendor/opensees-runtime'
    if folder.exists():sys.path.insert(0,str(folder))
    import openseespy.opensees as ops
    return ops


def external_solve(nodes,edges,radii,clamped,loads,E=2000.,nu=.3,springs=()):
    ops=runtime();ops.wipe();ops.model('basic','-ndm',3,'-ndf',6)
    active=sorted({v for e in edges for v in e});F=np.asarray(loads,dtype=float)
    if F.ndim==2:
        if F.shape[1]!=1:raise ValueError('External adapter uses one load case at a time')
        F=F[:,0]
    for v in active:
        ops.node(v+1,*[float(x) for x in nodes[v]])
        if v in clamped:ops.fix(v+1,1,1,1,1,1,1)
    for tag,((a,b),r) in enumerate(zip(edges,radii),1):
        direction=np.array(nodes[b],float)-nodes[a];direction/=np.linalg.norm(direction)
        # Independent local orientation; circular bending stiffness is isotropic.
        seed=np.eye(3)[int(np.argmin(abs(direction)))];vecxz=np.cross(direction,seed)
        ops.geomTransf('Linear',tag,*[float(x) for x in vecxz])
        A=np.pi*r*r;I=np.pi*r**4/4;J=2*I;G=E/(2*(1+nu))
        ops.element('elasticBeamColumn',tag,a+1,b+1,float(A),float(E),float(G),float(J),float(I),float(I),tag)
    for i,(dof,k) in enumerate(springs):
        if k==0:continue
        node=dof//6;ground=len(nodes)+i+1;tag=len(edges)+i+1
        ops.node(ground,*[float(x) for x in nodes[node]]);ops.fix(ground,1,1,1,1,1,1)
        ops.uniaxialMaterial('Elastic',tag,float(k))
        ops.element('zeroLength',tag,ground,node+1,'-mat',tag,'-dir',dof%6+1)
    ops.timeSeries('Linear',1);ops.pattern('Plain',1,1)
    for v in active:
        if np.any(F[6*v:6*v+6]):ops.load(v+1,*[float(x) for x in F[6*v:6*v+6]])
    ops.constraints('Plain');ops.numberer('RCM');ops.system('BandSPD');ops.algorithm('Linear');ops.integrator('LoadControl',1.);ops.analysis('Static')
    status=ops.analyze(1)
    if status!=0:raise RuntimeError(f'OpenSees analysis failed: {status}')
    u=np.zeros(6*len(nodes))
    for v in active:u[6*v:6*v+6]=ops.nodeDisp(v+1)
    ops.reactions();reactions=np.zeros_like(u)
    for v in active:
        if v in clamped:reactions[6*v:6*v+6]=ops.nodeReaction(v+1)
    ops.wipe();return u,reactions


def compare(nodes,edges,radii,clamped,loads,E=2000.,nu=.3,springs=()):
    from spatial_actuator.mechanics import solve
    ours=solve(nodes,edges,radii,clamped,loads,E,nu,springs)
    external,reactions=external_solve(nodes,edges,radii,clamped,loads,E,nu,springs)
    expected=ours['u'][:,0];error=float(abs(expected-external).max())
    reaction_dofs=[6*v+d for v in clamped for d in range(6)]
    re=float(abs(ours['reactions'][reaction_dofs,0]-reactions[reaction_dofs]).max())
    return {'passed':bool(np.allclose(expected,external,rtol=1e-8,atol=1e-10) and re<1e-8),
            'maximum_absolute_displacement_or_rotation_error':error,
            'maximum_absolute_anchor_force_or_moment_error':re,
            'max_scaled_u_error':error/max(1.,float(abs(external).max()))}


def run(directory):
    from spatial_actuator.design import compute
    from spatial_actuator.mechanics import solve
    ops=runtime();cases=[];rng=np.random.default_rng(291026)
    # Six separate load directions, including tip torques; vertical and arbitrary
    # beam orientations, with and without a grounded spring.
    for node in [[30,0,0],[0,0,30],[11,23,-17]]:
        for dof in range(6):
            F=np.zeros(12);F[6+dof]=.002
            check=compare([[0,0,0],node],[(0,1)],[.6],[0],F,springs=[(8,.02)])
            cases.append({'kind':'six_dof_cantilever','tip_mm':node,'loaded_tip_dof':dof,**check})
    for label,filename in [('numerical','numerical.json'),('Muse Wonder','meta-probe.json')]:
        saved=json.loads((directory/filename).read_text());task=json.loads((directory/'manifest.json').read_text())['task']
        for record in saved['records']:
            if not record.get('valid'):continue
            model=compute(task,record['edge_ids'],record['radii_mm'])
            check=compare(model['nodes'],model['edges'],record['radii_mm'],[0,1,2,3],model['loads'],task['E_N_mm2'],task['nu'],model['springs'])
            cases.append({'kind':'saved_development_candidate','controller':label,'id':record['id'],**check})
    pyd=ROOT/'research/vendor/opensees-runtime/openseespywin/opensees.pyd'
    report={'created_at_utc':datetime.now(timezone.utc).isoformat(),'external_solver':'OpenSees elasticBeamColumn with Linear geometric transformation',
            'opensees_version':ops.version(),'python_package_version':importlib.metadata.version('openseespy'),
            'external_binary_sha256':hashlib.sha256(pyd.read_bytes()).hexdigest() if pyd.exists() else None,
            'cases':cases,'passed':all(c['passed'] for c in cases),'case_count':len(cases),
            'max_absolute_u_error':max(c['maximum_absolute_displacement_or_rotation_error'] for c in cases),
            'max_absolute_reaction_error':max(c['maximum_absolute_anchor_force_or_moment_error'] for c in cases),
            'scope':'Independent external numerical agreement for the same ideal linear model. No experimental, solid-joint, nonlinear or clinical validation.',
            'published_frame3dd_example_reproduced':False,
            'references':['https://openseespydoc.readthedocs.io/en/latest/src/elasticBeamColumn.html','https://opensees.github.io/OpenSeesDocumentation/user/manual/model/geomTransf/Linear.html']}
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=ROOT/'artifacts/spatial-actuator-step1');parser.add_argument('--output',type=Path,default=ROOT/'research/spatial-opensees-check.json');args=parser.parse_args()
    report=run(args.directory);args.output.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
    if not report['passed']:raise SystemExit(1)
