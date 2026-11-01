"""Post-hoc adaptive numerical challenge, not a replacement frozen baseline.

Written after seeing preliminary robust Meta results. Controls the prior known
paired-torsion motif using ordinary coordinate pattern search; no AI calls.
"""
from copy import deepcopy
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from robust_discovery.experiment import Lab,rank,shared
from robust_discovery.engine import evaluate
from nonlinear_discovery.model import audit

def parameters(d):
    return np.array([d['springs'][0]['k'],d['springs'][1]['k'],d['springs'][0]['offset_A'],d['springs'][0]['offset_B'],d['springs'][3]['k'] if len(d['springs'])>3 else 0.])

def design(x):
    d=deepcopy(shared()[2]);d.pop('note',None);d['springs'][0].update(k=float(x[0]),offset_A=float(x[2]),offset_B=float(x[3]))
    for s in d['springs'][1:]:s['k']=float(x[1]);s['offset']=0.
    if x[4]>1e-8:d['springs'].append({'type':'axial','rings':[2,4],'k':float(x[4]),'offset':0.})
    return d

def main():
    output=ROOT/'research/robust-coordinate-challenge.json'
    if output.exists():raise ValueError('Preserve previous diagnostic')
    lab=Lab();start=time.monotonic()
    for d in shared():lab.evaluate(d)
    step=np.array([.004,4.,7.,7.,.002]);low=np.array([.001,.1,-10.,-10.,0.]);high=np.array([.08,30.,60.,60.,.02]);history=[]
    for sweep in range(5):
        before=rank(lab.best);best_before=lab.best['id']
        for coordinate in range(5):
            center=parameters(lab.best['design'])
            for sign in [-1,1]:
                if not lab.remaining:break
                x=center.copy();x[coordinate]=np.clip(x[coordinate]+sign*step[coordinate],low[coordinate],high[coordinate]);lab.evaluate(design(x))
            if not lab.remaining:break
        history.append({'sweep':sweep,'step':step.tolist(),'best_id':lab.best['id']})
        if rank(lab.best)>=before or lab.best['id']==best_before:step*=.5
        if not lab.remaining:break
    checks=[]
    for rec in sorted(lab.records,key=rank)[:3]:
        r=evaluate(rec['design'],128,True);a=audit(rec['design'],r);accepted=bool(r['summary']['passes_nominal_screen'] and a['passed'] and r.get('tolerance',{}).get('passed_trials')==8)
        checks.append({'id':rec['id'],'design':rec['design'],'result':r,'independent_audit':a,'accepted':accepted});print('Coordinate audit',rec['id'],accepted,r['summary']['worst_bias_N_mm'],r.get('tolerance',{}).get('passed_trials'),flush=True)
    result={'scope':'Post-hoc numerical pattern-search challenge; coded after preliminary new Meta results inspected, not prospective or a replacement scored baseline.','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'API_calls':0,'records':lab.records,'history':history,'queries':len(lab.records),'seconds':time.monotonic()-start,'audited':checks}
    output.write_text(json.dumps(result,indent=2));print('saved',output)

if __name__=='__main__':main()
