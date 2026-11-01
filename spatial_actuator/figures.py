"""Scientific views generated from actual numerical geometry/solutions."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from .design import compute


def deformed_member(nodes,edge,part,u,magnification=60.):
    a,b=edge;dofs,dk,T,kl,L=part;local=T@u[dofs];R=T[:3,:3];initial=[];deformed=[]
    for s in np.linspace(0,1,31):
        H=np.array([1-3*s*s+2*s**3,L*(s-2*s*s+s**3),3*s*s-2*s**3,L*(-s*s+s**3)])
        displacement=np.array([(1-s)*local[0]+s*local[6],H@local[[1,5,7,11]],H@(local[[2,4,8,10]]*[1,-1,1,-1])])@R
        point=(1-s)*nodes[a]+s*nodes[b];initial.append(point);deformed.append(point+magnification*displacement)
    return np.array(initial),np.array(deformed)


def design_figure(t,record,path,evaluated=None):
    result=evaluated if evaluated is not None else compute(t,record['edge_ids'],record['radii_mm']);nodes=result['nodes'];u=result['solved']['u'][:,0]
    fig=plt.figure(figsize=(12,8));axes=[fig.add_subplot(2,2,1,projection='3d')]+[fig.add_subplot(2,2,k) for k in [2,3,4]]
    views=[None,(0,2),(0,1),(1,2)];names=['Spatial view','XZ view','XY view','YZ view'];labels=['x (mm)','y (mm)','z (mm)']
    for ax,view,name in zip(axes,views,names):
        for edge,r,part in zip(result['edges'],record['radii_mm'],result['solved']['parts']):
            initial,motion=deformed_member(nodes,edge,part,u)
            if view is None:
                ax.plot(*initial.T,color='#385d85',lw=2);ax.plot(*motion.T,color='#cd6840',ls='--',lw=1.4)
            else:
                x,y=view;ax.plot(initial[:,x],initial[:,y],color='#385d85',lw=2);ax.plot(motion[:,x],motion[:,y],color='#cd6840',ls='--',lw=1.4)
        for v in sorted({v for edge in result['edges'] for v in edge}):
            color='#222222' if v<4 else '#087e8b' if v==4 else '#b33232' if v==9 else '#385d85'
            if view is None:ax.scatter(*nodes[v],color=color,s=24);ax.text(*nodes[v],f' {v}',fontsize=8)
            else:
                x,y=view;ax.scatter(nodes[v,x],nodes[v,y],color=color,s=24);ax.annotate(str(v),nodes[v,[x,y]],xytext=(3,4),textcoords='offset points',fontsize=8)
        if view is None:
            ax.set(xlabel=labels[0],ylabel=labels[1],zlabel=labels[2]);ax.set_box_aspect((40,16,20));ax.view_init(22,-62)
        else:ax.set(xlabel=labels[view[0]],ylabel=labels[view[1]]);ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.15)
        ax.set_title(name,fontsize=10)
    metrics=result['metrics'];fig.suptitle(f"Loaded spatial compliant transmission | volume proxy {metrics['volume_proxy_mm3']:.2f} mm³\nInput +x: 2 mN at node 4; output +z: {metrics['loaded_stroke_mm']*1000:.2f} µm against {t['output_spring_N_mm']:.3g} N/mm spring at node 9",fontsize=12)
    fig.text(.03,.025,'Blue: initial centerlines. Orange dashed: Hermite deformation ×60. Line thickness is illustrative; exact radii in JSON.\nBlack nodes: clamped. Passive linear synthetic-material model; no hardware or clinical validation.',fontsize=9)
    fig.tight_layout(rect=(0,.07,1,.92));path=Path(path);fig.savefig(path,dpi=170);fig.savefig(path.with_suffix('.svg'));plt.close(fig)


def load_sweep(t,record,directory):
    values=[]
    for k in np.r_[0.,np.geomspace(.001,.2,30)]:
        changed=dict(t,output_spring_N_mm=float(k));result=compute(changed,record['edge_ids'],record['radii_mm']);values.append({'output_spring_N_mm':float(k),**result['metrics'],'feasible':result['feasible']})
    fig,axes=plt.subplots(1,3,figsize=(12,3.8));x=[v['output_spring_N_mm'] for v in values]
    for ax,key,scale,label in [(axes[0],'loaded_stroke_mm',1000,'Loaded output stroke (µm)'),(axes[1],'output_force_N',1000,'Output force (mN)'),(axes[2],'output_spring_energy_N_mm',1000,'Stored spring energy (µJ)')]:
        ax.plot(x,[v[key]*scale for v in values],color='#385d85');ax.axvline(t['output_spring_N_mm'],ls='--',color='#cd6840',lw=1);ax.set(xlabel='Output load stiffness (N/mm)',ylabel=label);ax.grid(alpha=.2)
    fig.suptitle('Same structure and 2 mN input; changing the resisting load changes motion and delivered force',fontsize=11)
    fig.text(.04,.015,'Linear quasistatic predictions. Dashed line: design load. Sweep points may violate design constraints; no physical experiment.',fontsize=8)
    fig.tight_layout(rect=(0,.05,1,.92));fig.savefig(Path(directory)/'load-sweep.png',dpi=170);fig.savefig(Path(directory)/'load-sweep.svg');plt.close(fig)
    return values
