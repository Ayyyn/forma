"""python -m spatial_actuator verify | step1 | probe | report."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import time
from .design import task,compute
from .laboratory import Lab,numerical_control,source_manifest
from .verification import verify


def save(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)


def step1(directory):
    gate=verify()
    if not gate['passed']:raise ValueError('Mechanics verification failed')
    directory.mkdir(parents=True,exist_ok=False)
    manifest={'created_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Step 1 development proof; tasks inspected during development, no heldout benchmark',
              'task':task(),'source_hashes':source_manifest(),'candidate_budget_each_controller':192,
              'meta_probe':{'model':'muse-wonder-1.0','maximum_requests':4,'max_output_tokens_per_request':6144,'reasoning_effort':'medium'},
              'independent_validation':'analytic six-DOF cantilever and separately assembled Hermite energy model; no published Frame3DD example reproduced',
              'hardware_experiments':0,'prototype_savings_measured':False}
    save(directory/'manifest.json',manifest);root=Path(__file__).resolve().parents[1]
    for name in manifest['source_hashes']:
        target=directory/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
    save(directory/'verification.json',gate);lab=Lab(manifest['task']);started=time.monotonic();numerical_control(lab)
    output={'elapsed_seconds':time.monotonic()-started,'records':lab.records,'state':lab.state(),'independent_best_check':lab.verify(),
            'candidate_selection':'feasible then summed beam volume; broad conventional template sizing control, not a global optimum'}
    save(directory/'numerical.json',output)
    if lab.best and lab.best['valid']:
        from .figures import design_figure,load_sweep
        design_figure(lab.task,lab.best,directory/'numerical-design.png');save(directory/'load-sweep.json',load_sweep(lab.task,lab.best,directory))
        revised=dict(lab.task,E_N_mm2=1200.);result=compute(revised,lab.best['edge_ids'],lab.best['radii_mm'])
        save(directory/'material-change.json',{'scope':'fixed geometry; changed generic E, no reoptimization','E_N_mm2':1200.,'metrics':result['metrics'],'margins':result['margins'],'feasible':result['feasible']})
    print(json.dumps({'directory':str(directory),'physics_passed':gate['passed'],'state':output['state'],'oracle':output['independent_best_check']},indent=2))


def report(directory):
    manifest=json.loads((directory/'manifest.json').read_text());gate=json.loads((directory/'verification.json').read_text());numeric=json.loads((directory/'numerical.json').read_text())
    if source_manifest()!=manifest['source_hashes']:raise ValueError('Source drift; use snapshot for replay')
    reports={'numerical':numeric};path=directory/'meta-probe.json'
    if path.exists():reports['Muse Wonder']=json.loads(path.read_text())
    audits={}
    for name,result in reports.items():
        lab=Lab(manifest['task']);checks=0;maximum=0.
        for saved in result['records']:
            if not saved.get('valid'):continue
            reproduced=lab.evaluate(saved['edge_ids'],saved['radii_mm'],'offline_replay');check=lab.verify(reproduced)
            if not check['passed'] or saved['feasible']!=reproduced['feasible']:raise ValueError('Candidate replay/oracle failed')
            if any(abs(float(saved['metrics'][k])-float(v))>1e-9 for k,v in reproduced['metrics'].items() if v is not None):raise ValueError('Saved metric differs')
            maximum=max(maximum,check['max_displacement_or_rotation_error']);checks+=1
        audits[name]={'valid_records_replayed_and_oracle_checked':checks,'maximum_absolute_u_error':maximum,
                      'offline_additional_assemblies':3*checks,'note':'Production replay, production verification and independent assembly per valid record; never available to online search.'}
    (directory/'replay.json').write_text(json.dumps(audits,indent=2))
    lines=['# Loaded spatial compliant transmission: step 1','',
           'Development/integration proof, October 29, 2026. No heldout efficacy claim, new mechanical principle, physical experiment or demonstrated prototype savings.','',
           'Passive 3D beam transmission powered by an external 2 mN input force. Positive output z motion works against a 0.02 N/mm spring. Six DOFs/node, circular sections, rigid ideal joints, linear Euler–Bernoulli mechanics including torsion; synthetic E=2000 N/mm² and nu=0.3.','',
           'The catalogue task and numerical formulation were inspected during development. Same 192-candidate cap for both controllers; actual candidate work, API calls and wall time reported separately. This is a single case and is not a fair statistical comparison of general capability.','',
           '| Controller | Feasible | Volume proxy (mm³) | Loaded stroke (µm) | Input travel (µm) | Actual assemblies |',
           '|---|---|---:|---:|---:|---:|']
    for name,result in reports.items():
        best=result['state']['best_evaluated'];m=best['metrics'] if best else {};lines.append(f"| {name} | {bool(best and best['feasible'])} | {m.get('volume_proxy_mm3',float('nan')):.3f} | {m.get('loaded_stroke_mm',float('nan'))*1000:.3f} | {m.get('input_travel_mm',float('nan'))*1000:.3f} | {result['state']['actual_assemblies']} |")
    lines+=['',f"Analytical/reference gate: {gate['passed']}. Independent assembly max scaled error {gate['max_scaled_oracle_error']:.3g}; radius sensitivity error {gate['max_scaled_gradient_error']:.3g}. Analytical reference includes axial, both bending planes, moments, torsion, spatial coordinate changes, subdivision and resisting-spring energy. No published Frame3DD example has been reproduced.",'',
            'Volume sums member volumes and double-counts joint overlaps. Collision checking uses initial finite-radius envelopes, excludes intentional overlaps at shared ideal nodes, and does not model a fabricated joint. Nodal translation plus 17-section/member sampled rotations guard small deformation. Nominal normal/torsional strain and a pinned-member Euler compression ratio guard are not joint strength, nonlinear or loaded-system buckling validation. No contact, shear flexibility, fatigue, power-source, dynamic or clinical model. Stored spring energy/input ramp work is an energy allocation, not cycle efficiency.','',
            'load-sweep.json reports every sampled resisting stiffness, including points failing requirements. material-change.json changes E at fixed geometry and reports failure without silently repairing it. Actual force/stroke are tiny and synthetic: no real actuator material calibration or fabricated performance claim.','']
    if 'Muse Wonder' in reports:
        probe=reports['Muse Wonder'];events=probe['events'];unique=len({e['response_id'] for e in events if e.get('response_id')});usage=[e['transport'].get('usage') or {} for e in events]
        lines+=[f"Real Muse integration: {len(events)} actual requests, {unique} distinct provider IDs, HTTP statuses {[e['transport'].get('http_status') for e in events]}. Input tokens {sum(u.get('prompt_tokens',0) for u in usage)}, output tokens {sum(u.get('completion_tokens',0) for u in usage)}. No billing deduction verified. Public received/normalized commands and tool outputs retained; private reasoning text and credentials omitted.",'']
        best=probe['state']['best_evaluated']
        if best and best['valid']:
            from .figures import design_figure
            design_figure(manifest['task'],best,directory/'meta-design.png')
    lines+=['All valid candidate records were replayed and checked against the separately assembled energy model offline. Those extra solves are recorded in replay.json and were not search guidance.','',
            'Next gate: independent external-solver reference under matching assumptions, a richer problem/revision set and a predeclared stronger numerical control before any efficacy claim. Muse already receives exact geometry, tool feedback and optional multi-view deformation/sensitivity inspection. More context and multi-agent roles require measured ablations, not assumed benefit.','',
            'Reproduce: `python -m spatial_actuator verify`; `python -m spatial_actuator report --directory <this folder>`. `step1` creates a fresh offline proof directory; `probe` performs at most four paid Muse requests and preserves the received records.','',
            'Classical prior art: https://frame3dd.sourceforge.net/ ; https://pymoto.readthedocs.io/en/latest/auto_examples/topology_optimization/ex_compliant_mechanism_springs.html . No code from those projects was incorporated.']
    (directory/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print(json.dumps(audits,indent=2))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['verify','step1','probe','report']);parser.add_argument('--directory',type=Path,default=Path('artifacts/spatial-actuator-step1-v2'));args=parser.parse_args();directory=args.directory.resolve()
    if args.command=='verify':
        result=verify();print(json.dumps(result,indent=2))
        if not result['passed']:raise SystemExit(1)
    elif args.command=='step1':step1(directory)
    elif args.command=='report':report(directory)
    else:
        from .agent import probe
        result=probe(directory);print(json.dumps({'actual_requests':result['actual_requests'],'state':result['state'],'oracle':result['independent_best_check']},indent=2))


if __name__=='__main__':main()
