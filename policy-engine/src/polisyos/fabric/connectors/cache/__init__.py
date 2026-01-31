"""
Connector caching layer with CAS backend integration.

This module provides a content-addressable caching system for connector
fetch results, ensuring reproducibility and efficiency in data retrieval.
"""
from .invalidation import (
    InvalidationEvent,
    InvalidationOrchestrator,
    InvalidationStrategy,
    InvalidationTrigger,
)
from .policy import (
    CachePolicy,
    LRUPolicy,
    PolicyRegistry,
    SizeBoundedPolicy,
    SmartExpiryPolicy,
    StaticDataPolicy,
    TTLPolicy,
    VolatileDataPolicy,
)
from .prefetch import PrefetchJob, PrefetchScheduler
from .proxy import CachingConnectorProxy
from .store import CacheMetadata, CacheStats, CachedFetchResult, ConnectorCacheStore

__all__ = [
    "ConnectorCacheStore",
    "CachedFetchResult",
    "CacheMetadata",
    "CacheStats",
    "CachePolicy",
    "TTLPolicy",
    "StaticDataPolicy",
    "VolatileDataPolicy",
    "SmartExpiryPolicy",
    "LRUPolicy",
    "SizeBoundedPolicy",
    "PolicyRegistry",
    "InvalidationStrategy",
    "InvalidationEvent",
    "InvalidationTrigger",
    "InvalidationOrchestrator",
    "PrefetchScheduler",
    "PrefetchJob",
    "CachingConnectorProxy",
]
