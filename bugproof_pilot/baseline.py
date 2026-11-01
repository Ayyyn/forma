"""Literal report-to-contract extraction; no gold patches or model inference."""
import ast
import re


def literal_suite(issue,library):
    """Conservative rule baseline: retain explicit examples and explicit oracles.

    This is a limited comparator, NOT a state-of-the-art test-generation system.
    """
    tests=[]
    if library=='flask':
        if re.search(r'empty name',issue,re.I) and 'ValueError' in issue:
            tests.append({'action':'blueprint','parameters':{'name':''},'assertion':{'kind':'raises','value':'ValueError'}})
        return tests
    url_examples=re.findall(r'https?://[^\s`<>\)"\']+',issue)
    expected=issue.split('## Expected Result',1)[-1].split('## Actual Result',1)[0] if '## Expected Result' in issue else ''
    exception=re.search(r'\b([A-Z][A-Za-z]+(?:Error|URL|Url))\s*:',expected)
    if exception:
        name=exception[1].replace('InvalidUrl','InvalidURL')
        if url_examples:tests.append({'action':'request','parameters':{'url':url_examples[0]},'assertion':{'kind':'raises','value':name}})
    # Explicit session.header=None example plus explicit "not send" statement.
    null_header=re.search(r"headers\[['\"]([^'\"]+)['\"]\]\s*=\s*None",issue)
    if null_header and re.search(r'(not send|prevent sending)',issue,re.I):
        tests.append({'action':'request','parameters':{'session_headers':{null_header[1]:None}},'assertion':{'kind':'header_absent','value':null_header[1]}})
    # Extract explicit method/body calls; absence of an expected oracle stays a
    # no-crash test. No conversion of an observed buggy value into an expectation.
    for block in re.findall(r'```(?:python\d*|python)?\s*\n?(.*?)```',issue,re.S):
        try:tree=ast.parse(block)
        except SyntaxError:continue
        for call in ast.walk(tree):
            if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute):continue
            method=call.func.attr
            if method not in ['get','post','put','head','request']:continue
            params={'method':method.upper() if method!='request' else 'GET'}
            if call.args and isinstance(call.args[0],ast.Constant) and isinstance(call.args[0].value,str):params['url']=call.args[0].value
            for kw in call.keywords:
                if kw.arg=='method' and isinstance(kw.value,ast.Constant):
                    if isinstance(kw.value.value,bytes):params['method_bytes_hex']=kw.value.value.hex()
                    elif isinstance(kw.value.value,str):params['method']=kw.value.value
                if kw.arg=='data' and isinstance(kw.value,ast.Call) and isinstance(kw.value.func,ast.Attribute) and kw.value.func.attr=='encode':
                    x=kw.value.func.value
                    if isinstance(x,ast.Constant) and isinstance(x.value,str):params['body_bytes_hex']=x.value.encode('utf-8').hex()
            tests.append({'action':'request','parameters':params,'assertion':{'kind':'returns'}})
    return tests[:4]
