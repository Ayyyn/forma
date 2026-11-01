"""Keyless isolated child: execute only four allowlisted upstream API operations."""
import collections
import collections.abc
import json
from pathlib import Path
import socket
import sys
import warnings


def main():
    job=json.load(sys.stdin);root=Path(job['source']).resolve()
    dependencies=Path(job['dependencies']).resolve()
    sys.path.insert(0,str(dependencies))
    sys.path.insert(0,str(root/'src' if (root/'src').exists() else root))
    # Python 3.12 compatibility only: restore moved collection ABC import aliases.
    # No library bug logic or published fix is changed by this shared shim.
    for name in ['Callable','Mapping','MutableMapping','MutableSet','Sequence']:
        if not hasattr(collections,name):setattr(collections,name,getattr(collections.abc,name))
    warnings.simplefilter('ignore')
    if job['library']=='requests':
        import requests as library
    else:
        import flask as library
    if not Path(library.__file__).resolve().is_relative_to(root):raise RuntimeError('Installed-library fallback forbidden')
    def deny(*args,**kwargs):raise RuntimeError('Network disabled in regression fixture')
    socket.socket=deny;socket.create_connection=deny
    results=[]
    for test in job['tests']:
        p=test['parameters'];action=test['action']
        try:
            if action=='request' and job['library']=='requests':
                session=library.Session();session.trust_env=False;session.headers.update(p['session_headers'])
                def record(request,**kwargs):
                    response=library.Response();response.status_code=200;response.request=request
                    response.url=request.url;response._content=b''
                    return response
                session.send=record
                method=bytes.fromhex(p['method_bytes_hex']) if p['method_bytes_hex'] is not None else p['method']
                body=bytes.fromhex(p['body_bytes_hex']) if p['body_bytes_hex'] is not None else p['body_text']
                r=session.request(method,p['url'],data=body,headers=p['headers']).request
                facts={'method':r.method,'url':r.url,'body_type':type(r.body).__name__,
                       'body_hex':r.body.hex() if isinstance(r.body,bytes) else None,'headers':dict(r.headers)}
            elif action=='digest_header' and job['library']=='requests':
                library.auth.os.urandom=lambda n:b'\x11'*n
                library.auth.time.ctime=lambda *args:'Wed Oct 28 00:00:00 2026'
                auth=library.auth.HTTPDigestAuth(p['username'],p['password'])
                challenge={'realm':p['realm'],'nonce':p['nonce'],'qop':p['qop']}
                if hasattr(auth,'init_per_thread_state'):
                    auth.init_per_thread_state();auth._thread_local.chal=challenge
                else:auth.chal=challenge
                facts={'authorization':auth.build_digest_header('GET',p['url'])}
            elif action=='prepend_scheme' and job['library']=='requests':facts={'value':library.utils.prepend_scheme_if_needed(p['url'],p['scheme'])}
            elif action=='blueprint' and job['library']=='flask':facts={'blueprint_name':library.Blueprint(p['name'],'flask').name}
            else:raise ValueError('Action unavailable for this library')
            # Values are serialized rather than allowing model-provided expressions.
            results.append(facts)
        except Exception as error:results.append({'exception':type(error).__name__,'message':str(error)[:400]})
    print(json.dumps({'library_version':library.__version__,'library_origin':str(Path(library.__file__).resolve()),'results':results}),flush=True)


if __name__=='__main__':main()
