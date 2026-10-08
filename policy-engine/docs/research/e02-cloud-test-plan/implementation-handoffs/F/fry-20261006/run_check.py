import argparse, hashlib, json, os, resource, subprocess, time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('argv',nargs=argparse.REMAINDER);a=p.parse_args()
cmd=a.argv[1:] if a.argv[:1]==['--'] else a.argv
root=Path('/workspace/e02-F-20261006-receipts/fry');cwd=Path('/workspace/e02-F-fry-20261006/policy-engine')
env=dict(os.environ,PYTHONPATH='src:.:/workspace/e02-F-20261006-receipts/fry',UV_NO_SYNC='1',UV_PROJECT_ENVIRONMENT='/workspace/e02-F-closeout-20261006/policy-engine/.venv',E02_REPORT_PATH=str(root/(a.name+'.pytest.json')))
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=cwd,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=cwd,text=True).strip()
before=subprocess.check_output(['git','status','--porcelain'],cwd=cwd,text=True)
started=time.time()
with (root/(a.name+'.stdout.txt')).open('wb') as out,(root/(a.name+'.stderr.txt')).open('wb') as err:
 r=subprocess.run(cmd,cwd=cwd,env=env,stdout=out,stderr=err)
after=subprocess.check_output(['git','status','--porcelain'],cwd=cwd,text=True)
refs=[]
for path in [root/(a.name+'.stdout.txt'),root/(a.name+'.stderr.txt')]:
 b=path.read_bytes();refs.append(dict(path=str(path),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b)))
receipt=dict(source_sha=sha,source_tree=tree,cwd=str(cwd),argv=cmd,started_unix=started,exit_code=r.returncode,wall_s=time.time()-started,child_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,environment={k:env[k] for k in ['PYTHONPATH','UV_NO_SYNC','UV_PROJECT_ENVIRONMENT','E02_REPORT_PATH']},git_status_before=before,git_status_after=after,outputs=refs)
(root/(a.name+'.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
