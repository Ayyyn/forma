"""One Meta planning request followed by budgeted numerical selection and verification."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid
from pydantic import ValidationError

from .benchmark import Ledger, Plan, ToolPlan, SYSTEM, compact, rank
from .agent import load_env, request
from .geometry import Design, Requirements, validate_geometry
from .search import baseline_design

ROOT=Path(__file__).resolve().parents[1]


def run_single_pass(requirements: Requirements, brief: str, provider='baseten', objective='creases', seed=101):
    if objective not in ('creases','material'):
        raise ValueError('Unknown design objective')
    load_env()
    if provider=='baseten':
        base,key,model='https://inference.baseten.co/v1',os.environ.get('BASETEN_API_KEY'),'meta-models/muse-spark-open-1026'
    elif provider=='meta':
        base,key,model='https://api.meta.ai/v1',os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY'),'muse-spark-1.3'
    else:raise ValueError('Unknown provider')
    if not key:raise ValueError('Selected provider key is not configured locally')
    started=time.monotonic();ledger=Ledger(requirements,objective,budget=64)
    ledger.evaluate(baseline_design().model_dump(),'common-initial-candidate')
    baseline=ledger.best();trace=[];error=None;plan=None;selected=None;verification=None
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps({
        'brief':brief,'requirements':requirements.model_dump(),'objective':objective,
        'initial_candidate':compact(baseline),'seed':seed,'evaluation_budget_remaining':63,
        'instruction':'Choose exactly one search region now for all 63 remaining numerical candidate attempts. This is the only model request. You will not receive tool feedback or choose the winning candidate; the deterministic evaluator selects and verifies it. Honor the explicit objective and hard constraints.'})}]
    tool={'type':'function','function':{'name':'search_designs','description':'Propose one bounded region for numerical exploration; feasibility is determined only by actual computation.','parameters':ToolPlan.model_json_schema()}}
    transport,response=request(base,key,'/chat/completions',{
        'model':model,'messages':messages,'tools':[tool],'tool_choice':'auto','reasoning_effort':'medium',
        'max_tokens':49152,'temperature':.2,'seed':seed},timeout=180)
    trace.append({'kind':'model_request','turn':1,'model':model,'http_status':transport.get('http_status'),
        'latency_ms':transport.get('latency_ms'),'usage':transport.get('usage'),'request_id':transport.get('request_id'),
        'response_id':response.get('id') if response else None,'response_model':response.get('model') if response else None})
    if not response:error={'message':'The single planning request failed. No retry or provider substitution was made.','transport':transport}
    else:
        try:
            message=response['choices'][0]['message'];calls=message.get('tool_calls') or []
            if len(calls)!=1 or calls[0].get('function',{}).get('name')!='search_designs':
                raise ValueError('The planning request must return exactly one search_designs call')
            plan=ToolPlan.model_validate_json(calls[0]['function']['arguments'])
            settings=Plan(**{k:v for k,v in plan.model_dump().items() if k not in ('expected_feasible','rationale')})
            if plan.rationale:trace.append({'kind':'public_model_output','text':plan.rationale[:4000]})
            feedback=ledger.batch(settings,63,seed,'single-pass-plan')
            trace.append({'kind':'tool_result','tool':'search_designs','arguments':json.dumps(plan.model_dump()),'result':{
                'evaluated_count':feedback['attempts'],'feasible_count':feedback['feasible'],
                'search_space':settings.model_dump(),'candidates':feedback['best_candidates'],
                'invalid_count':feedback['attempts']-feedback['valid'],'total_attempts_including_start':len(ledger.records)}})
            best=ledger.best()
            if best and best['feasible']:
                verification=validate_geometry(Design(**best['design']))
                if not verification['passed']:raise ValueError('Selected candidate failed rigid-geometry verification')
                selected=best
                trace.append({'kind':'verification','result':verification,'text':'Selected by the declared numerical objective; all hard constraints, independent scoring oracle and rigid-facet checks passed.'})
            else:error={'message':'No feasible candidate was found in the 64-attempt allowance. Requirements were not relaxed.'}
        except (KeyError,IndexError,TypeError,ValidationError,ValueError,RuntimeError) as exc:
            selected=None;error={'message':'Plan or deterministic verification rejected: '+str(exc)[:1000]}
    candidates=[r['result'] for r in ledger.records if r['valid']]
    candidates.sort(key=lambda r:rank(r,objective))
    rationale=(f"Numerical verification selected {selected['id']}: all {len(selected['constraints'])} constraints pass, "
               f"with {selected['metrics']['crease_segments']} crease segments. Dimensions are predictions; physical measurements remain pending.") if selected else None
    report={'run_id':uuid.uuid4().hex[:12],'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'mode':'single_pass','provider':provider,'model':model,'model_calls':1,'tool_calls':int(plan is not None),
        'brief':brief,'objective':objective,'seed':seed,'requirements':requirements.model_dump(),
        'budget':64,'evaluations_used':len(ledger.records),'baseline':baseline,'selected':selected,
        'candidates':candidates[:24],'plan':plan.model_dump() if plan else None,
        'rationale':rationale,'status':'completed' if selected else 'incomplete','error':error,
        'latency_ms':round((time.monotonic()-started)*1000),'trace':trace,'validation':verification,'ledger':ledger.records,
        'comparison_limit':'One-pass planning role adopted from the equal-budget benchmark; this individual run is not a new benchmark or physical validation.'}
    directory=ROOT/'artifacts/runs';directory.mkdir(parents=True,exist_ok=True)
    (directory/(report['run_id']+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
