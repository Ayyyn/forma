"""Transport diagnostic only: no geometry tools executed or benchmark outcomes scored."""
import argparse,hashlib,json,os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from continuum.benchmark import SYSTEM,ToolPlan,BASE,MODEL,load_env,request,Ledger,task_requirements,TASKS,baseline_design,compact

load_env();key=os.environ['BASETEN_API_KEY']
r=task_requirements(TASKS[0]);ledger=Ledger(r,'creases');ledger.evaluate(baseline_design().model_dump(),'common-initial-candidate')
messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps({'requirements':r.model_dump(),'objective':'creases','initial_candidate':compact(ledger.best()),'instruction':'Choose exactly one search plan for 63 candidate attempts. No actual evaluation will happen in this diagnostic.'})}]
tool={'type':'function','function':{'name':'search_designs','description':'Choose a numerical search region.','parameters':ToolPlan.model_json_schema()}}
parser=argparse.ArgumentParser();parser.add_argument('--larger',action='store_true');args=parser.parse_args()
results=[]
conditions=[('auto','medium',16384),('auto','low',8192)] if args.larger else [(c,e,4096) for c in ['forced','auto'] for e in [None,'medium']]
for choice,effort,cap in conditions:
        payload={'model':MODEL,'messages':messages,'tools':[tool],'tool_choice':{'type':'function','function':{'name':'search_designs'}} if choice=='forced' else 'auto','max_tokens':cap,'temperature':.2,'seed':101}
        if effort:payload['reasoning_effort']=effort
        transport,response=request(BASE,key,'/chat/completions',payload)
        message=response['choices'][0]['message'] if response else {}
        item={'tool_choice':choice,'reasoning_effort':effort or 'provider_default','output_cap':cap,'transport':transport,'response_id':response.get('id') if response else None,
              'finish_reason':response['choices'][0].get('finish_reason') if response else None,
              'returned_tool_calls':len(message.get('tool_calls') or []),
              'reasoning_field_present':any(bool(message.get(k)) for k in ['reasoning_content','reasoning']),
              'request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()}
        results.append(item);print(json.dumps(item),flush=True)
Path('benchmarks/reasoning-transport-probe'+('-larger-budgets' if args.larger else '')+'.json').write_text(json.dumps({'purpose':'Transport diagnostic; no tool execution or scored benchmark candidates','results':results},indent=2),encoding='utf-8')
