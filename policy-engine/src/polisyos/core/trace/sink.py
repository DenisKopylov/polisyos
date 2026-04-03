"""Public trace sink module API."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .record import TraceRecord


class TraceSink(Protocol):
    """Trace sink public type."""
    def emit(self, rec: TraceRecord) -> None:
        ...


class JsonlTraceSink:
    """Jsonl trace sink public type."""
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, rec: TraceRecord) -> None:
        line = rec.model_dump_json(exclude_none=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")
            f.flush()


class CompositeTraceSink:
    """Fan-out sink writing the same TraceRecord to multiple sinks."""

    def __init__(self, sinks: list[TraceSink]):
        self._sinks = list(sinks)

    def emit(self, rec: TraceRecord) -> None:
        for sink in self._sinks:
            sink.emit(rec)
