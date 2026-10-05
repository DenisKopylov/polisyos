from __future__ import annotations
import asyncio, hashlib, inspect, json, logging, os, pathlib, runpy, subprocess, tempfile, textwrap, threading, time
from polisyos.core.artifacts.manifest import ArtifactRef, ArtifactTenantContextInfo
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec, NodeInvocation
from polisyos.core.components import ComponentId
import polisyos.scientist.orchestration.engine.async_executor as ae

ROOT=pathlib.Path('/workspace/e02-B-b52-oracle')
FIX=runpy.run_path(str(ROOT/'policy-engine/tests/integration/scientist/test_execution_state_replay.py'))
SOURCE='0f24d18d988f579db20a84c734a587abe6cabe20'
BASE_EXECUTE=AsyncWorkflowExecutor.execute

def make(root: pathlib.Path, label: str, mode: str):
    run_id='cold-seed-'+label
    node=FIX['_StateOperationsNode']();reg=NodeRegistry();reg.register(node)
    wf=WorkflowSpec(workflow_id='cold_seed',nodes=[NodeInvocation(alias='writer',node_id=ComponentId.parse(FIX['_NODE_ID']))])
    firstctx=FIX['_context'](root,run_id)
    hook=FIX['CASCheckpointHook'](store=firstctx.store,run_dir=firstctx.store.root/'runs'/run_id) if mode=='checkpoint' else None
    first=asyncio.run(AsyncWorkflowExecutor(firstctx,reg,checkpoint_hook=hook).execute(wf,FIX['_state'](run_id,current=False)))
    assert first.report.status=='ok' and node.calls==1
    records=[json.loads(s) for s in firstctx.run.trace_path.read_text().splitlines()]
    refs=[ArtifactRef.model_validate(ref) for rec in records if rec.get('event')=='NODE_CACHE_STORE' for ref in rec['refs']['outputs'] if ref['kind']=='scientist.node_cache_entry']
    assert len(refs)==1
    ctx=FIX['_context'](root,run_id)
    if mode=='checkpoint':
        checkpoint=FIX['resolve_latest_checkpoint'](ctx.store,run_id)
        assert checkpoint is not None and checkpoint[1].metadata.completed_nodes==['writer']
        assert checkpoint[1].metadata.cache_entry_refs==refs
        refs=list(checkpoint[1].metadata.cache_entry_refs)
        ctx.run.trace_path.write_text('')
    return node,reg,wf,ctx,refs,run_id

async def measured(root: pathlib.Path, label: str, mode: str, kind: str, offloop: bool):
    # Cold setup runs in an independent, completed loop before this measured loop.
    node,reg,wf,ctx,refs,run_id=SETUP
    executor=AsyncWorkflowExecutor(ctx,reg,checkpoint_cache_seed_refs=refs if mode=='checkpoint' else [],workflow_timeout_s=0.04 if kind=='deadline' else None)
    entry_id=refs[0].artifact_id
    real=ctx.store.get_bytes
    entered=threading.Event();released=threading.Event();done=threading.Event();gate_used=False;read_tid=None
    measurements={'io_ticks':0,'loop_tid':threading.get_ident(),'kind':kind,'mode':mode,'offloop_control':offloop}
    loop=asyncio.get_running_loop();task=None
    def gated_get_bytes(artifact_id):
        nonlocal gate_used,read_tid
        if artifact_id==entry_id and not gate_used:
            gate_used=True;read_tid=threading.get_ident();measurements['read_enter_s']=time.perf_counter();entered.set()
            assert released.wait(3), 'watchdog did not release real CAS read'
        return real(artifact_id)
    ctx.store.get_bytes=gated_get_bytes
    def watchdog():
        assert entered.wait(3),'native cold seed read not entered'
        if kind=='cancel':
            measurements['cancel_requested_s']=time.perf_counter()
            loop.call_soon_threadsafe(task.cancel)
        time.sleep(0.12)
        measurements['release_s']=time.perf_counter();released.set()
    async def ready_neighbor():
        while not done.is_set():
            await asyncio.sleep(0.001)
            if entered.is_set() and not released.is_set():measurements['io_ticks']+=1
    if offloop:
        src=textwrap.dedent(inspect.getsource(BASE_EXECUTE))
        src=src.replace('restored = self._cache.seed_from_trace(self._ctx.run.trace_path)','restored = await run_blocking_async(self._cache.seed_from_trace, self._ctx.run.trace_path, timeout_seconds=self._remaining_deadline_seconds(self._workflow_deadline))')
        src=src.replace('restored_cp = self._cache.seed_from_entry_refs(self._checkpoint_cache_seed_refs)','restored_cp = await run_blocking_async(self._cache.seed_from_entry_refs, self._checkpoint_cache_seed_refs, timeout_seconds=self._remaining_deadline_seconds(self._workflow_deadline))')
        ns=vars(ae).copy();exec(src,ns);AsyncWorkflowExecutor.execute=ns['execute']
    try:
        neighbor=asyncio.create_task(ready_neighbor());task=asyncio.create_task(executor.execute(wf,FIX['_state'](run_id,current=True)))
        watcher=threading.Thread(target=watchdog);watcher.start();start=time.perf_counter()
        try:
            result=await task
            measurements['outcome']=result.report.status
            measurements['state_params']=result.state.params
            if kind=='responsive':FIX['_assert_operations'](result.state)
        except BaseException as exc:
            measurements['outcome']=type(exc).__name__;measurements['exception_message']=str(exc)
        measurements['await_return_s']=time.perf_counter();measurements['elapsed_s']=time.perf_counter()-start
        await asyncio.to_thread(watcher.join)
        await asyncio.sleep(0.02)
        measurements['late_seed_cache_size']=executor._cache.size if executor._cache is not None else None
        measurements['producer_calls']=node.calls;measurements['read_tid']=read_tid
        if executor._cache is not None and executor._cache.size:
            key=next(iter(executor._cache._index.keys()))
            admitted=executor._cache.get(key)
            assert admitted is not None
            replayed=ae._merge_cached_outcome_state(alias='writer',node=node,base_state=FIX['_state'](run_id,current=True),outcome=admitted)
            FIX['_assert_operations'](replayed)
            measurements['post_attempt_real_consumer_replay']=replayed.params
            measurements['post_attempt_consumer_observation_only']=True
        measurements['cache_refs']=[r.model_dump(mode='json') for r in refs]
        print(json.dumps(measurements,sort_keys=True),flush=True)
    finally:
        done.set();await neighbor;ctx.store.get_bytes=real;AsyncWorkflowExecutor.execute=BASE_EXECUTE

def negative_controls(root):
    node,reg,wf,ctx,refs,run_id=make(root,'negative','trace');ref=refs[0]
    positive=NodeResultCache(ctx.store,run_id=run_id);assert positive.seed_from_entry_refs(refs)==1
    assert positive.get(next(iter(positive._index.keys()))) is not None
    foreign=NodeResultCache(ctx.store,run_id=run_id,tenant_context=ArtifactTenantContextInfo(tenant_id='other-tenant',cell_id='other-cell'))
    assert foreign.seed_from_entry_refs(refs)==0 and foreign.size==0
    payload_path=ctx.store._paths(ref.artifact_id)[0];original=payload_path.read_bytes();mode=payload_path.stat().st_mode
    try:
        payload_path.chmod(0)
        try:ctx.store.get_bytes(ref.artifact_id)
        except PermissionError:permission_control='real_filesystem_permission_error'
        else:raise AssertionError('filesystem permission negative unavailable under this uid')
        denied=NodeResultCache(ctx.store,run_id=run_id);assert denied.seed_from_entry_refs(refs)==0 and denied.size==0
    finally:payload_path.chmod(mode)
    try:
        payload_path.write_bytes(original+b' ')
        assert not ctx.store.verify(ref.artifact_id).ok
        tampered=NodeResultCache(ctx.store,run_id=run_id);assert tampered.seed_from_entry_refs(refs)==0 and tampered.size==0
    finally:payload_path.write_bytes(original)
    print(json.dumps({'kind':'negative_controls','scope_refused':True,'permission':permission_control,'tampered_real_bytes_refused':True,'positive_seed_size':positive.size,'uid':os.getuid()}),flush=True)

if __name__=='__main__':
    print(json.dumps({'source_sha':SOURCE,'source_readback':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'module_file':ae.__file__,'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'python':subprocess.check_output(['/workspace/polisyos/policy-engine/.venv/bin/python','--version'],text=True).strip(),'isolation':'temporary real FileSystemCAS paths; no DB/port/production dataset; one watchdog and ready coroutine intentionally concurrent'}),flush=True)
    with tempfile.TemporaryDirectory(prefix='e02-b52-real-cas-') as td:
        root=pathlib.Path(td)
        for offloop in [False,True]:
            for mode in ['trace','checkpoint']:
                for kind in ['responsive','deadline','cancel']:
                    SETUP=make(root/f'{mode}-{kind}-{offloop}',f'{mode}-{kind}-{offloop}',mode)
                    asyncio.run(measured(root,kind,mode,kind,offloop))
        negative_controls(root/'negative')
