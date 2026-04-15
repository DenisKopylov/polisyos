"""Append-only audit logging for runtime read paths."""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from polisyos.common.serialization import fast_json_dumps


class RuntimeDataAccessAuditTrail:
    """Persist data-access audit events for compliance review."""

    def __init__(self, *, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: dict[str, Any]) -> None:
        line = fast_json_dumps(entry, sort_keys=False) + "\n"
        with self._lock:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())


__all__ = ["RuntimeDataAccessAuditTrail"]
