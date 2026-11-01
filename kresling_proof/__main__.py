"""Run the isolated scientific proof; no model API calls, server, or CAD UI."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time
from .model import Cell
from .statics import equilibria,axial_curve,branch_barrier
from .verification import reference_checks,independent_checks,convergence_checks,REFERENCES
from .experiment import spring_experiments
from .plots import make_plots


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['all'])
    parser.add_argument('--output',type=Path,default=Path('artifacts/kresling-proof'))
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();cell=Cell()
    print('1/5: published stationary states and source-curve comparison',flush=True)
    solved=equilibria(cell)
    published=reference_checks(cell,solved)
    print('2/5: independent vertex geometry and 70-digit derivatives',flush=True)
    independent=independent_checks(cell)
    print('3/5: numerical convergence and branch identification',flush=True)
    convergence=convergence_checks(cell);curve=axial_curve(cell)
    barrier=branch_barrier(cell,solved['states'])
    print('4/5: declared pre-stress and stiffness sweeps',flush=True)
    prestress=spring_experiments(cell,solved['states'])
    base_pass=published['passed'] and independent['passed'] and convergence['passed']
    verdict='continue_scientific_model' if base_pass and prestress['passed'] else ('simplify_to_bare_model' if base_pass else 'no_go')
    files=list(Path(__file__).resolve().parent.glob('*.py'))+list(REFERENCES.glob('*.json'))
    report={'created_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'numerical reproduction of reduced-order mechanics',
      'parameters':cell.to_dict(),'units':{'length':'mm','angles_internal':'radians','force':'N','energy':'N mm = mJ'},
      'model':'Zang et al. JMPS 2024 five-term energy, rigid polygonal end rings, two symmetric DOFs',
      'sources':[
        {'doi':'10.1016/j.jmps.2024.105630','role':'base equations 1-9 and 14-15; Appendix A.3 and Figure 5A checkpoints',
         'url':'https://paulino.scholar.princeton.edu/sites/g/files/toruqf6546/files/documents/JMPS_24_KreslingMechanics.pdf'},
        {'doi':'10.1073/pnas.2426790122','role':'additional axial spring energy, Eq. 5; not reproducing its specific apparatus',
         'url':'https://www.pnas.org/doi/10.1073/pnas.2426790122'},
        {'doi':'10.1039/D5MH01607J','role':'prior art and alternative truss/PINN formulation; no network trained or paper accuracy claimed',
         'url':'https://arxiv.org/abs/2508.13559'}],
      'source_sha256':{str(p.relative_to(Path(__file__).resolve().parents[1])):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
      'runtime':{'python':platform.python_version(),'packages':{n:importlib.metadata.version(n) for n in ['numpy','scipy','sympy','mpmath','matplotlib']}},
      'equilibria':solved,'bare_branch_barrier':barrier,'published_reproduction':published,
      'independent_verification':independent,'convergence':convergence,'prestress':prestress,
      'decision':verdict,'physical_validation':'not performed','new_meta_api_calls':0,
      'limitations':['Only two symmetric generalized coordinates: minima are not a proof of full shell stability.',
        'No panel buckling, self-contact, thickness interference, plasticity, viscoelasticity, friction, fatigue or dynamic switching.',
        'Effective published stiffness coefficients, not independently calibrated properties of a fabricated sample.',
        'Branch barriers depend on the declared quasistatic loading path; no global transition-path optimum is claimed.',
        'Multi-start convergence does not prove all equilibria in the physical system have been found.',
        'Figure samples are digitized published theoretical data, not raw experiments.',
        'Ideal bilateral spring does not reproduce spring disengagement in some PNAS experimental mechanisms.',
        'No new mechanism, multistability, inverse-design method or AI advantage is claimed.']}
    print('5/5: plots, data and reproducibility report',flush=True)
    report['plots']=make_plots(cell,report,curve,out)
    report['elapsed_seconds']=time.perf_counter()-started
    (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    with (out/'bare_axial_curve.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(curve[0]));w.writeheader();w.writerows(curve)
    rows=published['curve_comparison']
    with (out/'published_curve_comparison.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    sweep_rows=[]
    for item in prestress['preload_sweeps']:
        minima=sorted((s for s in item['states'] if s['classification']=='minimum'),key=lambda s:s['u_mm'])
        b=item['branch_barrier']
        sweep_rows.append({'spring_stiffness_N_per_mm':item['spring']['stiffness_N_per_mm'],
            'spring_offset_mm':item['spring']['offset_mm'],'minima_found':len(minima),
            'first_u_mm':minima[0]['u_mm'] if minima else '',
            'second_u_mm':minima[1]['u_mm'] if len(minima)>1 else '',
            'forward_branch_barrier_N_mm':b.get('forward_N_mm',''),
            'reverse_branch_barrier_N_mm':b.get('reverse_N_mm',''),'barrier_status':b['status']})
    with (out/'prestress_sweep.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(sweep_rows[0]));w.writeheader();w.writerows(sweep_rows)
    brief=['# Kresling scientific proof',f"Decision: **{verdict}**.",'',
      f"Published reproduction: {published['passed']}; independent numerical checks: {independent['passed']}; convergence: {convergence['passed']}; spring sensitivity: {prestress['passed']}.",
      '',f"Source-curve NRMSE / plotted vertical range: {100*published['checks'][-1]['nrmse_full_vertical_range']:.4f}%.",
      f"Preload-induced first-equilibrium shift: {prestress['primary_equilibrium_shift']['shift_mm']:.6f} mm.",
      '', 'This is a GO only for further reduced-model research. Physical validity, useful inverse design, Meta benefit and hackathon competitiveness remain unestablished.',
      '', '## Limitations','']+['- '+x for x in report['limitations']]
    (out/'RESULTS.md').write_text('\n'.join(brief)+'\n',encoding='utf-8')
    print(json.dumps({'decision':verdict,'report':str(out/'report.json'),'seconds':report['elapsed_seconds'],
                      'physical_validation':'not performed','new_meta_api_calls':0},indent=2))
    return 0 if verdict=='continue_scientific_model' else 2


if __name__=='__main__':raise SystemExit(main())
