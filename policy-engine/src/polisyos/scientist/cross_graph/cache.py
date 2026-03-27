"""LRU cache for cross-graph evidence lookups."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any

from polisyos.ir.analytics.cross_graph import EvidenceNeed

from .protocols import GathererResult


class EvidenceCache:
    """Thread-safe LRU cache for evidence gatherer results.

    Avoids redundant lookups when the same need/concept pair appears
    across multiple compilation passes.
    """

    def __init__(self, maxsize: int = 256) -> None:
        self._maxsize = maxsize
        self._cache: OrderedDict[str, GathererResult] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> GathererResult | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def put(self, key: str, result: GathererResult) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = result
            else:
                if len(self._cache) >= self._maxsize:
                    self._cache.popitem(last=False)
                self._cache[key] = result

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    @property
    def hit_rate(self) -> float:
        with self._lock:
            total = self._hits + self._misses
            return self._hits / total if total > 0 else 0.0

    @staticmethod
    def make_key(dimension: str, need: EvidenceNeed, concepts: list[Any]) -> str:
        """Build a deterministic cache key for a gatherer call."""
        payload = {
            "dimension": dimension,
            "need_id": need.need_id,
            "need_type": need.need_type.value if hasattr(need.need_type, "value") else str(need.need_type),
            "concept_ids": sorted(str(getattr(c, "concept_id", c)) for c in concepts),
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
