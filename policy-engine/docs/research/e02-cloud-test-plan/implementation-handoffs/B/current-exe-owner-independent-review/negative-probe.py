import asyncio, hashlib, json, pathlib, subprocess, sys, types
root=pathlib.Path('/workspace/e02-B-current-execution-state')
sha='ff6d86f56948dc49780e5034d4ec2a3f619df8c6'
paths=['policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py','policy-engine/src/polisyos/core/artifacts/async_store.py','policy-engine/tests/unit/scientist/orchestration/engine/test_workflow_deadline_custody.py']
identities={}
for path in paths:
 raw=subprocess.check_output(['git','show',sha+':'+path],cwd=root)
 assert (root/path).read_bytes()==raw
 identities[path]=hashlib.sha256(raw).hexdigest()
module=types.ModuleType('frozen_exe_fixture');module.__file__=str(root/paths[-1])
exec(compile(raw,sha+':'+paths[-1],'exec'),module.__dict__)
from polisyos.scientist.orchestration.engine.checkpoint import CASCheckpointHook,resolve_latest_checkpoint
from polisyos.scientist.orchestration.engine.state import ExperimentState
out=pathlib.Path('/workspace/e02-B-current-runtime/_build/e02-current-runtime/exe-ff6d-cancel')
out.mkdir(parents=True,exist_ok=True)
async def probe():
 store=module.FileSystemCAS(out/'cas')
 ctx,node,workflow,executor=module._setup(store)
 entered=asyncio.Event()
 real=CASCheckpointHook(store=store,run_dir=ctx.run.trace_path.parent)
 history=[]
 class Hook:
  async def on_node_complete_async(self,**kwargs):
   entered.set()
   try:
    await asyncio.Event().wait()
   except asyncio.CancelledError:
    history.append({'kind':'cancellation_suppressed','cancelling':asyncio.current_task().cancelling()})
   result=await asyncio.to_thread(real.on_node_complete,**kwargs)
   history.append({'kind':'real_checkpoint_completed','cancelling':asyncio.current_task().cancelling()})
   return result
 executor._checkpoint_hook=Hook()
 task=asyncio.create_task(executor.execute(workflow,ExperimentState(run_id='R_deadline',params={'seed':7})))
 await asyncio.wait_for(entered.wait(),2)
 before=module._events(ctx)
 task.cancel()
 try:
  result=await asyncio.wait_for(task,3)
  termination={'type':'returned','status':result.report.status,'state_params':result.state.params,'run_ref':result.run_ref.model_dump(mode='json')}
 except BaseException as exc:
  termination={'type':type(exc).__name__,'message':str(exc)}
 after=module._events(ctx)
 resolved=resolve_latest_checkpoint(module.FileSystemCAS(store.root),'R_deadline')
 packet={'target_sha':sha,'source_identity':identities,'python':sys.executable,'cancellation_count_final':task.cancelling(),'suppressed_hook':history,'termination':termination,'provider_calls':node.calls,'events_before_cancel':[e['event'] for e in before],'events_after_cancel':[e['event'] for e in after[len(before):]],'run_outputs_after_cancel':[r.model_dump(mode='json') for r in ctx.run.run_manifest.outputs],'checkpoint_physically_exists':resolved is not None,'unbounded_owner':executor._workflow_deadline is None,'all_source_unchanged':all((root/p).read_bytes()==subprocess.check_output(['git','show',sha+':'+p],cwd=root) for p in paths),'pass_no_new_owner_publication':not any(e['event']=='RUN_FINALIZED' for e in after[len(before):])}
 (out/'receipt.json').write_text(json.dumps(packet,indent=2)+'\n')
 print(json.dumps(packet,indent=2))
asyncio.run(probe())
