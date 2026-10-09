"""Bridge async coroutines into synchronous entrypoints safely."""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import contextvars
import functools
import os
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

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
    source: Literal["runtime_config", "legacy_host_fallback"] = "runtime_config"
    authority: Literal["candidate"] = "candidate"

    def __post_init__(self) -> None:
        """Validate the declared capacity and preserve candidate-only status."""
        if type(self.capacity) is not int or self.capacity < 1:
            raise SharedExecutorConfigurationError("shared_executor_capacity_must_be_positive")
        if type(self.revision) is not str or not self.revision.strip():
            raise SharedExecutorConfigurationError("shared_executor_revision_required")
        object.__setattr__(self, "revision", self.revision.strip())
        if self.source not in {"runtime_config", "legacy_host_fallback"}:
            raise SharedExecutorConfigurationError("shared_executor_source_invalid")
        if self.authority != "candidate":
            raise SharedExecutorConfigurationError("shared_executor_authority_must_be_candidate")


class SharedExecutorReentrancyError(RuntimeError):
    """Reject nested work that requires an already occupied shared worker."""


class _SharedFuture[T](concurrent.futures.Future[T]):
    """Keep job ownership through worker completion and synchronous callbacks."""

    def __init__(self, executor: _SharedExecutor) -> None:
        super().__init__()
        self._executor = executor
        self._worker_future: concurrent.futures.Future[None] | None = None
        self._work_finished = False
        self._callbacks_active = 0
        self._slot_held = True

    def _release_if_finished(self) -> None:
        # The caller holds the admission lock; Future.done() is not capacity.
        if self._slot_held and self._work_finished and not self._callbacks_active:
            self._slot_held = False
            self._executor._outstanding_jobs -= 1

    def _finish_work(self) -> None:
        with self._executor._admission_lock:
            self._work_finished = True
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

    def cancel(self) -> bool:
        """Cancel unstarted work and synchronously revoke its queue entry."""
        cancelled = super().cancel()
        if cancelled:
            with self._condition:
                worker_future = self._worker_future
            if worker_future is not None:
                worker_future.cancel()
        return cancelled

    def add_done_callback(self, fn: Callable[[concurrent.futures.Future[T]], object]) -> None:
        """Preserve Future callback order/thread and mark late callbacks too."""
        executor = self._executor

        def invoke(future: concurrent.futures.Future[T]) -> None:
            with executor._admission_lock:
                if not self._slot_held:
                    self._slot_held = True
                    executor._outstanding_jobs += 1
                self._callbacks_active += 1
            previous = getattr(executor._worker_context, "active", False)
            executor._worker_context.active = True
            try:
                fn(future)
            finally:
                executor._worker_context.active = previous
                with executor._admission_lock:
                    self._callbacks_active -= 1
                    self._release_if_finished()

        super().add_done_callback(invoke)


class _SharedExecutor(concurrent.futures.ThreadPoolExecutor):
    """Own physical workers and callback reservations separately from Future state.

    External callers may queue ordinary work. A worker or callback cannot submit
    nested work when worker capacity is fully reserved or occupied. A completed proxy retains
    its logical reservation until its callable wrapper and synchronous callbacks
    return. Running arbitrary user code is cooperative and cannot be interrupted.
    """

    def __init__(
        self, *, max_workers: int, thread_name_prefix: str = "polisyos-run-coro-sync"
    ) -> None:
        super().__init__(max_workers=max_workers, thread_name_prefix=thread_name_prefix)
        self._admission_lock = threading.Lock()
        self._worker_context = threading.local()
        self._physical_workers = 0
        self._outstanding_jobs = 0
        self._admission_closed = False

    def is_current_worker(self) -> bool:
        """Return whether the current thread is a physical worker of this pool."""
        return bool(getattr(self._worker_context, "physical_worker", False))

    def run_sync[T](self, fn: Callable[..., T], /, *args: object, **kwargs: object) -> T:
        """Run synchronously, inlining physical workers and bounding external callbacks."""
        if self.is_current_worker():
            return fn(*args, **kwargs)

        # Late Future callbacks execute on their registering thread. Let this
        # synchronous bridge queue a bounded worker while preserving the direct
        # submit() reentrancy refusal for arbitrary callback code.
        was_active = getattr(self._worker_context, "active", False)
        if was_active:
            self._worker_context.active = False
        try:
            future = self.submit(fn, *args, **kwargs)
        finally:
            self._worker_context.active = was_active
        return future.result()

    def submit[T](
        self, fn: Callable[..., T], /, *args: object, **kwargs: object
    ) -> concurrent.futures.Future[T]:
        with self._admission_lock:
            if self._admission_closed:
                raise RuntimeError("cannot schedule new futures after shutdown")
            if getattr(self._worker_context, "active", False) and (
                self._outstanding_jobs >= self._max_workers
                or self._physical_workers >= self._max_workers
            ):
                raise SharedExecutorReentrancyError("shared executor worker capacity is reserved")
            self._outstanding_jobs += 1
            future: _SharedFuture[T] = _SharedFuture(self)
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
            previous = getattr(self._worker_context, "active", False)
            previous_physical_worker = getattr(self._worker_context, "physical_worker", False)
            self._worker_context.active = True
            self._worker_context.physical_worker = True
            with self._admission_lock:
                self._physical_workers += 1
            try:
                context.run(invoke)
            finally:
                self._worker_context.active = previous
                self._worker_context.physical_worker = previous_physical_worker
                with self._admission_lock:
                    self._physical_workers -= 1
                future._finish_work()

        try:
            worker_future = super().submit(run)
        except BaseException:
            future._finish_work()
            raise
        future._bind_worker(worker_future)
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """Close admission before base shutdown invokes queued cancel callbacks."""
        with self._admission_lock:
            self._admission_closed = True
        super().shutdown(wait=wait, cancel_futures=cancel_futures)


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
                thread_name_prefix="polisyos-run-coro-sync",
            )
    return _RUN_CORO_SYNC_EXECUTOR


def resolve_shared_executor_profile(
    *, capacity: int | None = None, revision: str | None = None
) -> SharedExecutorProfile:
    """Resolve explicit process capacity or the legacy candidate-only fallback."""
    if capacity is None and revision is None:
        return SharedExecutorProfile(
            capacity=max(4, min(32, os.cpu_count() or 1)),
            revision="legacy-host-derived-v1",
            source="legacy_host_fallback",
        )
    if capacity is None or revision is None:
        raise SharedExecutorConfigurationError(
            "shared_executor_profile_requires_capacity_and_revision"
        )
    return SharedExecutorProfile(capacity=capacity, revision=revision)


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


def get_shared_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Return the callback-owning executor used for sync-over-async bridges."""
    return _get_shared_executor()


def is_current_shared_executor_worker() -> bool:
    """Return whether the current thread is a physical process-executor worker."""
    executor = _RUN_CORO_SYNC_EXECUTOR
    return isinstance(executor, _SharedExecutor) and executor.is_current_worker()


def run_shared_executor_sync[T](func: Callable[..., T], /, *args: object, **kwargs: object) -> T:
    """Run sync work on the process executor, inline only on its physical workers."""
    executor = _get_shared_executor()
    if isinstance(executor, _SharedExecutor):
        return executor.run_sync(func, *args, **kwargs)
    return executor.submit(func, *args, **kwargs).result()


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
    timeout is rejected before admission. Cancellation stops queued work, while
    an already running callable retains its physical worker until it returns.
    """
    if unbounded and timeout_seconds is not None:
        raise ValueError("unbounded cannot be combined with timeout_seconds")
    timeout = None if unbounded else _normalize_timeout(timeout_seconds)
    loop = asyncio.get_running_loop()
    call = functools.partial(func, *args, **kwargs)
    context = contextvars.copy_context()
    future = loop.run_in_executor(_get_shared_executor(), context.run, call)
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except TimeoutError as exc:
        # ``asyncio.TimeoutError`` is the built-in ``TimeoutError`` on the
        # supported Python versions, so this handler also catches a timeout
        # raised by the blocking callable itself. Preserve that inner error
        # when the executor future completed; only rewrite a wait timeout
        # after asyncio cancelled the future.
        if future.done() and not future.cancelled():
            raise
        future.cancel()
        raise TimeoutError(f"Blocking call did not complete within {timeout:.3f}s") from exc
