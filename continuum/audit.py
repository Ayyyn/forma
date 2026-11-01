"""Independent numerical oracle using the unsimplified published unit-cell relations.

Never used to choose search proposals. Geometry.py's evaluator is not imported here.
"""
import math
import numpy as np


def reference_vertices(design, angle):
    # Schenk & Guest 2013, equations 1–4, evaluated in their unsimplified form.
    a,b,gamma,theta=design['a_mm'],design['b_mm'],math.radians(design['gamma_deg']),math.radians(angle)
    t=math.cos(theta)*math.tan(gamma)
    height=a*math.sin(theta)*math.sin(gamma)
    spacing=b*t/math.hypot(1,t)
    length=a*math.sqrt(1-math.sin(theta)**2*math.sin(gamma)**2)
    offset=b/math.hypot(1,t)
    return np.array([[i*length+(j%2)*offset,j*spacing,(i%2)*height]
                     for j in range(design['rows']+1) for i in range(design['columns']+1)])


def oracle(design, requirements):
    n,m=design['columns'],design['rows']
    faces=[[j*(n+1)+i,j*(n+1)+i+1,(j+1)*(n+1)+i+1,(j+1)*(n+1)+i] for j in range(m) for i in range(n)]
    extents={}
    for name,angle in [('deployed',design['deployed_theta_deg']),('packed',design['packed_theta_deg']),('flat',0)]:
        vertices=reference_vertices(design,angle)
        extents[name]=np.ptp(vertices,axis=0).tolist()
    flat=reference_vertices(design,0)
    area=sum(np.linalg.norm(np.cross(flat[f[1]]-flat[f[0]],flat[f[3]]-flat[f[0]])) for f in faces)
    d,p,f=extents['deployed'],extents['packed'],extents['flat']
    comparisons=[(d[0],requirements['deployed_x_min_mm'],True),(d[1],requirements['deployed_y_min_mm'],True),
        (max(p[:2]),requirements['packed_long_max_mm'],False),(min(p[:2]),requirements['packed_short_max_mm'],False),
        (p[2],requirements['packed_height_max_mm'],False),(f[0],requirements['blank_x_max_mm'],False),
        (f[1],requirements['blank_y_max_mm'],False),((n-1)*m+(m-1)*n,requirements['crease_segments_max'],False)]
    passed=[(value>=limit-1e-7) if lower else (value<=limit+1e-7) for value,limit,lower in comparisons]
    return {'feasible':all(passed),'constraint_passed':passed,'extents':extents,'material_area_mm2':float(area),
            'crease_segments':(n-1)*m+(m-1)*n,'packed_bounding_area_mm2':p[0]*p[1]}


def audit_record(record, requirements):
    independent=oracle(record['design'],requirements)
    comparisons=[]
    for state in ('deployed','packed','flat'):
        for axis,value in zip(('x_mm','y_mm','z_mm'),independent['extents'][state]):
            comparisons.append(abs(value-record['metrics'][state][axis]))
    area_delta=abs(independent['material_area_mm2']-record['metrics']['material_area_mm2'])
    flags=[c['passed'] for c in record['constraints']]
    passed=(max(comparisons)<1e-7 and area_delta<1e-6 and independent['feasible']==record['feasible']
            and flags==independent['constraint_passed'] and independent['crease_segments']==record['metrics']['crease_segments'])
    return {'passed':bool(passed),'max_extent_delta_mm':max(comparisons),'area_delta_mm2':area_delta,
            'feasibility_agrees':independent['feasible']==record['feasible']}
