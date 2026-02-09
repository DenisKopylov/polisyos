from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.cache import Cache, LRUCache, TTLCache


@dataclass
class _Clock:
    now: float = 0.0

    def time(self) -> float:
        return self.now

    def advance(self, delta: float) -> None:
        self.now += delta


def test_lru_cache_evicts_oldest_and_tracks_recent_use() -> None:
    cache = LRUCache[str, int](max_size=2)
    cache.set("a", 1)
    cache.set("b", 2)

    assert cache.get("a") == 1

    cache.set("c", 3)

    assert "a" in cache
    assert "b" not in cache
    assert "c" in cache
    assert cache.stats().evictions == 1


def test_lru_cache_prune_and_protocol_support() -> None:
    cache = LRUCache[str, int]()
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    assert isinstance(cache, Cache)
    assert cache.prune(1) == 2
    assert len(cache) == 1
    assert cache.keys() == ["c"]


def test_ttl_cache_expires_entries_by_time() -> None:
    clock = _Clock()
    cache = TTLCache[str, int](ttl_seconds=5.0, time_fn=clock.time)
    cache.set("k", 42)

    assert cache.get("k") == 42
    clock.advance(5.1)
    assert cache.get("k") is None
    assert cache.stats().expirations == 1


def test_ttl_cache_respects_lru_max_size() -> None:
    clock = _Clock()
    cache = TTLCache[str, int](ttl_seconds=60.0, max_size=2, time_fn=clock.time)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1  # touch a
    cache.set("c", 3)  # should evict b

    assert "a" in cache
    assert "b" not in cache
    assert "c" in cache
    assert cache.stats().evictions == 1


def test_ttl_cache_contains_cleans_expired() -> None:
    clock = _Clock()
    cache = TTLCache[str, int](ttl_seconds=1.0, time_fn=clock.time)
    cache.set("x", 1)

    assert "x" in cache
    clock.advance(2.0)
    assert "x" not in cache
    assert len(cache) == 0
