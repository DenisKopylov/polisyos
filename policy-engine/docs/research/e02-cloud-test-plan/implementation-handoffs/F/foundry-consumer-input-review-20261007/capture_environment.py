"""Capture only non-secret runtime/version identity for the measured native profile."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
out=Path('/tmp/e02-F-continuation-20261007/foundry')
python='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
code='import importlib.metadata as m,json,platform,sys; import numpy,scipy,sklearn; print(json.dumps({"python":sys.version,"executable":sys.executable,"platform":platform.platform(),"versions":{x:m.version(x) for x in ["numpy","scipy","scikit-learn","pytest","pydantic"]},"module_origins":{x.__name__:x.__file__ for x in [numpy,scipy,sklearn]},"baseline_optional_profile":"Python3.14 DoWhy/EconML exclusions are not positive backend witness; no shim", "global_orchestration_quota_introduced":False},sort_keys=True))'
argv=[python,'-c',code]
p=subprocess.run(argv,cwd='/workspace/e02-F-fry-20261006/policy-engine',capture_output=True)
records={}
for name,raw in [('stdout',p.stdout),('stderr',p.stderr)]:
 path=out/('environment.'+name+'.json' if name=='stdout' else 'environment.stderr.txt');path.write_bytes(raw);records[name]={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
record={'command':argv,'cwd':'/workspace/e02-F-fry-20261006/policy-engine','environment':{'app_python':python,'stdlib_baseline_python':sys.executable,'stdlib_baseline_version':sys.version,'inherited_numeric_options':{k:os.environ[k] for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'] if k in os.environ},'new_quota':False},'exit_code':p.returncode,**records}
(out/'environment.json').write_text(json.dumps(record,indent=2)+'\n');assert p.returncode==0;print(json.dumps({'environment_capture':'PASS','stdout':records['stdout']}))
