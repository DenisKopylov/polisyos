import argparse,copy
_arg=argparse.ArgumentParser();_arg.add_argument("--target",required=True);_arg.add_argument("--out",required=True);_arg.add_argument("--legacy-packet");args=_arg.parse_args()
import importlib.abc,importlib.util,hashlib,json,pathlib,subprocess,sys,types,asyncio,logging,os
from decimal import Decimal
repo=pathlib.Path('/workspace/e02-B-current-execution-state');sha=args.target
source_prefix='policy-engine/src/'
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',sha,'--','policy-engine/src/polisyos'],cwd=repo,text=True).splitlines()
module_paths={}
for path in paths:
 if not path.endswith('.py'):continue
 name=path[len(source_prefix):-3].replace('/','.')
 package=name.endswith('.__init__')
 if package:name=name[:-9]
 module_paths[name]=(path,package)
loaded_git_sources={}
class GitSourceLoader(importlib.abc.Loader):
 def __init__(self,name,path,package):self.name=name;self.path=path;self.package=package
 def create_module(self,spec):return None
 def exec_module(self,module):
  raw=subprocess.check_output(['git','show',sha+':'+self.path],cwd=repo)
  module.__file__=str(repo/self.path)
  if self.package:module.__path__=[str((repo/self.path).parent)]
  loaded_git_sources[self.path]=hashlib.sha256(raw).hexdigest()
  exec(compile(raw,sha+':'+self.path,'exec'),module.__dict__)
class GitSourceFinder(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in module_paths:
   path,package=module_paths[fullname]
   return importlib.util.spec_from_loader(fullname,GitSourceLoader(fullname,path,package),origin=sha+':'+path,is_package=package)
  if fullname=='polisyos' or fullname.startswith('polisyos.'):
   raise ModuleNotFoundError('canonical module absent at exact Git target: '+fullname)
sys.meta_path.insert(0,GitSourceFinder())
import hashlib,json,pathlib,subprocess,sys
from decimal import Decimal
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability,ComponentId,ComponentKind,ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome,NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state,snapshot_state
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes,StateReplayIncompatible
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache,compute_idempotency_key
from polisyos.scientist.orchestration.engine.runner.serialization import serialize_state_safe as native_serialize_state_safe
def state_bytes(state):
 return native_serialize_state_safe(ExperimentState.model_validate(state.model_dump(mode="python",by_alias=True,exclude_none=False)))[0]
repo=pathlib.Path('/workspace/e02-B-current-execution-state')
sha=args.target
out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
paths=['state_branching.py','state_merge.py','idempotency.py','state.py']
identities={}
for name in paths:
 path='policy-engine/src/polisyos/scientist/orchestration/engine/'+name
 raw=subprocess.check_output(['git','show',sha+':'+path],cwd=repo)
 assert hashlib.sha256(raw).hexdigest()==loaded_git_sources[path]
 identities[path]=hashlib.sha256(raw).hexdigest()
store=FileSystemCAS(out/'cas')
bundle=build_default_registry_bundle(store)
run=RunContext.start(store,bundle.bundle_ref,run_id='R_independent_STA')
spec=NodeSpec(metadata=ComponentMetadata(component_id=ComponentId.parse('scientist.independent_sta@1.0.0'),kind=ComponentKind.SCIENTIST_NODE,abi_targets={'world_abi':'1.x'},display_name='STA semantic oracle',description='Actual journal/cache consumer',capabilities=Capability.SCIENTIST_NODE),state_reads=['params.x'],state_writes=['params'])
rows=[];public_result=[]
def replay_case(name,mutate,initial,current_params,expected):
 base=ExperimentState(run_id='R_independent_STA',params=initial,budgets={'neighbor_reserved_usd':Decimal('7')})
 retained=state_bytes(base)
 sibling=branch_state(base,write_paths=('params',)).state
 sibling_before=state_bytes(sibling)
 branch=branch_state(base,write_paths=('params',))
 mutate(branch.state.params)
 assert state_bytes(base)==retained and state_bytes(sibling)==sibling_before
 producer_params=branch.state.model_dump(mode='json')['params']
 expected_native=copy.deepcopy(initial);mutate(expected_native)
 producer_matches_native=producer_params==expected_native
 outcome=NodeOutcome(status='ok',state=branch.state)
 key=compute_idempotency_key(spec,base,bind_params={'case':name})
 writer=NodeResultCache(store,base.run_id)
 ref=writer.put(key,str(spec.metadata.component_id),outcome)
 assert store.verify(ref).ok
 payload=store.get_bytes(ref)
 entry=from_canonical_bytes(payload)
 current=ExperimentState(run_id=base.run_id,params=current_params,budgets={'neighbor_reserved_usd':Decimal('11')})
 current_before=state_bytes(current)
 results=[]
 for profile,reader in [('warm',writer),('reopened',NodeResultCache(FileSystemCAS(store.root),base.run_id))]:
  if profile=='reopened': assert reader.load_entry(ref)
  loaded=reader.get(key)
  assert loaded is not None
  try:
   merged=merge_parallel_outcomes(current,{'producer':loaded},{'producer':['params']})
  except Exception as exc:
   results.append({'profile':profile,'error':{'type':type(exc).__name__,'message':str(exc)},'pass':False,'reserved_usd':str(current.budgets['neighbor_reserved_usd']),'base_bytes_unchanged':state_bytes(current)==current_before})
   continue
  assert state_bytes(current)==current_before
  result_ref=store.put_json(snapshot_state(merged.state).model_dump(mode='python'),PutOptions(kind='scientist.independent_sta_result',media_type='application/json'))
  assert store.verify(result_ref).ok
  physical=json.loads(store.get_bytes(result_ref))
  actual=physical['params']
  run.emit('independent.STA','STA_RESULT',outputs=[result_ref],metrics={'matched':int(actual==expected)})
  results.append({'profile':profile,'actual':actual,'expected':expected,'pass':actual==expected,'reserved_usd':str(merged.state.budgets['neighbor_reserved_usd']),'result_ref':result_ref.model_dump(mode='json'),'result_bytes':store.get_bytes(result_ref).decode()})
  if name=='same_value_scalar' and profile=='warm':
   before=state_bytes(merged.state)
   try:
    merged.state.params['post']={'values':[3]};merged.state.params['post']['values'].append(4)
    postref=store.put_json(snapshot_state(merged.state).model_dump(mode='python'),PutOptions(kind='scientist.independent_public_result',media_type='application/json'));assert store.verify(postref).ok
    postactual=json.loads(store.get_bytes(postref))['params'];public_result.append({'pass':postactual['post']=={'values':[3,4]},'actual':postactual,'result_ref':postref.model_dump(mode='json'),'result_bytes':store.get_bytes(postref).decode()})
   except Exception as exc:public_result.append({'pass':False,'error':{'type':type(exc).__name__,'message':str(exc)},'wire_unchanged_after_rejection':state_bytes(merged.state)==before})

 rows.append({'case':name,'producer_params':producer_params,'expected_native_python_values':expected_native,'producer_matches_native_python':producer_matches_native,'cache_ref':ref.model_dump(mode='json'),'cache_sha256':hashlib.sha256(payload).hexdigest(),'cache_bytes':payload.decode(),'operations':entry['state_mutations'],'base_and_sibling_unchanged':True,'current_base_unchanged':True,'results':results,'pass':producer_matches_native and all(x['pass'] and x['reserved_usd']=='11' for x in results)})

def standard():return {'x':2,'rows':[{'id':'a','v':1},{'id':'b','v':2}],'neighbor':{'queue':['kept'],'v':7},'scalar':7}
def pop_append(p):
 held=p['rows'].pop(0);p['rows'].append(held);held['v']=5
def cross_alias(p):
 held=p['rows'][0];p['alias']=held;held['v']=5
def reparent(p):
 held=p['rows'].pop(0);p['moved']=held;held['v']=5
def initial_alias():
 shared={'v':1};return {'x':2,'left':shared,'right':shared,'neighbor':{'queue':['kept'],'v':7},'scalar':7}
def shared_mutation(p):p['left']['v']=5
def numeric_initial():return {'x':2,'numeric':{'0':{'v':1}},'neighbor':{'queue':['kept'],'v':7},'scalar':7}
def numeric(p):p['numeric']['0']['v']=5
def scalar(p):p['scalar']=7
for name,initial,mutate in [('pop_append_held_path_changed',standard,pop_append),('cross_container_alias',standard,cross_alias),('reparent_held_descendant',standard,reparent),('initial_shared_dict_alias',initial_alias,shared_mutation),('numeric_dict_key',numeric_initial,numeric),('same_value_scalar',standard,scalar)]:
 inp=initial();current=initial();current['neighbor']={'queue':['current'],'v':13};expected=initial();mutate(expected);expected['neighbor']={'queue':['current'],'v':13}
 replay_case(name,mutate,inp,current,expected)
base=ExperimentState(run_id='R_independent_STA',params=standard(),budgets={'neighbor_reserved_usd':Decimal('17')})
branch=branch_state(base,write_paths=('params.rows',));before=state_bytes(branch.state);base_before=state_bytes(base)
evidence=store.put_bytes(base_before,PutOptions(kind='scientist.independent_retained_state',media_type='application/octet-stream'));evidence_before=store.get_bytes(evidence)
try:branch.state.params['neighbor']['v']=99;rejection=None
except Exception as exc:rejection={'type':type(exc).__name__,'message':str(exc),'code':getattr(exc,'code',None)}
undeclared={'case':'undeclared_neighbor_fail_before_write','error':rejection,'base_wire_unchanged':state_bytes(base)==base_before,'branch_wire_unchanged':state_bytes(branch.state)==before,'retained_actual_artifact_unchanged':store.get_bytes(evidence)==evidence_before and store.verify(evidence).ok,'retained_ref':evidence.model_dump(mode='json'),'retained_wire_sha256':hashlib.sha256(evidence_before).hexdigest(),'reserved_usd':str(base.budgets['neighbor_reserved_usd']),'pass':rejection is not None and state_bytes(base)==base_before and state_bytes(branch.state)==before and store.get_bytes(evidence)==evidence_before and store.verify(evidence).ok and base.budgets['neighbor_reserved_usd']==Decimal('17')}

artifact=store.put_json({'evidence':'retained'},PutOptions(kind='scientist.independent_evidence',media_type='application/json'))
base=ExperimentState(run_id='R_independent_STA',params={'safe':1},artifacts_index={'evidence':artifact},budgets={'neighbor_reserved_usd':Decimal('13')})
retained=state_bytes(base)
retained_artifact=store.get_bytes(artifact)
branch=branch_state(base,write_paths=('params','artifacts_index'))
branch.state.params['safe']=2
del branch.state.artifacts_index['evidence']
try:
 merge_parallel_outcomes(base,{'producer':NodeOutcome(status='ok',state=branch.state)},{'producer':['params','artifacts_index']})
 rejection=None
except StateReplayIncompatible as exc:
 rejection={'type':type(exc).__name__,'code':exc.code,'path':exc.path,'reason':exc.reason}
rows.append({'case':'protected_delete_atomic_rejection','rejection':rejection,'base_serialized_sha256':hashlib.sha256(retained).hexdigest(),'base_bytes_unchanged':state_bytes(base)==retained,'retained_evidence_bytes_unchanged':store.get_bytes(artifact)==retained_artifact,'evidence_verified':store.verify(artifact).ok,'reserved_usd':str(base.budgets['neighbor_reserved_usd']),'pass':rejection is not None and state_bytes(base)==retained and store.get_bytes(artifact)==retained_artifact and base.budgets['neighbor_reserved_usd']==Decimal('13')})

legacy=[];legacy_input=None
if args.legacy_packet:
 from polisyos.core.artifacts.manifest import SchemaInfo,ProducerInfo
 inputpath=pathlib.Path(args.legacy_packet);inputraw=inputpath.read_bytes();prior=json.loads(inputraw);legacy_input={'path':str(inputpath),'sha256':hashlib.sha256(inputraw).hexdigest(),'bytes':len(inputraw),'source_sha':prior['target_sha']}
 for oldcase in prior['cases']:
  if 'cache_bytes' not in oldcase:continue
  raw=oldcase['cache_bytes'].encode();assert hashlib.sha256(raw).hexdigest()==oldcase['cache_sha256'];payload=from_canonical_bytes(raw);proof=payload['journal_proof']
  ref=store.put_bytes(raw,PutOptions(kind=oldcase['cache_ref']['kind'],media_type=oldcase['cache_ref']['media_type'],schema=SchemaInfo.model_validate(proof['manifest_schema']),producer=ProducerInfo.model_validate(proof['manifest_producer'])));assert store.verify(ref).ok and store.get_bytes(ref)==raw
  reader=NodeResultCache(FileSystemCAS(store.root),payload['run_id']);admitted=reader.load_entry(ref);outcome=reader.get(payload['idempotency_key']);unsafe=not oldcase['producer_matches_native_python'];safe=oldcase['case']=='same_value_scalar'
  deciding=unsafe or safe
  row={'case':oldcase['case'],'version':payload['state_mutations_version'],'actual_old_producer_correct':oldcase['producer_matches_native_python'],'admitted':admitted,'get_present':outcome is not None,'artifact_bytes_unchanged':store.get_bytes(ref)==raw,'cache_ref':ref.model_dump(mode='json'),'deciding_admission_expectation':False if unsafe else True if safe else 'nondeciding_numeric_control','pass':not deciding or (admitted is safe and (outcome is not None) is safe)}
  if safe and admitted:
   current=ExperimentState(run_id='R_independent_STA',params=standard(),budgets={'neighbor_reserved_usd':Decimal('31')});current.params['scalar']=99;current.params['neighbor']={'queue':['current'],'v':13};result=merge_parallel_outcomes(current,{'legacy':outcome},{'legacy':['params']}).state
   result_ref=store.put_json(snapshot_state(result).model_dump(mode='python'),PutOptions(kind='scientist.independent_legacy_scalar_result',media_type='application/json'));assert store.verify(result_ref).ok
   actual=json.loads(store.get_bytes(result_ref))['params'];row.update({'actual':actual,'result_ref':result_ref.model_dump(mode='json'),'result_bytes':store.get_bytes(result_ref).decode(),'reserved_usd':str(result.budgets['neighbor_reserved_usd'])});row['pass']=row['pass'] and actual['scalar']==7 and actual['neighbor']=={'queue':['current'],'v':13} and result.budgets['neighbor_reserved_usd']==Decimal('31')
  legacy.append(row)
packet={'target_sha':sha,'target_tree':subprocess.check_output(['git','rev-parse',sha+'^{tree}'],cwd=repo,text=True).strip(),'source_identity':loaded_git_sources,'source_loading':'All canonical imported Python modules loaded from exact Git target; third-party venv/resource paths are separately supplied from admitted EXE lane. No new checkout or source/tests edits.','python':sys.executable,'cases':rows,'undeclared_neighbor':undeclared,'public_result_edit':public_result,'legacy_input':legacy_input,'legacy':legacy,'pass':all(x['pass'] for x in rows) and undeclared['pass'] and len(public_result)==1 and public_result[0]['pass'] and all(x['pass'] for x in legacy),'trace_bytes':run.trace_path.read_text()}
(out/'receipt.json').write_text(json.dumps(packet,indent=2)+'\n')
print(json.dumps(packet,indent=2))
