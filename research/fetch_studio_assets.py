"""Pinned Three.js editing control, matching the existing local renderer."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'crate_studio/web/vendor'
url='https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/TransformControls.js'
with urllib.request.urlopen(url,timeout=45) as response:data=response.read(500000)
if not data.startswith(b'import ') or b'class TransformControls' not in data:raise ValueError('Unexpected control source')
path=folder/'TransformControls.js';path.write_bytes(data)
(folder/'studio-receipt.json').write_text(json.dumps({'TransformControls.js':{'url':url,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'license':'MIT; see THREE-LICENSE.txt'}},indent=2),encoding='utf-8')
print(json.dumps({'downloaded':path.name,'bytes':len(data)}))
