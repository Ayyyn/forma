"""Validate one public contract from native calls, JSON, or observed atem XML.

This adapter interprets data only: no expressions, code execution or XML entities.
"""
import json
import re
import xml.etree.ElementTree as ET
from .contracts import Proposal


def decode(message):
    calls=message.get('tool_calls') or []
    if calls:
        if len(calls)!=1 or calls[0]['function']['name']!='submit_suite':raise ValueError('Expected exactly one submit_suite call')
        return Proposal.model_validate_json(calls[0]['function']['arguments']),'native_tool'
    text=(message.get('content') or '').strip()
    if text.startswith('{'):return Proposal.model_validate_json(text),'json_text'
    if not text.startswith('<atem:function_calls>') or '<!' in text:raise ValueError('No supported contract envelope')
    text=re.sub(r'(<\/?)atem:',r'\1',text)
    root=ET.fromstring(text)
    if root.tag!='function_calls' or len(root)!=1:raise ValueError('Expected one invocation')
    invoke=root[0]
    if invoke.tag!='invoke' or invoke.attrib!={'name':'submit_suite'}:raise ValueError('Unsupported invocation')
    fields={}
    for element in invoke:
        if element.tag!='parameter' or len(element) or set(element.attrib)!={'name'}:raise ValueError('Malformed parameter')
        name=element.attrib['name']
        if name not in Proposal.model_fields or name in fields:raise ValueError('Unknown or duplicate parameter')
        value=element.text or ''
        fields[name]=json.loads(value) if name=='tests' else value
    return Proposal.model_validate(fields),'atem_xml_text'
