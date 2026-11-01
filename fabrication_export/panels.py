"""Finite solid panel parts, true STEP and round-trip-checked triangle meshes.

Run in the isolated CAD runtime. No model/API calls or mechanics are performed.
Triangle edge lengths are preserved; the solid thickness is an export assumption.
These parts are a static geometry kit, not a validated folding mechanism.
"""
import hashlib,json,math,platform,zipfile
from pathlib import Path
import cadquery as cq
import numpy as np
import trimesh

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def flatten_triangle(points,thickness):
    p=np.asarray(points,dtype=float)
    if p.shape!=(3,3) or not np.isfinite(p).all():raise ValueError('Three finite 3D vertices required')
    ex=p[1]-p[0];length=np.linalg.norm(ex)
    if length<1e-5:raise ValueError('Degenerate edge')
    ex/=length;n=np.cross(ex,p[2]-p[0]);height=np.linalg.norm(n)
    if height<1e-5:raise ValueError('Degenerate triangle')
    n/=height;ey=np.cross(n,ex);x=float(np.dot(p[2]-p[0],ex));y=float(np.dot(p[2]-p[0],ey));shift=max(0.,-x)
    flat=np.array([[shift,0.],[length+shift,0.],[x+shift,y]])
    transform=np.eye(4);transform[:3,:3]=np.column_stack([ex,ey,n]);transform[:3,3]=p[0]-shift*ex-thickness*n/2
    reconstructed=np.column_stack([flat,np.full(3,thickness/2)])@transform[:3,:3].T+transform[:3,3]
    error=float(np.max(np.linalg.norm(reconstructed-p,axis=1)))
    if error>1e-8:raise ValueError('Flattening changes triangle dimensions')
    return flat,transform,error

def bbox(shape):
    b=shape.BoundingBox();return np.array([[b.xmin,b.ymin,b.zmin],[b.xmax,b.ymax,b.zmax]])

def mesh_from_shape(shape):
    vertices,faces=shape.tessellate(.05,.1)
    mesh=trimesh.Trimesh(vertices=np.array([v.toTuple() for v in vertices]),faces=np.array(faces),process=True)
    if not mesh.is_watertight or not mesh.is_winding_consistent or not mesh.is_volume:raise ValueError('CAD tessellation is not a closed consistently oriented volume')
    return mesh

def check_mesh(mesh,expected_bounds,expected_volume,solids):
    edge_counts=np.bincount(mesh.edges_unique_inverse)
    volume_error=abs(float(mesh.volume)-expected_volume)/expected_volume
    bounds_error=float(abs(mesh.bounds-expected_bounds).max())
    count=len(mesh.split(only_watertight=False))
    result={'watertight':bool(mesh.is_watertight),'winding_consistent':bool(mesh.is_winding_consistent),'positive_closed_volume':bool(mesh.is_volume),'all_edges_have_two_incident_faces':bool(np.all(edge_counts==2)),
            'connected_components':count,'expected_components':solids,'volume_mm3':float(mesh.volume),'relative_volume_error':volume_error,'max_bounds_error_mm':bounds_error,'bounds_mm':mesh.bounds.tolist()}
    result['passed']=bool(all(result[k] for k in ['watertight','winding_consistent','positive_closed_volume','all_edges_have_two_incident_faces']) and count==solids and volume_error<1e-5 and bounds_error<1e-4)
    if not result['passed']:raise ValueError('Mesh round-trip failed: '+json.dumps(result))
    return result

def save_set(shape,folder,stem,parts=1):
    folder.mkdir(parents=True,exist_ok=True);expected_bbox=bbox(shape);volume=float(shape.Volume())
    if not shape.isValid() or len(shape.Solids())!=parts or volume<=0:raise ValueError('Invalid or non-solid CAD shape')
    step=folder/(stem+'.step');cq.exporters.export(shape,str(step),exportType='STEP')
    restored=cq.importers.importStep(str(step)).val();step_err=abs(float(restored.Volume())-volume)/volume;bounds_err=float(abs(bbox(restored)-expected_bbox).max())
    unit_mm="SI_UNIT(.MILLI.,.METRE.)" in step.read_text().replace(' ','').replace('\n','')
    step_check={'valid_BREP':bool(restored.isValid()),'solid_count':len(restored.Solids()),'relative_volume_error':step_err,'max_bounds_error_mm':bounds_err,'explicit_millimetre_units':unit_mm,'passed':bool(restored.isValid() and len(restored.Solids())==parts and step_err<1e-8 and bounds_err<1e-6 and unit_mm)}
    if not step_check['passed']:raise ValueError('STEP round-trip failed: '+json.dumps(step_check))
    mesh=mesh_from_shape(shape);checks={'step':step_check};files={}
    for suffix in ['stl','obj']:
        file=folder/(stem+'.'+suffix)
        if suffix=='obj':file.write_text('# Units: millimetres (mm). Static panel geometry; no hinge mechanics.\n'+trimesh.exchange.obj.export_obj(mesh),encoding='utf-8')
        else:mesh.export(str(file),file_type='stl')
        restored_mesh=trimesh.load_mesh(str(file),process=True);checks[suffix]=check_mesh(restored_mesh,expected_bbox,volume,parts)
    for suffix in ['step','stl','obj']:
        p=folder/(stem+'.'+suffix);files[suffix]={'name':p.name,'sha256':digest(p),'bytes':p.stat().st_size}
    return {'volume_mm3':volume,'bounds_mm':expected_bbox.tolist(),'checks':checks,'files':files}

def export_kit(source,output,thickness=1.2,spacing=5.,columns=8):
    output=Path(output)
    if output.exists():raise ValueError('Preserve existing export; use a new output directory')
    if not .4<=thickness<=3 or not 1<=spacing<=20 or not 1<=columns<=12:raise ValueError('Invalid export dimensions/layout')
    if source.get('kind')!='triangular_panel_kit':raise ValueError('Unsupported geometry kind')
    vertices=np.asarray(source['vertices_mm'],float);faces=np.asarray(source['triangles'])
    if not np.issubdtype(faces.dtype,np.integer) or np.issubdtype(faces.dtype,np.bool_):raise ValueError('Triangle indices must be integers; refusing silent truncation')
    if vertices.ndim!=2 or vertices.shape[1]!=3 or not np.isfinite(vertices).all() or faces.ndim!=2 or faces.shape[1]!=3 or not 1<=len(faces)<=200 or faces.min()<0 or faces.max()>=len(vertices):raise ValueError('Invalid finite triangular geometry')
    prepared=[]
    for face in faces:
        flat,transform,error=flatten_triangle(vertices[face],thickness);prepared.append((flat,transform,error))
    width=max(float(flat[:,0].max()) for flat,_,_ in prepared)+spacing;height=max(float(flat[:,1].max()) for flat,_,_ in prepared)+spacing
    output.mkdir(parents=True);parts=[];placed=[];volumes=[]
    for i,(flat,transform,error) in enumerate(prepared):
        shape=cq.Workplane('XY').polyline(flat.tolist()).close().extrude(thickness).val();name=f'cell-{i//12+1}-panel-{i%12+1:02d}'
        check=save_set(shape,output/'parts',name);location=[(i%columns)*width,(i//columns)*height,0.];placed.append(shape.translate(tuple(location)));volumes.append(shape.Volume())
        parts.append({'id':name,'source_face_index':i,'source_vertex_indices':faces[i].tolist(),'layout_translation_mm':location,'flat_reference_outline_mm':flat.tolist(),'flat_solid_to_source_pose_transform':transform.tolist(),'triangle_reconstruction_error_mm':error,**check})
    compound=cq.Compound.makeCompound(placed)
    # Axis-aligned layout cells are separated by >= spacing; no Boolean union,
    # mesh repair or implicit physical joint is introduced.
    for i,shape in enumerate(placed):
        for other in placed[:i]:
            a,b=bbox(shape),bbox(other)
            if np.all(np.minimum(a[1],b[1])-np.maximum(a[0],b[0])>1e-7):raise ValueError('Panel layout bounding boxes overlap')
    assembly=save_set(compound,output,'panel-kit',len(parts));all_pass=all(v['passed'] for v in assembly['checks'].values()) and all(all(v['passed'] for v in p['checks'].values()) for p in parts)
    manifest={'kind':'finite-thickness static triangular panel kit','mechanical_status':'NOT a validated folding assembly, actuator, or reproduction of reduced-model energy. No hinges, guide, spring hardware or assembly clearances are designed.',
              'source':source.get('provenance'),'source_state':source.get('source_state'),'units':'mm; STL and OBJ have no enforced unit system: import as millimetres','panel_thickness_mm':thickness,'thickness_is_export_assumption':True,'layout_spacing_mm':spacing,'layout_columns':columns,'parts_count':len(parts),'printer_profile':'unconfirmed','minimum_printer_feature_validation':'not performed','hardware_tests':0,
              'geometry_checks_passed':bool(all_pass),'layout_nonoverlap_check':'all pairwise positive-volume axis-aligned bounding-box overlaps absent; separated planar panels',
              'limitations':['Panels preserve each selected deformed triangle, not an unstretched common sheet or a crease pattern.','Disconnected components are deliberate individual parts; the full layout is not a monolithic device.','The full layout may exceed a print bed: individual part files are included.','Water-tightness is a topology check, not material performance or universal printer compatibility.','STEP is exported from CAD solids, not a renamed or faceted mesh. Meshes are tessellated from those same solids.'],
              'runtime':{'python':platform.python_version(),'cadquery':cq.__version__,'trimesh':trimesh.__version__,'numpy':np.__version__},'assembly':assembly,'parts':parts}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2));(output/'source-geometry.json').write_text(json.dumps(source,indent=2))
    readme=f'''STATIC PANEL KIT — GEOMETRY CHECKED, PHYSICAL DEVICE UNVALIDATED

{len(parts)} separate triangular prisms, thickness {thickness} mm. Source pose,
part mapping and rigid transforms are in manifest.json. Each panel preserves
the three edge lengths of one triangle in the selected computed configuration.
The added thickness is NOT included in the reduced mechanical model.

Use individual files in parts/ for a print bed. panel-kit.* is a full layout;
its dimensions may exceed your bed. Import STL and OBJ in MILLIMETRES.
STEP contains millimetre units and exact planar CAD solids. All three formats
were independently re-imported for geometry, solid-count and volume checks.

No hinges, compliant joints, guide, preload hardware, spring routing or assembly
instructions are provided. Parts do not establish that the simulated device can
fold, retain a state or bear load. Printer/material profile is unconfirmed.
Do not use this educational static kit as a medical or safety-critical device.
Read source-geometry.json and manifest.json for assumptions and attribution.
'''
    (output/'README.txt').write_text(readme)
    for extension in ['step','stl','obj']:
        with zipfile.ZipFile(output/(extension+'-bundle.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
            for p in [output/('panel-kit.'+extension),output/'manifest.json',output/'source-geometry.json',output/'README.txt',*sorted((output/'parts').glob('*.'+extension))]:archive.write(p,p.relative_to(output))
    return manifest
