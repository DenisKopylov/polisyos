"""Local worker pool with deterministic priority queuing and resize-safe permits."""

from __future__ import annotations

import asyncio
import heapq
import logging
from dataclasses import dataclass, field

from polisyos.scientist.orchestration.engine.runner.worker_pool import (
    NodeTask,
    PoolCapacity,
)

_logger = logging.getLogger(__name__)
_LOCAL_POOL_RUNTIME_ERRORS = (
    AssertionError,
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


@dataclass(order=True)
class _QueuedSubmission:
    """Priority-ordered local submission waiting for execution capacity."""

    sort_priority: int
    submission_order: int
    task: NodeTask = field(compare=False)
    future: asyncio.Future[bytes] = field(compare=False)


class LocalWorkerPool:
    """In-process worker pool backed by asyncio tasks.

    Implements the ``WorkerPool`` protocol.
    """

    def __init__(self, *, max_workers: int = 4) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self._max_workers = max_workers
        self._capacity_changed = asyncio.Condition()
        self._active_tasks = 0
        self._shutdown = False
        self._runner_tasks: set[asyncio.Task[None]] = set()
        self._queued: list[_QueuedSubmission] = []
        self._submission_order = 0

    async def submit(self, task: NodeTask) -> asyncio.Future[bytes]:
        """Submit a task for execution, returning a future for the result."""
        if self._shutdown:
            raise RuntimeError("Pool is shut down")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()

        runner_task = asyncio.create_task(self._run_task(task, future))
        self._runner_tasks.add(runner_task)
        runner_task.add_done_callback(self._runner_tasks.discard)
        return future

    async def _run_task(self, task: NodeTask, future: asyncio.Future[bytes]) -> None:
        submission = _QueuedSubmission(
            sort_priority=-int(task.priority),
            submission_order=self._submission_order,
            task=task,
            future=future,
        )
        self._submission_order += 1
        active = False
        try:
            async with self._capacity_changed:
                heapq.heappush(self._queued, submission)
                await self._capacity_changed.wait_for(
                    lambda: future.cancelled() or self._can_start(submission)
                )
                if future.cancelled():
                    self._remove_submission(submission)
                    self._capacity_changed.notify_all()
                    return
                next_submission = heapq.heappop(self._queued)
                if next_submission is not submission:
                    raise RuntimeError("local worker pool queue invariant violated")
                self._active_tasks += 1
                active = True

            try:
                from polisyos.scientist.orchestration.engine.runner._activity_worker import (
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
            except asyncio.CancelledError:
                if not future.done():
                    future.cancel()
                raise
            except _LOCAL_POOL_RUNTIME_ERRORS as exc:
                if not future.done():
                    future.set_exception(exc)
            finally:
                if active:
                    async with self._capacity_changed:
                        self._active_tasks -= 1
                        active = False
                        self._capacity_changed.notify_all()
        except asyncio.CancelledError:
            async with self._capacity_changed:
                self._remove_submission(submission)
                if active:
                    self._active_tasks -= 1
                    active = False
                self._capacity_changed.notify_all()
            if not future.done():
                future.cancel()
            raise
        except _LOCAL_POOL_RUNTIME_ERRORS as exc:
            async with self._capacity_changed:
                self._remove_submission(submission)
                if active:
                    self._active_tasks -= 1
                    active = False
                self._capacity_changed.notify_all()
            if not future.done():
                future.set_exception(exc)

    def _can_start(self, submission: _QueuedSubmission) -> bool:
        return bool(
            self._queued
            and self._queued[0] is submission
            and self._active_tasks < self._max_workers
        )

    def _remove_submission(self, submission: _QueuedSubmission) -> None:
        try:
            self._queued.remove(submission)
        except ValueError:
            return
        heapq.heapify(self._queued)

    async def scale_to(self, workers: int) -> None:
        """Resize the pool's concurrency limit.

        Note: this only affects new task submissions — in-flight tasks
        continue until completion.
        """
        if workers < 1:
            raise ValueError("workers must be >= 1")
        async with self._capacity_changed:
            self._max_workers = workers
            self._capacity_changed.notify_all()

    async def current_capacity(self) -> PoolCapacity:
        """Return a snapshot of the pool's capacity."""
        async with self._capacity_changed:
            return PoolCapacity(
                total_workers=self._max_workers,
                idle_workers=max(0, self._max_workers - self._active_tasks),
                active_tasks=self._active_tasks,
                queue_depth=len(self._queued),
            )

    async def shutdown(self, graceful: bool = True) -> None:
        """Mark the pool as shut down."""
        self._shutdown = True
        if graceful:
            await asyncio.gather(*list(self._runner_tasks), return_exceptions=True)
            return
        for task in list(self._runner_tasks):
            task.cancel()
        await asyncio.gather(*list(self._runner_tasks), return_exceptions=True)
