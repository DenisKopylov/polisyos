"""Read-only current transfer tests using prior reviewed immutable capture shape."""
from pathlib import Path
import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import resource
import subprocess
import sys
import time
ROOT=Path('/dev/shm/e02-D-oct07-continuation');PRODUCT=ROOT/'policy-engine'
EXPECTED,OUTPUT,MODE=sys.argv[1:]; OUT=Path(OUTPUT); OUT.mkdir(parents=True,exist_ok=False)
ASSESS='a795967a80818a61fbc939a8d1b1ec8b0fca6477'
assert Path.cwd().resolve()==PRODUCT.resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
HARNESS_SHA=sha(Path(__file__))
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
def write(name,data):(OUT/name).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
def emit(data):
 with (OUT/'events.jsonl').open('a') as f:f.write(json.dumps({'utc':datetime.datetime.now(datetime.UTC).isoformat(),**data})+'\n')
tracked=git('ls-files','policy-engine/src','policy-engine/tests','policy-engine/tools','policy-engine/pyproject.toml','policy-engine/ruff.toml','policy-engine/uv.lock').splitlines()
def snap():return {'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'status':git('status','--porcelain'),'complete_declared_executable_inputs':len(tracked),'missing':[p for p in tracked if not(ROOT/p).is_file()],'inputs':{p:sha(ROOT/p) for p in tracked if(ROOT/p).is_file()}}
def origins():
 result={}
 for name,module in list(sys.modules.items()):
  filename=getattr(module,'__file__',None)
  if filename:
   p=Path(filename)
   if p.is_file():result[name]={'path':str(p),'sha256':sha(p)}
 return result
before=snap();write('before.json',before);assert before['head']==EXPECTED and not before['status'] and not before['missing']
changes=set(git('diff','--name-only',ASSESS,EXPECTED).splitlines())
new_test_inputs={'policy-engine/tests/integration/scientist/methods/search/funnel/test_native_node_resource_consumer.py','policy-engine/tests/unit/scientist/methods/search/strategies/test_transfer_legacy_refusal.py'}
assert changes.intersection(tracked)==new_test_inputs | {'policy-engine/src/polisyos/scientist/methods/search/funnel/README.md'}
assert not git('diff','--name-only','cbc46a0bc87761bc2267a0daa84da489d6702e89',EXPECTED,'policy-engine/src/polisyos','policy-engine/tools','policy-engine/pyproject.toml','policy-engine/uv.lock',':(exclude)*README.md')
write('assessed-source-equivalence.json',{'actual_execution_head':EXPECTED,'actual_execution_tree':before['tree'],'assessed_product_source':ASSESS,'assessed_product_tree':git('rev-parse',ASSESS+'^{tree}'),'complete_declared_executable_inputs':len(tracked),'changed_declared_inputs':sorted(changes.intersection(tracked)),'production_executable_delta':[],'new_test_sources':sorted(new_test_inputs),'new_tests_same_byte_as_assessed_product':False,'all_head_delta_paths':sorted(changes),'whole_catalog_tree_identity':False})
plan_file=Path(__file__).with_name('scope-plan.json');plan=json.loads(plan_file.read_text())[MODE]
import pytest,hnswlib,numpy
backend={n:importlib.metadata.version(n) for n in ('hnswlib','numpy','scipy','pytest','torch','botorch','gpytorch')}
assert backend['hnswlib']=='0.8.0' and backend['numpy']=='2.3.5'
argv=['-o','addopts=','-p','no:cacheprovider','-o','junit_family=xunit1','-o','junit_logging=all','-o','junit_log_passing_tests=true','-q','-s','-ra','--basetemp='+str(OUT/'basetemp'),'--junitxml='+str(OUT/'junit.xml'),*plan['selectors']]
class Observer:
 def pytest_collection_finish(self,session):emit({'event':'collection_finish','nodeids':[i.nodeid for i in session.items]})
 def pytest_runtest_logreport(self,report):emit({'event':'report','nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome,'duration':report.duration})
 def pytest_sessionfinish(self,session,exitstatus):emit({'event':'session_finish','exitstatus':int(exitstatus)})
plugins=[Observer()];negative=plan.get('plugin')
command={'wrapper_argv':sys.argv,'harness':str(Path(__file__).resolve()),'harness_sha256':HARNESS_SHA,'plan_file':str(plan_file),'plan_sha256':sha(plan_file),'pytest_argv':argv,'cwd':str(PRODUCT),'source':EXPECTED,'tree':before['tree'],'assessed_product_source':ASSESS,'assessed_product_tree':git('rev-parse',ASSESS+'^{tree}'),'backend':backend,'python':sys.version,'executable':sys.executable,'sys_path':sys.path,'environment_overrides':{k:os.environ.get(k) for k in ('PYTHONDONTWRITEBYTECODE','PYTHONPATH','TMPDIR')},'inherited_numeric_thread_environment_no_caps':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},'seed_inputs':'Actual original measured_history helper: two controlled donor observations; min/max × schema1/absent/placeholder; native deterministic test seed; no tenant/scientific rights','compute_limits_introduced':False,'scope_plan':plan}
if negative:
 path=Path(negative);command['removal_plugin']={'path':str(path),'sha256':sha(path)}
 spec=importlib.util.spec_from_file_location('transfer_current_removal',path);plugin=importlib.util.module_from_spec(spec);sys.modules['transfer_current_removal']=plugin;spec.loader.exec_module(plugin);plugins.append(plugin)
write('command.json',command);start=time.monotonic();usage_before=resource.getrusage(resource.RUSAGE_SELF)
rc=int(pytest.main(argv,plugins=plugins));write('origins.json',origins());after=snap();write('after.json',after);assert before==after;assert sha(Path(__file__))==HARNESS_SHA
usage=resource.getrusage(resource.RUSAGE_SELF);children=resource.getrusage(resource.RUSAGE_CHILDREN)
write('result.json',{'mode':MODE,'exitcode':rc,'source':EXPECTED,'tree':before['tree'],'assessed_product_source':ASSESS,'assessed_product_tree':git('rev-parse',ASSESS+'^{tree}'),'elapsed_seconds':time.monotonic()-start,'backend':backend,'complete_declared_executable_inputs':len(tracked),'source_and_executable_inputs_unchanged':True,'resource_posix':{'self_maxrss_kib':usage.ru_maxrss,'self_user_seconds':usage.ru_utime-usage_before.ru_utime,'self_system_seconds':usage.ru_stime-usage_before.ru_stime,'children_maxrss_kib':children.ru_maxrss,'children_user_seconds':children.ru_utime,'children_system_seconds':children.ru_stime},'P41':'not_established; no slice-base inherited-red claim','property':plan['property'],'deciding_sha256':{p.name:sha(p) for p in OUT.iterdir() if p.is_file()},'outer_complete_stdout_stderr':'Captured by caller; hash only after process ends'})
print('TRANSFER_CURRENT_RESULT '+json.dumps({'mode':MODE,'exitcode':rc,'output':str(OUT)}));sys.exit(rc)
