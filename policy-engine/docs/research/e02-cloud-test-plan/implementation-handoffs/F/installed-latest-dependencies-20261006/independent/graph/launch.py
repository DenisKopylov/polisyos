import json,os,pathlib,sys,pytest
root=pathlib.Path('/workspace/e02-F-20261006-receipts/installed-latest');m=json.loads((root/'wheel-setup-manifest.json').read_text());c=pathlib.Path(m['consumer']);site=pathlib.Path(m['site']).resolve()
assert sys.flags.isolated
os.environ['E02_TEST_DOWHY_WORKER_PYTHON']='/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python'
os.environ['E02_DOWHY_FIXTURE_PATH']=str(c/'test_dowhy_worker.py');os.environ['E02_GCM_FIXTURE_PATH']=str(c/'test_gcm_backend_contract.py');os.environ['E02_PROFILE_EXPECTED_JSON']=str(root/'wheel-setup-manifest.json')
import polisyos.ir.analytics.causal_graph as graph
import polisyos.foundry.methods.catalog.causal._dowhy_worker as bridge
assert pathlib.Path(graph.__file__).resolve().is_relative_to(site) and pathlib.Path(bridge.__file__).resolve().is_relative_to(site)
assert not any('/src' in p for p in sys.path)
argv=['-o','addopts=','-p','no:cacheprovider','-q','-s',str(c/'test_causal_graph_cache_rows.py')]+[str(c/'test_performance_primitives.py')+'::'+n for n in ['test_cached_adjacency_reuse','test_cached_adjacency_eviction','test_published_graph_rejects_nested_topology_mutation','test_warmed_derived_rows_are_not_reused_after_copy_update']]+[str(c/'test_installed_worker_profile.py')+'::'+n for n in ['test_public_canonical_helpers_and_pure_report_factory_identity','test_installed_true_gcm_job_and_scientist_source_bound_interval_consumer']]+['/workspace/e02-F-20261006-receipts/final-root/b220-independent-review/test_b220_independent.py']
print(json.dumps({'source_sha':m['source_sha'],'site':str(site),'interpreter':sys.executable,'isolated':sys.flags.isolated,'sys_path':sys.path,'origins':{'graph':graph.__file__,'bridge':bridge.__file__},'argv':argv}))
raise SystemExit(pytest.main(argv))
