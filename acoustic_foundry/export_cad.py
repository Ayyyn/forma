"""Export split prototype modules. Geometry verification is not acoustic validation."""
import argparse
import hashlib
import json
from pathlib import Path
import cadquery as cq
import trimesh


def export(design_path, output):
    design=json.loads(Path(design_path).read_text())
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    if design['duct_diameter_mm']!=40:raise ValueError('This prototype fixture supports a 40 mm bore')
    parts=[];checks=[];instructions=[]
    for i,cell in enumerate(design['cells']):
        x=cell['position_mm'];length=cell['neck_length_mm'];r=cell['neck_radius_mm']
        depth=cell['volume_cm3']*1000/(32*32)
        end=20+length+depth+4
        # Solid rectangular exterior permits a flat print base for each half.
        block=cq.Workplane('XY').box(42,end+26,48).translate((x,(end-26)/2,0)).val()
        bore=cq.Solid.makeCylinder(20,44,cq.Vector(x-22,0,0),cq.Vector(1,0,0))
        neck=cq.Solid.makeCylinder(r,length+2,cq.Vector(x,19,0),cq.Vector(0,1,0))
        cavity=cq.Workplane('XY').box(32,depth,32).translate((x,20+length+depth/2,0)).val()
        solid=block.cut(bore).cut(neck).cut(cavity)
        for dx in [-17,17]:
            for y in [-23,end-2.5]:
                solid=solid.cut(cq.Solid.makeCylinder(1.6,50,cq.Vector(x+dx,y,-25),cq.Vector(0,0,1)))
        for side,z in [('lower',-12),('upper',12)]:
            clip=cq.Workplane('XY').box(44,end+28,24).translate((x,(end-26)/2,z)).val()
            shape=solid.intersect(clip)
            if not shape.isValid() or len(shape.Solids())!=1:raise RuntimeError('Invalid split module')
            name=f'module-{i+1}-{side}'
            cq.exporters.export(shape,str(out/f'{name}.step'))
            # Both STL halves are open-side-up with their flat bases at z=0.
            printable=shape if side=='lower' else shape.mirror('XY')
            printable=printable.translate(cq.Vector(-x,26,24))
            cq.exporters.export(printable,str(out/f'{name}.stl'),tolerance=.03,angularTolerance=.08)
            mesh=trimesh.load(out/f'{name}.stl',force='mesh')
            restored=cq.importers.importStep(str(out/f'{name}.step')).val()
            err=abs(restored.Volume()-shape.Volume())/shape.Volume()
            check={'part':name,'brep_valid':shape.isValid(),'step_roundtrip_valid':restored.isValid(),
                   'step_relative_volume_error':err,'stl_watertight':bool(mesh.is_watertight),
                   'stl_winding_consistent':bool(mesh.is_winding_consistent),
                   'solid_volume_cm3':shape.Volume()/1000}
            check['passed']=all([check['brep_valid'],check['step_roundtrip_valid'],err<1e-8,
                                 check['stl_watertight'],check['stl_winding_consistent']])
            checks.append(check);parts.append(shape)
        instructions.append({'module':i+1,'neck_radius_mm':r,'neck_length_mm':length,
              'cavity_dimensions_mm':[32,depth,32],'cavity_volume_cm3':32*depth*32/1000,
              'pitch_mm':42,'bore_diameter_mm':40,'clearance_holes_mm':3.2})
    compound=cq.Compound.makeCompound(parts)
    cq.exporters.export(compound,str(out/'assembly.step'))
    back=cq.importers.importStep(str(out/'assembly.step')).val()
    report={'status':'geometry prototype; unprinted and acoustically unmeasured',
            'source_sha256':hashlib.sha256(Path(design_path).read_bytes()).hexdigest(),
            'checks':checks,'assembly_solids':len(back.Solids()),'modules':instructions,
            'all_passed':all(c['passed'] for c in checks) and len(back.Solids())==6,
            'physical_requirements':['Airtight gasket/seal at split faces and between modules.',
              'M3 through bolts/nuts; final length and gasket compression must be checked.',
              'Main 40 mm bore is geometrically preserved; airflow performance is unmeasured.',
              'Measure actual cavity/neck dimensions; printed roughness and leakage affect tuning.',
              'Use a controlled duct rig; model transmission loss is not room noise reduction.']}
    (out/'geometry-verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('design');p.add_argument('output');a=p.parse_args();export(a.design,a.output)
