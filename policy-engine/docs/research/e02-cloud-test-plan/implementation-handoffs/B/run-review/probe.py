import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
import json, os, sys, tempfile, time

from polisyos.scientist.orchestration.engine import retry
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.core.errors import ErrorCategory

class TransientValueError(ValueError):
    default_category = ErrorCategory.TRANSIENT
    code = 'node.transport'

class Node:
    def __init__(self, path, shape):
        self.path, self.shape = path, shape
        self.spec = SimpleNamespace(metadata=SimpleNamespace(component_id='B39-review'), state_writes=())
    def execute(self, ctx, state):
        with self.path.open('a') as output: output.write('attempt\n')
        attempt = len(self.path.read_text().splitlines())
        if self.shape == 'returned-invalid':
            return NodeOutcome(state=state, status='fail', error=NodeError(code='node.invalid_state', message='permanent bad input'))
        if self.shape == 'raised-invalid': raise ValueError('ConnectionError: transient-looking text')
        if self.shape == 'actual-deadline': time.sleep(0.1)
        if attempt == 1:
            if self.shape == 'raised-transient': raise OSError('ValueError: fatal-looking text')
            if self.shape == 'typed-transient-value': raise TransientValueError('invalid_state: permanent-looking text')
            if self.shape == 'node-timeout': raise TimeoutError('node provider timeout; operation did not hit wrapper deadline')
            if self.shape == 'returned-transient': return NodeOutcome(state=state, status='fail', error=NodeError(code='node.exception', message='temporary'))
        return NodeOutcome(state=state, status='ok')

class AsyncNode(Node):
    async def execute_async(self, ctx, state):
        if self.shape == 'actual-deadline':
            with self.path.open('a') as output: output.write('attempt\n')
            await asyncio.sleep(0.1)
            return NodeOutcome(state=state, status='ok')
        await asyncio.sleep(0)
        return self.execute(ctx, state)

class Store:
    def put_json(self, *args, **kwargs): return None
class Run:
    run_manifest = SimpleNamespace(run_id='B39-review')
    def __init__(self, path): self.path=path
    def emit(self, *args, **kwargs):
        with self.path.open('a') as output: output.write(json.dumps({'args':args,'kwargs':kwargs},default=str)+'\n')

base=Path(sys.argv[1]);base.mkdir(parents=True,exist_ok=True)
original_fork=retry._can_use_forked_timeout_worker
original_executor=retry.get_shared_executor
observations=[]
for mode in ['direct', 'sync-thread', 'sync-fork', 'async-sync-thread', 'async-fork', 'genuine-async-direct', 'genuine-async-timed']:
    for shape in ['returned-invalid','raised-invalid','returned-transient','raised-transient','typed-transient-value','node-timeout','actual-deadline']:
        if shape=='actual-deadline' and mode in {'direct','genuine-async-direct'}:continue
        stem=mode+'__'+shape
        path=base/(stem+'.attempts');event_path=base/(stem+'.events')
        node=(AsyncNode if mode.startswith('genuine-async') else Node)(path,shape)
        ctx=SimpleNamespace(store=Store(),run=Run(event_path))
        state=ExperimentState(run_id='B39-review')
        timeout=None if mode in {'direct','genuine-async-direct'} else (0.02 if shape=='actual-deadline' else 2.0)
        policy=retry.RetryPolicy(max_retries=2,backoff_base_s=0.1,jitter='none',retry_on=['node.exception','node.transport'])
        result_type='unknown'; error_type=None
        executor=None
        try:
            if 'thread' in mode:
                retry._can_use_forked_timeout_worker=lambda:False
                # Own real thread executor isolates inner admission from the async bridge executor.
                executor=ThreadPoolExecutor(max_workers=2)
                retry.get_shared_executor=lambda:executor
            else:retry._can_use_forked_timeout_worker=original_fork
            kwargs=dict(retry_policy=policy,timeout_s=timeout,alias='B39-review')
            if mode.startswith('async') or mode.startswith('genuine-async'):
                async def call():
                    try:return await retry.execute_with_retry_async(node,ctx,state,**kwargs)
                    finally:
                        # Settle the supplied bounded noncooperative timeout fixture.
                        if shape=='actual-deadline':await asyncio.sleep(0.12)
                result=asyncio.run(call())
            else:result=retry.execute_with_retry_sync(node,ctx,state,**kwargs)
            result_type=result.status
        except Exception as exc:
            result_type=type(exc).__name__;error_type=type(exc.__cause__).__name__ if exc.__cause__ else None
        finally:
            if executor:executor.shutdown(wait=True)
            retry._can_use_forked_timeout_worker=original_fork
            retry.get_shared_executor=original_executor
        expected_attempts=1 if shape in {'returned-invalid','raised-invalid','actual-deadline'} else 2
        actual_attempts=len(path.read_text().splitlines()) if path.exists() else 0
        expected_terminal={'returned-invalid':'fail','raised-invalid':'RetryExhaustedError','actual-deadline':'NodeTimeoutError'}.get(shape,'ok')
        row=dict(mode=mode,shape=shape,actual_attempts=actual_attempts,expected_attempts=expected_attempts,
                 actual_terminal=result_type,expected_terminal=expected_terminal,cause=error_type,
                 attempts_file=str(path),event_file=str(event_path),pass_=actual_attempts==expected_attempts and result_type==expected_terminal)
        observations.append(row);print(json.dumps(row),flush=True)
(base/'observations.json').write_text(json.dumps({'source_module':retry.__file__,'python':sys.version,'observations':observations},indent=2)+'\n')
print(json.dumps({'pass':sum(r['pass_'] for r in observations),'fail':sum(not r['pass_'] for r in observations),'source':retry.__file__}),flush=True)
