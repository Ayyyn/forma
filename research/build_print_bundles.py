"""Generate checked print-part bundles for the two accepted robustness winners."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];study=ROOT/'benchmarks/robust-discovery-v1'
summary=json.loads((study/'summary.json').read_text());cad=ROOT/'research/vendor/cad-runtime/Scripts/python.exe';receipt=[]
for method,group in summary['methods'].items():
    candidate=group['best_accepted_id']
    if not candidate:continue
    for setting in ['A','B']:
        slug=f'robust-{method}-{candidate}-{setting}';source=ROOT/'output/print-inputs'/(slug+'.json');destination=ROOT/'output/discovery-board/exports'/slug
        if not source.exists():subprocess.run([sys.executable,str(ROOT/'research/prepare_print_geometry.py'),'--study',str(study),'--method',method,'--candidate',candidate,'--setting',setting,'--output',str(source)],check=True)
        if not (destination/'manifest.json').exists():subprocess.run([str(cad),'-m','fabrication_export',str(source),'--output',str(destination)],cwd=ROOT,check=True)
        manifest=json.loads((destination/'manifest.json').read_text())
        if not manifest['geometry_checks_passed']:raise ValueError('Incomplete geometry checks')
        receipt.append({'method':method,'candidate':candidate,'setting':setting,'manifest':str(destination/'manifest.json'),'parts':manifest['parts_count'],'checks_passed':manifest['geometry_checks_passed']})
        if method=='meta':
            display=ROOT/'output/discovery-board/exports'/(slug+'-display-v2')
            if not (display/'manifest.json').exists():subprocess.run([str(cad),'-m','fabrication_export',str(source),'--output',str(display),'--kind','static-display'],cwd=ROOT,check=True)
            record=json.loads((display/'manifest.json').read_text())
            if not record['geometry_checks_passed']:raise ValueError('Static display geometry check failed')
            receipt.append({'method':method,'candidate':candidate,'setting':setting,'purpose':'fixed-pose static display','manifest':str(display/'manifest.json'),'parts':1,'checks_passed':True})
(ROOT/'output/discovery-board/print-export-receipt.json').write_text(json.dumps({'model_calls':0,'mechanical_solves':0,'exports':receipt},indent=2))
