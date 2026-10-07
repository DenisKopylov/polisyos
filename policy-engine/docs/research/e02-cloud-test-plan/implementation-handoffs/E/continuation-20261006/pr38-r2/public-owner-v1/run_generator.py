"""Canonical generator only; outputs redirected, no active checkout mutation."""
from pathlib import Path
import hashlib,json,os,subprocess,time,sys
O=Path(__file__).parent; R=Path('/workspace/e02-E-continuation-20261006'); F=O/'fixture-current'/'policy-engine'; PY=R/'policy-engine/.venv/bin/python'
phase=sys.argv[1]; D=O/('generated-'+phase);D.mkdir(exist_ok=True)
args=[str(PY),'tools/devx/architecture/guardrails.py','sync','--skip-deep-import-baseline','--public-json',str(D/'inventory.json'),'--public-md',str(D/'public-surface.md'),'--generated-md',str(D/'generated-artifacts.md')]
start=time.time(); env=dict(os.environ,UV_NO_SYNC='1');p=subprocess.run(args,cwd=F,env=env,capture_output=True,text=True)
(D/'sync.stdout').write_text(p.stdout+p.stderr)
sourcepaths=['src/polisyos/calibration/__init__.py','src/polisyos/calibration/forecast_bridge.py','src/polisyos/scientist/methods/backtesting/forecast_owner.py','src/polisyos/foundry/uncertainty/__init__.py','tools/devx/architecture/guardrails.py','architecture/public_surface/contract.toml']
result={'phase':phase,'command':args,'cwd':str(F),'UV_NO_SYNC':'1','exit_code':p.returncode,'wall_seconds':time.time()-start,'fixture_is_git_candidate':False,'no_full_global_guard':True,'input_paths':{s:{'sha256':hashlib.sha256((F/s).read_bytes()).hexdigest(),'bytes':(F/s).stat().st_size} for s in sourcepaths}}
(D/'execution.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(p.returncode)
