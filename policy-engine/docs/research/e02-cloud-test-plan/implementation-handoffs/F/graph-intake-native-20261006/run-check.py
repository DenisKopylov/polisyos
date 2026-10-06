import hashlib,json,os,pathlib,resource,subprocess,sys,time
root=pathlib.Path('/workspace/e02-F-graph-intake-20261006');out=pathlib.Path('/workspace/e02-F-20261006-receipts/graph-intake');label=sys.argv[1];argv=sys.argv[2:]
paths=['policy-engine/src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py']
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
def source():return {'sha':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'hashes':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},'diff_sha256':hashlib.sha256(subprocess.check_output(['git','diff'],cwd=root)).hexdigest()}
before=source();input_file=root/'policy-engine/tests/unit/scientist/methods/causal/test_reconcile_graph_intake_contract.py';inputs={'path':str(input_file),'bytes':input_file.stat().st_size,'sha256':hashlib.sha256(input_file.read_bytes()).hexdigest()};env={**os.environ,'PYTHONPATH':'src:.:tools','PYTHONDONTWRITEBYTECODE':'1'};start=time.time();p=subprocess.run(argv,cwd=root/'policy-engine',env=env,capture_output=True);after=source();assert before==after,'Source moved while check executed'
outputs={}
for ext,data in [('stdout',p.stdout),('stderr',p.stderr)]:
 file=out/(label+'.'+ext+'.txt');file.write_bytes(data);outputs[ext]={'path':str(file),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
d={'schema':'policyos.e02.execution.v1','source_before':before,'source_after':after,'input':inputs,'argv':argv,'cwd':str(root/'policy-engine'),'environment':{'PYTHONPATH':'src:.:tools','PYTHONDONTWRITEBYTECODE':'1','thread_cpu_quotas':'none'},'exit':p.returncode,'wall_seconds':time.time()-start,'maxrss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'outputs':outputs};(out/(label+'.json')).write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['exit','wall_seconds','outputs']}))
