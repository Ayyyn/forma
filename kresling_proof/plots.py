"""Scientific plots from saved calculations, with reference/simulation distinctions."""
from pathlib import Path
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from .model import energy,Cell,AxialSpring


def make_plots(cell,report,curve,out):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
    files=[]
    def save(fig,name):
        fig.savefig(out/(name+'.png'),bbox_inches='tight')
        fig.savefig(out/(name+'.svg'),bbox_inches='tight')
        plt.close(fig);files.append(name+'.png')
    u=np.linspace(0,cell.h0_mm-1e-5*cell.r_mm,241)
    p=np.linspace(0,cell.phi_max,241)
    U=energy(cell,u[None,:],p[:,None])/cell.energy_scale
    fig,ax=plt.subplots(figsize=(8.8,5.8))
    levels=np.linspace(0,.025,26)
    contour=ax.contourf(u/cell.r_mm,np.degrees(p),U,levels=levels,extend='max',cmap='viridis')
    fig.colorbar(contour,ax=ax,label='U / (ks r)')
    ax.plot([x['u_mm']/cell.r_mm for x in curve],[x['phi_deg'] for x in curve],color='white',lw=1.7,label='Lowest sampled angular well, refined')
    for state in report['equilibria']['states']:
        minimum=state['classification']=='minimum'
        ax.scatter(state['u_mm']/cell.r_mm,state['phi_deg'],s=80,marker='o' if minimum else 'X',
                   color='#efc84a' if minimum else '#ed5b57',edgecolor='black',zorder=4)
        ax.annotate(state['classification'],(state['u_mm']/cell.r_mm,state['phi_deg']),xytext=(8,7),textcoords='offset points')
    ax.set(xlabel='Axial compression u / r',ylabel='Additional twist phi (degrees)',
           title='Published five-term reduced model: energy and stationary states')
    ax.legend(loc='upper left',fontsize=8)
    fig.text(.1,.005,'Minima are stable only within the reduced (u, phi) model. Contact and non-axisymmetric modes are excluded.',fontsize=8)
    fig.tight_layout(rect=(0,.035,1,1));save(fig,'01_energy_landscape')

    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    x=np.array([c['u_mm']/cell.r_mm for c in curve]);y=[c['energy_normalized'] for c in curve]
    axes[0].plot(x,y,label='Computed: declared paper parameters',color='#235b94')
    ref=report['published_reproduction']['curve_comparison']
    axes[0].scatter([v['u_over_r'] for v in ref],[v['U_over_ks_r'] for v in ref],s=20,
                    facecolors='none',edgecolors='#a63631',label='Published theory: frozen PDF samples')
    axes[0].set(xlabel='u / r',ylabel='U / (ks r)',title='Figure 5A reproduction')
    axes[0].legend(fontsize=8)
    error=report['published_reproduction']['checks'][-1]['nrmse_full_vertical_range']
    axes[0].set_title(f'Figure 5A reproduction\nNRMSE / plotted vertical range: {100*error:.3f}%',fontsize=11)
    axes[1].plot(x,[c['force_N'] for c in curve],color='#235b94')
    axes[1].axhline(0,color='gray',lw=.7)
    axes[1].set(xlabel='u / r',ylabel='Axial reaction dU/du (N)',title='Computed force along free-rotation branch')
    fig.suptitle('Numerical reproduction of theory; no new physical measurements',fontsize=12)
    fig.tight_layout();save(fig,'02_published_reproduction')

    fig,axes=plt.subplots(1,2,figsize=(11,4.8))
    colors={.002:'#235b94',.1:'#a94c36'}
    for multiplier in [.002,.1]:
        rows=[r for r in report['prestress']['preload_sweeps'] if r['stiffness_multiplier_ks_over_r']==multiplier]
        offsets=[r['spring']['offset_mm'] for r in rows]
        first=[];second=[];barriers=[]
        for row in rows:
            minima=sorted((s for s in row['states'] if s['classification']=='minimum'),key=lambda s:s['u_mm'])
            first.append(minima[0]['u_mm'] if minima else np.nan)
            second.append(minima[1]['u_mm'] if len(minima)>1 else np.nan)
            b=row['branch_barrier'];barriers.append(b['forward_N_mm'] if b['status']=='resolved_on_declared_branch' else np.nan)
        label=f'k_e = {multiplier:g} ks/r'
        axes[0].plot(offsets,first,'o-',markersize=3,color=colors[multiplier],label=label+'; first minimum')
        if np.any(np.isfinite(second)):axes[0].plot(offsets,second,'--',color=colors[multiplier],label=label+'; second minimum')
        if np.any(np.isfinite(barriers)):axes[1].plot(offsets,barriers,'o-',markersize=3,color=colors[multiplier],label=label)
    axes[0].set(xlabel='Spring reference offset (mm)',ylabel='Equilibrium compression u (mm)',title='Predicted equilibrium positions')
    axes[1].set(xlabel='Spring reference offset (mm)',ylabel='Forward branch barrier (mJ = N mm)',title='Barrier only where two wells are resolved')
    axes[0].legend(fontsize=7);axes[1].legend(fontsize=8)
    axes[1].text(.03,.04,'Strong spring: second well not found in declared search.\nMissing barriers are not plotted as zero.',transform=axes[1].transAxes,fontsize=8)
    fig.suptitle('Ideal bilateral spring predictions; stiffness/offset inputs are numerical study choices',fontsize=11)
    fig.tight_layout();save(fig,'03_prestress_sensitivity')

    fig,axes=plt.subplots(1,2,figsize=(10,4.6))
    rows=report['independent_verification']['finite_difference_step_study']
    for q in [x['q'] for x in report['independent_verification']['high_precision_comparisons']]:
        selected=[r for r in rows if r['q']==q]
        axes[0].loglog([r['step'] for r in selected],[max(r['gradient_error_inf'],1e-18) for r in selected],'o-',label=str(q))
    axes[0].set(xlabel='Dimensionless finite-difference step',ylabel='Gradient discrepancy (infinity norm)',title='Derivative step study')
    axes[0].legend(title='(u/r, phi)',fontsize=7)
    conv=report['convergence']
    axes[1].plot(conv['root_scan_grids'],conv['state_counts'],'o-',color='#235b94')
    axes[1].set(xlabel='Multi-start grid points per axis',ylabel='Distinct stationary points found',title='Stationary-search refinement',ylim=(0,4))
    axes[1].text(.07,.1,f"Max scaled state difference: {conv['max_scaled_stationary_discrepancy']:.2e}\nNot a proof of exhaustive root isolation.",transform=axes[1].transAxes,fontsize=8)
    fig.tight_layout();save(fig,'04_numerical_checks')
    return files
