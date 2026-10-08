from pathlib import Path
import hashlib,json,os,subprocess,time
root=Path('/workspace/e02-F-graph-20261006');out=Path('/tmp/e02-F-continuation-20261007/api/graph-intake-review-647')
sha='647f5d35362c2a5d7ad32283b804a5b03ea56e83';tree='6b699cac11fb1fe5b317ed0ccfc76940e5958906';base='3e6b47e88e0f25474df8cffa213a5e09e7b7affa'
def git(*args):return subprocess.check_output(['git',*args],cwd=root)
assert git('rev-parse','HEAD').decode().strip()==sha
assert git('rev-parse','HEAD^{tree}').decode().strip()==tree
assert not git('status','--porcelain','--untracked-files=no')
paths=git('diff','--name-only',base,sha).decode().splitlines()
inputs=set(paths)|{
'policy-engine/src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py',
'policy-engine/src/polisyos/foundry/methods/catalog/causal/query_preservation.py',
'policy-engine/src/polisyos/foundry/methods/catalog/causal/composition_failure_cards.py',
'policy-engine/src/polisyos/ir/analytics/cross_graph.py',
'policy-engine/src/polisyos/ir/analytics/causal_graph.py',
'policy-engine/src/polisyos/ir/analytics/alignment_certification.py',
'policy-engine/tests/unit/scientist/methods/causal/test_reconcile_causal_graph_node.py',
'policy-engine/tests/unit/foundry/methods/catalog/causal/test_graph_reconciliation.py'}
records=[]
for p in sorted(inputs):
 b=git('show',sha+':'+p);assert (root/p).read_bytes()==b
 records.append({'path':p,'git_blob':git('rev-parse',sha+':'+p).decode().strip(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'changed_in_delta':p in paths})
(out/'full-delta.diff').write_bytes(git('diff','--full-index',base,sha))
(out/'source-bindings.json').write_text(json.dumps({'target_sha':sha,'tree':tree,'base':base,'base_tree':git('rev-parse',base+'^{tree}').decode().strip(),'changed_paths':paths,'bindings':records,'tracked_clean':True},indent=2)+'\n')
code="""import sys,json,importlib,importlib.util,importlib.metadata
mods=['polisyos.ir.analytics.causal_graph','polisyos.ir.analytics.cross_graph','polisyos.ir.analytics.alignment_certification','polisyos.foundry.methods.catalog.causal.graph_reconciliation','polisyos.foundry.methods.catalog.causal.query_preservation','polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph']
print(json.dumps({'python':sys.version,'executable':sys.executable,'origins':{m:importlib.import_module(m).__file__ for m in mods},'backend_presence':{m:importlib.util.find_spec(m) is not None for m in ['dowhy','econml']},'packages':{m:importlib.metadata.version(m) for m in ['pytest','numpy','networkx','pydantic']}},indent=2))
"""
env=os.environ.copy();env['PYTHONPATH']=str(root/'policy-engine/src')+':'+str(root/'policy-engine');env['PYTHONDONTWRITEBYTECODE']='1'
argv=['/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python','-c',code];start=time.monotonic();result=subprocess.run(argv,cwd=root/'policy-engine',env=env,capture_output=True)
(out/'profile.stdout').write_bytes(result.stdout);(out/'profile.stderr').write_bytes(result.stderr)
(out/'profile.json').write_text(json.dumps({'target_sha':sha,'tree':tree,'argv':argv,'cwd':str(root/'policy-engine'),'env':{k:env[k] for k in ['PYTHONPATH','PYTHONDONTWRITEBYTECODE']},'exit_code':result.returncode,'seconds':time.monotonic()-start},indent=2)+'\n')
assert result.returncode==0
assert git('rev-parse','HEAD').decode().strip()==sha and not git('status','--porcelain','--untracked-files=no')
print(result.stdout.decode());print({'bindings':len(records),'changed_paths':len(paths)})
