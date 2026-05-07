"""Tests for WorkerPool protocol and LocalWorkerPool."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from polisyos.scientist.orchestration.engine.runner.worker_pool import (
    NodeTask,
    PoolCapacity,
    ResourceRequirements,
)
from pydantic import ValidationError


def _make_task(**overrides) -> NodeTask:
    defaults = {
        "node_id": "test_node",
        "alias": "test",
        "params": {},
        "state_bytes": b"{}",
        "trace_carrier": {},
    }
    defaults.update(overrides)
    return NodeTask(**defaults)


class TestNodeTask:
    def test_frozen(self) -> None:
        task = _make_task()
        with pytest.raises(AttributeError):
            task.node_id = "changed"  # type: ignore[misc]

    def test_default_resource_requirements(self) -> None:
        task = _make_task()
        assert task.resource_requirements is None
        assert task.priority == 0
        assert task.queue_weight == 1.0

    def test_with_resource_requirements(self) -> None:
        req = ResourceRequirements(cpu_cores=2.0, memory_mb=1024, gpu=True)
        task = _make_task(resource_requirements=req)
        assert task.resource_requirements is not None
        assert task.resource_requirements.gpu is True


class TestPoolCapacity:
    def test_model_creation(self) -> None:
        cap = PoolCapacity(
            total_workers=8,
            idle_workers=5,
            active_tasks=3,
            queue_depth=2,
        )
        assert cap.total_workers == 8
        assert cap.idle_workers == 5

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            PoolCapacity(
                total_workers=1,
                idle_workers=1,
                active_tasks=0,
                queue_depth=0,
                extra=True,
            )


class TestLocalWorkerPool:
    def test_capacity_defaults(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=4)
        cap = asyncio.run(pool.current_capacity())
        assert cap.total_workers == 4
        assert cap.idle_workers == 4
        assert cap.active_tasks == 0
        assert cap.queue_depth == 0

    def test_scale_to_changes_capacity(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=2)

        async def _test() -> None:
            await pool.scale_to(8)
            cap = await pool.current_capacity()
            assert cap.total_workers == 8

        asyncio.run(_test())

    def test_scale_down_does_not_release_old_permits(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=5)

        async def _test() -> None:
            active = 0
            after_shrink_active = 0
            shrink_started = False
            first_batch_started = asyncio.Event()
            release_first_batch = asyncio.Event()
            release_after_shrink = asyncio.Event()
            lock = asyncio.Lock()

            async def _run_node(payload):
                nonlocal active, after_shrink_active
                del payload
                async with lock:
                    active += 1
                    if shrink_started:
                        after_shrink_active += 1
                    if active == 5:
                        first_batch_started.set()
                try:
                    if shrink_started:
                        await release_after_shrink.wait()
                    else:
                        await release_first_batch.wait()
                    return b"{}"
                finally:
                    async with lock:
                        active -= 1

            with patch(
                "polisyos.scientist.orchestration.engine.runner._activity_worker.run_node_in_worker",
                side_effect=_run_node,
            ):
                futures = [await pool.submit(_make_task(alias=f"task_{idx}")) for idx in range(10)]
                await asyncio.wait_for(first_batch_started.wait(), timeout=2.0)
                shrink_started = True
                await pool.scale_to(1)
                release_first_batch.set()

                deadline = asyncio.get_running_loop().time() + 2.0
                while after_shrink_active == 0 and asyncio.get_running_loop().time() < deadline:
                    await asyncio.sleep(0.01)

                await asyncio.sleep(0.05)
                assert after_shrink_active == 1
                release_after_shrink.set()
                results = await asyncio.gather(*futures, return_exceptions=True)
                assert results == [b"{}"] * 10
                cap = await pool.current_capacity()
                assert cap.active_tasks == 0
                assert cap.queue_depth == 0

        asyncio.run(_test())

    def test_shutdown_rejects_new_tasks(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=2)

        async def _test() -> None:
            await pool.shutdown()
            with pytest.raises(RuntimeError, match="shut down"):
                await pool.submit(_make_task())

        asyncio.run(_test())

    def test_priority_queue_runs_high_priority_submission_first(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=1)

        async def _test() -> None:
            started: list[str] = []
            release_first = asyncio.Event()

            async def _run_node(payload):
                started.append(payload["alias"])
                if payload["alias"] == "low":
                    await release_first.wait()
                return payload["alias"].encode("utf-8")

            with patch(
                "polisyos.scientist.orchestration.engine.runner._activity_worker.run_node_in_worker",
                side_effect=_run_node,
            ):
                low = await pool.submit(_make_task(alias="low", priority=0))
                medium = await pool.submit(_make_task(alias="medium", priority=1))
                high = await pool.submit(_make_task(alias="high", priority=10))
                await asyncio.sleep(0.05)
                assert started == ["low"]
                release_first.set()
                results = await asyncio.gather(low, medium, high)
                assert results == [b"low", b"medium", b"high"]
                assert started == ["low", "high", "medium"]

        asyncio.run(_test())

    def test_worker_runtime_error_surfaces_on_future(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=1)

        async def _test() -> None:
            async def _run_node(_payload):
                raise RuntimeError("worker exploded")

            with patch(
                "polisyos.scientist.orchestration.engine.runner._activity_worker.run_node_in_worker",
                side_effect=_run_node,
            ):
                future = await pool.submit(_make_task(alias="boom"))
                with pytest.raises(RuntimeError, match="worker exploded"):
                    await future

        asyncio.run(_test())
