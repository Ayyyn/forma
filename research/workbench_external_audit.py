"""Offline OpenSees check of preserved selected workbench revisions/cases."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.spatial_external_check import compare,runtime
from mechanical_workbench.physics import load_matrix

def main():
    ops=runtime();audits=[]
    for path in sorted((ROOT/'output/mechanical-workbench/runs').glob('*/result.json')):
        run=json.loads(path.read_text());final=run.get('final',{});selected=next((r for r in run.get('revisions',[]) if r['id']==final.get('selected_revision')),None)
        if not selected:continue
        output=path.parent/'external-audit.json'
        if output.exists():audits.append(json.loads(output.read_text()));continue
        d=selected['design'];cases=selected['result']['load_cases']+final['heldout_result']['load_cases'];checks=[]
        for case in cases:
            F=load_matrix(d['nodes_mm'],[case]);check=compare(d['nodes_mm'],[tuple(e) for e in d['edges']],d['radii_mm'],d['clamped_nodes'],F,d['E_N_mm2'],d['nu']);checks.append({'case':case['id'],**check})
        manifest=json.loads((path.parent/'manifest.json').read_text());sources_ok=all(hashlib.sha256((path.parent/'source'/name).read_bytes()).hexdigest()==digest for name,digest in manifest['source_hashes'].items())
        audit={'id':run['id'],'solver':'OpenSees elasticBeamColumn / Linear','version':ops.version(),'passed':bool(sources_ok and all(c['passed'] for c in checks)),'archived_source_hashes_match':sources_ok,'checks':checks,'scope':'Additional offline numerical audit of the same ideal linear law, not online policy work or hardware validation.'}
        output.write_text(json.dumps(audit,indent=2));audits.append(audit);print(run['id'],audit['passed'],flush=True)
    report={'passed':bool(audits and all(a['passed'] for a in audits)),'audits':audits,'case_count':sum(len(a['checks']) for a in audits),'maximum_displacement_or_rotation_error':max(c['maximum_absolute_displacement_or_rotation_error'] for a in audits for c in a['checks']),'new_Meta_API_calls':0}
    (ROOT/'output/mechanical-workbench/external-audit-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='audits'}))

if __name__=='__main__':main()
