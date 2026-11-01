"""Post-hoc catalogue robustness diagnostic; NOT the frozen pilot comparator.

Prompted by inspecting the pilot's new graphs. Enumerates conventional dense
grids and two-edge load paths, rather than injecting the AI's selected widths.
This is hypothesis generation for a later prospective stronger baseline.
"""
import hashlib
from itertools import product,combinations
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from structure_lab.design import geometry,templates,task_cases,bounds,validate_graph
from structure_lab.search import Laboratory


def catalogue():
    _,edges=geometry();lookup={tuple(sorted(e)):i for i,e in enumerate(edges)}
    graphs={tuple(ids) for ids in templates().values()}
    # Every orientation of one noncrossing diagonal in each rectangular cell.
    for diagonal in product(*[(10,14),(11,15),(12,16),(13,17)]):graphs.add(tuple(sorted(list(range(10))+list(diagonal))))
    paths=[]
    for left in [0,1,2]:
        for middle in [3,4,5]:
            keys=[tuple(sorted((left,middle))),tuple(sorted((middle,7)))]
            if all(k in lookup for k in keys):paths.append({lookup[k] for k in keys})
    for path in paths:graphs.add(tuple(sorted(path)))
    for a,b in combinations(paths,2):graphs.add(tuple(sorted(a|b)))
    return sorted(graphs,key=lambda g:(len(g),g))


def main():
    results=[];graphs=catalogue()
    for task in task_cases():
        if task['id'] not in ['stiff_mount','clear_channel']:continue
        lab=Laboratory(task);eligible=[];started=time.perf_counter()
        for ids in graphs:
            lower=[a for a,b in bounds(task,ids)]
            try:validate_graph(task,ids,lower)
            except ValueError:continue
            eligible.append(list(ids))
            if lab.remaining>32:lab.evaluate(list(ids),lower,'posthoc_catalogue_screen')
        candidates=[r for r in lab.records if r.get('valid')]
        candidates.sort(key=lambda r:r['volume_mm3']*(1+min(r['violation'],1000)))
        for candidate in candidates:
            if not lab.remaining:break
            lab.optimize(start_id=candidate['id'],allocation=min(12,lab.remaining))
        certificate=lab.final_verify()
        results.append({'task':task['id'],'charged_slots':len(lab.records),'actual_frame_assemblies':lab.physics_solves,
            'generated_graphs':len(graphs),'geometry_eligible':len(eligible),'best':lab.best,'certificate':certificate,
            'seconds':time.perf_counter()-started})
    report={'status':'post-hoc catalogue-sensitivity diagnostic, not prospective evidence or replacement of v3',
            'new_meta_calls':0,'physics_budget_per_task':96,'results':results,
            'interpretation':'Designed after seeing the pilot. Tests whether conventional catalogue coverage can explain apparent AI wins. Does not establish a fair general superiority result for either policy.',
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'pilot_manifest_sha256':hashlib.sha256((ROOT/'benchmarks/structure-pilot-v3/manifest.json').read_bytes()).hexdigest()}
    out=ROOT/'research/structure-catalogue-challenge.json';out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
