import hashlib,json,os,pathlib,subprocess,time
s=pathlib.Path(__file__).parent;repo=pathlib.Path('/workspace/e02-F-closeout-20261006');root=repo/'policy-engine';sha='12dce5675edfd345663591fd3219f2f8ea5e4fc2';path='policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py'
def source():
 raw=(repo/path).read_bytes();assert raw==subprocess.check_output(['git','-C',str(repo),'show',sha+':'+path])
 return {'sha':sha,'tree':subprocess.check_output(['git','-C',str(repo),'rev-parse',sha+'^{tree}'],text=True).strip(),'checkout_head':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),'node':{'path':path,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}}
def bind(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
script="""import inspect,json,pickle
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as node
from polisyos.foundry.methods import causal as public
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
assert node.TMLEEstimator is public.TMLEEstimator is TMLEEstimator
assert node.TMLEEstimator.report_from_result is public.TMLEEstimator.report_from_result
assert pickle.loads(pickle.dumps(public.TMLEEstimator.report_from_result)) is node.TMLEEstimator.report_from_result
print(json.dumps({'node_public_canonical_class_identity':True,'factory_identity':True,'factory_pickle_identity':True,'node_source':node.__file__,'fqn':node.TMLEEstimator.signature.fqn,'factory_signature':str(inspect.signature(node.TMLEEstimator.report_from_result))}))
"""
argv=[str(root/'.venv/bin/python'),'-c',script];env=dict(os.environ,PYTHONPATH=str(root/'src')+':'+str(root),PYTHONDONTWRITEBYTECODE='1');begin=source();start=time.time();out=s/'final-import.stdout.txt';err=s/'final-import.stderr.txt'
with out.open('wb') as o,err.open('wb') as e:observed=subprocess.run(argv,cwd=root,env=env,stdout=o,stderr=e)
receipt={'argv':argv,'cwd':str(root),'environment_overrides':{k:env[k] for k in ['PYTHONPATH','PYTHONDONTWRITEBYTECODE']},'source_begin':begin,'source_end':source(),'elapsed_seconds':time.time()-start,'exit_code':observed.returncode,'stdout':bind(out),'stderr':bind(err),'replayer':bind(pathlib.Path(__file__))}
(s/'final-import.execution.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'exit_code':observed.returncode,'stdout':receipt['stdout'],'stderr':receipt['stderr']}))
