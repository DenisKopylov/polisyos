from __future__ import annotations
import datetime
import gzip
import hashlib
import json
import os
import resource
import subprocess
import time
from pathlib import Path

ROOT=Path('/workspace/orch02-r2-c06-dfk-g/policy-engine')
OUT=Path('/workspace/orch02-r2/c06-dfk/required-invocation')
OUT.mkdir()
PY='/workspace/polisyos/policy-engine/.venv/bin/python'
env={**os.environ,'PYTHONPATH':str(ROOT/'src')+os.pathsep+str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'}
argv=[PY,'-m','polisyos.runtime.quality.production_invocation','--repo-root',str(ROOT),
      '--base','dee58973f7673299070b7c7374f419b0adb8175c','--receipt',str(OUT/'receipt.json')]
start=datetime.datetime.now(datetime.UTC).isoformat();tick=time.monotonic()
with (OUT/'stdout.txt').open('wb') as stdout, (OUT/'stderr.txt').open('wb') as stderr:
 result=subprocess.run(argv,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
outputs={}
for suffix in ('stdout.txt','stderr.txt'):
 data=(OUT/suffix).read_bytes();outputs[suffix]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
receipt={'argv':argv,'cwd':str(ROOT),'start_utc':start,'end_utc':datetime.datetime.now(datetime.UTC).isoformat(),
         'wall_seconds':time.monotonic()-tick,'returncode':result.returncode,'max_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
         'timeout_seconds':None,'selected_environment':{k:env.get(k) for k in ('PYTHONPATH','PYTHONDONTWRITEBYTECODE')},
         'source_commit':'3a0d5549606087c1d4e8d344ed474c0dfb4cbe5d','source_tree':'1e2e7c6ca7948f3c2b771af431bd0d73510fec3a','outputs':outputs}
(OUT/'command.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
if (OUT/'receipt.json').exists():
 raw=(OUT/'receipt.json').read_bytes();encoded=gzip.compress(raw,mtime=0)
 assert gzip.decompress(encoded)==raw
 (OUT/'receipt.json.gz').write_bytes(encoded)
 (OUT/'lossless.json').write_text(json.dumps({'original_raw_source':str(OUT/'receipt.json'),'compressed_path':'receipt.json.gz',
      'compressed_bytes':len(encoded),'compressed_sha256':hashlib.sha256(encoded).hexdigest(),
      'decoded_bytes':len(raw),'decoded_sha256':hashlib.sha256(raw).hexdigest(),'exact_roundtrip':True},sort_keys=True,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
