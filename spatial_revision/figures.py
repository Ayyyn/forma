"""Views from cached mechanics; no additional online physics solves."""
from pathlib import Path
import threading
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from spatial_actuator.figures import deformed_member
LOCK=threading.Lock()


def render(t,record,result,path):
    with LOCK:
        nodes=result['nodes'];u=result['solved']['u'][:,0];fig=plt.figure(figsize=(11,7))
        axes=[fig.add_subplot(2,2,1,projection='3d')]+[fig.add_subplot(2,2,k) for k in [2,3,4]]
        for ax,view in zip(axes,[None,(0,2),(0,1),(1,2)]):
            for edge,r,part in zip(result['edges'],record['radii_mm'],result['solved']['parts']):
                initial,motion=deformed_member(nodes,edge,part,u,60.)
                if view is None:ax.plot(*initial.T,color='#385d85');ax.plot(*motion.T,color='#c26842',ls='--')
                else:
                    a,b=view;ax.plot(initial[:,a],initial[:,b],color='#385d85');ax.plot(motion[:,a],motion[:,b],color='#c26842',ls='--')
            for v in sorted({v for e in result['edges'] for v in e}):
                color='black' if v<4 else '#19868a' if v==4 else '#c33b3b' if v==9 else '#385d85'
                if view is None:ax.scatter(*nodes[v],color=color,s=15);ax.text(*nodes[v],str(v),fontsize=7)
                else:
                    a,b=view;ax.scatter(nodes[v,a],nodes[v,b],color=color,s=15);ax.annotate(str(v),nodes[v,[a,b]],fontsize=7)
            if view is None:ax.set(xlabel='x (mm)',ylabel='y (mm)',zlabel='z (mm)');ax.set_box_aspect((40,16,20));ax.view_init(20,-60)
            else:ax.set(xlabel='xyz'[view[0]]+' (mm)',ylabel='xyz'[view[1]]+' (mm)');ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.2)
        m=record['metrics'];fig.suptitle(f"{t['id']} | target output sign {t['output_sign']:+d} z | volume {m['volume_proxy_mm3']:.2f} mm³\nSigned loaded stroke {1000*m['loaded_stroke_mm']:.2f} µm; input travel {1000*m['input_travel_mm']:.2f} µm",fontsize=11)
        fig.text(.025,.025,'Blue: initial centerlines. Orange dashed: actual Hermite deformation ×60. Line thickness illustrative; exact radii in JSON.\nBlack: anchors; teal: force input; red: spring-loaded output. Linear ideal model, no hardware validation.',fontsize=8)
        fig.tight_layout(rect=(0,.07,1,.91));fig.savefig(path,dpi=140);plt.close(fig)
