from pathlib import Path
import hashlib,json,resource,subprocess,time
root=Path('/dev/shm/e02-orch03-20261008/c09');out=Path('/dev/shm/e02-orch03-20261008/c09-scratch');product=root/'policy-engine'
python='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
cmd=[python,'-m','pytest','-q',
 'tests/unit/foundry/uncertainty/test_mean_estimator_error.py',
 'tests/unit/foundry/uncertainty/test_monte_carlo.py',
 'tests/unit/foundry/uncertainty/test_monte_carlo_b194.py',
 'tests/unit/foundry/uncertainty/test_adaptive_stopping.py',
 'tests/unit/scientist/methods/backtesting/test_evaluator_interval_admission.py::test_actual_backtest_keeps_unavailable_intervals_non_gating_after_cas_readback[interval0]',
 'tests/unit/scientist/methods/backtesting/test_evaluator_interval_admission.py::test_same_intervals_changed_observations_change_actual_persisted_coverage',
 f'--basetemp={out/"mean-final"}',f'--junitxml={out/"mean-final.junit.xml"}','-o',f'cache_dir={out/"mean-final-cache"}']
identity=subprocess.run(['git','rev-parse','HEAD','HEAD^{tree}'],cwd=root,capture_output=True,text=True,check=True).stdout.splitlines();start=time.monotonic()
with (out/'mean-final.stdout.txt').open('wb') as stdout,(out/'mean-final.stderr.txt').open('wb') as stderr:
 try:r=subprocess.run(cmd,cwd=product,stdout=stdout,stderr=stderr,timeout=240);rc=r.returncode;interrupted=None
 except subprocess.TimeoutExpired:rc=None;interrupted='harness_timeout_240_seconds'
meta={'source_sha':identity[0],'source_tree':identity[1],'cwd':str(product),'command':cmd,'returncode':rc,'interrupted':interrupted,'wall_seconds':time.monotonic()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'outputs':{}}
for suffix in ['stdout.txt','stderr.txt','junit.xml']:
 p=out/('mean-final.'+suffix)
 if p.exists():meta['outputs'][suffix]={'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(out/'mean-final.execution.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2));print((out/'mean-final.stdout.txt').read_text()[-7000:])
