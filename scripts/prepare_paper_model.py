"""Prepare a print manifest from an actual verified production run; no model calls."""
import argparse,csv,json,math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from continuum.geometry import Design,mesh,dimensions,fold_assignments,export_svg,export_fold,validate_geometry
from continuum.audit import audit_record

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run',default='ebd847afdf79')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
run=json.loads((root/'artifacts/runs'/f'{args.run}.json').read_text(encoding='utf-8'))
assert run['mode']=='single_pass' and run['status']=='completed' and run['model_calls']==1
selected=run['selected'];d=Design(**selected['design'])
assert validate_geometry(d)['passed'] and audit_record(selected,run['requirements'])['passed']
out=root/'output/paper';out.mkdir(parents=True,exist_ok=True)
manifest={'run_id':run['run_id'],'design_id':selected['id'],'model':run['model'],'design':d.model_dump(),
    'metrics':selected['metrics'],'constraints':selected['constraints'],'physical_validation':'pending',
    'flat_mesh':mesh(d,0),'assignments':fold_assignments(d),
    'poses':[{'angle':a,'mesh':mesh(d,a),'dimensions':dimensions(d,a)} for a in (8.,45.,d.packed_theta_deg)],
    'folding_reference':'https://www.stevenrwoodruff.com/wp-content/uploads/2023/05/ENGN250_S23_AllHandouts.pdf'}
(out/'paper-model.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(out/'paper-model.svg').write_text(export_svg(d),encoding='utf-8')
(out/'paper-model.fold').write_text(json.dumps(export_fold(d),indent=2),encoding='utf-8')
measurement_path=out/'measurements.csv'
if not measurement_path.exists():
    with measurement_path.open('x',newline='',encoding='utf-8') as handle:
        writer=csv.writer(handle)
        writer.writerow(['design_id','state','trial','theta_measured_deg','x_mm','y_mm','h_mm','measurement_uncertainty_mm','material','measured_at','notes'])
        for state in ['partial','packed']:
            for trial in range(1,4):writer.writerow([selected['id'],state,trial]+['']*8)
else:
    print('Existing measurements.csv preserved. Check its design ID before using a new manifest.')
print(json.dumps({'design_id':selected['id'],'run_id':run['run_id'],'flat':selected['metrics']['flat'],
                  'deployed':selected['metrics']['deployed'],'packed':selected['metrics']['packed'],'manifest':str(out/'paper-model.json')},indent=2))
