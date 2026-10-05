import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import threading
import time

from polisyos.common.async_tools import _SharedExecutor
from polisyos.scientist.orchestration.engine import retry
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState

class Store:
    def __init__(self, path): self.path=path
    def put_bytes(self, value): self.path.write_bytes(value)

class Node:
    def __init__(self, path, started=None, release=None):
        self.path, self.started, self.release = path, started, release
    def execute(self, ctx, state):
        with self.path.open('a') as output:
            output.write(json.dumps({'event':'physical_execute','monotonic':time.monotonic()})+'\n')
        if self.started:
            self.started.set()
            assert self.release.wait(2.0), 'fixture release timed out'
        ctx.store.put_bytes(b'attempt-owned write')
        with self.path.open('a') as output:
            output.write(json.dumps({'event':'physical_finish','monotonic':time.monotonic()})+'\n')
        return NodeOutcome(state=state, status='ok')

base=Path(sys.argv[1]);base.mkdir(parents=True,exist_ok=True)
original_executor, original_fork = retry.get_shared_executor,retry._can_use_forked_timeout_worker
observations=[]
async def one(mode,termination,running):
    stem=f'{mode}-{termination}-'+('running' if running else 'queued')
    path=base/(stem+'.physical'); owned=base/(stem+'.owned')
    assert not path.exists() and not owned.exists(), 'use a fresh empty evidence directory'
    executor=_SharedExecutor(max_workers=4,thread_name_prefix='B39-review-real-shared')
    release=threading.Event();started=threading.Event();blockers=[]
    retry.get_shared_executor=lambda:executor
    retry._can_use_forked_timeout_worker=lambda:False
    try:
        if not running:
            ready=threading.Barrier(5)
            def blocker():
                ready.wait(timeout=2.0)
                assert release.wait(2.0), 'fixture release timed out'
            blockers=[executor.submit(blocker) for _ in range(4)]
            ready.wait(timeout=2.0)
            assert executor._outstanding_jobs==4
        node=Node(path,started if running else None,release if running else None)
        ctx=SimpleNamespace(store=Store(owned),run=SimpleNamespace(run_manifest=None))
        state=ExperimentState(run_id='B39-queued-review')
        timeout=0.05 if termination=='deadline' else 5.0
        terminal=None
        if mode=='sync':
            try:retry._execute_with_timeout_sync(node,ctx,state,timeout_s=timeout)
            except Exception as exc:terminal=type(exc).__name__
        else:
            task=asyncio.create_task(retry._execute_with_timeout_thread_async(node,ctx,state,timeout_s=timeout))
            if termination=='caller-cancel':
                while executor._outstanding_jobs!=(1 if running else 5): await asyncio.sleep(0)
                if running:
                    while not started.is_set():await asyncio.sleep(0)
                assert running or not path.exists()
                task.cancel()
            try:await task
            except BaseException as exc:terminal=type(exc).__name__
        stopped_at=time.monotonic()
        before=path.read_text() if path.exists() else ''
        assert not running or started.is_set()
        assert running or before==''
        outstanding_before_release=executor._outstanding_jobs
        release.set()
        executor.shutdown(wait=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        physical=path.read_text() if path.exists() else ''
        events=[json.loads(line) for line in physical.splitlines()]
        row={'mode':mode,'termination':termination,'was_running_at_boundary':running,'terminal':terminal,
             'unstarted_at_boundary':not bool(before),'outstanding_before_release':outstanding_before_release,
             'physically_executed_after_boundary':any(e['monotonic']>stopped_at for e in events),
             'physical_events':events,'physical_file':str(path),'protected_owned_file_exists':owned.exists(),
             'expect_unstarted_job_cancelled':not running,
             'pass':bool(physical) if running else not bool(physical)}
        observations.append(row);print(json.dumps(row),flush=True)
    finally:
        release.set();executor.shutdown(wait=True)
        retry.get_shared_executor, retry._can_use_forked_timeout_worker=original_executor,original_fork

async def main():
    await one('sync','deadline',False)
    await one('async','deadline',False)
    await one('async','caller-cancel',False)
    await one('async','deadline',True)
    await one('async','caller-cancel',True)
asyncio.run(main())
record={'target_sha':sys.argv[2],'module':retry.__file__,'module_sha256':hashlib.sha256(Path(retry.__file__).read_bytes()).hexdigest(),
        'python':sys.version,'observations':observations}
(base/'observations.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'pass':sum(r['pass'] for r in observations),'fail':sum(not r['pass'] for r in observations),'source':retry.__file__}),flush=True)
