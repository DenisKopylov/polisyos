"""
Main connector cache store interface.

Provides the ``ConnectorCacheStore`` class -- the primary public API for
caching connector fetch results with TTL-based expiration, policy-driven
eviction, invalidation tracking, and indexed metadata queries.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import TYPE_CHECKING, Any, TypeVar

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    PutOptions,
    RootedArtifactStore,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.fabric._adapters.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.security import (
    DataClassification,
    RetentionScope,
    resolve_artifact_governance,
)

from ._store_index import CacheIndex
from ._store_models import (
    _SOURCE_INTENT_CONTRACT,
    _SOURCE_INTENT_KIND,
    _SOURCE_INTENT_ROLE,
    _SOURCE_INTENT_SCHEMA,
    _SOURCE_INTENT_VERSION,
    CACHE_METADATA_KIND,
    CACHE_PAYLOAD_KIND,
    CACHE_SCHEMA_NAME,
    CACHE_SCHEMA_VERSION,
    CachedFetchResult,
    CacheEntry,
    CacheMetadata,
    CacheSourceIntent,
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
    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        FetchRequest,
        FetchResult,
    )

__all__ = [
    "ConnectorCacheStore",
    "verify_selected_cache_payload_ref",
]

logger = get_logger(__name__)

_SELECTED_CACHE_KEY_PREFIX = "fabric.connector_cache.selected-source.v1:"
ResultDataT = TypeVar("ResultDataT")


def verify_selected_cache_payload_ref(
    cas_store: RootedArtifactStore,
    payload_ref: ArtifactRef,
    *,
    connector_id: str,
    request: FetchRequest,
    source_config: ConnectionConfig,
    result: FetchResult[ResultDataT] | None = None,
) -> bool:
    """Verify that an exact CAS payload ref carries the selected source intent.

    The cache index is an accelerator and may be stale or corrupted. A selected
    cache hit is admitted only when the payload manifest carries one exact
    source-intent edge whose immutable CAS content matches the current request
    and effective connection configuration. When ``result`` is supplied, its
    serialized bytes must also equal the bytes addressed by ``payload_ref``.
    """
    try:
        if (
            not connector_id
            or payload_ref.kind != CACHE_PAYLOAD_KIND
            or payload_ref.manifest_profile_sha256 is None
            or not cas_store.verify(payload_ref).ok
        ):
            return False

        payload_manifest = cas_store.get_manifest(payload_ref)
        payload_schema = payload_manifest.artifact_schema
        if (
            payload_manifest.artifact_id != payload_ref.artifact_id
            or payload_manifest.kind != CACHE_PAYLOAD_KIND
            or payload_manifest.media_type != payload_ref.media_type
            or payload_schema is None
            or payload_schema.name != CACHE_SCHEMA_NAME
            or payload_schema.version != CACHE_SCHEMA_VERSION
        ):
            return False

        intent_edges = [
            edge for edge in payload_manifest.inputs if edge.role == _SOURCE_INTENT_ROLE
        ]
        if len(intent_edges) != 1:
            return False
        intent_edge = intent_edges[0]
        if intent_edge.manifest_profile_sha256 is None:
            return False

        intent_ref = ArtifactRef(
            artifact_id=intent_edge.artifact_id,
            kind=_SOURCE_INTENT_KIND,
            media_type="application/json",
            manifest_profile_sha256=intent_edge.manifest_profile_sha256,
        )
        if not cas_store.verify(intent_ref).ok:
            return False
        intent_manifest = cas_store.get_manifest(intent_ref)
        intent_schema = intent_manifest.artifact_schema
        if (
            intent_manifest.artifact_id != intent_ref.artifact_id
            or intent_manifest.kind != _SOURCE_INTENT_KIND
            or intent_manifest.media_type != intent_ref.media_type
            or intent_schema is None
            or intent_schema.name != _SOURCE_INTENT_SCHEMA
            or intent_schema.version != _SOURCE_INTENT_VERSION
        ):
            return False
        intent = CacheSourceIntent.model_validate_json(cas_store.get_bytes(intent_ref))
        if (
            intent.contract != _SOURCE_INTENT_CONTRACT
            or intent.connector_id != connector_id
            or intent.dataset_id != request.dataset_id
            or intent.request_key != request.request_key
            or intent.source_scope_fingerprint != source_config.cache_scope_fingerprint
        ):
            return False

        if result is not None:
            result_bytes, media_type = ResultSerializer.serialize(result)
            if (
                payload_ref.media_type != media_type
                or cas_store.get_bytes(payload_ref) != result_bytes
            ):
                return False
        return True
    except Exception:
        return False


def _cache_key_for_request(
    request: FetchRequest,
    connector_id: str | None,
    source_config: ConnectionConfig | None,
) -> str:
    """Build a versioned key for selected source calls; preserve direct legacy API keys."""
    if source_config is None:
        return request.cache_key
    if not connector_id:
        raise ValueError("selected_source_cache_requires_connector_id")
    material = json.dumps(
        {
            "connector_id": connector_id,
            "request_key": request.cache_key,
            "source_scope_fingerprint": source_config.cache_scope_fingerprint,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{_SELECTED_CACHE_KEY_PREFIX}{digest}"


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


class ConnectorCacheStore:
    """
    Content-addressable cache for connector fetch results.

    Delegates all artifact storage to the supplied rooted store while adding:
    - TTL-based expiration
    - Policy-driven eviction
    - Invalidation tracking
    - Indexed metadata queries
    """

    def __init__(
        self,
        cas: RootedArtifactStore,
        policy: CachePolicy | PolicyRegistry,
        namespace: str = "connector_cache",
        *,
        tenant_id: str | None = None,
        metrics: MetricsRegistry | None = None,
        tracer: PolicyOSTracer | None = None,
    ) -> None:
        self._cas = cas
        self._policy_registry = (
            policy if isinstance(policy, PolicyRegistry) else PolicyRegistry(default_policy=policy)
        )
        self._namespace = namespace
        if tenant_id is None:
            from polisyos.core.security import get_current_tenant_id_or_none

            tenant_id = get_current_tenant_id_or_none()
        self._tenant_id = tenant_id
        self._cache_root = cas.root / namespace
        self._cache_root.mkdir(parents=True, exist_ok=True)
        self._index = CacheIndex(self._cache_root / "cache_index.sqlite3")

        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._stats_lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._eviction_lock = threading.RLock()
        self._metrics = metrics if metrics is not None else _default_metrics()
        self._tracer = tracer if tracer is not None else _default_tracer()
        self._closed = False

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def get(
        self,
        request: FetchRequest,
        *,
        connector_id: str | None = None,
        require_selected_profile: bool = False,
        source_config: ConnectionConfig | None = None,
    ) -> CachedFetchResult | None:
        self._ensure_open()
        start = time.perf_counter()
        cache_key = _cache_key_for_request(request, connector_id, source_config)
        require_selected_profile = require_selected_profile or source_config is not None
        metric_connector = connector_id
        status = "miss"

        try:
            with self._tracer.start_as_current_span(
                FABRIC_TRACE_NAMES["cache_get"],
                attributes={
                    "cache.operation": "get",
                    "cache.namespace": self._namespace,
                },
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
                if source_config is not None and (
                    metadata.request_key != request.request_key
                    or metadata.source_scope_fingerprint != source_config.cache_scope_fingerprint
                    or metadata.connector_id != connector_id
                    or metadata.dataset_id != request.dataset_id
                ):
                    self._index.delete_entry(cache_key)
                    status = "miss"
                    return None

                if not policy.is_valid(metadata):
                    status = "stale"
                    return None

                if metadata.is_stale:
                    status = "stale"
                    return None

                if (
                    require_selected_profile
                    and metadata.payload_ref.manifest_profile_sha256 is None
                ):
                    self._index.delete_entry(cache_key)
                    status = "miss"
                    return None

                try:
                    if metadata.payload_ref.manifest_profile_sha256 is not None:
                        verification = self._cas.verify(metadata.payload_ref)
                        if not verification.ok:
                            self._index.delete_entry(cache_key)
                            status = "miss"
                            return None
                    if not self._cas.has(metadata.payload_ref):
                        logger.warning("Cache payload missing in CAS", cache_key=cache_key)
                        self._index.delete_entry(cache_key)
                        return None
                    payload_bytes = self._cas.get_bytes(metadata.payload_ref)
                    result = ResultSerializer.deserialize(payload_bytes)
                    if source_config is not None and not verify_selected_cache_payload_ref(
                        self._cas,
                        metadata.payload_ref,
                        connector_id=connector_id or "",
                        request=request,
                        source_config=source_config,
                        result=result,
                    ):
                        self._index.delete_entry(cache_key)
                        status = "miss"
                        return None
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
        source_config: ConnectionConfig | None = None,
    ) -> CachedFetchResult | None:
        self._ensure_open()
        """
        Retrieve cached data regardless of freshness, optionally bounded by max staleness.

        This is intended for resilience fallbacks where stale data is acceptable.
        """
        start = time.perf_counter()
        cache_key = _cache_key_for_request(request, connector_id, source_config)
        metric_connector = connector_id
        status = "miss"

        try:
            with self._tracer.start_as_current_span(
                FABRIC_TRACE_NAMES["cache_get"],
                attributes={
                    "cache.operation": "get_any",
                    "cache.namespace": self._namespace,
                },
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
                if source_config is not None and (
                    metadata.request_key != request.request_key
                    or metadata.source_scope_fingerprint != source_config.cache_scope_fingerprint
                    or metadata.connector_id != connector_id
                    or metadata.dataset_id != request.dataset_id
                ):
                    self._index.delete_entry(cache_key)
                    status = "miss"
                    return None

                if max_staleness_seconds is not None:
                    age_seconds = (utc_now() - metadata.cached_at).total_seconds()
                    if age_seconds > max_staleness_seconds:
                        status = "stale"
                        return None

                if (
                    source_config is not None
                    and metadata.payload_ref.manifest_profile_sha256 is None
                ):
                    self._index.delete_entry(cache_key)
                    status = "miss"
                    return None

                try:
                    if metadata.payload_ref.manifest_profile_sha256 is not None:
                        verification = self._cas.verify(metadata.payload_ref)
                        if not verification.ok:
                            self._index.delete_entry(cache_key)
                            status = "miss"
                            return None
                    if not self._cas.has(metadata.payload_ref):
                        logger.warning("Cache payload missing in CAS", cache_key=cache_key)
                        self._index.delete_entry(cache_key)
                        return None
                    payload_bytes = self._cas.get_bytes(metadata.payload_ref)
                    result = ResultSerializer.deserialize(payload_bytes)
                    if source_config is not None and not verify_selected_cache_payload_ref(
                        self._cas,
                        metadata.payload_ref,
                        connector_id=connector_id or "",
                        request=request,
                        source_config=source_config,
                        result=result,
                    ):
                        self._index.delete_entry(cache_key)
                        status = "miss"
                        return None
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
        source_config: ConnectionConfig | None = None,
        schema_hash: str | None = None,
        classification: DataClassification | str | None = None,
        column_classification: Mapping[str, DataClassification | str] | None = None,
        encrypted_at_rest: bool = False,
        field_level_encrypted: bool = False,
        encryption_key_reference: str | None = None,
    ) -> CacheMetadata:
        self._ensure_open()
        start = time.perf_counter()
        cache_key = _cache_key_for_request(request, connector_id, source_config)
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
                source_intent_ref = None
                if source_config is not None:
                    if not connector_id:
                        raise ValueError("selected_source_cache_requires_connector_id")
                    source_intent = CacheSourceIntent(
                        contract=_SOURCE_INTENT_CONTRACT,
                        connector_id=connector_id,
                        dataset_id=request.dataset_id,
                        request_key=request.request_key,
                        source_scope_fingerprint=source_config.cache_scope_fingerprint,
                    )
                    source_intent_ref = self._cas.put_json(
                        source_intent.model_dump(mode="json"),
                        opts=PutOptions(
                            kind=_SOURCE_INTENT_KIND,
                            media_type="application/json",
                            schema=SchemaInfo(
                                name=_SOURCE_INTENT_SCHEMA,
                                version=_SOURCE_INTENT_VERSION,
                            ),
                            governance=governance,
                        ),
                        return_selected_profile=True,
                    )
                payload_ref = self._cas.put_bytes(
                    payload_bytes,
                    opts=PutOptions(
                        kind=CACHE_PAYLOAD_KIND,
                        media_type=media_type,
                        schema=SchemaInfo(name=CACHE_SCHEMA_NAME, version=CACHE_SCHEMA_VERSION),
                        inputs=(
                            [
                                input_ref_from_artifact_ref(
                                    source_intent_ref, role=_SOURCE_INTENT_ROLE
                                )
                            ]
                            if source_intent_ref is not None
                            else None
                        ),
                        governance=governance,
                    ),
                    return_selected_profile=True,
                )
                if payload_ref.manifest_profile_sha256 is None:
                    raise ValueError("connector_cache_payload_profile_unavailable")
            except Exception as exc:
                logger.error("Cache payload store failed", error=str(exc))
                self._record_metric("put", "error", connector_id)
                raise

        metadata = CacheMetadata(
            cache_key=cache_key,
            request_key=request.request_key,
            source_scope_fingerprint=(
                source_config.cache_scope_fingerprint if source_config is not None else None
            ),
            cached_at=utc_now(),
            expires_at=expires_at,
            policy_id=policy.policy_id,
            connector_id=connector_id,
            dataset_id=request.dataset_id,
            payload_artifact_id=payload_ref.artifact_id,
            metadata_artifact_id=None,
            payload_size_bytes=len(payload_bytes),
            payload_media_type=media_type,
            payload_manifest_profile_sha256=payload_ref.manifest_profile_sha256,
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
            source_scope_fingerprint=(
                source_config.cache_scope_fingerprint if source_config is not None else None
            ),
            query_key=request.query_key,
            connector_id=connector_id,
            dataset_id=request.dataset_id,
            cached_at=metadata.cached_at,
            expires_at=metadata.expires_at,
            policy_id=metadata.policy_id,
            payload_artifact_id=payload_ref.artifact_id,
            payload_media_type=media_type,
            payload_manifest_profile_sha256=payload_ref.manifest_profile_sha256,
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

    def put_derived_payload(
        self,
        result: FetchResult[Any],
        *,
        input_payload_ref: ArtifactRef,
        classification: DataClassification | str | None = None,
        column_classification: Mapping[str, DataClassification | str] | None = None,
    ) -> ArtifactRef:
        """Persist a transformed payload without replacing its raw cache entry."""
        self._ensure_open()
        if (
            input_payload_ref.kind != CACHE_PAYLOAD_KIND
            or input_payload_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("derived_cache_payload_requires_selected_cache_input")
        verification = self._cas.verify(input_payload_ref)
        if not verification.ok:
            raise ValueError("derived_cache_payload_input_verification_failed")

        payload_bytes, media_type = ResultSerializer.serialize(result)
        governance = resolve_artifact_governance(
            scope=RetentionScope.CACHE,
            classification=classification,
            column_classification=column_classification,
        )
        payload_ref = self._cas.put_bytes(
            payload_bytes,
            opts=PutOptions(
                kind=CACHE_PAYLOAD_KIND,
                media_type=media_type,
                schema=SchemaInfo(name=CACHE_SCHEMA_NAME, version=CACHE_SCHEMA_VERSION),
                inputs=[
                    input_ref_from_artifact_ref(
                        input_payload_ref,
                        role="connector_cache.raw_payload",
                    )
                ],
                governance=governance,
            ),
            return_selected_profile=True,
        )
        if payload_ref.manifest_profile_sha256 is None:
            raise ValueError("derived_cache_payload_profile_unavailable")
        return payload_ref

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
        return self._index.list_datasets()

    def list_dataset_connectors(self) -> list[tuple[str | None, str]]:
        self._ensure_open()
        return self._index.list_dataset_connectors()

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
        with self._lifecycle_lock:
            if self._closed:
                return
            self._index.close()
            self._closed = True

    @property
    def closed(self) -> bool:
        with self._lifecycle_lock:
            return self._closed

    def _ensure_open(self) -> None:
        with self._lifecycle_lock:
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
        with self._eviction_lock:
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
