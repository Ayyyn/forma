"""Post-hoc failure diagnosis, never a replacement scored controller.

Uses both policies' failed candidates and more numerical work. A found feasible
witness proves a bounded-search failure; lack of one is NOT infeasibility proof.
No API calls. Outputs remain separate from the frozen matrix.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from spatial_revision.study import load
from spatial_revision.laboratory import Lab,eligible_catalogue
from spatial_revision.problem import bounds,compute
from research.spatial_external_check import compare


def run(directory):
    manifest=load(directory);reports=[]
    for case in manifest['cases']:
        saved=[json.loads((directory/'runs'/case['id']/method/'result.json').read_text()) for method in manifest['methods']]
        if any(r['state']['best_evaluated'] and r['state']['best_evaluated']['feasible'] for r in saved):continue
        lab=Lab(case,1024)
        seeds=sorted([r for s in saved for r in s['records'] if r.get('valid')],key=Lab.rank);seen=set()
        for seed in seeds:
            ids=tuple(seed['edge_ids'])
            if ids in seen:continue
            seen.add(ids);record=lab.evaluate(seed['edge_ids'],seed['radii_mm'],'posthoc_saved_failed_seed');lab.optimize(allocation=min(80,lab.remaining),start_id=record['id'])
            if len(seen)>=6 or (lab.best and lab.best['feasible']):break
        if not lab.best or not lab.best['feasible']:
            for name,ids in eligible_catalogue(case).items():
                if not lab.remaining:break
                lab.evaluate(ids,[lo for lo,hi in bounds(case,ids)],'posthoc_full_catalogue:'+name)
            candidates=sorted([r for r in lab.records if r['valid']],key=Lab.rank);sized=set()
            for seed in candidates:
                ids=tuple(seed['edge_ids'])
                if ids in sized:continue
                sized.add(ids)
                if not lab.remaining:break
                lab.optimize(allocation=min(80,lab.remaining),start_id=seed['id'])
                if lab.best and lab.best['feasible']:break
        witness=lab.best if lab.best and lab.best['feasible'] else None;external=None
        if witness:
            result=compute(case,witness['edge_ids'],witness['radii_mm'])
            external=compare(result['nodes'],result['edges'],witness['radii_mm'],[0,1,2,3],result['loads'],case['E_N_mm2'],case['nu'],result['springs'])
            if not external['passed']:raise ValueError('Witness failed independent external check')
        reports.append({'case_id':case['id'],'revision_kind':case['revision_kind'],'diagnostic_budget':1024,
                        'additional_candidate_slots':len(lab.records),'additional_assemblies':lab.assemblies,
                        'found_feasible_witness':bool(witness),'witness':witness,'external_check':external,
                        'best_failed':None if witness else lab.best,'records':lab.records})
        print(f"Posthoc {case['id']}: witness={bool(witness)}, added candidates={len(lab.records)}",flush=True)
    return {'scope':'Post-hoc shared-seed, larger-budget diagnosis, not scored results','actual_api_calls':0,
            'classification_rule':'A witness establishes search failure; no witness leaves feasibility unresolved.',
            'uses_scored_method_candidates':True,'cases':reports}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('benchmarks/spatial-revision-v1'));p.add_argument('--output',type=Path,default=Path('research/spatial-revision-failure-diagnostic.json'));args=p.parse_args()
    if args.output.exists():raise ValueError('Existing diagnostic preserved')
    result=run(args.directory.resolve());args.output.write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
