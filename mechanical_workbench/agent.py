"""Bounded Muse tool orchestration: never substitutes narrative for solver data."""
import hashlib,json,os
from scripts.api_preflight import load_env,request
from structure_lab.tool_protocol import normalize

SYSTEM='''You are an engineering investigator in a structured mechanical workbench, not a chat assistant. Complete a material-change diagnosis and repair for a spatial assembly. Use registered tools; public explanations concise. You receive actual geometry/connectivity, load cases, fixed requirements, old predictions and new SYNTHETIC virtual observations. No hardware measurements exist. Current adapter: six-DOF/node, circular linear Euler-Bernoulli members, rigid joints, no contact/shear/geometric nonlinearity/fabricated joint mechanics. Complexity does not extend physical validity. A new material has unknown E; do not silently assume it. Choose a discriminating virtual experiment. All tests explicitly identify synthetic sources. Revision acceptance requires calibration-consistent E, fixed displacement/strain/rotation/Euler screens, and independent energy-quadrature agreement. Modulus uncertainty is a declared5%; under this model fixed nu/no grounded springs gives exact1/E response scaling. Requirements and loads cannot be edited to manufacture success. Use the shared deterministic sizing optimizer for continuous radii; do not waste calls guessing numerical radii. You may add/remove up to8 members per graph revision, obey finite-radius collision and diameter/length<=.1. The reference graph is not the only supported graph: engine supports90nodes/300members/8loadcases. But nonlinear target-force curves and functional CAD fabrication are not implemented yet. At most32 candidate queries,3 virtual tests,4 model requests and estimated$5 API cap. Optimizer internal candidates are charged. Cached inspections/tests free. Final oblique load case is withheld from sizing and can reject the result. First solve this concrete development case; no general AI advantage, physical validation, scientific novelty or avoided-prototype claims. Prefer minimal accepted volume in this fixed grammar, with a clear audit trail of experiment -> revision -> verification. Finish via finish tool. This is an intentionally constructed known-law development fixture, not an unseen efficacy benchmark. Other controllers have exactly the same numerical tools.'''

def schemas():
    def tool(name,description,properties,required=()):return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':list(required),'additionalProperties':False}}}
    return [tool('inspect_assembly','Read cached full graph, fixed requirements, load cases and previous observations. No solve.',{}),
            tool('run_virtual_test','Run or inspect one of three synthetic diagnostic tests; new tests charged to the virtual-test budget.',{'test':{'type':'string','enum':['coupon_cantilever','fixture_motion','repeat_assembly']}},['test']),
            tool('evaluate_revision','Create and independently check an immutable graph/radius/material revision. Requirements fixed.',{'parent_revision_id':{'type':'string'},'E_N_mm2':{'type':'number','minimum':300,'maximum':10000},'radius_mm':{'type':'number','minimum':.15,'maximum':.8},'remove_member_ids':{'type':'array','maxItems':8,'items':{'type':'integer'}},'add_members':{'type':'array','maxItems':8,'items':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'integer'}}}},['E_N_mm2','radius_mm']),
            tool('size_revision','Shared deterministic uniform-radius sizing after calibration. All new solver candidates charged; no global topology optimum.',{'parent_revision_id':{'type':'string'},'maximum_evaluations':{'type':'integer','minimum':2,'maximum':16}}),
            tool('inspect_revision','Read cached revision metrics, geometry and checks; no solve.',{'revision_id':{'type':'string'}},['revision_id']),
            tool('finish','End investigation. Independent checks and a withheld oblique load decide final acceptance.',{})]

def dispatch(lab,name,args):
    if name=='inspect_assembly' and not args:return lab.context()
    if name=='run_virtual_test' and set(args)=={'test'}:return lab.virtual_test(args['test'])
    if name=='evaluate_revision' and {'E_N_mm2','radius_mm'}<=set(args) and not set(args)-{'E_N_mm2','radius_mm','parent_revision_id','remove_member_ids','add_members'}:
        parent=args.get('parent_revision_id','reference');d=lab.candidate(args['E_N_mm2'],args['radius_mm'],args.get('remove_member_ids',()),args.get('add_members',()),parent);return lab.compact(lab.evaluate_design(d,parent))
    if name=='size_revision' and not set(args)-{'parent_revision_id','maximum_evaluations'}:return lab.size(args.get('parent_revision_id','reference'),args.get('maximum_evaluations',12))
    if name=='inspect_revision' and set(args)=={'revision_id'}:
        r=next(r for r in lab.records if r['id']==args['revision_id']);return {'summary':lab.compact(r),'design':r['design']}
    if name=='finish' and not args:return {'finished':True}
    raise ValueError('Unknown tool or invalid exact arguments')

def run_meta(lab,directory):
    load_env();key=os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY')
    if not key:raise ValueError('Missing MODEL_API_KEY; add it locally, never in the browser')
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(lab.context())}];events=[];spent=0.
    for turn in range(4):
        payload={'model':'muse-wonder-1.0','messages':messages,'tools':schemas(),'tool_choice':'auto','max_tokens':4096,'reasoning_effort':'high','temperature':.2};encoded=json.dumps(payload).encode();reserve=len(encoded)*4e-6+4096*20e-6
        if spent+reserve>5:
            lab.event('budget','API estimated cost cap reached',{'spent_USD':spent,'next_reserve_USD':reserve,'cap_USD':5});break
        lab.event('model','Muse request '+str(turn+1),{'model':payload['model'],'estimated_phase_cap_USD':5})
        transport,body=request('https://api.meta.ai/v1',key,'/chat/completions',payload,timeout=180);usage=transport.get('usage') or {};cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens',0);cost=(usage.get('prompt_tokens',0)-cached)*4e-6+cached*.2e-6+usage.get('completion_tokens',0)*20e-6;spent+=cost
        event={'turn':turn+1,'transport':transport,'response_id':body.get('id') if body else None,'returned_model':body.get('model') if body else None,'request_sha256':hashlib.sha256(encoded).hexdigest(),'estimated_USD':cost,'reserved_USD':reserve};events.append(event);stop=False
        if body:
            message=body['choices'][0]['message'];public={'role':'assistant','content':message.get('content'),'tool_calls':message.get('tool_calls') or []};event['received_assistant']=public
            try:
                public,encoding=normalize(public,{t['function']['name'] for t in schemas()},event['response_id']);event['normalized']=public;event['encoding']=encoding;calls=public.get('tool_calls') or [];event['tools']=[]
                if calls:
                    messages.append(public)
                    for call in calls:
                        name=call['function']['name'];args=json.loads(call['function']['arguments']);lab.event('tool','Muse selected '+name,{'arguments':args})
                        try:result=dispatch(lab,name,args)
                        except (ValueError,TypeError,KeyError,StopIteration) as error:result={'error':str(error)};lab.event('rejected','Tool command rejected',result)
                        event['tools'].append({'name':name,'arguments':args,'result':result,'call_id':call['id']});messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps({'result':result,'ledger':lab.ledger})})
                        if name=='finish':stop=True
                else:messages.append({'role':'user','content':'No executable tool call was returned. Use the registered tools; no narrative success claim is accepted.'})
            except (ValueError,TypeError,KeyError) as error:event['error']=str(error)
        else:stop=True
        with (directory/'api-events.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(event)+'\n')
        lab.event('receipt','Muse response received',{'http_status':transport.get('http_status'),'provider_response_id':event['response_id'],'estimated_total_USD':spent,'billing_verified':False})
        if stop:break
        messages.append({'role':'user','content':f'API requests left {3-turn}. Finish once you have a calibration-consistent verified repair. Tool results decide acceptance.'})
    return {'actual_API_calls':len(events),'unique_response_ids':len({e['response_id'] for e in events if e['response_id']}),'estimated_USD':spent,'billing_verified':False}
