"""Verified scientific-direction checkpoint; credentials/runtimes excluded.

Restore into a NEW folder only. This tool never restores over the workspace.
"""
import argparse,hashlib,json,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'checkpoints/2026-10-30-before-mechanical-workbench-v2'

def sha(data):return hashlib.sha256(data).hexdigest()
def sources():
    paths=[]
    for name in ['continuum','web','kresling_proof','kresling_bench','structure_lab','spatial_actuator','spatial_revision','nonlinear_discovery','robust_discovery','fabrication_export','discovery_board','tests','docs','ADR']:
        paths.extend((ROOT/name).rglob('*'))
    for folder in ['benchmarks','artifacts']:
        for path in (ROOT/folder).glob('*'):
            if path.is_dir() and path.name.startswith(('kresling','structure','spatial','nonlinear','robust')):paths.extend(path.rglob('*'))
    for name in ['discovery-board','robust-discovery']:
        paths.extend((ROOT/'output'/name).rglob('*'))
    for pattern in ['*nonlinear*','*robust*','*spatial*','*discovery_board*','*print*','cad-install-receipt.json','checkpoint_direction.py']:
        paths.extend((ROOT/'research').glob(pattern))
    paths.extend((ROOT/'output/print-inputs').glob('*.json'))
    paths.extend(ROOT.glob('requirements*.txt'));paths += [ROOT/'HACKATHON_WORK.md',ROOT/'.gitignore']
    return sorted({p for p in paths if p.is_file() and '__pycache__' not in p.parts and not p.is_relative_to(ROOT/'research/vendor') and not p.name.startswith('.env') and 'bugproof' not in p.name.lower()})

def verify(directory):
    m=json.loads((directory/'manifest.json').read_text());archive=directory/'snapshot.zip'
    if sha(archive.read_bytes())!=m['archive_sha256']:raise ValueError('Archive hash mismatch')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('ZIP CRC failure')
        if set(z.namelist())!=set(m['files']):raise ValueError('Archive members mismatch')
        for name,record in m['files'].items():
            if sha(z.read(name))!=record['sha256']:raise ValueError('Content mismatch: '+name)
    return m

def create(directory):
    directory.mkdir(parents=True,exist_ok=False);records={};paths=sources()
    with zipfile.ZipFile(directory/'snapshot.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in paths:
            name=p.relative_to(ROOT).as_posix();data=p.read_bytes();records[name]={'sha256':sha(data),'bytes':len(data)};archive.writestr(name,data)
    manifest={'name':'Before mechanical design-test workbench','created_utc':datetime.now(timezone.utc).isoformat(),'client_date':'2026-10-30','files':records,'archive_sha256':sha((directory/'snapshot.zip').read_bytes()),'credential_files_included':False,'runtimes_included':False,'scope':'Previous mechanical/origami source, experiments, results, viewer and exports. Unrelated bugproof direction and private credentials are excluded. Original folders remain in place.'}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2));verify(directory)
    # Check that the bytes archived equal the originals, without modifying them.
    if any(sha((ROOT/name).read_bytes())!=r['sha256'] for name,r in records.items()):raise ValueError('Source changed during checkpoint')
    (directory/'RESTORE.md').write_text('''# Preserved direction

Original sources/results and the viewer at port 8767 remain in place.
snapshot.zip contains a second verified copy, with per-file SHA-256 hashes in
manifest.json. No .env credentials or installed Python runtimes are included.

Verify:
python research/checkpoint_direction.py verify

Extract into a new independent folder (existing folders are refused):
python research/checkpoint_direction.py extract --destination restored/previous-direction

Install the pinned requirements in a separate environment when needed. Keep
scientific and CAD runtimes separate. Supply credentials locally only if you
choose to make new paid API calls. Reading/replaying saved results is offline.
''')
    print(json.dumps({'checkpoint':str(directory),'files':len(records),'uncompressed_bytes':sum(r['bytes'] for r in records.values()),'archive_bytes':(directory/'snapshot.zip').stat().st_size,'verified':True,'originals_unchanged':True}))

def extract(directory,destination):
    m=verify(directory);destination=destination.resolve()
    if not destination.is_relative_to(ROOT) or destination==ROOT:raise ValueError('Choose a NEW subfolder inside this workspace')
    if destination.exists():raise ValueError('Destination already exists; refusing overwrite')
    for name in m['files']:
        if not (destination/name).resolve().is_relative_to(destination):raise ValueError('Unsafe archive member')
    destination.mkdir(parents=True)
    with zipfile.ZipFile(directory/'snapshot.zip') as z:z.extractall(destination)
    print(json.dumps({'restored_into_new_folder':str(destination),'files':len(m['files'])}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['create','verify','extract']);p.add_argument('--directory',type=Path,default=DEFAULT);p.add_argument('--destination',type=Path);a=p.parse_args()
    if a.command=='create':create(a.directory.resolve())
    elif a.command=='verify':print(json.dumps({'verified':True,'files':len(verify(a.directory.resolve())['files'])}))
    elif a.destination:extract(a.directory.resolve(),a.destination)
    else:p.error('--destination is required for extract')
