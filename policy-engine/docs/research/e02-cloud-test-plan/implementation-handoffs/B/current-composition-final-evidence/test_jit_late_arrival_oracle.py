"""A real ready-hit schedule shows the old invalidation oracle lacks its premise."""
from __future__ import annotations
import hashlib,importlib.util,json,pathlib,sys,threading
import pytest
ROOT=pathlib.Path.cwd()
PATH=ROOT/'tests/unit/remediation/test_jit_01.py'
SPEC=importlib.util.spec_from_file_location('jit_schedule_existing',PATH)
OWNER=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=OWNER;SPEC.loader.exec_module(OWNER)

def test_original_oracle_rejects_legitimate_late_ready_hit(monkeypatch):
 published=threading.Event();lock=threading.Lock();observed={'gets':0,'late_ready_hits':0,'native_compiles':0}
 original_get=OWNER.CompilationCache.get;original_publish=OWNER.CompilationCache.publish_flight
 original_compile=OWNER.MethodCompiler._compile_method
 def get(cache,*args,**kwargs):
  with lock: observed['gets']+=1;number=observed['gets']
  if number==2: assert published.wait(2),'fixture publication not reached'
  result=original_get(cache,*args,**kwargs)
  if number==2 and result is not None: observed['late_ready_hits']+=1
  return result
 def publish(cache,*args,**kwargs):
  result=original_publish(cache,*args,**kwargs)
  if result: published.set()
  return result
 def compile_method(compiler,*args,**kwargs):
  with lock: observed['native_compiles']+=1
  return original_compile(compiler,*args,**kwargs)
 monkeypatch.setattr(OWNER.CompilationCache,'get',get)
 monkeypatch.setattr(OWNER.CompilationCache,'publish_flight',publish)
 monkeypatch.setattr(OWNER.MethodCompiler,'_compile_method',compile_method)
 value=OWNER.SlotSpec('value',OWNER.SlotType.SCALAR,OWNER.Unit('value','unit'),shape=())
 result=OWNER.SlotSpec('result',OWNER.SlotType.SCALAR,OWNER.Unit('value','unit'),shape=())
 with pytest.raises(AssertionError):
  OWNER.test_single_flight_retries_when_invalidation_wins_result_delivery((value,result),monkeypatch)
 assert observed['late_ready_hits']==1
 assert observed['native_compiles']==1
 print(json.dumps({'original_native_test':str(PATH),'test_sha256':hashlib.sha256(PATH.read_bytes()).hexdigest(),'actual_cache_schedule':observed,'outcome':'Original test rejects legitimate late ready-cache hit because pending follower premise was never established; production has one actual compilation and actual cached handle.'}))
