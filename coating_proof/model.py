"""Oblique planar-film R/T, two independent formulations and primary n/k data.

Vacuum wavelengths and thicknesses in nm; exp(-i omega t), passive n+i*k.
Flat isotropic coherent layers, semi-infinite media. No roughness/scattering,
finite substrate rear face, deposition validation or thermal/cell efficiency.
"""
from pathlib import Path
from functools import lru_cache
import re
import numpy as np
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'research/frontier_scout/vendor/refractive-index/database/data/main'

def index(material,wavelength_nm):
    wavelengths=np.atleast_1d(np.asarray(wavelength_nm,float))
    return _index_cached(material,tuple(wavelengths.tolist()))

@lru_cache(maxsize=128)
def _index_cached(material,wavelength_nm):
    wavelengths=np.atleast_1d(np.asarray(wavelength_nm,float));microns=wavelengths/1000
    if not np.isfinite(wavelengths).all() or (wavelengths<=0).any():raise ValueError('Positive finite vacuum wavelength required')
    if material=='SiO2':
        text=(DATA/'SiO2/nk/Malitson.yml').read_text(encoding='utf-8')
        if 'type: formula 1' not in text:raise ValueError('Unexpected silica source format')
        bounds=[float(v) for v in re.search(r'wavelength_range:\s*([^\n]+)',text)[1].split()]
        if microns.min()<bounds[0] or microns.max()>bounds[1]:raise ValueError('Outside source validity range')
        coefficients=[float(v) for v in re.search(r'coefficients:\s*([^\n]+)',text)[1].split()];n2=1+coefficients[0]+np.zeros(len(microns))
        for b,c in zip(coefficients[1::2],coefficients[2::2]):n2+=b*microns**2/(microns**2-c*c)
        return np.sqrt(n2).astype(complex)
    if material=='TiO2':
        text=(DATA/'TiO2/nk/Siefke.yml').read_text(encoding='utf-8');rows=[]
        if 'type: tabulated nk' not in text:raise ValueError('Unexpected titania source format')
        for line in text.splitlines():
            parts=line.split()
            if len(parts)!=3:continue
            try:rows.append([float(v) for v in parts])
            except ValueError:pass
        table=np.array(rows)
        if len(table)<3 or (np.diff(table[:,0])<=0).any():raise ValueError('Invalid n/k source table')
        if microns.min()<table[0,0] or microns.max()>table[-1,0]:raise ValueError('No material-data extrapolation allowed')
        return np.interp(microns,table[:,0],table[:,1])+1j*np.interp(microns,table[:,0],table[:,2])
    raise ValueError('Unknown verified material')

def setup(indices,thicknesses_nm,wavelengths_nm,angle_deg,polarization):
    wave=np.atleast_1d(np.asarray(wavelengths_nm,float));n=np.array([np.broadcast_to(np.asarray(v,complex),wave.shape) for v in indices]);d=np.asarray(thicknesses_nm,float)
    if len(n)!=len(d)+2 or not 0<=len(d)<=64 or polarization not in ['s','p'] or not 0<=angle_deg<85:raise ValueError('Invalid stack/angle/polarization')
    if not np.isfinite(n).all() or not np.isfinite(d).all() or not np.isfinite(wave).all() or (wave<=0).any() or (d<0).any() or (n.real<=0).any() or (n.imag<-1e-12).any() or (abs(n[0].imag)>1e-12).any():raise ValueError('Positive finite passive indices and dimensions required; lossless incident medium')
    parallel=n[0]*np.sin(np.deg2rad(angle_deg));cosine=np.sqrt(1-(parallel[None,:]/n)**2+0j);longitudinal=n*cosine
    reverse=(longitudinal.imag<-1e-12)|((abs(longitudinal.imag)<=1e-12)&(longitudinal.real<0));cosine[reverse]*=-1
    q=n*cosine if polarization=='s' else n/cosine
    phase=2*np.pi*n[1:-1]*cosine[1:-1]*d[:,None]/wave
    return n,q,phase

def recursive_rt(indices,thicknesses_nm,wavelengths_nm,angle_deg=0.,polarization='s'):
    n,q,phase=setup(indices,thicknesses_nm,wavelengths_nm,angle_deg,polarization);r=(q[-2]-q[-1])/(q[-2]+q[-1]);t=2*q[-2]/(q[-2]+q[-1])
    for j in range(len(thicknesses_nm)-1,-1,-1):
        interface=(q[j]-q[j+1])/(q[j]+q[j+1]);transmission=2*q[j]/(q[j]+q[j+1]);prop=np.exp(1j*phase[j]);denom=1+interface*r*prop**2;t=transmission*t*prop/denom;r=(interface+r*prop**2)/denom
    R=abs(r)**2;T=q[-1].real/q[0].real*abs(t)**2
    if not np.isfinite(R).all() or not np.isfinite(T).all():raise ValueError('Nonfinite optical prediction')
    return {'R':R,'T':T,'A':1-R-T}

def matrix_rt(indices,thicknesses_nm,wavelengths_nm,angle_deg=0.,polarization='s'):
    n,q,phase=setup(indices,thicknesses_nm,wavelengths_nm,angle_deg,polarization);M=np.broadcast_to(np.eye(2,dtype=complex),(n.shape[1],2,2)).copy()
    for j in range(len(thicknesses_nm)):
        c=np.cos(phase[j]);s=-1j*np.sin(phase[j]);layer=np.empty_like(M);layer[:,0,0]=layer[:,1,1]=c;layer[:,0,1]=s/q[j+1];layer[:,1,0]=s*q[j+1];M=M@layer
    D=q[0]*M[:,0,0]+q[0]*q[-1]*M[:,0,1]+M[:,1,0]+q[-1]*M[:,1,1];r=(q[0]*M[:,0,0]+q[0]*q[-1]*M[:,0,1]-M[:,1,0]-q[-1]*M[:,1,1])/D;t=2*q[0]/D
    R=abs(r)**2;T=q[-1].real/q[0].real*abs(t)**2
    return {'R':R,'T':T,'A':1-R-T}

def evaluate_stack(layers,wavelengths_nm,angle_deg=0.,polarization='s'):
    if not isinstance(layers,list) or len(layers)>20:raise ValueError('At most20 planar layers')
    for layer in layers:
        if set(layer)!={'material','thickness_nm'} or not 20<=layer['thickness_nm']<=350:raise ValueError('Layer schema/thickness bounds')
    if sum(layer['thickness_nm'] for layer in layers)>3000:raise ValueError('Total film thickness exceeds3000nm')
    wave=np.atleast_1d(wavelengths_nm);indices=[np.ones(len(wave),complex)]+[index(layer['material'],wave) for layer in layers]+[index('SiO2',wave)]
    return recursive_rt(indices,[l['thickness_nm'] for l in layers],wave,angle_deg,polarization)
