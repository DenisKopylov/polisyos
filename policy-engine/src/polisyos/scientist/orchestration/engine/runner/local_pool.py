"""Local worker pool with deterministic priority queuing and resize-safe permits."""

from __future__ import annotations

import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from polisyos.scientist.orchestration.engine.runner.worker_pool import (
    NodeTask,
    PoolCapacity,
)

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

_logger = logging.getLogger(__name__)


@dataclass(order=True)
class _QueuedSubmission:
    """Priority-ordered local submission waiting for execution capacity."""

    sort_priority: int
    submission_order: int
    task: NodeTask = field(compare=False)
    future: asyncio.Future[bytes] = field(compare=False)
    parent_context: Any | None = field(compare=False, default=None)
    receipt_payload: dict[str, Any] | None = field(compare=False, default=None)


class LocalWorkerPool:
    """In-process worker pool backed by asyncio tasks.

    Every accepted future reaches a terminal result, exception, or cancelled
    state. Cancelling a running future does not release its worker slot early.
    Implements the WorkerPool protocol.
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
        """Submit a task and return a future for its terminal outcome.

        Worker exceptions are delivered on the returned future. Cancelling that
        future does not stop an already running worker or release its slot early.
        """
        if task.worker_invocation_id is not None or task.worker_dispatch_sha256 is not None:
            raise RuntimeError("worker_task_parent_receipt_context_required")
        return await self._submit(task, parent_context=None, receipt_payload=None)

    async def submit_with_parent_context(
        self,
        task: NodeTask,
        parent_context: ExecutionContext,
    ) -> asyncio.Future[bytes]:
        """Submit a bound task and admit its staged receipt through the live parent run.

        This source-bound local route currently accepts untimed ``NodeTask`` values.
        Timed work must use an execution backend with a supported owned-process
        boundary; the worker pool does not convert cancellation into that proof.
        """
        receipt_payload = _prepare_parent_receipt(task, parent_context)
        return await self._submit(
            task,
            parent_context=parent_context,
            receipt_payload=receipt_payload,
        )

    async def _submit(
        self,
        task: NodeTask,
        *,
        parent_context: Any | None,
        receipt_payload: dict[str, Any] | None,
    ) -> asyncio.Future[bytes]:
        if self._shutdown:
            raise RuntimeError("Pool is shut down")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()

        runner_task = asyncio.create_task(
            self._run_task(
                task,
                future,
                parent_context=parent_context,
                receipt_payload=receipt_payload,
            )
        )
        self._runner_tasks.add(runner_task)
        runner_task.add_done_callback(self._runner_tasks.discard)
        return future

    async def _run_task(
        self,
        task: NodeTask,
        future: asyncio.Future[bytes],
        *,
        parent_context: Any | None,
        receipt_payload: dict[str, Any] | None,
    ) -> None:
        submission = _QueuedSubmission(
            sort_priority=-int(task.priority),
            submission_order=self._submission_order,
            task=task,
            future=future,
            parent_context=parent_context,
            receipt_payload=receipt_payload,
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
                    return
                next_submission = heapq.heappop(self._queued)
                if next_submission is not submission:
                    raise RuntimeError("local worker pool queue invariant violated")
                self._active_tasks += 1
                active = True

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

            if parent_context is not None:
                if receipt_payload is None:
                    raise RuntimeError("worker_task_parent_receipt_dispatch_missing")
                result = await _run_parent_receipt_task(
                    payload,
                    parent_context=parent_context,
                    receipt_payload=receipt_payload,
                )
            elif task.timeout_s is not None:
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
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)
        except BaseException as exc:
            # Preserve host-fatal signals on the runner task while also ensuring
            # that the accepted caller future cannot remain pending forever.
            if not future.done():
                future.set_exception(exc)
            raise
        finally:
            async with self._capacity_changed:
                self._remove_submission(submission)
                if active:
                    self._active_tasks -= 1
                    active = False
                self._capacity_changed.notify_all()

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


def _prepare_parent_receipt(task: NodeTask, parent_context: Any) -> dict[str, Any]:
    """Validate and freeze the exact local worker dispatch against its parent."""
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        deserialize_state,
        serialize_timeout_context,
        worker_dispatch_sha256,
    )

    if type(parent_context) is not ExecutionContext:
        raise ValueError("worker_task_parent_execution_context_unsupported")
    if task.timeout_s is not None:
        raise ValueError("worker_task_parent_receipt_timeout_unsupported")
    if type(task.context_meta) is not dict:
        raise ValueError("worker_task_parent_receipt_context_invalid")
    run = parent_context.run
    if (
        type(run) is not RunContext
        or run._active_lease is None
        or run._closed
        or run._suspended
        or run._trace_path is None
        or run._owner_snapshot_ref is None
    ):
        raise ValueError("worker_task_parent_run_not_active")
    try:
        state = deserialize_state(task.state_bytes)
    except (TypeError, ValueError) as exc:
        raise ValueError("worker_task_parent_receipt_state_invalid") from exc
    if state.run_id != run.run_manifest.run_id:
        raise ValueError("worker_task_parent_run_id_mismatch")
    try:
        expected_context = serialize_timeout_context(
            parent_context,
            expected_run_id=state.run_id,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("worker_task_parent_receipt_context_unsupported") from exc
    if task.context_meta != expected_context:
        raise ValueError("worker_task_parent_receipt_context_mismatch")
    expected_dispatch = worker_dispatch_sha256(
        node_id=task.node_id,
        alias=task.alias,
        params=task.params,
        state_bytes=task.state_bytes,
        trace_carrier=task.trace_carrier,
        timeout_s=task.timeout_s,
        max_retries=0,
        context_meta=task.context_meta,
    )
    if (
        type(task.worker_invocation_id) is not str
        or len(task.worker_invocation_id) != 64
        or any(character not in "0123456789abcdef" for character in task.worker_invocation_id)
        or task.worker_dispatch_sha256 != expected_dispatch
    ):
        raise ValueError("worker_task_parent_dispatch_binding_invalid")
    if type(run._owner_snapshot_ref) is not ArtifactRef:
        raise ValueError("worker_task_parent_owner_snapshot_invalid")
    run._validate_timeout_worker_owner_binding()
    return {
        "invocation_id": task.worker_invocation_id,
        "dispatch_sha256": expected_dispatch,
        "owner_snapshot_ref": run._owner_snapshot_ref,
        "run_id": state.run_id,
    }


async def _run_parent_receipt_task(
    payload: dict[str, Any],
    *,
    parent_context: Any,
    receipt_payload: dict[str, Any],
) -> bytes:
    """Run one staged task and admit its returned events through the parent writer."""
    from polisyos.scientist.orchestration.engine.retry import (
        _admit_worker_execution_receipt,
    )
    from polisyos.scientist.orchestration.engine.runner._activity_worker import (
        run_node_in_worker,
    )
    from polisyos.scientist.orchestration.engine.runner.serialization import serialize_outcome

    payload = {
        **payload,
        "worker_invocation_id": receipt_payload["invocation_id"],
        "worker_dispatch_sha256": receipt_payload["dispatch_sha256"],
    }
    worker_receipt = await run_node_in_worker(payload, parent_receipt=True)
    outcome = _admit_worker_execution_receipt(
        parent_context,
        worker_receipt,
        invocation_id=receipt_payload["invocation_id"],
        expected_dispatch=receipt_payload["dispatch_sha256"],
        owner_snapshot_ref=receipt_payload["owner_snapshot_ref"],
        expected_run_id=receipt_payload["run_id"],
    )
    return serialize_outcome(outcome)
