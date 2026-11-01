"""Bounded real Muse tool probe. Development integration, not efficacy evidence."""
import base64
import hashlib
import json
import os
from pathlib import Path
from scripts.api_preflight import load_env,request
from structure_lab.tool_protocol import normalize
from .design import geometry,catalogue,bounds,task
from .laboratory import Lab,Exhausted


SYSTEM='''You are designing a loaded spatial compliant transmission with actual numerical tools. The input is an external force source; the structure is passive. Minimize summed circular member volume while satisfying ALL requirements. Stroke is displacement against the stated output spring, not unloaded motion. Output force=k*stroke and stored spring energy=.5*k*stroke^2. Input work is a quasistatic ramp .5*F*u; stored spring energy divided by input work is an energy allocation, NOT cyclic efficiency or energy generation. Use exact N/mm/radian quantities and local radius sizing tools rather than calculating mechanics in prose. Six DOFs per node, rigid ideal joints, circular Euler-Bernoulli beams with torsion, synthetic E/nu, infinitesimal strain/displacement. No finite motion, contact, fatigue, joint stress concentrations or clinical claims. Nominal strains and a conservative pinned-member Euler ratio are guards, not loaded buckling certification. Finite-radius collisions are checked only in initial geometry, with joint overlaps idealized. The returned full margins decide feasibility. The optimizer directly constrains stroke, input travel and output x/y motion; other guards remain acceptance checks. You can propose any edge subset from the stated ground graph, inspect multiple actual views with DOF axes and deformation magnification, inspect exact port/sensitivity results, and invoke the common analytic-gradient sizing optimizer. All optimizer candidates consume the shared allowance. Cache hits are free and logged. There are at most four API requests and 192 candidate slots total. Public explanations should be short. Keep topology proposals distinct and motivated by computed failures. No external case answers are available. A successful development case is not general AI superiority or a new scientific structure. finish ends the probe; the host independently verifies and ranks evaluated results.'''


def definitions():
    def obj(properties,required):return {'type':'object','properties':properties,'required':required,'additionalProperties':False}
    ident={'type':'array','items':{'type':'integer'},'minItems':1,'maxItems':35}
    return [{'type':'function','function':{'name':name,'description':description,'parameters':schema}} for name,description,schema in [
        ('evaluate','Evaluate custom graph. One radius for each edge in the supplied order. Invalid new designs consume one slot.',obj({'edge_ids':ident,'radii_mm':{'type':'array','items':{'type':'number'},'minItems':1,'maxItems':35}},['edge_ids','radii_mm'])),
        ('optimize','Size a template, custom edge graph, or evaluated start_id. allocation counts new candidates within this tool.',obj({'template':{'type':'string'},'edge_ids':ident,'start_id':{'type':'string'},'allocation':{'type':'integer','minimum':1,'maximum':192},'start_fraction':{'type':'number','minimum':0,'maximum':1}},['allocation'])),
        ('inspect','Inspect an evaluated design or current best: exact metrics, all radius sensitivities and orthographic/spatial views. No new physics solve.',obj({'design_id':{'type':'string'}},[])),
        ('finish','End the probe; deterministic verified ranking selects the result.',obj({},[]))]]


def handle(lab,name,args,directory):
    allowed={v['function']['name']:v['function']['parameters'] for v in definitions()}
    if name not in allowed:raise ValueError('Unknown tool')
    if not isinstance(args,dict):raise ValueError('Tool arguments must be object')
    schema=allowed[name]
    if set(args)-set(schema['properties']) or not set(schema['required'])<=set(args):raise ValueError('Unexpected/missing tool fields')
    if name=='evaluate':return lab.evaluate(**args),None
    if name=='optimize':
        if sum(k in args for k in ['template','edge_ids','start_id'])!=1:raise ValueError('Choose exactly one topology/start source')
        return lab.optimize(**args),None
    if name=='finish':return {'finished':True},None
    record=next((r for r in lab.records if r['id']==args.get('design_id')),None) if args.get('design_id') else lab.best
    if not record or not record['valid']:raise ValueError('Inspect needs a valid evaluated design')
    from .figures import design_figure
    target=directory/f'view-{len(list(directory.glob("view-*.png"))):02d}.png'
    internal=lab.internal[record['id']];design_figure(lab.task,record,target,evaluated=internal)
    out=6*lab.task['output_node']+lab.task['output_axis'];inp=6*lab.task['input_node']+lab.task['input_axis']
    return {'design':record,'sensitivity_order_edge_ids':record['edge_ids'],
            'd_stroke_d_radius':internal['solved']['du_dr'][:,out,0].tolist(),
            'd_input_travel_d_radius':internal['solved']['du_dr'][:,inp,0].tolist(),
            'd_volume_d_radius':internal['solved']['dvolume_dr'].tolist(),'figure':target.name},'data:image/png;base64,'+base64.b64encode(target.read_bytes()).decode()


def probe(directory,model='muse-wonder-1.0',turns=4):
    from .laboratory import source_manifest
    frozen=json.loads((directory/'manifest.json').read_text())
    if source_manifest()!=frozen['source_hashes']:raise ValueError('Source drift: create a new version, do not alter a frozen probe')
    if (directory/'meta-probe.json').exists():raise ValueError('Existing paid probe preserved; choose a new directory for another probe')
    if (directory/'meta-events.jsonl').exists():raise ValueError('Existing partial paid journal preserved; do not silently repeat paid requests')
    if turns!=4 or model!='muse-wonder-1.0':raise ValueError('This frozen development probe specifies Wonder 1.0, four requests maximum')
    load_env();key=os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY')
    if not key:raise ValueError('MODEL_API_KEY missing')
    t=frozen['task'];lab=Lab(t);nodes,edges=geometry()
    context={'task':t,'nodes_mm':nodes,'edge_options':[{'id':i,'nodes':list(e)} for i,e in enumerate(edges)],
             'clamped_nodes':[0,1,2,3],'catalogue':catalogue(),'bounds_note':'Radius bounded by task min/max AND diameter <= .1*member length.',
             'geometry_scope':'10 nodes / 35 admissible edges, finite-radius initial nonjoint collisions rejected; both ports connected to anchors.',
             'state':lab.state(),'status':'Known development problem. Neither previous numerical answer nor posthoc improvements are supplied.'}
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(context)}];events=[]
    journal=directory/'meta-events.jsonl'
    for turn in range(turns):
        payload={'model':model,'messages':messages,'tools':definitions(),'tool_choice':'auto','max_tokens':6144,'reasoning_effort':'medium','temperature':.2}
        transport,body=request('https://api.meta.ai/v1',key,'/chat/completions',payload,timeout=180)
        event={'turn':turn+1,'transport':transport,'response_id':body.get('id') if body else None,'returned_model':body.get('model') if body else None,
               'request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
               'image_inputs_transmitted':sum(p.get('type')=='image_url' for m in messages if isinstance(m.get('content'),list) for p in m['content'])}
        events.append(event)
        if not body:event['stopped']='transport_failure'
        else:
            choice=body['choices'][0];message=choice['message'];event['finish_reason']=choice.get('finish_reason')
            public={'role':'assistant','content':message.get('content'),'tool_calls':message.get('tool_calls') or []};event['received_assistant']=public
            try:public,encoding=normalize(public,{d['function']['name'] for d in definitions()},event['response_id']);event['encoding']=encoding
            except (ValueError,TypeError,KeyError) as error:event['normalization_error']=str(error);public={'role':'assistant','content':None,'tool_calls':[]}
            event['assistant']=public;calls=public.get('tool_calls') or [];event['tools']=[];images=[];finished=False
            if not calls:
                if lab.remaining:event['invalid']=lab.invalid('No executable command, including truncated responses','model_response')
                messages.append({'role':'user','content':json.dumps({'error':'No usable tool command; one slot charged. Use the numerical tools.','state':lab.state()})})
            else:
                messages.append(public)
                for call in calls:
                    name=call['function']['name'];arguments=call['function']['arguments']
                    try:
                        result,image=handle(lab,name,json.loads(arguments),directory);finished=finished or name=='finish'
                    except (ValueError,KeyError,TypeError,IndexError,StopIteration,Exhausted) as error:
                        result={'error':str(error),'invalid':lab.invalid(str(error)) if lab.remaining else None};image=None
                    event['tools'].append({'name':name,'call_id':call['id'],'result':result,'image_queued':bool(image)})
                    messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps({'result':result,'state':lab.state()})})
                    if image:images.append(image)
                for image in images:messages.append({'role':'user','content':[{'type':'text','text':'Actual numerical geometry/deformation views. Magnification explicitly labeled; exact JSON determines dimensions.'},{'type':'image_url','image_url':{'url':image}}]})
                event['finished']=finished
                messages.append({'role':'user','content':f'Model requests left: {turns-turn-1}; candidates left: {lab.remaining}.'})
        with journal.open('a',encoding='utf-8') as stream:stream.write(json.dumps(event)+'\n')
        print(f"Muse request {turn+1}: HTTP {transport.get('http_status')}, candidates {len(lab.records)}, feasible best {bool(lab.best and lab.best['feasible'])}",flush=True)
        if not body or event.get('finished') or not lab.remaining:break
    report={'scope':'development integration probe, no statistical efficacy claim','model':model,'events':events,'actual_requests':len(events),
            'records':lab.records,'state':lab.state(),'independent_best_check':lab.verify()}
    with (directory/'meta-probe.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    return report
