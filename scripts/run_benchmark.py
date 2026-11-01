"""Freeze or execute the controlled benchmark; resume skips existing immutable cells."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from continuum.benchmark import ROOT, freeze_manifest, source_hashes, run_cell


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--workers',type=int,choices=[1,2,3],default=3)
    parser.add_argument('--manifest',type=Path,default=ROOT/'benchmarks/protocol-v5.json')
    args=parser.parse_args()
    if args.freeze:
        if args.manifest.exists():raise SystemExit('Manifest already exists; preserve it and choose a new filename for a new protocol.')
        manifest=freeze_manifest(args.manifest)
        print('FROZEN',args.manifest,hashlib.sha256(args.manifest.read_bytes()).hexdigest(),flush=True)
        print('Task feasibility witnesses:',[(t['id'],t['expected_feasible']) for t in manifest['tasks']],flush=True)
    if not args.run:return
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    if manifest['source_sha256']!=source_hashes():raise SystemExit('Frozen source hash differs. Do not silently mix protocol versions.')
    manifest_hash=hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    output=args.manifest.parent/f"runs-v{manifest['protocol_version']}";output.mkdir(exist_ok=True)
    jobs=[(task,seed,method) for task in manifest['tasks'] for seed in manifest['seeds'] for method in manifest['methods']]
    def work(job):
        task,seed,method=job
        path=output/f"{task['id']}--{seed}--{method}.json"
        if path.exists():return 'EXISTS '+path.name
        try:
            result=run_cell(task,seed,method)
            result['manifest_sha256']=manifest_hash
            path.write_text(json.dumps(result,indent=2),encoding='utf-8')
            quality=result['best']['metrics']['crease_segments'] if result['success'] else None
            return f"{task['id']} seed={seed} {method}: success={result['success']} attempts={result['attempts_used']}/64 best_creases={quality} complete={result['completed']}"
        except Exception as error:
            failure={'task_id':task['id'],'seed':seed,'method':method,'manifest_sha256':manifest_hash,'harness_error':str(error),'traceback':traceback.format_exc()}
            path.write_text(json.dumps(failure,indent=2),encoding='utf-8')
            return 'HARNESS ERROR '+path.name+': '+str(error)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for future in as_completed([executor.submit(work,job) for job in jobs]):print(future.result(),flush=True)
    print('Finished. Cell files:',len(list(output.glob('*.json'))),flush=True)

if __name__=='__main__':main()
