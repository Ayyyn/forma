import hashlib,json,os
from scripts.api_preflight import load_env,request
from structure_lab.tool_protocol import normalize,strict_json
from frontier_scout.meta import schema,Budget,SYSTEM as PREVIOUS
from frontier_scout.policy import validate_plan,expand
MODELS={'meta_wonder':('muse-wonder-1.0',4.,.2,20.),'meta_spark':('muse-spark-1.3',1.25,.15,4.25)}
SYSTEM='''You are a hypothesis-proposing expert in an EVIDENCE-GATED model portfolio. Raw GP, random forest and domain-feature GP remain available at all times. Your feature GP initially receives weight0.1; weights change using clipped Gaussian log losses of predictions made BEFORE newly revealed results (learning rate.2, sigma floor.05 standardized units, active weight floor.02). A valid expression alone is not evidence of a correct hypothesis. Mixture expected improvement selects experiments. Your expert is replaced/reset at8,16,24 observations, retaining the base-expert relative weights. The supplied diagnostic trace lists each expert forecast, observation and weights; use it to revise or abandon poor features. Empty features abstain and disable your additional expert. You may not edit the numerical system or infer hidden outcomes. These are statistical forecast experts, not validated physical laws.\n'''+PREVIOUS

def propose(dataset,history,previous,trace,directory,budget,method):
    model,input_rate,cache_rate,output_rate=MODELS[method];context={'task':dataset.public(),'observed_group_measurements':history,'previous_hypothesis':previous,'last_prequential_expert_evidence':trace[-8:],'total_group_budget':32,'phase_group_count':len(history),'expert_order':['raw_GP','RF','domain_GP','Meta_feature_GP']};payload={'model':model,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(context)}],'tools':schema(),'tool_choice':'auto','max_tokens':8192,'temperature':.2}
    if method=='meta_wonder':payload['reasoning_effort']='high'
    encoded=json.dumps(payload).encode();reserve=len(encoded)*input_rate/1e6+8192*output_rate/1e6+.005;fallback={'hypothesis':'Explicit abstention/fallback; not a model-generated discovery','features':[]}
    if not budget.reserve(reserve):return fallback,{'actual_API_call':False,'error':'budget/halt prevented dispatch'}
    load_env();key=os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY')
    if not key:budget.settle(reserve,0.);raise ValueError('Missing Meta key')
    phase=len(history);(directory/f'request-{phase:02d}.json').write_text(json.dumps(payload,indent=2));transport,body=request('https://api.meta.ai/v1',key,'/chat/completions',payload,timeout=240)
    if transport.get('http_status')!=200:budget.halt(str(transport))
    usage=transport.get('usage') or {};cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens',0);cost=((usage.get('prompt_tokens',0)-cached)*input_rate+cached*cache_rate+usage.get('completion_tokens',0)*output_rate)/1e6 if usage else reserve;budget.settle(reserve,cost)
    event={'actual_API_call':True,'method':method,'phase':phase,'transport':transport,'provider_response_id':body.get('id') if body else None,'returned_model':body.get('model') if body else None,'request_sha256':hashlib.sha256(encoded).hexdigest(),'reserved_estimate_USD':reserve,'estimated_USD':cost,'estimate_from_reported_usage':bool(usage),'accepted_feature_plan':False}
    try:
        if not body:raise ValueError('No body')
        choice=body['choices'][0];message=choice['message'];public={'role':'assistant','content':message.get('content'),'tool_calls':message.get('tool_calls') or []};event.update(public_assistant=public,finish_reason=choice.get('finish_reason'));command,encoding=normalize(public,{'propose_features'},event['provider_response_id']);calls=command.get('tool_calls') or []
        if calls:
            if len(calls)!=1:raise ValueError('One command required')
            plan=strict_json(calls[0]['function']['arguments'])
        else:
            content=(public.get('content') or '').strip()
            if content.startswith('```json') and content.endswith('```'):content=content[7:-3].strip()
            plan=strict_json(content);encoding='single_plan_JSON'
        validate_plan(plan,dataset.X.shape[1]);expand(dataset.X,plan['features']);event.update(plan=plan,encoding=encoding,accepted_feature_plan=True)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as exc:event['error']=str(exc);plan={**fallback,'hypothesis':'Validation failed: '+str(exc)}
    with (directory/'api-events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event)+'\n')
    print('Portfolio',method,dataset.name,len(history),'HTTP',transport.get('http_status'),'accepted',event['accepted_feature_plan'],flush=True)
    return plan,event
