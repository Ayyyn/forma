"""Pinned browser renderer from npm's public CDN; no user data or credentials."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'mechanical_workbench/web/vendor';folder.mkdir(parents=True,exist_ok=True)
files={'three.module.js':'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js','OrbitControls.js':'https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/OrbitControls.js','THREE-LICENSE.txt':'https://cdn.jsdelivr.net/npm/three@0.170.0/LICENSE'};receipts={}
for name,url in files.items():
    path=folder/name
    if path.exists():data=path.read_bytes()
    else:
        with urllib.request.urlopen(url,timeout=45) as response:data=response.read(3000000)
        path.write_bytes(data)
    receipts[name]={'url':url,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
(folder/'receipt.json').write_text(json.dumps(receipts,indent=2));print(json.dumps(receipts,indent=2))
