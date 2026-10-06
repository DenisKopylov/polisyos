import hashlib,json,pathlib,subprocess,sys
from decimal import Decimal
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
from polisyos.core.artifacts.manifest import SchemaInfo,ProducerInfo
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome,NodeSpec
from polisyos.core.components import ComponentMetadata,ComponentId,ComponentKind,Capability
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache,compute_idempotency_key
repo=pathlib.Path('/workspace/e02-B-current-runtime');target=pathlib.Path('/workspace/e02-B-current-execution-state')
sha='3b81bf197be10e20208f8d1925fd8d63eca74da9'
source_identity={}
for name in ['state_branching.py','state_merge.py','idempotency.py']:
 path='policy-engine/src/polisyos/scientist/orchestration/engine/'+name
 raw=subprocess.check_output(['git','show',sha+':'+path],cwd=target)
 assert raw==(target/path).read_bytes()
 source_identity[path]=hashlib.sha256(raw).hexdigest()
negative_path='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/current-sta-independent-review/journal-negative.json'
negative_raw=subprocess.check_output(['git','show','41b6b7ce1237e921a68d4322b27a1e9b3100569f:'+negative_path],cwd=repo)
assert hashlib.sha256(negative_raw).hexdigest()=='12033cfe8799bbec98683359c2f3efb0a5e701a470fc75bd4cb35c6e95217d6e'
negative=json.loads(negative_raw)
out=repo/'_build/e02-current-runtime/sta-review/legacy-ownership-oracle-v2';store=FileSystemCAS(out/'cas')
run=RunContext.start(store,build_default_registry_bundle(store).bundle_ref,run_id='R_independent_STA')
legacy=[]
for case in negative['cases'][:3]:
 raw=case['cache_bytes'].encode();assert hashlib.sha256(raw).hexdigest()==case['cache_sha256']
 entry=from_canonical_bytes(raw);proof=entry['journal_proof']
 ref=store.put_bytes(raw,PutOptions(kind=case['cache_ref']['kind'],media_type=case['cache_ref']['media_type'],schema=SchemaInfo.model_validate(proof['manifest_schema']),producer=ProducerInfo.model_validate(proof['manifest_producer'])))
 assert store.verify(ref).ok and store.get_bytes(ref)==raw
 reader=NodeResultCache(FileSystemCAS(store.root),entry['run_id']);admitted=reader.load_entry(ref);loaded=reader.get(entry['idempotency_key'])
 scalar=case['case']=='same_value_delete_null_no_write'
 assert admitted is scalar and (loaded is not None) is scalar
 row={'case':case['case'],'legacy_version':entry['state_mutations_version'],'cache_ref':ref.model_dump(mode='json'),'artifact_bytes_unchanged':True,'admitted':admitted,'pass':True}
 if scalar:
  base=ExperimentState(run_id=entry['run_id'],params={'x':2,'y':9,'stale':1,'nullable':'current','untouched':'new'},budgets={'neighbor_reserved_usd':Decimal('11')})
  merged=merge_parallel_outcomes(base,{'old':loaded},{'old':['params']}).state
  assert merged.params=={'x':2,'y':4,'nullable':None,'untouched':'new'} and merged.budgets['neighbor_reserved_usd']==Decimal('11')
  row['actual']=merged.model_dump(mode='json')['params'];row['reserved_usd']=str(merged.budgets['neighbor_reserved_usd'])
 run.emit('independent.legacy','LEGACY_CACHE_ADMISSION',outputs=[ref],metrics={'admitted':int(admitted)})
 legacy.append(row)

live=[]
def check(name,mutate,expected):
 base=ExperimentState(run_id='R_independent_STA',params={'rows':[{'id':'old','v':1}],'neighbor':{'queue':['kept']}},budgets={'neighbor_reserved_usd':Decimal('23')})
 branch=branch_state(base,write_paths=('params.rows',))
 mutate(branch.state.params['rows'])
 producer=branch.state.model_dump(mode='json')['params']['rows'];assert producer==expected
 writer=NodeResultCache(store,base.run_id)
 spec=NodeSpec(metadata=ComponentMetadata(component_id=ComponentId.parse('scientist.independent_live@1.0.0'),kind=ComponentKind.SCIENTIST_NODE,abi_targets={'world_abi':'1.x'},display_name='Independent live ownership',description='Actual captured operation replay',capabilities=Capability.SCIENTIST_NODE),state_reads=['params.rows'],state_writes=['params.rows'])
 key=compute_idempotency_key(spec,base,bind_params={'case':name})
 ref=writer.put(key,'scientist.independent_live@1.0.0',NodeOutcome(status='ok',state=branch.state))
 payload=from_canonical_bytes(store.get_bytes(ref));assert payload['state_mutations_version']=='1.1'
 profiles=[]
 for label,reader in [('warm',writer),('reopened',NodeResultCache(FileSystemCAS(store.root),base.run_id))]:
  if label=='reopened':assert reader.load_entry(ref)
  outcome=reader.get(key);assert outcome is not None
  result=merge_parallel_outcomes(base,{'live':outcome},{'live':['params.rows']}).state
  result_ref=store.put_json(result.model_dump(mode='python'),PutOptions(kind='scientist.independent_live_result',media_type='application/json'))
  assert store.verify(result_ref).ok
  actual=json.loads(store.get_bytes(result_ref))['params']['rows'];assert actual==expected
  assert result.params['neighbor']=={'queue':['kept']} and result.budgets['neighbor_reserved_usd']==Decimal('23')
  assert base.params['rows']==[{'id':'old','v':1}]
  profiles.append({'profile':label,'actual':actual,'result_ref':result_ref.model_dump(mode='json'),'result_bytes':store.get_bytes(result_ref).decode(),'reserved_usd':'23'})
 live.append({'case':name,'producer':producer,'operations':payload['state_mutations'],'profiles':profiles,'pass':True})
def held(rows):
 old=rows[0];rows.insert(0,{'id':'new','v':0});old['v']=5
check('held_shifted_descendant',held,[{'id':'new','v':0},{'id':'old','v':5}])
def repeated(rows):
 old=rows[0];rows*=2;old['v']=5
check('held_repeated_same_object',repeated,[{'id':'old','v':5},{'id':'old','v':5}])
def detached(rows):
 old=rows.pop();old['v']=99
check('detached_descendant_no_new_state_intent',detached,[])
packet={'target_sha':sha,'source_identity':source_identity,'python':sys.executable,'input_negative_commit':'41b6b7ce1237e921a68d4322b27a1e9b3100569f','input_negative_sha256':hashlib.sha256(negative_raw).hexdigest(),'legacy':legacy,'live':live,'trace_utf8':run.trace_path.read_text(),'pass':True}
(out/'receipt.json').write_text(json.dumps(packet,indent=2)+'\n');print(json.dumps(packet,indent=2))
