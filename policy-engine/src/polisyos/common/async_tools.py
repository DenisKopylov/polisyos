"""Bridge async coroutines into synchronous entrypoints safely."""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import contextvars
import functools
import os
import threading
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

T = TypeVar("T")

_EXECUTOR_LOCK = threading.Lock()
_RUN_CORO_SYNC_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None
_DEFAULT_TIMEOUT_SECONDS = max(
    0.1,
    float(os.getenv("POLISYOS_RUN_CORO_SYNC_TIMEOUT_SECONDS", "30").strip() or "30"),
)


def _get_shared_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _RUN_CORO_SYNC_EXECUTOR
    if _RUN_CORO_SYNC_EXECUTOR is not None:
        return _RUN_CORO_SYNC_EXECUTOR
    with _EXECUTOR_LOCK:
        if _RUN_CORO_SYNC_EXECUTOR is None:
            max_workers = max(4, min(32, (os.cpu_count() or 1)))
            _RUN_CORO_SYNC_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="polisyos-run-coro-sync",
            )
    return _RUN_CORO_SYNC_EXECUTOR


def shutdown_run_coro_sync_executor() -> None:
    """Shutdown the shared executor used by `run_coro_sync`."""
    global _RUN_CORO_SYNC_EXECUTOR
    with _EXECUTOR_LOCK:
        if _RUN_CORO_SYNC_EXECUTOR is None:
            return
        _RUN_CORO_SYNC_EXECUTOR.shutdown(wait=False, cancel_futures=True)
        _RUN_CORO_SYNC_EXECUTOR = None


atexit.register(shutdown_run_coro_sync_executor)


def get_shared_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Return the shared executor used for sync-over-async bridge operations."""
    return _get_shared_executor()


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
        future = _get_shared_executor().submit(
            _run_coro_in_fresh_loop,
            coro,
            timeout_seconds=timeout,
        )
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
    **kwargs: object,
) -> T:
    """Run a blocking call in the shared executor without stalling the event loop."""
    timeout = _normalize_timeout(timeout_seconds)
    loop = asyncio.get_running_loop()
    call = functools.partial(func, *args, **kwargs)
    context = contextvars.copy_context()
    future = loop.run_in_executor(_get_shared_executor(), context.run, call)
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except TimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"Blocking call did not complete within {timeout:.3f}s") from exc
