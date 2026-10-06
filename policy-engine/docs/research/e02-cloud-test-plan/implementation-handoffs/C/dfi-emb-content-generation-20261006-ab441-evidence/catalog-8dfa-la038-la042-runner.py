from __future__ import annotations
import hashlib,json,subprocess,sys,time
from datetime import UTC,datetime
from pathlib import Path
root=Path(__file__).parent
vector_python=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/dfi-ab441/venv-vector-search/bin/python')
source=root/'source/policy-engine/src'
metrics=root/'source/policy-engine/data/dataset_catalog/metrics_map.yaml'
wheel=root/'dist/policy_engine-0.1.0-py3-none-any.whl'
probes=[
 ('cat-dfi-038','/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/dfi-ab441/context038-probe-final.py',[str(root/'cat-dfi-038-run'),str(metrics),str(wheel),str(source)]),
 ('cat-dfi-042','/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/dfi-ab441/legal042-probe-final.py',[str(root/'cat-dfi-042-run'),str(wheel),str(source)]),
]
env={'PATH':'/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin','HOME':'/Users/deniskopylov','TMPDIR':'/tmp','LANG':'en_US.UTF-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0'}
records=[]
for name,script,args in probes:
 command=[str(vector_python),'-I',script,*args]
 start=datetime.now(UTC);t0=time.monotonic()
 result=subprocess.run(command,cwd='/tmp',env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
 elapsed=time.monotonic()-t0;end=datetime.now(UTC)
 out=root/f'{name}.stdout';err=root/f'{name}.stderr';out.write_bytes(result.stdout);err.write_bytes(result.stderr)
 def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
 manifest={'argv':command,'cwd':'/tmp','environment':env,'environment_is_complete_child_environment':True,'started_at_utc':start.isoformat(),'ended_at_utc':end.isoformat(),'elapsed_seconds':elapsed,'exit_code':result.returncode,'stdout_path':str(out),'stdout_sha256':sha(out),'stderr_path':str(err),'stderr_sha256':sha(err),'installed_wheel_sha256':sha(wheel)}
 man=root/f'{name}-command.json';man.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 records.append({'name':name,**manifest,'command_manifest_path':str(man),'command_manifest_sha256':sha(man)})
print(json.dumps(records,sort_keys=True))
if any(record['exit_code'] for record in records):raise SystemExit(1)
