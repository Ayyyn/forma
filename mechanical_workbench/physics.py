"""General spatial-frame adapter using previously independently checked physics.

No fixed 10-node catalogue. Circular Euler-Bernoulli beams, rigid joints, linear
quasistatics. Multiple loads, graph edits and independent energy quadrature.
"""
from copy import deepcopy
from functools import lru_cache
import json
import numpy as np
from spatial_actuator.mechanics import solve,section
from spatial_actuator.oracle import solve as independent_solve
from spatial_actuator.figures import deformed_member

ASSUMPTIONS=['Small-displacement linear Euler-Bernoulli beams with circular sections and ideal rigid joints.','No contact, shear deformation, geometric nonlinearity, fatigue, real joint compliance or fabricated-part validation.','Nominal strain and pinned-Euler ratios are screening guards, not a strength or buckling certification.','Cylinder geometry visualizes member dimensions; joint manufacturing geometry is not designed.']

def segment_gap(a,b,c,d):
    u=b-a;v=d-c;A=u@u;B=u@v;C=v@v;w=a-c;D=u@w;E=v@w;dist=[]
    for s in [0.,1.]:
        t=np.clip(v@(a+s*u-c)/C,0,1);dist.append(np.linalg.norm(a+s*u-c-t*v))
    for t in [0.,1.]:
        s=np.clip(u@(c+t*v-a)/A,0,1);dist.append(np.linalg.norm(a+s*u-c-t*v))
    determinant=A*C-B*B
    if determinant>1e-12*A*C:
        s=(B*E-C*D)/determinant;t=(A*E-B*D)/determinant
        if 0<=s<=1 and 0<=t<=1:dist.append(np.linalg.norm(a+s*u-c-t*v))
    return float(min(dist))

@lru_cache(maxsize=32)
def gaps(key):
    data=json.loads(key);nodes=np.array(data['nodes_mm']);edges=data['edges'];out=[]
    for i,(a,b) in enumerate(edges):
        for j,(c,d) in enumerate(edges[:i]):
            if not {a,b}&{c,d}:out.append((i,j,segment_gap(nodes[a],nodes[b],nodes[c],nodes[d])))
    return out

def validate(design):
    allowed={'nodes_mm','edges','radii_mm','clamped_nodes','E_N_mm2','nu','label'}
    if set(design)-allowed:raise ValueError('Unknown design fields')
    nodes=np.array(design['nodes_mm'],float);edges=design['edges'];radii=np.array(design['radii_mm'],float)
    if nodes.ndim!=2 or nodes.shape[1]!=3 or not 2<=len(nodes)<=90 or not np.isfinite(nodes).all():raise ValueError('2–90 finite 3D nodes required')
    if not 1<=len(edges)<=300 or len(edges)!=len(radii) or not np.isfinite(radii).all() or np.any(radii<.15):raise ValueError('1–300 members; radius >=.15mm required')
    if not np.isfinite(design['E_N_mm2']) or not 300<=design['E_N_mm2']<=10000 or not -1<design['nu']<.5:raise ValueError('Elastic coefficient bounds')
    seen=set()
    for a,b in edges:
        if type(a) is not int or type(b) is not int or not 0<=a<len(nodes) or not 0<=b<len(nodes) or a==b:raise ValueError('Invalid edge')
        pair=tuple(sorted((a,b)))
        if pair in seen:raise ValueError('Duplicate member')
        seen.add(pair)
    lengths=np.array([np.linalg.norm(nodes[b]-nodes[a]) for a,b in edges])
    if np.any(lengths<1e-5) or np.any(2*radii/lengths>.1+1e-10):raise ValueError('Zero/short member or diameter/length > .1')
    key=json.dumps({'nodes_mm':design['nodes_mm'],'edges':edges},sort_keys=True)
    if any(distance<radii[i]+radii[j]+.05-1e-8 for i,j,distance in gaps(key)):raise ValueError('Unjoined finite-radius member collision')
    return nodes,edges,radii

def load_matrix(nodes,cases):
    if not 1<=len(cases)<=8:raise ValueError('1–8 explicit load cases required')
    F=np.zeros((6*len(nodes),len(cases)))
    for index,case in enumerate(cases):
        for item in case['loads']:
            node=item['node'];vector=np.array(item['force_N']+item.get('moment_N_mm',[0,0,0]),float)
            if type(node) is not int or not 0<=node<len(nodes) or vector.shape!=(6,) or not np.isfinite(vector).all():raise ValueError('Invalid six-DOF load')
            F[6*node:6*node+6,index]+=vector
    if np.any(np.linalg.norm(F,axis=0)==0):raise ValueError('Each case needs a nonzero load')
    return F

def evaluate(design,cases,requirements,independent=True,on_assembly=None):
    expected={'maximum_displacement_mm','maximum_nominal_normal_strain','maximum_nominal_shear_strain','maximum_section_rotation_rad','maximum_pinned_euler_ratio','material_E_relative_uncertainty'}
    if set(requirements)!=expected or any(not np.isfinite(v) or v<=0 for k,v in requirements.items() if k!='material_E_relative_uncertainty'):raise ValueError('Exact positive finite screening requirements required')
    nodes,edges,radii=validate(design);F=load_matrix(nodes,cases);E=design['E_N_mm2'];nu=design['nu'];clamps=design['clamped_nodes']
    if on_assembly:on_assembly('production_assemblies')
    result=solve(nodes,[tuple(e) for e in edges],radii,clamps,F,E,nu);U=result['u'];case_results=[]
    for column,case in enumerate(cases):
        u=U[:,column];maximum=float(np.linalg.norm(u.reshape(-1,6)[:,:3],axis=1).max());strains=[];normal=0.;rotation=0.;buckling=0.;shear=0.
        for r,(dofs,dk,T,kl,L),ends in zip(radii,result['parts'],result['end_forces']):
            A,I,J=section(r);end=ends[:,column];value=max(abs(end[0]),abs(end[6]))/(E*A)+r*max(np.linalg.norm(end[[4,5]]),np.linalg.norm(end[[10,11]]))/(E*I);strains.append(float(value));normal=max(normal,float(value))
            G=E/(2*(1+nu));shear=max(shear,float(r*max(abs(end[3]),abs(end[9]))/(G*J)))
            compression=max(0.,end[0],-end[6]);buckling=max(buckling,float(compression/(np.pi**2*E*I/L**2)));local=T@u[dofs]
            for fraction in np.linspace(0,1,9):
                dh=np.array([(-6*fraction+6*fraction*fraction)/L,1-4*fraction+3*fraction*fraction,(6*fraction-6*fraction*fraction)/L,-2*fraction+3*fraction*fraction])
                rotations=[(1-fraction)*local[3]+fraction*local[9],-dh@(local[[2,4,8,10]]*[1,-1,1,-1]),dh@local[[1,5,7,11]]];rotation=max(rotation,float(np.linalg.norm(rotations)))
        uncertainty=requirements.get('material_E_relative_uncertainty',0.)
        if not 0<=uncertainty<=.2:raise ValueError('Supported modulus uncertainty is 0–20%')
        # All K scales linearly with E here: fixed nu, no grounded springs.
        # Hence u/strain/Euler-ratio bounds at E_low are exact model scalings.
        reserve=1-uncertainty
        margins={'displacement':1-maximum/reserve/requirements['maximum_displacement_mm'],'normal_strain':1-normal/reserve/requirements['maximum_nominal_normal_strain'],'torsion_strain':1-shear/reserve/requirements['maximum_nominal_shear_strain'],'sampled_rotation':1-rotation/reserve/requirements['maximum_section_rotation_rad'],'pinned_euler_ratio':1-buckling/reserve/requirements['maximum_pinned_euler_ratio']}
        balance=abs(float(result['input_ramp_work'][column]-result['beam_energy'][column]))/max(1e-12,abs(float(result['input_ramp_work'][column])))
        lines=[]
        for edge,part in zip(edges,result['parts']):
            a,b=deformed_member(nodes,edge,part,u,1.);lines.append(b[::3].tolist())
        case_results.append({'id':case['id'],'maximum_displacement_mm':maximum,'modulus_uncertainty_displacement_bound_mm':maximum/reserve,'max_nominal_normal_strain':normal,'max_nominal_shear_strain':shear,'sampled_max_section_rotation_rad':rotation,'max_compression_to_pinned_euler_ratio':buckling,'margins':margins,'passes_model_screen':all(m>=-1e-6 for m in margins.values()),'ramp_work_N_mm':float(result['input_ramp_work'][column]),'beam_energy_N_mm':float(result['beam_energy'][column]),'relative_work_balance_error':balance,'node_translations_mm':u.reshape(-1,6)[:,:3].tolist(),'node_rotations_rad':u.reshape(-1,6)[:,3:].tolist(),'deformed_centerlines_mm':lines,'member_nominal_strain':strains})
    oracle={'performed':False,'passed':False}
    if independent:
        if on_assembly:on_assembly('independent_assemblies')
        other=independent_solve(nodes,edges,radii,clamps,F,E,nu);error=float(abs(other-U).max());oracle={'performed':True,'passed':bool(np.allclose(U,other,rtol=1e-7,atol=1e-9)),'maximum_displacement_or_rotation_error':error,'method':'Independent strain-energy quadrature and independent transverse basis','scope':'Same ideal linear law; not physical validation'}
    envelope={'performed':False,'scope':'Explicit load cases only; no general directional guarantee.'}
    # Three orthogonal, equal-norm forces at one node span the load sphere.
    # For each node, sigma_max of its 3x3 response gives the exact largest
    # displacement over unit-norm combinations of those force cases.
    active_force_nodes=[v for v in range(len(nodes)) if np.any(F[6*v:6*v+6])]
    if len(cases)==3 and len(active_force_nodes)==1:
        port=active_force_nodes[0];basis=F[6*port:6*port+3];scale=float(np.linalg.norm(basis[:,0]));moments=F[6*port+3:6*port+6]
        if scale>0 and not np.any(moments) and np.allclose(basis.T@basis,np.eye(3)*scale**2,rtol=1e-9,atol=1e-14):
            singular=[np.linalg.svd(U[6*v:6*v+3],compute_uv=False)[0] for v in range(len(nodes))];critical=int(np.argmax(singular));maximum=float(singular[critical]);_,_,V=np.linalg.svd(U[6*critical:6*critical+3]);coefficients=V[0];reserve=1-requirements['material_E_relative_uncertainty'];margin=1-maximum/reserve/requirements['maximum_displacement_mm']
            envelope={'performed':True,'maximum_displacement_mm':maximum,'modulus_uncertainty_bound_mm':maximum/reserve,'critical_node':critical,'force_norm_N':scale,'critical_force_direction':(basis@coefficients/scale).tolist(),'margin':margin,'passed':bool(margin>=-1e-6),'scope':'Exact linear translational displacement envelope for all same-norm force directions at this one port, plus uniform E uncertainty. Strain/rotation/Euler guards remain checks of the explicit cases. No nonlinear or physical guarantee.'}
    return {'design':deepcopy(design),'load_cases':deepcopy(cases),'requirements':deepcopy(requirements),'node_count':len(nodes),'member_count':len(edges),'free_dofs':6*len({v for e in edges for v in e}-set(clamps)),'cases':case_results,'maximum_displacement_mm':max(c['maximum_displacement_mm'] for c in case_results),'volume_proxy_mm3':result['volume'],'passes_model_screen':all(c['passes_model_screen'] for c in case_results) and (not envelope['performed'] or envelope['passed']),'directional_envelope':envelope,'independent_check':oracle,'maximum_free_residual':result['free_residual_inf'],'assumptions':ASSUMPTIONS,'physical_validation':False,'model':'linear_spatial_frame_v2_direction_envelope'}

def grid(nx=5,ny=3,nz=3,spacing=12.,radius=.45,braced=True):
    if not all(type(n) is int and n>=2 for n in [nx,ny,nz]) or nx*ny*nz>90:raise ValueError('Supported grid: >=2 nodes per axis and <=90 total')
    index=lambda i,j,k:(i*ny+j)*nz+k
    nodes=[[i*spacing,(j-(ny-1)/2)*spacing,(k-(nz-1)/2)*spacing] for i in range(nx) for j in range(ny) for k in range(nz)];edges=[]
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                for di,dj,dk in [(1,0,0),(0,1,0),(0,0,1)]+([(1,1,1)] if braced else []):
                    if i+di<nx and j+dj<ny and k+dk<nz:edges.append([index(i,j,k),index(i+di,j+dj,k+dk)])
    d={'nodes_mm':nodes,'edges':edges,'radii_mm':[radius]*len(edges),'clamped_nodes':[index(0,j,k) for j in range(ny) for k in range(nz)],'E_N_mm2':2000.,'nu':.3,'label':'Spatial assembly / rigid-joint grid'}
    validate(d);return d,index(nx-1,ny//2,nz//2)

def development_scenario():
    d,port=grid();requirements={'maximum_displacement_mm':.12,'maximum_nominal_normal_strain':.005,'maximum_nominal_shear_strain':.005,'maximum_section_rotation_rad':.03,'maximum_pinned_euler_ratio':.2,'material_E_relative_uncertainty':.05}
    cases=[{'id':name,'loads':[{'node':port,'force_N':vector}]} for name,vector in [('axial',[.01,0,0]),('lateral',[0,.01,0]),('vertical',[0,0,.01])]]
    initial=evaluate(d,cases,requirements);factor=.1/initial['maximum_displacement_mm']
    for case in cases:case['loads'][0]['force_N']=(np.array(case['loads'][0]['force_N'])*factor).tolist()
    reference=evaluate(d,cases,requirements)
    # An intentionally constructed development case, not a sampled benchmark.
    actual=deepcopy(d);actual['E_N_mm2']=1200.;changed=evaluate(actual,cases,requirements)
    observation={'source':'synthetic virtual experiment from the same ideal law, not a physical measurement','load_case_peaks_mm':{c['id']:c['maximum_displacement_mm'] for c in changed['cases']},'maximum_displacement_mm':changed['maximum_displacement_mm'],'requirement_passed':changed['passes_model_screen'],'unknown_material_modulus':True,'noise_model':'none in this development fixture','cases':changed['cases']}
    return {'id':'complex-frame-material-revision-v1','title':'Recover a multi-load spatial assembly after a material change','design':d,'cases':cases,'requirements':requirements,'reference':reference,'observation':observation,'source':'Constructed development scenario; loads scaled to a .1 mm nominal peak, displacement limit .12 mm. This is not an unseen efficacy benchmark.','family':'linear spatial frames','coverage_next':'Nonlinear target-force response and functional fabrication are not implemented in this first slice.'}

def imported_scenario(design,cases,requirements):
    reference=evaluate(design,cases,requirements);actual=deepcopy(design);actual['E_N_mm2']*=.6;changed=evaluate(actual,cases,requirements)
    return {'id':'imported-assembly','title':'Imported spatial assembly: virtual material revision','design':deepcopy(design),'cases':deepcopy(cases),'requirements':deepcopy(requirements),'reference':reference,
            'observation':{'source':'synthetic virtual experiment from the same ideal law; no hardware','load_case_peaks_mm':{c['id']:c['maximum_displacement_mm'] for c in changed['cases']},'maximum_displacement_mm':changed['maximum_displacement_mm'],'requirement_passed':changed['passes_model_screen'],'unknown_material_modulus':True,'noise_model':'none','cases':changed['cases']},
            '_actual_E_N_mm2':actual['E_N_mm2'],'source':'User-specified graph/load cases and limits. Virtual material change is a known-law development fixture, not real experimental data.','family':'linear spatial frames','coverage_next':'Only the declared linear beam physics is supported.'}
