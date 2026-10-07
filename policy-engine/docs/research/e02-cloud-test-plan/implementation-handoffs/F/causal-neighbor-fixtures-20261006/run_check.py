import hashlib,json,os,pathlib,resource,subprocess,sys,time
root=pathlib.Path('/workspace/e02-F-graph-20261006');out=pathlib.Path(__file__).parent
sha=sys.argv[1];name=sys.argv[2];argv=sys.argv[3:]
paths=['policy-engine/tests/unit/foundry/methods/catalog/causal/'+n for n in ['test_id_engine_extensions.py','test_twin_amn_graph.py','test_compile_estimand_do_calculus_prepass.py']]+['policy-engine/src/polisyos/foundry/methods/catalog/causal/'+n for n in ['admg_ops.py','do_calculus.py','amn.py','id_engine/core.py','id_engine/transport.py','estimand_compiler.py']]+['policy-engine/src/polisyos/ir/analytics/causal_graph.py','policy-engine/src/polisyos/ir/analytics/estimand.py']
def git(*a):return subprocess.check_output(['git',*a],cwd=root)
def bindings():
 assert git('rev-parse','HEAD').decode().strip()==sha
 assert not git('status','--porcelain')
 return [{'source_path':p,'source_sha':sha,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for p in paths for b in [git('show',sha+':'+p)] if not ((root/p).read_bytes()!=b and (_ for _ in ()).throw(AssertionError(p)))]
before=bindings();env=dict(os.environ,PYTHONPATH=str(root/'policy-engine/src')+':'+str(root/'policy-engine/tools')+':'+str(root/'policy-engine'),PYTHONDONTWRITEBYTECODE='1')
t=time.monotonic();r=subprocess.run(argv,cwd=root/'policy-engine',env=env,capture_output=True);wall=time.monotonic()-t
refs=[]
for kind,b in [('stdout',r.stdout),('stderr',r.stderr)]:
 p=out/(name+'.'+kind+'.txt');p.write_bytes(b);refs.append({'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
after=bindings();assert before==after
record={'name':name,'command':argv,'source_sha':sha,'source_tree':git('rev-parse',sha+'^{tree}').decode().strip(),'environment':{'cwd':str(root/'policy-engine'),'PYTHONPATH':env['PYTHONPATH'],'PYTHONDONTWRITEBYTECODE':'1','interpreter':argv[0],'shared_environment_readonly':True},'exit_code':r.returncode,'check':'PASS' if r.returncode==0 else 'FAIL','wall_s':wall,'rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'source_begin':before,'source_end':after,'output_refs':refs}
(out/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['name','source_sha','source_tree','exit_code','check','wall_s','output_refs']}))
