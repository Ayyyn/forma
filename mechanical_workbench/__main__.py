import argparse,json
from .physics import development_scenario
from .runs import run
p=argparse.ArgumentParser();p.add_argument('command',choices=['serve','numerical','meta']);p.add_argument('--port',type=int,default=8770);a=p.parse_args()
if a.command=='serve':
    import uvicorn
    uvicorn.run('mechanical_workbench.server:app',host='127.0.0.1',port=a.port)
else:
    result=run(development_scenario(),a.command,notify=lambda e:print(e['title'],flush=True));print(json.dumps({'id':result['id'],'accepted':result['final']['accepted'],'ledger':result['final']['ledger'],'API':result['API']}))
