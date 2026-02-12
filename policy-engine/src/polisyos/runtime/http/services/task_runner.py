"""Simple in-process background task runner for control-plane operations."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

logger = logging.getLogger(__name__)

TaskState = Literal["pending", "running", "completed", "failed"]


@dataclass
class TaskRecord:
    task_id: str
    run_id: str
    state: TaskState = "pending"
    error: str | None = None


class TaskRunner:
    """Thread-pool-based background task executor.

    Designed for local/dev use.  Production deployments should replace
    with a proper job queue (Celery, etc.).
    """

    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ctrl")
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
        record = TaskRecord(task_id=task_id, run_id=run_id, state="pending")
        with self._lock:
            self._tasks[task_id] = record
        self._executor.submit(self._execute, record, fn, *args, **kwargs)
        return record

    def get(self, task_id: str) -> TaskRecord | None:
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
        except Exception as exc:
            record.state = "failed"
            record.error = str(exc)
            logger.exception("task %s (run %s) failed: %s", record.task_id, record.run_id, exc)


__all__ = ["TaskRecord", "TaskRunner"]
