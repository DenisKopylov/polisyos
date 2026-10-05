from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import time
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
