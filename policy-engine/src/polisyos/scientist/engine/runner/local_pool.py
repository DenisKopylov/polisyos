"""Local worker pool — asyncio-based pool for testing and fallback.

Uses an ``asyncio.Semaphore`` to bound concurrency and maintains
internal counters for capacity tracking.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from polisyos.scientist.engine.runner.worker_pool import (
    NodeTask,
    PoolCapacity,
)

_logger = logging.getLogger(__name__)


class LocalWorkerPool:
    """In-process worker pool backed by asyncio tasks.

    Implements the ``WorkerPool`` protocol.
    """

    def __init__(self, *, max_workers: int = 4) -> None:
        self._max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._active_tasks = 0
        self._queue_depth = 0
        self._shutdown = False

    async def submit(self, task: NodeTask) -> asyncio.Future[bytes]:
        """Submit a task for execution, returning a future for the result."""
        if self._shutdown:
            raise RuntimeError("Pool is shut down")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()

        asyncio.create_task(self._run_task(task, future))
        return future

    async def _run_task(self, task: NodeTask, future: asyncio.Future[bytes]) -> None:
        self._queue_depth += 1
        try:
            await self._semaphore.acquire()
            self._queue_depth -= 1
            self._active_tasks += 1
            try:
                from polisyos.scientist.engine.runner._activity_worker import (
                    run_node_in_worker,
                )

                payload = {
                    "node_id": task.node_id,
                    "alias": task.alias,
                    "params": task.params,
                    "state_bytes": task.state_bytes,
                    "trace_carrier": task.trace_carrier,
                    "timeout_s": task.timeout_s,
                    "context_meta": task.context_meta,
                }

                if task.timeout_s is not None:
                    result = await asyncio.wait_for(
                        run_node_in_worker(payload),
                        timeout=task.timeout_s,
                    )
                else:
                    result = await run_node_in_worker(payload)

                if not future.done():
                    future.set_result(result)
            except Exception as exc:
                if not future.done():
                    future.set_exception(exc)
            finally:
                self._active_tasks -= 1
                self._semaphore.release()
        except Exception as exc:
            self._queue_depth = max(0, self._queue_depth - 1)
            if not future.done():
                future.set_exception(exc)

    async def scale_to(self, workers: int) -> None:
        """Resize the pool's concurrency limit.

        Note: this only affects new task submissions — in-flight tasks
        continue until completion.
        """
        self._max_workers = workers
        self._semaphore = asyncio.Semaphore(workers)

    async def current_capacity(self) -> PoolCapacity:
        """Return a snapshot of the pool's capacity."""
        return PoolCapacity(
            total_workers=self._max_workers,
            idle_workers=max(0, self._max_workers - self._active_tasks),
            active_tasks=self._active_tasks,
            queue_depth=self._queue_depth,
        )

    async def shutdown(self, graceful: bool = True) -> None:
        """Mark the pool as shut down."""
        self._shutdown = True
