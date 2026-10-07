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
import copy,inspect
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability,ComponentId,ComponentKind,ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.protocol import NodeSpec,NodeOutcome
from polisyos.scientist.orchestration.engine.state_branching import branch_state,snapshot_state
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache,compute_idempotency_key
from polisyos.scientist.orchestration.engine.runner.serialization import serialize_state_safe
out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True);store=FileSystemCAS(out/'cas');run=RunContext.start(store,build_default_registry_bundle(store).bundle_ref,run_id='R_independent_additive')
def public(s):return ExperimentState.model_validate(s.model_dump(mode='python',by_alias=True,exclude_none=False))
def wire(s):return serialize_state_safe(public(s))[0]
meta=ComponentMetadata(component_id=ComponentId.parse('scientist.independent_additive@1.0.0'),kind=ComponentKind.SCIENTIST_NODE,abi_targets={'world_abi':'1.x'},display_name='Actual aliased additive intent',description='Current physical quantity consumer',capabilities=Capability.SCIENTIST_NODE)
spec=NodeSpec(metadata=meta,state_reads=['params.x'],state_writes=['params']);owned='enforce_write_scope' in inspect.signature(branch_state).parameters
rows=[]
for operation in ['append','pop']:
 for layout in ['aliased','split']:
  name=operation+'_'+layout
  base=ExperimentState(run_id=run.run_manifest.run_id,params={'x':2,'left':[],'right':[],'neighbor':{'queue':['kept']}},budgets={'neighbor_reserved_usd':Decimal('53')})
  shared=[{'id':'base','v':1},{'id':'remove','v':2}];base.params['left']=shared;base.params['right']=shared;assert base.params['left'] is base.params['right'];retained=wire(base)
  branch=branch_state(base,write_paths=('params',),**({'enforce_write_scope':True} if owned else {}))
  if operation=='append':branch.state.params['left'].append({'id':'added','v':5});expected_producer=[{'id':'base','v':1},{'id':'remove','v':2},{'id':'added','v':5}]
  else:branch.state.params['left'].pop();expected_producer=[{'id':'base','v':1}]
  producer=public(branch.state).params;producer_correct=producer['left']==expected_producer and producer['right']==expected_producer
  writer=NodeResultCache(store,base.run_id);key=compute_idempotency_key(spec,base,bind_params={'case':name});ref=writer.put(key,str(meta.component_id),NodeOutcome(status='ok',state=branch.state));assert store.verify(ref).ok;raw=store.get_bytes(ref);payload=from_canonical_bytes(raw);profiles=[]
  for profile,reader in [('warm',writer),('reopened',NodeResultCache(FileSystemCAS(store.root),base.run_id))]:
   if profile=='reopened':assert reader.load_entry(ref)
   outcome=reader.get(key);assert outcome is not None
   current=ExperimentState(run_id=base.run_id,params={'x':2,'left':[],'right':[],'neighbor':{'queue':['current']}},budgets={'neighbor_reserved_usd':Decimal('61')})
   left=[{'id':'currentL','v':17},{'id':'extraL','v':19},{'id':'removeL','v':31}]
   right=left if layout=='aliased' else [{'id':'currentR','v':27},{'id':'extraR','v':29},{'id':'removeR','v':41}]
   current.params['left']=left;current.params['right']=right;assert (current.params['left'] is current.params['right']) is (layout=='aliased');before=wire(current)
   if operation=='append':expected_left=left+[{'id':'added','v':5}];expected_right=right+[{'id':'added','v':5}]
   else:expected_left=left[:-1];expected_right=right[:-1]
   expected={'x':2,'left':expected_left,'right':expected_right,'neighbor':{'queue':['current']}}
   try:
    merged=merge_parallel_outcomes(current,{'producer':outcome},{'producer':['params']}).state
    resultref=store.put_json(snapshot_state(merged).model_dump(mode='python'),PutOptions(kind='scientist.independent_additive_result',media_type='application/json'));assert store.verify(resultref).ok;physical=json.loads(store.get_bytes(resultref))
    ok=physical['params']==expected and merged.budgets['neighbor_reserved_usd']==Decimal('61') and wire(current)==before
    profiles.append({'profile':profile,'pass':ok,'actual':physical['params'],'expected_literal_current_effect':expected,'current_input_alias_identity':layout=='aliased','original_current_wire_unchanged':wire(current)==before,'reserved_usd':str(merged.budgets['neighbor_reserved_usd']),'result_ref':resultref.model_dump(mode='json'),'result_bytes':store.get_bytes(resultref).decode()})
    run.emit('independent.additive','ADDITIVE_CURRENT_RESULT',outputs=[ref,resultref],metrics={'matched':int(ok)})
   except Exception as exc:profiles.append({'profile':profile,'pass':False,'error':{'type':type(exc).__name__,'message':str(exc)},'original_current_wire_unchanged':wire(current)==before})
  rows.append({'case':name,'producer_input_alias_identity':True,'producer':producer,'expected_producer_each_alias':expected_producer,'producer_correct':producer_correct,'producer_base_wire_unchanged':wire(base)==retained,'cache_ref':ref.model_dump(mode='json'),'cache_sha256':hashlib.sha256(raw).hexdigest(),'cache_bytes':raw.decode(),'mutations':payload['state_mutations'],'version':payload['state_mutations_version'],'profiles':profiles,'pass':producer_correct and wire(base)==retained and all(p['pass'] for p in profiles)})
packet={'target_sha':sha,'target_tree':subprocess.check_output(['git','rev-parse',sha+'^{tree}'],cwd=repo,text=True).strip(),'python':sys.executable,'source_identity':loaded_git_sources,'source_profile':'Exact Git canonical Python loader; declared producer True keyword where supported, prior declared write_paths producer API otherwise; existing admitted lane supplies resources/sharedvenv.','cases':rows,'trace_utf8':run.trace_path.read_text(),'pass':all(r['pass'] for r in rows)}
(out/'receipt.json').write_text(json.dumps(packet,indent=2)+'\n');print(json.dumps(packet,indent=2))
