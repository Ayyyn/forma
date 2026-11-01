"""Real Meta hypotheses for a bounded numerical feature language, with receipts."""
import hashlib,json,os,threading
from pathlib import Path
from scripts.api_preflight import load_env,request
from structure_lab.tool_protocol import normalize,strict_json
from .policy import OPS,validate_plan,expand
SYSTEM='''You propose TESTABLE feature hypotheses for sequential experimental design, not target property values. A fixed numerical Gaussian-process/ARD expected-improvement engine selects the next historical experiment. You cannot access unrevealed outcomes or run arbitrary code. At most six extra features are appended to the original raw features; all columns are normalized using only public candidate coordinates. New feature j is available at index d+j, so later features may compose earlier ones. Allowed operations: square(x),abs(x),log1p_abs(x),sqrt_abs(x),sin_deg(x),cos_deg(x),product(a,b),difference(a,b),sum(a,b),ratio(a,b)=a/sqrt(b*b+floor*floor) with floor=max(public range(b)*.001,1e-8),annular_area(radius,thickness)=pi*(r^2-(r-t)^2),annular_inertia(radius,thickness)=pi/4*(r^4-(r-t)^4). Annular inputs must obey radius>=thickness>=0 over the entire public pool. Input indices reference RAW PHYSICAL columns, then previous additional features. These are statistical representations; they do not become verified constitutive equations. The same engine and label budget are given to raw-GP, domain-informed-GP, random and random-forest-EI controls. Domain baseline includes annular area/inertia/total area/wall ratio/angular features for barrels, offset magnitudes/squares and prime-speed product for printing, pair interactions and squares for perovskite compositions. Your goal is a useful representation beyond that strong control, or retain raw inputs if uncertain. Consider data versus domain priors; revise an earlier hypothesis if prequential prediction errors contradict it. Do not assert causality, fabricated measurements, newly synthesized materials, new-to-science design or clinical validity. This is a replay of published experimental tables with grouped replicates, not real-time laboratory work. Return exactly one propose_features command with a short public hypothesis and <=6 features, each with name, op, integer inputs and short rationale. No guessed properties or recommendations outside this DSL.'''

def schema():
    plan={'type':'object','properties':{'hypothesis':{'type':'string'},'features':{'type':'array','maxItems':6,'items':{'type':'object','properties':{'name':{'type':'string'},'op':{'type':'string','enum':list(OPS)},'inputs':{'type':'array','minItems':1,'maxItems':2,'items':{'type':'integer'}},'rationale':{'type':'string'}},'required':['name','op','inputs','rationale'],'additionalProperties':False}}},'required':['hypothesis','features'],'additionalProperties':False}
    return [{'type':'function','function':{'name':'propose_features','description':'Propose a bounded, numerically checked feature representation for a shared Gaussian-process expected-improvement engine. No target predictions or arbitrary code.', 'parameters':plan}}]

class Budget:
    def __init__(self,cap=12.,maximum=36):self.cap=cap;self.maximum=maximum;self.spent=0.;self.pending=0.;self.calls=0;self.halt_reason=None;self.lock=threading.Lock()
    def reserve(self,cost):
        with self.lock:
            if self.halt_reason or self.calls>=self.maximum or self.spent+self.pending+cost>self.cap:return False
            self.calls+=1;self.pending+=cost;return True
    def settle(self,reserve,cost):
        with self.lock:self.pending-=reserve;self.spent+=cost
    def halt(self,reason):
        with self.lock:self.halt_reason=str(reason)
    def state(self):
        with self.lock:return {'request_count':self.calls,'estimated_USD':self.spent,'pending_reserved_USD':self.pending,'cap_USD':self.cap,'halt_reason':self.halt_reason,'billing_verified':False}

def propose(dataset,history,previous,diagnostics,directory,budget):
    context={'task':dataset.public(),'observed_group_measurements':history,'previous_proposal':previous,'recent_predictions_before_the_observations':diagnostics[-8:],'observations_revealed':len(history),'total_group_budget':32,'phase_scope':'Choose features; the GP selects subsequent points. No other measured outcomes are available.'}
    payload={'model':'muse-wonder-1.0','messages':[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(context)}],'tools':schema(),'tool_choice':'auto','max_tokens':6144,'reasoning_effort':'high','temperature':.2}
    encoded=json.dumps(payload).encode();reserve=len(encoded)*4e-6+6144*20e-6+.005
    fallback={'hypothesis':'Explicit numerical raw-feature fallback; not a model-generated discovery.','features':[]}
    if not budget.reserve(reserve):return fallback,{'status':'budget_not_dispatched','actual_API_call':False}
    load_env();key=os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY')
    if not key:budget.settle(reserve,0.);raise ValueError('Meta key missing')
    phase=len(history);directory.mkdir(parents=True,exist_ok=True);(directory/f'request-{phase:02d}.json').write_text(json.dumps(payload,indent=2))
    transport,body=request('https://api.meta.ai/v1',key,'/chat/completions',payload,timeout=240);usage=transport.get('usage');reported=bool(usage);usage=usage or {};cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens',0)
    if transport.get('http_status')!=200:budget.halt('Transport failure: '+str(transport.get('http_status',transport.get('status'))))
    cost=(usage.get('prompt_tokens',0)-cached)*4e-6+cached*.2e-6+usage.get('completion_tokens',0)*20e-6 if reported else reserve;budget.settle(reserve,cost)
    event={'phase_observations':phase,'actual_API_call':True,'transport':transport,'provider_response_id':body.get('id') if body else None,'returned_model':body.get('model') if body else None,'request_sha256':hashlib.sha256(encoded).hexdigest(),'reserved_estimate_USD':reserve,'estimated_USD':cost,'estimate_from_reported_tokens':reported,'accepted_feature_plan':False}
    try:
        if not body:raise ValueError('No response body')
        choice=body['choices'][0];message=choice['message'];public={'role':'assistant','content':message.get('content'),'tool_calls':message.get('tool_calls') or []};event['public_assistant']=public;event['finish_reason']=choice.get('finish_reason')
        command,encoding=normalize(public,{'propose_features'},event['provider_response_id']);calls=command.get('tool_calls') or []
        if calls:
            if len(calls)!=1 or calls[0]['function']['name']!='propose_features':raise ValueError('Expected exactly one feature command')
            plan=strict_json(calls[0]['function']['arguments'])
        else:
            content=(public.get('content') or '').strip()
            if content.startswith('```json') and content.endswith('```'):content=content[7:-3].strip()
            plan=strict_json(content);encoding='explicit_single_plan_JSON'
        validate_plan(plan,dataset.X.shape[1]);expand(dataset.X,plan['features']);event.update(accepted_feature_plan=True,encoding=encoding,plan=plan)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as exc:event['validation_error']=str(exc);plan=fallback
    with (directory/'api-events.jsonl').open('a',encoding='utf-8') as file:file.write(json.dumps(event)+'\n')
    print(f'Measured-data Muse {dataset.name} at {phase}: HTTP {transport.get("http_status")}, plan accepted={event["accepted_feature_plan"]}',flush=True)
    return plan,event
