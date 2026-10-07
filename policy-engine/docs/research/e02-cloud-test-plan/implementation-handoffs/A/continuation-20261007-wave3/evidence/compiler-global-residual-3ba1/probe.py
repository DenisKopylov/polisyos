import hashlib,importlib.util,json,pathlib,subprocess
repo=pathlib.Path(__file__).resolve().parents[4]
p=repo/'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/A/compiler-full/census_tracked_python.py'
spec=importlib.util.spec_from_file_location('e02_census_probe',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sources={'global': 'from importlib import import_module as load\ndef f():\n    global load\n    load = lambda name: None\n    return load("polisyos.data_requirement.compiler")\n', 'nonlocal':'def outer():\n    from importlib import import_module as load\n    def f():\n        nonlocal load\n        load = lambda name: None\n        return load("polisyos.data_requirement.compiler")\n    return f()\n'}
rows=[]
for name,source in sources.items():
 namespace={};exec(compile(source,'controlled-'+name+'.py','exec'),namespace)
 actual=namespace['f' if name=='global' else 'outer']()
 findings=m.source_findings('controlled-'+name+'.py',source,set())
 rows.append({'case':name,'source':source,'runtime_result':actual,'reported_dynamic_imports':findings['dynamic_import_literals'],'reported_unresolved':findings['unresolved_reflective_calls'],'false_positive_confirmed':actual is None and bool(findings['dynamic_import_literals']) and not findings['unresolved_reflective_calls']})
head=subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],cwd=repo,text=True).splitlines()
print(json.dumps({'candidate':head,'scanner_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'scope':'Controlled global/nonlocal rebinding residual; no actual tracked retired caller asserted','cases':rows,'residual_confirmed':all(x['false_positive_confirmed'] for x in rows)},indent=2))
raise SystemExit(0 if all(x['false_positive_confirmed'] for x in rows) else 1)
