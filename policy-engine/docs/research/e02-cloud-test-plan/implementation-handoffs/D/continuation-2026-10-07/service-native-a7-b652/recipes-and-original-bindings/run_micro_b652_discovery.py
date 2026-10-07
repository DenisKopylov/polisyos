"""Immutable actual native consumer wave capture, no source mutations."""
from pathlib import Path
import datetime, hashlib, json, os, subprocess, sys, time
import xml.etree.ElementTree as ET
ROOT=Path('/dev/shm/e02-D-oct07-continuation'); PRODUCT=ROOT/'policy-engine'
BASE=Path('/dev/shm/e02-D-oct07-service-start'); OUT=BASE/'final-native-b652'
PYTHON='/tmp/e02-D-runtime-minimal-20261006/bin/python'
SOURCE='b652b77eeec25f8ff1bd744d84ed20bd1b6cb21e'
SELECTIONS={
'ctl':[
 'tests/unit/scientist/methods/search/test_controller.py',
 'tests/unit/scientist/search/test_search_loop.py::TestOptimizationFlow::test_repeated_runs_are_fresh_and_returned_snapshots_stay_stable',
 'tests/unit/scientist/search/test_search_loop.py::TestOptimizationFlow::test_concurrent_runs_are_rejected_as_non_reentrant',
 'tests/integration/scientist/methods/search/test_controller.py',
 'tests/unit/scientist/search/test_search_loop.py::TestOptimizationFlow::test_malformed_typed_evaluation_cannot_fall_back_to_legacy_objective',
 'tests/unit/scientist/search/test_controller_api.py',
 'tests/unit/scientist/methods/search/test_controller_owner_admission.py',
 'tests/unit/scientist/methods/search/test_typed_objective_persisted_projection.py',
 'tests/unit/scientist/methods/search/test_semantic_dates_persisted_consumers.py',
 'tests/unit/scientist/methods/search/test_grid_factory_finite_exhaustion.py'],
'champion':[
 'tests/unit/scientist/methods/autotune/test_registry_and_runner.py',
 'tests/unit/scientist/methods/autotune/test_champion_verified_snapshot.py',
 'tests/unit/scientist/methods/autotune/test_benchmark_primitive_admission.py'],
'service':[
 'tests/unit/scientist/methods/search/test_service_factory_fault_resume.py',
 'tests/unit/scientist/methods/search/test_service_batch_control_reasons.py',
 'tests/unit/scientist/methods/search/test_service_control_cleanup_independent.py',
 'tests/unit/scientist/methods/search/test_service_ask_publication_review.py',
 'tests/unit/scientist/methods/autotune/test_native_search_lifecycle.py',
 'tests/unit/scientist/methods/autotune/test_execution_plan_autotune.py'],
'native-doe':['tests/unit/scientist/methods/autotune/test_native_doe_factory.py'],
'native-doe-real':['tests/unit/scientist/methods/autotune/test_native_doe_factory.py'],
'paid-original-real':['tests/integration/scientist/methods/search/test_controller.py'],
'contracts':['tests/unit/scientist/search/test_contracts.py'],
'rollback-removal-discovery':['tests/unit/scientist/methods/search/test_service_owner_budget_factory.py::test_actual_owner_change_after_ask_preflight_is_not_rolled_back_to_known_zero'],
'run-reset-removal':['tests/integration/scientist/methods/search/test_controller.py::test_two_paid_runs_on_same_controller_match_fresh_controllers_with_scoped_sentinels'],
'sentinel-removal':['tests/integration/scientist/methods/search/test_controller.py::test_two_paid_runs_on_same_controller_match_fresh_controllers_with_scoped_sentinels'],
'cursor-removal':['tests/unit/scientist/methods/search/test_service_factory_fault_resume.py'],
'grid-removal':['tests/unit/scientist/methods/search/test_grid_factory_finite_exhaustion.py'],
'objective-removal':['tests/unit/scientist/methods/search/test_typed_objective_persisted_projection.py'],
'date-removal':['tests/unit/scientist/methods/search/test_semantic_dates_persisted_consumers.py']}
PLUGINS={'rollback-removal-discovery':'budget_rollback_owner_refresh_removal','run-reset-removal':'controller_run_scope_marker_removal','sentinel-removal':'controller_run_scope_marker_removal','cursor-removal':'service_cursor_marker_removal','grid-removal':'grid_short_batch_marker_removal','objective-removal':'objective_present_marker_removal','date-removal':'semantic_date_marker_removal'}
BACKENDS={
'ctl':'Actual SearchController/NativeSearchService/ObjectiveStack/ParetoRegistry/FileSystemCAS, configured finite Grid/StrategyAdapter and canonical B1.2 BudgetMiddleware/FileBudgetLedger through actual Gateway response text; deterministic bounded StageB/evaluator inputs, no invoice or production law claim',
'champion':'Actual FileSystemCAS/ChampionRegistry/SearchLoopRunner/ChampionBackedRuntimeLoader; bounded paired BenchmarkEvaluator and active suite; existing local flock/CAS atomic pointer, competing threads and fresh process crash reader, no distributed guarantee',
'service':'Actual SearchLoopRunner.create_service/NativeSearchService/FileSystemCAS checkpoint and physical candidate generator; bounded native evaluator, actual provider ledger events, actual execution-plan topology selection; no unappointed external served caller claim'}
name=sys.argv[1]; OUT.mkdir(exist_ok=True)
if name in ['native-doe','native-doe-real']:PYTHON='/workspace/e02-D-locked-env/bin/python'
def git(*a): return subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
def inventory():
 result={}
 for entry in subprocess.check_output(['git','-C',str(ROOT),'ls-files','-s','-z']).decode().split('\0'):
  if not entry:continue
  stage,p=entry.split('\t',1); f=ROOT/p
  result[p]={'index':stage,'available':f.is_file(),**({'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} if f.is_file() else {})}
 return result
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain=v1')
argv=[PYTHON,'-m','pytest','--noconftest','-p','no:cacheprovider','-s','-ra','--basetemp',str(OUT/(name+'-fixtures')),'--junitxml',str(OUT/(name+'.junit.xml'))]
if name in PLUGINS:argv+=['-p',PLUGINS[name]]
argv+=SELECTIONS[name]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join([str(PRODUCT/'src'),str(PRODUCT),str(BASE)]))
if name in ['paid-original-real','run-reset-removal','sentinel-removal','rollback-removal-discovery']:env['TIKTOKEN_CACHE_DIR']='/workspace/e02-D2-receipts/tokenizer'
if name=='native-doe-real':env['PYTHONPATH']=os.pathsep.join([str(PRODUCT/'src'),str(PRODUCT),'/workspace/e02-D-locked-env/lib/python3.14/site-packages','/workspace/e02-D-doe-env/lib/python3.14/site-packages',str(BASE)])
if name=='rollback-removal-discovery':env['PYTHONPATH']+=os.pathsep+str(PRODUCT/'tests/unit/scientist/methods/search')
if name in ['run-reset-removal','sentinel-removal']:env['E02_CONTROLLER_REMOVAL_PROFILE']='run_reset' if name=='run-reset-removal' else 'sentinel'
record={'name':name,'source_sha':SOURCE,'source_tree':git('rev-parse','HEAD^{tree}'),'source_status_before':git('status','--porcelain=v1'),'argv':argv,'cwd':str(PRODUCT),'environment_overrides':{k:env[k] for k in ['PYTHONDONTWRITEBYTECODE','PYTHONPATH']+(['TIKTOKEN_CACHE_DIR'] if 'TIKTOKEN_CACHE_DIR' in env else [])},'backend':BACKENDS.get(name,'Actual marker-preserving removal at the indicated native consumer seam; positive scope and unaffected marker/corpus identities retained'),'no_artificial_quotas':True,'started_at':datetime.datetime.now(datetime.UTC).isoformat(),'runtime':json.loads(subprocess.check_output([PYTHON,'-c','import sys,platform,json,importlib.metadata as m; print(json.dumps({"python":sys.version,"executable":sys.executable,"platform":platform.platform(),"packages":{n:m.version(n) for n in ["pytest","pydantic","numpy","scipy"]}}))'],text=True)),'inputs_before':inventory()}
if name in PLUGINS:record['plugin_sha256']=hashlib.sha256((BASE/(PLUGINS[name]+'.py')).read_bytes()).hexdigest()
path=OUT/(name+'.command.json'); assert not path.exists(),'output already exists'; path.write_text(json.dumps(record,indent=2)+'\n')
start=time.monotonic()
with (OUT/(name+'.stdout.txt')).open('w') as out,(OUT/(name+'.stderr.txt')).open('w') as err:
 completed=subprocess.run(argv,cwd=PRODUCT,env=env,stdout=out,stderr=err)
record.update(returncode=completed.returncode,elapsed_seconds=time.monotonic()-start,completed_at=datetime.datetime.now(datetime.UTC).isoformat(),source_sha_after=git('rev-parse','HEAD'),source_status_after=git('status','--porcelain=v1'),inputs_after=inventory())
record['same_inputs']=record['inputs_before']==record['inputs_after']; record['outputs']={}
for ext in ['stdout.txt','stderr.txt','junit.xml']:
 p=OUT/(name+'.'+ext); record['outputs'][ext]={'available':p.exists(),**({'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} if p.exists() else {})}
record['case_phases']={k:0 for k in ['PASS','FAIL','ERROR','SKIP']}
junit=OUT/(name+'.junit.xml')
if junit.exists():
 for case in ET.parse(junit).getroot().iter('testcase'):
  tag=next((t for t in ['failure','error','skipped'] if case.find(t)is not None),None)
  record['case_phases'][{None:'PASS','failure':'FAIL','error':'ERROR','skipped':'SKIP'}[tag]]+=1
path.write_text(json.dumps(record,indent=2)+'\n')
summary={k:record[k] for k in ['name','source_sha','returncode','elapsed_seconds','case_phases','same_inputs','outputs']}; print(json.dumps(summary,indent=2))
