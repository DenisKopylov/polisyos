from pathlib import Path
import hashlib, json, subprocess, sys
root=Path('/workspace/e02-F-installed-worker-20261006');scratch=Path('/workspace/e02-F-20261006-receipts/installed-latest');kind=sys.argv[1]
assert kind in ('wheel','sdist')
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert source=='5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6'
artifact=scratch/'dist'/('policy_engine-0.1.0-py3-none-any.whl' if kind=='wheel' else 'policy_engine-0.1.0.tar.gz')
env=scratch/(kind+'-env');consumer=scratch/(kind+'-consumer')
commands=[['uv','venv',str(env),'--python','/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'],['uv','pip','install','--python',str(env/'bin/python'),'--no-deps',str(artifact)]]
import os
cache=Path('/tmp/e02-F-installed-latest-uv-cache');cache.mkdir(exist_ok=True)
setup_env=os.environ.copy();setup_env['UV_CACHE_DIR']=str(cache)
for argv in commands:subprocess.run(argv,check=True,env=setup_env)
site=env/'lib/python3.14/site-packages';(site/'e02-readonly-third-party.pth').write_text('/workspace/e02-F-closeout-20261006/policy-engine/.venv/lib/python3.14/site-packages\n')
consumer.mkdir(exist_ok=True)
carriers={}
for name in ['test_installed_worker_profile.py','test_dowhy_worker.py','test_gcm_backend_contract.py','test_causal_graph_cache_rows.py','test_performance_primitives.py']:
    path=('policy-engine/tests/unit/ir/' if name=='test_causal_graph_cache_rows.py' else 'policy-engine/tests/unit/foundry/methods/catalog/causal/')+name
    b=subprocess.check_output(['git','show',source+':'+path],cwd=root)
    (consumer/name).write_bytes(b)
    carriers[name]={'source_path':path,'git_blob':subprocess.check_output(['git','rev-parse',source+':'+path],cwd=root,text=True).strip(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
assets={}
for name in ['worker.py','protocol.py','pyproject.toml','uv.lock','.python-version','README.md']:
    path='policy-engine/workers/dowhy-014/'+name
    b=subprocess.check_output(['git','show',source+':'+path],cwd=root)
    assets[name]={'source_path':path,'git_blob':subprocess.check_output(['git','rev-parse',source+':'+path],cwd=root,text=True).strip(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
manifest={'source_sha':source,'kind':kind,'artifact':str(artifact),'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'artifact_bytes':artifact.stat().st_size,'python':str(env/'bin/python'),'site':str(site),'consumer':str(consumer),'commands':commands,'carriers':carriers,'assets':assets,'uv_cache_dir':str(cache),'dependency_isolation':'owned installed product; readonly shared third-party directory via literal .pth, no shared environment mutation; not independently resolved dependencies'}
(scratch/(kind+'-setup-manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
