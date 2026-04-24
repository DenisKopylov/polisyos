"""Public trace sink module API."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Protocol

from polisyos.common.logger import get_logger

from .record import TraceRecord

logger = get_logger(__name__)


class TraceSink(Protocol):
    """Trace sink public type."""

    def emit(self, rec: TraceRecord) -> None: ...


class JsonlTraceSink:
    """Jsonl trace sink public type."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, rec: TraceRecord) -> None:
        line = rec.model_dump_json(exclude_none=True)
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())


class CompositeTraceSink:
    """Fan-out sink writing the same TraceRecord to multiple sinks."""

    def __init__(self, sinks: list[TraceSink]) -> None:
        self._sinks = list(sinks)

    def emit(self, rec: TraceRecord) -> None:
        for sink in self._sinks:
            try:
                sink.emit(rec)
            except Exception as exc:
                logger.warning("Trace sink emit failed: %s", exc)
