"""Read-only actual JAX compiler witnesses; no product source or registry singleton writes."""
from __future__ import annotations
import hashlib, json, threading, traceback
from dataclasses import replace
from pathlib import Path
from typing import ClassVar, NamedTuple
import jax.numpy as jnp
from polisyos.foundry.methods.base import ComplexityClass, FidelityLevel, MethodMetadata, MethodSignature, ParameterSpec, SlotSpec, SlotType, Unit
from polisyos.foundry.methods.compiler import CompilationCache, MethodCompiler
from polisyos.foundry.methods.selection.registry import MethodRegistry
import polisyos.foundry.methods.compiler as compiler_module
unit=Unit('count','1')
signature=MethodSignature(name='scale',namespace='tests.e02_jit_real',version='1.0.0',input_slots=frozenset({SlotSpec('value',SlotType.SCALAR,unit,shape=())}),output_slots=frozenset({SlotSpec('result',SlotType.SCALAR,unit,shape=())}),parameters=(ParameterSpec('factor',default=2.0),),fidelity=FidelityLevel.LOW,complexity=ComplexityClass.O_1)
metadata=MethodMetadata(description='Real JAX immutable-kernel consumer',tags=frozenset({'test'}))
class State(NamedTuple):
 value:object
 result:object
class Original:
 signature:ClassVar=signature
 metadata:ClassVar=metadata
 @staticmethod
 def pure_step(state,params):return state._replace(result=state.value*params['factor'])
class Replacement:
 signature:ClassVar=signature
 metadata:ClassVar=metadata
 @staticmethod
 def pure_step(state,params):return state._replace(result=state.value*(params['factor']+1))
def compiler(cache=None):
 registry=MethodRegistry._create_fresh();registry.register(Original)
 return MethodCompiler(registry=registry,cache=cache or CompilationCache()),registry
state=State(jnp.asarray(10.0),jnp.asarray(0.0))
def compile_handle(c):return c.compile(method_name=signature.fqn,params={'factor':2.0},sample_inputs={'value':state.value},jit=True)
def value(h):return float(h(state,{}).result.block_until_ready())
results=[]
def record(name,fn):
 try:
  result=fn();results.append({'name':name,'result':result})
 except BaseException as exc:
  results.append({'name':name,'exception':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
def replacement():
 c,registry=compiler();old=compile_handle(c);old_value=value(old)
 registry.register(Replacement,override=True);warm=compile_handle(c);warm_value=value(warm)
 cold=compile_handle(MethodCompiler(registry=registry,cache=CompilationCache()));cold_value=value(cold)
 return {'old':old_value,'old_handle_after':value(old),'new_warm':warm_value,'new_cold':cold_value,'same_kernel':warm._kernel is old._kernel,'property_pass':warm_value==cold_value==30.0 and value(old)==20.0}
def missed_flight():
 first_miss=threading.Event();release_first=threading.Event();gate_guard=threading.Lock()
 class GateCache(CompilationCache):
  def get(self,*args,**kwargs):
   result=super().get(*args,**kwargs)
   if result is None and threading.current_thread().name=='first-owned-compiler' and not first_miss.is_set():
    first_miss.set()
    if not release_first.wait(5):raise RuntimeError('fixture second compiler failed to complete')
   return result
 cache=GateCache();c,registry=compiler(cache)
 class CountingCompiler(MethodCompiler):
  builds=0
  def _compile_method(self,*args,**kwargs):
   with gate_guard: self.builds+=1
   return super()._compile_method(*args,**kwargs)
 c=CountingCompiler(registry=registry,cache=cache);first_out=[];first_error=[]
 def first():
  try:first_out.append(compile_handle(c))
  except BaseException as exc:first_error.append(repr(exc))
 thread=threading.Thread(target=first,name='first-owned-compiler');thread.start()
 try:
  if not first_miss.wait(5):raise RuntimeError('fixture first actual miss never arrived')
  second=compile_handle(c);second_value=value(second)
 finally:release_first.set()
 thread.join(5)
 if thread.is_alive():raise RuntimeError('owned first compiler did not drain')
 if first_error:raise RuntimeError(first_error)
 first_value=value(first_out[0])
 return {'actual_builds':c.builds,'first_value':first_value,'second_value':second_value,'same_kernel':first_out[0]._kernel is second._kernel,'property_pass':c.builds==1 and first_out[0]._kernel is second._kernel and first_value==second_value==20.0}
record('same-FQN-source-replacement',replacement);record('miss-before-new-flight-claim',missed_flight)
print(json.dumps({'input_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'compiler_source_module':compiler_module.__file__,'compiler_source_sha256':hashlib.sha256(Path(compiler_module.__file__).read_bytes()).hexdigest(),'results':results},indent=2))
raise SystemExit(0 if all(item.get('result',{}).get('property_pass',False) for item in results) else 1)
