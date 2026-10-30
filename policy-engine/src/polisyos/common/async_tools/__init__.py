"""Bridge async coroutines into synchronous entrypoints safely."""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import contextvars
import functools
import hashlib
import os
import sys
import threading
import time
import traceback
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from types import CodeType
from typing import TYPE_CHECKING, Literal, cast
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator


class SharedExecutorReentrancyError(RuntimeError):
    """Reject nested work that requires an already occupied shared worker."""


class SharedExecutorBackpressureError(RuntimeError):
    """Reject work when the process-wide FIFO worker queue is full."""

    retryable = True
    code = "shared_executor_queue_full"

    def __init__(self, *, queue_depth: int, queue_capacity: int, capacity: int) -> None:
        super().__init__(self.code)
        self.queue_depth = queue_depth
        self.queue_capacity = queue_capacity
        self.capacity = capacity


class SharedExecutorWaitTimeoutError(TimeoutError):
    """Report a wait timeout without claiming a running callable has stopped."""

    retryable = True

    def __init__(self, *, cancelled_before_start: bool) -> None:
        disposition = (
            "queued shared work was cancelled before start"
            if cancelled_before_start
            else "running shared work retains its physical worker slot"
        )
        super().__init__(disposition)
        self.cancelled_before_start = cancelled_before_start
        self.running_slot_retained = not cancelled_before_start
        self.retryable = cancelled_before_start


@dataclass(frozen=True, slots=True)
class SharedExecutionFailure:
    """Small failure summary that never retains the worker exception or traceback."""

    exception_type: str
    message_excerpt: str = ""
    code: Literal["shared_execution_failed"] = "shared_execution_failed"
    retryable: Literal[False] = False

    def __post_init__(self) -> None:
        """Bound the strings kept by a completed handle."""
        if type(self.exception_type) is not str or type(self.message_excerpt) is not str:
            raise TypeError("shared_execution_failure_fields_must_be_strings")
        object.__setattr__(self, "exception_type", self.exception_type[:160])
        object.__setattr__(self, "message_excerpt", self.message_excerpt[:512])


@dataclass(frozen=True, slots=True)
class SharedExecutionCompletion[T]:
    """Store either the callable result or a bounded, traceback-free failure."""

    status: Literal["completed", "failed"]
    value: T | None = None
    failure: SharedExecutionFailure | None = None

    def __post_init__(self) -> None:
        """Keep completion and failure states mutually exclusive."""
        if self.status == "completed" and self.failure is not None:
            raise ValueError("completed_shared_execution_cannot_contain_failure")
        if self.status == "failed" and (self.failure is None or self.value is not None):
            raise ValueError("failed_shared_execution_requires_only_failure")


def _summarize_shared_execution_failure(exc: BaseException) -> SharedExecutionFailure:
    """Extract only bounded scalar diagnostics from a worker exception."""
    exception_type = type(exc)
    type_name = f"{exception_type.__module__}.{exception_type.__qualname__}"[:160]
    first_arg = exc.args[0] if exc.args else ""
    excerpt = first_arg[:512] if type(first_arg) is str else ""
    return SharedExecutionFailure(exception_type=type_name, message_excerpt=excerpt)


def _capture_shared_execution[T](fn: Callable[[], T]) -> SharedExecutionCompletion[T]:
    """Run one callable and discard traceback frames before storing its failure."""
    try:
        return SharedExecutionCompletion(status="completed", value=fn())
    except BaseException as exc:
        failure = _summarize_shared_execution_failure(exc)
        if exc.__traceback__ is not None:
            traceback.clear_frames(exc.__traceback__)
        exc.__traceback__ = None
        return SharedExecutionCompletion(status="failed", failure=failure)


class SharedExecutionHandle[T]:
    """Cancellable wait handle for shared work with traceback-free completion."""

    def __init__(self, future: concurrent.futures.Future[SharedExecutionCompletion[T]]) -> None:
        self._future = future

    def done(self) -> bool:
        """Return whether worker completion has reached this handle."""
        return self._future.done()

    def cancel(self) -> bool:
        """Cancel queued work; a running callable keeps its slot until return."""
        return self._future.cancel()

    def result(self, timeout: float | None = None) -> SharedExecutionCompletion[T]:
        """Wait for completion and cancel only work that has not started."""
        try:
            return self._future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            if self._future.done():
                return self._future.result()
            cancelled = self.cancel()
            if not cancelled and self._future.done():
                return self._future.result()
            raise SharedExecutorWaitTimeoutError(cancelled_before_start=cancelled) from None

    async def result_async(self, timeout: float | None = None) -> SharedExecutionCompletion[T]:
        """Wait without occupying a shared worker and preserve running slot ownership."""
        wrapped = asyncio.wrap_future(self._future)
        try:
            return await asyncio.wait_for(asyncio.shield(wrapped), timeout=timeout)
        except TimeoutError:
            if self._future.done():
                return self._future.result()
            cancelled = self.cancel()
            if not cancelled and self._future.done():
                return self._future.result()
            raise SharedExecutorWaitTimeoutError(cancelled_before_start=cancelled) from None
        except asyncio.CancelledError:
            self.cancel()
            raise


class _SharedFuture[T](concurrent.futures.Future[T]):
    """Keep a physical job reservation until its worker wrapper returns."""

    def __init__(self, executor: _SharedExecutor) -> None:
        super().__init__()
        self._executor = executor
        self._worker_future: concurrent.futures.Future[None] | None = None
        self._work_finished = False
        self._owner_cleanup_complete = threading.Event()
        self._slot_held = True
        self._work_reserved = False
        self._queued_slot = False

    def _mark_work_reserved(self) -> None:
        """Record the queue and work reservations made at admission."""
        self._work_reserved = True
        self._queued_slot = True

    def _mark_worker_started_locked(self) -> None:
        """Release queue depth when the physical worker begins this job."""
        if self._queued_slot:
            self._queued_slot = False
            self._executor._queued_jobs -= 1

    def _release_if_finished(self) -> None:
        # The caller holds the admission lock; Future.done() is not capacity.
        if self._slot_held and self._work_finished:
            self._slot_held = False
            self._executor._outstanding_jobs -= 1
            self._executor._capacity_changed.notify_all()

    def _finish_work(self) -> None:
        with self._executor._admission_lock:
            self._work_finished = True
            self._mark_worker_started_locked()
            if self._work_reserved:
                self._work_reserved = False
                self._executor._work_jobs -= 1
            self._release_if_finished()

    def _bind_worker(self, future: concurrent.futures.Future[None]) -> None:
        with self._condition:
            self._worker_future = future
        # Immediate completion/cancellation callbacks never run under admission.
        future.add_done_callback(self._worker_finished)
        if self.cancelled():
            future.cancel()

    def _worker_finished(self, future: concurrent.futures.Future[None]) -> None:
        if future.cancelled():
            super().cancel()
            # A removed queue item has no worker to notify wait()/as_completed().
            self.set_running_or_notify_cancel()
            self._finish_work()
            self._owner_cleanup_complete.set()

    def cancel(self) -> bool:
        """Cancel unstarted work while retaining its reservation until dequeued.

        ThreadPoolExecutor leaves cancelled work items in its unbounded internal
        queue. Keeping this owner's bounded reservation until the tombstone is
        dequeued prevents repeated cancel/submit cycles from accumulating hidden
        uncounted queue entries. The worker wrapper observes cancellation before
        invoking the submitted callable.
        """
        return super().cancel()

    def _physical_completion_state(self) -> Literal["pending", "returned", "failed", "not_started"]:
        """Observe actual wrapper exit after its physical slot was released.

        This does not establish downstream effect settlement or authorize a
        durable workflow completion. A caller must retain the exact owner-issued
        future and independently reconcile the actual result and all effects.
        """
        with self._condition:
            worker = self._worker_future
        if worker is None or not self._owner_cleanup_complete.is_set() or not worker.done():
            return "pending"
        if worker.cancelled() or self.cancelled():
            return "not_started"
        if not self.done():
            return "pending"
        if worker.exception() is not None or self.exception() is not None:
            return "failed"
        return "returned"

    def add_done_callback(self, fn: Callable[[concurrent.futures.Future[T]], object]) -> None:
        """Run callback bodies under the shared owner, including late callbacks.

        A callback registered before completion runs inline on the worker that
        completes this Future. A callback registered after completion is
        submitted through the same finite queue and its registering thread
        waits for that bounded owner work. The stored Future callback retains
        only this small wrapper after invocation, not the caller's closure.
        """
        executor = self._executor
        callback: Callable[[concurrent.futures.Future[T]], object] | None = fn

        def invoke(future: concurrent.futures.Future[T]) -> None:
            nonlocal callback
            selected_callback = callback
            callback = None
            if selected_callback is not None:
                executor.run_callback_sync(selected_callback, future)

        super().add_done_callback(invoke)


class _SharedExecutor(concurrent.futures.ThreadPoolExecutor):
    """Own physical workers and a finite queue separately from Future state.

    External callers may queue ordinary work. A worker or callback cannot submit
    nested work when worker capacity is fully reserved or occupied. A completed proxy retains
    its logical reservation until its callable wrapper and any callbacks invoked
    during completion return. Late callbacks are separate bounded owner work.
    Running arbitrary user code is cooperative and cannot be interrupted.
    """

    def __init__(
        self,
        *,
        max_workers: int,
        max_queued: int | None = None,
        thread_name_prefix: str = "polisyos-run-coro-sync",
    ) -> None:
        super().__init__(max_workers=max_workers, thread_name_prefix=thread_name_prefix)
        self._max_queued = max_workers if max_queued is None else max_queued
        self._admission_lock = threading.Lock()
        self._capacity_changed = threading.Condition(self._admission_lock)
        self._submit_lock = threading.Lock()
        # Draining workers and shutdown-time inline callbacks share this guard.
        self._physical_slot_guard = threading.BoundedSemaphore(max_workers)
        self._worker_context = threading.local()
        self._physical_workers = 0
        self._outstanding_jobs = 0
        self._work_jobs = 0
        self._queued_jobs = 0
        self._admission_closed = False

    def is_current_worker(self) -> bool:
        """Return whether the current thread belongs to a pool worker."""
        return bool(getattr(self._worker_context, "physical_worker", False))

    def _is_current_owner_slot(self) -> bool:
        """Return whether this thread currently owns a guarded executor slot."""
        return bool(getattr(self._worker_context, "owner_slot", False))

    def run_sync[T](self, fn: Callable[..., T], /, *args: object, **kwargs: object) -> T:
        """Run synchronously, inlining the current slot owner and bounding callbacks."""
        if self._is_current_owner_slot():
            return fn(*args, **kwargs)

        # External late callbacks use this synchronous bridge to queue the
        # actual callback body on a bounded worker. Preserve direct submit()
        # reentrancy refusal for arbitrary code already running as a callback.
        was_active = getattr(self._worker_context, "active", False)
        if was_active:
            self._worker_context.active = False
        try:
            future = self.submit(fn, *args, **kwargs)
        finally:
            self._worker_context.active = was_active
        return future.result()

    def run_callback_sync[T](
        self,
        fn: Callable[..., T],
        /,
        *args: object,
        **kwargs: object,
    ) -> T:
        """Run callback code on a shared worker, waiting outside the owner for room.

        Ordinary work receives immediate typed backpressure when the finite
        queue is full. Future callbacks have no result channel for that error, so
        a late callback waits on this caller thread until the owner can admit
        the callback. After shutdown closes admission, the completing or
        registration caller may run the callback inline only while holding the
        same physical-slot guard as draining workers.
        """
        if self._is_current_owner_slot():
            return fn(*args, **kwargs)
        while True:
            closed = False
            with self._capacity_changed:
                if self._admission_closed:
                    closed = True
                elif self._outstanding_jobs >= (self._max_workers + self._max_queued):
                    self._capacity_changed.wait()
                    continue
            if closed:
                return self._run_callback_under_slot_guard(fn, *args, **kwargs)
            was_active = getattr(self._worker_context, "active", False)
            if was_active:
                self._worker_context.active = False
            try:
                try:
                    future = self.submit(fn, *args, **kwargs)
                except SharedExecutorBackpressureError:
                    # This exception came from submit(), before the callback
                    # was admitted, so retrying cannot repeat its body.
                    continue
                except RuntimeError:
                    # Shutdown can race the admission check, but only a
                    # submit-time refusal proves the callback never started.
                    with self._admission_lock:
                        closed = self._admission_closed
                    if closed:
                        return self._run_callback_under_slot_guard(fn, *args, **kwargs)
                    raise
            finally:
                self._worker_context.active = was_active
            # Keep result delivery outside the retry handler. The callback body
            # may itself raise either exception caught during admission above.
            return future.result()

    def _run_callback_under_slot_guard[T](
        self,
        fn: Callable[..., T],
        /,
        *args: object,
        **kwargs: object,
    ) -> T:
        """Run a shutdown callback inside a slot shared with draining workers."""
        self._physical_slot_guard.acquire()
        previous_active = getattr(self._worker_context, "active", False)
        previous_physical_worker = getattr(self._worker_context, "physical_worker", False)
        previous_owner_slot = getattr(self._worker_context, "owner_slot", False)
        self._worker_context.active = True
        self._worker_context.owner_slot = True
        try:
            return fn(*args, **kwargs)
        finally:
            self._worker_context.active = previous_active
            self._worker_context.physical_worker = previous_physical_worker
            self._worker_context.owner_slot = previous_owner_slot
            self._physical_slot_guard.release()

    def submit[T](
        self, fn: Callable[..., T], /, *args: object, **kwargs: object
    ) -> concurrent.futures.Future[T]:
        # The admission lock alone does not order ThreadPoolExecutor enqueues:
        # callers could reserve FIFO positions, release it, and submit out of
        # order. Serialize reservation through enqueue so accepted order matches
        # the executor's FIFO queue while workers remain free to start promptly.
        with self._submit_lock:
            with self._admission_lock:
                if self._admission_closed:
                    raise RuntimeError("cannot schedule new futures after shutdown")
                max_admitted = self._max_workers + self._max_queued
                if self._outstanding_jobs >= max_admitted:
                    if getattr(self._worker_context, "active", False):
                        raise SharedExecutorReentrancyError(
                            "shared executor worker capacity is reserved"
                        )
                    raise SharedExecutorBackpressureError(
                        queue_depth=self._queued_jobs,
                        queue_capacity=self._max_queued,
                        capacity=self._max_workers,
                    )
                if getattr(self._worker_context, "active", False) and (
                    self._outstanding_jobs >= self._max_workers
                    or self._physical_workers >= self._max_workers
                ):
                    raise SharedExecutorReentrancyError(
                        "shared executor worker capacity is reserved"
                    )
                self._outstanding_jobs += 1
                self._work_jobs += 1
                self._queued_jobs += 1
                future: _SharedFuture[T] = _SharedFuture(self)
                future._mark_work_reserved()
            context = contextvars.copy_context()

            def invoke() -> None:
                if not future.set_running_or_notify_cancel():
                    return
                try:
                    result = fn(*args, **kwargs)
                except BaseException as exc:
                    future.set_exception(exc)
                else:
                    future.set_result(result)

            def run() -> None:
                slot_acquired = False
                worker_counted = False
                previous = getattr(self._worker_context, "active", False)
                previous_physical_worker = getattr(self._worker_context, "physical_worker", False)
                previous_owner_slot = getattr(self._worker_context, "owner_slot", False)
                try:
                    self._physical_slot_guard.acquire()
                    slot_acquired = True
                    self._worker_context.active = True
                    self._worker_context.physical_worker = True
                    self._worker_context.owner_slot = True
                    with self._admission_lock:
                        future._mark_worker_started_locked()
                        self._physical_workers += 1
                        worker_counted = True
                    context.run(invoke)
                except BaseException as exc:
                    if not future.done():
                        future.set_exception(exc)
                    raise
                finally:
                    self._worker_context.active = previous
                    self._worker_context.physical_worker = previous_physical_worker
                    self._worker_context.owner_slot = previous_owner_slot
                    try:
                        if worker_counted:
                            with self._admission_lock:
                                self._physical_workers -= 1
                        future._finish_work()
                    finally:
                        if slot_acquired:
                            self._physical_slot_guard.release()
                        future._owner_cleanup_complete.set()

            try:
                worker_future = super().submit(run)
            except BaseException:
                future._finish_work()
                raise
            future._bind_worker(worker_future)
            return future

    def submit_cancellable[T](self, fn: Callable[[], T], /) -> SharedExecutionHandle[T]:
        """Submit work with typed cancellation and traceback-free failure storage.

        This generic helper bounds queue admission and failure retention, but its
        callable/result contract does not prove that arguments or results are
        reference-only. Qualified callers must supply their fixed typed worker.
        """

        def capture_completion() -> SharedExecutionCompletion[T]:
            return _capture_shared_execution(fn)

        return SharedExecutionHandle(self.submit(capture_completion))

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """Close admission before base shutdown invokes queued cancel callbacks."""
        with self._admission_lock:
            self._admission_closed = True
            self._capacity_changed.notify_all()
        super().shutdown(wait=wait, cancel_futures=cancel_futures)


_EXECUTOR_LOCK = threading.Lock()
_RUN_CORO_SYNC_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None
_SHARED_EXECUTOR_PROFILE: SharedExecutorProfile | None = None
_SHARED_EXECUTOR_SHUTDOWN = False
_DEFAULT_TIMEOUT_SECONDS = max(
    0.1,
    float(os.getenv("POLISYOS_RUN_CORO_SYNC_TIMEOUT_SECONDS", "30").strip() or "30"),
)


class SharedExecutorConfigurationError(ValueError):
    """Refuse conflicting process-wide shared executor configuration."""


@dataclass(frozen=True, slots=True)
class SharedExecutorProfile:
    """Candidate-only process capacity profile for the canonical shared executor."""

    capacity: int
    revision: str
    queue_capacity: int | None = None
    source: Literal["runtime_config", "legacy_host_fallback"] = "runtime_config"
    authority: Literal["candidate"] = "candidate"

    def __post_init__(self) -> None:
        """Validate the declared capacity and preserve candidate-only status."""
        if type(self.capacity) is not int or self.capacity < 1:
            raise SharedExecutorConfigurationError("shared_executor_capacity_must_be_positive")
        if type(self.revision) is not str or not self.revision.strip():
            raise SharedExecutorConfigurationError("shared_executor_revision_required")
        object.__setattr__(self, "revision", self.revision.strip())
        if self.queue_capacity is None:
            object.__setattr__(self, "queue_capacity", self.capacity)
        elif type(self.queue_capacity) is not int or self.queue_capacity < 0:
            raise SharedExecutorConfigurationError(
                "shared_executor_queue_capacity_must_be_nonnegative_integer"
            )
        if self.source not in {"runtime_config", "legacy_host_fallback"}:
            raise SharedExecutorConfigurationError("shared_executor_source_invalid")
        if self.authority != "candidate":
            raise SharedExecutorConfigurationError("shared_executor_authority_must_be_candidate")


def _get_shared_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _RUN_CORO_SYNC_EXECUTOR, _SHARED_EXECUTOR_PROFILE
    if _SHARED_EXECUTOR_SHUTDOWN:
        raise RuntimeError("shared executor is shut down")
    if _RUN_CORO_SYNC_EXECUTOR is not None:
        return _RUN_CORO_SYNC_EXECUTOR
    with _EXECUTOR_LOCK:
        if _SHARED_EXECUTOR_SHUTDOWN:
            raise RuntimeError("shared executor is shut down")
        if _RUN_CORO_SYNC_EXECUTOR is None:
            if _SHARED_EXECUTOR_PROFILE is None:
                _SHARED_EXECUTOR_PROFILE = resolve_shared_executor_profile()
            _RUN_CORO_SYNC_EXECUTOR = _SharedExecutor(
                max_workers=_SHARED_EXECUTOR_PROFILE.capacity,
                max_queued=_SHARED_EXECUTOR_PROFILE.queue_capacity or 0,
                thread_name_prefix="polisyos-run-coro-sync",
            )
    return _RUN_CORO_SYNC_EXECUTOR


def resolve_shared_executor_profile(
    *,
    capacity: int | None = None,
    revision: str | None = None,
    queue_capacity: int | None = None,
) -> SharedExecutorProfile:
    """Resolve explicit process capacity or the legacy candidate-only fallback."""
    if capacity is None and revision is None:
        return SharedExecutorProfile(
            capacity=max(4, min(32, os.cpu_count() or 1)),
            revision="legacy-host-derived-v1",
            source="legacy_host_fallback",
            queue_capacity=queue_capacity,
        )
    if capacity is None or revision is None:
        raise SharedExecutorConfigurationError(
            "shared_executor_profile_requires_capacity_and_revision"
        )
    return SharedExecutorProfile(
        capacity=capacity,
        revision=revision,
        queue_capacity=queue_capacity,
    )


def configure_shared_executor_profile(profile: SharedExecutorProfile) -> SharedExecutorProfile:
    """Set the one process-wide worker profile, refusing later conflicts."""
    global _SHARED_EXECUTOR_PROFILE
    if type(profile) is not SharedExecutorProfile:
        raise SharedExecutorConfigurationError("shared_executor_profile_must_be_typed")
    with _EXECUTOR_LOCK:
        if _SHARED_EXECUTOR_SHUTDOWN:
            raise SharedExecutorConfigurationError("shared_executor_is_shut_down")
        current = _SHARED_EXECUTOR_PROFILE
        if current is not None and current != profile:
            raise SharedExecutorConfigurationError("shared_executor_profile_conflict")
        if _RUN_CORO_SYNC_EXECUTOR is not None and (
            _RUN_CORO_SYNC_EXECUTOR._max_workers != profile.capacity
            or (
                isinstance(_RUN_CORO_SYNC_EXECUTOR, _SharedExecutor)
                and _RUN_CORO_SYNC_EXECUTOR._max_queued != profile.queue_capacity
            )
        ):
            raise SharedExecutorConfigurationError("shared_executor_capacity_already_in_use")
        _SHARED_EXECUTOR_PROFILE = profile
    return profile


def get_shared_executor_profile() -> SharedExecutorProfile:
    """Return the active profile or an unpinned legacy fallback preview."""
    with _EXECUTOR_LOCK:
        if _SHARED_EXECUTOR_PROFILE is None:
            return resolve_shared_executor_profile()
        return _SHARED_EXECUTOR_PROFILE


def shutdown_run_coro_sync_executor() -> None:
    """Shut down the process executor permanently without reopening capacity."""
    global _SHARED_EXECUTOR_SHUTDOWN
    with _EXECUTOR_LOCK:
        executor = _RUN_CORO_SYNC_EXECUTOR
        _SHARED_EXECUTOR_SHUTDOWN = True
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)


atexit.register(shutdown_run_coro_sync_executor)


def create_dependency_executor(
    *, max_workers: int, max_queued: int, thread_name_prefix: str
) -> concurrent.futures.ThreadPoolExecutor:
    """Create a guard-owned dependency pool with bounded worker and queue capacity."""
    if type(max_workers) is not int or max_workers < 1:
        raise ValueError("dependency_executor_workers_must_be_positive")
    if type(max_queued) is not int or max_queued < 0:
        raise ValueError("dependency_executor_queue_must_be_nonnegative")
    return _SharedExecutor(
        max_workers=max_workers, max_queued=max_queued, thread_name_prefix=thread_name_prefix
    )


def get_shared_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Return the callback-owning executor used for sync-over-async bridges."""
    return _get_shared_executor()


def owns_shared_executor_slot(executor: concurrent.futures.ThreadPoolExecutor) -> bool:
    """Check the actual process executor and its current thread's occupied slot."""
    return (
        type(executor) is _SharedExecutor
        and executor is _RUN_CORO_SYNC_EXECUTOR
        and executor._is_current_owner_slot()
    )


def is_current_shared_executor_worker() -> bool:
    """Return whether the current thread is a physical process-executor worker."""
    executor = _RUN_CORO_SYNC_EXECUTOR
    return isinstance(executor, _SharedExecutor) and executor.is_current_worker()


def run_shared_executor_sync[T](func: Callable[..., T], /, *args: object, **kwargs: object) -> T:
    """Run sync work on the process executor, inline only while owning its slot."""
    executor = _get_shared_executor()
    if isinstance(executor, _SharedExecutor):
        return executor.run_sync(func, *args, **kwargs)
    return executor.submit(func, *args, **kwargs).result()


def submit_shared_executor_cancellable[T](func: Callable[[], T], /) -> SharedExecutionHandle[T]:
    """Submit one cancellable shared task and return a bounded completion handle.

    The helper provides finite FIFO admission and does not retain worker
    exceptions. Callers that need a reference-only memory guarantee must use a
    fixed worker whose descriptor and result types enforce that contract.
    """
    executor = _get_shared_executor()
    if isinstance(executor, _SharedExecutor):
        if executor._is_current_owner_slot():
            completed: concurrent.futures.Future[SharedExecutionCompletion[T]] = (
                concurrent.futures.Future()
            )
            completed.set_result(_capture_shared_execution(func))
            return SharedExecutionHandle(completed)
        return executor.submit_cancellable(func)
    raise SharedExecutorConfigurationError(
        "cancellable_work_requires_the_canonical_bounded_shared_executor"
    )


def _normalize_timeout(timeout_seconds: float | None) -> float:
    timeout = _DEFAULT_TIMEOUT_SECONDS if timeout_seconds is None else float(timeout_seconds)
    if timeout <= 0:
        raise ValueError("timeout_seconds must be > 0")
    return timeout


async def _await_awaitable[T](awaitable: Awaitable[T]) -> T:
    return await awaitable


def _run_coro_in_fresh_loop[T](coro: Awaitable[T], *, timeout_seconds: float) -> T:
    loop = asyncio.new_event_loop()
    task: asyncio.Task[T] | None = None
    try:
        asyncio.set_event_loop(loop)
        task = loop.create_task(_await_awaitable(coro))
        try:
            return loop.run_until_complete(asyncio.wait_for(task, timeout=timeout_seconds))
        except TimeoutError as exc:
            # Preserve inner timeout semantics from the coroutine itself, such as
            # shared-executor blocking-call timeouts raised by `run_blocking_async`.
            if task is not None and task.done() and not task.cancelled():
                raise
            if task is not None and not task.done():
                task.cancel()
                loop.run_until_complete(asyncio.gather(task, return_exceptions=True))
            raise TimeoutError(f"Coroutine did not complete within {timeout_seconds:.3f}s") from exc
    finally:
        pending = [
            pending_task for pending_task in asyncio.all_tasks(loop) if not pending_task.done()
        ]
        for pending_task in pending:
            pending_task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        asyncio.set_event_loop(None)
        loop.close()


def run_coro_sync[T](coro: Awaitable[T], *, timeout_seconds: float | None = None) -> T:
    """Run a coroutine from sync code with bounded timeout and cleanup semantics."""
    timeout = _normalize_timeout(timeout_seconds)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        context = contextvars.copy_context()
        call = functools.partial(
            _run_coro_in_fresh_loop,
            coro,
            timeout_seconds=timeout,
        )
        future = _get_shared_executor().submit(context.run, call)
        try:
            return future.result(timeout=timeout + 1.0)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"Coroutine worker did not stop cleanly within {timeout + 1.0:.3f}s"
            ) from exc

    return _run_coro_in_fresh_loop(coro, timeout_seconds=timeout)


SHARED_EXECUTOR_CALL_EVENT_NAME = "polisyos.common.shared_executor_call"


@dataclass(frozen=True, slots=True)
class _SharedExecutorCallObservation:
    """Live, in-process facts from one actual shared-executor invocation."""

    schema_version: str
    call_id: str
    helper_function: object
    helper_code: CodeType
    caller_module: str
    caller_code: CodeType
    caller_source_path: str
    caller_source_sha256: str
    caller_thread_ident: int
    target_function: object | None
    target_code: CodeType | None
    source_path: str
    source_sha256: str
    executor: object
    profile: SharedExecutorProfile
    worker_thread_ident: int
    worker_is_executor: bool
    trace_id: int
    span_id: int
    status: str


class _SharedExecutorCallCollector:
    """Collect live call objects without turning them into self-attested JSON."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._observations: list[_SharedExecutorCallObservation] = []

    def append(self, observation: _SharedExecutorCallObservation) -> None:
        with self._lock:
            self._observations.append(observation)

    def snapshot(self) -> tuple[_SharedExecutorCallObservation, ...]:
        with self._lock:
            return tuple(self._observations)


_SHARED_EXECUTOR_OBSERVATION_COLLECTOR: contextvars.ContextVar[
    _SharedExecutorCallCollector | None
] = contextvars.ContextVar("shared_executor_call_collector", default=None)


@contextmanager
def capture_shared_executor_observations() -> Iterator[_SharedExecutorCallCollector]:
    """Capture actual Common helper calls for one bounded controlled witness."""
    collector = _SharedExecutorCallCollector()
    token = _SHARED_EXECUTOR_OBSERVATION_COLLECTOR.set(collector)
    try:
        yield collector
    finally:
        _SHARED_EXECUTOR_OBSERVATION_COLLECTOR.reset(token)


def _observed_target_function(func: object) -> object | None:
    target = func
    while isinstance(target, functools.partial):
        target = target.func
    target_function = getattr(target, "__func__", target)
    return (
        target_function
        if isinstance(getattr(target_function, "__code__", None), CodeType)
        else None
    )


@dataclass(slots=True)
class _BlockingCallReceipt[T]:
    """Capture callable completion before its Future reaches the event loop."""

    value: T | None = None
    error: BaseException | None = None
    completed_at: float | None = None
    completed: threading.Event = field(default_factory=threading.Event)

    def result(self) -> T:
        """Return the callable result or re-raise its original exception."""
        if self.error is not None:
            raise self.error
        return cast("T", self.value)


async def run_blocking_async[T](
    func: Callable[..., T],
    /,
    *args: object,
    timeout_seconds: float | None = None,
    unbounded: bool = False,
    **kwargs: object,
) -> T:
    """Run a blocking call without stalling the loop.

    Omitted/None timeouts retain the helper default. An owner with no configured
    deadline must explicitly pass ``unbounded=True``; combining it with a float
    timeout is rejected before admission. Timely callable completion is kept even
    if its Future reaches the event loop late. Cancellation stops queued work,
    while an already running callable retains its physical worker until it returns.
    This helper deadline does not extend the owner's separate commit deadline.
    """
    if unbounded and timeout_seconds is not None:
        raise ValueError("unbounded cannot be combined with timeout_seconds")
    timeout = None if unbounded else _normalize_timeout(timeout_seconds)
    loop = asyncio.get_running_loop()
    call = functools.partial(func, *args, **kwargs)
    context = contextvars.copy_context()
    receipt: _BlockingCallReceipt[T] = _BlockingCallReceipt()
    collector = _SHARED_EXECUTOR_OBSERVATION_COLLECTOR.get()
    executor = _get_shared_executor()
    caller_module = ""
    caller_code: CodeType | None = None
    caller_source_path = ""
    caller_source_sha256 = ""
    caller_thread_ident: int | None = None
    profile: SharedExecutorProfile | None = None
    current_span = None
    trace_id = span_id = 0
    source_path = ""
    source_sha256 = ""
    helper_function = None
    helper_code = None
    target_function = None
    target_code = None
    if collector is not None:
        caller = sys._getframe(1)
        caller_module = str(caller.f_globals.get("__name__", ""))
        caller_code = caller.f_code
        caller_source_path = str(Path(caller_code.co_filename).resolve())
        caller_source_sha256 = hashlib.sha256(Path(caller_source_path).read_bytes()).hexdigest()
        caller_thread_ident = threading.get_ident()
        profile = get_shared_executor_profile()
        try:
            from opentelemetry import trace

            current_span = trace.get_current_span()
            span_context = current_span.get_span_context()
            if span_context.is_valid:
                trace_id = span_context.trace_id
                span_id = span_context.span_id
            else:
                current_span = None
        except ImportError:
            current_span = None
        source_path = str(Path(__file__).resolve())
        source_sha256 = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
        helper_function = globals().get("_RUN_BLOCKING_ASYNC_FUNCTION")
        helper_code = getattr(helper_function, "__code__", None)
        target_function = _observed_target_function(func)
        target_code = getattr(target_function, "__code__", None)

    def invoke() -> _BlockingCallReceipt[T]:
        status = "success"
        worker_thread_ident: int | None = None
        worker_is_executor = False
        if collector is not None:
            worker_thread_ident = threading.get_ident()
            worker_is_executor = is_current_shared_executor_worker()
        try:
            receipt.value = context.run(call)
        except BaseException as exc:
            status = "error"
            receipt.error = exc
        finally:
            receipt.completed_at = time.monotonic()
            receipt.completed.set()
            if (
                collector is not None
                and helper_function is not None
                and isinstance(helper_code, CodeType)
                and isinstance(profile, SharedExecutorProfile)
                and isinstance(caller_code, CodeType)
                and isinstance(caller_thread_ident, int)
                and isinstance(worker_thread_ident, int)
            ):
                observation = _SharedExecutorCallObservation(
                    schema_version="1.0",
                    call_id=uuid4().hex,
                    helper_function=helper_function,
                    helper_code=helper_code,
                    caller_module=caller_module,
                    caller_code=caller_code,
                    caller_source_path=caller_source_path,
                    caller_source_sha256=caller_source_sha256,
                    caller_thread_ident=caller_thread_ident,
                    target_function=target_function,
                    target_code=target_code,
                    source_path=source_path,
                    source_sha256=source_sha256,
                    executor=executor,
                    profile=profile,
                    worker_thread_ident=worker_thread_ident,
                    worker_is_executor=worker_is_executor,
                    trace_id=trace_id,
                    span_id=span_id,
                    status=status,
                )
                collector.append(observation)
                if current_span is not None and current_span.is_recording():
                    # A missing event makes the controlled trace join fail closed.
                    with suppress(Exception):
                        current_span.add_event(
                            SHARED_EXECUTOR_CALL_EVENT_NAME,
                            {
                                "call_id": observation.call_id,
                                "helper_module": str(getattr(helper_function, "__module__", "")),
                                "helper_code_object_id": hex(id(observation.helper_code)),
                                "helper_source_sha256": observation.source_sha256,
                                "caller_module": observation.caller_module,
                                "caller_code_object_id": hex(id(observation.caller_code)),
                                "caller_source_sha256": observation.caller_source_sha256,
                                "profile_revision": observation.profile.revision,
                                "profile_capacity": observation.profile.capacity,
                                "profile_queue_capacity": observation.profile.queue_capacity,
                                "executor_capacity": getattr(executor, "_max_workers", None),
                                "executor_queue_capacity": getattr(executor, "_max_queued", None),
                                "worker_thread_ident": worker_thread_ident,
                                "worker_is_executor": worker_is_executor,
                                "status": status,
                            },
                        )
        return receipt

    worker_future = executor.submit(invoke)
    future = asyncio.wrap_future(worker_future, loop=loop)
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        completed_receipt = await asyncio.wait_for(future, timeout=timeout)
    except TimeoutError as exc:
        # Future delivery may miss the wait even when the callable finished in time.
        if (
            receipt.completed.is_set()
            and receipt.completed_at is not None
            and (deadline is None or receipt.completed_at <= deadline)
        ):
            return receipt.result()
        worker_future.cancel()
        raise TimeoutError(f"Blocking call did not complete within {timeout:.3f}s") from exc
    except asyncio.CancelledError:
        worker_future.cancel()
        raise

    if receipt.completed_at is None or (deadline is not None and receipt.completed_at > deadline):
        future.cancel()
        worker_future.cancel()
        raise TimeoutError(f"Blocking call did not complete within {timeout:.3f}s")
    return completed_receipt.result()


# Preserve the import-time implementation object for live identity checks.
_RUN_BLOCKING_ASYNC_FUNCTION = run_blocking_async
