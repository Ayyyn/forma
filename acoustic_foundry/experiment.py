"""Small development experiment. No held-out, physical or AI-advantage claim."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
from scipy.optimize import differential_evolution
from .model import response, uncertainty_cases, wave_oracle, resonance_hz

ROOT = Path(__file__).resolve().parents[1]
FREQUENCY = np.linspace(350, 1400, 211)
WEIGHT = np.exp(-.5*((FREQUENCY-620)/30)**2) + .7*np.exp(-.5*((FREQUENCY-1040)/40)**2)
WEIGHT /= WEIGHT.sum()
BOUNDS = [(3.,7.),(6.,22.),(8.,45.)]*3
TASK = {'name':'Two-tone duct filter development case','peaks_hz':[620,1040],
        'peak_sigma_hz':[30,40], 'relative_peak_power':[1,.7],
        'duct_diameter_mm':40, 'resonators':3, 'pitch_mm':42,
        'objective':'Minimize worst of seven sampled spectrum-weighted transmitted-power ratios',
        'limits':'Three side branches; radius 3–7 mm, neck 6–22 mm, cavity 8–45 cm3',
        'physics':'Rigid walls, plane waves, matched terminations, no mean flow. Assumed loss factor .04; sampled .02–.08. Uncalibrated screening model.',
        'evidence_class':'constructed development task; no held-out benchmark or physical measurements'}


def design_from_vector(x):
    return {'duct_diameter_mm':40.,'cells':[{'position_mm':42.*i,
            'neck_radius_mm':float(x[3*i]),'neck_length_mm':float(x[3*i+1]),
            'volume_cm3':float(x[3*i+2]),'end_correction_radii':1.7,'loss_factor':.04}
            for i in range(3)]}


def score(design, frequency=FREQUENCY, weight=WEIGHT):
    records=[]
    for name,d in uncertainty_cases(design):
        out=response(d,frequency)
        power=float(np.dot(weight,out['power_t']))
        records.append({'scenario':name,'transmitted_power_ratio':power,
                        'spectrum_attenuation_db':float(-10*np.log10(power))})
    worst=max(r['transmitted_power_ratio'] for r in records)
    return {'worst_sampled_power_ratio':worst,
            'worst_sampled_spectrum_attenuation_db':float(-10*np.log10(worst)),
            'scenarios':records}


def optimize(seed_vector, seed, budget=480):
    rng=np.random.default_rng(seed)
    pop=np.column_stack([rng.uniform(lo,hi,40) for lo,hi in BOUNDS])
    pop[0]=seed_vector
    best={'loss':float('inf')};trace=[];started=time.monotonic()
    def objective(x):
        if len(trace)>=budget:raise RuntimeError('Objective budget exceeded')
        design=design_from_vector(x);s=score(design);loss=s['worst_sampled_power_ratio']
        trace.append({'query':len(trace)+1,'parameters':list(map(float,x)),'loss':loss})
        if loss<best['loss']:best.update(loss=loss,design=design,score=s)
        return loss
    differential_evolution(objective,BOUNDS,init=pop,maxiter=budget//40-1,
                           polish=False,seed=seed,tol=0,atol=0,updating='immediate')
    return {'design':best['design'],'score':best['score'],'objective_calls':len(trace),
            'frequency_scenario_evaluations':len(trace)*len(FREQUENCY)*7,
            'elapsed_s':time.monotonic()-started,'trace':trace,
            'method':'SciPy differential evolution; common random population except first seed'}


def meta_seed(out):
    from scripts.api_preflight import load_env, request
    load_env()
    key=os.environ.get('MODEL_API_KEY') or os.environ.get('META_API_KEY')
    if not key:raise RuntimeError('Meta key missing; no synthetic replacement')
    system='''You propose a passive acoustic duct filter in a declared lumped-model research experiment.
Return only JSON: {"rationale":string,"cells":[{"neck_radius_mm":number,"neck_length_mm":number,"volume_cm3":number}, ... exactly 3]}.
Use bounds in task. Three Helmholtz shunts spaced 42 mm in a 40 mm diameter duct, rigid walls,
matched terminations, rho=1.204 kg/m3, c=343 m/s. Z=R+j(omega*M-1/(omega*C)),
M=rho*(neck_length+1.7*radius)/(pi*radius^2); C=volume/(rho*c^2); R=.04*sqrt(M/C).
Numerical sizing will refine your seed. Seven uncertainty samples vary radius +/- .15 mm,
neck length +/- .3 mm, volume +/-5%, end correction 1.4–2.0 radii, loss .02–.08.
Choose distinct useful tunings for the two noisy bands, allowing for robustness.
No simulation result, physical attenuation or novelty may be claimed. Do not produce code.'''
    payload={'model':'muse-wonder-1.0','messages':[{'role':'system','content':system},
             {'role':'user','content':json.dumps(TASK)}], 'max_tokens':4096,
             'reasoning_effort':'medium','response_format':{'type':'json_object'}}
    # Persist reservation before making the single request; reruns cannot spend again.
    receipt=out/'meta-receipt.json'
    if receipt.exists():raise RuntimeError('Existing request receipt; use a new experiment directory')
    receipt.write_text(json.dumps({'status':'reserved','maximum_requests':1,'maximum_output_tokens':4096,
                                  'estimated_spend_ceiling_usd':1.0},indent=2))
    (out/'meta-request.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    status,body=request('https://api.meta.ai/v1',key,'/chat/completions',payload,timeout=150)
    public={'transport':status,'model':payload['model'],'id':body.get('id') if body else None,
            'usage':body.get('usage') if body else None}
    if body:
        public['finish_reason']=body['choices'][0].get('finish_reason')
        public['content']=body['choices'][0]['message'].get('content')
    receipt.write_text(json.dumps(public,indent=2),encoding='utf-8')
    if not body:raise RuntimeError('Meta request failed; receipt retained')
    plan=json.loads(public['content'])
    if set(plan)!={'rationale','cells'} or not isinstance(plan['rationale'],str) or len(plan['cells'])!=3:
        raise ValueError('Invalid Meta proposal')
    x=[]
    for cell in plan['cells']:
        if set(cell)!={'neck_radius_mm','neck_length_mm','volume_cm3'}:raise ValueError('Invalid cell schema')
        for key,(lo,hi) in zip(['neck_radius_mm','neck_length_mm','volume_cm3'],BOUNDS[:3]):
            v=cell[key]
            if type(v) not in (int,float) or not np.isfinite(v) or not lo<=v<=hi:raise ValueError('Out of bounds proposal')
            x.append(v)
    (out/'meta-proposal.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    return x


def run(out, live=False):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=False)
    (out/'task.json').write_text(json.dumps(TASK,indent=2),encoding='utf-8')
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted((ROOT/'acoustic_foundry').glob('*.py'))}
    (out/'manifest.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),
       'sources':sources,'budget_per_optimization':480,'seed':20261101,
       'status':'development feasibility, not a prospective generalization study'},indent=2))
    # Obtain proposal BEFORE numerical results are available to the model.
    proposed=meta_seed(out) if live else None
    naive=[4.5,12,25]*3
    # Conventional analytic seed: tune one resonator at first peak, two at second.
    conventional=[]
    for f in [620,1040,1040]:
        r=.005;l=.010+1.7*r
        v=343**2*np.pi*r*r/((2*np.pi*f)**2*l)*1e6
        conventional += [5.,10.,float(np.clip(v,8,45))]
    results={'task':TASK,'naive':{'design':design_from_vector(naive),'score':score(design_from_vector(naive))}}
    results['numerical']=optimize(conventional,20261101)
    print('Numerical',results['numerical']['score']['worst_sampled_spectrum_attenuation_db'],flush=True)
    if proposed:
        results['meta_seeded']=optimize(proposed,20261101)
        print('Meta-seeded',results['meta_seeded']['score']['worst_sampled_spectrum_attenuation_db'],flush=True)
    # Always export strongest actual development candidate, with attribution.
    choices=[k for k in results if k in ['numerical','meta_seeded']]
    selected=min(choices,key=lambda k:results[k]['score']['worst_sampled_power_ratio'])
    design=results[selected]['design']
    dense=np.linspace(350,1400,2101)
    weight=np.exp(-.5*((dense-620)/30)**2)+.7*np.exp(-.5*((dense-1040)/40)**2);weight/=weight.sum()
    checks=[]
    for name,d in uncertainty_cases(design):
        f=np.linspace(350,1400,151);pred=response(d,f);t,r=wave_oracle(d,f)
        error=float(max(np.max(abs(pred['amplitude_t']-t)),np.max(abs(pred['amplitude_r']-r))))
        checks.append({'scenario':name,'max_complex_amplitude_error':error,'passed':error<1e-10})
    results['selected_method']=selected
    results['dense_audit']=score(design,dense,weight)
    results['independent_wave_audit']=checks
    results['resonances_hz']=[resonance_hz(c) for c in design['cells']]
    results['limitations']=['Assumed losses and end corrections require measured calibration.',
        'Seven correlated perturbation samples do not certify robustness.',
        'No airflow resistance, nonlinear sound, flexible walls or microphone/room model.',
        'This is one constructed task with one seed; no AI superiority or benchmark win.',
        'Transmission loss under matched terminations is not measured room or rig insertion loss.']
    (out/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    (out/'selected-design.json').write_text(json.dumps(design,indent=2),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,5))
    for key,label in [('naive','Untuned reference'),('numerical','Numerical baseline'),('meta_seeded','Meta seed + numerical sizing')]:
        if key in results:ax.plot(dense,response(results[key]['design'],dense)['transmission_loss_db'],label=label)
    ax.set(xlabel='Frequency (Hz)',ylabel='Predicted transmission loss (dB)',ylim=(0,55),
           title='Acoustic Foundry · Development simulation · No physical measurements')
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'response.png',dpi=160);plt.close(fig)
    print(json.dumps({'directory':str(out),'selected':selected,'score':results['dense_audit'],
                       'audit_passed':all(x['passed'] for x in checks)},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--live',action='store_true')
    args=parser.parse_args();run(args.output,args.live)
