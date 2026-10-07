"""Read-only exact provider-bound consumer investigation capture."""
from pathlib import Path
import hashlib,json,os,platform,subprocess,sys,time
ROOT=Path('/workspace/e02-F-closeout-20261006')
OUT=Path('/tmp/e02-F-continuation-20261006/tmle-bridge-investigation')
REF='4a038c2ebf0c4fd79dcc084c983ed7b76756a488'
PY='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
paths=['policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/nuisance_layer.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py','policy-engine/src/polisyos/ir/analytics/causal.py','policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py','policy-engine/src/polisyos/scientist/compute/runner.py','policy-engine/src/polisyos/scientist/compute/job_spec.py','policy-engine/src/polisyos/scientist/orchestration/engine/context.py','policy-engine/src/polisyos/scientist/orchestration/engine/runner/local_pool.py','policy-engine/src/polisyos/scientist/orchestration/engine/runner/_activity_worker.py','policy-engine/src/polisyos/scientist/orchestration/engine/runner/serialization.py']
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def bind(path):
 data=git('show',f'{REF}:{path}');assert (ROOT/path).read_bytes()==data
 return dict(git_ref=REF,path=path,git_blob=git('rev-parse',f'{REF}:{path}').decode().strip(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def binding(p):
 data=Path(p).read_bytes();return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
mode=sys.argv[1];inputs=[bind(p) for p in paths]
env=dict(os.environ);env['PYTHONPATH']=str(ROOT/'policy-engine/src')+':'+str(ROOT/'policy-engine/tools');env['TMPDIR']='/tmp'
argv=[PY,str(OUT/'probe-v2.py'),mode]
start=time.perf_counter();p=subprocess.run(argv,cwd=ROOT/'policy-engine',env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180);wall=time.perf_counter()-start
stdout=OUT/(mode+'-v2.stdout.txt');stderr=OUT/(mode+'-v2.stderr.txt');stdout.write_bytes(p.stdout);stderr.write_bytes(p.stderr)
assert [bind(path) for path in paths]==inputs
receipt=dict(source_sha=REF,source_tree=git('rev-parse',REF+'^{tree}').decode().strip(),command=argv,cwd=str(ROOT/'policy-engine'),environment=dict(interpreter=PY,python=sys.version,platform=platform.platform(),PYTHONPATH=env['PYTHONPATH'],TMPDIR='/tmp',inherited_environment=True,quota_introduced=False),input_closure=inputs,exit_code=p.returncode,wall_seconds=wall,outcome='PASS' if p.returncode==0 else 'ERROR',output=str(stdout),output_ref=binding(stdout),stderr_ref=binding(stderr),replayer=binding(OUT/'probe-v2.py'),actual_worktree_status=git('status','--porcelain=v1').decode(),scope='Investigation of actual current boundary behavior; no positive EvalSafety/identification/shared admitted production budget claim')
(OUT/(mode+'-v2.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(mode=mode,exit=p.returncode,wall_seconds=wall,receipt=binding(OUT/(mode+'-v2.json')))))
