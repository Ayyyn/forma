"""One separate fresh-code probe; no historical pilot outcomes are replaced."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.api_preflight import load_env,request
from bugproof_pilot_v2.adapter import decode as buggy
from bugproof_review.adapter import decode as corrected

OUTPUT=ROOT/'research/bugproof/fresh-parser-probe.json'


class Test(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message:dict
    expected:Literal['returns','ValueError']


class Suite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    tests:list[Test]=Field(min_length=2,max_length=4)
    public_explanation:str


ISSUE='''Fresh local defect, first independently reproduced during this pilot, not an upstream benchmark instance: Our runner catches ValueError when an invalid model response should be rejected. The public decode(message) API should return a validated proposal/envelope for valid messages, and raise ValueError (including subclasses) for malformed contract envelopes. An unescaped ampersand in an atem parameter instead escapes as xml.etree.ElementTree.ParseError, which is not a ValueError, and can abort the batch. Please produce a minimal regression case and a valid-input control. Do not execute code or claim a run. The hidden evaluator will check your JSON message inputs on the original implementation, a separately written correction and an overbroad correction that rejects every message. Allowed expected values are returns and ValueError; they are public intended behavior, not observations. Use JSON input data only; no Python test code.'''


def evaluate(suite):
    def all_reject(message):raise ValueError('Overbroad negative-control mutant')
    versions={}
    for name,function in [('original',buggy),('corrected',corrected),('overbroad_mutant',all_reject)]:
        facts=[]
        for test in suite.tests:
            try:
                function(test.message);observed='returns';passed=test.expected=='returns'
            except Exception as error:
                observed=type(error).__name__;passed=test.expected=='ValueError' and isinstance(error,ValueError)
            facts.append({'observed':observed,'expected':test.expected,'passed':passed})
        versions[name]=facts
    ok=(all(x['passed'] for x in versions['corrected']) and not all(x['passed'] for x in versions['original'])
        and not all(x['passed'] for x in versions['overbroad_mutant']) and {t.expected for t in suite.tests}=={'returns','ValueError'})
    return {'verified':ok,'versions':versions,'note':'One fresh assisted case, not a statistical benchmark; the agent wrote message/assertion data, not the correction.'}


def main(replay=False):
    if replay:
        saved=json.loads(OUTPUT.read_text(encoding='utf-8'));suite=Suite.model_validate(saved['suite'])
        result=evaluate(suite)
        if result!=saved['evaluation']:raise AssertionError('Fresh example does not replay')
        print(json.dumps(result,indent=2));return
    if OUTPUT.exists():raise ValueError('Probe already saved; use --replay, never replace it')
    source=(ROOT/'bugproof_pilot_v2/adapter.py').read_text(encoding='utf-8')
    contracts=(ROOT/'bugproof_pilot_v2/contracts.py').read_text(encoding='utf-8').split('SDK=',1)[0]
    payload={'model':'meta-models/muse-spark-open-1026','messages':[
        {'role':'system','content':'You design executable regression inputs from a bug report and code. Return exactly one JSON object conforming to the provided schema, without markdown, XML function calls or tools. No confidence score or execution claim. Never weaken the specified expected behavior.'},
        {'role':'user','content':ISSUE+'\nIMPLEMENTATION\n'+source+'\nMODELS\n'+contracts}],
        'response_format':{'type':'json_schema','json_schema':{'name':'fresh_parser_suite','strict':True,'schema':Suite.model_json_schema()}},
        'reasoning_effort':'medium','temperature':.2,'seed':617,'max_tokens':8192}
    load_env();transport,response=request('https://inference.baseten.co/v1',os.environ['BASETEN_API_KEY'],'/chat/completions',payload,timeout=180)
    saved={'purpose':'Separately labeled fresh project-code capability probe; never pooled with v1/v2 scores.',
        'issue':ISSUE,'request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['bugproof_pilot_v2/adapter.py','bugproof_pilot_v2/contracts.py','bugproof_review/adapter.py','scripts/probe_fresh_parser_bug.py']},
        'transport':transport,'response_id':response.get('id') if response else None,'response_model':response.get('model') if response else None}
    if response:
        choice=response['choices'][0];saved['public_response_text']=choice['message'].get('content');saved['finish_reason']=choice.get('finish_reason')
        try:
            suite=Suite.model_validate_json(saved['public_response_text']);saved['suite']=suite.model_dump();saved['evaluation']=evaluate(suite)
        except (ValueError,TypeError) as error:saved['rejected_output']=str(error)[:600]
    OUTPUT.write_text(json.dumps(saved,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in saved.items() if k not in ['public_response_text','issue','source_sha256']},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--replay',action='store_true');args=parser.parse_args();main(args.replay)
