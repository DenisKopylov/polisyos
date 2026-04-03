"""Public foundry trace module API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List


@dataclass
class TraceEvent:
    """Trace event data model."""
    phase: str
    event: str
    payload: dict[str, Any]


@dataclass
class TraceSlice:
    """Trace slice public type."""
    events: List[TraceEvent]
