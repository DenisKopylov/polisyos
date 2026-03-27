"""Tests for evidence cache."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.scientist.cross_graph.cache import EvidenceCache
from polisyos.scientist.cross_graph.protocols import GathererResult


def _result(status: str = "ok") -> GathererResult:
    return GathererResult(
        status=status, confidence=0.8, diagnostics=[], provenance_refs=[], metadata={},
    )


class TestEvidenceCache:
    def test_get_miss(self):
        cache = EvidenceCache(maxsize=10)
        assert cache.get("nonexistent") is None

    def test_put_and_get(self):
        cache = EvidenceCache(maxsize=10)
        r = _result("supported")
        cache.put("key1", r)
        assert cache.get("key1") is r

    def test_lru_eviction(self):
        cache = EvidenceCache(maxsize=2)
        cache.put("a", _result("a"))
        cache.put("b", _result("b"))
        cache.put("c", _result("c"))
        assert cache.get("a") is None  # evicted
        assert cache.get("b") is not None
        assert cache.get("c") is not None

    def test_hit_rate(self):
        cache = EvidenceCache(maxsize=10)
        cache.put("k", _result())
        cache.get("k")
        cache.get("miss")
        assert cache.hit_rate == 0.5

    def test_invalidate(self):
        cache = EvidenceCache(maxsize=10)
        cache.put("k", _result())
        cache.invalidate("k")
        assert cache.get("k") is None

    def test_clear(self):
        cache = EvidenceCache(maxsize=10)
        cache.put("a", _result())
        cache.put("b", _result())
        cache.clear()
        assert cache.size == 0

    def test_make_key_deterministic(self):
        need = MagicMock()
        need.need_id = "n1"
        need.need_type.value = "metric"
        k1 = EvidenceCache.make_key("legal", need, [])
        k2 = EvidenceCache.make_key("legal", need, [])
        assert k1 == k2
        assert len(k1) == 16
