import hashlib,json,os,subprocess,time
from pathlib import Path
OUT=Path('/tmp/e02-F-graph-profile-20261007/api-review/combined4ee')
REPO=Path('/workspace/e02-F-closeout-20261006')
EXPECTED='4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
def guard():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=REPO,text=True).strip()
    diff=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=REPO,text=True)
    staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=REPO,text=True)
    assert head==EXPECTED and not diff and not staged
    return {'head':head,'tree':tree,'tracked_clean':True}
argv=['/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python',str(OUT/'probe_b204.py')]
env={'PYTHONPATH':str(REPO/'policy-engine/src')+':'+str(REPO/'policy-engine/tools')+':'+str(REPO/'policy-engine'),'PYTHONDONTWRITEBYTECODE':'1'}
before=guard();start=time.perf_counter()
r=subprocess.run(argv,cwd=REPO/'policy-engine',env={**os.environ,**env},capture_output=True)
(OUT/'b204.stdout.json').write_bytes(r.stdout);(OUT/'b204.stderr.txt').write_bytes(r.stderr)
def ref(p):
    raw=p.read_bytes();return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
record={'argv':argv,'cwd':str(REPO/'policy-engine'),'env_overrides':env,'source_before':before,'source_after':guard(),'exit_code':r.returncode,'wall_seconds':time.perf_counter()-start,'stdout':ref(OUT/'b204.stdout.json'),'stderr':ref(OUT/'b204.stderr.txt'),'replayer':ref(OUT/'probe_b204.py'),'scope':'native known DGP/checker; no authority or optional worker claim'}
(OUT/'b204.execution.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2));raise SystemExit(r.returncode)
