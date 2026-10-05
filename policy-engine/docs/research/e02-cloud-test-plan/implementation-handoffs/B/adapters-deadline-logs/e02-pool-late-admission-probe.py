import asyncio
import hashlib
import json
from pathlib import Path
import platform
import sys

from polisyos.fabric.connectors import pool as module
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, HealthStatus


class Connector:
    def __init__(self, operation, suppress):
        self.operation, self.suppress = operation, suppress
        self.started, self.cancelled, self.proceed = (asyncio.Event() for _ in range(3))
        self.handles, self.disconnected = [], []
        self.cancel_time = None

    async def wait(self, operation):
        if operation != self.operation:
            return
        self.started.set()
        try:
            await self.proceed.wait()
        except asyncio.CancelledError:
            self.cancel_time = asyncio.get_running_loop().time()
            self.cancelled.set()
            if not self.suppress:
                raise
            await self.proceed.wait()

    async def connect(self, config):
        await self.wait('connect')
        handle = ConnectionHandle(connector_id='actual-probe', config=config)
        self.handles.append(handle.session_id)
        return handle

    async def health_check(self, handle):
        await self.wait('health')
        return HealthStatus(healthy=True)

    async def disconnect(self, handle):
        self.disconnected.append(handle.session_id)


async def case(operation, suppress):
    connector = Connector(operation, suppress)
    pool = module.ConnectionPool(lambda: connector, ConnectionConfig(url='https://e02.invalid'), module.PoolConfig(max_size=1, acquire_timeout_seconds=0.08, connection_timeout_seconds=2, validate_on_acquire=operation == 'health'), pool_id=f'late-{operation}-{suppress}')
    loop = asyncio.get_running_loop()
    submitted = loop.time()
    task = asyncio.create_task(pool.acquire())
    try:
        await asyncio.wait_for(connector.started.wait(), 1)
        await asyncio.wait_for(connector.cancelled.wait(), 1)
        before = {'active': pool._active_acquires, 'in_use': list(pool._in_use), 'pending': list(pool._pending_cleanup), 'semaphore': pool._semaphore._value, 'task_done': task.done()}
        connector.proceed.set()
        returned = None
        try:
            handle = await asyncio.wait_for(asyncio.shield(task), 1)
            returned = handle.session_id
            outcome = 'returned_handle'
        except module.PoolExhaustedError:
            outcome = 'PoolExhaustedError'
        completed = loop.time()
        state = {'active': pool._active_acquires, 'in_use': list(pool._in_use), 'pending': list(pool._pending_cleanup), 'semaphore': pool._semaphore._value}
        late = returned is not None and completed > submitted + 0.08
        disconnects_before_close = list(connector.disconnected)
        await pool.close_all()
        record = {'operation': operation, 'suppresses_cancellation': suppress, 'submitted': submitted, 'cancel_observed': connector.cancel_time, 'completion': completed, 'budget': 0.08, 'before_proceed': before, 'outcome': outcome, 'returned_session': returned, 'late_handle_admitted': late, 'state_after_acquire': state, 'created_handles': connector.handles, 'disconnects_before_close': disconnects_before_close, 'disconnects_after_close': connector.disconnected, 'clean_after_close': pool._active_acquires == 0 and not pool._in_use and not pool._pending_cleanup and pool._semaphore._value == 1}
        print(json.dumps(record), flush=True)
        return record
    finally:
        connector.proceed.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await pool.close_all()


async def main():
    rows = [await case(operation, suppress) for operation in ['connect', 'health'] for suppress in [False, True]]
    assert all(r['cancel_observed'] >= r['submitted'] + 0.08 for r in rows)
    assert all(r['clean_after_close'] for r in rows)
    assert all(sorted(r['created_handles']) == sorted(r['disconnects_after_close']) for r in rows)
    assert all(r['outcome'] == 'PoolExhaustedError' and not r['late_handle_admitted'] for r in rows), 'late actual handle admission after deadline'


print(json.dumps({'module': module.__file__, 'module_sha256': hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(), 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'python': sys.version, 'platform': platform.platform(), 'input': 'real ConnectionPool and synthetic event-gated connector protocol; real loop.time; no TCP/database/dataset; 4 cooperative/suppress connect/health variants'}), flush=True)
asyncio.run(main())
