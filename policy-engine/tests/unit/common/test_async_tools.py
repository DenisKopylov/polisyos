from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
import time
from contextvars import ContextVar
from pathlib import Path
from typing import get_type_hints

import pytest

from polisyos.common.async_tools import get_shared_executor, run_blocking_async, run_coro_sync


def _probe_shared_executor_shutdown() -> None:
    """Gate actual executor locks; exit rather than leak a deadlocked worker."""
    from polisyos.common import async_tools

    shutdown_owned = threading.Event()
    allow_shutdown = threading.Event()
    submit_waits_shutdown = threading.Event()
    callback_touches_admission = threading.Event()

    class ObservedLock:
        def __init__(self, lock, *, before=None, after=None):
            self.lock = lock
            self.before = before
            self.after = after
            self.guard = threading.Lock()
            self.owner = None
            self.waiting = set()

        def __enter__(self):
            name = threading.current_thread().name
            with self.guard:
                self.waiting.add(name)
            if self.before:
                self.before(name)
            self.lock.acquire()
            with self.guard:
                self.waiting.remove(name)
                self.owner = name
            if self.after:
                self.after(name)
            return self

        def __exit__(self, *_args):
            with self.guard:
                self.owner = None
            self.lock.release()

        def snapshot(self):
            with self.guard:
                return {"owner": self.owner, "waiting": sorted(self.waiting)}

    executor = async_tools._SharedExecutor(max_workers=1, thread_name_prefix="shutdown-probe")
    release_worker = threading.Event()
    worker_started = threading.Event()

    def work():
        worker_started.set()
        assert release_worker.wait(3)
        return 42

    active = executor.submit(work)
    assert worker_started.wait(1)
    queued = executor.submit(lambda: "must not execute")

    def before_shutdown(name):
        if name == "submitter":
            submit_waits_shutdown.set()

    def after_shutdown(name):
        if name == "shutdown":
            shutdown_owned.set()
            assert allow_shutdown.wait(1)

    def before_admission(name):
        if name == "shutdown":
            callback_touches_admission.set()

    executor._admission_lock = ObservedLock(executor._admission_lock, before=before_admission)
    executor._shutdown_lock = ObservedLock(
        executor._shutdown_lock, before=before_shutdown, after=after_shutdown
    )
    errors = []

    def submit():
        try:
            executor.submit(lambda: "must be rejected")
        except RuntimeError as exc:
            errors.append(str(exc))

    stopping = threading.Thread(
        target=lambda: executor.shutdown(wait=False, cancel_futures=True),
        name="shutdown",
        daemon=True,
    )
    submitting = threading.Thread(target=submit, name="submitter", daemon=True)
    stopping.start()
    assert shutdown_owned.wait(1)
    submitting.start()
    assert submit_waits_shutdown.wait(1)
    allow_shutdown.set()
    assert callback_touches_admission.wait(1)
    stopping.join(0.1)
    submitting.join(0.1)
    if stopping.is_alive() or submitting.is_alive():
        record = {
            "admission": executor._admission_lock.snapshot(),
            "shutdown": executor._shutdown_lock.snapshot(),
        }
        print(json.dumps(record), flush=True)  # noqa: T201 - deciding child evidence
        os._exit(73)
    assert queued.cancelled()
    assert errors == ["cannot schedule new futures after shutdown"]
    assert executor._outstanding_jobs == 1
    release_worker.set()
    executor.shutdown(wait=True, cancel_futures=True)
    assert active.result() == 42
    assert executor._outstanding_jobs == 0


def test_shared_executor_submit_and_shutdown_do_not_invert_locks() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy,sys; runpy.run_path(sys.argv[1])['_probe_shared_executor_shutdown']()",
            str(Path(__file__).resolve()),
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_shared_executor_reservations_release_once_on_cancellation_and_rejection() -> None:
    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=1, thread_name_prefix="accounting")
    started = threading.Event()
    release = threading.Event()
    executions = []

    def work():
        started.set()
        assert release.wait(3)
        return 42

    try:
        active = executor.submit(work)
        assert started.wait(1)
        manual = executor.submit(lambda: executions.append("manual"))
        shutdown = executor.submit(lambda: executions.append("shutdown"))
        assert executor._outstanding_jobs == 3
        assert manual.cancel()
        assert manual.cancel()
        assert executor._outstanding_jobs == 2
        executor.shutdown(wait=False, cancel_futures=True)
        assert shutdown.cancelled()
        assert executor._outstanding_jobs == 1
        with pytest.raises(RuntimeError, match="cannot schedule new futures after shutdown"):
            executor.submit(lambda: executions.append("rejected"))
        assert executor._outstanding_jobs == 1
        release.set()
        executor.shutdown(wait=True)
        assert active.result() == 42
        assert executor._outstanding_jobs == 0
        assert executions == []
    finally:
        release.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_shared_executor_reservations_release_after_fast_success_and_failure() -> None:
    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=4, thread_name_prefix="fast-accounting")

    def work(index):
        if index % 2:
            raise ValueError(index)
        return index

    try:
        futures = [executor.submit(work, index) for index in range(256)]
        for index, future in enumerate(futures):
            if index % 2:
                with pytest.raises(ValueError):
                    future.result(timeout=2)
            else:
                assert future.result(timeout=2) == index
    finally:
        executor.shutdown(wait=True)
    assert executor._outstanding_jobs == 0


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


def test_nested_shared_executor_work_is_rejected_before_pool_saturation(monkeypatch) -> None:
    """A pool worker cannot enqueue work that needs the same occupied pool."""
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools.os, "cpu_count", lambda: 4)
    barrier = threading.Barrier(4)
    started: list[int] = []
    finished: list[int] = []

    async def _inner(index: int) -> int:
        barrier.wait(timeout=3.0)
        try:
            return await run_blocking_async(
                lambda: started.append(index) or 42,
                timeout_seconds=0.1,
            )
        finally:
            finished.append(index)

    def _outer(index: int) -> int | Exception:
        async def _running_loop() -> int:
            return run_coro_sync(_inner(index), timeout_seconds=0.5)

        try:
            return asyncio.run(_running_loop())
        except Exception as exc:
            return exc

    executor = get_shared_executor()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as callers:
            results = list(callers.map(_outer, range(4)))
        assert all(
            result == 42
            or (
                type(result) is RuntimeError
                and "shared executor does not support reentrant submission" in str(result)
            )
            for result in results
        )
        assert len(started) == results.count(42)
        assert sorted(finished) == list(range(4))

        async def _control() -> list[int]:
            return await asyncio.gather(
                *(run_blocking_async(lambda: 42, timeout_seconds=0.5) for _ in range(4))
            )

        assert asyncio.run(_control()) == [42, 42, 42, 42]
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_cooperative_timeout_releases_shared_coroutine_worker() -> None:
    """Cancellation runs finally and makes the worker available to later work."""
    cleaned = threading.Event()

    async def _wait() -> None:
        try:
            await asyncio.sleep(10)
        finally:
            cleaned.set()

    async def _running_loop() -> None:
        with pytest.raises(TimeoutError):
            run_coro_sync(_wait(), timeout_seconds=0.05)

    asyncio.run(_running_loop())
    assert cleaned.wait(timeout=0.5)
    assert get_shared_executor().submit(lambda: 42).result(timeout=0.5) == 42
