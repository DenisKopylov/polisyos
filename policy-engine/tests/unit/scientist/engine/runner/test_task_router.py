"""Tests for TaskRouter and routing strategies."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from polisyos.scientist.engine.runner.task_router import (
    LeastLoadedStrategy,
    ResourceAwareStrategy,
    RoundRobinStrategy,
    TaskRouter,
    WeightedQueueStrategy,
)
from polisyos.scientist.engine.runner.worker_pool import (
    NodeTask,
    PoolCapacity,
    ResourceRequirements,
)


def _make_task(gpu: bool = False, *, priority: int = 0, queue_weight: float = 1.0) -> NodeTask:
    req = ResourceRequirements(gpu=gpu) if gpu else None
    return NodeTask(
        node_id="n",
        alias="a",
        params={},
        state_bytes=b"{}",
        trace_carrier={},
        resource_requirements=req,
        priority=priority,
        queue_weight=queue_weight,
    )


def _mock_pool(idle: int = 4, total: int = 8, active: int = 4, queue: int = 0) -> AsyncMock:
    pool = AsyncMock()
    pool.current_capacity = AsyncMock(
        return_value=PoolCapacity(
            total_workers=total,
            idle_workers=idle,
            active_tasks=active,
            queue_depth=queue,
        )
    )
    pool.submit = AsyncMock(return_value=AsyncMock())
    return pool


class TestResourceAwareStrategy:
    def test_gpu_task_to_gpu_pool(self) -> None:
        strategy = ResourceAwareStrategy()
        caps = {
            "cpu": PoolCapacity(total_workers=4, idle_workers=2, active_tasks=2, queue_depth=0),
            "gpu": PoolCapacity(total_workers=2, idle_workers=1, active_tasks=1, queue_depth=0),
        }
        result = asyncio.run(strategy.select_pool(_make_task(gpu=True), caps))
        assert result == "gpu"

    def test_cpu_task_to_cpu_pool(self) -> None:
        strategy = ResourceAwareStrategy()
        caps = {
            "cpu": PoolCapacity(total_workers=4, idle_workers=2, active_tasks=2, queue_depth=0),
            "gpu": PoolCapacity(total_workers=2, idle_workers=1, active_tasks=1, queue_depth=0),
        }
        result = asyncio.run(strategy.select_pool(_make_task(gpu=False), caps))
        assert result == "cpu"

    def test_gpu_fallback_to_first_pool(self) -> None:
        strategy = ResourceAwareStrategy()
        caps = {
            "default": PoolCapacity(total_workers=4, idle_workers=2, active_tasks=2, queue_depth=0),
        }
        result = asyncio.run(strategy.select_pool(_make_task(gpu=True), caps))
        assert result == "default"


class TestRoundRobinStrategy:
    def test_even_distribution(self) -> None:
        strategy = RoundRobinStrategy()
        caps = {
            "a": PoolCapacity(total_workers=4, idle_workers=2, active_tasks=2, queue_depth=0),
            "b": PoolCapacity(total_workers=4, idle_workers=2, active_tasks=2, queue_depth=0),
        }
        results = [asyncio.run(strategy.select_pool(_make_task(), caps)) for _ in range(4)]
        assert results.count("a") == 2
        assert results.count("b") == 2


class TestLeastLoadedStrategy:
    def test_picks_most_idle(self) -> None:
        strategy = LeastLoadedStrategy()
        caps = {
            "busy": PoolCapacity(total_workers=8, idle_workers=1, active_tasks=7, queue_depth=0),
            "idle": PoolCapacity(total_workers=8, idle_workers=6, active_tasks=2, queue_depth=0),
        }
        result = asyncio.run(strategy.select_pool(_make_task(), caps))
        assert result == "idle"


class TestWeightedQueueStrategy:
    def test_prefers_less_backlogged_pool_for_weighted_task(self) -> None:
        strategy = WeightedQueueStrategy()
        caps = {
            "cpu_a": PoolCapacity(total_workers=8, idle_workers=2, active_tasks=6, queue_depth=8),
            "cpu_b": PoolCapacity(total_workers=8, idle_workers=1, active_tasks=7, queue_depth=1),
        }
        result = asyncio.run(strategy.select_pool(_make_task(priority=5, queue_weight=3.0), caps))
        assert result == "cpu_b"


class TestTaskRouter:
    def test_route_returns_pool_name(self) -> None:
        pools = {"cpu": _mock_pool(), "gpu": _mock_pool()}
        router = TaskRouter(pools, strategy=ResourceAwareStrategy())
        result = asyncio.run(router.route(_make_task()))
        assert result in pools

    def test_empty_pools_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one pool"):
            TaskRouter({})
