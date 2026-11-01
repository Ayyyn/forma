"""Replay frozen pilot scores without API calls; tolerate checkout relocation."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(version):
    module='bugproof_pilot' if version==1 else 'bugproof_pilot_v2'
    directory=ROOT/f'benchmarks/bugproof-pilot-v{version}'
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    for path,expected in manifest['source_sha256'].items():
        if hashlib.sha256((ROOT/path.replace('\\','/')).read_bytes()).hexdigest()!=expected:raise AssertionError('Frozen source drift: '+path)
    runtime=importlib.import_module(module+'.runtime');api=importlib.import_module(module+'.__main__')
    cases={c['instance_id']:c for c in manifest['cases']};files={};executed=0;compared=0
    for case in manifest['cases']:
        for relative,variants in case.get('changed_files',{}).items():
            for variant,expected in variants.items():
                p=ROOT/'research/bugproof/vendor'/case['instance_id']/variant/relative
                if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise AssertionError('Fixture drift: '+str(p))
        for method in manifest['methods']:
            for seed in manifest['seeds']:
                p=directory/'runs'/f"{method}-{case['instance_id']}-{seed}.json";raw=p.read_bytes();r=json.loads(raw)
                files[p.name]=hashlib.sha256(raw).hexdigest()
                if method=='meta':
                    digest=hashlib.sha256(json.dumps(api.payload(case,seed),sort_keys=True).encode()).hexdigest()
                    if digest!=r['request_sha256']:raise AssertionError('Request drift')
                    if version==2 and r.get('proposal'):
                        adapter=importlib.import_module(module+'.adapter')
                        decoded,_=adapter.decode({'content':r.get('public_response_text'),'tool_calls':r.get('public_tool_calls')})
                        if decoded.model_dump()!=r['proposal']:raise AssertionError('Recorded output does not decode identically')
                if r.get('execution'):
                    actual=runtime.verify(case,r['proposal']['tests']);saved=r['execution']
                    if actual['verified']!=saved['verified']:raise AssertionError('Proof verdict changed')
                    for variant in ['buggy','fixed']:
                        if actual[variant].get('passed')!=saved[variant].get('passed'):raise AssertionError('Assertion outcomes changed')
                        for old,new in zip(saved[variant].get('results',[]),actual[variant].get('results',[])):
                            # General API facts should match; the default User-Agent
                            # includes OS/Python information and is not an oracle.
                            old=json.loads(json.dumps(old));new=json.loads(json.dumps(new))
                            for x in [old,new]:
                                if 'headers' in x:x['headers'].pop('User-Agent',None)
                            if old!=new:raise AssertionError('Observed API facts changed')
                    executed+=1
                if r['verified']!=bool(r.get('execution',{}).get('verified')):raise AssertionError('Unexecuted proof')
                compared+=1
    result={'passed':True,'version':version,'cells_checked':compared,'execution_cells_replayed':executed,
        'source_hashes_verified':len(manifest['source_sha256']),'manifest_sha256':hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(),
        'audit_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'raw_cell_sha256':files,
        'note':'No model API calls. Recorded assertions and API facts replay; checkout paths and default User-Agent are not compared.'}
    (directory/'replay-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='raw_cell_sha256'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--version',type=int,choices=[1,2],default=2);args=p.parse_args();main(args.version)
