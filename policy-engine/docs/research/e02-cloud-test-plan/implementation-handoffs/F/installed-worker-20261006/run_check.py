from pathlib import Path
import sys,json,subprocess,os,time,resource
name=sys.argv[1];argv=json.loads(sys.argv[2]);cwd=sys.argv[3]
scratch=Path('/workspace/e02-F-20261006-receipts/installed-worker');root=Path('/workspace/e02-F-installed-worker-20261006')
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
env={**os.environ,'PYTHONPATH':'src:.'}
start=time.monotonic()
with (scratch/(name+'.stdout.txt')).open('wb') as out,(scratch/(name+'.stderr.txt')).open('wb') as err:
    result=subprocess.run(argv,cwd=cwd,env=env,stdout=out,stderr=err)
r={'argv':argv,'cwd':cwd,'source_sha_start':source,'source_sha_end':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'environment':{'PYTHONPATH':env['PYTHONPATH']},'exit':result.returncode,'wall_s':time.monotonic()-start,'rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}
(scratch/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r));print((scratch/(name+'.stdout.txt')).read_text()[-1200:]);print((scratch/(name+'.stderr.txt')).read_text()[-1200:])
raise SystemExit(result.returncode)
