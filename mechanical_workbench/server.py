"""Local workbench API; no files outside the new app/output are served."""
from copy import deepcopy
from functools import lru_cache
import json,re,threading,uuid
from pathlib import Path
from typing import Literal
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,ConfigDict,Field
from .physics import development_scenario,imported_scenario,evaluate
from .runs import RUNS,ROOT,run,list_runs,public_scenario

app=FastAPI(title='Mechanical Investigation Workbench');WEB=Path(__file__).parent/'web';gate=threading.Lock();pending={};custom_project=None
@lru_cache(maxsize=1)
def default_project():return development_scenario()
def project():return custom_project if custom_project is not None else default_project()
def valid_id(value):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',value):raise HTTPException(404,'Unknown run')
    return value

class RunRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    policy:Literal['meta','numerical']='numerical'
    project_spec:dict|None=None
class ImportRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    design:dict
    load_cases:list
    requirements:dict
class ExploreRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    E_N_mm2:float=Field(ge=300,le=10000)
    radius_mm:float=Field(ge=.15,le=.8)
    design:dict|None=None
    load_cases:list|None=None
    requirements:dict|None=None
    parent_id:str='reference'

@app.get('/api/project')
def get_project():return public_scenario(project())
@app.post('/api/project')
def import_project(body:ImportRequest):
    global custom_project
    if gate.locked():raise HTTPException(409,'Wait for the active investigation before importing another graph')
    try:custom_project=imported_scenario(body.design,body.load_cases,body.requirements);return public_scenario(custom_project)
    except (ValueError,KeyError,TypeError) as error:raise HTTPException(422,str(error))
@app.post('/api/explore')
def explore(body:ExploreRequest):
    d=deepcopy(body.design or project()['design']);d['E_N_mm2']=body.E_N_mm2;d['radii_mm']=[body.radius_mm]*len(d['edges'])
    try:result=evaluate(d,body.load_cases or project()['cases'],body.requirements or project()['requirements'])
    except (ValueError,KeyError,TypeError) as error:raise HTTPException(422,str(error))
    identifier='manual-'+uuid.uuid4().hex[:12];folder=ROOT/'output/mechanical-workbench/explorations';folder.mkdir(parents=True,exist_ok=True)
    record={'id':identifier,'parent':body.parent_id,'immutable':True,'source':'manual nominal prediction, not calibrated acceptance','result':result};(folder/(identifier+'.json')).write_text(json.dumps(record));return record
@app.get('/api/runs')
def get_runs():return list_runs()
@app.post('/api/runs',status_code=202)
def start_run(body:RunRequest):
    if not gate.acquire(blocking=False):raise HTTPException(409,'One investigation is already running')
    identifier='study-'+uuid.uuid4().hex[:12];pending[identifier]={'id':identifier,'policy':body.policy,'status':'queued'}
    try:
        if body.project_spec:
            supplied=ImportRequest(**body.project_spec);s=imported_scenario(supplied.design,supplied.load_cases,supplied.requirements)
        else:s=deepcopy(project())
    except Exception as error:gate.release();raise HTTPException(422,str(error))
    def work():
        try:run(s,body.policy,run_id=identifier)
        except Exception as error:pending[identifier]={'id':identifier,'status':'failed','error':str(error)}
        finally:gate.release()
    threading.Thread(target=work,daemon=True).start();return pending[identifier]
@app.get('/api/runs/{identifier}')
def get_run(identifier:str):
    directory=RUNS/valid_id(identifier)
    if (directory/'result.json').exists():data=json.loads((directory/'result.json').read_text())
    elif (directory/'status.json').exists():data=json.loads((directory/'status.json').read_text())
    elif identifier in pending:data=dict(pending[identifier])
    else:raise HTTPException(404,'Unknown run')
    path=directory/'timeline.jsonl';data['timeline']=[]
    if path.exists():
        for line in path.read_text().splitlines():
            try:data['timeline'].append(json.loads(line))
            except json.JSONDecodeError:pass # A trailing event may still be writing.
    audit=directory/'external-audit.json'
    if audit.exists():data['external_audit']=json.loads(audit.read_text())
    return data
@app.get('/api/runs/{identifier}/export')
def export_run(identifier:str):
    path=RUNS/valid_id(identifier)/'result.json'
    if not path.exists():raise HTTPException(404,'Completed result not found')
    return FileResponse(path,media_type='application/json',filename=identifier+'.json')
@app.get('/api/coverage')
def coverage():return {'active_adapter':'linear_spatial_frame_v2_direction_envelope','maximum_nodes':90,'maximum_members':300,'maximum_load_cases':8,'directional_envelope':'Displacement only, when three orthogonal equal-norm forces act at one port; other guards check explicit cases.','nonlinear_target_force_response':'not integrated','functional_fabrication':'not validated','physical_measurements':0,'prior_viewer':'http://127.0.0.1:8767/','checkpoint':'checkpoints/2026-10-30-before-mechanical-workbench-v2','Meta_API_budget_per_requested_run_USD_estimated':5}
@app.get('/')
def home():return FileResponse(WEB/'index.html')
app.mount('/assets',StaticFiles(directory=WEB),name='assets')
