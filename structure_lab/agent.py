"""Actual Meta tool use with compact state and proper public tool history."""
import base64
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from scripts.api_preflight import load_env,request
from .design import public_geometry
from .search import render_geometry,BudgetExhausted
from .tool_protocol import normalize

MODEL='meta-models/muse-spark-open-1026'
MAX_TURNS=6
RENDER_LOCK=threading.Lock()
SYSTEM='''You are designing a small mechanical frame network using real numerical tools. Optimize minimum summed beam volume subject to ALL exact task constraints. Numerical verification decides success, never your rationale. You can choose conventional templates, propose custom edge subsets, size members with the shared constrained SLSQP optimizer (analytic stiffness sensitivities), inspect exact geometry and analyze computed results. You have a total search allowance of 96 charged candidate slots, plus the common final independent check. Every candidate inside an optimizer counts; identical cached queries are free but logged, invalid new candidates consume a slot. You have at most six model requests, so batch useful tools and allocate numerical work deliberately. There is no benefit to mentally computing a stiffness matrix: use the tools. New topologies must use the stated graph language. All nodes use mm, loads N, compliance mm/N, volume mm^3. The material coefficient E is generic and synthetic, not a calibrated material. Each joint is moment-rigid; left nodes are clamped; output x and y compliances are from SEPARATE unit loads. Cxy is reciprocal cross response: y motion under x load, equal to x motion under y load. The actual test force is much smaller than 1 N; linearity guards apply to that force. Keepouts constrain the finite-width member envelope conservatively. Small-strain in-plane Euler-Bernoulli mechanics only: no large motion, contact, plasticity, fatigue, joint concentrations or loaded buckling validation. No clinical or medical claims. No external research or undisclosed case results. A custom graph is not a world-first invention. Preserve all task constraints. Use tool outputs to decide where to optimize and repair. finish_search ends the run; the shared deterministic ranking returns the best evaluated design, so you do not need to declare your own winner. Keep public explanations concise; perform numerical work through the tools.'''


class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class Optimize(Strict):
    template:str|None=None
    edge_ids:list[int]|None=None
    start_id:str|None=None
    allocation:int=Field(ge=1,le=96)
    start_fraction:float=Field(default=.6,ge=0,le=1)
class Evaluate(Strict):
    edge_ids:list[int]=Field(min_length=1,max_length=18)
    widths_mm:list[float]=Field(min_length=1,max_length=18)
class Inspect(Strict):design_id:str|None=None
class Analyze(Strict):design_id:str
class Finish(Strict):pass
class Plan(Strict):
    searches:list[Optimize]=Field(min_length=1,max_length=96)


def definitions(planner=False):
    items=[('plan_search',Plan,'Choose a fixed optimizer portfolio now, within 96 total allocated slots. No future model feedback.')] if planner else [
       ('optimize_design',Optimize,'Run the actual constrained analytic-gradient sizing optimizer for a template, custom graph or starting design ID. allocation is a maximum number of NEW charged candidates inside the tool.'),
       ('evaluate_design',Evaluate,'Evaluate a custom graph with one width per edge. New invalid graphs still consume one slot.'),
       ('inspect_geometry',Inspect,'Return exact graph context and a rendered view of an evaluated design, or the node grid when none exists.'),
       ('analyze_design',Analyze,'Inspect already computed compliance, constraint margins and member-width sensitivities without a new solve.'),
       ('finish_search',Finish,'End search and independently verify the shared best candidate.')]
    return [{'type':'function','function':{'name':name,'description':description,'parameters':schema.model_json_schema()}} for name,schema,description in items]


def initial_messages(lab,planner=False):
    prompt={'task':lab.task,'geometry_and_templates':public_geometry(lab.task),'state':lab.public_state(),
            'objective':'feasible first, then minimum summed member-volume proxy',
            'volume_proxy_note':'sum(depth*width*length); not exact CAD joint volume',
            'pilot_status':'development case; no clinical claims or physical measurements'}
    extra=' Produce exactly one plan_search call. Its allocations must total at most 96. The host executes your fixed plan with the same optimizer; no adaptive model feedback.' if planner else ''
    return [{'role':'system','content':SYSTEM+extra},{'role':'user','content':json.dumps(prompt,separators=(',',':'))}]


def model_request(messages,seed,planner=False):
    load_env();key=os.environ.get('BASETEN_API_KEY')
    if not key:raise RuntimeError('BASETEN_API_KEY missing')
    payload={'model':MODEL,'messages':messages,'tools':definitions(planner),'tool_choice':'auto',
             'reasoning_effort':'medium','temperature':.2,'seed':seed,'max_tokens':8192}
    transport,body=request('https://inference.baseten.co/v1',key,'/chat/completions',payload,timeout=180)
    event={'transport':transport,'response_id':body.get('id') if body else None,'returned_model':body.get('model') if body else None,
           'request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()}
    if not body:return None,event
    try:
        choice=body['choices'][0];message=choice['message'];event['finish_reason']=choice.get('finish_reason')
        # Save public tool arguments; never save private reasoning fields.
        public={'role':'assistant','content':message.get('content'), 'tool_calls':message.get('tool_calls') or []}
        event['received_assistant']=public
        try:
            allowed={d['function']['name'] for d in definitions(planner)}
            normalized,encoding=normalize(public,allowed,event['response_id'],single_tool='plan_search' if planner else None)
            public=normalized;event['tool_encoding']=encoding
        except (ValueError,KeyError,TypeError) as exc:
            event['normalization_error']=str(exc)[:500];event['tool_encoding']='rejected'
        event['assistant']=public
        return public,event
    except (KeyError,IndexError,TypeError):event['error']='Malformed response';return None,event


def run_tool(lab,name,arguments,directory):
    if name=='optimize_design':
        p=Optimize.model_validate_json(arguments)
        return lab.optimize(p.edge_ids,p.template,p.start_id,p.allocation,p.start_fraction),None
    if name=='evaluate_design':
        p=Evaluate.model_validate_json(arguments);return lab.evaluate(p.edge_ids,p.widths_mm,'meta_custom_graph'),None
    if name=='inspect_geometry':
        p=Inspect.model_validate_json(arguments)
        r=next((r for r in lab.records if r['id']==p.design_id),None) if p.design_id else lab.best
        target=directory/f'geometry-{len(list(directory.glob("geometry-*.png"))):02d}.png'
        with RENDER_LOCK:render_geometry(lab.task,r,target)
        result={'geometry':public_geometry(lab.task),'design':r,'render_file':target.name,
                'note':'Actual centerlines; line width is illustrative, exact widths appear in labels/JSON. No deformed motion is rendered.'}
        return result,'data:image/png;base64,'+base64.b64encode(target.read_bytes()).decode()
    if name=='analyze_design':
        p=Analyze.model_validate_json(arguments);r=next(r for r in lab.records if r['id']==p.design_id)
        if not r['valid']:return r,None
        internal=lab.internal[r['id']]
        return {'design':r,'d_compliance_d_width':internal['solved']['compliance_gradient'].tolist(),
                'd_volume_d_width':internal['solved']['volume_gradient'].tolist()},None
    if name=='finish_search':Finish.model_validate_json(arguments);return {'finished':True},None
    raise ValueError('Unknown tool')


def run_meta(lab,seed,directory,planner=False):
    messages=initial_messages(lab,planner);events=[];completed=False
    for turn in range(1 if planner else MAX_TURNS):
        assistant,event=model_request(messages,seed,planner);event['turn']=turn+1;events.append(event)
        event['image_inputs_transmitted']=sum(part.get('type')=='image_url' for m in messages if isinstance(m.get('content'),list) for part in m['content'])
        if assistant is None:
            event['stopped']='transport_or_response_failure';break
        calls=assistant['tool_calls']
        if not calls:
            invalid=lab.charge_invalid('No usable tool call, including any output-limit truncation') if lab.remaining else None
            event['invalid']=invalid
            if planner:break
            messages.append({'role':'user','content':json.dumps({'error':'No usable tool call; one search slot charged. Use numerical tools or finish.','state':lab.public_state()})})
            continue
        messages.append(assistant)
        event['tools']=[];finish=False;images=[]
        for call in calls:
            try:
                name=call['function']['name'];args=call['function']['arguments']
                if planner:
                    if name!='plan_search':raise ValueError('Expected plan_search')
                    plan=Plan.model_validate_json(args)
                    if sum(p.allocation for p in plan.searches)>lab.budget:raise ValueError('Plan allocation exceeds budget')
                    result=[]
                    for p in plan.searches:
                        result.append(lab.optimize(p.edge_ids,p.template,p.start_id,p.allocation,p.start_fraction))
                    image=None;finish=True
                else:
                    result,image=run_tool(lab,name,args,directory)
                    finish=finish or name=='finish_search'
            except (ValueError,KeyError,IndexError,TypeError,StopIteration,BudgetExhausted) as exc:
                result={'error':str(exc)[:600],'invalid_charged':lab.charge_invalid(str(exc)[:600]) if lab.remaining else None};image=None
            event['tools'].append({'call_id':call['id'],'name':call['function']['name'],'result':result,
                                   'image_queued':bool(image)})
            messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps({'result':result,'state':lab.public_state()},separators=(',',':'))})
            if image:images.append(image)
        # Complete every pending tool response before adding user/image context.
        for image in images:
            messages.append({'role':'user','content':[{'type':'text','text':'Numerically generated geometry view returned by inspect_geometry; use exact JSON for dimensions.'},
                                                       {'type':'image_url','image_url':{'url':image}}]})
        if finish or not lab.remaining:completed=True;break
        messages.append({'role':'user','content':f'Model decisions remaining: {MAX_TURNS-turn-1}. Search slots remaining: {lab.remaining}. Continue with tools or finish.'})
    return {'events':events,'completed_search':completed,'actual_api_calls':len(events),
            'all_transports_received':all(e['transport'].get('http_status')==200 for e in events),
            'planner_only':planner,'geometry_views_rendered':sum(t['image_queued'] for e in events for t in e.get('tools',[])),
            'image_inputs_transmitted':sum(e['image_inputs_transmitted'] for e in events)}
