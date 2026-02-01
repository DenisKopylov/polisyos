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
"""
from __future__ import annotations

import io
import json
import pickle
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, field_validator

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ArtifactID, ArtifactRef, FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon.canon_json import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors.base import FetchRequest, FetchResult
from polisyos.ir.connectors import DataVersion, QualityTier

from .policy import CachePolicy, PolicyRegistry

logger = get_logger(__name__)

# CAS artifact kinds
CACHE_PAYLOAD_KIND = "connector_cache.payload"
CACHE_METADATA_KIND = "connector_cache.metadata"
CACHE_SCHEMA_NAME = "fabric.connector_cache"
CACHE_SCHEMA_VERSION = "1.0"

# SQLite schema version
INDEX_SCHEMA_VERSION = 1


# =============================================================================
# Helpers
# =============================================================================


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


# =============================================================================
# Data Models
# =============================================================================


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


# =============================================================================
# Result Serialization
# =============================================================================


class ResultSerializer:
    """
    Handles FetchResult serialization/deserialization.

    Strategy:
    - DataFrames → Parquet (compact, preserves types)
    - Dicts/Lists → Canonical JSON (deterministic)
    - Other → Pickle (fallback)

    Format:
        [envelope_len: 4 bytes][envelope: canonical JSON][data: format-specific]
    """

    @staticmethod
    def serialize(result: FetchResult[Any]) -> tuple[bytes, str]:
        # Detect data type and serialize payload
        if isinstance(result.data, pd.DataFrame):
            buffer = io.BytesIO()
            result.data.to_parquet(buffer, compression="snappy")
            data_bytes = buffer.getvalue()
            data_media_type = "application/parquet"
        elif isinstance(result.data, (dict, list)):
            data_bytes = to_canonical_bytes(result.data, _canon_spec_allow_floats())
            data_media_type = "application/json"
        else:
            data_bytes = pickle.dumps(result.data)
            data_media_type = "application/pickle"

        envelope = {
            "schema_id": result.schema_id,
            "schema_version": result.schema_version,
            "version": result.version.model_dump(mode="json"),
            "fetched_at": result.fetched_at,
            "source_updated_at": result.source_updated_at,
            "evidence_ref": result.evidence_ref.model_dump(mode="json")
            if result.evidence_ref
            else None,
            "completeness": result.completeness,
            "quality_tier": result.quality_tier.value,
            "quality_flags": list(result.quality_flags),
            "row_count": result.row_count,
            "data_media_type": data_media_type,
            "has_more": result.has_more,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "fetch_duration_ms": result.fetch_duration_ms,
            "bytes_transferred": result.bytes_transferred,
            "resilience": result.resilience.model_dump(mode="json")
            if result.resilience
            else None,
        }

        envelope_bytes = to_canonical_bytes(envelope, _canon_spec_allow_floats())
        combined = len(envelope_bytes).to_bytes(4, "big") + envelope_bytes + data_bytes
        media_type = f"application/vnd.polisyos.cached-result+{data_media_type}"
        return combined, media_type

    @staticmethod
    def deserialize(data_bytes: bytes) -> FetchResult[Any]:
        envelope_len = int.from_bytes(data_bytes[:4], "big")
        envelope_bytes = data_bytes[4 : 4 + envelope_len]
        payload_bytes = data_bytes[4 + envelope_len :]

        envelope = from_canonical_bytes(envelope_bytes)
        data_media_type = envelope.get("data_media_type")

        if data_media_type == "application/parquet":
            data = pd.read_parquet(io.BytesIO(payload_bytes))
        elif data_media_type == "application/json":
            data = from_canonical_bytes(payload_bytes)
        else:
            data = pickle.loads(payload_bytes)

        evidence_ref = envelope.get("evidence_ref")
        if evidence_ref is not None:
            try:
                from polisyos.core.contracts.fabric import EvidenceBundleRef

                evidence_ref = EvidenceBundleRef.model_validate(evidence_ref)
            except Exception:
                evidence_ref = None

        resilience_info = envelope.get("resilience")
        if resilience_info is not None:
            try:
                from polisyos.fabric.connectors.base import ResilienceInfo

                resilience_info = ResilienceInfo.model_validate(resilience_info)
            except Exception:
                resilience_info = None

        return FetchResult(
            data=data,
            row_count=envelope["row_count"],
            schema_id=envelope["schema_id"],
            schema_version=envelope["schema_version"],
            version=DataVersion(**envelope["version"]),
            fetched_at=envelope["fetched_at"],
            source_updated_at=envelope.get("source_updated_at"),
            evidence_ref=evidence_ref,
            completeness=envelope["completeness"],
            quality_tier=QualityTier(envelope.get("quality_tier", QualityTier.UNVERIFIED)),
            quality_flags=frozenset(envelope.get("quality_flags", [])),
            has_more=envelope.get("has_more", False),
            next_page_token=envelope.get("next_page_token"),
            total_count=envelope.get("total_count"),
            fetch_duration_ms=envelope.get("fetch_duration_ms", 0.0),
            bytes_transferred=envelope.get("bytes_transferred", 0),
            resilience=resilience_info,
        )


# =============================================================================
# SQLite Index
# =============================================================================


class CacheIndex:
    """SQLite-backed metadata index for cache entries."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("PRAGMA temp_store=MEMORY;")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS cache_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    request_key TEXT NOT NULL,
                    query_key TEXT NOT NULL,
                    connector_id TEXT,
                    dataset_id TEXT NOT NULL,
                    cached_at REAL NOT NULL,
                    expires_at REAL,
                    policy_id TEXT NOT NULL,
                    payload_artifact_id TEXT NOT NULL,
                    payload_media_type TEXT NOT NULL,
                    payload_size_bytes INTEGER NOT NULL,
                    metadata_artifact_id TEXT,
                    fetch_duration_ms REAL NOT NULL,
                    source_version TEXT,
                    schema_hash TEXT,
                    is_stale INTEGER NOT NULL,
                    pinned INTEGER NOT NULL,
                    access_count INTEGER NOT NULL,
                    last_accessed_at REAL,
                    date_start REAL,
                    date_end REAL,
                    as_of REAL,
                    request_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_dataset ON cache_entries(dataset_id)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_connector ON cache_entries(connector_id)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_expiry ON cache_entries(expires_at)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_cached_at ON cache_entries(cached_at)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_stale ON cache_entries(is_stale)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_pinned ON cache_entries(pinned)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_dates ON cache_entries(date_start, date_end)"
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO cache_meta (key, value) VALUES (?, ?)",
                ("schema_version", str(INDEX_SCHEMA_VERSION)),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def get_entry(self, cache_key: str) -> CacheEntry | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cache_entries WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def upsert_entry(self, entry: CacheEntry) -> None:
        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT pinned FROM cache_entries WHERE cache_key = ?",
                (entry.cache_key,),
            ).fetchone()
            pinned = entry.pinned
            if existing is not None and existing["pinned"]:
                pinned = True

            self._conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries (
                    cache_key, request_key, query_key, connector_id, dataset_id,
                    cached_at, expires_at, policy_id,
                    payload_artifact_id, payload_media_type, payload_size_bytes,
                    metadata_artifact_id, fetch_duration_ms, source_version, schema_hash,
                    is_stale, pinned, access_count, last_accessed_at,
                    date_start, date_end, as_of, request_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.cache_key,
                    entry.request_key,
                    entry.query_key,
                    entry.connector_id,
                    entry.dataset_id,
                    _dt_to_ts(entry.cached_at),
                    _dt_to_ts(entry.expires_at),
                    entry.policy_id,
                    str(entry.payload_artifact_id),
                    entry.payload_media_type,
                    int(entry.payload_size_bytes),
                    str(entry.metadata_artifact_id) if entry.metadata_artifact_id else None,
                    float(entry.fetch_duration_ms),
                    json.dumps(entry.source_version.model_dump(mode="json"))
                    if entry.source_version
                    else None,
                    entry.schema_hash,
                    1 if entry.is_stale else 0,
                    1 if pinned else 0,
                    int(entry.access_count),
                    _dt_to_ts(entry.last_accessed_at),
                    _dt_to_ts(entry.date_start),
                    _dt_to_ts(entry.date_end),
                    _dt_to_ts(entry.as_of),
                    json.dumps(entry.request_payload, sort_keys=True),
                ),
            )

    def mark_stale(self, cache_key: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE cache_entries SET is_stale = 1 WHERE cache_key = ?",
                (cache_key,),
            )

    def delete_entry(self, cache_key: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM cache_entries WHERE cache_key = ?",
                (cache_key,),
            )

    def update_access(self, cache_key: str, accessed_at: datetime | None = None) -> None:
        accessed_at = accessed_at or _utc_now()
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE cache_entries
                SET access_count = access_count + 1,
                    last_accessed_at = ?
                WHERE cache_key = ?
                """,
                (_dt_to_ts(accessed_at), cache_key),
            )

    def set_pinned(self, cache_key: str, pinned: bool) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE cache_entries SET pinned = ? WHERE cache_key = ?",
                (1 if pinned else 0, cache_key),
            )

    def list_datasets(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT dataset_id FROM cache_entries",
            ).fetchall()
        return [row["dataset_id"] for row in rows]

    def list_dataset_connectors(self) -> list[tuple[str | None, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT connector_id, dataset_id FROM cache_entries",
            ).fetchall()
        return [(row["connector_id"], row["dataset_id"]) for row in rows]

    def list_expiring(self, threshold_ts: float) -> list[CacheEntry]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM cache_entries
                WHERE expires_at IS NOT NULL
                  AND expires_at <= ?
                  AND is_stale = 0
                """,
                (threshold_ts,),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def list_by_filters(self, **filters: Any) -> list[str]:
        clauses = []
        params: list[Any] = []

        if "cache_key" in filters:
            clauses.append("cache_key = ?")
            params.append(filters["cache_key"])
        if "dataset_id" in filters:
            clauses.append("dataset_id = ?")
            params.append(filters["dataset_id"])
        if "connector_id" in filters:
            clauses.append("connector_id = ?")
            params.append(filters["connector_id"])
        if "policy_id" in filters:
            clauses.append("policy_id = ?")
            params.append(filters["policy_id"])

        # Date range intersection: (start is null or start <= end_filter) and (end is null or end >= start_filter)
        date_start = filters.get("date_start")
        date_end = filters.get("date_end")
        if date_start is not None or date_end is not None:
            start_ts = _dt_to_ts(date_start) if date_start else None
            end_ts = _dt_to_ts(date_end) if date_end else None
            if end_ts is not None:
                clauses.append("(date_start IS NULL OR date_start <= ?)")
                params.append(end_ts)
            if start_ts is not None:
                clauses.append("(date_end IS NULL OR date_end >= ?)")
                params.append(start_ts)

        where_clause = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f"SELECT cache_key FROM cache_entries{where_clause}"

        with self._lock:
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [row["cache_key"] for row in rows]

    def get_latest_for_dataset(self, dataset_id: str) -> CacheEntry | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM cache_entries
                WHERE dataset_id = ?
                ORDER BY cached_at DESC
                LIMIT 1
                """,
                (dataset_id,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def stats(self) -> tuple[int, int, float | None]:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS count, SUM(payload_size_bytes) AS total, MIN(cached_at) AS oldest FROM cache_entries"
            ).fetchone()
        if row is None:
            return 0, 0, None
        return int(row["count"] or 0), int(row["total"] or 0), row["oldest"]

    def total_size(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT SUM(payload_size_bytes) AS total FROM cache_entries"
            ).fetchone()
        return int(row["total"] or 0) if row else 0

    def total_entries(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS count FROM cache_entries"
            ).fetchone()
        return int(row["count"] or 0) if row else 0

    def list_lru_candidates(self, limit: int, *, include_pinned: bool = False) -> list[CacheEntry]:
        where = "" if include_pinned else "WHERE pinned = 0"
        sql = (
            "SELECT * FROM cache_entries "
            f"{where} "
            "ORDER BY COALESCE(last_accessed_at, cached_at) ASC "
            "LIMIT ?"
        )
        with self._lock:
            rows = self._conn.execute(sql, (limit,)).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> CacheEntry:
        request_payload = json.loads(row["request_json"])
        source_version = json.loads(row["source_version"]) if row["source_version"] else None
        return CacheEntry(
            cache_key=row["cache_key"],
            request_key=row["request_key"],
            query_key=row["query_key"],
            connector_id=row["connector_id"],
            dataset_id=row["dataset_id"],
            cached_at=_ts_to_dt(row["cached_at"]) or _utc_now(),
            expires_at=_ts_to_dt(row["expires_at"]),
            policy_id=row["policy_id"],
            payload_artifact_id=ArtifactID.model_validate(row["payload_artifact_id"]),
            payload_media_type=row["payload_media_type"],
            payload_size_bytes=int(row["payload_size_bytes"]),
            metadata_artifact_id=ArtifactID.model_validate(row["metadata_artifact_id"])
            if row["metadata_artifact_id"]
            else None,
            fetch_duration_ms=float(row["fetch_duration_ms"]),
            source_version=DataVersion.model_validate(source_version) if source_version else None,
            schema_hash=row["schema_hash"],
            is_stale=bool(row["is_stale"]),
            pinned=bool(row["pinned"]),
            access_count=int(row["access_count"]),
            last_accessed_at=_ts_to_dt(row["last_accessed_at"]),
            date_start=_ts_to_dt(row["date_start"]),
            date_end=_ts_to_dt(row["date_end"]),
            as_of=_ts_to_dt(row["as_of"]),
            request_payload=request_payload,
        )


# =============================================================================
# Cache Store
# =============================================================================


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
        except Exception:
            pass

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
        except Exception:
            pass

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
