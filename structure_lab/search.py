"""Shared numerical tools and explicit candidate ledger for all policies."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from .mechanics import solve_frame
from .oracle import oracle_solve
from .design import geometry,templates,bounds,validate_graph,constraint_values


class BudgetExhausted(Exception):pass
class LocalLimit(Exception):pass


def ranked(record):
    return (not record.get('feasible',False),record.get('violation',1e6) if not record.get('feasible') else 0.,record.get('volume_mm3',1e12))


class Laboratory:
    def __init__(self,task,budget=96):
        self.task=task;self.budget=budget;self.records=[];self.cache={};self.internal={}
        self.physics_solves=0;self.cache_hits=0;self.optimizer_calls=[]

    @property
    def remaining(self):return self.budget-len(self.records)

    @property
    def best(self):return min(self.records,key=ranked) if self.records else None

    def evaluate(self,edge_ids,widths,source='evaluate'):
        order=np.argsort(edge_ids);edge_ids=[edge_ids[i] for i in order];widths=[float(widths[i]) for i in order]
        raw=json.dumps([edge_ids,widths],separators=(',',':'));key=hashlib.sha256(raw.encode()).hexdigest()
        if key in self.cache:self.cache_hits+=1;return self.cache[key]
        if self.remaining<=0:raise BudgetExhausted('Search allowance exhausted')
        record={'id':f'D{len(self.records)+1:03d}','attempt':len(self.records)+1,'source':source,
                'edge_ids':edge_ids,'widths_mm':widths,'valid':False,'feasible':False,'violation':1e6}
        self.records.append(record);self.cache[key]=record
        try:
            nodes,edges=validate_graph(self.task,edge_ids,widths)
            self.physics_solves+=1
            solved=solve_frame(nodes,edges,widths,[0,1,2],7)
            values,gradients,labels=constraint_values(self.task,solved['compliance'],solved['compliance_gradient'])
            actual=solved['displacements_per_unit_load']*self.task['actual_test_force_N']
            maxd=float(np.linalg.norm(actual.reshape(-1,3,2)[:,:2,:],axis=1).max())
            maxr=float(abs(actual[2::3]).max())
            nominal_strain=float(solved['nominal_stress_per_unit_load'].max()*self.task['actual_test_force_N']/2000.)
            guards=[1-maxd/self.task['max_displacement_mm'],1-maxr/self.task['max_rotation_rad'],1-nominal_strain/.001]
            violations=np.maximum(-np.r_[values,guards],0.)
            record.update(valid=True,feasible=bool(max(violations)<=1e-6),violation=float(sum(violations)),
               volume_mm3=solved['volume_mm3'],compliance_mm_per_N=solved['compliance'].tolist(),
               constraint_margins=dict(zip(labels,values.tolist())),
               actual_load_model_checks={'maximum_nodal_translation_mm':maxd,'maximum_nodal_rotation_rad':maxr,
                                         'maximum_nominal_member_strain':nominal_strain},
               residual_inf=solved['free_residual_inf'],physics_solve_index=self.physics_solves)
            self.internal[record['id']]={'solved':solved,'values':values,'jacobian':gradients}
        except (ValueError,np.linalg.LinAlgError) as exc:record['error']=str(exc)
        return record

    def charge_invalid(self,message):
        if not self.remaining:raise BudgetExhausted()
        r={'id':f'D{len(self.records)+1:03d}','attempt':len(self.records)+1,'valid':False,'feasible':False,
           'violation':1e6,'source':'invalid_tool','error':message};self.records.append(r);return r

    def optimize(self,edge_ids=None,template=None,start_id=None,allocation=16,fraction=.6):
        if not 1<=allocation<=self.remaining:raise ValueError('Allocation must fit remaining allowance')
        if start_id:
            start=next(r for r in self.records if r['id']==start_id)
            edge_ids=start['edge_ids'];x0=np.array(start['widths_mm'])
        else:
            edge_ids=templates()[template] if template else edge_ids
            if not edge_ids:raise ValueError('Provide a template, custom edges, or evaluated starting design')
            b=bounds(self.task,edge_ids);x0=np.array([lo+(hi-lo)*fraction for lo,hi in b])
        # Preserve explicit correspondence between widths and edge IDs.
        # The evaluator stores canonical edge order, so optimizer variables and
        # their analytic derivative columns must use that SAME order too.
        order=np.argsort(edge_ids);edge_ids=[edge_ids[i] for i in order];x0=np.asarray(x0)[order]
        b=bounds(self.task,edge_ids);begin=len(self.records)
        def get(x):
            # SLSQP objective/Jacobian/constraint requests share exactly one solve.
            if len(self.records)-begin>=allocation:raise LocalLimit()
            return self.evaluate(edge_ids,np.asarray(x).tolist(),'optimizer')
        def fun(x):
            r=get(x);return r.get('volume_mm3',1e9)/1000
        def jac(x):
            r=get(x)
            return self.internal[r['id']]['solved']['volume_gradient']/1000 if r['valid'] else np.zeros(len(x))
        def constraints(x):
            r=get(x);return self.internal[r['id']]['values'] if r['valid'] else np.full(sum(('lower' in z)+('upper' in z) for z in self.task['requirements']),-1000.)
        def constraints_jac(x):
            r=get(x);return self.internal[r['id']]['jacobian'] if r['valid'] else np.zeros((len(constraints(x)),len(x)))
        status='allocation_reached'
        try:
            result=minimize(fun,x0,jac=jac,bounds=b,method='SLSQP',
                constraints=[{'type':'ineq','fun':constraints,'jac':constraints_jac}],
                options={'maxiter':80,'ftol':1e-10,'disp':False})
            status=str(result.message)
        except LocalLimit:pass
        records=self.records[begin:]
        report={'template':template,'edge_ids':edge_ids,'start_id':start_id,'allocated_slots':allocation,
                'used_slots':len(records),'status':status,'best_this_call':min(records,key=ranked) if records else None}
        self.optimizer_calls.append(report);return report

    def public_state(self):
        candidates=sorted(self.records,key=ranked)[:5]
        return {'remaining_search_slots':self.remaining,'actual_frame_assemblies':self.physics_solves,
                'best_evaluated':self.best,'top_candidates':candidates}

    def final_verify(self):
        r=self.best
        if not r or not r.get('valid'):return {'passed':False,'reason':'No valid candidate evaluated','oracle_solves':0}
        nodes,edges=validate_graph(self.task,r['edge_ids'],r['widths_mm'])
        c=oracle_solve(nodes,edges,r['widths_mm'],[0,1,2],7)
        discrepancy=float(np.max(np.abs(c-np.array(r['compliance_mm_per_N']))))
        scale=max(1.,float(abs(c).max()))
        values,_,labels=constraint_values(self.task,c,np.zeros((len(edges),2,2)))
        return {'passed':bool(discrepancy<1e-8*scale),'independent_compliance_mm_per_N':c.tolist(),
                'maximum_compliance_discrepancy':discrepancy,'independent_margins':dict(zip(labels,values.tolist())),
                'independent_constraints_feasible':bool(np.min(values)>=-1e-6),
                'oracle_solves':1,'scope':'independent numerical implementation of the same linear frame model'}


def eligible_templates(task):
    eligible=[]
    for name,ids in templates().items():
        try:validate_graph(task,ids,[lo for lo,hi in bounds(task,ids)]);eligible.append(name)
        except ValueError:pass
    return eligible


def numerical_portfolio(lab,seed=101):
    rng=np.random.default_rng(seed);names=eligible_templates(lab.task)
    screened=[]
    # Cheap geometry/feature screening plus BOTH width extremes, not a random
    # sampler. Then prioritize feasible or low-violation topology starts.
    for name in names:
        ids=templates()[name];b=bounds(lab.task,ids);trials=[]
        for fraction in [0.,1.]:
            if not lab.remaining:break
            trials.append(lab.evaluate(ids,[lo+(hi-lo)*fraction for lo,hi in b],'topology_screen'))
        if trials:screened.append((min(trials,key=ranked),name))
    screened.sort(key=lambda pair:ranked(pair[0]))
    for record,name in screened[:4]:
        if not lab.remaining:break
        lab.optimize(start_id=record['id'],allocation=min(14,lab.remaining))
    stagnant=0
    while lab.remaining and stagnant<8:
        before=len(lab.records);best=lab.best
        if best and best.get('valid'):
            # Alternate continuation with genuine topology neighbors.
            if stagnant%2==0:
                lab.optimize(start_id=best['id'],allocation=min(12,lab.remaining))
            if lab.remaining:
                ids=list(best['edge_ids']);allids=list(range(len(geometry(lab.task['length_mm'],lab.task['height_mm'])[1])))
                if len(ids)>2 and rng.random()<.5:ids.remove(int(rng.choice(ids)))
                else:
                    unused=[i for i in allids if i not in ids]
                    if unused:ids.append(int(rng.choice(unused)))
                lab.optimize(edge_ids=sorted(ids),allocation=min(8,lab.remaining),fraction=float(rng.uniform(.45,.8)))
        else:lab.optimize(template=str(rng.choice(names)),allocation=min(12,lab.remaining),fraction=float(rng.uniform(.4,.9)))
        stagnant=stagnant+1 if len(lab.records)==before else 0


def render_geometry(task,record,target):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    nodes,all_edges=geometry(task['length_mm'],task['height_mm']);nodes=np.asarray(nodes)
    fig,ax=plt.subplots(figsize=(6,3.6),layout='constrained')
    if record and record.get('valid'):
        for eid,w in zip(record['edge_ids'],record['widths_mm']):
            a,b=all_edges[eid];ax.plot(nodes[[a,b],0],nodes[[a,b],1],color='#285b70',lw=2*w,label=None)
            mid=(nodes[a]+nodes[b])/2;ax.text(*mid,f'e{eid}:{w:.2f}',fontsize=6)
    ax.scatter(nodes[:,0],nodes[:,1],color='#404040',s=15)
    for i,(x,y) in enumerate(nodes):ax.annotate(str(i),(x,y),xytext=(3,4),textcoords='offset points',fontsize=8)
    if task.get('central_gap_half_height_mm'):
        from matplotlib.patches import Rectangle
        gap=task['central_gap_half_height_mm'];ax.add_patch(Rectangle((.2*task['length_mm'],-gap),.6*task['length_mm'],2*gap,fc='#e8b29b',alpha=.5))
    ax.scatter(nodes[:3,0],nodes[:3,1],marker='s',s=60,color='#333333');ax.scatter(*nodes[7],marker='*',s=130,color='#b06032')
    ax.set(xlabel='x (mm)',ylabel='y (mm)',title=f"{task['id']} / {record['id'] if record else 'node grid'} / graph centerlines")
    ax.set_aspect('equal');ax.margins(.12);fig.savefig(target,dpi=140);plt.close(fig)
    return str(target)
