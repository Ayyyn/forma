"""Actual Muse revision controller with matched numerical tools and a journal."""
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from scripts.api_preflight import load_env,request
from structure_lab.tool_protocol import normalize
from spatial_actuator.agent import SYSTEM as PREVIOUS_SYSTEM,definitions as original_definitions
from .laboratory import eligible_catalogue,Exhausted
from .problem import geometry

SYSTEM=PREVIOUS_SYSTEM.replace('192 candidate slots','256 candidate slots')+'''
This is a prospective revision study. The old design is supplied to every policy. Its response under the revised conditions has already consumed one common candidate slot. Geometry and all constraints in the current task are authoritative; the previous task is historical context only. Output stroke is output_sign times global z displacement; a negative output_sign requires NEGATIVE global z motion while stroke remains positive in acceptance metrics. Do not change any task requirement or material law. You can retain, resize or replace the graph using the public edge language. All geometrically eligible conventional graphs are available in the shared catalogue; a larger ordinary numerical control also uses them. No control outcomes, feasibility witnesses or other case results are supplied. Use inspections to see the actual spatial geometry, current motion and sensitivities. Failure is allowed and recorded. No unsupported declaration of success overrides returned constraint margins.'''


def definitions():
    tools=deepcopy(original_definitions())
    for tool in tools:
        if tool['function']['name']=='optimize':tool['function']['parameters']['properties']['allocation']['maximum']=256
    return tools


def handle(lab,name,args,directory):
    allowed={d['function']['name']:d['function']['parameters'] for d in definitions()}
    if name not in allowed or not isinstance(args,dict):raise ValueError('Unknown tool/invalid object')
    schema=allowed[name]
    if set(args)-set(schema['properties']) or not set(schema['required'])<=set(args):raise ValueError('Unexpected/missing fields')
    if name=='evaluate':return lab.evaluate(**args),None
    if name=='optimize':
        if sum(k in args for k in ['template','edge_ids','start_id'])!=1:raise ValueError('Exactly one topology/start source required')
        return lab.optimize(**args),None
    if name=='finish':return {'finished':True},None
    record=next((r for r in lab.records if r['id']==args.get('design_id')),None) if args.get('design_id') else lab.best
    if not record or not record['valid']:raise ValueError('Valid evaluated design required')
    from .figures import render
    internal=lab.internal[record['id']];target=directory/f'view-{len(list(directory.glob("view-*.png"))):02d}.png';render(lab.task,record,internal,target)
    inp=6*lab.task['input_node']+lab.task['input_axis'];out=6*lab.task['output_node']+lab.task['output_axis']
    return {'design':record,'edge_order':record['edge_ids'],'d_signed_stroke_d_radius':(lab.task['output_sign']*internal['solved']['du_dr'][:,out,0]).tolist(),
            'd_input_travel_d_radius':internal['solved']['du_dr'][:,inp,0].tolist(),'d_volume_d_radius':internal['solved']['dvolume_dr'].tolist()},'data:image/png;base64,'+base64.b64encode(target.read_bytes()).decode()


def run(lab,starter,previous_task,directory,seed):
    load_env();key=os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY')
    if not key:raise ValueError('MODEL_API_KEY missing')
    initial=lab.evaluate(starter['edge_ids'],starter['radii_mm'],'shared_previous_design')
    nodes,edges=geometry(lab.task)
    context={'current_task':lab.task,'previous_task':previous_task,'previous_design':starter,
             'current_nodes_mm':nodes.tolist(),'edge_options':[{'id':i,'nodes':list(e)} for i,e in enumerate(edges)],
             'clamped_nodes':[0,1,2,3],'geometrically_eligible_conventional_catalogue':eligible_catalogue(lab.task),
             'state':lab.state(),'optimizer_note':'Direct stroke/input/x/y constraints with exact radius sensitivities; other guards checked on every candidate.',
             'scope':'Unseen requirement instance; no score/control results shown. Fixed 256 candidate slots and four model requests maximum.'}
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(context)}];events=[]
    for turn in range(4):
        payload={'model':'muse-wonder-1.0','messages':messages,'tools':definitions(),'tool_choice':'auto','max_tokens':6144,'reasoning_effort':'medium','temperature':.2}
        transport,body=request('https://api.meta.ai/v1',key,'/chat/completions',payload,timeout=180)
        event={'turn':turn+1,'transport':transport,'response_id':body.get('id') if body else None,'returned_model':body.get('model') if body else None,
               'request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
               'image_inputs_transmitted':sum(p.get('type')=='image_url' for m in messages if isinstance(m.get('content'),list) for p in m['content'])}
        events.append(event);stop=False
        if not body:event['stopped']='transport_failure';stop=True
        else:
            try:
                choice=body['choices'][0];event['finish_reason']=choice.get('finish_reason');message=choice['message']
                public={'role':'assistant','content':message.get('content'),'tool_calls':message.get('tool_calls') or []};event['received_assistant']=public
                public,encoding=normalize(public,{d['function']['name'] for d in definitions()},event['response_id']);event['encoding']=encoding;event['assistant']=public
                calls=public.get('tool_calls') or [];images=[];event['tools']=[]
                if not calls:
                    if lab.remaining:event['invalid']=lab.invalid('No executable tool response, including truncation')
                    messages.append({'role':'user','content':json.dumps({'error':'No executable tool command; one slot charged. Use tools or finish.','state':lab.state()})})
                else:
                    messages.append(public)
                    for call in calls:
                        try:
                            result,image=handle(lab,call['function']['name'],json.loads(call['function']['arguments']),directory);stop=stop or call['function']['name']=='finish'
                        except (ValueError,KeyError,TypeError,IndexError,StopIteration,Exhausted) as error:
                            result={'error':str(error),'invalid':lab.invalid(str(error)) if lab.remaining else None};image=None
                        event['tools'].append({'name':call['function']['name'],'call_id':call['id'],'result':result,'image_queued':bool(image)})
                        messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps({'result':result,'state':lab.state()})})
                        if image:images.append(image)
                    for image in images:messages.append({'role':'user','content':[{'type':'text','text':'Current exact geometry and numerical deformation. Magnification labeled; JSON is authoritative.'},{'type':'image_url','image_url':{'url':image}}]})
                    messages.append({'role':'user','content':f'Model requests remaining {3-turn}; candidate slots remaining {lab.remaining}.'})
            except (ValueError,TypeError,KeyError,IndexError) as error:
                event['response_error']=str(error)
                if lab.remaining:event['invalid']=lab.invalid('Malformed/rejected model response')
                messages.append({'role':'user','content':'Malformed response. Use a permitted tool.'})
        with (directory/'events.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(event)+'\n')
        print(f"{lab.task['id']} Muse turn {turn+1}, HTTP {transport.get('http_status')}, candidates {len(lab.records)}",flush=True)
        if stop or not lab.remaining:break
    return {'events':events,'actual_api_calls':len(events),'seed_label':seed,'remote_seed_guarantee':False}
