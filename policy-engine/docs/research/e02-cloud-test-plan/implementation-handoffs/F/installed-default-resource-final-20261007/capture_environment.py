"""Observe real installed environments without importing/scoring providers."""
import hashlib,json,os,subprocess
from pathlib import Path
base=Path(__file__).resolve().parent;config=json.loads((base/'installed-config.json').read_text());env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1';records=[]
for kind in ('wheel','sdist'):
 argv=[config['installed_pythons'][kind],'-I',str(base/'environment.py')];cwd=base/(kind+'-consumer');result=subprocess.run(argv,cwd=cwd,env=env,capture_output=True);row={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'argv':argv,'cwd':str(cwd),'exit_code':result.returncode,'observation_only':True}
 for stream,data in [('stdout',result.stdout),('stderr',result.stderr)]:
  path=base/(kind+'-environment.'+stream+'.json');assert not path.exists();path.write_bytes(data);row[stream]={'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 records.append(row);assert result.returncode==0
argv=[config['worker_python'],'-I','-c',"import importlib.metadata,platform,sys;print(platform.python_version());print(importlib.metadata.version('dowhy'));print(sys.executable)"]
result=subprocess.run(argv,cwd=base,env=env,capture_output=True);row={'source_sha':config['source_sha'],'argv':argv,'cwd':str(base),'exit_code':result.returncode,'scope':'External locked backend metadata/resource observation only, no new inference/backend-execution positive'}
for stream,data in [('stdout',result.stdout),('stderr',result.stderr)]:
 path=base/('worker-metadata.'+stream+'.txt');path.write_bytes(data);row[stream]={'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
records.append(row);assert result.returncode==0
(base/'environment-checks.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps({'source_sha':config['source_sha'],'observations':len(records),'outcome':'PASS','scientific_backend_execution':False}))
