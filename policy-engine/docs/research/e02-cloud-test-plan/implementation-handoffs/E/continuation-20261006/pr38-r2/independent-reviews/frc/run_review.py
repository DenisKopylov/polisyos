import hashlib,json,os,platform,resource,subprocess,sys,time
from pathlib import Path
lane=Path('/workspace/e02-E-frc-20261006')
out=Path('/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/frc')
label=sys.argv[1];argv=sys.argv[2:]
def git(*args):return subprocess.check_output(['git','-C',str(lane),*args],text=True).strip()
def snapshot():
    paths=git('ls-files','policy-engine/src/polisyos').splitlines()
    items={p:hashlib.sha256((lane/p).read_bytes()).hexdigest() for p in paths}
    changed=git('diff','--name-only','22998874b5f32434c462065baaca44a78e967f91','8486baad6fdef8063cfaad80b15f6b6d8532460a','--','policy-engine/src').splitlines()
    return dict(head=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'),
        src_file_count=len(items),src_sha256=hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest(),
        changed_source_sha256={p:items[p] for p in changed},
        diff_from_frozen=git('diff','8486baad6fdef8063cfaad80b15f6b6d8532460a','--','policy-engine/src'))
before=snapshot();env=dict(os.environ,UV_NO_SYNC='1',PYTHONPATH=str(lane/'policy-engine/src'),
    FRC_REVIEW_OUTPUT=str(out/(label+'-origins-artifacts.json')))
start=time.monotonic()
with (out/(label+'.log')).open('w') as stream:
    process=subprocess.run(argv,cwd=lane/'policy-engine',env=env,stdout=stream,stderr=subprocess.STDOUT)
after=snapshot();rusage=resource.getrusage(resource.RUSAGE_CHILDREN)
receipt=dict(label=label,argv=argv,cwd=str(lane/'policy-engine'),exit_code=process.returncode,
    wall_seconds=time.monotonic()-start,maxrss_kib=rusage.ru_maxrss,
    source_base='22998874b5f32434c462065baaca44a78e967f91',source_candidate='8486baad6fdef8063cfaad80b15f6b6d8532460a',
    source_tree='3be4935b1bfa426a71f8581bc376fa322145fe31',before=before,after=after,
    source_unchanged=before['src_sha256']==after['src_sha256'] and not after['diff_from_frozen'],
    environment={k:env.get(k) for k in ('PYTHONPATH','UV_NO_SYNC','FRC_REVIEW_OUTPUT','OMP_NUM_THREADS',
        'OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','XLA_FLAGS')},python=sys.version,executable=sys.executable,
    stdout_sha256=hashlib.sha256((out/(label+'.log')).read_bytes()).hexdigest())
(out/(label+'-receipt.json')).write_text(json.dumps(receipt,indent=2))
print(json.dumps({k:receipt[k] for k in ('label','exit_code','wall_seconds','source_unchanged')},indent=2))
print((out/(label+'.log')).read_text()[-6500:])
sys.exit(process.returncode)
