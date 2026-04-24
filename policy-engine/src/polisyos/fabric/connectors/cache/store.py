"""
Connector cache store with CAS backend delegation.

This module implements the primary caching interface for connector fetch results,
delegating all storage operations to FileSystemCAS while adding:
- TTL-based expiration via policy
- Index-backed metadata lookup (SQLite)
- Soft/hard invalidation
- Optional pinning hooks for reproducibility

Design notes:
- Payload and metadata are stored as CAS artifacts.
- The cache index maps request cache_key -> payload artifact + metadata snapshot.
- Cache entries are accelerators; pinned artifacts are retained independently.

Implementation is split across private sub-modules for maintainability:
- ``_store_models``         -- data models and helper utilities
- ``_store_serialization``  -- FetchResult serialization / deserialization
- ``_store_index``          -- SQLite-backed metadata index
- ``_store_core``           -- main ConnectorCacheStore class
"""

from ._store_core import ConnectorCacheStore
from ._store_index import CacheIndex
from ._store_models import (
    CACHE_METADATA_KIND,
    CACHE_PAYLOAD_KIND,
    CACHE_SCHEMA_NAME,
    CACHE_SCHEMA_VERSION,
    INDEX_SCHEMA_VERSION,
    CachedFetchResult,
    CacheEntry,
    CacheMetadata,
    CacheStats,
)
from ._store_serialization import ResultSerializer

__all__ = [
    "CACHE_METADATA_KIND",
    "CACHE_PAYLOAD_KIND",
    "CACHE_SCHEMA_NAME",
    "CACHE_SCHEMA_VERSION",
    "INDEX_SCHEMA_VERSION",
    "CacheEntry",
    "CacheIndex",
    "CacheMetadata",
    "CacheStats",
    "CachedFetchResult",
    "ConnectorCacheStore",
    "ResultSerializer",
]
