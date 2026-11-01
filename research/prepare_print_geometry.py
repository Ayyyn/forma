"""Prepare saved nonlinear state geometry; no solves or model API calls."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nonlinear_discovery.model import mesh
p=argparse.ArgumentParser();p.add_argument('--study',type=Path,default=ROOT/'benchmarks/nonlinear-discovery-v1');p.add_argument('--method',default='meta');p.add_argument('--candidate',default='n022');p.add_argument('--setting',choices=['A','B'],default='A');p.add_argument('--role',choices=['target','counter'],default='target');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
path=a.study/'summary.json';summary=json.loads(path.read_text());method=summary['methods'][a.method];rows=method.get('audited',method.get('final_refined',[]));row=next(r for r in rows if r['id']==a.candidate);result=row.get('result',row.get('refined'));detail=result.get('summary',result)['details'][a.setting];state=detail[a.role];geometry=mesh(row['design'],state)
output={'kind':'triangular_panel_kit','vertices_mm':geometry['vertices_mm'],'triangles':geometry['triangles'],'source_state':state,'provenance':{'study':a.study.name,'method':a.method,'candidate':a.candidate,'setting':a.setting,'role':a.role,'study_summary_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'accepted_in_source_study':row['accepted'],'geometry':'Selected deformed triangles of ideal zero-thickness Kresling visualization; exported thickness is additional geometry, not verified mechanics.','literature':['https://doi.org/10.1016/j.jmps.2024.105630','https://doi.org/10.1073/pnas.2426790122'],'original_model_authors':'Zang et al.; no invention of Kresling mechanics or inverse design claimed','new_API_calls':0,'new_equilibrium_solves':0}}
a.output.parent.mkdir(parents=True,exist_ok=True)
with a.output.open('x') as f:json.dump(output,f,indent=2)
print(a.output)
