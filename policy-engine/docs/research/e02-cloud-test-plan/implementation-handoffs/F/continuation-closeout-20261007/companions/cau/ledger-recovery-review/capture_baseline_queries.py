"""Capture complete source-reported baseline navigation for all35 F IDs."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

REPO=Path('/workspace/e02-F-cau-20261006')
SOURCE='4d8eaec43d09d9c7df3a2ac8bd244e4d132d03f9'
OUT=Path(__file__).resolve().parent/'baseline-queries'
OUT.mkdir(exist_ok=True)
P='policy-engine/docs/research/e02-cloud-test-plan/'
def sha(value): return hashlib.sha256(value).hexdigest()
def ref(path):
    b=path.read_bytes()
    return dict(path=str(path),bytes=len(b),sha256=sha(b))
def head(): return subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip()
assert head()==SOURCE
raw=subprocess.check_output(['git','show',SOURCE+':'+P+'execution-organization/finding-owners.tsv'],cwd=REPO)
all_rows=list(csv.DictReader(io.StringIO(raw.decode()),delimiter='\t'))
ids=[r['finding_id'] for r in all_rows if r['unit']=='F']
assert len(all_rows)==282 and len(ids)==len(set(ids))==35
jobs=[('F-failures30',['--unit','F','--failures-only','--limit','30'])]
jobs += [(fid,['--finding',fid,'--details','--limit','10000','--block-limit','10000']) for fid in ids]
processes=[]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
for label,args in jobs:
    command=[sys.executable,P+'results/query.py',*args]
    start=time.time()
    process=subprocess.Popen(command,cwd=REPO,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    processes.append((label,command,start,process))
records=[]
for label,command,start,process in processes:
    stdout,stderr=process.communicate()
    out=OUT/(label+'.stdout.json');err=OUT/(label+'.stderr')
    out.write_bytes(stdout);err.write_bytes(stderr)
    record=dict(label=label,command=command,cwd=str(REPO),source_sha=SOURCE,exit=process.returncode,elapsed_s=time.time()-start,environment=dict(python=platform.python_version(),executable=sys.executable,PYTHONDONTWRITEBYTECODE='1',purpose='stdlib source-reported metadata navigation; no product/backend test'),stdout=ref(out),stderr=ref(err),product_PASS_inference=False)
    (OUT/(label+'.execution.json')).write_text(json.dumps(record,indent=2)+'\n')
    records.append(record)
assert head()==SOURCE
result=dict(schema='e02.F.baseline-query-capture.v1',check='PASS' if all(r['exit']==0 for r in records) else 'ERROR',source_sha=SOURCE,finding_denominator=35,total_full_source_owner_rows=282,query_launches=len(records),source_begin_end_unchanged=True,records=records,scope='Complete requested query stdout/stderr, not deciding candidate behavior; failure30 is navigation only, per-ID full cells/source blocks are joined separately.',replayer=ref(Path(__file__)))
(OUT/'capture.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(check=result['check'],query_launches=len(records),finding_denominator=35,exit_counts={str(c):sum(r['exit']==c for r in records) for c in set(r['exit'] for r in records)},stdout_total_bytes=sum(r['stdout']['bytes'] for r in records),stderr_total_bytes=sum(r['stderr']['bytes'] for r in records),output=ref(OUT/'capture.json')),indent=2))
