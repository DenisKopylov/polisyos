"""Tests for WorkerPool protocol and LocalWorkerPool."""

from __future__ import annotations

import asyncio

import pytest

from polisyos.scientist.engine.runner.worker_pool import (
    NodeTask,
    PoolCapacity,
    ResourceRequirements,
    WorkerPool,
)


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
        with pytest.raises(Exception):
            PoolCapacity(
                total_workers=1, idle_workers=1,
                active_tasks=0, queue_depth=0,
                extra=True,
            )


class TestLocalWorkerPool:
    def test_capacity_defaults(self) -> None:
        from polisyos.scientist.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=4)
        cap = asyncio.run(pool.current_capacity())
        assert cap.total_workers == 4
        assert cap.idle_workers == 4
        assert cap.active_tasks == 0
        assert cap.queue_depth == 0

    def test_scale_to_changes_capacity(self) -> None:
        from polisyos.scientist.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=2)

        async def _test() -> None:
            await pool.scale_to(8)
            cap = await pool.current_capacity()
            assert cap.total_workers == 8

        asyncio.run(_test())

    def test_shutdown_rejects_new_tasks(self) -> None:
        from polisyos.scientist.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=2)

        async def _test() -> None:
            await pool.shutdown()
            with pytest.raises(RuntimeError, match="shut down"):
                await pool.submit(_make_task())

        asyncio.run(_test())
