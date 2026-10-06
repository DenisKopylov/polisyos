from pathlib import Path
import hashlib,json,os,pytest,sys
scratch=Path('/workspace/e02-F-20261006-receipts/installed-worker');consumer=scratch/'pre-mapping-consumer'
os.environ['E02_TEST_DOWHY_WORKER_PYTHON']='/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python'
os.environ['E02_DOWHY_FIXTURE_PATH']=str(consumer/'test_dowhy_worker.py')
os.environ['E02_GCM_FIXTURE_PATH']=str(consumer/'test_gcm_backend_contract.py')
os.environ['E02_PROFILE_EXPECTED_JSON']=str(scratch/'pre-mapping-profile-expected.json')
argv=['-o','addopts=','-v','-s',str(consumer/'test_installed_worker_profile.py')]
print(json.dumps({'consumer':str(consumer),'pytest_args':argv,'source_sha':'d3961a101ca6bb0aa9d3e927cc6d62eae09c403d','sys_path':sys.path,'isolated':sys.flags.isolated,'environment':{k:v for k,v in os.environ.items() if k.startswith('E02_')}}))
raise SystemExit(pytest.main(argv))
