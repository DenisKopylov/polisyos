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
sha='1bd1fd11b683bbade5411a71b02706ea206b149d'
out=pathlib.Path('/workspace/e02-B-current-runtime/_build/e02-current-runtime/sta-review/journal-oracle-v3')
paths=['state_branching.py','state_merge.py','idempotency.py','state.py']
identities={}
for name in paths:
 path='policy-engine/src/polisyos/scientist/orchestration/engine/'+name
 raw=subprocess.check_output(['git','show',sha+':'+path],cwd=repo)
 assert raw==(repo/path).read_bytes()
 identities[path]=hashlib.sha256(raw).hexdigest()
store=FileSystemCAS(out/'cas')
bundle=build_default_registry_bundle(store)
run=RunContext.start(store,bundle.bundle_ref,run_id='R_independent_STA')
spec=NodeSpec(metadata=ComponentMetadata(component_id=ComponentId.parse('scientist.independent_sta@1.0.0'),kind=ComponentKind.SCIENTIST_NODE,abi_targets={'world_abi':'1.x'},display_name='STA semantic oracle',description='Actual journal/cache consumer',capabilities=Capability.SCIENTIST_NODE),state_reads=['params.x'],state_writes=['params'])
rows=[]
def replay_case(name,mutate,initial,current_params,expected):
 base=ExperimentState(run_id='R_independent_STA',params=initial,budgets={'neighbor_reserved_usd':Decimal('7')})
 retained=state_bytes(base)
 sibling=branch_state(base,write_paths=('params',)).state
 sibling_before=state_bytes(sibling)
 branch=branch_state(base,write_paths=('params',))
 mutate(branch.state.params)
 assert state_bytes(base)==retained and state_bytes(sibling)==sibling_before
 producer_params=branch.state.model_dump(mode='json')['params']
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
 rows.append({'case':name,'producer_params':producer_params,'cache_ref':ref.model_dump(mode='json'),'cache_sha256':hashlib.sha256(payload).hexdigest(),'cache_bytes':payload.decode(),'operations':entry['state_mutations'],'base_and_sibling_unchanged':True,'current_base_unchanged':True,'results':results,'pass':all(x['pass'] and x['reserved_usd']=='11' for x in results)})

def shifted(p):
 p['rows'].insert(0,{'id':'new','v':0})
 p['rows'][1]['v']=5
replay_case('insert_then_existing_nested_write',shifted,{'x':2,'rows':[{'id':'old','v':1}],'unrelated':'old'}, {'x':2,'rows':[{'id':'old','v':1}],'unrelated':'new'}, {'x':2,'rows':[{'id':'new','v':0},{'id':'old','v':5}],'unrelated':'new'})

def unchanged(p):
 p['rows'][0]['v']=5
replay_case('no_shift_nested_positive',unchanged,{'x':2,'rows':[{'id':'old','v':1}],'unrelated':'old'}, {'x':2,'rows':[{'id':'old','v':1}],'unrelated':'new'}, {'x':2,'rows':[{'id':'old','v':5}],'unrelated':'new'})

def intents(p):
 p['y']=4
 del p['stale']
 p['nullable']=None
replay_case('same_value_delete_null_no_write',intents,{'x':2,'y':4,'stale':1,'nullable':'prior','untouched':'old'}, {'x':2,'y':9,'stale':1,'nullable':'current','untouched':'new'}, {'x':2,'y':4,'nullable':None,'untouched':'new'})
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
packet={'target_sha':sha,'source_identity':identities,'python':sys.executable,'cases':rows,'pass':all(x['pass'] for x in rows),'trace_bytes':run.trace_path.read_text()}
(out/'receipt.json').write_text(json.dumps(packet,indent=2)+'\n')
print(json.dumps(packet,indent=2))
