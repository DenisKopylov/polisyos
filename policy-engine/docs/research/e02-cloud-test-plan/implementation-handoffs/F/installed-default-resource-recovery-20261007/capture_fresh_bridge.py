from pathlib import Path
import hashlib,json,os,subprocess,time
OUT=Path(__file__).resolve().parent;PACKET=Path('/tmp/e02-F-continuation-20261007/foundry/installed-default-resource-forward');config=json.loads((PACKET/'installed-config.json').read_text())
argv=[config['installed_pythons']['wheel'],'-I',str(OUT/'fresh_graph_bridge.py')];cwd=PACKET/'wheel-consumer';env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1';start=time.monotonic()
p=subprocess.run(argv,cwd=cwd,env=env,capture_output=True)
r={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'argv':argv,'cwd':str(cwd),'environment':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':'1'},'exit_code':p.returncode,'seconds':time.monotonic()-start,'scope':'One missing registered MethodJob->Node->selectedCAS->fresh-I child proof on wheel only.'}
for name,body in [('stdout',p.stdout),('stderr',p.stderr)]:
 path=OUT/('fresh-bridge.'+name+'.txt');path.write_bytes(body);r[name]={'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
(OUT/'fresh-bridge.command.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
raise SystemExit(p.returncode)
