"""Non-interfering diagnostic observer for one exact served selector."""
import importlib,json,os,threading,time
from pathlib import Path
import pytest
OUT=Path(os.environ['E02C_OUT']); NODE='tests/integration/runtime/http/test_registered_sql_live_grant.py::test_real_sql_workflows_recheck_current_use_on_every_debug_get'; EVENTS=[]; ERRORS=[]; DISPATCHES=0
def text(x,n=2000): return None if x is None else str(x)[:n]
def guard(op,fn):
 try:return True,fn()
 except BaseException as e:
  try: ERRORS.append({'classification':'HARNESS_ERROR','operation':op,'exception_class':type(e).__name__,'message':text(e)})
  except BaseException:pass
  return False,None
def mapping(x):
 if isinstance(x,dict):return x
 f=getattr(x,'model_dump',None)
 return f(mode='json') if callable(f) else {}
def stage(service,name):
 original=getattr(service,name)
 def wrapped(*args,**kwargs):
  job=kwargs.get('job'); base={'stage':name,'pid':os.getpid(),'thread_id':threading.get_ident(),'thread_name':threading.current_thread().name,'job_id':text(getattr(job,'job_id',None),128),'run_id':text(getattr(job,'run_id',None),128),'monotonic_ns':time.monotonic_ns()}; guard(name+'.entry_event',lambda:EVENTS.append({**base,'edge':'entry'}))
  try:r=original(*args,**kwargs)
  except BaseException as e:
   guard(name+'.raised_event',lambda:EVENTS.append({**base,'edge':'raised','exception_class':type(e).__name__,'message':text(e),'monotonic_ns':time.monotonic_ns()})); raise
  guard(name+'.returned_event',lambda:EVENTS.append({**base,'edge':'returned','result_class':type(r).__name__,'monotonic_ns':time.monotonic_ns()})); return r
 setattr(service,name,wrapped); return original,wrapped
def terminal(store,jid):
 job=store.get_job(jid)
 if job is None:return {'job_record_present':False,'job_id':text(jid,128)}
 p=mapping(job.progress); f=mapping(p.get('failure')); s=mapping(job.method_execution_selection)
 return {'job_record_present':True,'job_id':text(job.job_id,128),'run_id':text(job.run_id,128),'state':text(job.state,64),'error_message':text(job.error_message),'progress':p,'progress_failure':f,'payload_ref':text(job.payload_ref,512),'capability_manifest_ref':text(job.capability_manifest_ref,512),'method_execution_selection':{'present':job.method_execution_selection is not None,'type':type(job.method_execution_selection).__name__,'keys':sorted(map(str,s))[:64]}}
def write(record):
 p=OUT/'observations'/f'c152-served-diagnostic-{os.getpid()}.json'; payload={'schema':'polisyos.e02.c152.served_failure_diagnostic.v1','selector':NODE,'pytest_pid':os.getpid(),'records':[record],'diagnostic_errors':ERRORS,'diagnostic_status':'HARNESS_ERROR' if ERRORS else 'CAPTURED'}; t=p.with_suffix('.tmp'); t.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); t.replace(p)
@pytest.hookimpl(hookwrapper=True,tryfirst=True)
def pytest_runtest_call(item):
 global DISPATCHES
 if item.nodeid!=NODE: yield; return
 cw=importlib.import_module('tests._helpers.control_worker'); dispatch=cw.dispatch_one_control_job
 def observed_dispatch(*,store,handler,expected_job_id=None):
  global DISPATCHES
  DISPATCHES+=1
  if DISPATCHES!=1:return dispatch(store=store,handler=handler,expected_job_id=expected_job_id)
  service=getattr(handler,'__self__',None); patched=[]
  if service:
   for n in ('_execute_legacy_shadow_workflow','_run_legacy_scientist_workflow'):
    ok,v=guard(n+'.install',lambda n=n:stage(service,n))
    if ok:patched.append((n,*v))
  try:
   try:r=dispatch(store=store,handler=handler,expected_job_id=expected_job_id)
   except BaseException as e:
    rec={'dispatch_returned':False,'dispatch_exception_class':type(e).__name__,'dispatch_exception_message':text(e),'expected_job_id':text(expected_job_id,128),'stage_events':list(EVENTS)}; ok,j=guard('terminal_job_select',lambda:terminal(store,expected_job_id)); rec['terminal_job']=j if ok else None; guard('diagnostic_json_write',lambda:write(rec)); raise
   rec={'dispatch_returned':True,'dispatch_result_job_id':text(r,128),'expected_job_id':text(expected_job_id,128),'stage_events':list(EVENTS)}; ok,j=guard('terminal_job_select',lambda:terminal(store,expected_job_id)); rec['terminal_job']=j if ok else None; guard('diagnostic_json_write',lambda:write(rec)); return r
  finally:
   if service:
    for n,old,wrapped in reversed(patched):
     if getattr(service,n,None) is wrapped:setattr(service,n,old)
 cw.dispatch_one_control_job=observed_dispatch
 try:yield
 finally:cw.dispatch_one_control_job=dispatch
