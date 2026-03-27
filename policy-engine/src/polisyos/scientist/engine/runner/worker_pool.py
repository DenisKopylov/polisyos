"""Worker pool protocol and data models for horizontal scaling.

Defines the ``WorkerPool`` protocol for submitting node tasks to a
pool of workers, along with ``NodeTask``, ``ResourceRequirements``,
and ``PoolCapacity`` models.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


type JsonValue = str | int | float | bool | None | dict[str, Any] | list[Any]


@dataclass(frozen=True)
class ResourceRequirements:
    """Resource requirements for a node task."""

    cpu_cores: float = 1.0
    memory_mb: int = 512
    gpu: bool = False


@dataclass(frozen=True)
class NodeTask:
    """A unit of work to be submitted to a worker pool."""

    node_id: str
    alias: str
    params: dict[str, Any]
    state_bytes: bytes
    trace_carrier: dict[str, str]
    timeout_s: float | None = None
    context_meta: dict[str, Any] = field(default_factory=dict)
    resource_requirements: ResourceRequirements | None = None


class PoolCapacity(BaseModel):
    """Snapshot of a worker pool's capacity."""

    model_config = ConfigDict(extra="forbid")

    total_workers: int
    idle_workers: int
    active_tasks: int
    queue_depth: int


@runtime_checkable
class WorkerPool(Protocol):
    """Protocol for a pool of workers that can execute node tasks."""

    async def submit(self, task: NodeTask) -> asyncio.Future[bytes]:  # pragma: no cover - protocol
        """Submit a task and return a future for the result bytes."""
        ...

    async def scale_to(self, workers: int) -> None:  # pragma: no cover - protocol
        """Scale the pool to the given number of workers."""
        ...

    async def current_capacity(self) -> PoolCapacity:  # pragma: no cover - protocol
        """Return current pool capacity snapshot."""
        ...

    async def shutdown(self, graceful: bool = True) -> None:  # pragma: no cover - protocol
        """Shutdown the pool, optionally waiting for in-flight tasks."""
        ...
