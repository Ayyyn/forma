"""Scientific plots and open OBJ exports from audited equilibrium coordinates."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from nonlinear_discovery.model import mesh


def main():
    folder=ROOT/'benchmarks/nonlinear-discovery-v1';report=json.loads((folder/'summary.json').read_text());meta=report['methods']['meta'];selected=next(r for r in meta['final_refined'] if r['id']==meta['best_accepted_id']);design=selected['design'];result=selected['refined']
    out=ROOT/'output/discovery-board/models';out.mkdir(parents=True,exist_ok=True)
    fig=plt.figure(figsize=(11,8));colors=['#5f88b5','#be884f','#79a38a','#a984a6']
    for k,(setting,role) in enumerate([('A','target'),('A','counter'),('B','target'),('B','counter')],1):
        state=result['details'][setting][role];geometry=mesh(design,state);ax=fig.add_subplot(2,2,k,projection='3d');vertices=geometry['vertices_mm']
        faces=[[vertices[v] for v in triangle] for triangle in geometry['triangles']];collection=Poly3DCollection(faces,facecolors=[colors[i//12] for i in range(48)],edgecolors='#404b55',alpha=.5,linewidths=.4);ax.add_collection3d(collection)
        height=geometry['ring_heights_mm'][-1];ax.set(xlim=(-34,34),ylim=(-34,34),zlim=(0,height),xlabel='x (mm)',ylabel='y (mm)',zlabel='z (mm)');ax.set_box_aspect((60,60,height));ax.view_init(18,-65)
        ax.set_title(f"Setting {setting} / {'preferred' if role=='target' else 'metastable opposite'}\nE={state['energy_N_mm']:.2f} mJ; P={state['polarization']:.3f}",fontsize=10)
        if role=='target':
            text=['# Audited reduced-model configuration; coordinates in mm. Open surface mesh, NOT a manufacturing solid.']
            text += ['v '+' '.join(f'{x:.9f}' for x in point) for point in vertices]
            text += ['f '+' '.join(str(i+1) for i in tri) for tri in geometry['triangles']]
            (out/f'meta-{selected["id"]}-{setting}.obj').write_text('\n'.join(text)+'\n')
            (out/f'meta-{selected["id"]}-{setting}.json').write_text(json.dumps({'design':design,'setting':setting,'state':state,'mesh':geometry},indent=2))
    fig.suptitle('Same endpoint length and twist: internally distinct local minima under two preload settings',fontsize=12)
    fig.text(.03,.015,'Ideal coaxial guides and bilateral ring springs; six internal DOFs. Surface coordinates from the actual equilibria.\nNo contact, shell/material failure, fabricated joint or physical switching validation. Springs omitted from geometric views; topology is in JSON.',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.94));fig.savefig(folder/'equilibrium-configurations.png',dpi=170);fig.savefig(folder/'equilibrium-configurations.svg');plt.close(fig)
    diagnostic=json.loads((ROOT/'research/nonlinear-catalogue-challenge.json').read_text());numeric=report['methods']['numerical']['best_bias_N_mm'];value=meta['best_bias_N_mm']
    dense=json.loads((ROOT/'research/nonlinear-dense-check.json').read_text())['checks'];lookup={c['method']:c['result']['worst_bias_N_mm'] for c in dense}
    fig,ax=plt.subplots(figsize=(9,4.6));values=[numeric,diagnostic['refined']['worst_bias_N_mm'],value];labels=['Frozen numerical control','Post-hoc spring grid','Muse architecture'];x=list(range(3))
    bars=ax.bar([v-.18 for v in x],values,width=.36,label='64 starts / setting',color='#5f88b5')
    dense_values=[lookup.get(k,values[i]) for i,k in enumerate(['numerical','posthoc','meta'])];bars2=ax.bar([v+.18 for v in x],dense_values,width=.36,label='256 starts / setting',color='#c27c4f')
    for i in [1]:bars[i].set_hatch('//');bars2[i].set_hatch('//')
    for bar,v in zip(list(bars)+list(bars2),values+dense_values):ax.text(bar.get_x()+bar.get_width()/2,v+.6,f'{v:.2f}',ha='center',fontsize=9)
    ax.set_xticks(x,labels);ax.set(ylabel='Worst A/B found-state energy bias (mJ)',ylim=(0,max(values+dense_values)*1.22),title='More complete state search can change the apparent design score');ax.legend();ax.spines[['top','right']].set_visible(False)
    fig.text(.04,.02,'One exploratory task. Original numerical sampling used a narrower preload range; hatched grid is post-hoc.\nAll shown selected designs pass local-minimum checks. Found-state bias is not a transition barrier, global preference proof or scientific novelty.',fontsize=8)
    fig.tight_layout(rect=(0,.09,1,1));fig.savefig(folder/'bias-comparison.png',dpi=170);fig.savefig(folder/'bias-comparison.svg');plt.close(fig)
    (out/'README.md').write_text('OBJ coordinates are in millimeters. Import into Blender or another mesh viewer with matching units. These are open triangular surface visualizations of a bar/hinge reduced model, not watertight solids, printable parts or validated CAD. The companion JSON contains exact parameters and computed equilibrium/stability evidence. No physical measurements exist.\n')
    print(json.dumps({'plots':['equilibrium-configurations.png','bias-comparison.png'],'OBJ_directory':str(out),'additional_model_calls':0}))


if __name__=='__main__':main()
