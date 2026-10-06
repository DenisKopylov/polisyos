import asyncio
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
import platform
import sys
import threading
from typing import get_type_hints

from polisyos.common import async_tools

records = []
executor = async_tools._SharedExecutor(max_workers=1, thread_name_prefix='independent-accounting')
started, release = threading.Event(), threading.Event()
executions = []

def count(label, expected):
    actual = executor._outstanding_jobs
    records.append({'phase': label, 'outstanding': actual, 'expected': expected})
    assert actual == expected, records[-1]

def active_body():
    started.set()
    assert release.wait(2)
    executions.append('active')
    return 42

try:
    active = executor.submit(active_body)
    assert started.wait(1)
    cancelled = executor.submit(lambda: executions.append('cancelled'))
    pending_shutdown = executor.submit(lambda: executions.append('shutdown-cancelled'))
    count('active-plus-two-queued', 3)
    assert cancelled.cancel() and cancelled.cancel()
    count('repeated-cancel', 2)
    executor.shutdown(wait=False, cancel_futures=True)
    assert pending_shutdown.cancelled()
    count('shutdown-cancel', 1)
    try:
        executor.submit(lambda: executions.append('rejected'))
    except RuntimeError as exc:
        records.append({'phase': 'rejected-after-shutdown', 'exception': type(exc).__name__, 'message': str(exc)})
    else:
        raise AssertionError('submission unexpectedly admitted after shutdown')
    count('rejection-rollback', 1)
    release.set()
    executor.shutdown(wait=True)
    assert active.result() == 42 and executions == ['active']
    count('all-physical-jobs-settled', 0)
finally:
    release.set()
    executor.shutdown(wait=True, cancel_futures=True)

scope = ContextVar('independent-scope', default='missing')
async def bridge_control():
    token = scope.set('owner')
    try:
        assert await async_tools.run_blocking_async(scope.get, timeout_seconds=1) == 'owner'
        assert async_tools.run_coro_sync(asyncio.sleep(0, result=11), timeout_seconds=1) == 11
    finally:
        scope.reset(token)
assert async_tools.run_coro_sync(asyncio.sleep(0, result=7), timeout_seconds=1) == 7
asyncio.run(bridge_control())
async_tools.shutdown_run_coro_sync_executor()
helpers = (async_tools._await_awaitable, async_tools._run_coro_in_fresh_loop, async_tools.run_coro_sync, async_tools.run_blocking_async)
for helper in helpers:
    (parameter,) = helper.__type_params__
    hints = get_type_hints(helper, globalns={**vars(async_tools), 'Awaitable': Awaitable, 'Callable': Callable}, localns={'T': parameter})
    assert hints['return'] is parameter
assert len({helper.__type_params__[0] for helper in helpers}) == 4
assert not hasattr(async_tools, 'T') and not hasattr(async_tools, 'TypeVar')
module = Path(async_tools.__file__)
print(json.dumps({'outcome': 'PASS', 'module': str(module), 'module_sha256': hashlib.sha256(module.read_bytes()).hexdigest(), 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'python': sys.version, 'platform': platform.platform(), 'accounting': records, 'physical_executions': executions, 'bridge_controls': 'direct7, running-loop11, blocking context owner, helper generic identities', 'limitations': 'Actual Future cancellation and real post-shutdown refusal, without replacing source functions. This does not claim physical worker capacity during user done callbacks.'}, indent=2))
