"""Versioned nonlinear architecture discovery, equal root-start work per query."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import numpy as np
from scipy.stats import qmc
from scripts.api_preflight import load_env,request
from structure_lab.tool_protocol import normalize
from .model import reference,validate,evaluate,audit,mesh,SPANS,independent_energy,jet

ROOT=Path(__file__).resolve().parents[1]
SYSTEM='''You are investigating nonlinear programmable mechanical assemblies using an independently checked published reduced cell model and ideal ring-to-ring spring couplings. This is architecture/prestress discovery, not the previous linear beam task. Four Kresling cells (n=6,r=30 mm,ks=50N,kr=.005) remain coaxial under an IDEAL GUIDE. Total shortening is 55mm and additional end twist is clamped at zero. Six internal coordinates are free. The guide excludes lateral modes. Quasistatic local equilibria, not dynamic trajectories, are computed. Spring 0 has two externally set rest/preload values A/B; other springs have fixed preload. Axial ring spring measures SUM of shortenings in its span in mm; torsional ring spring measures SUM of handedness*additional twist in radians. All springs are ideal bilateral elements; actual routing, hardware, one-way slack, contact and fabrication are unsupported. Cell energies follow Zang JMPS 2024 and prestress is established prior art in Zang PNAS 2025. Nothing here is an invented principle. The objective is a memory-like device: at both settings, find stable minima with first two cells more folded AND with last two more folded. Polarization=(u0+u1-u2-u3)/55. Setting A should energetically prefer polarization>=.35, B should prefer <=-.35. Both opposite modes must remain local minima at each setting; energy bias to the lowest FOUND non-target minimum >=.5 Nmm, normalized selected Hessian eigenvalue>=.0002, selected axial holding force magnitude<=1.5N. Maximize the smaller A/B bias among feasible designs. Found minima are NOT exhaustive or a global-minimum proof. Final independent and denser-start audits may reject apparent successes. Use actual tools to evaluate architectures; do not infer stability from geometry. Geometry/gradients alone are not equilibrium or stability. You have 24 charged candidate queries total, including the shared reference; each new query uses 16 stationary starts at each of two settings (32 root-start attempts). Invalid new actions consume one query. Inspection reuses cached results. At most eight model requests. Batch useful evaluations, explore topology and chirality as well as stiffness, then exploit actual tool evidence. Do not run code or modify physics. Keep public explanations short. A larger bias in a small development experiment is not general AI advantage, physical validation or novelty. Never claim avoided prototypes or a new-to-science design.'''


def hashes():
    paths=list((ROOT/'nonlinear_discovery').glob('*.py'))+list((ROOT/'kresling_proof').glob('*.py'))+[ROOT/'scripts/api_preflight.py',ROOT/'structure_lab/tool_protocol.py',ROOT/'docs/NONLINEAR_DISCOVERY_PROTOCOL.md']
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def freeze(directory):
    directory.mkdir(parents=True,exist_ok=False);source=hashes()
    manifest={'created_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Exploratory nonlinear architecture discovery; single task/trajectory, not confirmatory benchmark',
              'source_hashes':source,'candidate_queries_per_policy':24,'starts_per_setting':16,'settings':['A','B'],
              'common_final_refinement_starts_per_setting':64,'final_refined_candidates_per_policy':3,
              'maximum_api_calls':8,'model':'muse-wonder-1.0','reasoning_effort':'high','max_output_tokens':12288,
              'estimated_API_cost_cap_USD':15.,'rates_per_million':{'input':4.,'cached':.2,'output':20.},
              'budget_note':'Conservative pre-request reserve uses UTF-8 input bytes as token bound plus maximum output. No images in API requests in this phase. Actual promotional-credit deduction unverified.',
              'task':'Prefer opposite localized configurations under two preload settings, retaining both local minima at each setting and bounded holding force; maximize smaller found-state bias.',
              'literature':['https://doi.org/10.1016/j.jmps.2024.105630','https://doi.org/10.1073/pnas.2426790122'],
              'physical_experiments':0,'scientific_novelty_claim':False}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
    for name in source:
        target=directory/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    print(json.dumps({'frozen':str(directory),'maximum_API_calls':8,'estimated_API_cap_USD':15}))


def load(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['source_hashes']!=hashes():raise ValueError('Frozen source mismatch; preserve old study and create a separate version')
    return manifest


def compact(record):
    if not record.get('valid'):return record
    r=record['result']
    return {'id':record['id'],'design':record['design'],'feasible':r['feasible'],'violation':r['violation'],'worst_bias_N_mm':r['worst_bias_N_mm'],
            'minimum_selected_hessian_eigenvalue':r['minimum_selected_hessian_eigenvalue'],'maximum_selected_holding_force_N':r['maximum_selected_holding_force_N'],
            'settings':{k:[{'polarization':s['polarization'],'energy_N_mm':s['energy_N_mm'],'classification':s['classification'],'minimum_eigenvalue':s['hessian_eigenvalues_normalized'][0]} for s in v['states']] for k,v in r['settings'].items()}}


def rank(record):
    if not record.get('valid'):return (2,1e9,1e9)
    r=record['result'];return (0 if r['feasible'] else 1,r['violation'] if not r['feasible'] else 0.,-(r['worst_bias_N_mm'] or -1e6))


class Lab:
    def __init__(self):self.records=[];self.cache={};self.cache_hits=0
    @property
    def remaining(self):return 24-len(self.records)
    @property
    def best(self):return min(self.records,key=rank) if self.records else None
    def invalid(self,message):
        if not self.remaining:raise ValueError('Budget exhausted')
        r={'id':f'n{len(self.records):03d}','valid':False,'error':str(message)};self.records.append(r);return r
    def evaluate(self,design):
        key=json.dumps(design,sort_keys=True)
        if key in self.cache:self.cache_hits+=1;return self.cache[key]
        if not self.remaining:raise ValueError('Budget exhausted')
        started=time.monotonic();record={'id':f'n{len(self.records):03d}','design':deepcopy(design)};self.records.append(record);self.cache[key]=record
        try:record.update(valid=True,result=evaluate(design,16))
        except (ValueError,KeyError,TypeError,FloatingPointError,OverflowError) as e:record.update(valid=False,error=str(e))
        record['seconds']=time.monotonic()-started;return record
    def state(self):return {'remaining_queries':self.remaining,'cache_hits':self.cache_hits,'best':compact(self.best) if self.best else None}


def numerical(lab):
    lab.evaluate(reference())
    # A strong ordinary control for the established one-spring mechanism:
    # stiffness continuation, then geometric/architectural Sobol variation.
    for k in [.002,.005,.02,.035,.05,.065,.08]:
        d=reference();d['springs'][0]['k']=k;lab.evaluate(d)
    sampler=qmc.Sobol(12,scramble=True,seed=29102026);points=sampler.random_base2(4)
    for row in points:
        if not lab.remaining:break
        d=deepcopy(lab.best['design']);d.pop('note',None)
        d['springs'][0]['k']=float(.003+.067*row[0]);d['springs'][0]['offset_A']=float(32+23*row[1]);d['springs'][0]['offset_B']=float(23*row[2])
        if row[3]>.4:
            d['cells']=[{'h0_mm':float(36+8*row[4+i]),'theta0_deg':float(28+6*row[8+i])} for i in range(4)]
        if row[3]>.7:
            span=SPANS[min(len(SPANS)-1,int(row[5]*len(SPANS)))];kind='axial' if row[6]<.5 else 'torsion'
            d['springs'].append({'type':kind,'rings':list(span),'k':float(.025*row[7]+.001) if kind=='axial' else float(15*row[7]+.2),'offset':float(30*row[8]) if kind=='axial' else float(.8*row[8]-.4)})
        lab.evaluate(d)


def tools():
    design={'type':'object','properties':{'cells':{'type':'array','minItems':4,'maxItems':4,'items':{'type':'object','properties':{'h0_mm':{'type':'number'},'theta0_deg':{'type':'number'}},'required':['h0_mm','theta0_deg'],'additionalProperties':False}},
            'handedness':{'type':'array','minItems':4,'maxItems':4,'items':{'type':'integer'}},'springs':{'type':'array','minItems':1,'maxItems':4,'items':{'type':'object','properties':{'type':{'type':'string','enum':['axial','torsion']},'rings':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'integer'}},'k':{'type':'number'},'offset_A':{'type':'number'},'offset_B':{'type':'number'},'offset':{'type':'number'}},'required':['type','rings','k'],'additionalProperties':False}}},'required':['cells','handedness','springs'],'additionalProperties':False}
    return [{'type':'function','function':{'name':name,'description':desc,'parameters':params}} for name,desc,params in [
        ('evaluate_design','Evaluate nonlinear stationary states and constrained Hessians at two preload settings. Exactly 16 starts per setting. Design must obey the stated physical grammar.',{'type':'object','properties':{'design':design},'required':['design'],'additionalProperties':False}),
        ('inspect_design','Read complete cached equilibrium coordinates, forces, torques, energies and stability at both settings. No new root solve.',{'type':'object','properties':{'design_id':{'type':'string'}},'required':['design_id'],'additionalProperties':False}),
        ('finish','End this exploratory search; final common denser-start/independent audit decides acceptance.',{'type':'object','properties':{},'additionalProperties':False})]]


def run_meta(lab,directory):
    load_env();key=os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY')
    if not key:raise ValueError('Missing MODEL_API_KEY')
    lab.evaluate(reference());events=[];spent=0.
    context={'grammar':{'cell_count':4,'n':6,'radius_mm':30,'h0_mm':[36,44],'theta0_deg':[28,34],
                        'handedness':'two +1 and two -1','ring_ids':[0,1,2,3,4],'allowed_spring_ring_pairs':SPANS,
                        'maximum_springs':4,'spring0':'programmed offset_A and offset_B; all later springs require offset only',
                        'axial_k_N_per_mm':[.000001,.08],'axial_offsets_mm':[-10,60],'torsion_k_Nmm_per_rad':[.000001,30.],'torsion_offsets_rad':[-1.5,1.5]},
             'reference':compact(lab.best),'task':'Keep target and opposite modes stable at both settings; maximize smaller target-state energy bias without violating guards.',
             'literature_context':'Kresling elasticity JMPS2024; spring prestress and programming folding sequences PNAS2025 are established. Ideal bilateral ring springs here differ from one-way hardware. Do not claim paper reproduction for this assembly or novelty.'}
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(context)}]
    for turn in range(8):
        payload={'model':'muse-wonder-1.0','messages':messages,'tools':tools(),'tool_choice':'auto','max_tokens':12288,'reasoning_effort':'high','temperature':.3}
        encoded=json.dumps(payload).encode();reserve=len(encoded)*4e-6+12288*20e-6
        if spent+reserve>15:break
        transport,body=request('https://api.meta.ai/v1',key,'/chat/completions',payload,timeout=240)
        event={'turn':turn+1,'transport':transport,'response_id':body.get('id') if body else None,'returned_model':body.get('model') if body else None,'request_sha256':hashlib.sha256(encoded).hexdigest(),'reserved_estimate_USD':reserve}
        events.append(event);usage=transport.get('usage') or {};input_tokens=usage.get('prompt_tokens',0);cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens',0);output=usage.get('completion_tokens',0)
        cost=(input_tokens-cached)*4e-6+cached*.2e-6+output*20e-6;spent+=cost;event['reported_usage_estimated_USD']=cost;stop=False
        if not body:stop=True
        else:
            try:
                choice=body['choices'][0];event['finish_reason']=choice.get('finish_reason');m=choice['message'];public={'role':'assistant','content':m.get('content'),'tool_calls':m.get('tool_calls') or []};event['received_assistant']=public
                public,encoding=normalize(public,{t['function']['name'] for t in tools()},event['response_id']);event['encoding']=encoding;event['assistant']=public;calls=public.get('tool_calls') or [];event['tools']=[]
                if not calls:
                    if lab.remaining:lab.invalid('No executable model tool command, including truncation')
                    messages.append({'role':'user','content':'No usable tool command. Use the registered tools; invalid response charged.'})
                else:
                    messages.append(public)
                    for call in calls:
                        try:
                            name=call['function']['name'];args=json.loads(call['function']['arguments'])
                            if name=='evaluate_design' and set(args)=={'design'}:result=compact(lab.evaluate(args['design']))
                            elif name=='inspect_design' and set(args)=={'design_id'}:result=next(r for r in lab.records if r['id']==args['design_id'])
                            elif name=='finish' and args=={}:result={'finished':True};stop=True
                            else:raise ValueError('Unknown tool or arguments')
                        except (ValueError,KeyError,TypeError,StopIteration) as e:result={'error':str(e),'invalid':lab.invalid(str(e)) if lab.remaining else None}
                        event['tools'].append({'name':call['function']['name'],'result':result,'call_id':call['id']})
                        messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps({'result':result,'state':lab.state()})})
                    messages.append({'role':'user','content':f'API requests remaining {7-turn}; candidate queries {lab.remaining}; reported usage estimate ${spent:.3f} of $15 cap. Explore or finish.'})
            except (ValueError,KeyError,TypeError,IndexError) as e:
                event['error']=str(e)
                if lab.remaining:lab.invalid(str(e))
        with (directory/'events.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(event)+'\n')
        print(f"Nonlinear Muse turn {turn+1}: HTTP {transport.get('http_status')}, queries {len(lab.records)}, estimated ${spent:.3f}",flush=True)
        if stop or not lab.remaining:break
    return {'events':events,'actual_api_calls':len(events),'estimated_USD':spent,'billing_verified':False}


def run(directory,method):
    load(directory);target=directory/method
    if target.exists():raise ValueError('Existing run preserved; no silent retries')
    target.mkdir();lab=Lab();started=time.monotonic();meta=None
    if method=='numerical':numerical(lab)
    else:meta=run_meta(lab,target)
    result={'method':method,'records':lab.records,'best_screened_id':lab.best['id'] if lab.best else None,'cache_hits':lab.cache_hits,'seconds':time.monotonic()-started,'meta':meta,
            'stationary_start_attempts':sum(sum(v['attempts'] for v in r['result']['settings'].values()) for r in lab.records if r.get('valid'))}
    (target/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({'method':method,'queries':len(lab.records),'best':compact(lab.best),'stationary_start_attempts':result['stationary_start_attempts']},indent=2))


def finalize(directory):
    load(directory);summaries={};board=[]
    for method in ['numerical','meta']:
        raw=json.loads((directory/method/'result.json').read_text());ranked=sorted([r for r in raw['records'] if r.get('valid')],key=rank)[:3];audited=[]
        for rec in ranked:
            result=evaluate(rec['design'],64);check=audit(rec['design'],result);accepted=bool(result['feasible'] and check['passed'])
            entry={'id':rec['id'],'design':rec['design'],'screened':rec['result'],'refined':result,'independent_audit':check,'accepted':accepted};audited.append(entry)
            item={'id':method+'-'+rec['id'],'method':method,'design':rec['design'],'accepted':accepted,'result':result,'audit':check,'views':[],'profiles':[]}
            for setting in ['A','B']:
                for state in result['settings'][setting]['states']:
                    item['views'].append({'setting':setting,'state':state,'mesh':mesh(rec['design'],state)})
                detail=result['details'][setting]
                if detail.get('target_and_counter_found'):
                    a=np.array(detail['target']['x']);b=np.array(detail['counter']['x']);points=[]
                    for t in np.linspace(0,1,61):
                        try:value=independent_energy(rec['design'],(1-t)*a+t*b,setting)*1500.;points.append([float(t),value])
                        except (ValueError,FloatingPointError):pass
                    item['profiles'].append({'setting':setting,'points':points,'label':'Straight configuration interpolation energy; NOT a minimum-energy path or switching barrier.'})
            board.append(item);print(f"Refined/audited {method} {rec['id']}: accepted={accepted}",flush=True)
        best=min([r for r in audited if r['accepted']],key=lambda r:-r['refined']['worst_bias_N_mm'],default=None)
        summaries[method]={'query_count':len(raw['records']),'valid_queries':sum(r.get('valid',False) for r in raw['records']),'stationary_start_attempts_screening':raw['stationary_start_attempts'],
                           'final_refined':audited,'best_accepted_id':best['id'] if best else None,'best_bias_N_mm':best['refined']['worst_bias_N_mm'] if best else None,'seconds_screening':raw['seconds'],'meta':raw.get('meta')}
    report={'scope':'Single-task nonlinear discovery pilot; no new-to-science or general AI superiority claim','methods':summaries,'physical_validation':False}
    (directory/'summary.json').write_text(json.dumps(report,indent=2));(directory/'board-data.json').write_text(json.dumps({'kind':'nonlinear','candidates':board},separators=(',',':')))
    print(json.dumps({m:{k:v for k,v in s.items() if k not in ['final_refined','meta']} for m,s in summaries.items()},indent=2))
