"""Procedural 90-node spatial graph capability check, not AI discovery."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mechanical_workbench.physics import grid,evaluate,load_matrix
from research.spatial_external_check import compare
d,port=grid(10,3,3);nodes=np.array(d['nodes_mm'],float)
for i,p in enumerate(nodes):
    t=p[0]/108.;angle=.35*np.sin(np.pi*t);y,z=p[1],p[2];nodes[i,1]=np.cos(angle)*y-np.sin(angle)*z;nodes[i,2]=np.sin(angle)*y+np.cos(angle)*z+6*np.sin(np.pi*t)
d['nodes_mm']=nodes.tolist();d['label']='Twisted spatial reference assembly — procedural, not AI-discovered'
cases=[{'id':name,'loads':[{'node':port,'force_N':vector}]} for name,vector in [('axial',[.002,0,0]),('lateral',[0,.002,0]),('vertical',[0,0,.002])]]
requirements={'maximum_displacement_mm':.12,'maximum_nominal_normal_strain':.005,'maximum_nominal_shear_strain':.005,'maximum_section_rotation_rad':.03,'maximum_pinned_euler_ratio':.2,'material_E_relative_uncertainty':.05}
result=evaluate(d,cases,requirements);checks=[]
for case in cases:checks.append({'case':case['id'],**compare(nodes,[tuple(e) for e in d['edges']],d['radii_mm'],d['clamped_nodes'],load_matrix(nodes,[case]),d['E_N_mm2'],d['nu'])})
folder=ROOT/'examples/mechanical-workbench';folder.mkdir(parents=True,exist_ok=True);path=folder/'twisted-90-node.json'
path.write_text(json.dumps({'design':d,'load_cases':cases,'requirements':requirements,'provenance':'Procedural reference example. Independent ideal-law checks; no AI generation or physical validation.'},indent=2))
output=ROOT/'output/mechanical-workbench/large-example-check.json';output.write_text(json.dumps({'nodes':len(nodes),'members':len(d['edges']),'free_dofs':result['free_dofs'],'independent_check':result['independent_check'],'external_checks':checks,'external_checks_passed':all(c['passed'] for c in checks),'physical_validation':False,'AI_discovery':False,'new_Meta_calls':0,'result':result},indent=2))
print(json.dumps({'example':str(path),'nodes':len(nodes),'members':len(d['edges']),'free_dofs':result['free_dofs'],'independent_check':result['independent_check'],'OpenSees_passed':all(c['passed'] for c in checks),'maximum_displacement_mm':result['maximum_displacement_mm']}))
