"""Development-only loaded spatial compliant transmission; exact graph language."""
from itertools import combinations
import numpy as np
from scipy.optimize import lsq_linear
from .mechanics import solve,section


def geometry():
    nodes=[[0,-8,-8],[0,8,-8],[0,-8,8],[0,8,8],[18,0,0],
           [20,-8,0],[20,8,0],[24,-8,12],[24,8,12],[40,0,8]]
    edges=[(a,b) for a in range(4) for b in range(4,9)]
    edges+=list(combinations(range(4,9),2));edges +=[(a,9) for a in range(4,9)]
    return nodes,edges


def catalogue():
    _,edges=geometry();lookup={e:i for i,e in enumerate(edges)}
    def ids(ee):return sorted(lookup[tuple(sorted(e))] for e in ee)
    result={}
    # Wide conventional development control: every anchor pair drives a common
    # input junction and distinct output; plus four separated spatial forks.
    for a,b in combinations(range(4),2):result[f'anchor_pair_{a}_{b}']=ids([(a,4),(b,4),(4,9)])
    for a,b,c,d in [(0,1,5,6),(2,3,7,8),(0,3,5,8),(1,2,6,7)]:
        result[f'fork_{a}_{b}']=ids([(a,c),(b,d),(c,4),(d,4),(c,9),(d,9)])
        result[f'braced_fork_{a}_{b}']=ids([(a,c),(b,d),(c,4),(d,4),(c,9),(d,9),(c,d)])
    result['four_anchor_chain']=ids([(a,4) for a in range(4)]+[(4,9)])
    return result


def task():
    return {'id':'loaded_spatial_converter_development','E_N_mm2':2000.,'nu':.3,
            'input_node':4,'input_axis':0,'input_force_N':.002,'output_node':9,'output_axis':2,
            'output_spring_N_mm':.02,'minimum_loaded_stroke_mm':.02,
            'maximum_input_travel_mm':.04,'maximum_parasitic_y_mm':.01,'maximum_parasitic_x_mm':.008,
            'maximum_nodal_translation_mm':.25,'maximum_section_rotation_rad':.02,
            'maximum_nominal_normal_strain':.001,'maximum_nominal_torsional_shear_strain':.002,
            'maximum_compression_to_pinned_euler_ratio':.1,
            'minimum_radius_mm':.35,'maximum_radius_mm':.9,
            'maximum_diameter_length_ratio':.1,'minimum_nonjoint_gap_mm':.05,
            'description':'Minimize summed circular beam volume while an external +x input force produces positive z stroke against a grounded output spring. Passive linear transmission, synthetic material.',
            'physical_measurements':False}


def bounds(t,ids):
    nodes,edges=geometry();nodes=np.array(nodes)
    return [(t['minimum_radius_mm'],min(t['maximum_radius_mm'],.5*t['maximum_diameter_length_ratio']*np.linalg.norm(nodes[edges[i][0]]-nodes[edges[i][1]]))) for i in ids]


def segment_distance(a,b,c,d):
    # Convex bounded least squares includes interior, endpoint and parallel cases.
    delta=np.asarray(a)-c;matrix=np.column_stack((np.asarray(b)-a,np.asarray(c)-d))
    fit=lsq_linear(matrix,-delta,bounds=(0,1),tol=1e-12)
    return float(np.linalg.norm(matrix@fit.x+delta))


def validate(t,ids,radii):
    nodes,all_edges=geometry();nodes=np.array(nodes,dtype=float)
    if not ids or len(ids)!=len(set(ids)) or any(type(i) is not int or not 0<=i<len(all_edges) for i in ids):raise ValueError('Nonempty unique allowed edge IDs required')
    if len(ids)!=len(radii):raise ValueError('One radius per edge required')
    edges=[all_edges[i] for i in ids];used={v for e in edges for v in e}
    if not {t['input_node'],t['output_node']}<=used:raise ValueError('Both ports must be connected')
    for r,(lo,hi) in zip(radii,bounds(t,ids)):
        if not np.isfinite(r) or not lo-1e-9<=r<=hi+1e-9:raise ValueError('Radius/feature/slenderness bound')
    for k,(a,b) in enumerate(edges):
        for j,(c,d) in enumerate(edges[:k]):
            if {a,b}&{c,d}:continue # Ideal joined envelopes overlap at declared nodes.
            if segment_distance(nodes[a],nodes[b],nodes[c],nodes[d])<radii[k]+radii[j]+t['minimum_nonjoint_gap_mm']-1e-9:
                raise ValueError('Unjoined finite-radius member envelopes collide')
    return nodes,edges


def compute(t,ids,radii,sensitivities=False):
    nodes,edges=validate(t,ids,radii);F=np.zeros(6*len(nodes));inp=6*t['input_node']+t['input_axis'];out=6*t['output_node']+t['output_axis']
    F[inp]=t['input_force_N'];springs=[(out,t['output_spring_N_mm'])]
    solved=solve(nodes,edges,radii,[0,1,2,3],F,t['E_N_mm2'],t['nu'],springs,sensitivities)
    u=solved['u'][:,0];stroke=float(u[out]);force=t['output_spring_N_mm']*stroke
    normal=0.;shear=0.;buckling=0.;maxrotation=0.
    for r,(dofs,dk,T,kl,L),ends in zip(radii,solved['parts'],solved['end_forces']):
        A,I,J=section(r);end=ends[:,0]
        normal=max(normal,max(abs(end[0]),abs(end[6]))/(t['E_N_mm2']*A)+r*max(np.linalg.norm(end[[4,5]]),np.linalg.norm(end[[10,11]]))/(t['E_N_mm2']*I))
        G=t['E_N_mm2']/(2*(1+t['nu']));shear=max(shear,r*max(abs(end[3]),abs(end[9]))/(G*J))
        compression=max(0.,end[0],-end[6]);buckling=max(buckling,compression/(np.pi**2*t['E_N_mm2']*I/L**2))
        local=T@u[dofs]
        # EB cross-section rotations between nodes, quadratic shape derivatives.
        # Max norm sampled at 17 sites; report as a sampled linearity guard.
        for x in np.linspace(0,1,17):
            dH=np.array([(-6*x+6*x*x)/L,1-4*x+3*x*x,(6*x-6*x*x)/L,-2*x+3*x*x])
            rz=dH@local[[1,5,7,11]];ry=-dH@(local[[2,4,8,10]]*[1,-1,1,-1]);rx=(1-x)*local[3]+x*local[9]
            maxrotation=max(maxrotation,float(np.linalg.norm([rx,ry,rz])))
    metrics={'loaded_stroke_mm':stroke,'output_force_N':force,'input_travel_mm':float(u[inp]),
             'parasitic_y_mm':float(u[6*t['output_node']+1]),'parasitic_x_mm':float(u[6*t['output_node']]),'volume_proxy_mm3':solved['volume'],
             'max_nodal_translation_mm':float(np.linalg.norm(u.reshape(-1,6)[:,:3],axis=1).max()),
             'sampled_max_section_rotation_rad':maxrotation,'max_nominal_normal_strain':normal,
             'max_nominal_torsional_shear_strain':shear,'max_compression_to_pinned_euler_ratio':buckling,
             'input_ramp_work_N_mm':float(solved['input_ramp_work'][0]),'beam_energy_N_mm':float(solved['beam_energy'][0]),
             'output_spring_energy_N_mm':float(solved['spring_energy'][0]),
             'free_residual_inf_N_or_Nmm':solved['free_residual_inf']}
    limits=[('loaded_stroke_mm',t['minimum_loaded_stroke_mm'],1),('input_travel_mm',t['maximum_input_travel_mm'],-1),
            ('parasitic_y_mm',t['maximum_parasitic_y_mm'],-1),('parasitic_x_mm',t['maximum_parasitic_x_mm'],-1),('max_nodal_translation_mm',t['maximum_nodal_translation_mm'],-1),
            ('sampled_max_section_rotation_rad',t['maximum_section_rotation_rad'],-1),('max_nominal_normal_strain',t['maximum_nominal_normal_strain'],-1),
            ('max_nominal_torsional_shear_strain',t['maximum_nominal_torsional_shear_strain'],-1),('max_compression_to_pinned_euler_ratio',t['maximum_compression_to_pinned_euler_ratio'],-1)]
    margins={name:sign*((metrics[name] if sign==1 else abs(metrics[name]))-bound)/bound for name,bound,sign in limits}
    feasible=all(v>=-1e-6 for v in margins.values())
    work=metrics['input_ramp_work_N_mm'];metrics['spring_energy_fraction']=metrics['output_spring_energy_N_mm']/work if work>0 else None
    return {'metrics':metrics,'margins':margins,'feasible':feasible,'solved':solved,'loads':F,'springs':springs,'nodes':nodes,'edges':edges}
