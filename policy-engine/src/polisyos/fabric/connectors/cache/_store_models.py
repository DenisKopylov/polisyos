"""
Cache data models and helper utilities.

Contains:
- CacheMetadata, CacheEntry, CachedFetchResult, CacheStats data classes
- Timestamp / datetime conversion helpers
- Request serialization helpers for index storage
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.fabric.connectors.base import FetchRequest, FetchResult
from polisyos.ir.connectors import DataVersion, QualityTier

__all__ = [
    "CACHE_METADATA_KIND",
    "CACHE_PAYLOAD_KIND",
    "CACHE_SCHEMA_NAME",
    "CACHE_SCHEMA_VERSION",
    "INDEX_SCHEMA_VERSION",
    "CacheEntry",
    "CacheMetadata",
    "CacheStats",
    "CachedFetchResult",
    "_canon_spec_allow_floats",
    "_dt_to_ts",
    "_payload_to_request",
    "_request_to_payload",
    "_ts_to_dt",
    "_utc_now",
]

# ── CAS artifact kinds ──────────────────────────────────────────────────────

CACHE_PAYLOAD_KIND = "connector_cache.payload"
CACHE_METADATA_KIND = "connector_cache.metadata"
CACHE_SCHEMA_NAME = "fabric.connector_cache"
CACHE_SCHEMA_VERSION = "1.0"

# SQLite schema version
INDEX_SCHEMA_VERSION = 1


# ── Helpers ─────────────────────────────────────────────────────────────────


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _dt_to_ts(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _ts_to_dt(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _request_to_payload(request: FetchRequest) -> dict[str, Any]:
    incremental_dump = (
        request.incremental_since.model_dump(mode="python")
        if request.incremental_since
        else None
    )
    return {
        "dataset_id": request.dataset_id,
        "date_start": request.date_start.isoformat() if request.date_start else None,
        "date_end": request.date_end.isoformat() if request.date_end else None,
        "as_of": request.as_of.isoformat() if request.as_of else None,
        "filters": {key: list(values) for key, values in request.filters},
        "incremental_since": incremental_dump,
        "include_metadata": request.include_metadata,
        "include_schema": request.include_schema,
        "page_size": request.page_size,
        "page_token": request.page_token,
        "min_quality_tier": request.min_quality_tier.value,
        "retryable": request.retryable,
    }


def _payload_to_request(payload: dict[str, Any]) -> FetchRequest:
    incremental = payload.get("incremental_since")
    incremental_since = DataVersion.model_validate(incremental) if incremental else None
    filters = payload.get("filters") or {}
    filter_tuple = tuple((k, tuple(v)) for k, v in filters.items())
    min_quality = payload.get("min_quality_tier", QualityTier.UNVERIFIED)
    return FetchRequest(
        dataset_id=payload["dataset_id"],
        date_start=datetime.fromisoformat(payload["date_start"]) if payload.get("date_start") else None,
        date_end=datetime.fromisoformat(payload["date_end"]) if payload.get("date_end") else None,
        as_of=datetime.fromisoformat(payload["as_of"]) if payload.get("as_of") else None,
        filters=filter_tuple,
        incremental_since=incremental_since,
        include_metadata=payload.get("include_metadata", True),
        include_schema=payload.get("include_schema", True),
        page_size=payload.get("page_size"),
        page_token=payload.get("page_token"),
        min_quality_tier=QualityTier(min_quality),
        retryable=payload.get("retryable"),
    )


def _canon_spec_allow_floats() -> CanonSpec:
    return CanonSpec(forbid_floats=False)


# ── Data Models ─────────────────────────────────────────────────────────────


class CacheMetadata(BaseModel):
    """Lightweight metadata describing a cached entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cache_key: str
    cached_at: datetime
    expires_at: datetime | None
    policy_id: str

    connector_id: str | None
    dataset_id: str

    payload_artifact_id: ArtifactID
    metadata_artifact_id: ArtifactID | None
    payload_size_bytes: int
    payload_media_type: str

    fetch_duration_ms: float
    source_version: DataVersion | None
    schema_hash: str | None

    is_stale: bool = False
    pinned: bool = False
    access_count: int = 0
    last_accessed_at: datetime | None = None

    @field_validator("cached_at", "expires_at", "last_accessed_at", mode="after")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @property
    def payload_ref(self) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=self.payload_artifact_id,
            kind=CACHE_PAYLOAD_KIND,
            media_type=self.payload_media_type,
        )


class CacheEntry(BaseModel):
    """Internal representation of a cache entry stored in the index."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cache_key: str
    request_key: str
    query_key: str

    connector_id: str | None
    dataset_id: str

    cached_at: datetime
    expires_at: datetime | None
    policy_id: str

    payload_artifact_id: ArtifactID
    payload_media_type: str
    payload_size_bytes: int
    metadata_artifact_id: ArtifactID | None

    fetch_duration_ms: float
    source_version: DataVersion | None
    schema_hash: str | None

    is_stale: bool = False
    pinned: bool = False
    access_count: int = 0
    last_accessed_at: datetime | None = None

    date_start: datetime | None = None
    date_end: datetime | None = None
    as_of: datetime | None = None

    request_payload: dict[str, Any]

    @field_validator("cached_at", "expires_at", "last_accessed_at", "date_start", "date_end", "as_of", mode="after")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def to_metadata(self) -> CacheMetadata:
        return CacheMetadata(
            cache_key=self.cache_key,
            cached_at=self.cached_at,
            expires_at=self.expires_at,
            policy_id=self.policy_id,
            connector_id=self.connector_id,
            dataset_id=self.dataset_id,
            payload_artifact_id=self.payload_artifact_id,
            metadata_artifact_id=self.metadata_artifact_id,
            payload_size_bytes=self.payload_size_bytes,
            payload_media_type=self.payload_media_type,
            fetch_duration_ms=self.fetch_duration_ms,
            source_version=self.source_version,
            schema_hash=self.schema_hash,
            is_stale=self.is_stale,
            pinned=self.pinned,
            access_count=self.access_count,
            last_accessed_at=self.last_accessed_at,
        )


@dataclass(frozen=True, slots=True)
class CachedFetchResult:
    """Wrapper for cached FetchResult with metadata and provenance info."""

    result: FetchResult[Any]
    metadata: CacheMetadata


class CacheStats(BaseModel):
    """Cache statistics for monitoring."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_entries: int
    total_size_bytes: int
    oldest_entry_age_hours: float
    hit_rate: float = 0.0
    eviction_count: int = 0
    namespace: str = "connector_cache"
