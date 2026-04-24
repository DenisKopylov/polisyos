"""Simple in-process background task runner for control-plane operations."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from polisyos.common.async_tools import get_shared_executor
from polisyos.common.logger import get_logger

logger = get_logger(__name__)

TaskState = Literal["pending", "running", "completed", "failed"]

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class TaskRecord:
    """Track in-process task state for local/dev background execution."""

    task_id: str
    run_id: str
    state: TaskState = "pending"
    error: str | None = None


class TaskRunner:
    """Thread-pool-based background task executor.

    Designed for local/dev use.  Production deployments should replace
    with a proper job queue (Celery, etc.).
    """

    def __init__(
        self,
        max_workers: int | None = None,
        *,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._owns_executor = False
        if executor is not None:
            self._executor = executor
        elif max_workers is None:
            self._executor = get_shared_executor()
        else:
            self._executor = ThreadPoolExecutor(
                max_workers=max(max_workers, 1),
                thread_name_prefix="ctrl",
            )
            self._owns_executor = True
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        task_id: str,
        run_id: str,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> TaskRecord:
        """Submit a function to the local thread pool and return its mutable task record."""
        record = TaskRecord(task_id=task_id, run_id=run_id, state="pending")
        with self._lock:
            self._tasks[task_id] = record
        self._executor.submit(self._execute, record, fn, *args, **kwargs)
        return record

    def get(self, task_id: str) -> TaskRecord | None:
        """Return the latest known task record or `None` when `task_id` is unknown."""
        with self._lock:
            return self._tasks.get(task_id)

    # ------------------------------------------------------------------

    def _execute(
        self,
        record: TaskRecord,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        record.state = "running"
        try:
            fn(*args, **kwargs)
            record.state = "completed"
            logger.info("task %s (run %s) completed", record.task_id, record.run_id)
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            record.state = "failed"
            record.error = str(exc)
            logger.exception("task %s (run %s) failed: %s", record.task_id, record.run_id, exc)

    def close(self, *, wait: bool = True, cancel_futures: bool = False) -> None:
        """Shut down the shared thread pool cleanly during runtime teardown."""
        if self._owns_executor:
            self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)


__all__ = ["TaskRecord", "TaskRunner"]
