# Cache (`polisyos.core.cache`)

`core.cache` provides a tiny in-process cache layer with no external dependencies. It exists so
shared infrastructure can keep hot-path lookups fast without pulling in Redis or another service.

## Role in System

- **Depends on:** nothing outside the standard library and the local cache primitives.
- **Used by:** `core.security` and other hot-path helpers that need lightweight memoization.
- **Boundary function:** offers a stable cache contract without committing the project to a distributed cache backend.

## Key Concepts

- **Protocol-first design** - the `Cache[K, V]` protocol lets callers depend on behavior, not a concrete implementation.
- **LRU cache** - bounded least-recently-used storage with stats.
- **TTL cache** - time-based eviction for short-lived lookups.
- **Stats objects** - separate stats models keep observability simple without extra dependencies.

## Public API

- `Cache`
- `LRUCache`
- `LRUCacheStats`
- `TTLCache`
- `TTLCacheStats`

## Current State

- Last updated: 2026-04-03
- The package remains strictly in-process and intentionally small.
- `protocol.py`, `lru.py`, and `ttl.py` are the only implementation modules in the tree.
