"""Public task definition and mechanical prediction catalogue; no API calls."""
from dataclasses import replace
from itertools import product
import math
import numpy as np
from kresling_proof.model import Cell,AxialSpring,jet
from kresling_proof.oracle import vertex_energy

BUDGET=4
SEEDS=[101,202,303]
NOISE=np.array([.015,.20]) # synthetic standard deviations: N, N mm
QUADRATURE=25


def catalogue():
    cell=Cell()
    hypotheses=[]
    springs=[AxialSpring(),AxialSpring(True,.002*cell.ks_N/cell.r_mm,0),
             AxialSpring(True,.002*cell.ks_N/cell.r_mm,.1*cell.h0_mm),
             AxialSpring(True,.1*cell.ks_N/cell.r_mm,.1*cell.h0_mm)]
    for kr,spring in product([0.,.0025,.005,.01],springs):
        hypotheses.append({'id':f'H{len(hypotheses)+1:02d}','kr_per_length':kr,'spring':spring.to_dict()})
    experiments=[{'id':f'E{i+1:02d}','u_mm':u,'phi_deg':p} for i,(u,p) in enumerate(product([3.,12.,21.,30.],[8.,28.,48.]))]
    heldout=[{'id':f'V{i+1:02d}','u_mm':u,'phi_deg':p} for i,(u,p) in enumerate(product([6.,15.,24.,33.],[14.,38.]))]
    def predictions(settings):
        means=[]
        for h in hypotheses:
            c=replace(cell,kr_per_length=h['kr_per_length']);s=AxialSpring(**h['spring'])
            means.append([jet(c,e['u_mm'],math.radians(e['phi_deg']),s)[1].tolist() for e in settings])
        return np.asarray(means)
    calibration=[{'id':f'C{i+1:02d}','offset_F_T':[f,t]} for i,(f,t) in enumerate(product([-.1,0.,.1],[-1.,0.,1.]))]
    return {'cell':cell.to_dict(),'hypotheses':hypotheses,'calibration_profiles':calibration,'experiments':experiments,'heldout':heldout,
            'means':predictions(experiments).tolist(),'heldout_means':predictions(heldout).tolist(),
            'noise_std_F_T':NOISE.tolist(),'measurement_budget':BUDGET,
            'observation_protocol':'Hold both reduced coordinates u and phi; read axial reaction and torque together. One paired F/T observation costs one slot.',
            'physical_data':False}


def oracle_check(data):
    """Independent finite differences of the vertex energy at every catalogue pose."""
    errors=[]
    for hi,h in enumerate(data['hypotheses']):
        parameters={**data['cell'],'kr_per_length':h['kr_per_length']}
        for key,means_key in [('experiments','means'),('heldout','heldout_means')]:
            for ei,e in enumerate(data[key]):
                u=e['u_mm'];p=math.radians(e['phi_deg']);v=lambda a,b:vertex_energy(parameters,a,b,h['spring'])
                def derivative(axis,step):
                    f=(lambda x:v(x,p)) if axis==0 else (lambda x:v(u,x))
                    at=u if axis==0 else p
                    return (-f(at+2*step)+8*f(at+step)-8*f(at-step)+f(at-2*step))/(12*step)
                reference=np.array([derivative(0,1e-3),derivative(1,1e-4)])
                prediction=np.array(data[means_key][hi][ei])
                errors.append(np.abs(reference-prediction))
    maximum=np.max(errors,axis=0)
    return {'passed':bool(np.all(maximum<1e-6)),'states_checked':len(errors),
            'max_abs_force_error_N':float(maximum[0]),'max_abs_torque_error_N_mm':float(maximum[1]),
            'method':'five-point finite difference of independent vertex/face-normal energy',
            'scope':'same reduced constitutive model, not experimental validation'}
