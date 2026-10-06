"""Complete historical installed warning membership, without copying tracked logs."""
from pathlib import Path
import ast
from collections import Counter
import hashlib
import json
import re
import subprocess

root=Path('/workspace/e02-F-closeout-20261006')
receipt_sha='3dde887e22592cdd7c1fe8865707afdfd72dc6fb'
source_sha='5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6'
prefix='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-latest-dependencies-20261006/'

def git(*args):
    return subprocess.check_output(['git','-C',str(root),*args])

def bound(path, sha=receipt_sha):
    data=git('show',f'{sha}:{path}')
    return data,dict(git_sha=sha,path=path,git_blob=git('rev-parse',f'{sha}:{path}').decode().strip(),
        bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

raw,receipt_ref=bound(prefix[:-1]+'.json')
receipt=json.loads(raw)
test_path='policy-engine/tests/unit/foundry/methods/catalog/causal/test_installed_worker_profile.py'
test,test_ref=bound(test_path,source_sha)
test_order=[n.name for n in ast.parse(test).body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
launcher,launcher_ref=bound(prefix+'author/final_launch.py')
profiles=[]
for kind in ('wheel','sdist'):
    check=next(c for c in receipt['checks'] if c['id']==kind+'-native')
    raw,output_ref=bound(check['output_ref']['path'])
    assert output_ref['bytes']==check['output_ref']['bytes']
    assert output_ref['sha256']==check['output_ref']['sha256']
    text=raw.decode()
    manifests=[json.loads(line) for line in text.splitlines() if line.startswith('{"manifest":')]
    assert len(manifests)==1
    provenance=manifests[0]
    manifest=provenance['manifest']
    assert manifest['source_sha']==source_sha
    blocks=text.split('warnings summary')
    assert len(blocks)==2
    warning_text=blocks[1].split('-- Docs:')[0]
    groups=[]; pending=[]
    for line in warning_text.splitlines():
        if line.startswith('test_') and '::' in line:
            pending.append(line.strip())
        match=re.match(r'^\s+(.+:\d+): (\w+Warning): (.*)$',line)
        if match:
            location,category,message=match.groups()
            runtime=re.fullmatch(r'\[(WARNING|ERROR)\] ([^:]+): ([^ ]+) — (.*)',message)
            group=dict(observed_group_order=len(groups),category=category,message=message,
                location=location,test_memberships=pending[:],occurrences=max(1,len(pending)),
                classification='runtime_output_monitor' if runtime else 'instrumentation_or_other')
            if runtime:
                severity,key,code,reason=runtime.groups()
                group.update(severity=severity.lower(),key=key,code=code,reason=reason)
            groups.append(group);pending=[]
    assert groups
    memberships=[dict(test=test,category=g['category'],key=g['key'],code=g['code'],
        severity=g['severity'],message=g['message']) for g in groups if g['classification']=='runtime_output_monitor'
        for test in g['test_memberships']]
    other=[g for g in groups if g['classification']!='runtime_output_monitor']
    summary=re.findall(r'(\d+) passed, (\d+) warnings? in ([\d.]+)s',text)
    assert len(summary)==1
    passed,warnings,seconds=summary[0]
    assert int(warnings)==len(memberships)+sum(g['occurrences'] for g in other)
    assert passed==str(len(test_order))
    profiles.append(dict(profile=kind,source_sha=source_sha,source_tree=git('rev-parse',source_sha+'^{tree}').decode().strip(),
        command=check['command'],argv=check['argv'],cwd=check['cwd'],environment=check['environment'],
        output_ref=output_ref,pytest_args=provenance['pytest_args'],isolated=provenance['isolated'],
        interpreter=manifest['python'],site=manifest['site'],consumer=manifest['consumer'],
        archive=dict(path=manifest['artifact'],bytes=manifest['artifact_bytes'],sha256=manifest['artifact_sha256']),
        fixture_carriers=manifest['carriers'],worker_assets=manifest['assets'],
        execution_test_order=test_order,warning_groups=groups,runtime_memberships=memberships,
        counts=dict(passed=int(passed),pytest_warnings=int(warnings),runtime_warnings=len(memberships),
            distinct_runtime_messages=len({g['message'] for g in groups if g['classification']=='runtime_output_monitor'}),
            runtime_codes=dict(Counter(g['code'] for g in memberships)),runtime_by_test=dict(Counter(g['test'] for g in memberships)),
            instrumentation_warnings=sum(g['occurrences'] for g in other)),pytest_seconds=float(seconds)))
normalize=lambda p:Counter((x['test'],x['category'],x['key'],x['code'],x['severity'],x['message']) for x in p['runtime_memberships'])
assert normalize(profiles[0])==normalize(profiles[1])
print(json.dumps(dict(outcome='PASS',scope='Complete two native raw stdout warning blocks at historical installed scientific source; no new runtime execution.',
    receipt=receipt_ref,fixture=test_ref,launcher=launcher_ref,profiles=profiles,
    identical_memberships=True,warning_order='Retain actual group ordering separately; order differs between independent interpreters due to runtime unordered slot iteration, not membership.',
    limitations=['Native3PASS per historical profile is bounded scientific computation; warning anomaly14 was real and preserved.',
        'Baseline configured external3.12 worker via POLISYOS_DOWHY_WORKER_PYTHON; no default-interpreter discovery proof.',
        'No source/installed environments modified; actual archives/build/new consumers held until composed common freeze.',
        'Optional LightGBM warnings are separate categories, not runtime monitor corrections.']),indent=2,sort_keys=True))
