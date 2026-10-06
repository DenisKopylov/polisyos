from pathlib import Path
import json,os,pytest,sys
scratch=Path('/workspace/e02-F-20261006-receipts/installed-worker');kind=sys.argv[1]
assert kind in ('wheel','sdist')
manifest=json.loads((scratch/(kind+'-setup-manifest.json')).read_text());consumer=Path(manifest['consumer'])
os.environ['E02_TEST_DOWHY_WORKER_PYTHON']='/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python'
os.environ['E02_DOWHY_FIXTURE_PATH']=str(consumer/'test_dowhy_worker.py')
os.environ['E02_GCM_FIXTURE_PATH']=str(consumer/'test_gcm_backend_contract.py')
os.environ['E02_PROFILE_EXPECTED_JSON']=str(scratch/(kind+'-setup-manifest.json'))
assert sys.flags.isolated==1
argv=['-o','addopts=','-v','-s',str(consumer/'test_installed_worker_profile.py')]
print(json.dumps({'manifest':manifest,'pytest_args':argv,'sys_path':sys.path,'isolated':sys.flags.isolated,'environment':{k:v for k,v in os.environ.items() if k.startswith('E02_')}}))
raise SystemExit(pytest.main(argv))
