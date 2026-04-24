"""
Main connector cache store interface.

Provides the ``ConnectorCacheStore`` class -- the primary public API for
caching connector fetch results with TTL-based expiration, policy-driven
eviction, invalidation tracking, and indexed metadata queries.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ArtifactID, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.fabric.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.security import DataClassification, RetentionScope, resolve_artifact_governance
from polisyos.fabric.storage.tenant_cas import infer_tenant_id_from_cas_root

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
    canon_spec_allow_floats,
    dt_to_ts,
    payload_to_request,
    request_to_payload,
    utc_now,
)
from ._store_serialization import ResultSerializer
from .policy import CachePolicy, PolicyRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import TracebackType

    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.fabric.connectors.base import FetchRequest, FetchResult

__all__ = [
    "ConnectorCacheStore",
]

logger = get_logger(__name__)


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


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
        *,
        metrics: MetricsRegistry | None = None,
        tracer: PolicyOSTracer | None = None,
    ) -> None:
        self._cas = cas
        self._policy_registry = (
            policy if isinstance(policy, PolicyRegistry) else PolicyRegistry(default_policy=policy)
        )
        self._namespace = namespace
        self._tenant_id = infer_tenant_id_from_cas_root(cas.root)
        self._cache_root = cas.root / namespace
        self._cache_root.mkdir(parents=True, exist_ok=True)
        self._index = CacheIndex(self._cache_root / "cache_index.sqlite3")

        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._stats_lock = threading.Lock()
        self._metrics = metrics if metrics is not None else _default_metrics()
        self._tracer = tracer if tracer is not None else _default_tracer()
        self._closed = False

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def get(
        self, request: FetchRequest, *, connector_id: str | None = None
    ) -> CachedFetchResult | None:
        self._ensure_open()
        start = time.perf_counter()
        cache_key = request.cache_key
        metric_connector = connector_id
        status = "miss"

        try:
            with self._tracer.start_as_current_span(
                FABRIC_TRACE_NAMES["cache_get"],
                attributes={"cache.operation": "get", "cache.namespace": self._namespace},
            ):
                try:
                    entry = self._index.get_entry(cache_key)
                except Exception as exc:
                    logger.warning("Cache index lookup failed", error=str(exc))
                    status = "error"
                    return None

                if entry is None:
                    return None

                policy = self._policy_registry.get_policy_by_id(entry.policy_id)
                metric_connector = connector_id or entry.connector_id
                if policy is None:
                    status = "stale"
                    return None

                metadata = entry.to_metadata()

                if not policy.is_valid(metadata):
                    status = "stale"
                    return None

                if metadata.is_stale:
                    status = "stale"
                    return None

                if not self._cas.has(metadata.payload_artifact_id):
                    logger.warning("Cache payload missing in CAS", cache_key=cache_key)
                    self._index.delete_entry(cache_key)
                    return None

                try:
                    payload_bytes = self._cas.get_bytes(metadata.payload_artifact_id)
                    result = ResultSerializer.deserialize(payload_bytes)
                except Exception as exc:
                    logger.warning("Cache payload load failed", cache_key=cache_key, error=str(exc))
                    self._index.delete_entry(cache_key)
                    status = "error"
                    return None

                try:
                    self._index.update_access(cache_key)
                except Exception as exc:
                    logger.debug("Ignored exception: %s", exc)

                status = "hit"
                return CachedFetchResult(result=result, metadata=metadata)
        finally:
            latency = time.perf_counter() - start
            self._record_lookup_outcome("get", status, metric_connector, latency)

    def get_any(
        self,
        request: FetchRequest,
        *,
        connector_id: str | None = None,
        max_staleness_seconds: float | None = None,
    ) -> CachedFetchResult | None:
        self._ensure_open()
        """
        Retrieve cached data regardless of freshness, optionally bounded by max staleness.

        This is intended for resilience fallbacks where stale data is acceptable.
        """
        start = time.perf_counter()
        cache_key = request.cache_key
        metric_connector = connector_id
        status = "miss"

        try:
            with self._tracer.start_as_current_span(
                FABRIC_TRACE_NAMES["cache_get"],
                attributes={"cache.operation": "get_any", "cache.namespace": self._namespace},
            ):
                try:
                    entry = self._index.get_entry(cache_key)
                except Exception as exc:
                    logger.warning("Cache index lookup failed", error=str(exc))
                    status = "error"
                    return None

                if entry is None:
                    return None

                metric_connector = connector_id or entry.connector_id
                metadata = entry.to_metadata()

                if max_staleness_seconds is not None:
                    age_seconds = (utc_now() - metadata.cached_at).total_seconds()
                    if age_seconds > max_staleness_seconds:
                        status = "stale"
                        return None

                if not self._cas.has(metadata.payload_artifact_id):
                    logger.warning("Cache payload missing in CAS", cache_key=cache_key)
                    self._index.delete_entry(cache_key)
                    return None

                try:
                    payload_bytes = self._cas.get_bytes(metadata.payload_artifact_id)
                    result = ResultSerializer.deserialize(payload_bytes)
                except Exception as exc:
                    logger.warning("Cache payload load failed", cache_key=cache_key, error=str(exc))
                    self._index.delete_entry(cache_key)
                    status = "error"
                    return None

                try:
                    self._index.update_access(cache_key)
                except Exception as exc:
                    logger.debug("Ignored exception: %s", exc)

                status = "hit"
                return CachedFetchResult(result=result, metadata=metadata)
        finally:
            latency = time.perf_counter() - start
            self._record_lookup_outcome("get_any", status, metric_connector, latency)

    def put(
        self,
        request: FetchRequest,
        result: FetchResult[Any],
        *,
        connector_id: str | None = None,
        schema_hash: str | None = None,
        classification: DataClassification | str | None = None,
        column_classification: Mapping[str, DataClassification | str] | None = None,
        encrypted_at_rest: bool = False,
        field_level_encrypted: bool = False,
        encryption_key_reference: str | None = None,
    ) -> CacheMetadata:
        self._ensure_open()
        start = time.perf_counter()
        cache_key = request.cache_key
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["cache_put"],
            attributes={"cache.operation": "put", "cache.namespace": self._namespace},
        ):
            policy = self._policy_registry.get_policy(request, connector_id=connector_id)
            expires_at = policy.compute_expiry(request, result)

            try:
                payload_bytes, media_type = ResultSerializer.serialize(result)
                governance = resolve_artifact_governance(
                    scope=RetentionScope.CACHE,
                    classification=classification,
                    column_classification=column_classification,
                    encrypted_at_rest=encrypted_at_rest,
                    field_level_encrypted=field_level_encrypted,
                    encryption_key_reference=encryption_key_reference,
                )
                payload_ref = self._cas.put_bytes(
                    payload_bytes,
                    opts=PutOptions(
                        kind=CACHE_PAYLOAD_KIND,
                        media_type=media_type,
                        schema=SchemaInfo(name=CACHE_SCHEMA_NAME, version=CACHE_SCHEMA_VERSION),
                        governance=governance,
                    ),
                )
            except Exception as exc:
                logger.error("Cache payload store failed", error=str(exc))
                self._record_metric("put", "error", connector_id)
                raise

        metadata = CacheMetadata(
            cache_key=cache_key,
            cached_at=utc_now(),
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
                    governance=governance,
                ),
                canon_spec=canon_spec_allow_floats(),
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
            request_payload=request_to_payload(request),
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
        self._ensure_open()
        strategy_value = getattr(strategy, "value", strategy)
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["cache_invalidate"],
            attributes={
                "cache.strategy": str(strategy_value),
                "cache.namespace": self._namespace,
            },
        ):
            cache_keys = self._index.list_by_filters(**filters)
            if not cache_keys:
                return 0

            if strategy_value == "hard_delete":
                for key in cache_keys:
                    self._index.delete_entry(key)
            else:
                for key in cache_keys:
                    self._index.mark_stale(key)

            self._record_metric("invalidate", "success", None)
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
        self._ensure_open()
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
        self._ensure_open()
        total_entries, total_size, oldest_ts = self._index.stats()
        oldest_age_hours = (time.time() - oldest_ts) / 3600.0 if oldest_ts is not None else 0.0
        return CacheStats(
            total_entries=total_entries,
            total_size_bytes=total_size,
            oldest_entry_age_hours=oldest_age_hours,
            hit_rate=self.hit_rate,
            eviction_count=self._eviction_count,
            namespace=self._namespace,
        )

    def list_datasets(self) -> list[str]:
        self._ensure_open()
        return cast("list[str]", self._index.list_datasets())

    def list_dataset_connectors(self) -> list[tuple[str | None, str]]:
        self._ensure_open()
        return cast(
            "list[tuple[str | None, str]]",
            self._index.list_dataset_connectors(),
        )

    def get_latest_metadata(self, dataset_id: str) -> CacheMetadata | None:
        self._ensure_open()
        entry = self._index.get_latest_for_dataset(dataset_id)
        return entry.to_metadata() if entry else None

    def list_expiring_entries(self, window_seconds: float) -> list[CacheMetadata]:
        self._ensure_open()
        threshold_ts = (dt_to_ts(utc_now()) or 0.0) + window_seconds
        entries = self._index.list_expiring(threshold_ts)
        return [entry.to_metadata() for entry in entries]

    def get_metadata(self, cache_key: str) -> CacheMetadata | None:
        self._ensure_open()
        entry = self._index.get_entry(cache_key)
        return entry.to_metadata() if entry else None

    def get_payload_artifact_id(self, cache_key: str) -> ArtifactID | None:
        self._ensure_open()
        entry = self._index.get_entry(cache_key)
        return entry.payload_artifact_id if entry else None

    def get_request(self, cache_key: str) -> FetchRequest | None:
        self._ensure_open()
        entry = self._index.get_entry(cache_key)
        if entry is None:
            return None
        return payload_to_request(entry.request_payload)

    def get_request_payload(self, cache_key: str) -> dict[str, Any] | None:
        self._ensure_open()
        entry = self._index.get_entry(cache_key)
        if entry is None:
            return None
        return dict(entry.request_payload)

    def get_source_signature(self, cache_key: str) -> dict[str, Any] | None:
        payload = self.get_request_payload(cache_key)
        if payload is None:
            return None
        source_signature = payload.get("source_signature")
        if not isinstance(source_signature, dict):
            return None
        return dict(source_signature)

    def pin(self, cache_key: str) -> None:
        self._ensure_open()
        self._index.set_pinned(cache_key, True)

    def unpin(self, cache_key: str) -> None:
        self._ensure_open()
        self._index.set_pinned(cache_key, False)

    def close(self) -> None:
        """Close owned cache resources. Idempotent."""
        if self._closed:
            return
        self._index.close()
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError(f"ConnectorCacheStore is closed: {self._namespace}")

    def __enter__(self) -> ConnectorCacheStore:
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb
        self.close()

    @property
    def hit_rate(self) -> float:
        with self._stats_lock:
            total = self._hit_count + self._miss_count
            hits = self._hit_count
        return hits / total if total > 0 else 0.0

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _record_metric(self, operation: str, status: str, connector_id: str | None) -> None:
        metric = getattr(self._metrics, "connector_cache_operations_total", None)
        if metric is None:
            return
        labels = self._metric_labels(operation=operation, status=status)
        if connector_id:
            labels["connector_id"] = connector_id
        metric.add(1, labels)

    def _record_latency(self, operation: str, seconds: float) -> None:
        metric = getattr(self._metrics, "connector_cache_latency_seconds", None)
        if metric is None:
            return
        metric.record(
            seconds,
            self._metric_labels(operation=operation),
        )

    def _update_cache_gauges(self) -> None:
        hit_rate = self.hit_rate
        entries_metric = getattr(self._metrics, "connector_cache_entries_total", None)
        if entries_metric is not None:
            entries_metric.set(
                float(self._index.total_entries()),
                self._metric_labels(),
            )
        size_metric = getattr(self._metrics, "connector_cache_size_bytes", None)
        if size_metric is not None:
            size_metric.set(
                float(self._index.total_size()),
                self._metric_labels(),
            )
        hit_rate_metric = getattr(self._metrics, "connector_cache_hit_rate", None)
        if hit_rate_metric is not None:
            hit_rate_metric.set(
                float(hit_rate),
                self._metric_labels(),
            )

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
                target_count = max(1, self._index.total_entries())
                reclaim_bytes = 0
                candidates_to_delete = []
                for entry in self._index.list_lru_candidates(target_count):
                    candidates_to_delete.append(entry)
                    reclaim_bytes += entry.payload_size_bytes
                    if total_size - reclaim_bytes <= max_size_bytes:
                        break

                for entry in candidates_to_delete:
                    self._index.delete_entry(entry.cache_key)
                self._record_eviction("size", len(candidates_to_delete))

        self._update_cache_gauges()

    def _record_eviction(self, reason: str, count: int) -> None:
        if count <= 0:
            return
        with self._stats_lock:
            self._eviction_count += count
        metric = getattr(self._metrics, "connector_cache_evictions_total", None)
        if metric is None:
            return
        metric.add(
            count,
            self._metric_labels(reason=reason),
        )

    def _record_lookup_outcome(
        self,
        operation: str,
        status: str,
        connector_id: str | None,
        latency: float,
    ) -> None:
        with self._stats_lock:
            if status == "hit":
                self._hit_count += 1
            elif status in {"miss", "stale"}:
                self._miss_count += 1
        self._record_metric(operation, status, connector_id)
        self._record_latency(operation, latency)
        self._update_cache_gauges()

    def _metric_labels(self, **extra: Any) -> dict[str, Any]:
        labels: dict[str, Any] = {"namespace": self._namespace, **extra}
        if self._tenant_id:
            labels["tenant_id"] = self._tenant_id
        return labels
