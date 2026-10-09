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
OUT=Path('/workspace/orch02-r2/c06-dfk/author-gates')
PY='/workspace/polisyos/policy-engine/.venv/bin/python'
RUFF='/workspace/polisyos/policy-engine/.venv/bin/ruff'
G='dee58973f7673299070b7c7374f419b0adb8175c'
paths=['tools/quality/validation/schema_fqn_census.py','tests/unit/remediation/test_dfk_01.py']
environment={**os.environ,'PYTHONPATH':str(ROOT)+os.pathsep+str(ROOT/'src'),'PYTHONDONTWRITEBYTECODE':'1'}
commands=[
 ('ruff-check',[RUFF,'check',*paths]),
 ('ruff-format',[RUFF,'format','--check',*paths]),
 ('mypy',[PY,'-m','mypy','--strict','--follow-imports=skip','--cache-dir',str(OUT/'mypy-cache'),paths[0]]),
 ('imports',[PY,'-m','tools.quality.lint.lint_imports','--changed-only','--git-base-ref',G,'--cache-dir',str(OUT/'imports-cache'),'--output-format','json']),
 ('architecture-nongenerated',[PY,'-m','tools.cli','architecture','guardrails','check','--skip-generated-checks'])]
for name,argv in commands:
 directory=OUT/name
 directory.mkdir(parents=True,exist_ok=True)
 start=datetime.datetime.now(datetime.UTC).isoformat(); tick=time.monotonic()
 result=subprocess.run(argv,cwd=ROOT,env=environment,capture_output=True)
 outputs={}
 for suffix,data in [('stdout.txt',result.stdout),('stderr.txt',result.stderr)]:
  (directory/suffix).write_bytes(data)
  outputs[suffix]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 receipt={'argv':argv,'cwd':str(ROOT),'start_utc':start,'end_utc':datetime.datetime.now(datetime.UTC).isoformat(),'wall_seconds':time.monotonic()-tick,'returncode':result.returncode,'max_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'timeout_seconds':None,'selected_environment':{k:environment.get(k) for k in ('PYTHONPATH','PYTHONDONTWRITEBYTECODE')},'outputs':outputs}
 (directory/'command.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
 print(json.dumps({'gate':name,'returncode':result.returncode,'stdout_bytes':len(result.stdout),'stderr_bytes':len(result.stderr)}),flush=True)
