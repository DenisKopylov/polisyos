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
    SchemaChangeInvalidationTrigger,
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
from .schema_aware import make_schema_hash_provider
from .store import (
    CachedFetchResult,
    CacheMetadata,
    CacheStats,
    ConnectorCacheStore,
    ResultSerializer,
)

__all__ = [
    "CacheMetadata",
    "CachePolicy",
    "CacheStats",
    "CachedFetchResult",
    "CachingConnectorProxy",
    "ConnectorCacheStore",
    "InvalidationEvent",
    "InvalidationOrchestrator",
    "InvalidationStrategy",
    "InvalidationTrigger",
    "LRUPolicy",
    "PolicyRegistry",
    "PrefetchJob",
    "PrefetchScheduler",
    "ResultSerializer",
    "SchemaChangeInvalidationTrigger",
    "SizeBoundedPolicy",
    "SmartExpiryPolicy",
    "StaticDataPolicy",
    "TTLPolicy",
    "VolatileDataPolicy",
    "make_schema_hash_provider",
]
