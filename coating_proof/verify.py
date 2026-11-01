"""Numerical feasibility and analytical/external checks, no Meta calls."""
import hashlib,json,platform,sys,zipfile
from pathlib import Path
import numpy as np
from .model import ROOT,index,recursive_rt,matrix_rt,evaluate_stack

def source_checks():
    folder=ROOT/'research/frontier_scout/vendor/refractive-index';record=json.loads((folder/'receipt.json').read_text())
    for file in record['files']:
        if hashlib.sha256((folder/file['path']).read_bytes()).hexdigest()!=file['sha256']:raise ValueError('Material source hash mismatch')
    return record

def external_check():
    folder=ROOT/'research/frontier_scout/vendor/tmm';receipt=json.loads((folder/'receipt.json').read_text());wheel=(folder/receipt['filename']).resolve()
    if hashlib.sha256(wheel.read_bytes()).hexdigest()!=receipt['sha256']:raise ValueError('Reference wheel hash mismatch')
    sys.path.insert(0,str(wheel));import tmm
    if str(wheel) not in tmm.__file__:raise ValueError('Unexpected reference implementation')
    rng=np.random.default_rng(3010202602);waves=np.array([425.,550.,700.,1000.,1350.]);max_external=0.;max_matrix=0.;minimum_absorptance=1.;checks=0
    for case in range(64):
        count=int(rng.integers(0,13));materials=rng.choice(['SiO2','TiO2'],count).tolist();d=rng.uniform(20,250,count).tolist();ns=[np.ones(len(waves))]+[index(name,waves) for name in materials]+[index('SiO2',waves)]
        for angle in [0.,23.,57.]:
            for pol in ['s','p']:
                a=recursive_rt(ns,d,waves,angle,pol);b=matrix_rt(ns,d,waves,angle,pol);max_matrix=max(max_matrix,float(abs(a['R']-b['R']).max()),float(abs(a['T']-b['T']).max()));minimum_absorptance=min(minimum_absorptance,float(a['A'].min()))
                for i,wave in enumerate(waves):
                    reference=tmm.coh_tmm(pol,[n[i] for n in ns],[np.inf,*d,np.inf],np.deg2rad(angle),float(wave));max_external=max(max_external,float(abs(a['R'][i]-reference['R'])),float(abs(a['T'][i]-reference['T'])));checks+=1
    passed=bool(max_external<1e-10 and max_matrix<1e-10 and minimum_absorptance>=-1e-10)
    if not passed:raise ValueError('External optics check failed')
    return {'passed':passed,'point_checks':checks,'random_stacks':64,'maximum_RT_error_against_tmm':max_external,'maximum_RT_error_between_own_formulations':max_matrix,'minimum_absorptance_roundoff':minimum_absorptance,'reference':receipt}

def metrics(layers,band_points=41):
    visible=np.linspace(450,650,band_points);infrared=np.linspace(900,1100,band_points);waves=np.r_[visible,infrared];T=[];R=[];rng=np.random.default_rng(3010202603);count=len(layers);d=np.array([l['thickness_nm'] for l in layers]);perturbations=[np.zeros(count),np.full(count,3.),np.full(count,-3.),np.array([3. if i%2 else -3. for i in range(count)]),rng.uniform(-3,3,count)]
    for perturbation in perturbations:
        proposal=[{'material':l['material'],'thickness_nm':float(value)} for l,value in zip(layers,d+perturbation)]
        for angle in [0.,30.]:
            for pol in ['s','p']:
                value=evaluate_stack(proposal,waves,angle,pol);T.append(float(np.trapezoid(value['T'][:band_points],visible)/200));R.append(float(np.trapezoid(value['R'][band_points:],infrared)/200))
    minimum_T,minimum_R=min(T),min(R);violation=max(0.,.85-minimum_T)+max(0.,.8-minimum_R)
    return {'minimum_sampled_visible_band_average_T':minimum_T,'minimum_sampled_NIR_band_average_R':minimum_R,'violation':violation,'feasible_in_samples':violation<=1e-10,'quality_loss':violation+.01*(2-minimum_T-minimum_R),'total_thickness_nm':sum(d),'wavelength_quadrature_points_per_band':band_points,'scope':'Uniform-wavelength trapezoidal band integrals; five sampled thickness perturbations, angles0/30deg, both polarizations. Not full tolerance bounds, photopic/solar weighting, finished-window transmission, cooling power or fabricated-stack validation.'}

def baseline_grid():
    results=[]
    for pairs in [2,4,6,8,10]:
        for center in [850.,900.,950.,1000.,1050.,1100.,1150.]:
            layers=[{'material':name,'thickness_nm':float(center/(4*index(name,[center])[0].real))} for _ in range(pairs) for name in ['TiO2','SiO2']]
            try:result=metrics(layers);results.append({'pairs':pairs,'center_nm':center,'layers':layers,'metrics':result})
            except ValueError as exc:results.append({'pairs':pairs,'center_nm':center,'error':str(exc)})
    best=min((r for r in results if 'metrics' in r),key=lambda r:r['metrics']['quality_loss'])
    return {'scope':'Human-written conventional quarter-wave grid; not AI-designed, new-to-science or a serious global-optimization efficacy baseline. Establishes a reproducible reference starting point; target feasibility is reported explicitly, not assumed.','evaluated_recipes':len(results),'recipes':results,'best':best}

def run():
    source=source_checks();reference=external_check();grid=baseline_grid();out=ROOT/'output/coating-proof';out.mkdir(parents=True,exist_ok=True)
    result={'scope':'Numerical forward-model feasibility proof only; no Meta discovery/efficacy experiment has run in this optics direction.','source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},'runtime':{'python':platform.python_version(),'numpy':np.__version__},'material_data':source,'independent_reference':reference,'baseline_feasibility':grid,'physical_experiments':0,'Meta_API_calls':0}
    (out/'proof.json').write_text(json.dumps(result,indent=2));(out/'baseline-recipe.json').write_text(json.dumps(grid['best'],indent=2))
    with zipfile.ZipFile(ROOT/'research/frontier_scout/vendor/tmm'/reference['reference']['filename']) as archive:
        license_name=next(name for name in archive.namelist() if 'LICENSE' in name.upper());(out/'reference-license.txt').write_bytes(archive.read(license_name))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    waves=np.linspace(400,1400,501);fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    for angle in [0.,30.]:
        for pol in ['s','p']:
            spectra=evaluate_stack(grid['best']['layers'],waves,angle,pol);label=f'{angle:g}deg {pol}'
            axes[0].plot(waves,spectra['T'],label=label);axes[1].plot(waves,spectra['R'],label=label)
    for ax,title in zip(axes,['Transmission into the substrate','Front reflectance']):
        ax.set(xlabel='Vacuum wavelength (nm)',ylabel='Power fraction',title=title,ylim=(-.02,1.02));ax.axvspan(450,650,color='#bbbbbb',alpha=.15);ax.axvspan(900,1100,color='#888888',alpha=.1);ax.legend(fontsize=9);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Conventional coating feasibility witness — not an AI discovery');fig.text(.5,.005,'Measured n/k input; ideal coherent planar films; no fabricated-device or cooling-power claim.',ha='center',fontsize=10);fig.tight_layout(rect=[0,.035,1,.94]);fig.savefig(out/'baseline-spectrum.png',dpi=160);plt.close(fig)
    print(json.dumps({'external_check':reference,'baseline_best':{k:v for k,v in grid['best'].items() if k!='layers'},'Meta_calls':0},indent=2))
