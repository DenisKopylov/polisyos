from __future__ import annotations
import datetime
import hashlib
import json
import os
import resource
import subprocess
import time
from pathlib import Path

ROOT=Path('/workspace/orch02-r2-c06-dfk-g/policy-engine')
OUT=Path('/workspace/orch02-r2/c06-dfk/required-architecture')
OUT.mkdir()
NODE='/workspace/.polisyos-environment/node-v22.23.3-linux-x64/bin'
UV='/workspace/.polisyos-environment/uv/bin'
PY='/workspace/polisyos/policy-engine/.venv/bin/python'
env={**os.environ,'PATH':os.pathsep.join((NODE,UV,str(Path(PY).parent),os.environ['PATH'])),
     'PYTHONPATH':str(ROOT/'src')+os.pathsep+str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'}
commands=[('node-bootstrap',[NODE+'/corepack','pnpm','install','--frozen-lockfile','--ignore-scripts']),
          ('architecture',[PY,'-m','tools.cli','architecture','guardrails','check',
                           '--generated-freshness-workspace-root',str(OUT/'generated-freshness'),
                           '--generated-freshness-uv-cache-dir','/workspace/.polisyos-environment/cache/uv'])]
for name,argv in commands:
 directory=OUT/name;directory.mkdir()
 start=datetime.datetime.now(datetime.UTC).isoformat();tick=time.monotonic()
 with (directory/'stdout.txt').open('wb') as stdout,(directory/'stderr.txt').open('wb') as stderr:
  result=subprocess.run(argv,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
 outputs={}
 for suffix in ('stdout.txt','stderr.txt'):
  data=(directory/suffix).read_bytes();outputs[suffix]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 receipt={'argv':argv,'cwd':str(ROOT),'start_utc':start,'end_utc':datetime.datetime.now(datetime.UTC).isoformat(),
          'wall_seconds':time.monotonic()-tick,'returncode':result.returncode,
          'max_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'timeout_seconds':None,
          'selected_environment':{k:env.get(k) for k in ('PATH','PYTHONPATH','PYTHONDONTWRITEBYTECODE')},
          'source_commit':'3a0d5549606087c1d4e8d344ed474c0dfb4cbe5d','source_tree':'1e2e7c6ca7948f3c2b771af431bd0d73510fec3a','outputs':outputs}
 (directory/'command.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
 print(json.dumps({'gate':name,'returncode':result.returncode,'wall_seconds':receipt['wall_seconds'],'outputs':outputs}),flush=True)
 if name=='node-bootstrap' and result.returncode:
  raise SystemExit(result.returncode)
