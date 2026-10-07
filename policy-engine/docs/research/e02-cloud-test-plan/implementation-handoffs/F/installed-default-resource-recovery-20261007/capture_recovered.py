from pathlib import Path
import hashlib,json,os,subprocess,sys,time
out=Path(__file__).resolve().parent;name=sys.argv[1]
assert name in ['review_custody','review_native_outputs']
argv=[sys.executable,str(out/(name+'.py'))];env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1';start=time.monotonic()
p=subprocess.run(argv,cwd=out,env=env,capture_output=True)
r={'source_sha':'519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82','source_tree':'750d28da94f372848fe6b2db5f88db95b94cb57d','argv':argv,'cwd':str(out),'environment':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':'1'},'exit_code':p.returncode,'seconds':time.monotonic()-start,'scope':'Read-only saved-byte evidence recheck, not native suite or scientific estimator replay.'}
for stream,body in [('stdout',p.stdout),('stderr',p.stderr)]:
 path=out/(name+'.'+stream+'.txt');path.write_bytes(body);r[stream]={'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
(out/(name+'.command.json')).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));sys.exit(p.returncode)
