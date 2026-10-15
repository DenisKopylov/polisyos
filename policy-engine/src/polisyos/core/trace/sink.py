"""Public trace sink module API."""

from __future__ import annotations

import os
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from polisyos.common.logger import get_logger

from .record import TraceRecord

logger = get_logger(__name__)


class TraceSink(Protocol):
    """Trace sink public type."""

    def emit(self, rec: TraceRecord) -> None: ...


@runtime_checkable
class BatchTraceSink(TraceSink, Protocol):
    """Trace sink that accepts a serialized batch under one sink-owned lock."""

    def emit_many(self, records: Sequence[TraceRecord]) -> None: ...


class JsonlTraceSink:
    """Jsonl trace sink public type."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, rec: TraceRecord) -> None:
        self.emit_many([rec])

    def emit_many(self, records: Sequence[TraceRecord]) -> None:
        """Append a batch under one sink-owned lock and fsync the file.

        A write or fsync failure can leave a prefix in the file. Callers that
        need crash recovery must bind and reconcile that prefix themselves.
        """
        if not records:
            return
        payload = "".join(f"{record.model_dump_json(exclude_none=True)}\n" for record in records)
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            written = f.write(payload)
            if written != len(payload):
                raise OSError("trace batch append incomplete")
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
