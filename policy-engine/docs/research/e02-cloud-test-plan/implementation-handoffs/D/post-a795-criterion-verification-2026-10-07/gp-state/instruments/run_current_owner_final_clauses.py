"""Actual native wrapper consumer wave; fitted corpus/restore is not a new posterior oracle."""
from pathlib import Path
import datetime
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time

ROOT=Path('/dev/shm/e02-D-oct07-continuation');PRODUCT=ROOT/'policy-engine'
assert Path.cwd().resolve()==PRODUCT.resolve(), 'run from actual product directory'
HARNESS_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
EXPECTED=sys.argv[1];OUT=Path(sys.argv[2]);MODE=sys.argv[3];OUT.mkdir(parents=True,exist_ok=False)
ASSESS='a795967a80818a61fbc939a8d1b1ec8b0fca6477';ASSESS_TREE='2cd7e7058eeb0431b0571b30af3ad80b9a3c2668'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
def write(name,data):(OUT/name).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
def emit(name,data):
    with (OUT/name).open('a') as f:f.write(json.dumps({'timestamp':datetime.datetime.now(datetime.UTC).isoformat(),**data})+'\n')
tracked=git('ls-files','policy-engine/src','policy-engine/tests','policy-engine/tools','policy-engine/pyproject.toml','policy-engine/ruff.toml','policy-engine/uv.lock').splitlines()
def snap():return {'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'status':git('status','--porcelain'),'complete_executable_input_denominator':len(tracked),'missing':[p for p in tracked if not(ROOT/p).is_file()],'inputs':{p:sha(ROOT/p) for p in tracked if(ROOT/p).is_file()}}
def origins():
    result={}
    for name,module in list(sys.modules.items()):
        filename=getattr(module,'__file__',None)
        if filename:
            p=Path(filename)
            if p.is_file():result[name]={'path':str(p),'sha256':sha(p)}
    return result
before=snap();write('before.json',before);assert before['head']==EXPECTED and not before['status'] and not before['missing']
changed_assessed=set(git('diff','--name-only',ASSESS,EXPECTED).splitlines());assert not set(tracked)&changed_assessed
write('assessed-source-equivalence.json',{'actual_execution_head':EXPECTED,'actual_execution_tree':before['tree'],'assessed_product_source':ASSESS,'assessed_product_tree':ASSESS_TREE,'complete_declared_executable_input_denominator':len(tracked),'changed_executable_inputs':[],'all_head_delta_paths':sorted(changed_assessed),'whole_catalog_tree_identity':False})
import pytest,torch,botorch,gpytorch,hnswlib
backend={n:importlib.metadata.version(n) for n in ('torch','botorch','gpytorch','numpy','scipy','pytest','hnswlib')}
assert torch.__version__=='2.10.0+cu128' and botorch.__version__=='0.16.1' and gpytorch.__version__=='1.15.1'
from polisyos.scientist.methods.search.strategies import _deps,bayesian
actual_fit=_deps.fit_gpytorch_mll
fit_id=0
def values(value):
    if torch.is_tensor(value):return value.detach().cpu().tolist()
    if isinstance(value,(list,tuple)):return [values(v) for v in value]
    if isinstance(value,dict):return {k:values(v) for k,v in value.items()}
    return value

def observed_fit(mll,*args,**kwargs):
    global fit_id
    fit_id+=1
    identity=fit_id;model=mll.model
    def fitted():return {'model_class':type(model).__name__,'mll_class':type(mll).__name__,'train_inputs':values(model.train_inputs),'train_targets':values(model.train_targets),'weights':values(model.state_dict())}
    emit('fit-events.jsonl',{'event':'actual_mll_start','identity':identity,'state':fitted(),'real_callable_module':actual_fit.__module__,'real_callable_name':actual_fit.__qualname__})
    result=actual_fit(mll,*args,**kwargs)
    emit('fit-events.jsonl',{'event':'actual_mll_return','identity':identity,'state':fitted()});return result
_deps.fit_gpytorch_mll=observed_fit;bayesian.fit_gpytorch_mll=observed_fit
from polisyos.scientist.methods.search.strategies import multi_objective
multi_objective.fit_gpytorch_mll=observed_fit
plan=json.loads((Path(__file__).parent/'scope-plan-final-clauses.json').read_text()); selectors=plan[MODE]['selectors']; negative=None
argv=['-o','addopts=','-p','no:cacheprovider','-q','-s','-ra','--basetemp='+str(OUT/'basetemp'),'--junitxml='+str(OUT/'junit.xml'),*selectors]
command={'wrapper_argv':sys.argv,'harness_file':str(Path(__file__).resolve()),'harness_sha256':HARNESS_SHA256,'actual_cwd':str(Path.cwd().resolve()),'pytest_argv':argv,'cwd':str(PRODUCT),'source':before['head'],'tree':before['tree'],'backend':backend,'python':sys.version,'executable':sys.executable,'sys_path':sys.path,'env_overrides':{k:os.environ.get(k) for k in ('PYTHONDONTWRITEBYTECODE','PYTHONPATH')},'actual_numeric_thread_env_no_caps':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},'torch_threads_before':torch.get_num_threads(),'torch_interop_threads_before':torch.get_num_interop_threads(),'profile':'existing supported CPU/sequential owner profiles; locked currentversion; no scientific/source/tenant authority','new_posterior_oracle':'Current selected analytic original-unit fullcovariance only when defining selector actually executes; older other core receipts remain source-qualified separately','assessed_product_source':ASSESS,'assessed_product_tree':ASSESS_TREE,'scope_plan':plan[MODE]}
class Observer:
    def pytest_collection_finish(self,session):emit('events.jsonl',{'event':'collection_finish','nodeids':[item.nodeid for item in session.items]})
    def pytest_runtest_logreport(self,report):emit('events.jsonl',{'event':'report','nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome,'duration':report.duration})
    def pytest_sessionfinish(self,session,exitstatus):emit('events.jsonl',{'event':'session_finish','exitstatus':int(exitstatus)})
plugins=[Observer()]
if negative:
    import importlib.util
    command['removal_plugin']={'path':str(negative),'sha256':sha(negative),'kept':'schema3/config/count/nativeartifact/CAS/RNG/row/digest parser; only nativecount/cardinality grounding removed'}
    spec=importlib.util.spec_from_file_location('gp_wrapper_count_removal',negative);plugin=importlib.util.module_from_spec(spec);spec.loader.exec_module(plugin);sys.modules['gp_wrapper_count_removal']=plugin;plugins.append(plugin)
write('command.json',command)
started=time.monotonic();rc=int(pytest.main(argv,plugins=plugins));write('origins.json',origins());after=snap();write('after.json',after);assert before==after
assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==HARNESS_SHA256
write('result.json',{'harness_file':str(Path(__file__).resolve()),'harness_sha256':HARNESS_SHA256,'actual_cwd':str(Path.cwd().resolve()),'exitcode':rc,'mode':MODE,'source':EXPECTED,'tree':before['tree'],'assessed_product_source':ASSESS,'assessed_product_tree':ASSESS_TREE,'wall_s':time.monotonic()-started,'actual_fit_start_ids':fit_id,'backend':backend,'torch_threads_after':torch.get_num_threads(),'torch_interop_threads_after':torch.get_num_interop_threads(),'complete_executable_input_denominator':len(tracked),'source_and_executable_inputs_immutable':True,'predicate':plan[MODE]['property'],'P41':'not_established; no inherited-red claim','deciding_output_sha256':{p.name:sha(p) for p in OUT.iterdir() if p.is_file()},'outer_streams':'Append hashes after wrapper END; not hashed prematurely here'})
print('GP_WRAPPER_SCOPE_RESULT '+json.dumps({'mode':MODE,'exitcode':rc,'fit_starts':fit_id,'output':str(OUT)}));sys.exit(rc)
