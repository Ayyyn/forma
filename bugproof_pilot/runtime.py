import json
import os
from pathlib import Path
import subprocess
import sys
from .contracts import Contract,check

ROOT=Path(__file__).resolve().parents[1]


def execute(case,variant,tests):
    tests=[Contract.model_validate(x).model_dump() for x in tests]
    for t in tests:
        p=t['parameters']
        if len(json.dumps(p))>8000:raise ValueError('Contract inputs too large')
        for key in ['method_bytes_hex','body_bytes_hex']:
            if p[key] is not None:bytes.fromhex(p[key])
    job={'source':str(ROOT/'research/bugproof/vendor'/case['instance_id']/variant),
         'dependencies':str(ROOT/'research/bugproof/runtime-deps'),
         'library':'flask' if case['repo']=='pallets/flask' else 'requests','tests':tests}
    # Explicit whitelist: no API keys, tokens, user profile or inherited PYTHONPATH.
    env={k:os.environ[k] for k in ['SystemRoot','WINDIR','PATH','TEMP','TMP'] if k in os.environ}
    result=subprocess.run([sys.executable,'-I',str(ROOT/'bugproof_pilot/worker.py')],input=json.dumps(job),
          text=True,encoding='utf-8',capture_output=True,env=env,cwd=ROOT/'research/bugproof',timeout=15)
    if result.returncode:return {'runtime_error':result.stderr[-2000:],'returncode':result.returncode}
    output=json.loads(result.stdout)
    output['passed']=[check(facts,Contract.model_validate(t).assertion) for t,facts in zip(tests,output['results'])]
    return output


def verify(case,tests):
    a=execute(case,'buggy',tests);b=execute(case,'fixed',tests)
    verified=bool(tests and 'passed' in a and 'passed' in b and all(b['passed']) and not all(a['passed']))
    return {'verified':verified,'buggy':a,'fixed':b,'test_count':len(tests),
            'note':'Offline unit-level before/after regression proof, not a live server or full upstream suite.'}
