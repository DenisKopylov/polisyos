import hashlib,json,os,platform,resource,subprocess,sys,time
from pathlib import Path
lane=Path('/workspace/e02-E-backtest-20261006')
out=Path('/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/welfare')
label=sys.argv[1];argv=sys.argv[2:]
def git(*args):return subprocess.check_output(['git','-C',str(lane),*args],text=True).strip()
def snapshot():
    paths=git('ls-files','policy-engine/src/polisyos').splitlines()
    items={p:hashlib.sha256((lane/p).read_bytes()).hexdigest() for p in paths}
    changed=git('diff','--name-only','5d4e01011a0b7e0a3954decdb622a9e9cf1fb787','884681db485b7466b183a206f83bbe0635f86ca3','--','policy-engine/src').splitlines()
    return dict(head=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'),
        src_file_count=len(items),src_sha256=hashlib.sha256(json.dumps(items,sort_keys=True).encode()).hexdigest(),
        changed_source_sha256={p:items[p] for p in changed},
        diff_from_frozen=git('diff','884681db485b7466b183a206f83bbe0635f86ca3','--','policy-engine/src'))
before=snapshot();env=dict(os.environ,UV_NO_SYNC='1',PYTHONPATH=str(lane/'policy-engine/src'),
    WELFARE_REVIEW_OUTPUT=str(out/(label+'-origins-artifacts.json')))
start=time.monotonic()
with (out/(label+'.log')).open('w') as stream:
    process=subprocess.run(argv,cwd=lane/'policy-engine',env=env,stdout=stream,stderr=subprocess.STDOUT)
after=snapshot();rusage=resource.getrusage(resource.RUSAGE_CHILDREN)
receipt=dict(label=label,argv=argv,cwd=str(lane/'policy-engine'),exit_code=process.returncode,
    wall_seconds=time.monotonic()-start,maxrss_kib=rusage.ru_maxrss,
    source_base='5d4e01011a0b7e0a3954decdb622a9e9cf1fb787',source_candidate='884681db485b7466b183a206f83bbe0635f86ca3',
    source_tree='b9cdce22cd8af3bee3cda176207242a8381cbe1b',before=before,after=after,
    source_unchanged=before['src_sha256']==after['src_sha256'] and not after['diff_from_frozen'],
    environment={k:env.get(k) for k in ('PYTHONPATH','UV_NO_SYNC','WELFARE_REVIEW_OUTPUT','OMP_NUM_THREADS',
        'OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','XLA_FLAGS')},python=sys.version,executable=sys.executable,
    stdout_sha256=hashlib.sha256((out/(label+'.log')).read_bytes()).hexdigest())
(out/(label+'-receipt.json')).write_text(json.dumps(receipt,indent=2))
print(json.dumps({k:receipt[k] for k in ('label','exit_code','wall_seconds','source_unchanged')},indent=2))
print((out/(label+'.log')).read_text()[-6500:])
sys.exit(process.returncode)
