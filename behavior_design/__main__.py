import argparse
import uvicorn
p=argparse.ArgumentParser();p.add_argument('command',choices=['serve']);p.add_argument('--port',type=int,default=8780);a=p.parse_args();uvicorn.run('behavior_design.server:app',host='127.0.0.1',port=a.port)
