"""Render our trusted local project board with user-requested downloads enabled."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Render a local board using a trusted, separately installed visualization wrapper.')
parser.add_argument('--fragment',type=Path,default=ROOT/'output/discovery-board/fragment.html')
parser.add_argument('--renderer',type=Path,required=True,help='Path to the trusted wrapper render.py')
args=parser.parse_args()
fragment=args.fragment.resolve()
renderer=args.renderer.resolve()
for path in (fragment,renderer):
    if not path.is_file():parser.error('Required local file does not exist: '+str(path))
destination=ROOT/'output/discovery-board/index.html'
destination.parent.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,str(renderer),str(fragment),str(destination),'--force'],check=True)
text=destination.read_text(encoding='utf-8')
needle='sandbox="allow-scripts"'
if text.count(needle)!=1:raise ValueError('Unexpected wrapper; inspect before enabling downloads')
assets={}
for manifest in (ROOT/'output/discovery-board/exports').glob('*/manifest.json'):
    data=json.loads(manifest.read_text())
    if data.get('geometry_checks_passed'):
        for fmt in ['step','stl','obj']:
            path=manifest.parent/(fmt+'-bundle.zip')
            if path.is_file():assets[path.relative_to(destination.parent).as_posix()]=manifest.parent.name+'-'+fmt+'.zip'
bridge='''<p id="cad-download-status" role="status"></p><script>
(() => { const permitted=ASSETS;
window.addEventListener('message',event=>{
 const frame=document.getElementById('codex-visualization');
 if(event.source!==frame.contentWindow||event.data?.type!=='verified-cad-download')return;
 const asset=event.data.asset;if(!Object.prototype.hasOwnProperty.call(permitted,asset))return;
 const link=document.createElement('a');link.href=asset;link.download=permitted[asset];document.body.append(link);link.click();link.remove();
 document.getElementById('cad-download-status').textContent='Download requested: '+permitted[asset];
});})();</script>'''.replace('ASSETS',json.dumps(assets))
text=text.replace(needle,'sandbox="allow-scripts allow-downloads"')
destination.write_text(text.replace('</body>',bridge+'</body>'),encoding='utf-8')
print('Local board uses an explicit verified-asset download allowlist; iframe origin isolation retained.')
