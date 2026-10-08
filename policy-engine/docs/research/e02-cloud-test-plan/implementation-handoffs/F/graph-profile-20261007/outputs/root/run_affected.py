from __future__ import annotations
import hashlib,json,os,subprocess,time
from pathlib import Path
root=Path('/workspace/e02-F-closeout-20261006')
out=Path('/tmp/e02-F-graph-profile-20261007/root/final-wave');out.mkdir(exist_ok=True)
sha='4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
py=str(root/'policy-engine/.venv/bin/python')
env=dict(os.environ,PYTHONPATH=str(root/'policy-engine/src'))
def git(*args):return subprocess.check_output(['git',*args],cwd=root).decode().strip()
assert git('rev-parse','HEAD')==sha
assert git('branch','--show-current')=='codex/e02-F-closeout-20261006'
test='policy-engine/tests/unit/foundry/methods/catalog/causal/test_graph_reconciliation.py'
names=['test_simple_cycle_converts_min_confidence_edge_to_lagged_edge','test_more_than_eight_cycles_triggers_fallback_removal_warning','test_cycle_edge_with_lag_depth_limit_is_removed','test_diagnostics_truncated_when_hard_limits_exceeded','test_compose_scm_fragments_refuses_other_semantic_profiles','test_compose_scm_fragments_preserves_exact_observed_interface','test_compose_scm_fragments_allows_supported_internal_cyclic_scc','test_compose_scm_fragments_promotes_output_to_admg_when_any_fragment_is_admg']
pyfiles=[p for p in git('diff','--name-only','25cdea9064ddea2c3a812fd68670076bd4b088cb',sha).splitlines() if p.endswith('.py')]
checks=[('graph-consumers',[py,'-m','pytest','-q','policy-engine/tests/unit/scientist/methods/causal/test_graph_intake_current_content.py',*[test+'::'+n for n in names],'policy-engine/tests/unit/remediation/test_grf_03.py','--junitxml='+str(out/'graph-consumers.junit.xml')]),('format',[py,'-m','ruff','format','--check',*pyfiles]),('ruff-runtime-tests',[py,'-m','ruff','check',*[p for p in pyfiles if '/benchmarks/' not in p]]),('ruff-benchmark',[py,'-m','ruff','check',*[p for p in pyfiles if '/benchmarks/' in p]]),('source-diff-check',['git','diff','--check','25cdea9064ddea2c3a812fd68670076bd4b088cb',sha])]
records=[]
for name,argv in checks:
 start=time.monotonic();p=subprocess.run(argv,cwd=root,env=env,capture_output=True)
 stdout=out/(name+'.stdout');stderr=out/(name+'.stderr');stdout.write_bytes(p.stdout);stderr.write_bytes(p.stderr)
 r={'name':name,'argv':argv,'cwd':str(root),'target_sha':sha,'target_tree':git('rev-parse',sha+'^{tree}'),'environment':{'PYTHONPATH':env['PYTHONPATH'],'parent_python':py},'returncode':p.returncode,'check_result':'PASS' if p.returncode==0 else ('ERROR' if p.returncode<0 else 'FAIL'),'wall_seconds':time.monotonic()-start,'stdout':str(stdout),'stderr':str(stderr),'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
 records.append(r);(out/'checks.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps({'name':name,'returncode':p.returncode,'wall_seconds':r['wall_seconds']}),flush=True)
assert git('rev-parse','HEAD')==sha
