"""Derived evidence/figures from preserved experiments, no API calls or solves."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from nonlinear_discovery.model import mesh

def best(group):return max((r for r in group if r['accepted']),key=lambda r:r['result']['summary']['worst_bias_N_mm'])
def numbers(row):
    result=row['result'];s=result['summary'];t=result['tolerance']
    return {'id':row['id'],'bias_N_mm':s['worst_bias_N_mm'],'max_axial_force_N':s['max_axial_force_N'],'max_clamp_torque_N_mm':s['max_holding_torque_N_mm'],'min_selected_hessian_eigenvalue':s['min_hessian_eigenvalue'],
            'minimum_sampled_path_height_N_mm':min(v['minimum_sampled_escape_path_height_N_mm'] for v in s['details'].values()),'tolerance_passed':t['passed_trials'],'tolerance_total':t['total_trials'],
            'max_perturbed_axial_force_N':max(abs(m['state']['holding_axial_force_N']) for trial in t['trials'] for m in trial['modes'] if m['state']),
            'independent_max_energy_error_normalized':max(r['energy_error_normalized'] for r in row.get('independent_audit',{}).get('checks',[{'energy_error_normalized':0}])),
            'independent_max_hessian_error_normalized':max(r['hessian_error_normalized'] for r in row.get('independent_audit',{}).get('checks',[{'hessian_error_normalized':0}]))}

def main():
    out=ROOT/'output/robust-discovery';out.mkdir(parents=True,exist_ok=True)
    study=json.loads((ROOT/'benchmarks/robust-discovery-v1/summary.json').read_text())['methods'];coordinate=json.loads((ROOT/'research/robust-coordinate-challenge.json').read_text());geometry=json.loads((ROOT/'research/robust-geometry-challenge.json').read_text())
    entries={'frozen_numerical':best(study['numerical']['audited']),'Meta':best(study['meta']['audited']),'posthoc_coordinate':best(coordinate['audited']),'posthoc_geometry':best(geometry['audited'])};evidence={name:numbers(row) for name,row in entries.items()}
    events=[json.loads(line) for line in (ROOT/'benchmarks/robust-discovery-v1/meta/events.jsonl').read_text().splitlines()]
    receipts={'calls':len(events),'unique_provider_response_ids':len({e['response_id'] for e in events}),'http_statuses':[e['transport'].get('http_status') for e in events],'estimated_USD':sum(e['estimated_USD'] for e in events),'billing_verified':False,'usage':[e['transport'].get('usage') for e in events]}
    evidence['api_receipts']=receipts;evidence['physical_validation']=False;evidence['scientific_novelty_established']=False
    evidence['comparison_scope']='Frozen single-task comparison plus explicitly informed post-hoc numerical challenges. No general AI advantage, global retention or physical validation established.'
    (out/'evidence.json').write_text(json.dumps(evidence,indent=2))
    old=json.loads((ROOT/'research/nonlinear-robustness-corrected.json').read_text())['result'];original={'bias_N_mm':old['summary']['worst_bias_N_mm'],'max_axial_force_N':old['summary']['max_axial_force_N'],'minimum_sampled_path_height_N_mm':min(v['minimum_sampled_escape_path_height_N_mm'] for v in old['summary']['details'].values()),'tolerance_passed':old['tolerance']['passed_trials']}
    rows=[original,evidence['frozen_numerical'],evidence['Meta'],evidence['posthoc_coordinate']];labels=['Earlier Meta\noffset repair','Frozen\nnumerical','New Meta','Post-hoc numerical\npattern search'];colors=['#c25f57','#78889d','#467b68','#9d8458']
    fig,axes=plt.subplots(2,2,figsize=(12,8));specs=[('bias_N_mm','Worst found-state bias (mJ)',False),('minimum_sampled_path_height_N_mm','Lowest identified sampled path height (mJ)',True),('max_axial_force_N','Maximum selected clamp force (N)',False),('tolerance_passed','Passed local tolerance samples / 8',False)]
    for ax,(key,title,log) in zip(axes.flat,specs):
        values=[r[key] for r in rows];ax.bar(range(4),values,color=colors);ax.set_xticks(range(4),labels);ax.set_title(title,fontsize=11);ax.spines[['top','right']].set_visible(False)
        if log:ax.set_yscale('log');ax.axhline(.5,color='#555555',linestyle=':',linewidth=1)
        if key=='max_axial_force_N':ax.axhline(1.5,color='#555555',linestyle=':',linewidth=1);ax.set_ylim(0,1.7)
        if key=='tolerance_passed':ax.set_ylim(0,9);ax.set_yticks([0,2,4,6,8])
        for i,value in enumerate(values):ax.annotate(f'{value:.3g}',(i,value),xytext=(0,5),textcoords='offset points',ha='center',fontsize=10)
    fig.suptitle('Model-level repair: energy preference alone missed fragile competing states',fontsize=14)
    fig.text(.5,.015,'Path heights are sampled diagnostics, not certified barriers. Eight tolerance samples are not manufactured-part validation.\nThe post-hoc numerical challenge is additional informed work; these are not population-level AI effect estimates.',ha='center',fontsize=10)
    fig.tight_layout(rect=[0,.07,1,.95]);fig.savefig(out/'comparison.png',dpi=170);fig.savefig(out/'comparison.svg');plt.close(fig)
    winner=entries['Meta'];fig=plt.figure(figsize=(12,5));s=winner['result']['summary'];polys=[]
    for column,setting in enumerate(['A','B']):
        state=s['details'][setting]['target'];shape=mesh(winner['design'],state);vertices=np.array(shape['vertices_mm']);faces=np.array(shape['triangles']);ax=fig.add_subplot(1,2,column+1,projection='3d')
        collection=Poly3DCollection(vertices[faces],facecolors=[['#547a95','#b99455','#63886e','#9b7599'][i//12] for i in range(len(faces))],edgecolors='#4d4d4d',linewidths=.4,alpha=.5);ax.add_collection3d(collection);ax.auto_scale_xyz(vertices[:,0],vertices[:,1],vertices[:,2]);ax.set_box_aspect(np.ptp(vertices,axis=0));ax.view_init(20,-55)
        ax.set_xlabel('x (mm)');ax.set_ylabel('y (mm)');ax.set_zlabel('z (mm)');ax.set_title(f'{setting}: selected local minimum | P={state["polarization"]:.3f}\nEnergy {state["energy_N_mm"]:.3f} mJ')
    fig.suptitle('Computed configurations of Meta r028 — ideal guide, zero-thickness facets')
    fig.text(.5,.015,'No switching dynamics, contact, hinges or printed-device mechanics are simulated.',ha='center');fig.tight_layout(rect=[0,.04,1,.94]);fig.savefig(out/'computed-states.png',dpi=170);plt.close(fig)
    print(json.dumps(evidence,indent=2))

if __name__=='__main__':main()
