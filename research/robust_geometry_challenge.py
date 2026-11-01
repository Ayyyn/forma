"""Post-hoc geometry sweep after the pattern-search challenge; zero API calls.

This is additional, unequal-budget, informed numerical work. It cannot replace
the frozen prospective controller. It probes whether the remaining AI gain is
just catalogue coverage in an established low-dimensional mechanism family.
"""
from copy import deepcopy
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from robust_discovery.engine import evaluate
from nonlinear_discovery.model import audit
from robust_discovery.experiment import rank

def main():
    path=ROOT/'research/robust-geometry-challenge.json'
    if path.exists():raise ValueError('Existing diagnostic preserved')
    previous=json.loads((ROOT/'research/robust-coordinate-challenge.json').read_text());best=max((r for r in previous['audited'] if r['accepted']),key=lambda r:r['result']['summary']['worst_bias_N_mm']);records=[];start=time.monotonic()
    for theta in [28.,29.,30.,31.,32.,33.,34.]:
        d=deepcopy(best['design'])
        for c in d['cells']:c['theta0_deg']=theta
        r=evaluate(d,16);records.append({'id':'theta-'+str(theta),'design':d,'valid':True,'result':r});print(theta,r['summary']['passes_nominal_screen'],r['summary']['worst_bias_N_mm'],flush=True)
    checks=[]
    for record in sorted(records,key=rank)[:3]:
        r=evaluate(record['design'],128,True);a=audit(record['design'],r);passed=bool(r['summary']['passes_nominal_screen'] and a['passed'] and r.get('tolerance',{}).get('passed_trials')==8)
        checks.append({'id':record['id'],'design':record['design'],'result':r,'independent_audit':a,'accepted':passed});print('Geometry audit',record['id'],passed,r['summary']['worst_bias_N_mm'],flush=True)
    out={'scope':__doc__,'API_calls':0,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'screened_queries':len(records),'additional_to_previous_coordinate_queries':previous['queries'],'records':records,'audited':checks,'seconds':time.monotonic()-start}
    path.write_text(json.dumps(out,indent=2))

if __name__=='__main__':main()
