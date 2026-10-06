from pathlib import Path
import hashlib,json,os,subprocess,time,importlib.metadata,sys
O=Path(__file__).parent;F=O/'fixture-current'/'policy-engine';PY=Path('/workspace/e02-E-continuation-20261006/policy-engine/.venv/bin/python');results=[]
source_inputs={p:{'sha256':hashlib.sha256((F/p).read_bytes()).hexdigest(),'bytes':(F/p).stat().st_size} for p in ['src/polisyos/core/__init__.py','src/polisyos/ir/api.py','src/polisyos/foundry/execute/__init__.py','src/polisyos/core/artifacts/__init__.py','src/polisyos/core/canon/__init__.py','src/polisyos/core/registry/__init__.py','src/polisyos/ir/analytics/uncertainty.py','src/polisyos/ir/analytics/forecasting_uncertainty.py','src/polisyos/foundry/execute/_internal/models/__init__.py','src/polisyos/foundry/execute/_internal/snapshots/__init__.py','architecture/production_quality/method_catalog_dependency_digest_domains.toml']}
for label,mutant,expected in [('owner-final-positive',None,0),('owner-final-snapshot-noop','snapshot-persist-noop',1),('owner-final-forecast-noop','forecast-persist-noop',1)]:
 args=[str(PY),str(O/'api_probe.py'),'--phase','after-owner-patch','--cas-root',str(O/('cas-'+label))]
 if mutant:args+=['--mutant',mutant]
 start=time.time();env=dict(os.environ,UV_NO_SYNC='1',PYTHONPATH=str(F/'src'));p=subprocess.run(args,cwd=F,env=env,capture_output=True,text=True);(O/(label+'.stdout')).write_text(p.stdout+p.stderr)
 result={'label':label,'command':args,'cwd':str(F),'environment_overrides':{'UV_NO_SYNC':'1','PYTHONPATH':str(F/'src')},'exit_code':p.returncode,'expected_exit_code':expected,'control_outcome':'PASS' if p.returncode==expected else 'FAIL','wall_seconds':time.time()-start,'script_sha256':hashlib.sha256((O/'api_probe.py').read_bytes()).hexdigest()};results.append(result); print(json.dumps(result));assert p.returncode==expected
assert all(hashlib.sha256((F/p).read_bytes()).hexdigest()==v['sha256'] for p,v in source_inputs.items())
output={'fixture_is_git_candidate':False,'owner_admission':'not_ratified','python':sys.version,'backend_versions':{n:importlib.metadata.version(n) for n in ['numpy','scipy','jax','jaxlib','pydantic','jsonschema']},'input_source_before_after_equal':True,'source_inputs':source_inputs,'checks':results}
(O/'native-execution.json').write_text(json.dumps(output,indent=2)+'\n')
