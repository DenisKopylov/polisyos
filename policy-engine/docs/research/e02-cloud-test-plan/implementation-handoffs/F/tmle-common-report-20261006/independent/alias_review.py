from __future__ import annotations
import hashlib,json,os,pathlib,subprocess,time
SCRATCH=pathlib.Path(__file__).parent;REPO=pathlib.Path('/workspace/e02-F-tmle-20261006');ROOT=REPO/'policy-engine';SHA='6c711bd2d4f1b6bf851c42a5f3d22b795efb020d';PYTHON='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
paths=['policy-engine/src/polisyos/foundry/methods/causal/__init__.py','policy-engine/src/polisyos/foundry/methods/causal/_facade.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/__init__.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py','policy-engine/src/polisyos/ir/analytics/causal.py']
def source():
 head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip();assert head==SHA
 rows=[]
 for path in paths:
  b=(REPO/path).read_bytes();assert b==subprocess.check_output(['git','-C',str(REPO),'show',SHA+':'+path]);rows.append({'path':path,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 return {'sha':head,'tree':subprocess.check_output(['git','-C',str(REPO),'rev-parse',SHA+'^{tree}'],text=True).strip(),'files':rows}
script="""import inspect,json,pickle
from dataclasses import fields
from polisyos.foundry.methods import causal as public
from polisyos.foundry.methods.catalog import causal as catalog
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
from polisyos.foundry.methods.catalog.causal.tmle_core import ATENuisanceContract
assert public.TMLEEstimator is catalog.TMLEEstimator is TMLEEstimator
factory=TMLEEstimator.report_from_result
assert public.TMLEEstimator.report_from_result is factory and catalog.TMLEEstimator.report_from_result is factory
assert pickle.loads(pickle.dumps(factory)) is factory
assert len(TMLEEstimator.signature.parameters)==len(fields(ATENuisanceContract))==32
assert {s.name for s in TMLEEstimator.signature.output_slots}=={'result','report','envelope'}
print(json.dumps({'public_catalog_class_identity':True,'factory_identity_pickle':True,'fqn':TMLEEstimator.signature.fqn,'factory_signature':str(inspect.signature(factory)),'native_parameter_count':32,'output_slots':['result','report','envelope']}))
"""
argv=[PYTHON,'-c',script];env=dict(os.environ,PYTHONPATH=str(ROOT/'src')+':'+str(ROOT),PYTHONDONTWRITEBYTECODE='1')
begin=source();start=time.time();out=SCRATCH/'alias.stdout.txt';err=SCRATCH/'alias.stderr.txt'
with out.open('wb') as o,err.open('wb') as e:result=subprocess.run(argv,cwd=ROOT,env=env,stdout=o,stderr=e)
def bind(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
receipt={'argv':argv,'cwd':str(ROOT),'environment_overrides':{k:env[k] for k in ['PYTHONPATH','PYTHONDONTWRITEBYTECODE']},'source_begin':begin,'source_end':source(),'exit_code':result.returncode,'elapsed_seconds':time.time()-start,'stdout':bind(out),'stderr':bind(err),'script':bind(pathlib.Path(__file__))}
(SCRATCH/'alias.execution.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'exit_code':result.returncode,'stdout':receipt['stdout'],'stderr':receipt['stderr']}))
