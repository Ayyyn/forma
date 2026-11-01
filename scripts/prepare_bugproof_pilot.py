"""Fetch pinned upstream fixtures; never execute downloaded issue text or tests."""
from pathlib import Path
import hashlib
import io
import json
import re
import shutil
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'research/bugproof'
SELECTED=['pallets__flask-5014','psf__requests-1142','psf__requests-1766',
          'psf__requests-1921','psf__requests-2317','psf__requests-2931','psf__requests-5414','psf__requests-6028']


def apply_verified_patch(root,patch):
    lines=patch.splitlines(keepends=True);index=0;changed=[]
    while index<len(lines):
        if not lines[index].startswith('--- a/'):
            index+=1;continue
        relative=lines[index][6:].strip();target=(root/relative).resolve()
        if not target.is_relative_to(root.resolve()):raise ValueError('Patch escaped fixture')
        old=target.read_text(encoding='utf-8').splitlines(keepends=True);result=[];position=0;index+=2
        while index<len(lines) and not lines[index].startswith('diff --git'):
            if not lines[index].startswith('@@ '):index+=1;continue
            start=int(re.match(r'@@ -(\d+)',lines[index])[1])-1
            result.extend(old[position:start]);position=start;index+=1
            while index<len(lines) and not lines[index].startswith(('@@ ','diff --git')):
                line=lines[index];prefix=line[:1];value=line[1:]
                if prefix in [' ','-']:
                    if old[position]!=value:raise ValueError(f'Patch context mismatch {relative}:{position+1}')
                    position+=1
                if prefix in [' ','+']:result.append(value)
                index+=1
        result.extend(old[position:]);target.write_text(''.join(result),encoding='utf-8',newline='')
        changed.append(relative)
    return changed


def main():
    rows=json.loads((DEST/'candidate-issues.json').read_text(encoding='utf-8'));manifest=[]
    for row in rows:
        if row['instance_id'] not in SELECTED:continue
        folder=DEST/'vendor'/row['instance_id'];source=folder/'buggy';fixed=folder/'fixed'
        url=f"https://codeload.github.com/{row['repo']}/zip/{row['base_commit']}"
        archive=folder/'source.zip';folder.mkdir(parents=True,exist_ok=True)
        if not archive.exists():
            with urllib.request.urlopen(url,timeout=90) as response:archive.write_bytes(response.read())
        if not source.exists():
            source.mkdir()
            with zipfile.ZipFile(io.BytesIO(archive.read_bytes())) as zipped:
                for info in zipped.infolist():
                    relative=Path(*Path(info.filename).parts[1:]);target=(source/relative).resolve()
                    if not target.is_relative_to(source.resolve()):raise ValueError('Archive escaped fixture')
                    if not relative.parts:continue
                    if info.is_dir():target.mkdir(parents=True,exist_ok=True)
                    else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(zipped.read(info))
        if not fixed.exists():
            shutil.copytree(source,fixed)
            changed=apply_verified_patch(fixed,row['patch'])
        else:changed=[l[6:].strip() for l in row['patch'].splitlines() if l.startswith('--- a/')]
        record={'instance_id':row['instance_id'],'repo':row['repo'],'base_commit':row['base_commit'],
            'issue_url':'https://github.com/'+row['repo']+'/issues/'+row['instance_id'].split('-')[-1],
            'source_url':url,'source_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
            'changed_files':{p:{variant:hashlib.sha256((folder/variant/p).read_bytes()).hexdigest() for variant in ['buggy','fixed']} for p in changed},
            'problem_statement':row['problem_statement'],'gold_patch_sha256':hashlib.sha256(row['patch'].encode()).hexdigest(),
            'gold_test_patch_sha256':hashlib.sha256(row['test_patch'].encode()).hexdigest()}
        manifest.append(record);print(row['instance_id'],'prepared',flush=True)
    (DEST/'upstream-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')


if __name__=='__main__':main()
