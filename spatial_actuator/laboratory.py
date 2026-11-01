"""Metered design tools shared by the numerical control and Meta controller."""
import hashlib
import json
import numpy as np
from scipy.optimize import minimize
from .design import geometry,catalogue,bounds,compute
from .oracle import solve as independent


class Exhausted(RuntimeError):pass


class Lab:
    def __init__(self,task,budget=192):
        self.task=task;self.budget=budget;self.records=[];self.cache={};self.internal={};self.best=None;self.cache_hits=0;self.assemblies=0

    @property
    def remaining(self):return self.budget-len(self.records)

    def evaluate(self,edge_ids,radii_mm,reason='evaluate'):
        # Keep variables and derivatives in the same canonical order.
        if len(edge_ids)!=len(radii_mm):return self.invalid('Edge/radius length mismatch',reason)
        order=sorted(range(len(edge_ids)),key=lambda j:edge_ids[j]);ids=[edge_ids[j] for j in order];rr=[float(radii_mm[j]) for j in order]
        key=json.dumps([ids,rr],allow_nan=True)
        if key in self.cache:self.cache_hits+=1;return self.cache[key]
        if not self.remaining:raise Exhausted('Shared candidate allowance exhausted')
        record={'id':f'd{len(self.records):04d}','edge_ids':ids,'radii_mm':rr,'reason':reason}
        self.records.append(record);self.cache[key]=record
        try:
            from .design import validate
            validate(self.task,ids,rr);self.assemblies+=1
            result=compute(self.task,ids,rr,True);record.update(valid=True,feasible=result['feasible'],metrics=result['metrics'],margins=result['margins'])
            self.internal[record['id']]=result
            if self.best is None or self.rank(record)<self.rank(self.best):self.best=record
        except (ValueError,np.linalg.LinAlgError) as error:record.update(valid=False,feasible=False,error=str(error))
        return record

    def invalid(self,error,reason='invalid_action'):
        if not self.remaining:raise Exhausted('Shared candidate allowance exhausted')
        record={'id':f'd{len(self.records):04d}','valid':False,'feasible':False,'error':str(error),'reason':reason}
        self.records.append(record);return record

    @staticmethod
    def rank(record):
        if not record['valid']:return (2,float('inf'),float('inf'))
        violation=sum(max(0.,-v) for v in record['margins'].values())
        return (0 if record['feasible'] else 1,0. if record['feasible'] else violation,record['metrics']['volume_proxy_mm3'])

    def state(self):return {'remaining_candidates':self.remaining,'actual_assemblies':self.assemblies,'cache_hits':self.cache_hits,'best_evaluated':self.best}

    def optimize(self,allocation=32,template=None,edge_ids=None,start_id=None,start_fraction=.25):
        if type(allocation) is not int or not 1<=allocation<=self.budget:raise ValueError('Invalid allocation')
        if not 0<=start_fraction<=1:raise ValueError('Invalid start fraction')
        if start_id is not None:
            seed=next(r for r in self.records if r['id']==start_id and r['valid']);ids=seed['edge_ids'];x0=np.array(seed['radii_mm'])
        else:
            ids=catalogue()[template] if template else edge_ids
            if not ids or any(type(i) is not int for i in ids) or len(ids)!=len(set(ids)):raise ValueError('Choose valid template or unique edges')
            ids=sorted(ids);bb=bounds(self.task,ids);x0=np.array([lo+start_fraction*(hi-lo) for lo,hi in bb])
        bb=bounds(self.task,ids);before=len(self.records);local_budget=min(allocation,self.remaining)
        def evaluate(x):
            # Cache may be reused even when local sample allowance is exhausted.
            key=json.dumps([ids,[float(v) for v in x]],allow_nan=True)
            if key not in self.cache and len(self.records)-before>=local_budget:raise Exhausted('Tool allocation consumed')
            record=self.evaluate(ids,x,'optimizer')
            if not record['valid']:raise ValueError(record['error'])
            return record,self.internal[record['id']]
        def objective(x):
            record,internal=evaluate(x);return record['metrics']['volume_proxy_mm3'],internal['solved']['dvolume_dr']
        def constraints(x):
            record,internal=evaluate(x);m=record['metrics'];du=internal['solved']['du_dr'][:,:,0];t=self.task
            ii=6*t['input_node']+t['input_axis'];oo=6*t['output_node'];rows=[];der=[]
            value=m['loaded_stroke_mm'];limit=t['minimum_loaded_stroke_mm'];rows.append((value-limit)/limit);der.append(du[:,oo+t['output_axis']]/limit)
            for value,dof,limit in [(m['input_travel_mm'],ii,t['maximum_input_travel_mm']),(m['parasitic_y_mm'],oo+1,t['maximum_parasitic_y_mm']),(m['parasitic_x_mm'],oo,t['maximum_parasitic_x_mm'])]:
                rows.extend([(limit-value)/limit,(limit+value)/limit]);der.extend([-du[:,dof]/limit,du[:,dof]/limit])
            return np.array(rows),np.array(der)
        try:
            result=minimize(objective,x0,jac=True,bounds=bb,method='SLSQP',constraints={'type':'ineq','fun':lambda x:constraints(x)[0],'jac':lambda x:constraints(x)[1]},options={'maxiter':60,'ftol':1e-10})
            status={'success':bool(result.success),'message':str(result.message)}
        except (Exhausted,ValueError,StopIteration) as error:status={'success':False,'message':str(error)}
        return {'optimizer':status,'charged_candidates':len(self.records)-before,'state':self.state(),
                'note':'Optimizer directly constrains stroke/input travel/output x,y; all other mechanics guards and finite-envelope checks still decide acceptance of every candidate.'}

    def verify(self,record=None):
        record=record or self.best
        if record is None or not record['valid']:return {'passed':False,'reason':'No valid candidate'}
        # Re-evaluate production and independent oracle offline; separately counted.
        result=compute(self.task,record['edge_ids'],record['radii_mm'])
        oracle=independent(result['nodes'],result['edges'],record['radii_mm'],[0,1,2,3],result['loads'],self.task['E_N_mm2'],self.task['nu'],result['springs'])
        error=float(abs(result['solved']['u']-oracle).max());scaled=error/max(1.,abs(oracle).max())
        metrics_error=max(abs(float(result['metrics'][k])-float(v)) for k,v in record['metrics'].items() if v is not None)
        return {'passed':scaled<1e-8 and metrics_error<1e-9,'max_displacement_or_rotation_error':error,'max_saved_metric_error':metrics_error,
                'feasible':result['feasible'],'extra_production_assemblies':1,'extra_oracle_assemblies':1,'physical_validation':False}


def numerical_control(lab):
    # Broad fixed conventional catalogue, two sizes, then analytic sizing on
    # promising distinct graphs. No model-selected seed is injected.
    for name,ids in catalogue().items():
        for fraction in [0.,.5]:
            if not lab.remaining:return
            rr=[lo+fraction*(hi-lo) for lo,hi in bounds(lab.task,ids)];lab.evaluate(ids,rr,'catalogue_screen:'+name)
    seeds=sorted([r for r in lab.records if r['valid']],key=lab.rank);seen=set()
    for record in seeds:
        graph=tuple(record['edge_ids'])
        if graph in seen:continue
        seen.add(graph)
        if not lab.remaining:break
        lab.optimize(allocation=min(32,lab.remaining),start_id=record['id'])


def source_manifest():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    paths=list((root/'spatial_actuator').glob('*.py'))+[root/'scripts/api_preflight.py',root/'structure_lab/tool_protocol.py']
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
