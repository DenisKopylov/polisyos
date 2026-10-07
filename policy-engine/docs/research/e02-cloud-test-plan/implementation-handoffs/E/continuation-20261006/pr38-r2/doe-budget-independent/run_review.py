import hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
LANE=Path('/workspace/e02-E-doe-20261006');OUT=Path('/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/doe-budget')
SOURCE='70c4a14fc872f5ef66437d958ba63884ecdda168';BASE='a2677935015e8a0e7f2dfd5412b671e13fb3175a'
label=sys.argv[1];argv=sys.argv[2:]
def git(*args):return subprocess.check_output(['git','-C',str(LANE),*args],text=True).strip()
def snapshot():
 paths=git('ls-files','policy-engine/src').splitlines();items={p:hashlib.sha256((LANE/p).read_bytes()).hexdigest() for p in paths}
 return dict(head=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'),source_count=len(items),source_digest=hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest(),frozen_source_delta=git('diff',SOURCE,'--','policy-engine/src'),changed_source_sha256={p:items[p] for p in git('diff','--name-only',BASE,SOURCE,'--','policy-engine/src').splitlines()})
before=snapshot();assert not before['frozen_source_delta'];env=dict(os.environ,UV_NO_SYNC='1',PYTHONPATH=str(LANE/'policy-engine/src'),REVIEW_LANE=str(LANE),REVIEW_SOURCE=SOURCE,REVIEW_OUTPUT=str(OUT/(label+'-origins-artifacts.json')))
start=time.monotonic()
with (OUT/(label+'.stdout.txt')).open('w') as stream:p=subprocess.run(argv,cwd=LANE/'policy-engine',env=env,stdout=stream,stderr=subprocess.STDOUT)
after=snapshot();assert before['source_digest']==after['source_digest'] and not after['frozen_source_delta']
dictout=dict(label=label,base=BASE,candidate=SOURCE,tree=git('rev-parse',SOURCE+'^{tree}'),argv=argv,cwd=str(LANE/'policy-engine'),exit_code=p.returncode,wall_seconds=time.monotonic()-start,before=before,after=after,source_unchanged=True,environment={k:env.get(k) for k in ['PYTHONPATH','UV_NO_SYNC','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','XLA_FLAGS','REVIEW_OUTPUT']},wrapper_executable=sys.executable,wrapper_python=sys.version,stdout_sha256=hashlib.sha256((OUT/(label+'.stdout.txt')).read_bytes()).hexdigest())
(OUT/(label+'-receipt.json')).write_text(json.dumps(dictout,indent=2)+'\n');print(json.dumps({k:dictout[k] for k in ['label','candidate','exit_code','wall_seconds','source_unchanged']},indent=2));print((OUT/(label+'.stdout.txt')).read_text()[-6000:]);sys.exit(p.returncode)
