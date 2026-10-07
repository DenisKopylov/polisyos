import pathlib,subprocess,sys,json
root=pathlib.Path('/workspace/e02-F-cau-20261006');app='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python';rows=[]
for rel in ['policy-engine/benchmarks/interference/policy_did_interference.py','policy-engine/benchmarks/natural_experiments/policy_natural_experiments.py']:
 for ref in ['198076863e143dea9f89f02734b13d50dae3eed5','HEAD']:
  content=subprocess.check_output(['git','show',ref+':'+rel],cwd=root)
  argv=[app,'-m','ruff','check','--output-format','json','--stdin-filename',rel.removeprefix('policy-engine/'),'-']
  p=subprocess.run(argv,cwd=root/'policy-engine',input=content,capture_output=True)
  print(json.dumps({'source_ref':ref,'path':rel,'command':argv,'exit':p.returncode,'stdout':p.stdout.decode(),'stderr':p.stderr.decode()}))
  diagnostics=json.loads(p.stdout);rows.append({'ref':ref,'path':rel,'exit':p.returncode,'diagnostics':diagnostics})
for rel in sorted({r['path'] for r in rows}):
 before=[r for r in rows if r['path']==rel and r['ref']!='HEAD'][0]['diagnostics'];after=[r for r in rows if r['path']==rel and r['ref']=='HEAD'][0]['diagnostics']
 # Full checker row/diagnostic equality including source-sensitive messages (line text
 # differs only in relocated import name, so compare actual code/location/message).
 def d(items,delta=0):return [(v['code'],{'column':v['location']['column'],'row':v['location']['row']+delta},v['message']) for v in items]
 delta=2 if '/interference/' in rel else 0
 assert d(before,delta)==d(after),(rel,d(before,delta),d(after))
print(json.dumps({'outcome':'PASS_DIAGNOSTIC_EQUALITY','whole_benchmark_lint':'FAIL_BOTH_BASE_AND_HEAD','scope':'Exact two full admitted benchmark source files; no broad repository lint claim.'}))
