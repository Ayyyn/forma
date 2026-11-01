"""Declared ideal-spring experiments. These are predictions, not measurements."""
from dataclasses import replace
import numpy as np
from .model import AxialSpring,jet
from .statics import equilibria,branch_barrier,relax_phi
from .oracle import high_precision_jet


def spring_experiments(cell,bare_states):
    # Original planned value is retained even though it suppresses the second well.
    multipliers=[.001,.002,.005,.01,.02,.05,.1]
    offsets=np.linspace(0,.1*cell.h0_mm,21)
    sweeps=[]
    for multiplier in [.002,.1]:
        k=multiplier*cell.ks_N/cell.r_mm
        for offset in offsets:
            spring=AxialSpring(True,k,float(offset))
            result=equilibria(cell,spring,grid=7)
            barrier=branch_barrier(cell,result['states'],spring)
            sweeps.append({'stiffness_multiplier_ks_over_r':multiplier,'spring':spring.to_dict(),
                           'states':result['states'],'search':result['search'],'branch_barrier':barrier})
    stiffness_sweep=[]
    for multiplier in multipliers:
        for offset in [0.,.1*cell.h0_mm]:
            spring=AxialSpring(True,multiplier*cell.ks_N/cell.r_mm,offset)
            result=equilibria(cell,spring,grid=7)
            stiffness_sweep.append({'multiplier':multiplier,'spring':spring.to_dict(),'states':result['states'],
                                    'search':result['search']})
    strong=[x for x in sweeps if x['stiffness_multiplier_ks_over_r']==.1]
    first=lambda item:min((s for s in item['states'] if s['classification']=='minimum'),key=lambda s:abs(s['u_mm']))
    low=first(strong[0]);high=first(strong[-1])
    selected=AxialSpring(**strong[-1]['spring'])
    q=[high['u_mm']/cell.r_mm,high['phi_rad']]
    _,go,ho=high_precision_jet(cell.to_dict(),q,selected.to_dict())
    repeat=equilibria(cell,selected,grid=9)
    refined=min((s for s in repeat['states'] if s['classification']=='minimum'),key=lambda s:abs(s['u_mm']-high['u_mm']))
    uncertainty=max(abs(refined['u_mm']-high['u_mm']),1e-8*cell.r_mm)
    shift=high['u_mm']-low['u_mm']
    _,bare_g,_=jet(cell,10.,.5)
    _,loaded_g,_=jet(cell,10.,.5,selected)
    expected_force_change=selected.stiffness_N_per_mm*(10-selected.offset_mm)
    force_error=abs(loaded_g[0]-bare_g[0]-expected_force_change)
    torque_error=abs(loaded_g[1]-bare_g[1])
    # At fixed axial displacement an axial-only spring cannot change the relaxed twist.
    angle_error=abs(relax_phi(cell,10.,selected)['phi_rad']-relax_phi(cell,10.)['phi_rad'])
    passed=abs(shift)>10*uncertainty and max(abs(go))<1e-8 and min(np.linalg.eigvalsh(ho))>1e-7
    passed=passed and force_error<1e-10 and torque_error<1e-10 and angle_error<1e-9
    return {'passed':bool(passed),'spring_law':'0.5*k_e*(offset-u)^2 when enabled, zero when disabled',
            'scope':'bilateral, always-engaged ideal axial spring; not the disengaging experimental apparatus',
            'protocol_note':'Strong planned spring retained; weaker sweep added explicitly to examine retained bistability. All declared outcomes are saved.',
            'primary_equilibrium_shift':{'from':low,'to':high,'shift_mm':shift,'numerical_uncertainty_estimate_mm':uncertainty,
                                         'independent_high_precision_gradient_residual':float(max(abs(go)))},
            'identity_checks':{'force_increment_error_N':float(force_error),'torque_increment_error_N_mm':float(torque_error),
                               'fixed_u_relaxed_twist_change_rad':float(angle_error)},
            'preload_sweeps':sweeps,'stiffness_sweep':stiffness_sweep,
            'uncertainty_note':'numerical uncertainty only; stiffness and material uncertainty are not inferred'}
