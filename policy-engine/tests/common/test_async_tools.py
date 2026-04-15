from __future__ import annotations

import asyncio
import time

import pytest

from polisyos.common.async_tools import get_shared_executor, run_blocking_async, run_coro_sync


def test_run_coro_sync_returns_result_without_running_loop() -> None:
    assert run_coro_sync(asyncio.sleep(0, result=7)) == 7


def test_run_coro_sync_works_inside_running_loop() -> None:
    async def _wrapper() -> int:
        return run_coro_sync(asyncio.sleep(0.01, result=11))

    assert asyncio.run(_wrapper()) == 11


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
