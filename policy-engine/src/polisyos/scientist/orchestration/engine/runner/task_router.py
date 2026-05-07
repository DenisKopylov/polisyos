"""Task routing across worker pools.

Routes ``NodeTask`` instances to the appropriate pool based on
configurable strategies (resource-aware, round-robin, least-loaded,
priority-aware weighted queuing).
"""

from __future__ import annotations

import itertools
import logging
from typing import Protocol, runtime_checkable

from polisyos.scientist.orchestration.engine.runner.worker_pool import (
    NodeTask,
    PoolCapacity,
    WorkerPool,
)

_logger = logging.getLogger(__name__)


@runtime_checkable
class RoutingStrategy(Protocol):
    """Strategy for selecting a pool for a given task."""

    async def select_pool(
        self,
        task: NodeTask,
        capacities: dict[str, PoolCapacity],
    ) -> str:  # pragma: no cover - protocol
        """Return the pool name for this task."""
        ...


class ResourceAwareStrategy:
    """Route GPU tasks to a 'gpu' pool, everything else to 'cpu'.

    Falls back to the first available pool if the required pool
    doesn't exist.
    """

    async def select_pool(
        self,
        task: NodeTask,
        capacities: dict[str, PoolCapacity],
    ) -> str:
        if task.resource_requirements and task.resource_requirements.gpu:
            if "gpu" in capacities:
                return "gpu"
        if "cpu" in capacities:
            return "cpu"
        # Fallback to first pool
        return next(iter(capacities))


class RoundRobinStrategy:
    """Cycle through pools in order."""

    def __init__(self) -> None:
        self._cycle: itertools.cycle[str] | None = None
        self._pool_names: list[str] = []

    async def select_pool(
        self,
        task: NodeTask,
        capacities: dict[str, PoolCapacity],
    ) -> str:
        pool_names = sorted(capacities.keys())
        if pool_names != self._pool_names:
            self._pool_names = pool_names
            self._cycle = itertools.cycle(pool_names)
        assert self._cycle is not None
        return next(self._cycle)


class LeastLoadedStrategy:
    """Route to the pool with the most idle workers."""

    async def select_pool(
        self,
        task: NodeTask,
        capacities: dict[str, PoolCapacity],
    ) -> str:
        return max(
            capacities,
            key=lambda name: capacities[name].idle_workers,
        )


class WeightedQueueStrategy:
    """Route high-priority tasks toward the pool with the healthiest queue score."""

    async def select_pool(
        self,
        task: NodeTask,
        capacities: dict[str, PoolCapacity],
    ) -> str:
        preferred_pool: str | None = None
        if task.resource_requirements and task.resource_requirements.gpu and "gpu" in capacities:
            preferred_pool = "gpu"
        elif "cpu" in capacities:
            preferred_pool = "cpu"

        candidate_names = (
            [preferred_pool] if preferred_pool is not None else sorted(capacities.keys())
        )
        if preferred_pool is None:
            candidate_names = sorted(capacities.keys())

        def _score(pool_name: str) -> tuple[float, int, int, str]:
            capacity = capacities[pool_name]
            weighted_depth = max(float(capacity.queue_depth) + float(task.queue_weight), 1.0)
            idle_bias = float(capacity.idle_workers + max(task.priority, 0) + 1)
            score = idle_bias / weighted_depth
            return (
                score,
                capacity.idle_workers,
                -capacity.queue_depth,
                pool_name,
            )

        return max(candidate_names, key=_score)


class TaskRouter:
    """Routes tasks to worker pools using a pluggable strategy.

    Parameters
    ----------
    pools:
        Mapping of pool name to ``WorkerPool`` instance.
    strategy:
        Routing strategy (default: ``ResourceAwareStrategy``).
    """

    def __init__(
        self,
        pools: dict[str, WorkerPool],
        strategy: RoutingStrategy | None = None,
    ) -> None:
        if not pools:
            raise ValueError("TaskRouter requires at least one pool")
        self._pools = pools
        self._strategy = strategy or ResourceAwareStrategy()

    async def route(self, task: NodeTask) -> str:
        """Select the pool name for *task* and return it."""
        capacities = {}
        for name, pool in self._pools.items():
            capacities[name] = await pool.current_capacity()
        return await self._strategy.select_pool(task, capacities)

    async def submit(self, task: NodeTask) -> bytes:
        """Route *task* to the best pool and await its result."""
        pool_name = await self.route(task)
        pool = self._pools[pool_name]
        future = await pool.submit(task)
        return await future
