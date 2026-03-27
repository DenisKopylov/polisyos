"""Evidence compilation budget management."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompilationBudget:
    """Tracks resource consumption during evidence compilation.

    Enforces limits on time, need count, and external queries
    to prevent runaway compilation.
    """

    max_needs: int = 500
    max_wall_time_s: float = 120.0
    max_queries_per_dimension: int = 200

    _needs_processed: int = field(default=0, init=False)
    _start_time: float = field(default=0.0, init=False)
    _queries: dict[str, int] = field(default_factory=dict, init=False)
    _started: bool = field(default=False, init=False)

    def start(self) -> None:
        self._start_time = time.monotonic()
        self._needs_processed = 0
        self._queries.clear()
        self._started = True

    def record_need(self) -> None:
        self._needs_processed += 1

    def record_query(self, dimension: str) -> None:
        self._queries[dimension] = self._queries.get(dimension, 0) + 1

    @property
    def needs_processed(self) -> int:
        return self._needs_processed

    @property
    def elapsed_s(self) -> float:
        if not self._started:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def queries_by_dimension(self) -> dict[str, int]:
        return dict(self._queries)

    def is_needs_exhausted(self) -> bool:
        return self._needs_processed >= self.max_needs

    def is_time_exhausted(self) -> bool:
        if not self._started:
            return False
        return self.elapsed_s >= self.max_wall_time_s

    def is_dimension_exhausted(self, dimension: str) -> bool:
        return self._queries.get(dimension, 0) >= self.max_queries_per_dimension

    def is_any_exhausted(self) -> bool:
        return self.is_needs_exhausted() or self.is_time_exhausted()

    def remaining_needs(self) -> int:
        return max(0, self.max_needs - self._needs_processed)

    def remaining_time_s(self) -> float:
        if not self._started:
            return self.max_wall_time_s
        return max(0.0, self.max_wall_time_s - self.elapsed_s)

    def summary(self) -> dict[str, Any]:
        return {
            "needs_processed": self._needs_processed,
            "max_needs": self.max_needs,
            "elapsed_s": round(self.elapsed_s, 2),
            "max_wall_time_s": self.max_wall_time_s,
            "queries_by_dimension": dict(self._queries),
            "exhausted": self.is_any_exhausted(),
        }
