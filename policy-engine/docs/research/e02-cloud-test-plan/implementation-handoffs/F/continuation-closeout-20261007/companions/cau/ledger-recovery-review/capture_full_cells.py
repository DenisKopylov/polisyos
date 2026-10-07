"""Complete unique routed cells and one full source dictionary per baseline job."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

REPO=Path('/workspace/e02-F-cau-20261006');SOURCE='4d8eaec43d09d9c7df3a2ac8bd244e4d132d03f9'
OUT=Path(__file__).resolve().parent/'baseline-cells';OUT.mkdir(exist_ok=True)
ROOT=Path(__file__).resolve().parent
P='policy-engine/docs/research/e02-cloud-test-plan/results/'
def sha(b): return hashlib.sha256(b).hexdigest()
def ref(p):
    b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=sha(b))
def head():return subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip()
assert head()==SOURCE
cells={};job_cell={}
for path in (ROOT/'baseline-queries').glob('*.stdout.json'):
    if path.name=='F-failures30.stdout.json':continue
    o=json.loads(path.read_text());assert o['matching_cells']==o['displayed_cells']==len(o['cells'])
    assert o['matching_source_blocks']==len(o['source_blocks'])
    for c in o['cells']:
        if c['id'] in cells:assert cells[c['id']]==c
        cells[c['id']]=c;job_cell.setdefault(c['job'],c['id'])
jobs=[(cid,['--cell',cid,'--details','--limit','10000','--block-limit','10000']) for cid in sorted(cells)]
jobs += [(job+'-context',['--cell',cid,'--details','--job-context','--limit','10000','--block-limit','10000']) for job,cid in sorted(job_cell.items())]
processes=[];env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
for label,args in jobs:
    command=[sys.executable,P+'query.py',*args];start=time.time();process=subprocess.Popen(command,cwd=REPO,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE);processes.append((label,command,start,process))
records=[]
for label,command,start,process in processes:
    stdout,stderr=process.communicate();out=OUT/(label+'.stdout.json');err=OUT/(label+'.stderr');out.write_bytes(stdout);err.write_bytes(stderr)
    o=json.loads(stdout) if process.returncode==0 else {}
    if o:assert o['matching_cells']==o['displayed_cells']==len(o['cells']) and o['matching_source_blocks']==len(o['source_blocks'])
    record=dict(label=label,command=command,cwd=str(REPO),source_sha=SOURCE,exit=process.returncode,elapsed_s=time.time()-start,environment=dict(python=platform.python_version(),executable=sys.executable,PYTHONDONTWRITEBYTECODE='1',scope='metadata query only, not baseline or candidate backend runtime'),stdout=ref(out),stderr=ref(err),display_complete=bool(o),raw_archive_witness=False)
    (OUT/(label+'.execution.json')).write_text(json.dumps(record,indent=2)+'\n');records.append(record)
assert head()==SOURCE
result=dict(schema='e02.F.baseline-full-cell-capture.v1',check='PASS' if all(r['exit']==0 for r in records) else 'ERROR',source_sha=SOURCE,full35_query_denominator=35,unique_routed_cells=len(cells),unique_source_jobs=len(job_cell),records=records,source_begin_end_unchanged=True,scope='Full unique cell query bodies plus complete job dictionaries/capability/markers input metadata. Source reported compact only, not positive native backend or candidate scientific property.',replayer=ref(Path(__file__)))
(OUT/'capture.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(check=result['check'],unique_cells=len(cells),jobs=len(job_cell),launches=len(records),stdout_bytes=sum(r['stdout']['bytes'] for r in records),stderr_bytes=sum(r['stderr']['bytes'] for r in records),output=ref(OUT/'capture.json')),indent=2))
