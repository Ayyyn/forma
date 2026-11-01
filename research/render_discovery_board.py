"""Render our trusted local project board with user-requested downloads enabled."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
fragment=Path('C:/Users/LENOVO/.codex/visualizations/2026/10/27/01a17d16-9e76-7400-b87a-08dd7c219596/nonlinear-discovery-board.html')
renderer=Path('C:/Users/LENOVO/.codex/plugins/cache/openai-bundled/visualize/1.0.55/skills/visualize/scripts/render.py')
destination=ROOT/'output/discovery-board/index.html'
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
