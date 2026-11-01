"""Local scientific viewer. Page loads cannot spend credits. Original apps untouched."""
import json,re,uuid
from pathlib import Path
from typing import Literal
import numpy as np
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,ConfigDict,Field
from .model import design,evaluate,independent_audit

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/behavior-design';WEB=Path(__file__).parent/'web';app=FastAPI(title='Nonlinear behavior design')
def study():
    latest=(OUT/'latest-study.txt').read_text().strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',latest):raise ValueError('Invalid study id')
    return OUT/'studies'/latest
@app.get('/api/study')
def report():return json.loads((study()/'report.json').read_text())
@app.get('/api/raw/{run}')
def raw(run:str):
    if not re.fullmatch(r'(initial|compact_revision)-(numerical|single_pass|adaptive)',run):raise HTTPException(404)
    return FileResponse(study()/'runs'/run/'result.json',media_type='application/json',filename=run+'.json')
@app.get('/api/candidate/{run}/{candidate}')
def candidate(run:str,candidate:str):
    if not re.fullmatch(r'(initial|compact_revision)-(numerical|single_pass|adaptive)',run) or not re.fullmatch(r'c[0-9]{3}',candidate):raise HTTPException(404)
    data=json.loads((study()/'runs'/run/'result.json').read_text());r=next((r for r in data['records'] if r['id']==candidate),None)
    if not r:raise HTTPException(404)
    return r
class Manual(BaseModel):
    model_config=ConfigDict(extra='forbid')
    task_id:Literal['initial','compact_revision']
    architecture:str=Field(max_length=60)
    parameters:list[float]=Field(min_length=4,max_length=4)
@app.post('/api/evaluate')
def manual(body:Manual):
    if not np.isfinite(body.parameters).all():raise HTTPException(422,'Finite parameters required')
    task=next(t for t in report()['tasks'] if t['id']==body.task_id)
    try:
        result=evaluate(design(body.architecture,body.parameters),task,np.linspace(0,12,97),True);check=independent_audit(result['design'],result['points']);identifier='manual-'+uuid.uuid4().hex[:12];saved={'id':identifier,'source':'Human manual branch, not a benchmark run. Target values between the17 provided points use linear interpolation; no held-out accuracy claim.','result':result,'independent':check};folder=OUT/'explorations';folder.mkdir(exist_ok=True);(folder/(identifier+'.json')).write_text(json.dumps(saved,indent=2,allow_nan=False));return saved
    except (ValueError,TypeError,KeyError) as e:raise HTTPException(422,str(e))
@app.get('/vendor/{name}')
def vendor(name:str):
    if name not in ['three.module.js','OrbitControls.js','THREE-LICENSE.txt']:raise HTTPException(404)
    return FileResponse(ROOT/'mechanical_workbench/web/vendor'/name)
@app.get('/plot/{name}')
def plot(name:str):
    if name not in ['benchmark.png','mechanics-proof.png']:raise HTTPException(404)
    return FileResponse(study()/name)
app.mount('/assets',StaticFiles(directory=WEB),name='assets')
@app.get('/')
def index():return FileResponse(WEB/'index.html')
