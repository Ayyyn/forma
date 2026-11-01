"""Public graph language, conventional templates and exact synthetic tasks."""
import numpy as np


def geometry(length=40.,height=20.):
    nodes=[[i*length/2,(j-1)*height/2] for i in range(3) for j in range(3)]
    edges=[(3*i+j,3*(i+1)+j) for i in range(2) for j in range(3)]
    edges += [(3*i+j,3*i+j+1) for i in [1,2] for j in range(2)]
    edges += [(3*i+j,3*(i+1)+j+1) for i in range(2) for j in range(2)]
    edges += [(3*i+j+1,3*(i+1)+j) for i in range(2) for j in range(2)]
    return nodes,edges


def templates():
    spine=[(1,4),(4,7)]
    up=[(2,5),(5,8),(7,8)]
    down=[(0,3),(3,6),(6,7)]
    shapes={'straight_beam':spine,'upper_frame':up,'lower_frame':down,'dual_rail':up+down,
       'upper_triangulated':spine+up+[(2,4),(4,8)],
       'lower_triangulated':spine+down+[(0,4),(4,6)],
       'ladder_frame':up+down+[(3,4),(4,5)],
       'diagonal_path':[(0,4),(4,8),(7,8)]}
    _,allowed=geometry();lookup={tuple(sorted(e)):i for i,e in enumerate(allowed)}
    return {name:sorted(lookup[tuple(sorted(e))] for e in edges) for name,edges in shapes.items()}


def public_geometry(task):
    nodes,edges=geometry(task['length_mm'],task['height_mm'])
    return {'nodes_mm':nodes,'edge_options':[{'id':i,'nodes':list(e)} for i,e in enumerate(edges)],
            'clamped_nodes':[0,1,2],'output_node':7,'templates':templates(),
            'E_N_per_mm2':2000.,'out_of_plane_depth_mm':3.,
            'minimum_width_mm':.4,'maximum_width_mm':2.,'maximum_width_to_length_ratio':.1}


def bounds(task,edge_ids):
    nodes,edges=geometry(task['length_mm'],task['height_mm']);nodes=np.array(nodes)
    return [( .4,min(2.,.1*float(np.linalg.norm(nodes[edges[i][1]]-nodes[edges[i][0]])))) for i in edge_ids]


def validate_graph(task,edge_ids,widths):
    nodes,all_edges=geometry(task['length_mm'],task['height_mm'])
    if not edge_ids or len(edge_ids)!=len(set(edge_ids)):raise ValueError('Nonempty unique edge IDs required')
    if len(edge_ids)!=len(widths) or any(type(i) is not int or not 0<=i<len(all_edges) for i in edge_ids):raise ValueError('Invalid edges/width count')
    nodes=np.array(nodes);edges=[all_edges[i] for i in edge_ids]
    for w,(lo,hi) in zip(widths,bounds(task,edge_ids)):
        if not np.isfinite(w) or not lo-1e-8<=w<=hi+1e-8:raise ValueError('Width outside feature/slenderness bounds')
    # Diagonals crossing inside a grid cell would physically intersect. Without
    # an explicit joint node that is a different model, so reject that graph.
    def cross(a,b):return float(a[0]*b[1]-a[1]*b[0])
    for ei,(a,b) in enumerate(edges):
        for c,d in edges[ei+1:]:
            if {a,b}&{c,d}:continue
            A,B,C,D=nodes[[a,b,c,d]]
            if cross(B-A,C-A)*cross(B-A,D-A)<-1e-12 and cross(D-C,A-C)*cross(D-C,B-C)<-1e-12:
                raise ValueError('Crossing members require an unmodeled joint')
    # Clearance uses member envelope, not only the zero-width centerline.
    gap=task.get('central_gap_half_height_mm',0.)
    if gap:
        xmin=.2*task['length_mm'];xmax=.8*task['length_mm']
        for (a,b),w in zip(edges,widths):
            A,B=nodes[[a,b]];delta=B-A
            lower=np.array([xmin-w/2,-gap-w/2]);upper=np.array([xmax+w/2,gap+w/2])
            t0=0.;t1=1.
            for j in range(2):
                if abs(delta[j])<1e-14:
                    if A[j]<lower[j] or A[j]>upper[j]:t0=2.;break
                else:
                    s=sorted([(lower[j]-A[j])/delta[j],(upper[j]-A[j])/delta[j]])
                    t0=max(t0,s[0]);t1=min(t1,s[1])
            if t0<=t1:raise ValueError('Member envelope intersects reserved central channel')
    return nodes,edges


def task_cases():
    # Development tasks, not hidden clinical/material specifications.
    base={'length_mm':40.,'height_mm':20.,'actual_test_force_N':.01,
          'max_displacement_mm':.2,'max_rotation_rad':.02,
          'central_gap_half_height_mm':0.,'physical_data':False}
    return [dict(base,id='motion_coupler',requirements=[{'quantity':'Cxy','lower':1.},{'quantity':'Cxx','upper':2.},{'quantity':'Cyy','upper':8.}],description='Minimize beam-volume proxy; a positive x-directed load must produce positive y motion, with bounded compliance in both axes.'),
            dict(base,id='stiff_mount',requirements=[{'quantity':'Cxx','upper':.05},{'quantity':'Cyy','upper':.08}],description='Minimize beam-volume proxy while stiff under separate x/y loads.'),
            dict(base,id='directional_flexure',requirements=[{'quantity':'Cxx','upper':.04},{'quantity':'Cyy','lower':4.,'upper':12.}],description='Minimize beam-volume proxy; stiff along x but deliberately compliant along y.'),
            dict(base,id='clear_channel',central_gap_half_height_mm=3.,requirements=[{'quantity':'Cxx','upper':.15},{'quantity':'Cyy','upper':8.}],description='Minimize beam-volume proxy with a reserved central channel and bounded x/y compliance.')]


def constraint_values(task,C,gradient):
    pos={'Cxx':(0,0),'Cyy':(1,1),'Cxy':(0,1)};values=[];derivatives=[];labels=[]
    for item in task['requirements']:
        row,col=pos[item['quantity']];v=C[row,col];g=gradient[:,row,col]
        for bound,sign in [('upper',-1.),('lower',1.)]:
            if bound not in item:continue
            scale=max(abs(item[bound]),1e-6)
            values.append(sign*(v-item[bound])/scale);derivatives.append(sign*g/scale)
            labels.append(item['quantity']+'_'+bound)
    return np.array(values),np.array(derivatives),labels
