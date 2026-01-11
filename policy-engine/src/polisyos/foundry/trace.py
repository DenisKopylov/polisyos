from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List


@dataclass
class TraceEvent:
    phase: str
    event: str
    payload: dict[str, Any]


@dataclass
class TraceSlice:
    events: List[TraceEvent]
