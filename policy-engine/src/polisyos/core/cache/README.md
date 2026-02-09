# Core Cache

Unified in-memory cache primitives for core and higher-level modules.

## Public API

- `Cache[K, V]` — protocol for mutable key/value caches
- `LRUCache[K, V]` — thread-safe least-recently-used cache
- `TTLCache[K, V]` — thread-safe time-to-live cache with optional LRU bound

## Design Goals

- Shared cache contract (`Cache`) across modules
- Deterministic eviction semantics
- Low dependency footprint (stdlib only)
- Safe usage from concurrent code paths (internal `RLock`)
