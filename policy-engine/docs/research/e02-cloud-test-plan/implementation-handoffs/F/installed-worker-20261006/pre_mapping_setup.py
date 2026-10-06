from pathlib import Path
import hashlib,json,subprocess
root=Path('/workspace/e02-F-installed-worker-20261006');scratch=Path('/workspace/e02-F-20261006-receipts/installed-worker')
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
commands=[['uv','venv',str(scratch/'pre-mapping-env'),'--python','/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'],['uv','pip','install','--python',str(scratch/'pre-mapping-env/bin/python'),'--no-deps',str(scratch/'pre-mapping-dist/policy_engine-0.1.0-py3-none-any.whl')]]
for argv in commands:subprocess.run(argv,check=True)
site=scratch/'pre-mapping-env/lib/python3.14/site-packages';(site/'e02-readonly-third-party.pth').write_text('/workspace/e02-F-closeout-20261006/policy-engine/.venv/lib/python3.14/site-packages\n')
consumer=scratch/'pre-mapping-consumer';consumer.mkdir(exist_ok=True)
(consumer/'test_installed_worker_profile.py').write_bytes((scratch/'test_installed_worker_profile.py').read_bytes())
for kind,name in [('dowhy','test_dowhy_worker.py'),('gcm','test_gcm_backend_contract.py')]:
    (consumer/name).write_bytes((root/'policy-engine/tests/unit/foundry/methods/catalog/causal'/name).read_bytes())
assets={}
for name in ['worker.py','protocol.py','pyproject.toml','uv.lock','.python-version','README.md']:
    path='policy-engine/workers/dowhy-014/'+name
    b=subprocess.check_output(['git','show',source+':'+path],cwd=root)
    assets[name]={'git_blob':subprocess.check_output(['git','rev-parse',source+':'+path],cwd=root,text=True).strip(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
(scratch/'pre-mapping-profile-expected.json').write_text(json.dumps({'source_sha':source,'assets':assets},indent=2)+'\n')
print(json.dumps({'source_sha':source,'setup_commands':commands,'neutral_consumer':str(consumer),'asset_denominator':6}))
