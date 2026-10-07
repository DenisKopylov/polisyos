from __future__ import annotations
import datetime as dt,hashlib,json,os,resource,shutil,subprocess,time
from pathlib import Path
base=Path(__file__).resolve().parent;task=base.parents[1]
root=Path('/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos');py=root/'policy-engine/.venv/bin/python'
candidate=task/'candidate/policy-engine'
env={**os.environ,'PYTHONPATH':str(candidate/'src'),'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','C_CANON_GROOT':str(root)}
argv=[str(py),'-B',str(base/'probe.py')];outp=base/'stdout.txt';errp=base/'stderr.txt'
started=dt.datetime.now(dt.timezone.utc).isoformat();free0=shutil.disk_usage(root).free;t=time.monotonic()
try:p=subprocess.run(argv,cwd=candidate,env=env,capture_output=True,timeout=60);out,err,code=p.stdout,p.stderr,p.returncode;timed=False
except subprocess.TimeoutExpired as e:out,err,code=e.stdout or b'',e.stderr or b'',None;timed=True
wall=time.monotonic()-t;ended=dt.datetime.now(dt.timezone.utc).isoformat();outp.write_bytes(out);errp.write_bytes(err)
rec={'candidate_sha':'55b45d9a5c95c3b773fc3b4d8679786b3993eb1e','candidate_tree':'70ed14e004063536ff3a12d30d14d9bdd79a4916','argv':argv,'cwd':str(candidate),'environment':{k:env[k] for k in ('PYTHONPATH','PYTHONNOUSERSITE','PYTHONDONTWRITEBYTECODE','C_CANON_GROOT')},'python_version':subprocess.check_output([str(py),'--version'],text=True).strip(),'timeout_seconds':60,'timed_out':timed,'exit_code':code,'started_utc':started,'ended_utc':ended,'wall_seconds':wall,'disk_free_bytes_before':free0,'disk_free_bytes_after':shutil.disk_usage(root).free,'maxrss_platform_units':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'stdout_path':str(outp),'stderr_path':str(errp),'stdout_bytes':len(out),'stderr_bytes':len(err),'stdout_sha256':hashlib.sha256(out).hexdigest(),'stderr_sha256':hashlib.sha256(err).hexdigest()}
(base/'supervisor-receipt.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec,indent=2))
