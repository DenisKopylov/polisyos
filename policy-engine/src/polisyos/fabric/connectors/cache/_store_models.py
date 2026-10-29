"""
Cache data models and helper utilities.

Contains:
- CacheMetadata, CacheEntry, CachedFetchResult, CacheStats data classes
- Timestamp / datetime conversion helpers
- Request serialization helpers for index storage
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
)
from polisyos.ir.connectors import DataVersion, QualityTier

__all__ = [
    "CACHE_METADATA_KIND",
    "CACHE_PAYLOAD_KIND",
    "CACHE_SCHEMA_NAME",
    "CACHE_SCHEMA_VERSION",
    "INDEX_SCHEMA_VERSION",
    "CacheEntry",
    "CacheFetchReceipt",
    "CacheMetadata",
    "CacheSourceIntent",
    "CacheStats",
    "CachedFetchResult",
    "_canon_spec_allow_floats",
    "_dt_to_ts",
    "_payload_to_request",
    "_request_to_payload",
    "_ts_to_dt",
    "_utc_now",
    "canon_spec_allow_floats",
    "capture_cache_source_intent",
    "dt_to_ts",
    "payload_to_request",
    "request_to_payload",
    "ts_to_dt",
    "utc_now",
]

# ── CAS artifact kinds ──────────────────────────────────────────────────────

CACHE_PAYLOAD_KIND = "connector_cache.payload"
CACHE_METADATA_KIND = "connector_cache.metadata"
CACHE_SCHEMA_NAME = "fabric.connector_cache"
CACHE_SCHEMA_VERSION = "1.0"

# SQLite schema version
INDEX_SCHEMA_VERSION = 3

_SOURCE_INTENT_KIND = "fabric.connector_cache.selected_source_intent"
_SOURCE_INTENT_ROLE = "fabric.connector_cache.selected_source_intent"
_SOURCE_INTENT_SCHEMA = "fabric.connector_cache.selected_source_intent"
_SOURCE_INTENT_VERSION = "1.0"
_SOURCE_INTENT_CONTRACT: Literal["fabric.connector_cache.selected_source_intent.v1"] = (
    "fabric.connector_cache.selected_source_intent.v1"
)


class CacheSourceIntent(BaseModel):
    """Bind one selected cache payload to its immutable source/request intent."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    contract: Literal["fabric.connector_cache.selected_source_intent.v1"]
    connector_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    request_key: str = Field(min_length=1)
    source_scope_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def capture_cache_source_intent(
    handle: ConnectionHandle,
    request: FetchRequest,
    *,
    expected_connector_id: str,
) -> CacheSourceIntent:
    """Capture the exact owner, request, and effective config selected for a fetch.

    The result is a frozen in-memory snapshot of already typed request and handle
    inputs. It contains only the effective configuration digest, never credentials
    or raw endpoint settings.
    """
    if not isinstance(handle, ConnectionHandle):
        raise TypeError("selected_source_cache_requires_connection_handle")
    if not isinstance(request, FetchRequest):
        raise TypeError("selected_source_cache_requires_fetch_request")
    if not isinstance(handle.config, ConnectionConfig):
        raise TypeError("selected_source_cache_requires_connection_config")
    if (
        not isinstance(expected_connector_id, str)
        or not expected_connector_id
        or handle.connector_id != expected_connector_id
    ):
        raise ValueError("connector_cache_handle_owner_mismatch")
    return CacheSourceIntent(
        contract=_SOURCE_INTENT_CONTRACT,
        connector_id=expected_connector_id,
        dataset_id=request.dataset_id,
        request_key=request.request_key,
        source_scope_fingerprint=handle.config.cache_scope_fingerprint,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────


def utc_now() -> datetime:
    return datetime.now(UTC)


def dt_to_ts(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def ts_to_dt(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC)


def request_to_payload(request: FetchRequest) -> dict[str, Any]:
    incremental_dump = (
        request.incremental_since.model_dump(mode="json") if request.incremental_since else None
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
        "source_signature": _dataset_source_signature(request.dataset_id),
    }


def payload_to_request(payload: dict[str, Any]) -> FetchRequest:
    incremental = payload.get("incremental_since")
    incremental_since = DataVersion.model_validate(incremental) if incremental else None
    filters = payload.get("filters") or {}
    filter_tuple = tuple((k, tuple(v)) for k, v in filters.items())
    min_quality = payload.get("min_quality_tier", QualityTier.UNVERIFIED)
    return FetchRequest(
        dataset_id=payload["dataset_id"],
        date_start=datetime.fromisoformat(payload["date_start"])
        if payload.get("date_start")
        else None,
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


def canon_spec_allow_floats() -> CanonSpec:
    return CanonSpec(forbid_floats=False)


_utc_now = utc_now
_dt_to_ts = dt_to_ts
_ts_to_dt = ts_to_dt
_request_to_payload = request_to_payload
_payload_to_request = payload_to_request
_canon_spec_allow_floats = canon_spec_allow_floats


def _dataset_source_signature(dataset_id: str) -> dict[str, Any] | None:
    normalized = str(dataset_id or "").strip()
    if not normalized:
        return None
    try:
        path = Path(normalized)
        if not path.exists() or not path.is_file():
            return None
        stat = path.stat()
        return {
            "path": str(path.resolve()),
            "mtime": stat.st_mtime,
            "size": stat.st_size,
        }
    except OSError:
        return None


# ── Data Models ─────────────────────────────────────────────────────────────


class CacheMetadata(BaseModel):
    """Lightweight metadata describing a cached entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cache_key: str
    request_key: str | None = None
    source_scope_fingerprint: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    cached_at: datetime
    expires_at: datetime | None
    policy_id: str

    connector_id: str | None
    dataset_id: str

    payload_artifact_id: ArtifactID
    metadata_artifact_id: ArtifactID | None
    payload_size_bytes: int
    payload_media_type: str
    payload_manifest_profile_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )

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
            return value.replace(tzinfo=UTC)
        return value

    @property
    def payload_ref(self) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=self.payload_artifact_id,
            kind=CACHE_PAYLOAD_KIND,
            media_type=self.payload_media_type,
            manifest_profile_sha256=self.payload_manifest_profile_sha256,
        )


class CacheEntry(BaseModel):
    """Internal representation of a cache entry stored in the index."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cache_key: str
    request_key: str
    source_scope_fingerprint: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    query_key: str

    connector_id: str | None
    dataset_id: str

    cached_at: datetime
    expires_at: datetime | None
    policy_id: str

    payload_artifact_id: ArtifactID
    payload_media_type: str
    payload_manifest_profile_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
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

    @field_validator(
        "cached_at",
        "expires_at",
        "last_accessed_at",
        "date_start",
        "date_end",
        "as_of",
        mode="after",
    )
    @classmethod
    def _ensure_tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def to_metadata(self) -> CacheMetadata:
        return CacheMetadata(
            cache_key=self.cache_key,
            request_key=self.request_key,
            source_scope_fingerprint=self.source_scope_fingerprint,
            cached_at=self.cached_at,
            expires_at=self.expires_at,
            policy_id=self.policy_id,
            connector_id=self.connector_id,
            dataset_id=self.dataset_id,
            payload_artifact_id=self.payload_artifact_id,
            metadata_artifact_id=self.metadata_artifact_id,
            payload_size_bytes=self.payload_size_bytes,
            payload_media_type=self.payload_media_type,
            payload_manifest_profile_sha256=self.payload_manifest_profile_sha256,
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


@dataclass(frozen=True, slots=True)
class CacheFetchReceipt:
    """Bind one connector fetch result to its cache lookup and selected write."""

    result: FetchResult[Any]
    lookup_outcome: Literal["hit", "miss"]
    cache_result: CachedFetchResult | None
    selected_intent: CacheSourceIntent | None = None

    @property
    def payload_ref(self) -> ArtifactRef | None:
        """Return the exact selected payload ref persisted by the cache writer."""
        return self.cache_result.metadata.payload_ref if self.cache_result is not None else None


class CacheStats(BaseModel):
    """Cache statistics for monitoring."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_entries: int
    total_size_bytes: int
    oldest_entry_age_hours: float
    hit_rate: float = 0.0
    eviction_count: int = 0
    namespace: str = "connector_cache"
