from __future__ import annotations

import asyncio
import concurrent.futures
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextvars import ContextVar
from typing import get_type_hints

import pytest

from polisyos.common.async_tools import get_shared_executor, run_blocking_async, run_coro_sync


def test_function_type_parameters_resolve_without_module_typevar() -> None:
    """All four helpers resolve their own generic identities after cleanup."""
    from collections.abc import Awaitable, Callable

    from polisyos.common import async_tools

    helpers = (
        async_tools._await_awaitable,
        async_tools._run_coro_in_fresh_loop,
        async_tools.run_coro_sync,
        async_tools.run_blocking_async,
    )
    for helper in helpers:
        (parameter,) = helper.__type_params__
        hints = get_type_hints(
            helper,
            globalns={**vars(async_tools), "Awaitable": Awaitable, "Callable": Callable},
            localns={"T": parameter},
        )
        assert hints["return"] is parameter
    assert len({helper.__type_params__[0] for helper in helpers}) == 4
    assert not hasattr(async_tools, "T")
    assert not hasattr(async_tools, "TypeVar")


def test_run_coro_sync_returns_result_without_running_loop() -> None:
    assert run_coro_sync(asyncio.sleep(0, result=7)) == 7


def test_run_coro_sync_works_inside_running_loop() -> None:
    async def _wrapper() -> int:
        return run_coro_sync(asyncio.sleep(0.01, result=11))

    assert asyncio.run(_wrapper()) == 11


def test_run_coro_sync_preserves_context_inside_running_loop() -> None:
    owner_scope: ContextVar[str | None] = ContextVar("owner_scope", default=None)

    async def _read_scope() -> str | None:
        return owner_scope.get()

    async def _wrapper() -> str | None:
        token = owner_scope.set("tenant-owner")
        try:
            return run_coro_sync(_read_scope())
        finally:
            owner_scope.reset(token)

    assert asyncio.run(_wrapper()) == "tenant-owner"


def test_run_coro_sync_times_out_instead_of_hanging() -> None:
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="did not complete within"):
        run_coro_sync(asyncio.sleep(1), timeout_seconds=0.05)
    assert time.monotonic() - started < 0.5


def test_run_blocking_async_keeps_event_loop_responsive() -> None:
    async def _exercise() -> bool:
        ticked = False

        async def _ticker() -> None:
            nonlocal ticked
            await asyncio.sleep(0.01)
            ticked = True

        ticker = asyncio.create_task(_ticker())
        await run_blocking_async(time.sleep, 0.05)
        await ticker
        return ticked

    assert run_coro_sync(_exercise()) is True


def test_run_blocking_async_times_out() -> None:
    async def _exercise() -> None:
        await run_blocking_async(time.sleep, 1.0, timeout_seconds=0.05)

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="Blocking call did not complete within"):
        run_coro_sync(_exercise())
    assert time.monotonic() - started < 0.5


def test_run_blocking_async_preserves_inner_timeout_message() -> None:
    def _raise_inner_timeout() -> None:
        raise TimeoutError("inner worker timeout")

    async def _exercise() -> None:
        await run_blocking_async(_raise_inner_timeout, timeout_seconds=5.0)

    with pytest.raises(TimeoutError, match=r"^inner worker timeout$"):
        asyncio.run(_exercise())


def test_run_blocking_async_reuses_shared_executor_soak_smoke() -> None:
    async def _exercise() -> set[int]:
        executor_ids: set[int] = set()
        for _ in range(32):
            executor_ids.add(id(get_shared_executor()))
            assert await run_blocking_async(lambda: "ok") == "ok"
        executor_ids.add(id(get_shared_executor()))
        return executor_ids

    assert run_coro_sync(_exercise()) == {id(get_shared_executor())}


def test_run_blocking_async_concurrent_soak_smoke() -> None:
    async def _exercise() -> tuple[list[int], set[int]]:
        async def _run_one(index: int) -> int:
            return await run_blocking_async(lambda: index)

        results = await asyncio.gather(*(_run_one(index) for index in range(24)))
        return results, {id(get_shared_executor())}

    results, executor_ids = run_coro_sync(_exercise())
    assert results == list(range(24))
    assert executor_ids == {id(get_shared_executor())}


@pytest.fixture
def capacity_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[concurrent.futures.ThreadPoolExecutor]:
    """Use the actual shared producer at its supported four-worker minimum."""
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools.os, "cpu_count", lambda: 4)
    executor = get_shared_executor()
    try:
        yield executor
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_done_callbacks_hold_physical_capacity_and_refuse_nested_work(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    """Completed Futures do not free workers still inside their callbacks."""
    executor = capacity_executor
    work_gate = threading.Event()
    callback_gate = threading.Event()
    entered = threading.Barrier(5)
    decided = threading.Barrier(5)
    errors: list[BaseException] = []
    actual_inner_calls: list[int] = []

    def callback(future: concurrent.futures.Future[int]) -> None:
        assert future.result() == 7
        entered.wait(timeout=3)
        try:
            executor.submit(actual_inner_calls.append, 42).result(timeout=0.15)
        except BaseException as exc:
            errors.append(exc)
        finally:
            decided.wait(timeout=3)
            callback_gate.wait(timeout=3)

    futures = [executor.submit(lambda: (work_gate.wait(timeout=3), 7)[1]) for _ in range(4)]
    for future in futures:
        future.add_done_callback(callback)
    try:
        work_gate.set()
        entered.wait(timeout=3)
        decided.wait(timeout=3)
        assert all(future.done() and future.result() == 7 for future in futures)
        assert actual_inner_calls == []
        assert [type(exc).__name__ for exc in errors] == ["SharedExecutorReentrancyError"] * 4
    finally:
        work_gate.set()
        callback_gate.set()
    executor.shutdown(wait=True)
    assert actual_inner_calls == []


def test_worker_body_refuses_nested_work_when_physically_full(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    entered = threading.Barrier(4)
    decided = threading.Barrier(5)
    release = threading.Event()
    inner_calls: list[int] = []
    results: list[str] = []

    def outer() -> str:
        entered.wait(timeout=3)
        try:
            capacity_executor.submit(inner_calls.append, 42).result(timeout=0.15)
        except BaseException as exc:
            result = type(exc).__name__
        else:
            result = "accepted"
        results.append(result)
        decided.wait(timeout=3)
        release.wait(timeout=3)
        return result

    futures = [capacity_executor.submit(outer) for _ in range(4)]
    try:
        decided.wait(timeout=3)
        assert results == ["SharedExecutorReentrancyError"] * 4
    finally:
        release.set()
    assert [future.result(timeout=3) for future in futures] == ["SharedExecutorReentrancyError"] * 4
    capacity_executor.shutdown(wait=True)
    assert inner_calls == []


def test_nested_callback_uses_an_actual_spare_worker(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    gate = threading.Event()
    finished = threading.Event()
    result: list[int] = []
    worker_ids: list[int] = []

    def inner() -> int:
        worker_ids.append(threading.get_ident())
        return 42

    def callback(future: concurrent.futures.Future[int]) -> None:
        worker_ids.append(threading.get_ident())
        assert future.result() == 7
        result.append(capacity_executor.submit(inner).result(timeout=2))
        finished.set()

    future = capacity_executor.submit(lambda: (gate.wait(timeout=3), 7)[1])
    future.add_done_callback(callback)
    gate.set()
    assert finished.wait(timeout=3)
    assert result == [42]
    assert len(set(worker_ids)) == 2


def test_late_callback_refuses_nested_work_under_new_full_workers(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    finished = capacity_executor.submit(lambda: 7)
    assert finished.result(timeout=3) == 7
    worker_gate = threading.Event()
    started = threading.Barrier(5)
    inner_calls: list[int] = []
    errors: list[BaseException] = []
    callback_threads: list[int] = []

    def blocker() -> None:
        started.wait(timeout=3)
        worker_gate.wait(timeout=3)

    def callback(future: concurrent.futures.Future[int]) -> None:
        callback_threads.append(threading.get_ident())
        assert future.result() == 7
        try:
            capacity_executor.submit(inner_calls.append, 42).result(timeout=0.15)
        except BaseException as exc:
            errors.append(exc)

    blockers = [capacity_executor.submit(blocker) for _ in range(4)]
    try:
        started.wait(timeout=3)
        finished.add_done_callback(callback)
        assert callback_threads == [threading.get_ident()]
        assert [type(exc).__name__ for exc in errors] == ["SharedExecutorReentrancyError"]
        assert inner_calls == []
    finally:
        worker_gate.set()
    for future in blockers:
        future.result(timeout=3)
    capacity_executor.shutdown(wait=True)
    assert inner_calls == []


def test_proxy_queue_cancellation_notifies_waiters_and_never_executes(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    gate = threading.Event()
    started = threading.Barrier(5)
    calls: list[int] = []
    callbacks: list[tuple[bool, int]] = []

    def blocker() -> None:
        started.wait(timeout=3)
        gate.wait(timeout=3)

    blockers = [capacity_executor.submit(blocker) for _ in range(4)]
    try:
        started.wait(timeout=3)
        queued = capacity_executor.submit(calls.append, 42)
        assert not queued.running() and not queued.done()
        queued.add_done_callback(
            lambda future: callbacks.append((future.cancelled(), threading.get_ident()))
        )
        assert queued.cancel() and queued.cancel()
        assert queued.cancelled() and queued.done() and not queued.running()
        assert callbacks == [(True, threading.get_ident())]
        done, pending = concurrent.futures.wait([queued], timeout=0.1)
        assert done == {queued} and not pending
        with pytest.raises(concurrent.futures.CancelledError):
            queued.result()
    finally:
        gate.set()
    for future in blockers:
        future.result(timeout=3)
    assert calls == []


def test_proxy_callback_order_exception_context_and_late_registration(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
    caplog: pytest.LogCaptureFixture,
) -> None:
    gate = threading.Event()
    callbacks_finished = threading.Event()
    seen: list[tuple[str, int]] = []
    worker_ids: list[int] = []

    def work() -> int:
        worker_ids.append(threading.get_ident())
        gate.wait(timeout=3)
        return 42

    def first(future: concurrent.futures.Future[int]) -> None:
        assert future.result() == 42
        seen.append(("first", threading.get_ident()))
        raise ValueError("callback sentinel")

    def second(future: concurrent.futures.Future[int]) -> None:
        seen.append(("second", threading.get_ident()))
        callbacks_finished.set()

    future = capacity_executor.submit(work)
    assert isinstance(future, concurrent.futures.Future)
    future.add_done_callback(first)
    future.add_done_callback(second)
    gate.set()
    assert future.result(timeout=3) == 42
    assert callbacks_finished.wait(timeout=3)
    assert seen == [("first", worker_ids[0]), ("second", worker_ids[0])]
    assert "callback sentinel" in caplog.text
    future.add_done_callback(lambda _: seen.append(("late", threading.get_ident())))
    assert seen[-1] == ("late", threading.get_ident())
    assert capacity_executor.submit(lambda: 43).result(timeout=3) == 43


@pytest.mark.asyncio
async def test_proxy_future_preserves_asyncio_result_exception_and_context(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    scope: ContextVar[str | None] = ContextVar("callback_scope", default=None)
    token = scope.set("request-A")
    try:
        assert await asyncio.wrap_future(capacity_executor.submit(scope.get)) == "request-A"
    finally:
        scope.reset(token)
    assert await asyncio.wrap_future(capacity_executor.submit(scope.get)) is None
    error = ValueError("producer sentinel")

    def fail() -> None:
        raise error

    failed = capacity_executor.submit(fail)
    with pytest.raises(ValueError, match="producer sentinel") as captured:
        await asyncio.wrap_future(failed)
    assert captured.value is error and failed.exception() is error


def test_shutdown_cancel_callback_can_submit_without_a_lock_cycle() -> None:
    """Base shutdown cancellation must not call user code under admission."""
    script = """
import json, os, threading
from polisyos.common import async_tools
async_tools.os.cpu_count = lambda: 4
executor = async_tools.get_shared_executor()
gate = threading.Event()
entered = threading.Barrier(5)
callback_done = threading.Event()
errors = []
calls = []
def block():
    entered.wait(timeout=2)
    gate.wait(timeout=3)
blockers = [executor.submit(block) for _ in range(4)]
entered.wait(timeout=2)
queued = executor.submit(calls.append, 42)
def callback(future):
    try:
        executor.submit(calls.append, 43)
    except RuntimeError as error:
        errors.append(type(error).__name__)
    callback_done.set()
queued.add_done_callback(callback)
shutdown = threading.Thread(target=lambda: executor.shutdown(wait=False, cancel_futures=True))
shutdown.start()
shutdown.join(timeout=.3)
observation = {'shutdown_finished': not shutdown.is_alive(), 'callback_finished': callback_done.is_set(), 'queued_cancelled': queued.cancelled(), 'calls': calls, 'errors': errors}
gate.set()
print(json.dumps(observation), flush=True)
if shutdown.is_alive():
    os._exit(73)
executor.shutdown(wait=True)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=5
    )
    import json

    observed = json.loads(completed.stdout)
    assert observed == {
        "shutdown_finished": True,
        "callback_finished": True,
        "queued_cancelled": True,
        "calls": [],
        "errors": ["RuntimeError"],
    }, completed.stdout + completed.stderr
    assert completed.returncode == 0


@pytest.mark.asyncio
async def test_explicit_unbounded_owner_does_not_inherit_helper_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_DEFAULT_TIMEOUT_SECONDS", 0.01)
    assert await run_blocking_async(lambda: (time.sleep(0.03), 42)[1], unbounded=True) == 42
    with pytest.raises(TimeoutError, match="Blocking call did not complete"):
        await run_blocking_async(time.sleep, 0.03)


@pytest.mark.asyncio
async def test_unbounded_and_float_timeout_are_rejected_before_admission() -> None:
    calls: list[int] = []
    with pytest.raises(ValueError, match="unbounded cannot be combined"):
        await run_blocking_async(calls.append, 42, unbounded=True, timeout_seconds=1)
    assert calls == []
