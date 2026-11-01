"""Data-backed beam-envelope diagrams of the frozen and post-hoc candidates."""
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from structure_lab.design import geometry,task_cases


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon,Rectangle
    folder=ROOT/'benchmarks/structure-pilot-v3'
    challenge=json.loads((ROOT/'research/structure-catalogue-challenge.json').read_text())
    enhanced={r['task']:r['best'] for r in challenge['results']}
    fig,axes=plt.subplots(2,3,figsize=(12,6.7),layout='constrained')
    for row,tid in enumerate(['stiff_mount','clear_channel']):
        task=next(t for t in task_cases() if t['id']==tid);nodes,edges=geometry(task['length_mm'],task['height_mm']);nodes=np.asarray(nodes)
        candidates=[json.loads((folder/'runs'/f'{tid}-202-{m}.json').read_text())['best'] for m in ['numerical','tool_agent']]+[enhanced[tid]]
        for col,(label,candidate,color) in enumerate(zip(['Frozen numerical','Frozen Meta agent','Post-hoc wider catalogue'],candidates,['#58746d','#bb693a','#476f8d'])):
            ax=axes[row,col]
            gap=task.get('central_gap_half_height_mm',0.)
            if gap:ax.add_patch(Rectangle((8,-gap),24,2*gap,fc='#efc7b8',alpha=.7))
            active=set()
            for eid,width in zip(candidate['edge_ids'],candidate['widths_mm']):
                i,j=edges[eid];a,b=nodes[[i,j]];d=b-a;perp=np.array([-d[1],d[0]])/np.linalg.norm(d)*width/2
                ax.add_patch(Polygon([a+perp,b+perp,b-perp,a-perp],fc=color,ec=color,lw=.4));active.update([i,j])
            active=sorted(active);ax.scatter(nodes[active,0],nodes[active,1],s=8,c=color,zorder=3)
            used=[i for i in [0,1,2] if i in active];ax.scatter(nodes[used,0],nodes[used,1],s=35,marker='s',c='#242424',zorder=4)
            ax.scatter(*nodes[7],s=60,marker='*',c='#242424',zorder=4)
            ax.set(xlim=(-2,42),ylim=(-12,12),xlabel='x (mm)',ylabel='y (mm)',aspect='equal',
                   title=f"{label}\n{tid}: {candidate['volume_mm3']:.1f} mm³ proxy")
            ax.spines[['top','right']].set_visible(False);ax.tick_params(labelsize=8)
    fig.suptitle('Two structural leads and a catalogue-coverage check',fontsize=14)
    fig.supxlabel('Seed 202 illustrations. Ideal beam envelopes/joints; synthetic linear models.\nPost-hoc catalogue designed after the pilot. All motion losses, ties and failures remain in the full report.',fontsize=9)
    fig.savefig(folder/'structures.png',dpi=160);fig.savefig(folder/'structures.svg');plt.close(fig)


if __name__=='__main__':main()
