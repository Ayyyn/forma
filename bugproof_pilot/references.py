"""Evaluator-only unit adaptations of the upstream gold regression tests."""
GOLD={
 'pallets__flask-5014':[{'action':'blueprint','parameters':{'name':''},'assertion':{'kind':'raises','value':'ValueError'}}],
 'psf__requests-1142':[{'action':'request','parameters':{'method':m},'assertion':{'kind':'header_absent','value':'Content-Length'}} for m in ['GET','HEAD']],
 'psf__requests-1766':[{'action':'digest_header','assertion':{'kind':'contains','field':'authorization','value':'qop="auth"'}}],
 'psf__requests-1921':[{'action':'request','parameters':{'session_headers':{'Accept-Encoding':None}},'assertion':{'kind':'header_absent','value':'Accept-Encoding'}}],
 'psf__requests-2317':[{'action':'request','parameters':{'method_bytes_hex':'474554'},'assertion':{'kind':'equals','field':'method','value':'GET'}}],
 'psf__requests-2931':[{'action':'request','parameters':{'method':'PUT','body_bytes_hex':'c3a9'},'assertion':{'kind':'equals','field':'body_type','value':'bytes'}}],
 'psf__requests-5414':[{'action':'request','parameters':{'url':'http://.example.com'},'assertion':{'kind':'raises','value':'InvalidURL'}}],
 'psf__requests-6028':[{'action':'prepend_scheme','parameters':{'url':'http://user:pass@example.com/path?query'},'assertion':{'kind':'equals','field':'value','value':'http://user:pass@example.com/path?query'}}],
}
