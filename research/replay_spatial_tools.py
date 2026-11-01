"""Replay previously received tool arguments after a rendering cache fix.

No model endpoint is contacted. Provider records remain in the original archive.
This checks mechanical/action equivalence, not what a model would say anew.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from spatial_actuator.agent import handle
from spatial_actuator.laboratory import Lab,source_manifest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--original',type=Path,default=Path('artifacts/spatial-actuator-step1'));parser.add_argument('--current',type=Path,default=Path('artifacts/spatial-actuator-step1-v2'));args=parser.parse_args()
    original=args.original.resolve();current=args.current.resolve();frozen=json.loads((current/'manifest.json').read_text())
    if frozen['source_hashes']!=source_manifest():raise ValueError('Current source differs from frozen snapshot')
    received=json.loads((original/'meta-probe.json').read_text());t=json.loads((original/'manifest.json').read_text())['task'];lab=Lab(t)
    directory=current/'offline-received-tool-replay';directory.mkdir(exist_ok=False);commands=0;rendered=0
    for event in received['events']:
        for call in event['assistant']['tool_calls']:
            result,image=handle(lab,call['function']['name'],json.loads(call['function']['arguments']),directory);commands+=1;rendered+=bool(image)
    if lab.records!=received['records']:raise ValueError('Tool replay changed saved candidates')
    if lab.best!=received['state']['best_evaluated']:raise ValueError('Tool replay changed selected candidate')
    result={'mode':'offline replay of received commands, no new model responses','actual_api_calls_this_replay':0,
            'original_paid_receipt_file':str(original/'meta-probe.json'),'original_file_sha256':hashlib.sha256((original/'meta-probe.json').read_bytes()).hexdigest(),
            'source_hashes':source_manifest(),'commands_replayed':commands,'views_rendered_without_reassembly':rendered,
            'all_candidate_records_identical':True,'state':lab.state(),'independent_best_check':lab.verify(),
            'original_extra_online_rendering_assemblies':1,'original_new_candidate_assemblies':received['state']['actual_assemblies'],
            'original_total_search_and_inspection_assemblies':received['state']['actual_assemblies']+1,
            'note':'Original inspection recomputed an identical solution despite a tool description promising none. Candidate identities/physics were unaffected; that extra assembly is explicitly added here. Current rendering consumes the cached solution. Original source/results remain unchanged.'}
    (current/'received-tool-replay.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['state','source_hashes']},indent=2))


if __name__=='__main__':main()
