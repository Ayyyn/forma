from typing import Literal
from pydantic import BaseModel,ConfigDict,Field


class Assertion(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['equals','contains','header_absent','header_equals','raises','returns']
    field:Literal['method','url','body_type','body_hex','value','authorization','blueprint_name']='value'
    header:str=''
    value:str=''


class Parameters(BaseModel):
    model_config=ConfigDict(extra='forbid')
    method:str='GET'
    method_bytes_hex:str|None=None
    url:str='http://example.com/'
    body_text:str|None=None
    body_bytes_hex:str|None=None
    session_headers:dict[str,str|None]=Field(default_factory=dict)
    headers:dict[str,str|None]=Field(default_factory=dict)
    scheme:str='http'
    username:str='user'
    password:str='pass'
    realm:str='test-realm'
    nonce:str='test-nonce'
    qop:str='auth'
    name:str='example'


class Contract(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['request','digest_header','prepend_scheme','blueprint']
    parameters:Parameters=Field(default_factory=Parameters)
    assertion:Assertion


class Proposal(BaseModel):
    model_config=ConfigDict(extra='forbid')
    status:Literal['suite','need_information']
    evidence_quote:str=''
    question:str=''
    tests:list[Contract]=Field(default_factory=list,max_length=4)


def check(facts,assertion):
    if assertion.kind=='raises':return facts.get('exception')==assertion.value
    if facts.get('exception'):return False
    if assertion.kind=='returns':return True
    if assertion.kind=='header_absent':return assertion.value.lower() not in {k.lower() for k in facts.get('headers',{})}
    if assertion.kind=='header_equals':
        headers={k.lower():v for k,v in facts.get('headers',{}).items()}
        return assertion.header.lower() in headers and headers[assertion.header.lower()]==assertion.value
    value=facts.get(assertion.field)
    if assertion.kind=='contains':return isinstance(value,str) and assertion.value in value
    return value==assertion.value


SDK='''You can propose up to FOUR independent executable test contracts. No Python code is accepted.
Actions:
request: constructs a Session, applies session_headers, and calls Session.request(method,url,data,headers) with transport replaced by a recorder returning the PreparedRequest. It performs REAL upstream request preparation but NEVER sends a network request. It reports method, url, body_type (bytes/str/NoneType/etc), body_hex (for bytes), and headers. Use method_bytes_hex or body_bytes_hex for literal binary values; body_text for a Unicode string. For example 504f5354 encodes ASCII POST. Session environment proxies are disabled.
digest_header: constructs upstream HTTPDigestAuth with username/password, applies realm/nonce/qop challenge, builds GET Authorization header for url, reports authorization. Random nonce/digest fields are not stable; assert only the property named by the report.
prepend_scheme: calls upstream requests.utils.prepend_scheme_if_needed(url,scheme), reports value. This helper adds a missing scheme while retaining existing URL components.
blueprint: calls upstream Flask Blueprint(name,'flask'), reports blueprint_name or exception. Supported only for Flask cases.
Assertions: equals/contains check one of the listed string fields against value; header_absent checks absence of the header named in value; header_equals compares the header named in the separate header property against string value, case-insensitive in header name; raises checks EXACT exception class name; returns checks only normal completion. There is NO field called headers or status_code. The value field exists ONLY for prepend_scheme output. For normal request controls use returns, a method/url/body assertion, or header_equals; never use contains on value to inspect request headers. Exceptions are reported as class names. A test must assert the CORRECT intended behavior, so a regression proof is a test that passes fixed code and fails buggy code. Never assert the buggy result simply to obtain a green test. Do not assert HTTP server statuses: no server is called. Use only actions for the provided library. Tests must exercise the reported issue rather than a different defect. If the issue is too incomplete to state a supported expected behavior, return need_information with a precise question. Quote one exact relevant substring of the issue as evidence. The runtime, two-version checks and empty-suite rejection decide verification; your confidence or prose does not.'''
