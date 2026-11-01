"""Regenerate derived plots/report from preserved raw results; makes no API calls."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from behavior_design.model import design,predict,evaluate,bounds,ARCHITECTURES,geometry_budget
from behavior_design.tasks import TEACHER,WITNESS
from behavior_design.linkage import primitive

LABELS={'numerical':'Numerical control','single_pass':'Single-pass Muse','adaptive':'Adaptive Muse'}
COLORS={'numerical':'#466b92','single_pass':'#c17d30','adaptive':'#19776e'}
def build(study):
    path=ROOT/'output/behavior-design/studies'/study;manifest=json.loads((path/'manifest.json').read_text());tasks=json.loads((path/'tasks.json').read_text());ref=json.loads((path/'reference.json').read_text());results=[];ids=[];cost=0.;calls=0
    for file in sorted((path/'runs').glob('*/result.json')):
        r=json.loads(file.read_text());entry={k:v for k,v in r.items() if k not in ('records','events')};entry['id']=file.parent.name;entry['candidates']=[{k:v for k,v in record.items() if k!='result'} for record in r['records']];entry['events']=r['events'];entry['architectures']=[]
        if entry['audit']:
            hidden=entry['audit']['heldout'];task=next(t for t in tasks if t['id']==r['task_id']);normalizer=max(task['target_force_N']);delta=np.array([p['force_N'] for p in hidden['points']])-ref['heldout_target_force_N']
            hidden['raw_RMS_normalized_by_heldout_maximum']=hidden['normalized_RMS_error'];hidden['raw_max_normalized_by_heldout_maximum']=hidden['normalized_max_error'];hidden['normalized_RMS_error']=float(np.sqrt(np.mean(delta**2))/normalizer);hidden['normalized_max_error']=float(max(abs(delta))/normalizer);hidden['normalization_note']='Offline reporting correction: use full-stroke fit-target maximum, as preregistered. Raw auditor used its held-out maximum (0.93% smaller); raw files untouched. No candidates or model calls changed; no acceptance decisions changed.';hidden['target_passed']=bool(hidden['mechanical_screen_passed'] and hidden['normalized_RMS_error']<=task['maximum_normalized_RMS_error'] and hidden['normalized_max_error']<=task['maximum_normalized_max_error']);corrected=bool(hidden['target_passed'] and entry['audit']['independent']['passed'] and r['selected']['target_passed'])
            if corrected!=entry['audit']['accepted']:raise ValueError('Reporting correction changed an acceptance decision')
        for name in ARCHITECTURES:
            records=[c for c in r['records'] if c['architecture']==name and 'result' in c]
            if records:
                best=min(records,key=lambda c:(not c['mechanical_screen_passed'],c['normalized_RMS_error']));entry['architectures'].append({'name':name,'id':best['id'],'result':best['result']})
        api=file.parent/'api-events.jsonl';entry['receipts']=[]
        if api.exists():
            for line in api.read_text().splitlines():
                e=json.loads(line);entry['receipts'].append({k:e[k] for k in ['response_id','returned_model','transport','estimated_USD','encoding'] if k in e});ids.append(e.get('response_id'));calls+=1;cost+=e.get('estimated_USD',0.)
        results.append(entry)
    if len(results)!=6:raise ValueError('Wait for all six raw result files')
    source_checks={name:hashlib.sha256((path/'source'/name).read_bytes()).hexdigest()==digest for name,digest in manifest['source_hashes'].items()}
    examples=[]
    for name in ARCHITECTURES:
        box=bounds(name,tasks[0])
        try:
            d=design(name,box.mean(axis=1));result=evaluate(d,tasks[0],np.linspace(0,12,49),True);examples.append({'name':name,'result':result,'origin':'Engineer-defined public motif at domain midpoint, not AI discovery.'})
        except ValueError as e:examples.append({'name':name,'error':str(e)})
    grid=np.linspace(0,12,145);teacher_points=predict(TEACHER,grid)
    original_pack=geometry_budget(TEACHER,tasks[0]);compact_pack=geometry_budget(WITNESS,tasks[1]);component=json.loads((ROOT/'output/behavior-design/component-audit.json').read_text())
    report={'study_id':study,'manifest':manifest,'tasks':tasks,'runs':results,'library':ARCHITECTURES,'examples':examples,'reference':{'points':teacher_points,'design':TEACHER,'initial_geometry':original_pack,'compact_witness_geometry':compact_pack,'revision_rejects_original':original_pack['width_mm']>tasks[1]['maximum_width_mm'],'scope':ref['scope']},'component_audit':component,'verification':{'archived_source_hashes_match':all(source_checks.values()),'actual_Meta_calls':calls,'unique_provider_response_ids':len(set(i for i in ids if i)),'estimated_USD':cost,'billing_verified':False,'independently_accepted_runs':sum(bool(r['audit'] and r['audit']['accepted']) for r in results),'total_runs':len(results)},'conclusion':'The nonlinear modeling workflow works; AI benefit is unproven. Numerical control and adaptive Muse fit both briefs, with essentially equal accuracy. All successful policies first pass at query 16. A simple single-linkage motif already satisfies the 5% criterion: this task does not require architecture discovery. One single-pass response supplied no executable command.','next_gate':'A preregistered multi-brief test that genuinely requires different architecture families, includes infeasible cases and has independently calibrated physics. Continue discovery claims only if useful behavior and/or test selection improves over a strong matched numerical control.','metric_reporting_note':'The raw held-out evaluator normalized against the held-out maximum rather than the preregistered full-stroke maximum. The derived report corrects the denominator uniformly; raw evidence is preserved and all acceptance decisions are unchanged.'}
    report['reference']['initial_result']=evaluate(TEACHER,tasks[0],grid);report['reference']['initial_result']['points']=teacher_points;report['reference']['initial_result']['normalized_RMS_error']=0.;report['reference']['initial_result']['normalized_max_error']=0.;report['reference']['initial_result']['error_scope']='Zero by definition: this is the known target-generating design, not an independently designed or measured result.'
    report['revision_scope']='Two independent requirement variants of the same original80mm reference. Compact runs do not continue each controller initial winner: those already happen to fit the compact envelope. Therefore no measured revision-time saving is claimed.'
    (path/'report.json').write_text(json.dumps(report,indent=2));(ROOT/'output/behavior-design/latest-study.txt').write_text(study)
    figures(path,report);print(json.dumps(report['verification'],indent=2));return report

def figures(path,report):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    truth=report['reference']['points']
    for col,task in enumerate(report['tasks']):
        ax=axes[0,col];ax.plot([p['travel_mm'] for p in truth],[p['force_N'] for p in truth],color='#343936',ls='--',lw=2,label='Constructed target')
        for r in report['runs']:
            if r['task_id']!=task['id']:continue
            if r['audit']:
                p=r['audit']['heldout']['points'];ax.plot([q['travel_mm'] for q in p],[q['force_N'] for q in p],color=COLORS[r['policy']],label=LABELS[r['policy']],alpha=.8)
            a=axes[1,col];best=1.;xx=[];yy=[]
            for i,c in enumerate(r['candidates']):
                if c.get('mechanical_screen_passed'):best=min(best,c['normalized_RMS_error'])
                xx.append(i+1);yy.append(best)
            if xx:a.semilogy(xx,yy,color=COLORS[r['policy']],label=LABELS[r['policy']])
            else:a.text(.02,.15,'Single-pass: no executable command',transform=a.transAxes,color=COLORS['single_pass'])
        ax.set(title=task['title'],xlabel='Prescribed travel (mm)',ylabel='Resistance (N)');ax.legend(fontsize=8);ax.grid(alpha=.15)
        axes[1,col].axhline(.05,color='#777777',ls=':',label='RMS acceptance limit');axes[1,col].set(xlabel='Charged new candidate queries',ylabel='Best feasible normalized fit RMS',xlim=(0,240));axes[1,col].grid(alpha=.15)
    fig.suptitle('Behavior design — controlled development comparison\nSame 240-candidate allowance and numerical tools; no hardware validation',fontsize=14);fig.savefig(path/'benchmark.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,3.8),constrained_layout=True);u=np.linspace(0,40,501)
    for H,color in [(20.,'#19776e'),(15.,'#c17d30')]:
        E,F,K,_=primitive(20.,H,1.,0.,u,1,False);axes[0].plot(u,E,color=color,label=f'Rise H={H:g} mm');axes[1].plot(u,F,color=color);axes[0].scatter([0,2*H],[0,0],color=color);axes[0].scatter([H],[(20-np.hypot(20,H))**2],facecolors='none',edgecolors=color)
    axes[0].set(xlabel='Prescribed travel (mm)',ylabel='Energy (N mm)',title='Classical two-spring reference');axes[0].legend(fontsize=8)
    axes[1].set(xlabel='Prescribed travel (mm)',ylabel='Drive force (N)',title='Geometry changes the response');axes[1].axhline(0,color='#999999',lw=.7)
    checks=report['component_audit']['checks'];axes[2].scatter([c['analytic_force_N'] for c in checks],[c['opensees_force_N'] for c in checks],c='#19776e');lims=axes[2].get_xlim();axes[2].plot(lims,lims,'--',color='#999999');axes[2].set(xlabel='Analytical force (N)',ylabel='OpenSees force (N)',title='12 independent component checks')
    fig.suptitle('Solid dots: free minima in the guided ideal model. Hollow dots: unstable free maxima.\nNegative-slope configurations require displacement control; no measured snap dynamics.',fontsize=11);fig.savefig(path/'mechanics-proof.png',dpi=170);plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('study');args=p.parse_args();build(args.study)
