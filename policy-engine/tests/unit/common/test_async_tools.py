from __future__ import annotations

import asyncio
import concurrent.futures
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import get_type_hints

import pytest

import polisyos.common.async_tools as async_tools
from polisyos.common.async_tools import get_shared_executor, run_blocking_async, run_coro_sync


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


def test_async_bridge_module_typevar_cleanup_preserves_function_type_parameters() -> None:
    """The narrow module cleanup must not change any function generic contract."""
    assert not hasattr(async_tools, "T")
    assert not hasattr(async_tools, "TypeVar")

    namespace = dict(vars(async_tools))
    namespace.update(Awaitable=Awaitable, Callable=Callable)
    generic_functions = (
        async_tools._await_awaitable,
        async_tools._run_coro_in_fresh_loop,
        async_tools.run_coro_sync,
        async_tools.run_blocking_async,
    )

    for function in generic_functions:
        type_params = getattr(function, "__type_params__", ())
        assert len(type_params) == 1
        assert type_params[0].__name__ == "T"
        hints = get_type_hints(function, globalns=namespace, localns=namespace)
        assert "return" in hints


def test_shared_executor_saturation_does_not_turn_inner_work_into_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A small saturated pool must progress or reject re-entry explicitly."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", executor)

    def _run_inner(index: int) -> int:
        async def _exercise() -> int:
            return await run_blocking_async(lambda: index, timeout_seconds=0.02)

        return asyncio.run(_exercise())

    futures = [executor.submit(_run_inner, index) for index in range(2)]
    outcomes: list[object] = []
    try:
        for future in futures:
            try:
                outcomes.append(future.result(timeout=0.5))
            except Exception as exc:  # explicit re-entry rejection is allowed
                outcomes.append(exc)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)

    for index, outcome in enumerate(outcomes):
        if outcome == index:
            continue
        assert type(outcome) is RuntimeError
        assert str(outcome) == "async bridge re-entry into the shared executor is unsupported"
