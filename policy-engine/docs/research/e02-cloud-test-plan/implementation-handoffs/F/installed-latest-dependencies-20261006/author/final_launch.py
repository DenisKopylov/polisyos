from pathlib import Path
import json,os,pytest,sys
scratch=Path('/workspace/e02-F-20261006-receipts/installed-latest');kind=sys.argv[1]
assert kind in ('wheel','sdist')
manifest=json.loads((scratch/(kind+'-setup-manifest.json')).read_text());consumer=Path(manifest['consumer'])
os.environ['E02_TEST_DOWHY_WORKER_PYTHON']='/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python'
os.environ['E02_DOWHY_FIXTURE_PATH']=str(consumer/'test_dowhy_worker.py')
os.environ['E02_GCM_FIXTURE_PATH']=str(consumer/'test_gcm_backend_contract.py')
os.environ['E02_PROFILE_EXPECTED_JSON']=str(scratch/(kind+'-setup-manifest.json'))
assert sys.flags.isolated==1
mode=sys.argv[2] if len(sys.argv)>2 else 'native'
assert mode in ('native','b220')
selectors=[str(consumer/'test_installed_worker_profile.py')] if mode=='native' else [str(consumer/'test_causal_graph_cache_rows.py')]+[str(consumer/'test_performance_primitives.py')+'::'+name for name in ['test_cached_adjacency_reuse','test_cached_adjacency_eviction','test_published_graph_rejects_nested_topology_mutation','test_warmed_derived_rows_are_not_reused_after_copy_update']]
argv=['-o','addopts=','-p','no:cacheprovider','-v','-s']+selectors
import polisyos.ir.analytics.causal_graph as cg
import polisyos.foundry.methods.catalog.causal._dowhy_worker as bridge
site=Path(manifest['site']).resolve()
assert Path(cg.__file__).resolve().is_relative_to(site)
assert Path(bridge.__file__).resolve().is_relative_to(site)
assert not any('/src' in p for p in sys.path)
print(json.dumps({'mode':mode,'origins':{'causal_graph':cg.__file__,'worker_bridge':bridge.__file__}}))
print(json.dumps({'manifest':manifest,'pytest_args':argv,'sys_path':sys.path,'isolated':sys.flags.isolated,'environment':{k:v for k,v in os.environ.items() if k.startswith('E02_')}}))
raise SystemExit(pytest.main(argv))
