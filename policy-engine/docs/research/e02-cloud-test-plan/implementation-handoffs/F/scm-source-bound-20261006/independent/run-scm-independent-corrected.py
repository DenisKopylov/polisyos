import os,sys,json,subprocess,pathlib,hashlib,time,resource
root=pathlib.Path('/workspace/e02-F-graph-20261006');target='1e70434b8e5a04661bb22c02362854ca14714436';out=pathlib.Path('/workspace/e02-F-20261006-receipts/cau');label=sys.argv[1];argv=sys.argv[2:]
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
paths=subprocess.check_output(['git','diff','--name-only','198076863e143dea9f89f02734b13d50dae3eed5',target],cwd=root,text=True).splitlines();paths=[p for p in paths if p.endswith('.py') or '/workers/' in p or '/schemas/' in p]
def hashes():return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
before=hashes();expected={p:hashlib.sha256(subprocess.check_output(['git','show',target+':'+p],cwd=root)).hexdigest() for p in paths};assert before==expected
state={'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'target_sha':target,'target_tree':git('rev-parse',target+'^{tree}'),'source_hashes':before};env={**os.environ,'PYTHONPATH':'src:.:tools','PYTHONDONTWRITEBYTECODE':'1'};start=time.time();p=subprocess.run(argv,cwd=root/'policy-engine',env=env,capture_output=True);after=hashes();assert before==after
outputs={}
for ext,data in [('stdout',p.stdout),('stderr',p.stderr)]:
 file=out/(label+'.'+ext+'.txt');file.write_bytes(data);outputs[ext]={'path':str(file),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
r={'schema':'policyos.e02.independent_execution.v1','target_sha':target,'source_before':state,'head_after':git('rev-parse','HEAD'),'checked_source_hashes_unchanged':True,'command':argv,'cwd':str(root/'policy-engine'),'environment':{'PYTHONPATH':'src:.:tools','PYTHONDONTWRITEBYTECODE':'1','thread_cpu_quotas':'none'},'exit':p.returncode,'wall_seconds':time.time()-start,'maxrss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'outputs':outputs};(out/(label+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
