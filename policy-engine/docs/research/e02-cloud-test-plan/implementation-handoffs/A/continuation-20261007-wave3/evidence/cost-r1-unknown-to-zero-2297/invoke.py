import importlib.util,pathlib,pytest
root=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('e02_cost_r1',root/'run_probe.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
test_file=pathlib.Path.cwd()/'tests/unit/runtime/http/test_nl_pipeline_materialization.py'
probe=module.UnknownCostToZeroRemovalProbe(test_file,root/'result.json')
raise SystemExit(pytest.main([str(test_file)+'::'+module.TARGET_TEST,'-o','addopts=','--import-mode=importlib','--strict-markers','-q','--junitxml='+str(root/'junit.xml'),'--basetemp='+str(root/'pytest-basetemp')],plugins=[probe]))
