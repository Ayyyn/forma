"""Analytical 3D references and independent global-assembly checks."""
import numpy as np
from scipy.spatial.transform import Rotation
from .mechanics import solve,section
from .oracle import solve as independent


def verify():
    checks={};L=30.;r=.6;E=2000.;nu=.3;A,I,J=section(r);G=E/(2*(1+nu))
    nodes=[[0.,0.,0.],[L,0.,0.]];F=np.zeros((12,6));F[6:]=np.eye(6)
    model=solve(nodes,[(0,1)],[r],[0],F,E,nu)
    expected=np.diag([L/E/A,L**3/(3*E*I),L**3/(3*E*I),L/G/J,L/E/I,L/E/I])
    expected[1,5]=expected[5,1]=L**2/(2*E*I)
    expected[2,4]=expected[4,2]=-L**2/(2*E*I)
    checks['six_dof_analytical_cantilever']=bool(np.allclose(model['u'][6:],expected,rtol=2e-12,atol=1e-12))
    splitF=np.zeros((18,6));splitF[12:]=np.eye(6)
    split=solve([[0,0,0],[L/2,0,0],[L,0,0]],[(0,1),(1,2)],[r,r],[0],splitF,E,nu)
    checks['subdivision_invariance']=bool(np.allclose(split['u'][12:],expected,rtol=1e-11,atol=1e-11))
    R=Rotation.from_rotvec([.44,.73,-.21]).as_matrix();T=np.kron(np.eye(2),R)
    rot=solve(np.array(nodes)@R.T,[(0,1)],[r],[0],F,E,nu)
    checks['full_spatial_coordinate_covariance']=bool(np.allclose(rot['u'][6:],T@expected@T.T,rtol=1e-10,atol=1e-10))
    checks['maxwell_betti_reciprocity']=bool(np.allclose(model['u'][6:],model['u'][6:].T,atol=1e-12))
    checks['energy_work_balance']=bool(np.allclose(model['beam_energy']+model['spring_energy'],model['input_ramp_work'],rtol=1e-12))
    # Analytical loaded cantilever: u=F/(3EI/L^3+k), spring force=k*u.
    spring=[(8,.02)];load=np.zeros(12);load[8]=.002
    result=solve(nodes,[(0,1)],[r],[0],load,E,nu,spring)
    reference=.002/(3*E*I/L**3+.02)
    checks['analytical_output_spring']=bool(np.isclose(result['u'][8,0],reference,rtol=1e-12))
    checks['loaded_energy_partition']=bool(np.allclose(result['beam_energy']+result['spring_energy'],result['input_ramp_work'],rtol=1e-12))
    from .design import geometry,catalogue
    vertices,options=geometry();max_oracle=0.;max_gradient=0.;rng=np.random.default_rng(29102026);count=0
    for ids in list(catalogue().values())[:12]:
        radii=rng.uniform(.45,.65,len(ids));edges=[options[i] for i in ids]
        rhs=np.zeros((6*len(vertices),3));rhs[6*4,0]=.002;rhs[6*9+2,1]=.002;rhs[6*9+1,2]=.002
        spring=[(6*9+2,.02)]
        out=solve(vertices,edges,radii,[0,1,2,3],rhs,springs=spring,sensitivities=True)
        truth=independent(vertices,edges,radii,[0,1,2,3],rhs,springs=spring)
        max_oracle=max(max_oracle,float(np.max(abs(out['u']-truth))/max(1.,abs(truth).max())))
        checks[f'equilibrium_{count}']=out['free_residual_inf']<1e-9
        for j in range(len(ids)):
            delta=np.zeros(len(ids));delta[j]=1e-5
            plus=solve(vertices,edges,radii+delta,[0,1,2,3],rhs,springs=spring)['u']
            minus=solve(vertices,edges,radii-delta,[0,1,2,3],rhs,springs=spring)['u']
            fd=(plus-minus)/2e-5;g=out['du_dr'][j]
            max_gradient=max(max_gradient,float(abs(fd-g).max()/max(1.,abs(g).max())))
        count+=1
    checks['independent_3d_strain_energy_assembly']=max_oracle<1e-8
    checks['analytic_radius_sensitivities']=max_gradient<2e-5
    return {'passed':all(checks.values()),'checks':checks,'reference':'closed-form 3D cantilever, six unit tip loads, plus grounded spring',
            'max_scaled_oracle_error':max_oracle,'max_scaled_gradient_error':max_gradient,
            'spatial_graphs_checked':count,'physical_validation':False,
            'published_frame3dd_example_reproduced':False}
