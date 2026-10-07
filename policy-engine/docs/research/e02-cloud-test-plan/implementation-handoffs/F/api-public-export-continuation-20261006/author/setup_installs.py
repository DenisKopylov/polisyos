from pathlib import Path
import hashlib,json,subprocess,sys
b=Path('/tmp/e02-F-continuation-20261006/api');python=Path('/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python')
shared_site=python.parent.parent/'lib/python3.14/site-packages'
records=[]
for kind,archive in [('wheel',b/'dist-5484/policy_engine-0.1.0-py3-none-any.whl'),('sdist',b/'dist-5484/policy_engine-0.1.0.tar.gz')]:
 env=b/(kind+'-env-5484');cmds=[['uv','venv','--python',str(python),str(env)],['uv','pip','install','--python',str(env/'bin/python'),'--no-deps',str(archive)]]
 for index,argv in enumerate(cmds):
  out=subprocess.run(argv,cwd=b,capture_output=True);prefix=b/(kind+f'-setup-{index}')
  record={'argv':argv,'cwd':str(b),'exit_code':out.returncode,'artifact':str(archive),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
  for stream,data in [('stdout',out.stdout),('stderr',out.stderr)]:
   p=Path(str(prefix)+'.'+stream);p.write_bytes(data);record[stream]={'path':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
  records.append(record)
  (b/'setup-installs-records.json').write_text(json.dumps(records,indent=2)+'\n')
  if out.returncode:raise SystemExit(out.returncode)
 site=env/'lib/python3.14/site-packages'
 (site/'e02_readonly_dependencies.pth').write_text(str(shared_site)+'\n')
 print(json.dumps({'kind':kind,'site':str(site),'dependency_directory':str(shared_site)}))
