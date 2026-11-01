"""Boolean-unioned finite panels: a fixed-pose display, never an actuator."""
import hashlib,json,platform,zipfile
from pathlib import Path
import cadquery as cq
import numpy as np
import trimesh
from .panels import flatten_triangle,bbox,save_set

def export_display(source,output,thickness=1.2):
    output=Path(output)
    if output.exists():raise ValueError('Existing output preserved')
    if source.get('kind')!='triangular_panel_kit' or not .4<=thickness<=3.:raise ValueError('Unsupported input or thickness')
    vertices=np.asarray(source['vertices_mm'],float);faces=np.asarray(source['triangles'])
    if vertices.ndim!=2 or vertices.shape[1]!=3 or not np.isfinite(vertices).all() or faces.ndim!=2 or faces.shape[1]!=3 or not np.issubdtype(faces.dtype,np.integer) or not 1<=len(faces)<=200 or faces.min()<0 or faces.max()>=len(vertices):raise ValueError('Invalid finite indexed triangles')
    solids=[];errors=[]
    for face in faces:
        p=vertices[face];_,_,error=flatten_triangle(p,thickness);errors.append(error)
        normal=np.cross(p[1]-p[0],p[2]-p[0]);normal/=np.linalg.norm(normal);lower=p-normal*thickness/2
        wire=cq.Wire.makePolygon([cq.Vector(*point) for point in lower],close=True)
        solid=cq.Solid.extrudeLinear(wire,[],cq.Vector(*(normal*thickness)))
        if not solid.isValid() or len(solid.Solids())!=1:raise ValueError('Invalid individual panel prism')
        solids.append(solid)
    # Intentional union at panel intersections creates a rigid display body.
    # This changes joint/crease geometry; no mechanical equivalence is claimed.
    joined=solids[0].fuse(*solids[1:]).clean()
    if not joined.isValid() or len(joined.Solids())!=1:raise ValueError('Display union did not create exactly one valid solid')
    before=bbox(joined);translation=[0.,0.,-float(before[0,2])];joined=joined.translate(tuple(translation))
    output.mkdir(parents=True);geometry=save_set(joined,output,'static-display',1)
    area_sum=sum(float(.5*np.linalg.norm(np.cross(vertices[f][1]-vertices[f][0],vertices[f][2]-vertices[f][0]))) for f in faces)
    volume_before=area_sum*thickness;volume_after=geometry['volume_mm3']
    if not 0<volume_after<=volume_before*(1+1e-8):raise ValueError('Union volume outside independent panel-volume bound')
    manifest={'kind':'single fixed-pose solid display','geometry_checks_passed':all(v['passed'] for v in geometry['checks'].values()),'source':source['provenance'],'source_state':source['source_state'],
              'units':'mm; import STL/OBJ as millimetres','panel_thickness_mm':thickness,'thickness_is_export_assumption':True,'source_panel_count':len(faces),'parts_count':1,'bed_translation_mm':translation,'volume_before_union_mm3':volume_before,'overlap_volume_removed_mm3':volume_before-volume_after,
              'mechanical_status':'RIGID STATIC DISPLAY ONLY. Panels were deliberately fused; no folding, switching, energy landscape or actuator performance is reproduced. Added thickness/joints are outside the mechanics model.',
              'printer_profile':'not decided','supports_orientation_and_slicing':'not validated; choose with the printer/material','hardware_tests':0,'maximum_source_triangle_mapping_error_mm':max(errors),
              'runtime':{'python':platform.python_version(),'cadquery':cq.__version__,'trimesh':trimesh.__version__},'exporter_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'assembly':geometry}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2));(output/'source-geometry.json').write_text(json.dumps(source,indent=2))
    (output/'exporter-source.py').write_bytes(Path(__file__).read_bytes())
    (output/'README.txt').write_text(f'''FIXED-POSE STATIC DISPLAY — NOT A FOLDING MECHANISM

This is one CAD solid formed by thickening each source facet symmetrically and
Boolean-unioning all the panels. Source coordinates are in millimetres. A rigid
translation places the lowest exported point at z=0. Read manifest.json for
dimensions, volume, thickness, removed overlap and geometry round-trip checks.

STL and OBJ: import as MILLIMETRES. STEP contains explicit millimetre units.
The selected pose comes from an ideal zero-thickness reduced mechanical model.
The {thickness:g} mm display walls and fused joints are added export assumptions. This
display cannot fold or switch; its strength and load response are not modeled.
No printer/material, support strategy, orientation or slicing profile has been
validated. Check those in your slicer before printing. No physical tests exist.
Attribution and the original computed state are in source-geometry.json.
''')
    for extension in ['step','stl','obj']:
        with zipfile.ZipFile(output/(extension+'-bundle.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
            for p in [output/('static-display.'+extension),output/'manifest.json',output/'source-geometry.json',output/'README.txt']:archive.write(p,p.name)
    return manifest
