from pathlib import Path
import subprocess,json,hashlib,datetime,time,resource,os,sys
root=Path('/workspace/e02-F-installed-worker-20261006');scratch=Path('/workspace/e02-F-20261006-receipts/installed-latest')
name=sys.argv[1];cwd=Path(sys.argv[2]);argv=sys.argv[3:]
expected='5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6'
def identity():
 return {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip(),'status':subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)}
before=identity();assert before['head']==expected
start=datetime.datetime.now(datetime.timezone.utc).isoformat();clock=time.monotonic();env=os.environ.copy();env.pop('PYTHONPATH',None)
with (scratch/(name+'.stdout')).open('wb') as out,(scratch/(name+'.stderr')).open('wb') as err:
 p=subprocess.run(argv,cwd=cwd,env=env,stdout=out,stderr=err)
after=identity();assert before==after
outputs={}
for stream in ('stdout','stderr'):
 path=scratch/(name+'.'+stream);data=path.read_bytes();outputs[stream]={'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
meta={'argv':argv,'cwd':str(cwd),'source_before':before,'source_after':after,'started_utc':start,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'wall_seconds':time.monotonic()-clock,'child_maxrss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'exit_code':p.returncode,'outcome':'PASS' if p.returncode==0 else 'FAIL','outputs':outputs,'environment':{'PYTHONPATH':env.get('PYTHONPATH'),'worker_python':env.get('E02_TEST_DOWHY_WORKER_PYTHON')}}
(scratch/(name+'.json')).write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2));raise SystemExit(p.returncode)
