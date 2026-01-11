from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .record import TraceRecord


class TraceSink(Protocol):
    def emit(self, rec: TraceRecord) -> None: ...


class JsonlTraceSink:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, rec: TraceRecord) -> None:
        line = rec.model_dump_json(exclude_none=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")
            f.flush()
