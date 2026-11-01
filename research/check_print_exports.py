"""Independent artifact-level geometry/mapping/hash/ZIP checks; no CAD or AI calls."""
import hashlib,json,zipfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
for path in sorted((ROOT/'output/discovery-board/exports').glob('*/manifest.json')):
    manifest=json.loads(path.read_text());source=json.loads((path.parent/'source-geometry.json').read_text());vertices=np.array(source['vertices_mm']);faces=np.array(source['triangles']);largest_edge=0.;largest_reconstruction=0.;largest_volume=0.;total=0.;files=[]
    display=manifest['kind']=='single fixed-pose solid display'
    for part in manifest.get('parts',[]):
        original=vertices[faces[part['source_face_index']]];flat=np.array(part['flat_reference_outline_mm']);expected=.5*np.linalg.norm(np.cross(original[1]-original[0],original[2]-original[0]))*manifest['panel_thickness_mm'];largest_volume=max(largest_volume,abs(part['volume_mm3']-expected)/expected);total+=expected
        for i,j in [(0,1),(1,2),(2,0)]:largest_edge=max(largest_edge,abs(np.linalg.norm(original[i]-original[j])-np.linalg.norm(flat[i]-flat[j])))
        transform=np.array(part['flat_solid_to_source_pose_transform']);coordinates=np.column_stack([flat,np.full(3,manifest['panel_thickness_mm']/2),np.ones(3)]);restored=(transform@coordinates.T).T[:,:3];largest_reconstruction=max(largest_reconstruction,float(abs(restored-original).max()))
        for file in part['files'].values():
            p=path.parent/'parts'/file['name'];assert sha(p)==file['sha256'];files.append(p)
    for file in manifest['assembly']['files'].values():
        p=path.parent/file['name'];assert sha(p)==file['sha256'];files.append(p)
    bundles={}
    for fmt in ['step','stl','obj']:
        p=path.parent/(fmt+'-bundle.zip')
        with zipfile.ZipFile(p) as archive:
            assert archive.testzip() is None
            expected=[f for f in files if f.suffix=='.'+fmt]+[path,path.parent/'source-geometry.json',path.parent/'README.txt']
            for f in expected:assert archive.read(f.relative_to(path.parent).as_posix())==f.read_bytes()
            assert len(archive.namelist())==len(expected)
        bundles[fmt]={'sha256':sha(p),'bytes':p.stat().st_size,'members':len(expected)}
    if display:
        total=sum(float(.5*np.linalg.norm(np.cross(vertices[f][1]-vertices[f][0],vertices[f][2]-vertices[f][0]))) for f in faces)*manifest['panel_thickness_mm']
        passed=bool(abs(total-manifest['volume_before_union_mm3'])/total<1e-10 and 0<manifest['assembly']['volume_mm3']<=total*(1+1e-8) and sha(path.parent/'exporter-source.py')==manifest['exporter_source_sha256'] and manifest['assembly']['bounds_mm'][0][2]>=-1e-8)
    else:passed=bool(largest_edge<1e-8 and largest_reconstruction<1e-8 and largest_volume<1e-10 and abs(total-manifest['assembly']['volume_mm3'])/total<1e-10)
    assert passed
    checks.append({'export':path.parent.name,'purpose':manifest['kind'],'passed':passed,'parts':manifest['parts_count'],'three_format_files_hash_checked':len(files),'maximum_edge_length_error_mm':None if display else float(largest_edge),'maximum_source_pose_reconstruction_error_mm':None if display else largest_reconstruction,'maximum_part_volume_relative_error':None if display else float(largest_volume),'panel_volume_before_union_mm3':float(total),'actual_solid_volume_mm3':manifest['assembly']['volume_mm3'],'bundles':bundles})
result={'passed':bool(checks and all(c['passed'] for c in checks)),'checks':checks,'new_model_API_calls':0,'new_equilibrium_solves':0,'scope':'Artifact geometry/mapping, source-triangle area, all format file hashes and ZIP member checks. CAD/mesh re-import checks were recorded during export, not repeated here. Printer/material and mechanical device validation remain outstanding.'}
(ROOT/'output/discovery-board/print-integrity-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed'],'kits':len(checks),'parts_checked':sum(c['parts'] for c in checks),'format_files_checked':sum(c['three_format_files_hash_checked'] for c in checks)}))
