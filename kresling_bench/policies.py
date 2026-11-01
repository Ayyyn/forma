"""Policies receive the same prediction catalogue and Bayesian state, not truth."""
import json
import hashlib
import os
import time
import numpy as np
from pydantic import BaseModel,ConfigDict
from scripts.api_preflight import load_env,request
from .inference import information_scores
from .design import QUADRATURE

MODEL='meta-models/muse-spark-open-1026'
SYSTEM='''You select informative virtual mechanics experiments. Your goal is to identify the hidden MECHANICAL Kresling hypothesis as accurately and early as possible within FOUR paired force/torque measurements. The public catalogue and predicted unbiased mean reactions are exact for this closed-world simulation. One UNKNOWN CALIBRATION PROFILE adds a constant F/T offset to ALL measurements in this case. It is fixed through the case and drawn uniformly from the listed profiles. Independent Gaussian observation noise with the supplied standard deviations is then added to each paired measurement. Mechanical hypotheses and calibration profiles have independent uniform priors. The common Bayesian estimator marginalizes calibration to estimate the mechanical model. Joint posterior order is mechanical-major, calibration-minor. You do not estimate the posterior yourself. You can choose any listed experiment, including repeats (new independent noise, same calibration, consumes a slot). Think about separating remaining mechanical hypotheses, nuisance calibration, and future measurements. Choose exactly ONE perform_experiment tool call now. You cannot change hypotheses, estimator, noise, geometry, allowance or observations. Each measured state holds BOTH u and phi; this is not a force-free/torque-free path. Public rationale is optional, short, and is not a score. No real physical experiment is being performed. No external tools or prior-case results are available.'''


class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    experiment_id:str
    public_reason:str=''


def public_catalogue(data):
    return {k:data[k] for k in ['cell','hypotheses','calibration_profiles','experiments','means','noise_std_F_T','measurement_budget','observation_protocol']}


class InformationPolicy:
    def __init__(self):self.cache={}
    def choose(self,lab):
        key=lab.logp.tobytes()
        if key not in self.cache:self.cache[key]=information_scores(lab.logp,lab.means,lab.noise,QUADRATURE,lab.members)
        scores=self.cache[key];index=int(np.argmax(scores))
        return lab.data['experiments'][index]['id'],{'expected_information_nats':scores.tolist(),'quadrature_order':QUADRATURE}


def space_filling(lab):
    # Four corners cover the fixed pose rectangle without observing outcomes.
    index=[0,11,2,9][len(lab.trace)]
    return lab.data['experiments'][index]['id'],{'method':'fixed four-corner coverage; no hidden-case information'}


def build_payload(lab):
    return {'model':MODEL,'messages':[{'role':'system','content':SYSTEM+' The scored objective is mean negative log probability of the true mechanical hypothesis after steps 1, 2, 3 and 4; lower is better.'},
       {'role':'user','content':json.dumps({'catalogue':public_catalogue(lab.data),'state':lab.public_state()},separators=(',',':'))}],
       'tools':[{'type':'function','function':{'name':'perform_experiment','description':'Spend one slot on one listed paired reaction measurement; repeats allowed.','parameters':Selection.model_json_schema()}}],
       'tool_choice':'auto','reasoning_effort':'medium','temperature':.2,'seed':lab.seed,'max_tokens':8192}


def meta_choice(lab):
    load_env();key=os.environ.get('BASETEN_API_KEY')
    if not key:raise RuntimeError('BASETEN_API_KEY not configured')
    payload=build_payload(lab)
    transport,response=request('https://inference.baseten.co/v1',key,'/chat/completions',payload,timeout=180)
    event={'transport':transport,'requested_model':MODEL,'response_id':response.get('id') if response else None,
           'response_model':response.get('model') if response else None,'valid_selection':False,
           'request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()}
    if not response:
        event['error']='Transport failed; no retry or provider fallback'
        return None,event
    try:
        event['finish_reason']=response['choices'][0].get('finish_reason')
        calls=response['choices'][0]['message'].get('tool_calls',[])
        if len(calls)!=1 or calls[0]['function']['name']!='perform_experiment':raise ValueError('Expected one perform_experiment call')
        selected=Selection.model_validate_json(calls[0]['function']['arguments'])
        event.update(valid_selection=True,selection=selected.model_dump())
        return selected.experiment_id,event
    except (ValueError,KeyError,TypeError,IndexError) as exc:
        event['error']='Rejected selection: '+str(exc)[:600]
        return None,event
