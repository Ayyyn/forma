"""Parameterized geometry and shared public design language for revision tasks."""
from itertools import combinations,permutations
import numpy as np
from spatial_actuator.design import geometry as old_geometry,catalogue as old_catalogue,task as old_task,segment_distance
from spatial_actuator.mechanics import solve,section


def geometry(t):
    nodes,edges=old_geometry();nodes=np.asarray(nodes,float)
    # Affine dimensions plus explicit node offsets; no hidden geometry changes.
    nodes=nodes@np.asarray(t.get('geometry_matrix',np.eye(3)),float).T
    nodes+=np.asarray(t.get('node_offsets_mm',np.zeros_like(nodes)),float)
    return nodes,edges


def catalogue():
    return old_catalogue()


def broad_catalogue():
    result=dict(catalogue());_,edges=old_geometry();lookup={e:i for i,e in enumerate(edges)}
    def add(name,ee):result[name]=sorted(lookup[tuple(sorted(e))] for e in ee)
    # Every pair of anchors and ordered pair of distinct side nodes. Same
    # grounded language as Muse; not limited to the four old fork layouts.
    for a,b in combinations(range(4),2):
        for c,d in permutations(range(5,9),2):
            ee=[(a,c),(b,d),(c,4),(d,4),(c,9),(d,9)]
            add(f'spatial_fork_{a}_{b}_{c}_{d}',ee)
            add(f'braced_{a}_{b}_{c}_{d}',ee+[(c,d)])
    # One- and two-anchor input chains from the old catalogue remain included.
    unique={}
    for name,ids in result.items():unique.setdefault(tuple(ids),name)
    return {name:list(ids) for ids,name in unique.items()}


def development_task():
    t=old_task();t.update(id='revision_adapter_development',geometry_matrix=np.eye(3).tolist(),node_offsets_mm=np.zeros((10,3)).tolist(),output_sign=1)
    return t


def generate_cases(seed):
    """No solver calls, feasibility filtering or target fitting in generation."""
    rng=np.random.default_rng(seed);cases=[]
    kinds=['material','load','dimensions','asymmetry','reverse','material_load','shape_reverse','combined']
    for index,kind in enumerate(kinds):
        t=development_task();t['id']=f'revision_{index:02d}';t['revision_kind']=kind
        if kind in ['material','material_load','combined']:t['E_N_mm2']=float(rng.uniform(1100,1600))
        if kind in ['load','material_load','combined']:t['output_spring_N_mm']=float(rng.uniform(.025,.045))
        if kind in ['dimensions','shape_reverse','combined']:
            sx,sy,sz=rng.uniform(.85,1.2,3);t['geometry_matrix']=[[float(sx),0.,0.],[0.,float(sy),0.],[0.,0.,float(sz)]]
        if kind in ['asymmetry','combined']:
            offsets=np.zeros((10,3));offsets[4]=rng.uniform([-1.5,-1.2,-1.],[1.5,1.2,1.]);offsets[9]=rng.uniform([-2.,-1.5,-1.],[2.,1.5,1.])
            t['node_offsets_mm']=offsets.tolist()
        if kind in ['reverse','shape_reverse']:t['output_sign']=-1
        t['description']='Revise the supplied previous design to satisfy this exact changed task. Preserve all unmodified constraints. Minimum volume with target-signed loaded output stroke; no privileged numerical answers.'
        cases.append(t)
    return cases


def bounds(t,ids):
    nodes,edges=geometry(t)
    return [(t['minimum_radius_mm'],min(t['maximum_radius_mm'],.5*t['maximum_diameter_length_ratio']*np.linalg.norm(nodes[edges[i][0]]-nodes[edges[i][1]]))) for i in ids]


def validate(t,ids,radii):
    nodes,options=geometry(t)
    if not ids or len(ids)!=len(set(ids)) or any(type(i) is not int or not 0<=i<len(options) for i in ids):raise ValueError('Unique allowed edge IDs required')
    if len(ids)!=len(radii):raise ValueError('One radius per edge')
    edges=[options[i] for i in ids]
    if not {4,9}<={v for e in edges for v in e}:raise ValueError('Both ports must be connected')
    for r,(lo,hi) in zip(radii,bounds(t,ids)):
        if not np.isfinite(r) or not lo-1e-9<=r<=hi+1e-9:raise ValueError('Radius/feature/slenderness violation')
    for i,(a,b) in enumerate(edges):
        for j,(c,d) in enumerate(edges[:i]):
            if {a,b}&{c,d}:continue
            if segment_distance(nodes[a],nodes[b],nodes[c],nodes[d])<radii[i]+radii[j]+t['minimum_nonjoint_gap_mm']-1e-9:raise ValueError('Unjoined finite-radius collision')
    return nodes,edges


def compute(t,ids,radii,sensitivities=False):
    nodes,edges=validate(t,ids,radii);F=np.zeros(6*len(nodes));inp=6*t['input_node']+t['input_axis'];out=6*t['output_node']+t['output_axis']
    F[inp]=t['input_force_N'];springs=[(out,t['output_spring_N_mm'])]
    solved=solve(nodes,edges,radii,[0,1,2,3],F,t['E_N_mm2'],t['nu'],springs,sensitivities)
    u=solved['u'][:,0];stroke=t['output_sign']*float(u[out]);force=t['output_spring_N_mm']*stroke
    normal=0.;shear=0.;compression_ratio=0.;maxrotation=0.
    for r,(dofs,dk,T,kl,L),ends in zip(radii,solved['parts'],solved['end_forces']):
        A,I,J=section(r);end=ends[:,0]
        nominal=max(abs(end[0]),abs(end[6]))/(t['E_N_mm2']*A)+r*max(np.linalg.norm(end[[4,5]]),np.linalg.norm(end[[10,11]]))/(t['E_N_mm2']*I)
        normal=max(normal,nominal);G=t['E_N_mm2']/(2*(1+t['nu']));shear=max(shear,r*max(abs(end[3]),abs(end[9]))/(G*J))
        compression=max(0.,end[0],-end[6]);compression_ratio=max(compression_ratio,compression/(np.pi**2*t['E_N_mm2']*I/L**2))
        local=T@u[dofs]
        for s in np.linspace(0,1,17):
            dh=np.array([(-6*s+6*s*s)/L,1-4*s+3*s*s,(6*s-6*s*s)/L,-2*s+3*s*s])
            ry=-dh@(local[[2,4,8,10]]*[1,-1,1,-1]);rz=dh@local[[1,5,7,11]];rx=(1-s)*local[3]+s*local[9]
            maxrotation=max(maxrotation,float(np.linalg.norm([rx,ry,rz])))
    metrics={'loaded_stroke_mm':stroke,'output_force_N':force,'input_travel_mm':float(u[inp]),
             'parasitic_y_mm':float(u[6*t['output_node']+1]),'parasitic_x_mm':float(u[6*t['output_node']]),
             'volume_proxy_mm3':solved['volume'],'max_nodal_translation_mm':float(np.linalg.norm(u.reshape(-1,6)[:,:3],axis=1).max()),
             'sampled_max_section_rotation_rad':maxrotation,'max_nominal_normal_strain':float(normal),
             'max_nominal_torsional_shear_strain':float(shear),'max_compression_to_pinned_euler_ratio':float(compression_ratio),
             'input_ramp_work_N_mm':float(solved['input_ramp_work'][0]),'beam_energy_N_mm':float(solved['beam_energy'][0]),
             'output_spring_energy_N_mm':float(solved['spring_energy'][0]),'free_residual_inf_N_or_Nmm':solved['free_residual_inf']}
    limits=[('loaded_stroke_mm',t['minimum_loaded_stroke_mm'],1),('input_travel_mm',t['maximum_input_travel_mm'],-1),
            ('parasitic_y_mm',t['maximum_parasitic_y_mm'],-1),('parasitic_x_mm',t['maximum_parasitic_x_mm'],-1),
            ('max_nodal_translation_mm',t['maximum_nodal_translation_mm'],-1),('sampled_max_section_rotation_rad',t['maximum_section_rotation_rad'],-1),
            ('max_nominal_normal_strain',t['maximum_nominal_normal_strain'],-1),('max_nominal_torsional_shear_strain',t['maximum_nominal_torsional_shear_strain'],-1),
            ('max_compression_to_pinned_euler_ratio',t['maximum_compression_to_pinned_euler_ratio'],-1)]
    margins={name:sign*((metrics[name] if sign==1 else abs(metrics[name]))-limit)/limit for name,limit,sign in limits}
    work=metrics['input_ramp_work_N_mm'];metrics['spring_energy_fraction']=metrics['output_spring_energy_N_mm']/work if work>0 else None
    return {'metrics':metrics,'margins':margins,'feasible':all(v>=-1e-6 for v in margins.values()),'solved':solved,'loads':F,'springs':springs,'nodes':nodes,'edges':edges}
