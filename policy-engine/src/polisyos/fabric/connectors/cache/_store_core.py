"""
Main connector cache store interface.

Provides the ``ConnectorCacheStore`` class -- the primary public API for
caching connector fetch results with TTL-based expiration, policy-driven
eviction, invalidation tracking, and indexed metadata queries.
"""
from __future__ import annotations

import time
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ArtifactID, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors.base import FetchRequest, FetchResult

from ._store_index import CacheIndex
from ._store_models import (
    CACHE_METADATA_KIND,
    CACHE_PAYLOAD_KIND,
    CACHE_SCHEMA_NAME,
    CACHE_SCHEMA_VERSION,
    CachedFetchResult,
    CacheEntry,
    CacheMetadata,
    CacheStats,
    _canon_spec_allow_floats,
    _dt_to_ts,
    _payload_to_request,
    _request_to_payload,
    _utc_now,
)
from ._store_serialization import ResultSerializer
from .policy import CachePolicy, PolicyRegistry

__all__ = [
    "ConnectorCacheStore",
]

logger = get_logger(__name__)


class ConnectorCacheStore:
    """
    Content-addressable cache for connector fetch results.

    Delegates all storage to FileSystemCAS while adding:
    - TTL-based expiration
    - Policy-driven eviction
    - Invalidation tracking
    - Indexed metadata queries
    """

    def __init__(
        self,
        cas: FileSystemCAS,
        policy: CachePolicy | PolicyRegistry,
        namespace: str = "connector_cache",
    ) -> None:
        self._cas = cas
        self._policy_registry = (
            policy if isinstance(policy, PolicyRegistry) else PolicyRegistry(default_policy=policy)
        )
        self._namespace = namespace
        self._cache_root = cas.root / namespace
        self._cache_root.mkdir(parents=True, exist_ok=True)
        self._index = CacheIndex(self._cache_root / "cache_index.sqlite3")

        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._metrics = get_metrics()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def get(self, request: FetchRequest, *, connector_id: str | None = None) -> CachedFetchResult | None:
        start = time.perf_counter()
        cache_key = request.cache_key

        try:
            entry = self._index.get_entry(cache_key)
        except Exception as exc:
            logger.warning("Cache index lookup failed", error=str(exc))
            self._record_metric("get", "error", connector_id)
            return None

        if entry is None:
            self._miss_count += 1
            self._record_metric("get", "miss", connector_id)
            return None

        policy = self._policy_registry.get_policy_by_id(entry.policy_id)
        metric_connector = connector_id or entry.connector_id
        if policy is None:
            self._miss_count += 1
            self._record_metric("get", "miss", metric_connector)
            return None

        metadata = entry.to_metadata()

        if not policy.is_valid(metadata):
            self._miss_count += 1
            self._record_metric("get", "miss", metric_connector)
            return None

        if metadata.is_stale:
            self._miss_count += 1
            self._record_metric("get", "miss", metric_connector)
            return None

        if not self._cas.has(metadata.payload_artifact_id):
            logger.warning("Cache payload missing in CAS", cache_key=cache_key)
            self._index.delete_entry(cache_key)
            self._miss_count += 1
            self._record_metric("get", "miss", metric_connector)
            return None

        try:
            payload_bytes = self._cas.get_bytes(metadata.payload_artifact_id)
            result = ResultSerializer.deserialize(payload_bytes)
        except Exception as exc:
            logger.warning("Cache payload load failed", cache_key=cache_key, error=str(exc))
            self._index.delete_entry(cache_key)
            self._miss_count += 1
            self._record_metric("get", "error", metric_connector)
            return None

        try:
            self._index.update_access(cache_key)
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)

        self._hit_count += 1
        latency = time.perf_counter() - start
        self._record_latency("get", latency)
        self._record_metric("get", "hit", metric_connector)
        self._update_cache_gauges()

        return CachedFetchResult(result=result, metadata=metadata)

    def get_any(
        self,
        request: FetchRequest,
        *,
        connector_id: str | None = None,
        max_staleness_seconds: float | None = None,
    ) -> CachedFetchResult | None:
        """
        Retrieve cached data regardless of freshness, optionally bounded by max staleness.

        This is intended for resilience fallbacks where stale data is acceptable.
        """
        start = time.perf_counter()
        cache_key = request.cache_key

        try:
            entry = self._index.get_entry(cache_key)
        except Exception as exc:
            logger.warning("Cache index lookup failed", error=str(exc))
            self._record_metric("get_any", "error", connector_id)
            return None

        if entry is None:
            self._record_metric("get_any", "miss", connector_id)
            return None

        metadata = entry.to_metadata()

        if max_staleness_seconds is not None:
            age_seconds = (_utc_now() - metadata.cached_at).total_seconds()
            if age_seconds > max_staleness_seconds:
                self._record_metric("get_any", "stale", connector_id)
                return None

        if not self._cas.has(metadata.payload_artifact_id):
            logger.warning("Cache payload missing in CAS", cache_key=cache_key)
            self._index.delete_entry(cache_key)
            self._record_metric("get_any", "miss", connector_id)
            return None

        try:
            payload_bytes = self._cas.get_bytes(metadata.payload_artifact_id)
            result = ResultSerializer.deserialize(payload_bytes)
        except Exception as exc:
            logger.warning("Cache payload load failed", cache_key=cache_key, error=str(exc))
            self._index.delete_entry(cache_key)
            self._record_metric("get_any", "error", connector_id)
            return None

        try:
            self._index.update_access(cache_key)
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)

        latency = time.perf_counter() - start
        self._record_latency("get_any", latency)
        self._record_metric("get_any", "hit", connector_id)

        return CachedFetchResult(result=result, metadata=metadata)

    def put(
        self,
        request: FetchRequest,
        result: FetchResult[Any],
        *,
        connector_id: str | None = None,
        schema_hash: str | None = None,
    ) -> CacheMetadata:
        start = time.perf_counter()
        cache_key = request.cache_key

        policy = self._policy_registry.get_policy(request, connector_id=connector_id)
        expires_at = policy.compute_expiry(request, result)

        try:
            payload_bytes, media_type = ResultSerializer.serialize(result)
            payload_ref = self._cas.put_bytes(
                payload_bytes,
                opts=PutOptions(
                    kind=CACHE_PAYLOAD_KIND,
                    media_type=media_type,
                    schema=SchemaInfo(name=CACHE_SCHEMA_NAME, version=CACHE_SCHEMA_VERSION),
                ),
            )
        except Exception as exc:
            logger.error("Cache payload store failed", error=str(exc))
            self._record_metric("put", "error", connector_id)
            raise

        metadata = CacheMetadata(
            cache_key=cache_key,
            cached_at=_utc_now(),
            expires_at=expires_at,
            policy_id=policy.policy_id,
            connector_id=connector_id,
            dataset_id=request.dataset_id,
            payload_artifact_id=payload_ref.artifact_id,
            metadata_artifact_id=None,
            payload_size_bytes=len(payload_bytes),
            payload_media_type=media_type,
            fetch_duration_ms=result.fetch_duration_ms,
            source_version=result.version,
            schema_hash=schema_hash,
            is_stale=False,
            pinned=False,
            access_count=0,
            last_accessed_at=None,
        )

        metadata_ref = None
        try:
            metadata_ref = self._cas.put_json(
                metadata.model_dump(mode="json"),
                opts=PutOptions(
                    kind=CACHE_METADATA_KIND,
                    media_type="application/json",
                    schema=SchemaInfo(name=CACHE_SCHEMA_NAME, version=CACHE_SCHEMA_VERSION),
                ),
                canon_spec=_canon_spec_allow_floats(),
            )
        except Exception as exc:
            logger.warning("Cache metadata CAS write failed", error=str(exc))

        if metadata_ref is not None:
            metadata = metadata.model_copy(
                update={"metadata_artifact_id": metadata_ref.artifact_id}
            )

        entry = CacheEntry(
            cache_key=cache_key,
            request_key=request.request_key,
            query_key=request.query_key,
            connector_id=connector_id,
            dataset_id=request.dataset_id,
            cached_at=metadata.cached_at,
            expires_at=metadata.expires_at,
            policy_id=metadata.policy_id,
            payload_artifact_id=payload_ref.artifact_id,
            payload_media_type=media_type,
            payload_size_bytes=len(payload_bytes),
            metadata_artifact_id=metadata_ref.artifact_id if metadata_ref else None,
            fetch_duration_ms=result.fetch_duration_ms,
            source_version=result.version,
            schema_hash=schema_hash,
            is_stale=False,
            pinned=False,
            access_count=0,
            last_accessed_at=None,
            date_start=request.date_start,
            date_end=request.date_end,
            as_of=request.as_of,
            request_payload=_request_to_payload(request),
        )

        try:
            self._index.upsert_entry(entry)
        except Exception as exc:
            logger.error("Cache index update failed", error=str(exc))
            self._record_metric("put", "error", connector_id)
            raise

        self._record_metric("put", "success", connector_id)
        latency = time.perf_counter() - start
        self._record_latency("put", latency)
        self._update_cache_gauges()

        self._evict_if_needed(policy)
        return metadata

    def invalidate(self, strategy: str | Any = "soft_mark", **filters: Any) -> int:
        strategy_value = getattr(strategy, "value", strategy)
        cache_keys = self._index.list_by_filters(**filters)
        if not cache_keys:
            return 0

        if strategy_value == "hard_delete":
            for key in cache_keys:
                self._index.delete_entry(key)
        else:
            for key in cache_keys:
                self._index.mark_stale(key)

        self._update_cache_gauges()
        return len(cache_keys)

    def hard_delete(self, **filters: Any) -> int:
        return self.invalidate(strategy="hard_delete", **filters)

    def invalidate_by_schema_hash(
        self,
        *,
        connector_id: str,
        exclude_hash: str,
    ) -> int:
        """
        Mark entries stale when their schema_hash differs from exclude_hash.

        Args:
            connector_id: Connector whose entries are checked.
            exclude_hash: New contract hash that remains valid.

        Returns:
            Number of invalidated entries.
        """
        if not connector_id:
            return 0

        cache_keys = self._index.list_by_filters(connector_id=connector_id)
        if not cache_keys:
            return 0

        invalidated = 0
        for cache_key in cache_keys:
            entry = self._index.get_entry(cache_key)
            if entry is None:
                continue
            if entry.schema_hash != exclude_hash:
                self._index.mark_stale(cache_key)
                invalidated += 1

        if invalidated:
            self._update_cache_gauges()
        return invalidated

    def stats(self) -> CacheStats:
        total_entries, total_size, oldest_ts = self._index.stats()
        if oldest_ts is not None:
            oldest_age_hours = (time.time() - oldest_ts) / 3600.0
        else:
            oldest_age_hours = 0.0
        return CacheStats(
            total_entries=total_entries,
            total_size_bytes=total_size,
            oldest_entry_age_hours=oldest_age_hours,
            hit_rate=self.hit_rate,
            eviction_count=self._eviction_count,
            namespace=self._namespace,
        )

    def list_datasets(self) -> list[str]:
        return self._index.list_datasets()

    def list_dataset_connectors(self) -> list[tuple[str | None, str]]:
        return self._index.list_dataset_connectors()

    def get_latest_metadata(self, dataset_id: str) -> CacheMetadata | None:
        entry = self._index.get_latest_for_dataset(dataset_id)
        return entry.to_metadata() if entry else None

    def list_expiring_entries(self, window_seconds: float) -> list[CacheMetadata]:
        threshold_ts = _dt_to_ts(_utc_now()) + window_seconds
        entries = self._index.list_expiring(threshold_ts)
        return [entry.to_metadata() for entry in entries]

    def get_metadata(self, cache_key: str) -> CacheMetadata | None:
        entry = self._index.get_entry(cache_key)
        return entry.to_metadata() if entry else None

    def get_payload_artifact_id(self, cache_key: str) -> ArtifactID | None:
        entry = self._index.get_entry(cache_key)
        return entry.payload_artifact_id if entry else None

    def get_request(self, cache_key: str) -> FetchRequest | None:
        entry = self._index.get_entry(cache_key)
        if entry is None:
            return None
        return _payload_to_request(entry.request_payload)

    def pin(self, cache_key: str) -> None:
        self._index.set_pinned(cache_key, True)

    def unpin(self, cache_key: str) -> None:
        self._index.set_pinned(cache_key, False)

    @property
    def hit_rate(self) -> float:
        total = self._hit_count + self._miss_count
        return self._hit_count / total if total > 0 else 0.0

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _record_metric(self, operation: str, status: str, connector_id: str | None) -> None:
        if not self._metrics or not getattr(self._metrics, "connector_cache_operations_total", None):
            return
        labels = {"operation": operation, "status": status}
        if connector_id:
            labels["connector_id"] = connector_id
        self._metrics.connector_cache_operations_total.add(1, labels)  # type: ignore[union-attr]

    def _record_latency(self, operation: str, seconds: float) -> None:
        if not self._metrics or not getattr(self._metrics, "connector_cache_latency_seconds", None):
            return
        self._metrics.connector_cache_latency_seconds.record(seconds, {"operation": operation})  # type: ignore[union-attr]

    def _update_cache_gauges(self) -> None:
        if not self._metrics:
            return
        if getattr(self._metrics, "connector_cache_entries_total", None):
            self._metrics.connector_cache_entries_total.set(
                float(self._index.total_entries()), {"namespace": self._namespace}
            )  # type: ignore[union-attr]
        if getattr(self._metrics, "connector_cache_size_bytes", None):
            self._metrics.connector_cache_size_bytes.set(
                float(self._index.total_size()), {"namespace": self._namespace}
            )  # type: ignore[union-attr]
        if getattr(self._metrics, "connector_cache_hit_rate", None):
            self._metrics.connector_cache_hit_rate.set(
                float(self.hit_rate), {"namespace": self._namespace}
            )  # type: ignore[union-attr]

    def _evict_if_needed(self, policy: CachePolicy) -> None:
        # LRU policy enforcement
        max_entries = getattr(policy, "max_entries", None)
        if max_entries is not None:
            total_entries = self._index.total_entries()
            if total_entries > max_entries:
                to_evict = total_entries - max_entries
                candidates = self._index.list_lru_candidates(to_evict)
                for entry in candidates:
                    self._index.delete_entry(entry.cache_key)
                self._record_eviction("lru", len(candidates))

        # Size-bounded policy enforcement
        max_size_bytes = getattr(policy, "max_size_bytes", None)
        if max_size_bytes is not None:
            total_size = self._index.total_size()
            if total_size > max_size_bytes:
                # Evict least recently used until under limit
                while total_size > max_size_bytes:
                    candidates = self._index.list_lru_candidates(1)
                    if not candidates:
                        break
                    for entry in candidates:
                        self._index.delete_entry(entry.cache_key)
                        total_size -= entry.payload_size_bytes
                    self._record_eviction("size", len(candidates))

        self._update_cache_gauges()

    def _record_eviction(self, reason: str, count: int) -> None:
        if count <= 0:
            return
        self._eviction_count += count
        if not self._metrics or not getattr(self._metrics, "connector_cache_evictions_total", None):
            return
        self._metrics.connector_cache_evictions_total.add(
            count, {"reason": reason, "namespace": self._namespace}
        )  # type: ignore[union-attr]
