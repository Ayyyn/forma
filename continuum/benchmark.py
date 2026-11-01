"""Controlled search-planning comparison; all proposal evaluations pass one ledger."""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .geometry import Design, Requirements, evaluate
from .search import baseline_design
from .audit import audit_record
from .agent import load_env, request

ROOT=Path(__file__).resolve().parents[1]
MODEL='meta-models/muse-spark-open-1026'
BASE='https://inference.baseten.co/v1'
BUDGET=64
SEEDS=[101,202,303]


class Plan(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    family: Literal['both','miura','accordion']='both'
    gamma_min: float=Field(25,ge=25,le=90,description='Miura lower sector angle; ignored for accordion (fixed 90).')
    gamma_max: float=Field(85,ge=25,le=90,description='Miura upper sector angle, at most 85; ignored for accordion.')
    columns_min: int=Field(2,ge=2,le=16)
    columns_max: int=Field(16,ge=2,le=16)
    rows_min: int=Field(2,ge=1,le=12,description='Miura lower row count, at least 2; accordion always uses one row.')
    rows_max: int=Field(12,ge=1,le=12,description='Miura upper row count; ignored for accordion.')
    packed_theta_min: float=Field(65,ge=65,le=88)
    packed_theta_max: float=Field(88,ge=65,le=88)

    @model_validator(mode='after')
    def ordered(self):
        if self.family=='accordion':
            self.gamma_min=self.gamma_max=90
            self.rows_min=self.rows_max=1
        elif self.gamma_max>85 or self.rows_min<2:
            raise ValueError('Miura search bounds require gamma<=85 and rows>=2')
        for name in ('gamma','columns','rows','packed_theta'):
            if getattr(self,name+'_min')>getattr(self,name+'_max'):
                raise ValueError(name+' minimum exceeds maximum')
        return self


def propose(requirements,plan,count,seed):
    """Shared sampler; no evaluation, filtering, hidden exemplar, or rejection resampling."""
    rng=random.Random(seed)
    for _ in range(count):
        family=rng.choice(['miura','accordion']) if plan.family=='both' else plan.family
        gamma=90. if family=='accordion' else rng.uniform(plan.gamma_min,plan.gamma_max)
        cols=rng.randint(plan.columns_min,plan.columns_max)
        rows=1 if family=='accordion' else rng.randint(plan.rows_min,plan.rows_max)
        packed=rng.uniform(plan.packed_theta_min,plan.packed_theta_max)
        g,t=math.radians(gamma),math.radians(8)
        q=math.sqrt(1-math.sin(t)**2*math.sin(g)**2)
        # Construct deployed extents analytically. All methods receive this same mapping.
        target_x=requirements.deployed_x_min_mm*rng.uniform(1.005,1.06)
        target_y=requirements.deployed_y_min_mm*rng.uniform(1.005,1.06)
        b=target_y*q/(rows*math.sin(g)*math.cos(t))
        a=(target_x-b*math.cos(g)/q)/(cols*q)
        yield {'family':family,'columns':cols,'rows':rows,'a_mm':round(a,6),'b_mm':round(b,6),
               'gamma_deg':round(gamma,6),'deployed_theta_deg':8.,'packed_theta_deg':round(packed,6)}


def rank(result,objective):
    m=result['metrics']
    primary,secondary=(m['crease_segments'],m['material_area_mm2']) if objective=='creases' else (m['material_area_mm2'],m['crease_segments'])
    return (0,primary,secondary,m['packed_bounding_area_mm2']) if result['feasible'] else (1,result['normalized_violation'],primary,secondary)


class Ledger:
    def __init__(self,requirements,objective,budget=BUDGET):
        self.requirements,self.objective,self.budget=requirements,objective,budget
        self.records=[];self.seen=set()

    @property
    def remaining(self): return self.budget-len(self.records)

    def evaluate(self,proposal,origin):
        if not self.remaining: raise ValueError('Evaluation budget exhausted')
        entry={'attempt':len(self.records)+1,'origin':origin,'proposal':proposal}
        self.records.append(entry)  # Charge before validation; errors and duplicates consume attempts.
        try:
            d=Design.model_validate(proposal)
            if d.deployed_theta_deg!=8 or not 65<=d.packed_theta_deg<=88:
                raise ValueError('Outside common benchmark operating-angle domain')
            result=evaluate(d,self.requirements)
            entry.update(valid=True,duplicate=result['id'] in self.seen,result=result,
                         independent_audit=audit_record(result,self.requirements.model_dump()))
            self.seen.add(result['id'])
            if not entry['independent_audit']['passed']:raise RuntimeError('Independent scoring oracle disagreement')
        except (ValidationError,ValueError) as exc:
            entry.update(valid=False,error=str(exc)[:700],duplicate=False)
        return entry

    def best(self):
        results=[r['result'] for r in self.records if r['valid']]
        return min(results,key=lambda r:rank(r,self.objective)) if results else None

    def batch(self,plan,count,seed,origin):
        count=min(count,self.remaining)
        before=len(self.records)
        for proposal in propose(self.requirements,plan,count,seed):self.evaluate(proposal,origin)
        records=self.records[before:]
        valid=[r['result'] for r in records if r['valid']]
        valid.sort(key=lambda r:rank(r,self.objective))
        return {'attempts':len(records),'valid':len(valid),'feasible':sum(r['feasible'] for r in valid),
                'remaining_budget':self.remaining,'best_candidates':[compact(r) for r in valid[:6]],
                'invalid_examples':[r['error'] for r in records if not r['valid']][:2]}


def compact(result):
    return {'id':result['id'],'design':result['design'],'feasible':result['feasible'],
            'metrics':result['metrics'],'violations':[{k:c[k] for k in ('name','value','limit','violation')}
              for c in result['constraints'] if not c['passed']]}


TASKS=[
 {'id':'tight_pocket','objective':'creases','changes':{}},
 {'id':'generous_pocket','objective':'creases','changes':{'deployed_x_min_mm':220,'deployed_y_min_mm':120,'packed_long_max_mm':160,'packed_short_max_mm':55,'packed_height_max_mm':30,'crease_segments_max':80}},
 {'id':'shallow_packet','objective':'creases','changes':{'packed_long_max_mm':140,'packed_short_max_mm':38,'packed_height_max_mm':16,'crease_segments_max':200}},
 {'id':'few_folds','objective':'creases','changes':{'deployed_x_min_mm':200,'deployed_y_min_mm':120,'packed_long_max_mm':115,'packed_short_max_mm':45,'packed_height_max_mm':24,'crease_segments_max':48}},
 {'id':'larger_surface','objective':'material','changes':{'deployed_x_min_mm':260,'deployed_y_min_mm':165,'packed_long_max_mm':135,'packed_short_max_mm':55,'packed_height_max_mm':22,'crease_segments_max':200}},
 {'id':'impossible_blank_width','objective':'creases','changes':{'deployed_y_min_mm':220,'blank_y_max_mm':190,'packed_long_max_mm':160,'packed_short_max_mm':60,'packed_height_max_mm':30,'crease_segments_max':200}},
]


def task_requirements(task):return Requirements(**{**Requirements().model_dump(),**task['changes']})


def deterministic(ledger,seed):
    # Constraint-directed family pruning is a proof, not a model-provided hint.
    family='miura' if ledger.requirements.deployed_y_min_mm>ledger.requirements.packed_long_max_mm else 'both'
    plan=Plan(family=family)
    trace=[]
    for stage in range(3):
        if stage:
            best=ledger.best()
            if best and best['design']['family']=='miura':
                d=best['design']
                plan=Plan(family='miura',gamma_min=max(25,d['gamma_deg']-10),gamma_max=min(85,d['gamma_deg']+10),
                    columns_min=max(2,d['columns']-2),columns_max=min(16,d['columns']+2),
                    rows_min=max(2,d['rows']-2),rows_max=min(12,d['rows']+2),
                    packed_theta_min=max(65,d['packed_theta_deg']-5),packed_theta_max=min(88,d['packed_theta_deg']+5))
            elif best and best['design']['family']=='accordion':
                d=best['design']
                plan=Plan(family='accordion',columns_min=max(2,d['columns']-2),columns_max=min(16,d['columns']+2),
                    packed_theta_min=max(65,d['packed_theta_deg']-5),packed_theta_max=min(88,d['packed_theta_deg']+5))
        feedback=ledger.batch(plan,min(21,ledger.remaining),seed+stage*10007,'deterministic-stage-'+str(stage+1))
        trace.append({'plan':plan.model_dump(),'feedback':feedback})
    return trace


SYSTEM=("You are a search-planning policy for a controlled ideal origami benchmark. Use the search_designs tool. "
 "All hard requirements are immutable. Choose search regions to find feasible designs and improve the given objective. "
 "Each call samples the supplied region with the SAME deterministic sampler used by the numerical baseline. "
 "There are no hidden feasible exemplars. The initial candidate and evaluation count are common to all methods. "
 "Shared construction: deployed theta=8 deg, packed theta=65..88. For gamma g, q=sqrt(1-sin(8deg)^2 sin(g)^2). "
 "For sampled rows r and columns c, target extents X,Y are independently 1.005..1.06 times their required minima; "
 "b=Y*q/(r*sin(g)*cos(8deg)); a=(X-b*cos(g)/q)/(c*q). Invalid dimensions consume budget. "
 "Miura gamma=25..85, rows=2..12, columns=2..16. Accordion gamma=90 and rows=1. a=5..100 mm, b=5..250 mm. "
 "At any theta, qtheta=sqrt(1-sin(theta)^2*sin(g)^2). Ideal folded extents: H=a*sin(theta)*sin(g), L=a*qtheta, V=b*cos(g)/qtheta, S=b*sin(g)*cos(theta)/qtheta; "
 "sheet x=c*L+V,y=r*S,z=H. Packed x/y may rotate, but deployed x/y and printable blank orientation are fixed. "
 "An accordion preserves its full width. Crease segments=(c-1)*r+(r-1)*c. "
 "Objective is feasibility first, then minimum crease segments (ties: material then packed area), or minimum material "
 "(ties: crease segments then packed area), as the task specifies. All are computational predictions, not physical measurements. "
 "Make exactly one search_designs tool call per model turn. Bounds may be equal to fix a parameter. No external tools, "
 "prior run candidates, or changing requirements. Set expected_feasible and a short public rationale; your claim will not change evaluator results.")


class ToolPlan(Plan):
    expected_feasible: bool
    rationale: str=Field(default='',description='Optional short public explanation; it does not affect numerical scoring.')


def model_policy(ledger,task,seed,method):
    load_env();key=os.environ.get('BASETEN_API_KEY')
    if not key:raise RuntimeError('BASETEN_API_KEY missing')
    rounds=1 if method=='single_pass' else 3
    quota=63 if method=='single_pass' else 21
    instruction=(f"You get {rounds} planning turn(s). Each call evaluates exactly {quota} fresh candidates unless fewer slots remain. "
                 +("You will receive NO feedback before all your evaluations finish. Choose one search region now." if rounds==1 else
                   "You will receive actual tool feedback after each batch. Use it to adapt the next search region."))
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps({
        'case_token':hashlib.sha256(json.dumps(ledger.requirements.model_dump(),sort_keys=True).encode()).hexdigest()[:8],
        'requirements':ledger.requirements.model_dump(),'objective':task['objective'],
        'initial_candidate':compact(ledger.best()),'seed':seed,'evaluation_budget_remaining':ledger.remaining,'instruction':instruction})}]
    tool={'type':'function','function':{'name':'search_designs','description':'Allocate this turn\'s candidate-evaluation quota to a shared numerical sampler. Bad candidate proposals and duplicates still consume attempts.','parameters':ToolPlan.model_json_schema()}}
    trace=[]
    for turn in range(rounds):
        payload={'model':MODEL,'messages':messages,'tools':[tool],
                 'tool_choice':'auto','reasoning_effort':'medium',
                 'max_tokens':49152 if rounds==1 else 16384,'temperature':0.2,'seed':seed}
        transport,response=request(BASE,key,'/chat/completions',payload,timeout=180)
        event={'turn':turn+1,'transport':transport,'request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
               'output_cap':payload['max_tokens'],'model':MODEL,'response_model':response.get('model') if response else None}
        event['response_id']=response.get('id') if response else None
        trace.append(event)
        if not response:event['error']='HTTP/transport failure; no retry or substitution';break
        choice=response['choices'][0];message=choice['message'];event['finish_reason']=choice.get('finish_reason')
        event['reasoning_field_present']=any(bool(message.get(k)) for k in ('reasoning_content','reasoning'))
        event['public_output']=message.get('content');event['tool_calls']=message.get('tool_calls',[])
        calls=message.get('tool_calls',[])
        if len(calls)!=1 or calls[0].get('function',{}).get('name')!='search_designs':
            event['error']='Expected exactly one search_designs call';break
        try:
            plan=ToolPlan.model_validate_json(calls[0]['function']['arguments'])
            settings=Plan(**{k:v for k,v in plan.model_dump().items() if k not in ('expected_feasible','rationale')})
        except (ValidationError,ValueError) as exc:
            event['error']='Invalid search plan: '+str(exc)[:700]
            messages.extend([message,{'role':'tool','tool_call_id':calls[0]['id'],'content':json.dumps({'error':event['error'],'remaining_budget':ledger.remaining})}])
            if turn+1<rounds:messages.append({'role':'user','content':'Correct the invalid plan within the original turn and evaluation budgets.'})
            continue
        event['expected_feasible']=plan.expected_feasible;event['public_rationale']=plan.rationale[:4000]
        allocation=ledger.remaining if turn==rounds-1 else min(quota,ledger.remaining)
        feedback=ledger.batch(settings,allocation,seed+turn*10007,method+'-turn-'+str(turn+1))
        event['feedback']=feedback
        # Private reasoning stays in memory for provider continuity and is never written to disk.
        messages.extend([message,{'role':'tool','tool_call_id':calls[0]['id'],'content':json.dumps(feedback)}])
        if turn+1<rounds:
            messages.append({'role':'user','content':f'Plan the next batch using this feedback. Remaining candidate attempts: {ledger.remaining}.'})
    return trace


def run_cell(task,seed,method):
    started=time.monotonic();requirements=task_requirements(task);ledger=Ledger(requirements,task['objective'])
    ledger.evaluate(baseline_design().model_dump(),'common-initial-candidate')
    trace=deterministic(ledger,seed) if method=='deterministic' else model_policy(ledger,task,seed,method)
    best=ledger.best();valid=[r for r in ledger.records if r['valid']]
    completed=len(ledger.records)==BUDGET
    return {'task_id':task['id'],'seed':seed,'method':method,'objective':task['objective'],'requirements':requirements.model_dump(),
            'budget':BUDGET,'attempts_used':len(ledger.records),'unused_budget':ledger.remaining,'completed':completed,
            'valid_proposals':len(valid),'unique_valid_proposals':len(ledger.seen),'duplicate_attempts':sum(r.get('duplicate',False) for r in ledger.records),
            'feasible_proposals':sum(r['result']['feasible'] for r in valid),'success':bool(best and best['feasible']),
            'best':best,'latency_ms':round((time.monotonic()-started)*1000),'trace':trace,'ledger':ledger.records}


def source_hashes():
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
        'continuum/benchmark.py','continuum/geometry.py','continuum/audit.py','continuum/search.py','scripts/api_preflight.py')}


def freeze_manifest(path):
    tasks=[]
    for task in TASKS:
        r=task_requirements(task)
        witness=None
        if task['id']!='impossible_blank_width':
            # Task-construction check only; these witnesses are never passed to the search methods.
            for raw in propose(r,Plan(family='miura'),10000,98765):
                try:candidate=evaluate(Design(**raw),r)
                except ValidationError:continue
                if candidate['feasible']:witness=candidate;break
            if not witness and task['id']=='generous_pocket':
                for raw in propose(r,Plan(family='accordion'),1000,98765):
                    try:candidate=evaluate(Design(**raw),r)
                    except ValidationError:continue
                    if candidate['feasible']:witness=candidate;break
            if not witness:raise RuntimeError('No independently checked feasible witness for '+task['id'])
            if not audit_record(witness,r.model_dump())['passed']:raise RuntimeError('Witness oracle mismatch')
        tasks.append({**task,'requirements':r.model_dump(),'expected_feasible':witness is not None,
                      'hidden_task_construction_witness':witness,
                      'infeasibility_certificate':'deployed y <= flat y <= 190 mm < required 220 mm' if witness is None else None})
    manifest={'protocol_version':5,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'model':MODEL,'base_url':BASE,
        'budget':BUDGET,'seeds':SEEDS,'tasks':tasks,'methods':['deterministic','single_pass','agent'],
        'selection':'Best evaluator-observed candidate for every method, not model-reported success.',
        'objective':'Feasibility first; task-specific lexicographic objective; no post-hoc weight choice.',
        'shared_initial_candidate':baseline_design().model_dump(),'known_feasible_seed_injection':False,
        'model_output_token_cap_per_run':49152,'agent_output_cap_per_turn':16384,'agent_rounds':3,'single_pass_rounds':1,
        'tool_choice':'auto','reasoning_effort':'medium','temperature':0.2,
        'request_timeout_seconds':180,
        'configuration_evidence':['reasoning-transport-probe.json','reasoning-transport-probe-larger-budgets.json','output-cap-probe.json'],
        'cost_estimate_rates':{'input_per_million_usd':1.25,'cached_input_per_million_usd':.15,'output_per_million_usd':4.25,
          'source':'https://www.baseten.co/library/muse-spark-open/','limitation':'Public generic model rates; hackathon-slug actual charges and balances unverified.'},
        'source_sha256':source_hashes()}
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest
