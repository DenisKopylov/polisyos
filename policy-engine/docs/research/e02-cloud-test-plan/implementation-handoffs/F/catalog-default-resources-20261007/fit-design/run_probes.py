from pathlib import Path
import hashlib, json, os, subprocess, sys, time
scratch=Path(__file__).resolve().parent
base=Path('/tmp/e02-F-continuation-20261007/foundry/installed-continuation-final')
kind=sys.argv[1]
argv=[str(base/f'{kind}-env/bin/python'),'-I',str(scratch/'probe_additional_consumers.py'),str(base/'installed-config.json'),kind,'/workspace/e02-F-closeout-20261006/policy-engine/data/dataset_catalog',str(scratch/'state')]
env={k:v for k,v in os.environ.items() if k not in {'PYTHONPATH','PYTHONHOME'}}
start=time.monotonic();result=subprocess.run(argv,cwd=scratch,env=env,capture_output=True);wall=time.monotonic()-start
outputs={}
for label,data in [('stdout',result.stdout),('stderr',result.stderr)]:
 path=scratch/f'{kind}-additional.{label}.txt';path.write_bytes(data);outputs[label]={'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
record={'argv':argv,'cwd':str(scratch),'env_changes':{'PYTHONPATH':'removed if inherited','PYTHONHOME':'removed if inherited'},'new_resource_quota':False,'exit':result.returncode,'wall_seconds':wall,'outputs':outputs}
(scratch/f'{kind}-additional.execution.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(result.returncode)
