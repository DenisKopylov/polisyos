import ast,inspect,sys,json,hashlib,pathlib,pytest
from polisyos.foundry.methods.catalog.causal import did
mode=sys.argv[1]
if mode=='no_pre_guard':
 tree=ast.parse(inspect.getsource(did._run_standard_did));fn=tree.body[0]
 gates=[n for n in fn.body if isinstance(n,ast.If) and ast.unparse(n.test)=='t0 <= 0'];assert len(gates)==1
 gates[0].test=ast.Constant(False)
 exec(compile(ast.fix_missing_locations(tree),'<zero-pre-guard-removal>','exec'),did.__dict__)
 selector='tests/unit/remediation/test_cau_01.py::test_cau_01_standard_did_rejects_zero_pre_period'
elif mode=='cluster_as_hc1':
 did._ols_cluster_cr0=lambda x,y,clusters:did._ols_hc1(x,y)
 selector='tests/unit/foundry/methods/catalog/causal/test_did_diagnostics_ownership.py::test_independent_statsmodels_covariance_on_group_labelled_design[cluster]'
elif mode=='fixed_95_critical':
 did._normal_critical_value=lambda level:1.959963984540054
 selector='tests/unit/remediation/test_cau_01.py::test_cau_01_confidence_level_changes_did_interval'
else:raise ValueError(mode)
print(json.dumps({'mode':mode,'source_path':did.__file__,'source_sha256':hashlib.sha256(pathlib.Path(did.__file__).read_bytes()).hexdigest(),'marker_fields_preserved':True,'scope':'isolated native function-code mutation only, no canonical source writes'}))
raise SystemExit(pytest.main(['-o','addopts=','-q','-p','no:cacheprovider',selector]))
