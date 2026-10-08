import importlib.util,json
spec=importlib.util.spec_from_file_location('controls','/tmp/e02-F-continuation-20261006/cau/diagnostic-consumer-controls.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
assert c.fresh.diagnostics[0].passed is True and c.old.diagnostics[0].passed is False
try:c.proposal.verify_selected_did_diagnostics({'report':c.fresh},observational_data=c.data)
except ValueError as e:print(json.dumps({'control':'retain positive no_detected_pretrend report, change only time_treatment3→2 to current not_testable','target_binding_unchanged':c.old.method_params['target_binding']==c.fresh.method_params['target_binding'],'outcome':'REFUSED','reason':str(e)}))
else:raise AssertionError('stale positive diagnostic accepted against untestable current window')
