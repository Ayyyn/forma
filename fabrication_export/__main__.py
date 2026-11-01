import argparse,json
from pathlib import Path
from .panels import export_kit
from .display import export_display
p=argparse.ArgumentParser(description='CAD-solid static panel kit with STEP/STL/OBJ round-trip checks; no API calls.')
p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--kind',choices=['panel-kit','static-display'],default='panel-kit');p.add_argument('--thickness-mm',type=float,default=1.2);p.add_argument('--spacing-mm',type=float,default=5.);p.add_argument('--columns',type=int,default=8);a=p.parse_args()
source=json.loads(a.input.read_text())
r=export_display(source,a.output,a.thickness_mm) if a.kind=='static-display' else export_kit(source,a.output,a.thickness_mm,a.spacing_mm,a.columns)
print(json.dumps({'output':str(a.output.resolve()),'geometry_checks_passed':r['geometry_checks_passed'],'parts':r['parts_count'],'bounds_mm':r['assembly']['bounds_mm'],'scope':r['mechanical_status']}))
