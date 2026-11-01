"""Bounded real Meta calls; no hidden fallback or fabricated tool execution."""
import hashlib,json,os
from scripts.api_preflight import load_env,request
from structure_lab.tool_protocol import normalize,strict_json
from .laboratory import BudgetExhausted

SYSTEM='''Design a generic passive resistance cartridge using the registered nonlinear architecture library. This is a constructed development problem, not unseen scientific evidence. Follow the fixed force curve and packaging limits. You may select architecture and parameters and use the shared deterministic fitter. All inner candidates, including invalid ones, count toward the same 240-query allowance used by the numerical control. Cached inspection is free. Geometry budget is a declared ideal envelope, not hardware-certified CAD. Guided two-axial-spring linkages use bilateral ideal springs and pins, not buckling solid beams. Linkage return spring makes every stage strictly convex, so series internal displacement equilibrium is unique. Kresling is the previously published bar/hinge model, torque-free in the sampled twist sector; no exhaustive-root claim. Neither adapter predicts contact, failure, manufacturing, dynamics, hysteresis or free deployment. Curve travel is prescribed by a displacement controller. Do not call arbitrary configurations freely stable equilibria. This task has eight established motifs and four continuous parameters per motif, not unbounded topology discovery. The numerical control enumerates every feasible architecture, fits each for 24 queries, then refines/restarts the best. Same fitter for all controllers. Optimize numerical evidence, not explanation. No hardware data, physical validation, saved-prototype or scientific-novelty claims. Return executable registered tools only. No code execution, files or browsing. Use fit_architecture for continuous tuning. Lower normalized RMS is better subject to all mechanical screens. You have at most six API requests (one for single-pass mode), 4096 output tokens per request and an estimated $10 cap per task. The complete public library and target are provided.'''

def schemas(single=False):
    names=['single_hardening','parallel_hardening','series_hardening','graded_series_parallel','consolidated_graded_series','softening_hardening_stack','kresling_parallel_1','kresling_parallel_2']
    props={'architecture':{'type':'string','enum':names},'maximum_evaluations':{'type':'integer','minimum':1,'maximum':240},'start_parameters':{'type':'array','items':{'type':'number'},'minItems':4,'maxItems':4}}
    def tool(name,description,properties,required=()):return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':list(required),'additionalProperties':False}}}
    if single:return [tool('submit_plan','One-shot sequence of shared architecture fits; total requested allowance <=240. No solver feedback to model.',{'searches':{'type':'array','minItems':1,'maxItems':12,'items':{'type':'object','properties':props,'required':['architecture','maximum_evaluations'],'additionalProperties':False}}},['searches'])]
    return [tool('fit_architecture','Same bounded least-squares optimizer as numerical baseline. New inner candidates charged, best cached candidate returned.',props,['architecture','maximum_evaluations']),tool('evaluate_design','Evaluate one explicit four-parameter design.',{'architecture':props['architecture'],'parameters':props['start_parameters']},['architecture','parameters']),tool('inspect_library','Read public task, domains, grammar and budget.',{}),tool('inspect_candidate','Read cached full design and response, no new solve.',{'candidate_id':{'type':'string'}},['candidate_id']),tool('finish','Finish with best feasible numerical candidate selected automatically.',{})]

def dispatch(lab,name,args):
    if name=='fit_architecture' and not set(args)-{'architecture','maximum_evaluations','start_parameters'} and {'architecture','maximum_evaluations'}<=set(args):return lab.fit(args['architecture'],args['maximum_evaluations'],args.get('start_parameters'))
    if name=='evaluate_design' and set(args)=={'architecture','parameters'}:return lab.summary(lab.evaluate(args['architecture'],args['parameters']))
    if name=='inspect_library' and not args:return lab.context()
    if name=='inspect_candidate' and set(args)=={'candidate_id'}:
        r=next(r for r in lab.records if r['id']==args['candidate_id']);return {'summary':lab.summary(r),'result':r.get('result')}
    if name=='finish' and not args:return {'finished':True,'best':lab.summary(lab.best()) if lab.best() else None}
    if name=='submit_plan' and set(args)=={'searches'}:
        searches=args['searches']
        if not isinstance(searches,list) or not 1<=len(searches)<=12 or sum(s['maximum_evaluations'] for s in searches)>lab.budget:raise ValueError('Invalid plan or plan exceeds 240 candidates')
        return {'fits':[dispatch(lab,'fit_architecture',s) for s in searches]}
    raise ValueError('Unknown tool or invalid exact arguments')

def run_meta(lab,directory,single=False):
    load_env();key=os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY')
    if not key:raise ValueError('Missing local MODEL_API_KEY')
    messages=[{'role':'system','content':SYSTEM+(' SINGLE-PASS MODE: use submit_plan once. No solver feedback will be returned.' if single else ' ADAPTIVE MODE: use feedback to allocate queries; finish when done.')},{'role':'user','content':json.dumps(lab.context())}];events=[];spent=0.;tools=schemas(single)
    for turn in range(1 if single else 6):
        payload={'model':'muse-wonder-1.0','messages':messages,'tools':tools,'tool_choice':'auto','max_tokens':4096,'reasoning_effort':'high','temperature':.2};encoded=json.dumps(payload).encode();reserve=len(encoded)*4e-6+4096*20e-6
        if spent+reserve>10:lab.event('api_cap',{'estimated_spend_USD':spent});break
        lab.event('model_request',{'turn':turn+1,'model':payload['model']})
        transport,body=request('https://api.meta.ai/v1',key,'/chat/completions',payload,timeout=180);usage=transport.get('usage') or {};cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens',0);cost=(usage.get('prompt_tokens',0)-cached)*4e-6+cached*.2e-6+usage.get('completion_tokens',0)*20e-6;spent+=cost
        event={'turn':turn+1,'transport':transport,'response_id':body.get('id') if body else None,'returned_model':body.get('model') if body else None,'request_sha256':hashlib.sha256(encoded).hexdigest(),'estimated_USD':cost,'reserve_USD':reserve,'tool_results':[]};events.append(event);stop=False
        if body:
            try:
                message=body['choices'][0]['message'];public={'role':'assistant','content':message.get('content'),'tool_calls':message.get('tool_calls') or []};event['received_assistant']=public
                public,encoding=normalize(public,{t['function']['name'] for t in tools},event['response_id'],single_tool='submit_plan' if single else None);event['encoding']=encoding;calls=public.get('tool_calls') or []
                if calls:
                    messages.append(public)
                    for call in calls:
                        name=call['function']['name'];args=strict_json(call['function']['arguments'])
                        try:result=dispatch(lab,name,args)
                        except (ValueError,TypeError,KeyError,StopIteration,BudgetExhausted) as e:result={'error':str(e)}
                        event['tool_results'].append({'name':name,'arguments':args,'result':result});lab.event('tool',event['tool_results'][-1]);messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result)})
                        if name=='finish':stop=True
                else:messages.append({'role':'user','content':'No executable tool call received. Use the registered tools.'})
            except (ValueError,TypeError,KeyError) as e:event['error']=str(e)
        else:stop=True
        with (directory/'api-events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event)+'\n')
        lab.event('model_receipt',{'http_status':transport.get('http_status'),'provider_response_id':event['response_id'],'estimated_total_USD':spent})
        print(json.dumps({'task':lab.task['id'],'policy':'single_pass' if single else 'adaptive','turn':turn+1,'http_status':transport.get('http_status'),'response_id':event['response_id'],'candidates':len(lab.records),'estimated_USD':spent}),flush=True)
        if stop or not lab.remaining:break
        messages.append({'role':'user','content':f'API requests left: {5-turn}. New candidate allowance remaining: {lab.remaining}. Finish or use remaining queries to improve the best feasible RMS. Never relax requirements.'})
    return {'actual_API_calls':len(events),'http_200_responses':sum(e['transport'].get('http_status')==200 for e in events),'unique_response_ids':len({e['response_id'] for e in events if e['response_id']}),'estimated_USD':spent,'billing_verified':False}
