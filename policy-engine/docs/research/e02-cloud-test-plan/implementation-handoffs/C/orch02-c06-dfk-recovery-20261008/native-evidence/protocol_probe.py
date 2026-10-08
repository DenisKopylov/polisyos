from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT=Path('/workspace/orch02-native-c06/protocol-matrix-v3')
SCRIPT=Path('/workspace/orch02-c06-dfk/policy-engine/tools/quality/validation/schema_fqn_census.py')
sys.path.insert(0,str(SCRIPT.parents[3]))


def run_case(mode: str, nested: bool):
    root=ROOT/(mode+('-nested' if nested else '-root'))
    root.mkdir(parents=True,exist_ok=False)
    prefix='policy-engine/' if nested else ''
    command_receipts=[]
    def git(*args,cwd=None):
        cmd=['git',*args]
        proc=subprocess.run(cmd,cwd=cwd or root,capture_output=True,check=True)
        command_receipts.append({'argv':cmd,'cwd':str(cwd or root),'stdout_hex':proc.stdout.hex(),'stderr_hex':proc.stderr.hex(),'returncode':proc.returncode})
        return proc.stdout
    git('init','--quiet');git('config','user.email','fixture@example.invalid');git('config','user.name','Fixture');git('config','status.renames','copies')
    source='configs/01 original\nпуть.json';dest='configs/02 copy space.json';sentinel='configs/03 sentinel.json'
    data=json.dumps({'module':'polisyos.foundry.domain.schema','values':[f'value-{i:04}' for i in range(200)]},indent=2)+'\n'
    files={source:data,sentinel:'{}\n'}
    if mode=='added-modified':files={'base.json':'{}\n'}
    for path,text in files.items():
        p=root/(prefix+path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    if nested:(root/'outside.json').write_text('{}\n')
    git('add','--all');git('commit','--quiet','-m','fixture base')
    product=root/'policy-engine' if nested else root
    if mode=='added-modified':
        for path in (source,sentinel):
            p=product/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}\n')
        git('add','--all')
        for path in (source,sentinel):(product/path).write_text(data)
    elif mode in ('ordinary-staged','ordinary-unstaged'):
        for path in (source,sentinel):(product/path).write_text(data+'\n')
        if mode=='ordinary-staged':git('add','--all')
    elif mode.startswith('rename'):
        if mode=='rename-unstaged':
            (product/source).rename(product/dest);git('add','-N','--',prefix+dest)
        else:
            git('mv','--',prefix+source,prefix+dest)
            if mode=='rename-staged-modified':(product/dest).write_text(data+'\n')
        (product/sentinel).write_text(data)
    elif mode.startswith('copy'):
        (product/dest).write_text(data);(product/source).write_text(data+'\n')
        if mode=='copy-unstaged':git('add','-N','--',prefix+dest)
        else:
            git('add','--all')
            if mode=='copy-staged-modified':(product/dest).write_text(data+'\n')
        (product/sentinel).write_text(data)
    if nested:(root/'outside.json').write_text('{"changed":true}\n')
    raw=git('status','--porcelain=v1','-z','--untracked-files=all')
    oracle=set()
    for args in (
        ('diff','--relative','--name-only','--no-renames','-z','--','.'),
        ('diff','--cached','--relative','--name-only','--no-renames','-z','--','.'),
        ('ls-files','--others','--exclude-standard','-z','--','.'),
    ):
        oracle.update(os.fsdecode(p) for p in git(*args,cwd=product).split(b'\0') if p)
    git('diff','--cached','--raw','-z','-C','--find-copies-harder')
    git('diff','--raw','-z','-C','--find-copies-harder')
    spec=importlib.util.spec_from_file_location('c06_bound_census',SCRIPT);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    parsed,metadata=module._git_status_paths(product)
    assert set(parsed)==oracle,(mode,nested,parsed,oracle,repr(raw))
    if mode.startswith('rename') or mode.startswith('copy'):
        status={'rename-staged':b'R ','rename-staged-modified':b'RM','rename-unstaged':b' R','copy-staged':b'C ','copy-staged-modified':b'CM','copy-unstaged':b' C'}[mode]
        assert status+b' '+os.fsencode(prefix+dest)+b'\0'+os.fsencode(prefix+source)+b'\0' in raw,(mode,repr(raw))
    completed=subprocess.run([sys.executable,str(SCRIPT),'--repo-root',str(product)],capture_output=True,check=False)
    receipt=json.loads(completed.stdout)
    (root/'census.stdout.json').write_bytes(completed.stdout)
    (root/'census.stderr.txt').write_bytes(completed.stderr)
    selected=set(receipt['selection']['selected_paths'])
    assert set(receipt['selection']['working_tree_changes'])==oracle&selected,(mode,nested)
    if mode=='rename-unstaged':
        # Intent-to-add exposes the real Y=R protocol, but its missing old path
        # is still tracked. The actual census must preserve that fail-closed fact.
        assert completed.returncode==2
        assert receipt['read_receipt']['complete_verdict'] is False
        assert receipt['scanned_denominator']['unreadable_paths']==[source]
        assert receipt['scanned_denominator']['successful_byte_reads']==len(selected)-1
    else:
        assert completed.returncode==0,(mode,nested,completed.returncode,completed.stderr)
        assert receipt['read_receipt']['complete_verdict'] is True
        assert receipt['scanned_denominator']['successful_byte_reads']==len(selected)
    assert all('outside.json' != p for p in selected) if nested else True
    return {'mode':mode,'nested':nested,'fixture':str(root),'commands':command_receipts,'parsed_paths':parsed,'oracle':sorted(oracle),'selected_paths':sorted(selected),'parser_metadata':metadata,'census_stdout_sha256':hashlib.sha256(completed.stdout).hexdigest(),'result':'PASS'}


if __name__=='__main__':
    ROOT.mkdir(exist_ok=False)
    results=[]
    for mode in ('ordinary-staged','ordinary-unstaged','added-modified','rename-staged','rename-staged-modified','rename-unstaged','copy-staged','copy-staged-modified','copy-unstaged','clean'):
        for nested in (False,True):
            results.append(run_case(mode,nested))
            print(mode,'nested' if nested else 'root','PASS')
    origins=[]
    for name,module in sorted(sys.modules.items()):
        if name=='tools' or name.startswith('tools.'):
            path=Path(module.__file__).resolve()
            assert path.is_relative_to(SCRIPT.parents[3]),(name,path)
            origins.append({'module':name,'origin':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (ROOT/'receipt.json').write_text(json.dumps({'source_commit':'cbbfffd367fe283813a8177575d26c0ede8d20c4','source_sha256':hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),'origins':origins,'cases':results},indent=2)+'\n')
