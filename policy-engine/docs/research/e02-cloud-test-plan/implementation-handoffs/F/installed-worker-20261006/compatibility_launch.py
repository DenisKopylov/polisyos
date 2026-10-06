from pathlib import Path
import hashlib,json,os,pytest,subprocess,sys
scratch=Path('/workspace/e02-F-20261006-receipts/installed-worker');root=Path('/workspace/e02-F-installed-worker-20261006');kind=sys.argv[1];source='ab56a0f3414c6e903f7dcdaaa7b7ed540b1923c5'
manifest=json.loads((scratch/(kind+'-setup-manifest.json')).read_text());consumer=Path(manifest['consumer']);site=Path(manifest['site']);bindings={}
for target,path in [('test_installed_facade_contract.py','policy-engine/tests/unit/foundry/methods/catalog/causal/test_installed_facade_contract.py'),('census.py','policy-engine/docs/research/e02-cloud-test-plan/verification/F/api-20261006/census.py')]:
 b=subprocess.check_output(['git','show',source+':'+path],cwd=root);(consumer/target).write_bytes(b);bindings[target]={'source_path':path,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
os.environ['E02_CENSUS_SCRIPT']=str(consumer/'census.py')
argv=['-o','addopts=','-q',str(consumer/'test_installed_facade_contract.py')]
print(json.dumps({'source_sha':source,'carriers':bindings,'isolated':sys.flags.isolated,'sys_path':sys.path,'argv':argv}));assert sys.flags.isolated
code=pytest.main(argv)
origins={n:m.__file__ for n,m in sys.modules.copy().items() if n.startswith('polisyos') and getattr(m,'__file__',None)}
assert all(Path(p).is_relative_to(site) for p in origins.values())
print(json.dumps({'product_origins':origins,'product_origin_count':len(origins),'source_origin_violations':0},sort_keys=True))
raise SystemExit(code)
