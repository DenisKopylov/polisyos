import subprocess,sys,pathlib,os,json,hashlib,time,resource
root=pathlib.Path('/workspace/e02-F-cau-20261006')
out=pathlib.Path('/workspace/e02-F-20261006-receipts/cau')
label=sys.argv[1]; argv=sys.argv[2:]
env=os.environ.copy();env['PYTHONPATH']='src:.:tools';env['PYTHONDONTWRITEBYTECODE']='1'
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
before={'sha':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'diff_sha256':hashlib.sha256(subprocess.check_output(['git','diff'],cwd=root)).hexdigest()}
start=time.time();p=subprocess.run(argv,cwd=root/'policy-engine',env=env,capture_output=True)
for ext,content in [('stdout',p.stdout),('stderr',p.stderr)]: (out/f'{label}.{ext}.txt').write_bytes(content)
after={'sha':git('rev-parse','HEAD'),'diff_sha256':hashlib.sha256(subprocess.check_output(['git','diff'],cwd=root)).hexdigest()}
r={'argv':argv,'cwd':str(root/'policy-engine'),'source_before':before,'source_after':after,'exit':p.returncode,'duration_seconds':time.time()-start,'maxrss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'environment':{'PYTHONPATH':env['PYTHONPATH'],'PYTHONDONTWRITEBYTECODE':'1','thread_cpu_quotas':'none'},'outputs':{ext:{'path':str(out/f'{label}.{ext}.txt'),'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()} for ext,content in [('stdout',p.stdout),('stderr',p.stderr)]}}
(out/f'{label}.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
