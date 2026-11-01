"""Strict normalization of observed provider tool encodings; never executes code.

Accepted forms: native API calls; one ATEM XML invocation block; or, only when
there is a single available tool, its exact JSON argument object. The raw
received assistant output remains in the API ledger. Synthesized invocation IDs
are explicitly local protocol IDs, never claimed to be provider response IDs.
"""
import hashlib
import json
import re
import xml.etree.ElementTree as ET


def strict_json(value):
    def pairs(items):
        out={}
        for key,val in items:
            if key in out:raise ValueError('Duplicate JSON field')
            out[key]=val
        return out
    def constant(value):raise ValueError('Nonfinite JSON value')
    return json.loads(value,object_pairs_hook=pairs,parse_constant=constant)


def normalize(public,allowed,response_id,single_tool=None):
    if public.get('tool_calls'):
        for call in public['tool_calls']:
            if call['function']['name'] not in allowed:raise ValueError('Unknown native tool')
        return public,'native'
    content=public.get('content') or '';invocations=[];encoding=None
    if '<atem:function_calls>' in content:
        blocks=re.findall(r'<atem:function_calls>.*?</atem:function_calls>',content,flags=re.S)
        if len(blocks)!=1 or content.count('<atem:function_calls>')!=1:raise ValueError('Ambiguous XML tool blocks')
        block=blocks[0]
        if '<!' in block or '&' in block or '<?' in block:raise ValueError('XML declarations/entities are forbidden')
        try:root=ET.fromstring(block.replace('<atem:','<').replace('</atem:','</'))
        except ET.ParseError as exc:raise ValueError('Malformed XML tool block') from exc
        if root.tag!='function_calls' or root.attrib:raise ValueError('Invalid tool XML root')
        for child in root:
            if child.tag!='invoke' or set(child.attrib)!={'name'}:raise ValueError('Invalid invocation')
            name=child.attrib['name'];arguments={}
            if name not in allowed:raise ValueError('Unknown XML tool')
            for parameter in child:
                if parameter.tag!='parameter' or set(parameter.attrib)!={'name'} or len(parameter):raise ValueError('Invalid XML parameter')
                key=parameter.attrib['name']
                if key in arguments:raise ValueError('Duplicate XML parameter')
                text=(parameter.text or '').strip()
                try:arguments[key]=strict_json(text)
                except json.JSONDecodeError:arguments[key]=text
            invocations.append((name,arguments))
        encoding='atem_xml'
    elif single_tool:
        text=content.strip()
        fenced=re.findall(r'```(?:json)?\s*(.*?)```',text,flags=re.S)
        if fenced:
            if len(fenced)!=1:raise ValueError('Ambiguous JSON tool objects')
            text=fenced[0].strip()
        if text.startswith('{'):
            obj=strict_json(text)
            if not isinstance(obj,dict) or set(obj)!={'searches'}:raise ValueError('Not an exact single-plan argument object')
            invocations=[(single_tool,obj)];encoding='single_tool_json'
    if not invocations:return public,'no_command'
    calls=[]
    for i,(name,args) in enumerate(invocations):
        digest=hashlib.sha256(f'{response_id}|{i}'.encode()).hexdigest()[:20]
        calls.append({'id':'local-normalized-'+digest,'type':'function',
                      'function':{'name':name,'arguments':json.dumps(args,separators=(',',':'))}})
    return {'role':'assistant','content':None,'tool_calls':calls},encoding
