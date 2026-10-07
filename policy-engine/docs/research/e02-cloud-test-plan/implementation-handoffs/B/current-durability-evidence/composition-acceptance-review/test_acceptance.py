"""Independent actual MethodComposer build/freeze/execute acceptance witnesses."""
from __future__ import annotations
import asyncio,json,os,pathlib,subprocess,sys,threading
import numpy as np
from typing import ClassVar
import pytest
from polisyos.foundry.methods.base import ComplexityClass,ComputeBackend,FidelityLevel,MethodMetadata,MethodSignature,SlotSpec,SlotType,Unit
from polisyos.foundry.methods.components.composer import MethodComposer,SemanticValidationLevel as Level
from polisyos.foundry.methods.components.linker import SlotLinker,LinkerConfig
from polisyos.foundry.methods.components.slot_schema import SemanticCompatibilityError
from polisyos.foundry.methods.backends.chain_executor import execute_heterogeneous_chain,execute_heterogeneous_chain_async
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.exceptions import CyclicDependencyError,SlotConnectionError
ROOT=pathlib.Path('/workspace/e02-B-current-durability');TARGET=os.environ.get('E02_REVIEW_TARGET_SHA','31ccd716859a27bcd087eec79fb64565f27b4f2b');OWNER=os.environ.get('E02_REVIEW_OWNER_SHA','061c94bf27bb6a2ad951047605bafa3b2e4d9cdf')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==TARGET
for rel in ['components/composer.py','components/linker.py','components/semantic_validator.py','components/slot_schema.py','backends/chain_executor.py','backends/async_chain_executor.py','selection/registry.py','base.py']:
 p='policy-engine/src/polisyos/foundry/methods/'+rel;assert (ROOT/p).read_bytes()==subprocess.check_output(['git','show',OWNER+':'+p],cwd=ROOT)
UNIT=Unit('review','unit')
def slot(name,contract=None,unit=UNIT,shape=(),kind=SlotType.SCALAR):return SlotSpec(name=name,slot_type=kind,unit=unit,contract_id=contract,shape=shape)
def method(name,inputs,outputs,step,requires=(),family='review',variant='review'):
 sig=MethodSignature(name=name,namespace='review.composition',version='1.0.0',input_slots=frozenset(inputs),output_slots=frozenset(outputs),parameters=(),fidelity=FidelityLevel.LOW,complexity=ComplexityClass.O_1,backend=ComputeBackend.NUMPY,supports_jit=False,supports_vmap=False,supports_grad=False,requires=frozenset(requires),family=family,variant=variant)
 class ActualMethod:
  signature:ClassVar=sig
  metadata:ClassVar=MethodMetadata(description='independent actual arithmetic',tags=frozenset({'review'}))
  @staticmethod
  def materialize_input(bound_inputs,fallback_state):
   state=dict(fallback_state) if isinstance(fallback_state,dict) else {};state.update(bound_inputs);return state
  @staticmethod
  def pure_step(state,params):return step(state,params)
 ActualMethod.__name__=name;return ActualMethod
def registry(*classes):
 MethodRegistry.reset_instance();r=MethodRegistry.get_instance()
 for c in classes:r.register(c,override=True)
 return r
@pytest.fixture(autouse=True)
def isolated_registry():
 MethodRegistry.reset_instance();yield;MethodRegistry.reset_instance()
def scalar_chain(out_name='value',in_name='value',linker=None,mapping=True):
 a=method('source',(),(slot(out_name),),lambda s,p:{out_name:7});b=method('target',(slot(in_name),),(slot('result'),),lambda s,p:{'result':s[in_name]*3});r=registry(a,b);c=MethodComposer(registry=r,linker=linker);na=c.add(a.signature.fqn);nb=c.add(b.signature.fqn);link=c.connect(na,nb,{out_name:in_name} if mapping else None);return r,c,na,nb,link
@pytest.mark.parametrize('order',['chain-first','async-first'])
def test_two_fresh_import_orders_execute_real_bound_values(order):
 worker=pathlib.Path(__file__).with_name('import_worker.py');p=subprocess.run([sys.executable,str(worker),order],cwd=ROOT/'policy-engine',capture_output=True,text=True,timeout=20)
 assert p.returncode==0,p.stdout+p.stderr;record=json.loads(p.stdout.split('RESULT:')[1]);assert record['value']==21 and record['node_count']==2
 print(json.dumps(record))
def test_required_only_edge_keeps_actual_parallel_level_and_value():
 gate=None
 def produce(s,p):
  if gate is not None:gate.wait(timeout=5)
  return {'prepared':7}
 def neighbor(s,p):
  if gate is not None:gate.wait(timeout=5)
  return {'neighbor':5}
 a=method('prepare',(),(slot('prepared'),),produce);b=method('use_prepared',(slot('prepared'),),(slot('result'),),lambda s,p:{'result':s['prepared']*3},requires=(a.signature.fqn,));n=method('neighbor',(),(slot('neighbor'),),neighbor);r=registry(a,b,n);c=MethodComposer(registry=r);nb=c.add(b.signature.fqn);na=c.add(a.signature.fqn);nn=c.add(n.signature.fqn);chain=c.build(validate_semantics=Level.STRICT)
 assert not chain.bindings and len(chain.dag.compute_parallel_levels()[0])==2 and set(chain.dag.compute_parallel_levels()[0])=={na.id,nn.id}
 seq=execute_heterogeneous_chain(chain,state={'prepared':100},registry=r,executor_mode='sequential');assert seq.final_state['result']==21
 gate=threading.Barrier(2);par=asyncio.run(execute_heterogeneous_chain_async(chain,state={'prepared':100},registry=r));assert par.final_state['result']==21 and par.final_state['neighbor']==5
 assert [i for i,_ in par.node_results].index(na.id)<[i for i,_ in par.node_results].index(nb.id)
 print(json.dumps({'sequential_value':seq.final_state['result'],'async_state':par.final_state,'levels':[[str(x) for x in l] for l in chain.dag.compute_parallel_levels()],'actual_parallel_barrier_parties':2}))
@pytest.mark.parametrize('rename',[False,True])
def test_matching_consumes_actual_fixed_and_flexible_values(rename):
 flexible,fixed,first,second=('z_flexible','a_fixed','z_first','a_second') if rename else ('a_flexible','b_fixed','c_first','d_second')
 a=method('matching_source',(),(slot(flexible),slot(fixed,'B')),lambda s,p:{flexible:7,fixed:11});b=method('matching_target',(slot(first,'B'),slot(second,'A')),(slot('result'),),lambda s,p:{'result':s[first]*100+s[second]});r=registry(a,b);c=MethodComposer(registry=r,linker=SlotLinker(LinkerConfig.strict()));na=c.add(a.signature.fqn);nb=c.add(b.signature.fqn);linked=c.connect(na,nb);chain=c.build(validate_semantics=Level.STRICT);expected={first:fixed,second:flexible};assert {x.target_slot:x.source_slot for x in linked.bindings}==expected
 result=execute_heterogeneous_chain(chain,state={first:1000,second:2000},registry=r);assert result.final_state['result']==1107
 print(json.dumps({'rename':rename,'actual_bindings':expected,'actual_result':result.final_state}))
def _multi_source(linker):
 a=method('left_source',(),(slot('value'),),lambda s,p:{'value':10});b=method('right_source',(),(slot('value'),),lambda s,p:{'value':20});m=method('sum_target',(slot('left'),slot('right')),(slot('result'),),lambda s,p:{'result':s['left']+s['right']});r=registry(a,b,m);c=MethodComposer(registry=r,linker=linker);na=c.add(a.signature.fqn);nb=c.add(b.signature.fqn);nm=c.add(m.signature.fqn);return r,c,na,nb,nm

def test_strict_complete_dag_accepts_two_partial_edges_as_one_complete_input_set():
 r,c,a,b,m=_multi_source(SlotLinker());c.connect(a,m,{'value':'left'});c.connect(b,m,{'value':'right'});control=c.build(validate_semantics=Level.STRICT);result=execute_heterogeneous_chain(control,state={'left':100,'right':200},registry=r);assert result.final_state['result']==30
 print(json.dumps({'positive_actual_full_dag_result':result.final_state,'positive_bound_inputs':[(x.source_slot,x.target_slot) for x in control.bindings]}),flush=True)
 r,c,a,b,m=_multi_source(SlotLinker(LinkerConfig.semantic_strict()))
 c.connect(a,m,{'value':'left'});c.connect(b,m,{'value':'right'});chain=c.build(validate_semantics=Level.STRICT)
 assert execute_heterogeneous_chain(chain,state={},registry=r).final_state['result']==30

def _occurrence_chain(requires=False,early_sensitivity=False):
 estimate_name='review.composition.estimate@1.0.0';a=method('estimate',(slot('value'),),(slot('value'),),lambda s,p:{'value':s['value']+1},family='estimation',variant='estimate');b=method('sensitivity',(slot('value'),),(slot('value'),),lambda s,p:{'value':s['value']*10},requires=(estimate_name,) if requires else (),family='sensitivity',variant='sensitivity');r=registry(a,b);c=MethodComposer(registry=r);classes=(b,a,b) if early_sensitivity else (a,b,a);nodes=[c.add(x.signature.fqn) for x in classes]
 for x,y in zip(nodes,nodes[1:]):c.connect(x,y,{'value':'value'})
 return r,c,nodes

def test_actual_repeated_occurrence_tag_validator_positive_negative():
 r,c,nodes=_occurrence_chain();chain=c.build(validate_semantics=Level.STRICT);result=execute_heterogeneous_chain(chain,state={'value':2},registry=r);assert result.final_state['value']==31
 r,c,_=_occurrence_chain(early_sensitivity=True)
 with pytest.raises(ValueError,match='ordering'):c.build(validate_semantics=Level.STRICT)
 warn=c.build(validate_semantics=Level.WARN);assert any('precede it' in x for x in warn.warnings)
 print(json.dumps({'actual_valid_repeated_value':31,'early_invalid_strict':'ValueError ordering','early_invalid_warn':warn.warnings,'warn_not_executed':True}))

def test_explicit_earlier_required_occurrence_does_not_depend_on_future_occurrence():
 r,c,_=_occurrence_chain();control=c.build(validate_semantics=Level.STRICT);assert execute_heterogeneous_chain(control,state={'value':2},registry=r).final_state['value']==31
 r,c,nodes=_occurrence_chain(requires=True);print(json.dumps({'actual_control_final_value':31,'explicit_edges':[(str(a),str(b)) for a,b in c.dag.edges],'required_earlier_id':str(nodes[0].id),'future_same_FQN_id':str(nodes[2].id)}),flush=True)
 chain=c.build(validate_semantics=Level.STRICT);assert execute_heterogeneous_chain(chain,state={'value':2},registry=r).final_state['value']==31

def test_duplicate_producer_strict_refusal_warn_visible_actual_merge():
 a=method('first',(),(slot('value'),),lambda s,p:{'value':10});b=method('second',(),(slot('value'),),lambda s,p:{'value':20});t=method('target',(slot('value'),),(slot('result'),),lambda s,p:{'result':s['value']});r=registry(a,b,t);c=MethodComposer(registry=r);na=c.add(a.signature.fqn);nb=c.add(b.signature.fqn);nt=c.add(t.signature.fqn);c.connect(na,nt,{'value':'value'});c.connect(nb,nt,{'value':'value'})
 with pytest.raises(ValueError,match='connected multiple times'):c.build(validate_semantics=Level.STRICT)
 warn=c.build(validate_semantics=Level.WARN);assert any('connected multiple times' in x for x in warn.warnings)
 r,c,a,b,m=_multi_source(SlotLinker());c.connect(a,m,{'value':'left'});c.connect(b,m,{'value':'right'});merge=c.build(validate_semantics=Level.STRICT);value=execute_heterogeneous_chain(merge,state={},registry=r).final_state['result'];assert value==30
 print(json.dumps({'strict_duplicate':'ValueError','warn_diagnostics':warn.warnings,'warn_not_authority_or_execution':True,'actual_merge_result':value}))

def test_same_semantic_gate_and_actual_positive_for_manual_auto():
 outcomes={}
 for explicit in [False,True]:
  r,c,na,nb,_=scalar_chain('outcome','residual',SlotLinker(LinkerConfig.semantic_strict()),explicit);chain=c.build(validate_semantics=Level.STRICT);value=execute_heterogeneous_chain(chain,state={'residual':100},registry=r).final_state['result'];assert value==21
  a=method('bad_source',(),(slot('outcome'),),lambda s,p:{'outcome':7});b=method('bad_target',(slot('treatment'),),(slot('result'),),lambda s,p:{'result':s['treatment']*3});r=registry(a,b);c=MethodComposer(registry=r,linker=SlotLinker(LinkerConfig.semantic_strict()));na=c.add(a.signature.fqn);nb=c.add(b.signature.fqn)
  with pytest.raises(SemanticCompatibilityError):c.connect(na,nb,{'outcome':'treatment'} if explicit else None)
  outcomes[str(explicit)]={'actual_allowed_value':value,'forbidden_type':'SemanticCompatibilityError'}
 print(json.dumps(outcomes))
@pytest.mark.parametrize('gate',['unit','shape','partial'])
def test_both_typed_structural_paths_refuse_before_execution(gate):
 record={}
 for explicit in [False,True]:
  a_slots=(slot('source',unit=Unit('currency','USD')),) if gate=='unit' else (slot('source',shape=(2,),kind=SlotType.VECTOR),) if gate=='shape' else (slot('required'),)
  b_slots=(slot('target',unit=Unit('time','yr')),) if gate=='unit' else (slot('target',shape=(3,),kind=SlotType.VECTOR),) if gate=='shape' else (slot('required'),slot('missing'))
  calls=[];a=method('structural_source',(),a_slots,lambda s,p:(calls.append('SOURCE') or {a_slots[0].name:np.array([7,8]) if gate=='shape' else 7}));b=method('structural_target',b_slots,(slot('result'),),lambda s,p:(calls.append('TARGET') or {'result':7}));r=registry(a,b);c=MethodComposer(registry=r,linker=SlotLinker(LinkerConfig.strict()));na=c.add(a.signature.fqn);nb=c.add(b.signature.fqn);mapping={a_slots[0].name:b_slots[0].name} if explicit else None
  try:c.connect(na,nb,mapping)
  except (SlotConnectionError,ValueError) as exc:record[str(explicit)]={'type':type(exc).__name__,'message':str(exc),'producer_calls':calls}
  else:raise AssertionError('structural mismatch admitted')
  assert not calls
 print(json.dumps({'gate':gate,'actual_routes':record}))

def test_actual_requires_cycle_rejected_before_any_method_run():
 calls=[];a=method('cycle_a',(),(slot('a'),),lambda s,p:calls.append('a'),requires=('review.composition.cycle_b@1.0.0',));b=method('cycle_b',(),(slot('b'),),lambda s,p:calls.append('b'),requires=(a.signature.fqn,));r=registry(a,b);c=MethodComposer(registry=r);c.add(a.signature.fqn);c.add(b.signature.fqn)
 with pytest.raises(CyclicDependencyError):c.build(validate_semantics=Level.STRICT)
 assert not calls


def test_missing_required_async_module_is_addressed_error_not_permanent_unavailable():
 worker=pathlib.Path(__file__).with_name('import_worker.py');p=subprocess.run([sys.executable,str(worker),'missing'],cwd=ROOT/'policy-engine',capture_output=True,text=True,timeout=20)
 assert p.returncode==0,p.stdout+p.stderr;record=json.loads(p.stdout.split('RESULT:')[1]);assert record['type']=='ModuleNotFoundError' and record['name']=='polisyos.foundry.methods.backends.async_chain_executor';print(json.dumps(record))
