"""Scientific acceptance gate before any real-model pilot."""
import numpy as np
from .mechanics import solve_frame
from .oracle import oracle_solve
from .design import task_cases,geometry,templates,bounds


def verify():
    checks={};L=40.;E=2000.;B=3.;t=.8;I=B*t**3/12;A=B*t
    straight=solve_frame([[0.,0.],[L,0.]],[(0,1)],[t],[0],1,E,B)
    expected=np.diag([L/(E*A),L**3/(3*E*I)])
    checks['analytic_cantilever']=bool(np.allclose(straight['compliance'],expected,rtol=1e-12,atol=1e-12))
    checks['tip_rotation']=bool(np.isclose(straight['displacements_per_unit_load'][5,1],L**2/(2*E*I),rtol=1e-12))
    subdiv=solve_frame([[0.,0.],[L/2,0.],[L,0.]],[(0,1),(1,2)],[t,t],[0],2,E,B)
    checks['subdivision_invariance']=bool(np.allclose(subdiv['compliance'],expected,rtol=1e-11,atol=1e-11))
    checks['energy_work_identity']=bool(np.allclose(2*straight['internal_strain_energy_per_unit_load'],np.diag(straight['compliance']),rtol=1e-12))
    nodes,edges=geometry();rng=np.random.default_rng(292026);max_oracle=0.;max_sensitivity=0.;checked=0
    for ids in templates().values():
        widths=np.array([rng.uniform(lo+.05*(hi-lo),hi-.05*(hi-lo)) for lo,hi in bounds(task_cases()[0],ids)])
        ee=[edges[i] for i in ids];result=solve_frame(nodes,ee,widths,[0,1,2],7)
        oracle=oracle_solve(nodes,ee,widths,[0,1,2],7)
        max_oracle=max(max_oracle,float(np.max(abs(result['compliance']-oracle))/max(1.,abs(oracle).max())))
        for j in range(len(ids)):
            delta=np.zeros(len(ids));delta[j]=1e-5
            plus=solve_frame(nodes,ee,widths+delta,[0,1,2],7)['compliance']
            minus=solve_frame(nodes,ee,widths-delta,[0,1,2],7)['compliance']
            fd=(plus-minus)/(2e-5);analytic=result['compliance_gradient'][j]
            max_sensitivity=max(max_sensitivity,float(abs(fd-analytic).max()/max(1.,abs(analytic).max())))
        checks[f'reciprocity_{checked}']=bool(np.allclose(result['compliance'],result['compliance'].T,atol=1e-10))
        checks[f'equilibrium_{checked}']=bool(result['free_residual_inf']<1e-8);checked+=1
    angle=.53;R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    rotated=solve_frame((np.array([[0.,0.],[L,0.]])@R.T).tolist(),[(0,1)],[t],[0],1,E,B)
    checks['rigid_frame_covariance']=bool(np.allclose(rotated['compliance'],R@expected@R.T,rtol=1e-10,atol=1e-10))
    checks['independent_hermite_energy_oracle']=max_oracle<1e-9
    checks['analytic_adjoint_width_gradients']=max_sensitivity<2e-5
    return {'passed':all(checks.values()),'checks':checks,'topologies_checked':checked,
            'max_scaled_independent_compliance_error':max_oracle,'max_scaled_width_gradient_error':max_sensitivity,
            'physics':'small-displacement linear rigid-jointed in-plane Euler-Bernoulli frame',
            'physical_validation':False}
