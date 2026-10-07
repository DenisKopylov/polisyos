from pathlib import Path
import hashlib,json,os,platform,subprocess,time
ROOT=Path('/workspace/e02-F-tmle-20261006')
OUT=Path('/tmp/e02-F-continuation-20261007/foundry/fit-composed-review')
SHA='0c81614f5aa737a4b26c6c74044955a842b26cf4'
PYTHON='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode()
assert git('rev-parse','HEAD').strip()==SHA and git('status','--porcelain=v1')==''
paths=git('diff-tree','--no-commit-id','--name-only','-r',SHA).splitlines()
bindings=[]
for p in paths:
 b=subprocess.check_output(['git','show',f'{SHA}:{p}'],cwd=ROOT)
 assert b==(ROOT/p).read_bytes()
 bindings.append({'path':p,'blob':git('rev-parse',f'{SHA}:{p}').strip(),'sha256':hashlib.sha256(b).hexdigest(),'size_bytes':len(b)})
env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'policy-engine/src')+':'+str(ROOT/'policy-engine/tools')
argv=[PYTHON,'-m','pytest','-o','addopts=','-q','-s','-ra','tests/unit/scientist/governance/test_tmle_persisted_evidence_consumers.py','--basetemp='+str(OUT/'native-tmp'),'--junitxml='+str(OUT/'native.xml')]
spec={'source_sha':SHA,'source_tree':git('rev-parse',SHA+'^{tree}').strip(),'source_refs':bindings,'argv':argv,'cwd':str(ROOT/'policy-engine'),'environment':{'PYTHONPATH':env['PYTHONPATH'],'python':PYTHON,'worker':None,'backend':'native NumPy/scikit-learn TMLE; no DoWhy/EconML claim','quotas':'none introduced'},'prior_status':'clean'}
(OUT/'native-command.json').write_text(json.dumps(spec,indent=2)+'\n')
start=time.monotonic()
with (OUT/'native.stdout.txt').open('wb') as stdout,(OUT/'native.stderr.txt').open('wb') as stderr:
 result=subprocess.run(argv,cwd=ROOT/'policy-engine',env=env,stdout=stdout,stderr=stderr)
spec.update(exit_code=result.returncode,wall_seconds=time.monotonic()-start,source_guard_unchanged=git('rev-parse','HEAD').strip()==SHA and git('status','--porcelain=v1')=='')
for key in ['stdout','stderr']:
 p=OUT/f'native.{key}.txt';b=p.read_bytes();spec[key]={'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'size_bytes':len(b)}
(OUT/'native-result.json').write_text(json.dumps(spec,indent=2)+'\n');print(json.dumps(spec,indent=2));assert spec['source_guard_unchanged'] and result.returncode==0
