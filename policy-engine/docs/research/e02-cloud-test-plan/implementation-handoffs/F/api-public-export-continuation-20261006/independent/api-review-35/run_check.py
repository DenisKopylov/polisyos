"""Independent read-only API review execution and immutable source binding."""
import hashlib,json,os,pathlib,resource,subprocess,sys,time
root=pathlib.Path('/workspace/e02-F-api-20261006')
out=pathlib.Path('/tmp/e02-F-continuation-20261006/graph/api-review-35')
sha='35b1808c63fa84dd0555ff9043e0aaffe9831e7b'
tree='0002a76b106d74a3bc5fb341b578c1093e6c193c'
base='449d32909928caf39382f4ff02ac74b0adf277eb'
def git(*args):return subprocess.check_output(['git',*args],cwd=root)
def bound_source():
 assert git('rev-parse','HEAD').decode().strip()==sha
 assert git('rev-parse','HEAD^{tree}').decode().strip()==tree
 assert not git('status','--porcelain')
 paths=git('diff','--name-only',base,sha).decode().splitlines()
 refs=[]
 for path in paths:
  body=git('show',sha+':'+path)
  assert (root/path).read_bytes()==body,path
  refs.append({'source_path':path,'source_sha':sha,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
 return refs
name=sys.argv[1];argv=sys.argv[2:]
start_refs=bound_source()
env=dict(os.environ,PYTHONPATH=str(root/'policy-engine/src')+':'+str(root/'policy-engine/tools')+':'+str(root/'policy-engine'),PYTHONDONTWRITEBYTECODE='1')
start=time.monotonic();process=subprocess.run(argv,cwd=root/'policy-engine',env=env,capture_output=True);elapsed=time.monotonic()-start
outputs=[]
for label,body in [('stdout',process.stdout),('stderr',process.stderr)]:
 path=out/(name+'.'+label+'.txt');path.write_bytes(body)
 outputs.append({'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
end_refs=bound_source();assert end_refs==start_refs
record={'name':name,'command':argv,'source_sha':sha,'source_tree':tree,'slice_base_sha':base,'environment':{'PYTHONPATH':env['PYTHONPATH'],'PYTHONDONTWRITEBYTECODE':'1','cwd':str(root/'policy-engine'),'interpreter':argv[0],'shared_environment_readonly':True,'cloud_quota_introduced':False},'exit_code':process.returncode,'check':'PASS' if process.returncode==0 else 'FAIL','wall_seconds':elapsed,'rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'source_begin':start_refs,'source_end':end_refs,'output_refs':outputs}
(out/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
