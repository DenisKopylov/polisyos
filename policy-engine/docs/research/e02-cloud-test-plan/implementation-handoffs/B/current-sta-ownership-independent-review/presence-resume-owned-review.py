import argparse,inspect
_arg=argparse.ArgumentParser();_arg.add_argument('--target',required=True);_arg.add_argument('--out',required=True);args=_arg.parse_args()
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
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
from polisyos.core.canon import from_canonical_bytes,to_canonical_bytes,CanonSpec
from polisyos.core.components import Capability,ComponentId,ComponentKind,ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome,NodeSpec,NodeError
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache,compute_idempotency_key,compute_idempotency_payload
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec,NodeInvocation
from polisyos.scientist.orchestration.engine.checkpoint import CASCheckpointHook,resolve_latest_checkpoint,resume_from_checkpoint,compute_workflow_fingerprint,WorkflowMismatchError
out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
identities={}
def metadata(name):
 return ComponentMetadata(component_id=ComponentId.parse('scientist.independent_'+name+'@1.0.0'),kind=ComponentKind.SCIENTIST_NODE,abi_targets={'world_abi':'1.x'},display_name='Independent '+name,description='Actual state semantic consumer',capabilities=Capability.SCIENTIST_NODE)
def state_for(params,run_id):return ExperimentState(run_id=run_id,params=params,budgets={'neighbor_reserved_usd':Decimal('19')})
store=FileSystemCAS(out/'presence'/'cas');bundle=build_default_registry_bundle(store);run=RunContext.start(store,bundle.bundle_ref,run_id='R_independent_presence')
spec=NodeSpec(metadata=metadata('presence'),state_reads=['params.options.threshold'],state_writes=['params.effective'])
writer=NodeResultCache(store,run.run_manifest.run_id);rows=[];calls=0;refs=[]
for label,params in [('missing_leaf',{'options':{},'neighbor':{'queue':['kept']}}),('null_leaf',{'options':{'threshold':None},'neighbor':{'queue':['kept']}}),('zero',{'options':{'threshold':0},'neighbor':{'queue':['kept']}}),('false',{'options':{'threshold':False},'neighbor':{'queue':['kept']}}),('empty_list',{'options':{'threshold':[]},'neighbor':{'queue':['kept']}})]:
 base=state_for(params,run.run_manifest.run_id);key=compute_idempotency_key(spec,base);assert writer.get(key) is None
 expected_native_effective=base.params.get('options',{}).get('threshold',5)
 branch=branch_state(base,write_paths=spec.state_writes,**({'enforce_write_scope':True} if 'enforce_write_scope' in inspect.signature(branch_state).parameters else {}))
 effective=branch.state.params.get('options',{}).get('threshold',5)
 calls+=1;branch.state.params['effective']=effective
 evidence=store.put_json({'label':label,'effective':effective},PutOptions(kind='scientist.independent_presence',media_type='application/json'))
 ref=writer.put(key,str(spec.metadata.component_id),NodeOutcome(status='ok',state=branch.state,artifacts=[evidence]));refs.append(ref)
 assert store.verify(ref).ok and store.verify(evidence).ok
 profiles=[]
 for profile,reader in [('warm',writer),('reopened',NodeResultCache(FileSystemCAS(store.root),run.run_manifest.run_id))]:
  if profile=='reopened':assert reader.load_entry(ref)
  loaded=reader.get(key);assert loaded is not None
  merged=merge_parallel_outcomes(base,{'method':loaded},{'method':spec.state_writes}).state
  result_ref=store.put_json(merged.model_dump(mode='python'),PutOptions(kind='scientist.independent_presence_merge',media_type='application/json'))
  assert store.verify(result_ref).ok
  actual=json.loads(store.get_bytes(result_ref))['params']['effective'];assert type(actual) is type(expected_native_effective) and actual==expected_native_effective
  assert merged.params['neighbor']=={'queue':['kept']} and merged.budgets['neighbor_reserved_usd']==Decimal('19')
  effect_json=json.loads(store.get_bytes(loaded.artifacts[0]));assert type(effect_json['effective']) is type(expected_native_effective) and effect_json['effective']==expected_native_effective
  run.emit('independent.presence','PRESENCE_CACHE_CONSUMED',outputs=[ref,evidence],metrics={'matched':1})
  profiles.append({'profile':profile,'effective':actual,'python_type':type(actual).__name__,'artifact_payload_utf8':store.get_bytes(evidence).decode(),'neighbor_reserved_usd':str(merged.budgets['neighbor_reserved_usd']),'merged_result_ref':result_ref.model_dump(mode='json'),'merged_result_bytes':store.get_bytes(result_ref).decode()})
 rows.append({'label':label,'key':key,'payload':compute_idempotency_payload(spec,base),'cache_ref':ref.model_dump(mode='json'),'artifact_ref':evidence.model_dump(mode='json'),'cache_bytes':store.get_bytes(ref).decode(),'profiles':profiles})
assert len({r['key'] for r in rows})==5
absent=state_for({'neighbor':{'queue':['kept']}},run.run_manifest.run_id);absent_key=compute_idempotency_key(spec,absent)
assert absent_key==rows[0]['key']
loaded=writer.get(absent_key);assert loaded is not None
merged=merge_parallel_outcomes(absent,{'method':loaded},{'method':spec.state_writes}).state
assert merged.params['effective']==5 and 'options' not in merged.params and calls==5
presence={'pass':True,'five_distinct_actual_keys':True,'provider_calls':calls,'rows':rows,'missing_intermediate_equivalent_default_control':{'key':absent_key,'result':merged.params,'provider_calls_unchanged':calls,'declared_semantics':'options absent and options={} both use threshold default5; null leaf remains separate'},'trace_utf8':run.trace_path.read_text()}

class ResumeNode:
 def __init__(self,name,input_key,fail_once=False):
  self.name=name;self.input_key=input_key;self.fail_once=fail_once;self.calls=0;self.refs=[]
  self.spec=NodeSpec(metadata=metadata('resume_'+name),state_reads=['params.'+input_key],state_writes=['params.'+name])
 def execute(self,ctx,state):raise AssertionError('Native async route required')
 async def execute_async(self,ctx,state):
  self.calls+=1
  if self.fail_once and self.calls==1:return NodeOutcome(status='fail',state=state,error=NodeError(code='node.invalid_input',message='independent intentional stop '+self.name))
  state.params[self.name]=state.params[self.input_key]+1
  ref=ctx.store.put_json({'node':self.name,'ordinal':self.calls,'value':state.params[self.name]},PutOptions(kind='scientist.independent_resume',media_type='application/json'));self.refs.append(ref)
  return NodeOutcome(status='ok',state=state,artifacts=[ref])
store2=FileSystemCAS(out/'resume'/'cas');bundle2=build_default_registry_bundle(store2);run2=RunContext.start(store2,bundle2.bundle_ref,run_id='R_independent_double_resume')
ctx=ExecutionContext(store=store2,run=run2,logger=logging.getLogger('independent-resume'))
nodes=[ResumeNode('a','seed'),ResumeNode('b','a',True),ResumeNode('c','b',True)];registry=NodeRegistry()
for node in nodes:registry.register(node)
workflow=WorkflowSpec(workflow_id='independent_double_resume',nodes=[NodeInvocation(alias=node.name,node_id=node.spec.metadata.component_id,depends_on=[] if i==0 else [nodes[i-1].name]) for i,node in enumerate(nodes)])
original_fp=compute_workflow_fingerprint(workflow);hook=CASCheckpointHook(store=store2,run_dir=run2.trace_path.parent)
first=asyncio.run(AsyncWorkflowExecutor(ctx,registry,checkpoint_hook=hook).execute(workflow,state_for({'seed':31,'neighbor':{'queue':['kept']}},run2.run_manifest.run_id)))
assert first.report.status=='fail' and [n.calls for n in nodes]==[1,1,0]
heads=[]
def capture(expected):
 reopened=FileSystemCAS(store2.root);resolved=resolve_latest_checkpoint(reopened,run2.run_manifest.run_id);assert resolved is not None
 head,cp=resolved;assert cp.metadata.completed_nodes==expected
 assert cp.metadata.origin_workflow_fingerprint==original_fp
 assert reopened.verify(head.checkpoint_ref).ok
 assert all(reopened.verify(ref).ok for ref in cp.metadata.cache_entry_refs)
 heads.append({'sequence':head.sequence_number,'checkpoint_ref':head.checkpoint_ref.model_dump(mode='json'),'checkpoint_bytes':reopened.get_bytes(head.checkpoint_ref).decode(),'origin_fingerprint':cp.metadata.origin_workflow_fingerprint,'execution_fingerprint':cp.metadata.workflow_fingerprint,'completed_nodes':cp.metadata.completed_nodes,'state':cp.state,'calls':[n.calls for n in nodes]})
capture(['a'])
os.environ['POLISYOS_RUNNER_BACKEND']='local'
second=resume_from_checkpoint(FileSystemCAS(store2.root),run2.run_manifest.run_id,workflow=workflow,registry=registry,registry_bundle_ref=bundle2.bundle_ref)
assert second.report.status=='fail' and [n.calls for n in nodes]==[1,2,1]
capture(['a','b'])
third=resume_from_checkpoint(FileSystemCAS(store2.root),run2.run_manifest.run_id,workflow=workflow,registry=registry,registry_bundle_ref=bundle2.bundle_ref)
assert third.report.status=='ok' and [n.calls for n in nodes]==[1,2,2]
assert third.state.params['a']==32 and third.state.params['b']==33 and third.state.params['c']==34
assert third.state.params['neighbor']=={'queue':['kept']} and third.state.budgets['neighbor_reserved_usd']==Decimal('19')
capture(['a','b','c'])
reopened_complete=resume_from_checkpoint(FileSystemCAS(store2.root),run2.run_manifest.run_id,workflow=workflow,registry=None,registry_bundle_ref=bundle2.bundle_ref)
assert reopened_complete.report.status=='ok' and reopened_complete.report.nodes==[] and [n.calls for n in nodes]==[1,2,2]
changed_nodes=list(workflow.nodes);changed_nodes[0]=changed_nodes[0].model_copy(update={'params':{'semantic_version':'changed'}})
changed=workflow.model_copy(update={'nodes':changed_nodes})
try:
 resume_from_checkpoint(FileSystemCAS(store2.root),run2.run_manifest.run_id,workflow=changed,registry=registry,registry_bundle_ref=bundle2.bundle_ref)
 invalid_rejection=None
except WorkflowMismatchError as exc:invalid_rejection={'type':type(exc).__name__,'message':str(exc)}
assert invalid_rejection and [n.calls for n in nodes]==[1,2,2]
assert all(store2.verify(ref).ok for node in nodes for ref in node.refs)
resume={'pass':True,'original_workflow_fingerprint':original_fp,'heads':heads,'provider_calls_final':[n.calls for n in nodes],'result_params':third.state.params,'reserved_usd':str(third.state.budgets['neighbor_reserved_usd']),'completed_reopen_nodes':len(reopened_complete.report.nodes),'changed_query_rejection':invalid_rejection,'trace_utf8':run2.trace_path.read_text()}
packet={'target_sha':sha,'target_tree':subprocess.check_output(['git','rev-parse',sha+'^{tree}'],cwd=repo,text=True).strip(),'source_identity':loaded_git_sources,'source_loading':'All imported canonical polisyos Python modules loaded from exact target Git objects; third-party runtime from explicit shared venv; repository resource paths from admitted EXE lane, no source edits/checkout' ,'python':sys.executable,'producer_profile':'Owned True keyword where supported; previous API declared write_paths. Effective semantic value/type compared with original public typed method input, then actual JSON artifact/state payloads, not private mutable-view class names.','presence_B62':presence,'double_resume_B70':resume,'pass':True}
encoded=json.loads(to_canonical_bytes(packet,CanonSpec(forbid_floats=False)))
(out/'receipt.json').write_text(json.dumps(encoded,indent=2)+'\n');print(json.dumps(encoded,indent=2))
