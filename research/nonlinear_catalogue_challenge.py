"""Post-hoc ordinary spring-grid challenge; not a new prospective baseline.

Architecture class informed by the pilot; uses no additional Meta calls. Keeps
the original comparison intact and tests its catalogue-coverage sensitivity.
"""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nonlinear_discovery.model import reference,evaluate,audit,jet,mapping
from nonlinear_discovery.experiment import Lab,rank
import numpy as np


def main():
    target=ROOT/'research/nonlinear-catalogue-challenge.json'
    if target.exists():raise ValueError('Original diagnostic preserved')
    lab=Lab()
    for kt in [0.,10.,20.,30.]:
        for ka in [.01,.02,.03,.04,.05,.06]:
            d=reference();d.pop('note',None);d['springs'][0].update(k=ka,offset_A=60.,offset_B=-10.)
            if kt:
                d['springs'] +=[{'type':'torsion','rings':[0,2],'k':kt,'offset':0.},{'type':'torsion','rings':[2,4],'k':kt,'offset':0.}]
            lab.evaluate(d)
    best=lab.best;refined=evaluate(best['design'],64);check=audit(best['design'],refined)
    result={'scope':'Post-hoc coverage diagnostic, not replacement prospective controller','actual_api_calls':0,
            'queries':len(lab.records),'records':lab.records,'best':best,'refined':refined,'audit':check,
            'accepted':refined['feasible'] and check['passed'],'catalogue_class_informed_by_pilot':True,
            'initial_starts_per_setting':16,'refinement_starts_per_setting':64}
    # Algebraic check: equal torsion springs on the two halves with equal offset
    # add k*psi^2 + k*offset^2 under zero total additional end twist. Their common
    # offset only adds a constant on this constraint surface, while changing the
    # clamp torque. It does not create additional state-shaping freedom.
    d=reference();d['springs'] +=[{'type':'torsion','rings':[0,2],'k':30.,'offset':1.},{'type':'torsion','rings':[2,4],'k':30.,'offset':1.}]
    zero=json.loads(json.dumps(d));zero['springs'][1]['offset']=0.;zero['springs'][2]['offset']=0.
    x=np.array([.8,.8,.7,.7,.1,.1]);v,g,h=jet(d,x,'A');v0,g0,h0=jet(zero,x,'A')
    result['torsional_preload_redundancy_check']={'energy_shift_N_mm':(v-v0)*1500.,'gradient_difference':float(abs(g-g0).max()),'hessian_difference':float(abs(h-h0).max()),
        'interpretation':'At fixed zero end twist, equal torsion offsets contribute only a constant to constrained energy. They can change the endpoint holding torque. No new internal energy-landscape freedom comes from that common offset.'}
    target.write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['records','best','refined','audit']},indent=2));print('best_bias',refined['worst_bias_N_mm'])


if __name__=='__main__':main()
