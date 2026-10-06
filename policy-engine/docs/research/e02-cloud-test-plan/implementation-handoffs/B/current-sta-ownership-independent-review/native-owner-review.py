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
import logging,asyncio,copy
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
from polisyos.core.canon import from_canonical_bytes,to_canonical_bytes,CanonSpec
from polisyos.core.components import Capability,ComponentId,ComponentKind,ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.protocol import NodeSpec,NodeOutcome
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec,NodeInvocation
from polisyos.scientist.orchestration.engine.runner.serialization import serialize_state_safe
out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
def public(s):return ExperimentState.model_validate(s.model_dump(mode='python',by_alias=True,exclude_none=False))
def wire(s):return serialize_state_safe(public(s))[0]
def initial(runid):return ExperimentState(run_id=runid,params={'rows':[{'id':'a','v':1},{'id':'b','v':2}],'neighbor':{'queue':['kept'],'v':7}},budgets={'neighbor_reserved_usd':Decimal('37')})
class NativeOwnerNode:
 def __init__(self,name,forbidden):
  self.name=name;self.forbidden=forbidden;self.calls=0;self.reached_after=False;self.refs=[]
  self.spec=NodeSpec(metadata=ComponentMetadata(component_id=ComponentId.parse('scientist.independent_owner_'+name+'@1.0.0'),kind=ComponentKind.SCIENTIST_NODE,abi_targets={'world_abi':'1.x'},display_name='Native owner '+name,description='Actual node-entry authority consumer',capabilities=Capability.SCIENTIST_NODE),state_reads=['params.rows','params.neighbor'],state_writes=['params.rows'])
 def execute(self,ctx,state):raise AssertionError('Native genuineasync producer route required')
 async def execute_async(self,ctx,state):
  self.calls+=1
  if self.forbidden:state.params['neighbor']['v']=99
  else:
   held=state.params['rows'].pop(0);state.params['rows'].append(held);held['v']=5
  self.reached_after=True
  ref=ctx.store.put_json({'rows':state.params['rows'],'neighbor':state.params['neighbor']},PutOptions(kind='scientist.independent_native_owner',media_type='application/json'));self.refs.append(ref)
  return NodeOutcome(status='ok',state=state,artifacts=[ref])
rows=[]
for name,forbidden in [('undeclared_neighbor_actual_node_entry',True),('owned_alias_and_public_result',False)]:
 store=FileSystemCAS(out/name/'cas');bundle=build_default_registry_bundle(store);run=RunContext.start(store,bundle.bundle_ref,run_id='R_independent_native_'+name)
 node=NativeOwnerNode(name,forbidden);registry=NodeRegistry();registry.register(node);ctx=ExecutionContext(store=store,run=run,logger=logging.getLogger(name));base=initial(run.run_manifest.run_id);before=wire(base)
 workflow=WorkflowSpec(workflow_id='independent_native_'+name,nodes=[NodeInvocation(alias='producer',node_id=node.spec.metadata.component_id)])
 result=asyncio.run(AsyncWorkflowExecutor(ctx,registry).execute(workflow,base))
 report=result.report.model_dump(mode='json');input_artifacts=[];cache_artifacts=[];trace=run.trace_path.read_text()
 for line in trace.splitlines():
  event=json.loads(line)
  for section in ['inputs','outputs']:
   for r in event.get('refs',{}).get(section,[]):
    if r.get('kind') in ['scientist.experiment_state','scientist.node_cache_entry']:
     from polisyos.core.artifacts.manifest import ArtifactRef
     ref=ArtifactRef.model_validate(r);raw=store.get_bytes(ref);assert store.verify(ref).ok
     entry={'ref':r,'bytes':raw.decode(),'sha256':hashlib.sha256(raw).hexdigest()}
     collection=input_artifacts if r['kind']=='scientist.experiment_state' else cache_artifacts
     if not any(x['sha256']==entry['sha256'] for x in collection):collection.append(entry)
 evidence=[{'ref':ref.model_dump(mode='json'),'bytes':store.get_bytes(ref).decode(),'sha256':hashlib.sha256(store.get_bytes(ref)).hexdigest(),'verified':store.verify(ref).ok} for ref in node.refs]
 actual=public(result.state).params;row={'case':name,'status':result.report.status,'report':report,'calls':node.calls,'after_mutation_reached':node.reached_after,'original_input_wire_unchanged':wire(base)==before,'params':actual,'reserved_usd':str(result.state.budgets['neighbor_reserved_usd']),'input_artifacts':input_artifacts,'cache_artifacts':cache_artifacts,'provider_artifacts':evidence,'trace_utf8':trace}
 if forbidden:
  row['pass']=result.report.status=='fail' and node.calls==1 and not node.reached_after and not node.refs and wire(base)==before and actual['neighbor']=={'queue':['kept'],'v':7} and result.state.budgets['neighbor_reserved_usd']==Decimal('37') and bool(input_artifacts)
 else:
  expected=[{'id':'b','v':2},{'id':'a','v':5}]
  effects_correct=all(json.loads(e['bytes'])['rows']==expected for e in evidence)
  try:
   result.state.params['post']={'values':[3]};result.state.params['post']['values'].append(4)
   ref=store.put_json(public(result.state).model_dump(mode='python'),PutOptions(kind='scientist.independent_native_public_result',media_type='application/json'));assert store.verify(ref).ok;payload=json.loads(store.get_bytes(ref))
   row['public_result_edit']={'pass':payload['params']['post']=={'values':[3,4]},'ref':ref.model_dump(mode='json'),'bytes':store.get_bytes(ref).decode()}
  except Exception as exc:row['public_result_edit']={'pass':False,'error':{'type':type(exc).__name__,'message':str(exc)}}
  row['pass']=result.report.status=='ok' and node.calls==1 and node.reached_after and bool(evidence) and effects_correct and actual['rows']==expected and actual['neighbor']=={'queue':['kept'],'v':7} and wire(base)==before and result.state.budgets['neighbor_reserved_usd']==Decimal('37') and row['public_result_edit']['pass'] and bool(cache_artifacts)
 rows.append(row)
packet={'target_sha':sha,'target_tree':subprocess.check_output(['git','rev-parse',sha+'^{tree}'],cwd=repo,text=True).strip(),'python':sys.executable,'source_identity':loaded_git_sources,'source_profile':'All canonical Python imports pinned exact Git target; actual public AsyncWorkflowExecutor/NodeRegistry genuineasync producer entry, no source replacement.','cases':rows,'pass':all(r['pass'] for r in rows)}
encoded=json.loads(to_canonical_bytes(packet,CanonSpec(forbid_floats=False)));(out/'receipt.json').write_text(json.dumps(encoded,indent=2)+'\n');print(json.dumps(encoded,indent=2))
