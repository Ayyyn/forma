"""Prospective repair study; preserves the earlier nonlinear pilot unchanged."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,os,shutil,time
from pathlib import Path
import numpy as np
from scipy.stats import qmc
from nonlinear_discovery import model as old
from nonlinear_discovery.experiment import tools as old_tools
from scripts.api_preflight import load_env,request
from structure_lab.tool_protocol import normalize
from .engine import evaluate,tolerance_check

ROOT=Path(__file__).resolve().parents[1]
LIMIT=32
SYSTEM='''Investigate a guided four-cell nonlinear Kresling assembly. This is a repair/robustness development experiment, not a general AI benchmark. All previous raw results remain unchanged. Use only evaluate_design / inspect_design / finish tools. Published JMPS2024 cell energy; ideal coaxial guide, total shortening55mm, additional end twist0, six internal coordinates. Four n6,r30mm cells,ks50N,kr.005. Ideal bilateral ring springs, first spring has externally selected rest values A/B. No contact, lateral instability, finite thickness, hinge hardware, stress/fatigue or fabricated-device physics. Geometry is not a stable state. Both settings require two opposite LOCAL minima: polarization P=(u0+u1-u2-u3)/55; A prefers P>=.35, B prefers P<=-.35. Selected target and opposite must both have Hessian eigenvalue>=.0002, axial clamp force<=1.5N, clamp torque<=5Nmm. Bias to lowest FOUND non-target minimum>=.5mJ. Index-one-saddle directed numerical descents supplement identical16 stationary starts/setting. Both selected modes need a constructed path to another minimum; reject any found sampled path height<.5mJ. Those are SAMPLED path energies, not certified barriers or retention. Missing paths fail the screen, not an impossibility proof. Objective: maximize smaller A/B found-state bias among nominal-screen passers. Top3/policy get128starts/setting, independent energy/Hessian audit and8seeded tolerance continuations (h0+-1%,theta+-.25deg,k+-5%,axial offsets+-.25mm,torsion+-.01rad); all8 must preserve four selected modes and force/torque/Hessian limits for final acceptance. These are sampled checks, not physical validation or global robustness.32 candidate queries including3 shared known designs. Same evaluator/candidate cap for a full-range numerical controller; root iterations and saddle counts vary, so not equal CPU/FLOPs. Invalid new designs charged; cached inspection free. At most8API calls. Batch useful tool evaluations. Do not invent results or tools. Last high-bias design had47.16mJ bias but .0208mJ shallow path and only2/8 tolerance samples passed. Equal common offsets on paired half torsion springs merely add a constant at clamped end twist; removing them removes30Nmm gratuitous clamp torque but does not repair shallow minima. This engineering identity is shared context, not an AI discovery. Balance bias against persistence, geometry and spring topology; a larger bias by itself is not useful. No novelty/avoided-prototypes/AI-superiority claims.'''

def shared():
    prior=json.loads((ROOT/'research/nonlinear-robustness-corrected.json').read_text())['result']['design']
    return [old.reference(),prior,json.loads((ROOT/'research/nonlinear-catalogue-challenge.json').read_text())['best']['design']]

def hashes():
    files=list((ROOT/'robust_discovery').glob('*.py'))+list((ROOT/'nonlinear_discovery').glob('*.py'))+list((ROOT/'kresling_proof').glob('*.py'))
    files += [ROOT/'scripts/api_preflight.py',ROOT/'structure_lab/tool_protocol.py',ROOT/'docs/ROBUST_DISCOVERY_PROTOCOL.md',ROOT/'research/nonlinear-robustness-corrected.json',ROOT/'research/nonlinear-catalogue-challenge.json']
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def freeze(directory):
    directory.mkdir(parents=True,exist_ok=False);source=hashes()
    manifest={'created_at_utc':datetime.now(timezone.utc).isoformat(),'source_hashes':source,'candidate_limit':LIMIT,'stationary_starts_per_setting':16,'directed_saddles_per_setting_maximum':12,'final_starts_per_setting':128,'final_candidates_per_policy':3,'tolerance_trials':8,'model':'muse-wonder-1.0','maximum_API_calls':8,'estimated_cost_cap_USD':15,'rates_per_million':{'input':4,'cached':.2,'output':20},'shared_designs':shared(),'system_prompt':SYSTEM,'scope':'Single-task prospective development comparison; not confirmatory population evidence. Candidate evaluator/caps equal, variable numerical work logged.','hardware_tests':0}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
    for name in source:
        p=directory/'source'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    print('Frozen',directory)

def load(directory):
    m=json.loads((directory/'manifest.json').read_text())
    if m['source_hashes']!=hashes():raise ValueError('Frozen source mismatch; create a new version')
    return m

def compact(r):
    if not r['valid']:return r
    s=r['result']['summary'];details={}
    for k,d in s['details'].items():
        details[k]={a:b for a,b in d.items() if a not in ['target','counter','competitor','identified_sampled_escape_paths']}
        for role in ['target','counter','competitor']:
            if role in d:details[k][role]=d[role]
    return {'id':r['id'],'design':r['design'],'summary':{**{k:v for k,v in s.items() if k!='details'},'details':details},'seconds':r['seconds']}

def rank(r):
    if not r['valid']:return (2,1e9,1e9)
    s=r['result']['summary'];return (0 if s['passes_nominal_screen'] else 1,s['violation'] if not s['passes_nominal_screen'] else 0.,-(s['worst_bias_N_mm'] or -1e6))

class Lab:
    def __init__(self):self.records=[];self.cache={};self.hits=0
    @property
    def remaining(self):return LIMIT-len(self.records)
    @property
    def best(self):return min(self.records,key=rank)
    def invalid(self,error):
        if not self.remaining:raise ValueError('Budget exhausted')
        r={'id':f'r{len(self.records):03d}','valid':False,'error':str(error)};self.records.append(r);return r
    def evaluate(self,d):
        key=json.dumps(d,sort_keys=True)
        if key in self.cache:self.hits+=1;return self.cache[key]
        if not self.remaining:raise ValueError('Budget exhausted')
        r={'id':f'r{len(self.records):03d}','design':deepcopy(d)};self.records.append(r);self.cache[key]=r;t=time.monotonic()
        try:r.update(valid=True,result=evaluate(d,16))
        except (ValueError,KeyError,TypeError,FloatingPointError,OverflowError,np.linalg.LinAlgError) as e:r.update(valid=False,error=str(e))
        r['seconds']=time.monotonic()-t;return r
    def state(self):return {'remaining':self.remaining,'cache_hits':self.hits,'best':compact(self.best)}

def numerical(lab):
    # A known-mechanism continuation sweep, then full-range Sobol architecture
    # variation. Same old full allowed bounds, including extrema, unlike v1.
    for ka in [.006,.012,.018,.024]:
        for kt in [10.,20.,30.]:
            d=old.reference();d.pop('note',None);d['springs'][0].update(k=ka,offset_A=45.,offset_B=10.)
            d['springs'] +=[{'type':'torsion','rings':span,'k':kt,'offset':0.} for span in [[0,2],[2,4]]];lab.evaluate(d)
    points=qmc.Sobol(16,scramble=True,seed=30102027).random_base2(5)
    for i,row in enumerate(points):
        if not lab.remaining:break
        d=deepcopy(lab.best['design']);d.pop('note',None)
        d['springs'][0].update(k=float(.001+.079*row[0]),offset_A=float(-10+70*row[1]),offset_B=float(-10+70*row[2]))
        if d['springs'][0]['type']!='axial':raise ValueError('Shared numerical starting design must have axial programmed spring')
        if i%3==0:
            d['cells']=[{'h0_mm':float(36+8*row[3+j]),'theta0_deg':float(28+6*row[7+j])} for j in range(4)]
        if i%3==1:
            d['handedness']=[[1,-1,1,-1],[1,1,-1,-1],[1,-1,-1,1]][min(2,int(row[11]*3))]
            for s in d['springs'][1:]:s['k']=float((30. if s['type']=='torsion' else .08)*(.01+.99*row[12]));s['offset']=0.
        if i%3==2:
            span=list(old.SPANS[min(len(old.SPANS)-1,int(row[13]*len(old.SPANS)))]);kind='axial' if row[14]<.5 else 'torsion'
            s={'type':kind,'rings':span,'k':float(.001+.079*row[12]) if kind=='axial' else float(.1+29.9*row[12]),'offset':float(-10+70*row[15]) if kind=='axial' else float(-1.5+3*row[15])}
            if len(d['springs'])<4:d['springs'].append(s)
            else:d['springs'][-1]=s
        lab.evaluate(d)

def tool_schema():
    out=old_tools()
    out[0]['function']['description']='Evaluate design with16 stationary starts/setting plus saddle-directed descents. Read actual minima, found-state bias, forces, torques and sampled path screen.'
    out[1]['function']['description']='Inspect cached minimum coordinates, found-state energies and sampled path summaries. No new solve.'
    return out

def meta(lab,directory):
    load_env();key=os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY')
    if not key:raise ValueError('Missing Meta key')
    context={'shared_results':[compact(r) for r in lab.records],'grammar':{'h0_mm':[36,44],'theta0_deg':[28,34],'handedness':'two +1 and two -1','spring_count':[1,4],'allowed_spans':old.SPANS,'axial_k':[.000001,.08],'axial_offset':[-10,60],'torsion_k':[.000001,30],'torsion_offset':[-1.5,1.5],'first_spring_offsets':['offset_A','offset_B'],'other_spring_offset':'offset'},'remaining_queries':lab.remaining}
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(context)}];events=[];spent=0.
    for turn in range(8):
        payload={'model':'muse-wonder-1.0','messages':messages,'tools':tool_schema(),'tool_choice':'auto','max_tokens':12288,'reasoning_effort':'high','temperature':.3};encoded=json.dumps(payload).encode();reserve=len(encoded)*4e-6+12288*20e-6
        if spent+reserve>15:break
        transport,body=request('https://api.meta.ai/v1',key,'/chat/completions',payload,timeout=240);usage=transport.get('usage') or {};cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens',0)
        cost=(usage.get('prompt_tokens',0)-cached)*4e-6+cached*.2e-6+usage.get('completion_tokens',0)*20e-6;spent+=cost
        event={'turn':turn+1,'transport':transport,'response_id':body.get('id') if body else None,'returned_model':body.get('model') if body else None,'request_sha256':hashlib.sha256(encoded).hexdigest(),'reserved_estimate_USD':reserve,'estimated_USD':cost};events.append(event);stop=False
        try:
            if not body:raise ValueError('No API body')
            choice=body['choices'][0];m=choice['message'];public={'role':'assistant','content':m.get('content'),'tool_calls':m.get('tool_calls') or []};event['received_assistant']=public;event['finish_reason']=choice.get('finish_reason')
            public,encoding=normalize(public,{t['function']['name'] for t in tool_schema()},event['response_id']);event.update(encoding=encoding,assistant=public,tools=[]);calls=public.get('tool_calls') or []
            if not calls:
                if lab.remaining:lab.invalid('No executable tool command')
                messages.append({'role':'user','content':'No usable tool command; charged. Use registered tools.'})
            else:
                messages.append(public)
                for call in calls:
                    try:
                        name=call['function']['name'];args=json.loads(call['function']['arguments'])
                        if name=='evaluate_design' and set(args)=={'design'}:out=compact(lab.evaluate(args['design']))
                        elif name=='inspect_design' and set(args)=={'design_id'}:out=compact(next(r for r in lab.records if r['id']==args['design_id']))
                        elif name=='finish' and not args:out={'finished':True};stop=True
                        else:raise ValueError('Invalid tool/schema')
                    except (ValueError,KeyError,TypeError,StopIteration) as e:out={'error':str(e),'invalid':lab.invalid(str(e)) if lab.remaining else None}
                    event['tools'].append({'name':call['function']['name'],'call_id':call['id'],'result':out});messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps({'result':out,'state':lab.state()})})
                messages.append({'role':'user','content':f'API calls left {7-turn}; candidate queries left {lab.remaining}; estimated cost ${spent:.3f} / $15. Exploit real evidence; finish when done.'})
        except (ValueError,KeyError,TypeError,IndexError) as e:
            event['error']=str(e)
            if lab.remaining:lab.invalid(str(e))
        with (directory/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event)+'\n')
        # Preserve partial candidate evidence after every received API response.
        (directory/'checkpoint.json').write_text(json.dumps(lab.records))
        print(f'Robust Muse turn {turn+1}: HTTP {transport.get("http_status")}, queries {len(lab.records)}, estimated ${spent:.3f}',flush=True)
        if stop or not lab.remaining:break
    return {'actual_API_calls':len(events),'estimated_USD':spent,'billing_verified':False}

def run(directory,method):
    m=load(directory);target=directory/method;target.mkdir(exist_ok=False);lab=Lab();t=time.monotonic()
    for d in m['shared_designs']:lab.evaluate(d)
    api=meta(lab,target) if method=='meta' else numerical(lab)
    ledger={'stationary_starts':sum(sum(s['attempts'] for s in r['result']['settings'].values()) for r in lab.records if r['valid']),'directed_minimizations':sum(sum(s['directed_minimizations'] for s in r['result']['settings'].values()) for r in lab.records if r['valid'])}
    result={'method':method,'records':lab.records,'cache_hits':lab.hits,'seconds':time.monotonic()-t,'API':api,'work_ledger':ledger}
    (target/'result.json').write_text(json.dumps(result));print(json.dumps({'method':method,'queries':len(lab.records),'seconds':result['seconds'],'ledger':ledger,'best':compact(lab.best),'API':api}))

def finalize(directory):
    load(directory);output={}
    for method in ['numerical','meta']:
        raw=json.loads((directory/method/'result.json').read_text());audited=[]
        for r in sorted(raw['records'],key=rank)[:3]:
            if not r['valid']:continue
            refined=evaluate(r['design'],128,True);audit=old.audit(r['design'],refined);tol=refined.get('tolerance',{});passed=refined['summary']['passes_nominal_screen'] and audit['passed'] and tol.get('passed_trials')==8
            audited.append({'id':r['id'],'design':r['design'],'result':refined,'independent_audit':audit,'accepted':bool(passed)});print(f'Final audited {method} {r["id"]}: {passed}',flush=True)
        accepted=[r for r in audited if r['accepted']];best=max(accepted,key=lambda r:r['result']['summary']['worst_bias_N_mm'],default=None)
        output[method]={'query_count':len(raw['records']),'valid_queries':sum(r['valid'] for r in raw['records']),'nominal_passes':sum(r['valid'] and r['result']['summary']['passes_nominal_screen'] for r in raw['records']),'work_ledger':raw['work_ledger'],'seconds':raw['seconds'],'API':raw['API'],'audited':audited,'best_accepted_id':best['id'] if best else None,'best_accepted_bias_N_mm':best['result']['summary']['worst_bias_N_mm'] if best else None}
    (directory/'summary.json').write_text(json.dumps({'scope':'Exploratory single-task robustness repair; no general AI effect or physical validation','methods':output},indent=2));print(json.dumps({k:{a:b for a,b in v.items() if a!='audited'} for k,v in output.items()},indent=2))
