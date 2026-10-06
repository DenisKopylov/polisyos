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
from decimal import Decimal
import copy
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
from polisyos.core.artifacts.manifest import SchemaInfo,ProducerInfo
from polisyos.core.canon import from_canonical_bytes,to_canonical_bytes
from polisyos.core.components import Capability,ComponentId,ComponentKind,ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.protocol import NodeSpec,NodeOutcome
from polisyos.scientist.orchestration.engine.state_branching import branch_state,snapshot_state
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache,NodeCacheEntry,compute_idempotency_key
import polisyos.scientist.orchestration.engine.idempotency as idem
out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);store=FileSystemCAS(out/'cas');run=RunContext.start(store,build_default_registry_bundle(store).bundle_ref,run_id='R_independent_group_type')
meta=ComponentMetadata(component_id=ComponentId.parse('scientist.independent_group_type@1.0.0'),kind=ComponentKind.SCIENTIST_NODE,abi_targets={'world_abi':'1.x'},display_name='Native grouped primitive consumer',description='Malformed grouped journal through actual typed CAS cache input',capabilities=Capability.SCIENTIST_NODE)
spec=NodeSpec(metadata=meta,state_reads=['params.x'],state_writes=['params']);rows=[]
for name,left,right,consistent in [('same_false_control',False,False,True),('false_zero_distinct_primitives',False,0,False),('nested_false_zero_distinct',{'items':[False]},{'items':[0]},False)]:
 base=ExperimentState(run_id=run.run_manifest.run_id,params={'x':2,'left':{'v':7},'right':{'v':7}},budgets={'neighbor_reserved_usd':Decimal('73')});branch=branch_state(base,write_paths=('params',),enforce_write_scope=True)
 branch.state.params['left']['v']=left;branch.state.params['right']['v']=right
 writer=NodeResultCache(store,base.run_id);key=compute_idempotency_key(spec,base,bind_params={'case':name});original=writer.put(key,str(meta.component_id),NodeOutcome(status='ok',state=branch.state));assert store.verify(original).ok;originalraw=store.get_bytes(original);payload=from_canonical_bytes(originalraw)
 original_reader=NodeResultCache(FileSystemCAS(store.root),base.run_id);original_admitted=original_reader.load_entry(original);assert original_admitted and original_reader.get(key) is not None
 entry=NodeCacheEntry.model_validate(payload);ops=tuple(op.model_copy(update={'operation_group':0}) for op in entry.state_mutations);assert len(ops)==2
 entry=entry.model_copy(update={'state_mutations':ops});proof=entry.journal_proof;assert proof is not None
 digest=idem._journal_proof_hash(entry,manifest_schema=SchemaInfo.model_validate(proof.manifest_schema),manifest_producer=ProducerInfo.model_validate(proof.manifest_producer));entry=entry.model_copy(update={'journal_proof':proof.model_copy(update={'payload_hash':digest})})
 raw=to_canonical_bytes(entry.model_dump(mode='python',by_alias=True,exclude_none=False),idem._IDEM_CANON)
 ref=store.put_bytes(raw,PutOptions(kind='scientist.node_cache_entry',media_type='application/json',schema=SchemaInfo.model_validate(proof.manifest_schema),producer=ProducerInfo.model_validate(proof.manifest_producer)));assert store.verify(ref).ok and store.get_bytes(ref)==raw
 reader=NodeResultCache(FileSystemCAS(store.root),base.run_id);admitted=reader.load_entry(ref);loaded=reader.get(key)
 row={'case':name,'expected_consistent_group':consistent,'admitted':admitted,'get_present':loaded is not None,'original_native_admitted':original_admitted,'original_native_producer_ref':original.model_dump(mode='json'),'original_native_producer_bytes':originalraw.decode(),'grouped_ref':ref.model_dump(mode='json'),'grouped_bytes':raw.decode(),'grouped_sha256':hashlib.sha256(raw).hexdigest(),'mutation_difference':'Only operation_group=None→0 on two native independent intents; journal proof hash recomputed using actual versioned _journal_proof_hash helper/config, including replay epoch and immutable manifest metadata. All original values/proof metadata/state/context retained. Integrity/version valid; purpose is malformed-group semantic validation, not a claim the ordinary producer emits bad groups.','pass':admitted is consistent and (loaded is not None) is consistent}
 if loaded is not None:
  current=ExperimentState(run_id=base.run_id,params={'x':2,'left':{},'right':{},'neighbor':'current'},budgets={'neighbor_reserved_usd':Decimal('79')});shared={'v':7};current.params['left']=shared;current.params['right']=shared;assert current.params['left'] is current.params['right']
  result=merge_parallel_outcomes(current,{'loaded':loaded},{'loaded':['params']}).state
  resultref=store.put_json(snapshot_state(result).model_dump(mode='python'),PutOptions(kind='scientist.independent_grouped_result',media_type='application/json'));assert store.verify(resultref).ok;actual=json.loads(store.get_bytes(resultref))['params']
  row.update({'actual_current_aliased_result':actual,'actual_types':[type(actual['left']['v']).__name__,type(actual['right']['v']).__name__],'result_ref':resultref.model_dump(mode='json'),'result_bytes':store.get_bytes(resultref).decode(),'neighbor_reserved_usd':str(result.budgets['neighbor_reserved_usd'])})
  if consistent:row['pass']=row['pass'] and actual['left']['v'] is False and actual['right']['v'] is False and actual['neighbor']=='current' and result.budgets['neighbor_reserved_usd']==Decimal('79')
 rows.append(row)
packet={'target_sha':sha,'target_tree':subprocess.check_output(['git','rev-parse',sha+'^{tree}'],cwd=repo,text=True).strip(),'python':sys.executable,'source_identity':loaded_git_sources,'authority_purpose':'Native producer supplies valid independent events; fixture changes grouping label to test actual cache input contract consistency. Valid integrity/provenance metadata does not establish semantic sameintent; reader explicitly checks it. Actual CAS→load/get→physical aliased merge consumer, no source replacement.','cases':rows,'pass':all(r['pass'] for r in rows)}
(out/'receipt.json').write_text(json.dumps(packet,indent=2)+'\n');print(json.dumps(packet,indent=2))
