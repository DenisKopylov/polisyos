from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
root=Path.cwd(); base=root/'policy-engine/_build/e02-g-continuation-20261006/R/local-transition-20261009'
pairs=[('CAN','2762cec321d0cc78874abb986736dab54e2fb189'),('C11','03698439abfb1cb59f763397a182d8e0e393d40d'),('C10','e6854a70a6d2ae9e4df82351925d7cabe1e9e5e8'),('DFK','3a0d5549606087c1d4e8d344ed474c0dfb4cbe5d')]
for name, sha in pairs:
    data=json.loads((base/'checks'/name/'import-origins.json').read_text())
    modules=[m for m in data['modules'] if m.get('candidate_relative_path') is not None]
    refs=[f'{sha}:policy-engine/{m["candidate_relative_path"]}' for m in modules]
    p=subprocess.Popen(['git','cat-file','--batch'],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert p.stdin and p.stdout
    mismatches=[]
    for module, ref in zip(modules,refs,strict=True):
        p.stdin.write(ref.encode()+b'\n'); p.stdin.flush()
        header=p.stdout.readline().decode().strip().split()
        if len(header)<3 or header[1]!='blob': raise RuntimeError(f'unexpected git object header: {header!r}')
        size=int(header[2]); blob=p.stdout.read(size); assert len(blob)==size
        assert p.stdout.read(1)==b'\n'
        digest=hashlib.sha256(blob).hexdigest()
        if digest!=module['sha256']: mismatches.append({'module':module['module'],'path':module['candidate_relative_path'],'import_sha256':module['sha256'],'git_sha256':digest})
    p.stdin.close(); stderr=p.stderr.read() if p.stderr else b''; code=p.wait()
    if code: raise RuntimeError(f'git cat-file failed: {stderr!r}')
    out={'slice':name,'commit':sha,'imported_module_count':len(data['modules']),'candidate_module_files_checked':len(modules),'outside_candidate_imports':sum(1 for m in data['modules'] if m.get('candidate_relative_path') is None),'mismatches':mismatches,'result':'PASS' if not mismatches else 'MISMATCH'}
    (base/'checks'/name/'origin-blob-check.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,sort_keys=True))
