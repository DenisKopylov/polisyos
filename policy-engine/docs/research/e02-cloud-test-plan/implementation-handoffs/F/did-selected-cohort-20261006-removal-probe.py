import ast,inspect,sys,json,hashlib,pathlib,pytest
from polisyos.foundry.methods.catalog.causal import did
mode=sys.argv[1]
if mode=='share':
 fn=did._selected_participation_influence
 source=inspect.getsource(fn);tree=ast.parse(source);node=tree.body[0]
 loops=[n for n in node.body if isinstance(n,ast.For) and 'cohort_values[group] - point' in ast.unparse(n)]
 assert len(loops)==1
 node.body.remove(loops[0]);removed=ast.unparse(loops[0]);exec(compile(ast.fix_missing_locations(tree),'<share-term-removal>','exec'),did.__dict__)
 selector='tests/unit/foundry/methods/catalog/causal/test_did_selected_participation.py::test_unequal_followup_selected_target_and_ratio_influence'
elif mode=='uncentered':
 fn=did._run_staggered_did;source=inspect.getsource(fn)
 old='np.abs(\n            unit_draws @ influence / (data.n_units * standard_error)\n        )'
 if old not in source:
  old='np.abs(unit_draws @ influence / (data.n_units * standard_error))'
 assert source.count(old)==1
 changed=source.replace(old,'np.abs(att / standard_error + unit_draws @ influence / (data.n_units * standard_error))');removed=old
 exec(compile(changed,'<uncentered-null-removal>','exec'),did.__dict__)
 selector='tests/unit/foundry/methods/catalog/causal/test_did_selected_participation.py::test_same_centered_studentized_law_drives_null_test_and_interval'
else:raise ValueError(mode)
print(json.dumps({'mode':mode,'canonical_owner_file':did.__file__,'canonical_owner_sha256':hashlib.sha256(pathlib.Path(did.__file__).read_bytes()).hexdigest(),'removed_mechanism':removed,'receipt_markers_preserved':True,'scope':'isolated process function-code mutation only; canonical frozen source untouched'}))
raise SystemExit(pytest.main(['-o','addopts=','-q','-p','no:cacheprovider',selector]))
