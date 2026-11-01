"""Real local HTTP and download verification. No model calls."""
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.error
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:8770'

def call(path,data=None,headers=None):
    encoded=None if data is None else json.dumps(data).encode()
    req=urllib.request.Request(BASE+path,data=encoded,headers={'Content-Type':'application/json',**(headers or {})})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:return r.status,r.headers,r.read()
    except urllib.error.HTTPError as e:return e.code,e.headers,e.read()

def run():
    rows=[]
    def check(name,ok,detail=''):
        rows.append({'check':name,'passed':bool(ok),'detail':detail})
        if not ok:raise AssertionError(name+': '+detail)
    status,_,raw=call('/api/bootstrap');b=json.loads(raw);p=b['project'];check('bootstrap',status==200 and p['geometry_verification']['passed'])
    spec={**p['spec'],'thickness_mm':8,'material':'polypropylene'}
    status,_,raw=call('/api/design',{'spec':spec,'requirements':p['requirements']});preview=json.loads(raw)
    check('manual_preview',status==200 and preview['metrics']['capacity_l']==p['metrics']['capacity_l'] and preview['geometry_verification']['passed'])
    status,_,_=call('/api/design',{'spec':{**spec,'inner_width_mm':-1},'requirements':p['requirements']});check('invalid_dimensions_rejected',status==422)
    status,_,_=call('/api/design',{'spec':spec,'requirements':p['requirements'],'execute':'no'});check('extra_input_rejected',status==422)
    status,_,_=call('/api/projects',{'spec':spec,'requirements':p['requirements']},headers={'Origin':'https://unrelated.example'});check('cross_origin_write_rejected',status==403)
    status,_,_=call('/api/projects',{'spec':spec,'requirements':p['requirements'],'source':'meta'});check('manual_source_cannot_claim_meta',status==422)
    status,_,raw=call('/api/projects',{'spec':spec,'requirements':p['requirements'],'parent_id':p['id'],'label':'HTTP export verification','source':'manual'});saved=json.loads(raw);id=saved['id']
    check('save_and_parent',status==200 and saved['parent_id']==p['id'])
    status,_,raw=call('/api/projects/'+id);check('reload_saved_geometry',status==200 and json.loads(raw)['spec']==spec)
    results={}
    for fmt in ['bundle','step','stl','svg','pdf','dxf','csv','source','json']:
        status,headers,data=call(f'/api/projects/{id}/export/{fmt}');check('export_'+fmt,status==200 and len(data)>100)
        results[fmt]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        if fmt=='bundle':
            archive=zipfile.ZipFile(io.BytesIO(data));names=archive.namelist()
            check('bundle_complete',all(name in names for name in ['assembly.step','assembly.stl','spec.json','project.json','design-checks.json','verification.json','parametric_model.py','drawing.pdf','drawing.svg','cut-list.csv','sha256.json']))
            hashes=json.loads(archive.read('sha256.json'));check('bundle_hashes',all(hashlib.sha256(archive.read(name)).hexdigest()==digest for name,digest in hashes.items()))
            check('step_roundtrip_passed',json.loads(archive.read('verification.json'))['step_roundtrip']['passed'])
            # Only newly authored project files belong in this export.
            check('bundle_has_no_credentials',not any(name.startswith('.') or '.env' in name.lower() or 'events.jsonl' in name for name in names))
        if fmt=='pdf':check('pdf_header',data.startswith(b'%PDF'))
        if fmt=='json':check('project_export_requirements',json.loads(data)['requirements']==p['requirements'])
    status,_,_=call('/.env');check('credentials_not_served',status==404)
    status,_,_=call('/api/projects/unknown/export/step');check('unknown_project_not_served',status==404)
    record={'utc':datetime.now(timezone.utc).isoformat(),'checks':rows,'passed':all(r['passed'] for r in rows),'exports':results,'project_id':id,'scope':'Local HTTP and artifact integration; no physical or customer validation'}
    (ROOT/'output/forma/http-verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({'passed':record['passed'],'checks':len(rows),'export_bytes':results},indent=2))

if __name__=='__main__':run()
