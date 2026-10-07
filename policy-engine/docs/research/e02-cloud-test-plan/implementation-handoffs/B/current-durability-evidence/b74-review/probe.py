"""Independent actual-class helper replacement cold/resume discriminator."""
from __future__ import annotations
import datetime,hashlib,importlib.util,json,pathlib,subprocess,sys,time
from typing import ClassVar
ROOT=pathlib.Path('/workspace/e02-B-current-composition');TARGET=sys.argv[2] if len(sys.argv)>2 else 'c639295e25a602869c6c28754cd43fd856aa05cf'
SCRATCH=pathlib.Path(sys.argv[1]).resolve();assert not SCRATCH.exists();SCRATCH.mkdir(parents=True)
for relative in ['policy-engine/src/polisyos/foundry/methods/backends/checkpointing.py','policy-engine/src/polisyos/foundry/methods/artifacts/_fingerprint.py','policy-engine/src/polisyos/core/artifacts/manifest_profile.py','policy-engine/tests/unit/foundry/methods/backends/test_checkpoint_identity.py']:
 assert (ROOT/relative).read_bytes()==subprocess.check_output(['git','show',TARGET+':'+relative],cwd=ROOT)
spec=importlib.util.spec_from_file_location('b74_owner_fixture',ROOT/'policy-engine/tests/unit/foundry/methods/backends/test_checkpoint_identity.py');fixture=importlib.util.module_from_spec(spec);sys.modules[spec.name]=fixture;spec.loader.exec_module(fixture)
from polisyos.foundry.methods.backends.checkpointing import ChainCheckpoint,CheckpointingChainExecutor,CheckpointError
from polisyos.core.artifacts.store import FileSystemCAS
class HelperSource:
 signature:ClassVar=fixture._PRODUCER_SIGNATURE
 metadata:ClassVar=fixture._METADATA
 @staticmethod
 def scale(x,factor):return x*factor
 @staticmethod
 def pure_step(state,params):return {'product':HelperSource.scale(state['x'],params['factor'])}
def changed_scale(x,factor):return x*(factor+1)
chain,registry=fixture._chain();registry.register(HelperSource,override=True)
store=FileSystemCAS(SCRATCH/'cas');context=fixture._strict_context(store,chain);dispatcher=fixture._RecordingDispatcher()
executor=CheckpointingChainExecutor(registry=registry,dispatcher=dispatcher,artifact_store=store,checkpoint_dir=SCRATCH/'first')
original=executor.execute(chain,initial_state={'x':3},seed=7,artifact_context=context);path=next((SCRATCH/'first').glob('*_0000_*.json'));checkpoint=ChainCheckpoint.load(path);selected_bytes=path.read_bytes()
assert original.final_state['total']==7 and checkpoint.intermediate_state['product']==6
unchanged=executor.execute(chain,initial_state={'x':3},checkpoint=checkpoint,seed=7,artifact_context=context);assert unchanged.final_state['total']==7 and unchanged.history_complete
HelperSource.scale=staticmethod(changed_scale)
cold=CheckpointingChainExecutor(registry=registry,artifact_store=store).execute(chain,initial_state={'x':3},seed=7,artifact_context=context)
assert cold.final_state['total']==10
before=list(dispatcher.calls);failure=None;resumed=None
try:resumed=executor.execute(chain,initial_state={'x':3},checkpoint=checkpoint,seed=7,artifact_context=context)
except CheckpointError as exc:failure={'type':type(exc).__name__,'message':str(exc)}
record={'target_sha':TARGET,'target_tree':subprocess.check_output(['git','rev-parse',TARGET+'^{tree}'],cwd=ROOT,text=True).strip(),'original_total':original.final_state['total'],'unchanged_resume_total':unchanged.final_state['total'],'changed_actual_cold_total':cold.final_state['total'],'changed_resume_error':failure,'changed_resume_total':None if resumed is None else resumed.final_state['total'],'changed_resume_dispatches':dispatcher.calls[len(before):],'history_complete':None if resumed is None else resumed.history_complete,'original_checkpoint_unchanged':path.read_bytes()==selected_bytes,'source_class_same':registry.get(fixture._PRODUCER_SIGNATURE.fqn) is HelperSource,'environment':{'python':sys.version,'executable':sys.executable,'checkpoint_module':sys.modules[CheckpointingChainExecutor.__module__].__file__},'end_utc':datetime.datetime.now(datetime.UTC).isoformat(),'meaning':'class identity and original inspected class source unchanged, actual helper callable changed; all CAS refs, ABI, seed, input, cache and history unchanged'}
print(json.dumps(record,indent=2),flush=True)
assert failure is not None,'B74 stale resume admitted: helper replacement changes actual cold total10, but strict checkpoint retains old total7'
