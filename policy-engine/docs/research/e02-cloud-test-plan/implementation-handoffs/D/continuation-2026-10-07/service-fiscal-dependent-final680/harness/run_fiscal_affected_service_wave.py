"""Exact immutable native consumer receipts; no production or fixture reuse."""
from pathlib import Path
import datetime,fcntl,gzip,hashlib,json,os,subprocess,sys,time,xml.etree.ElementTree as ET
ROOT=Path('/dev/shm/e02-D-oct07-continuation');PRODUCT=ROOT/'policy-engine';BASE=Path('/dev/shm/e02-D-oct07-service-start')
SOURCE,OUTNAME,NAME=sys.argv[1:4];OUT=BASE/OUTNAME;OUT.mkdir(exist_ok=True)
SELECT={
 'fiscal-dependent':['tests/unit/scientist/methods/search/test_service_batch_control_reasons.py','tests/unit/scientist/methods/search/test_service_control_cleanup_independent.py','tests/unit/scientist/methods/search/test_service_ask_publication_review.py'],
 'dedup':['tests/unit/scientist/methods/search/test_service_trial_deduplication.py','tests/unit/scientist/methods/autotune/test_dedup.py'],
 'service':['tests/unit/scientist/methods/search/test_service_factory_fault_resume.py','tests/unit/scientist/methods/search/test_service_batch_control_reasons.py','tests/unit/scientist/methods/search/test_service_control_cleanup_independent.py','tests/unit/scientist/methods/search/test_service_ask_publication_review.py','tests/unit/scientist/methods/autotune/test_native_search_lifecycle.py','tests/unit/scientist/methods/autotune/test_execution_plan_autotune.py'],
 'champion':['tests/unit/scientist/methods/autotune/test_registry_and_runner.py','tests/unit/scientist/methods/autotune/test_champion_verified_snapshot.py','tests/unit/scientist/methods/autotune/test_benchmark_primitive_admission.py'],
 'paid-original':['tests/integration/scientist/methods/search/test_controller.py'],
 'contracts':['tests/unit/scientist/search/test_contracts.py'],
 'native-doe':['tests/unit/scientist/methods/autotune/test_native_doe_factory.py'],
 'cursor-removal':['tests/unit/scientist/methods/search/test_service_factory_fault_resume.py'],
 'objective-removal':['tests/unit/scientist/methods/search/test_typed_objective_persisted_projection.py'],
 'date-removal':['tests/unit/scientist/methods/search/test_semantic_dates_persisted_consumers.py'],
 'grid-removal':['tests/unit/scientist/methods/search/test_grid_factory_finite_exhaustion.py'],
}
PLUGINS={'cursor-removal':'service_cursor_marker_removal','objective-removal':'objective_present_marker_removal','date-removal':'semantic_date_marker_removal','grid-removal':'grid_short_batch_marker_removal'}
PYTHON='/workspace/e02-D-locked-env/bin/python' if NAME=='native-doe' else '/tmp/e02-D-runtime-minimal-20261006/bin/python'
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inputs():
 result={}
 for entry in subprocess.check_output(['git','-C',str(ROOT),'ls-files','-s','-z']).decode().split('\0'):
  if entry:
   stage,path=entry.split('\t',1);p=ROOT/path;result[path]={'git_index':stage,'available':p.is_file(),**({'sha256':digest(p)} if p.is_file() else {})}
 return result
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain=v1')
before=inputs();manifest=OUT/'frozen-inputs.json.gz'
# Independent writers receive one identical deterministic manifest; no mutable shared fixture.
manifest_bytes=gzip.compress((json.dumps(before,sort_keys=True,separators=(',',':'))+'\n').encode(),mtime=0)
with (OUT/'source-input-manifest.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 if manifest.exists():assert manifest.read_bytes()==manifest_bytes
 else:manifest.write_bytes(manifest_bytes)
 fcntl.flock(lock,fcntl.LOCK_UN)
argv=[PYTHON,'-m','pytest','-o','addopts=','--noconftest','-p','no:cacheprovider','-s','-ra','--basetemp',str(OUT/(NAME+'-fixtures')),'--junitxml',str(OUT/(NAME+'.junit.xml'))]
if NAME == 'fiscal-dependent':argv+=['-p','service_fiscal_observer']
if NAME in PLUGINS:argv+=['-p',PLUGINS[NAME]]
argv+=SELECT[NAME]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join([str(PRODUCT/'src'),str(PRODUCT),str(BASE)]))
if NAME=='fiscal-dependent':env['E02_SERVICE_OBSERVER_OUTPUT']=str(OUT/(NAME+'.loaded-origins-and-phases.json'))
if NAME=='paid-original':env['TIKTOKEN_CACHE_DIR']='/workspace/e02-D2-receipts/tokenizer'
if NAME=='native-doe':env['PYTHONPATH']=os.pathsep.join([str(PRODUCT/'src'),str(PRODUCT),'/workspace/e02-D-locked-env/lib/python3.14/site-packages','/workspace/e02-D-doe-env/lib/python3.14/site-packages',str(BASE)])
record={'name':NAME,'source_sha':SOURCE,'source_tree':git('rev-parse','HEAD^{tree}'),'source_status_before':git('status','--porcelain=v1'),'argv':argv,'cwd':str(PRODUCT),'environment_overrides':{k:env[k] for k in ['PYTHONDONTWRITEBYTECODE','PYTHONPATH']+(['TIKTOKEN_CACHE_DIR'] if NAME=='paid-original' else [])},'harness':{'path':str(Path(__file__)),'sha256':digest(Path(__file__))},'backend':'Actual native SearchLoopRunner/NativeSearchService/qualified FileSystemCAS/ChampionRegistry; actual supported typed mutation/evaluator/data-context profiles and physical invocation counts. No scientific law, appointed production caller, external identity migration or distributed atomicity inferred. Actual Torch/SALib only in native DOE cohort; provider fixtures are not invoice truth.','no_artificial_quotas':True,'started_at':datetime.datetime.now(datetime.UTC).isoformat(),'complete_frozen_input_manifest':{'path':manifest.name,'bytes':manifest.stat().st_size,'sha256':digest(manifest),'entries':len(before)},'runtime':json.loads(subprocess.check_output([PYTHON,'-c','import sys,platform,json,importlib.metadata as m; print(json.dumps({"python":sys.version,"executable":sys.executable,"platform":platform.platform(),"packages":{n:m.version(n) for n in ["pytest","pydantic","numpy","scipy"]}}))'],text=True))}
if NAME=='fiscal-dependent':record['observer']={'path':str(BASE/'service_fiscal_observer.py'),'sha256':digest(BASE/'service_fiscal_observer.py'),'output':env['E02_SERVICE_OBSERVER_OUTPUT'],'effect':'Read-only pytest report and module-origin observation; no runtime monkeypatch or fixture effects.'}
if NAME in PLUGINS:record['plugin_sha256']=digest(BASE/(PLUGINS[NAME]+'.py'))
p=OUT/(NAME+'.receipt.json');assert not p.exists();p.write_text(json.dumps(record,indent=2)+'\n')
start=time.monotonic()
with (OUT/(NAME+'.stdout.txt')).open('w') as out,(OUT/(NAME+'.stderr.txt')).open('w') as err: completed=subprocess.run(argv,cwd=PRODUCT,env=env,stdout=out,stderr=err)
after=inputs();record.update(returncode=completed.returncode,elapsed_seconds=time.monotonic()-start,completed_at=datetime.datetime.now(datetime.UTC).isoformat(),source_sha_after=git('rev-parse','HEAD'),source_status_after=git('status','--porcelain=v1'),same_inputs=before==after,changed_inputs=[path for path in sorted(set(before)|set(after)) if before.get(path)!=after.get(path)],case_phases={k:0 for k in ['PASS','FAIL','ERROR','SKIP']},cases=[],outputs={})
for suffix in ['stdout.txt','stderr.txt','junit.xml','loaded-origins-and-phases.json']:
 q=OUT/(NAME+'.'+suffix);record['outputs'][suffix]={'available':q.exists(),**({'bytes':q.stat().st_size,'sha256':digest(q)} if q.exists() else {})}
j=OUT/(NAME+'.junit.xml')
if j.exists():
 for case in ET.parse(j).getroot().iter('testcase'):
  tag=next((x for x in ['failure','error','skipped'] if case.find(x) is not None),None);status={None:'PASS','failure':'FAIL','error':'ERROR','skipped':'SKIP'}[tag];record['case_phases'][status]+=1;record['cases'].append({'name':case.attrib.get('name'),'classname':case.attrib.get('classname'),'status':status})
p.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['name','source_sha','returncode','elapsed_seconds','case_phases','same_inputs','changed_inputs','outputs']},indent=2))
