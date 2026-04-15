"""
SQLite-backed metadata index for cache entries.

Provides efficient lookup, filtering, and LRU eviction support for the
connector cache store via a local SQLite database.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from polisyos.core.artifacts import ArtifactID
from polisyos.ir.connectors import DataVersion

from ._store_models import (
    INDEX_SCHEMA_VERSION,
    CacheEntry,
    _dt_to_ts,
    _ts_to_dt,
    _utc_now,
)

__all__ = [
    "CacheIndex",
]


class CacheIndex:
    """SQLite-backed metadata index for cache entries."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._closed = False
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
            if self._closed:
                return
            self._conn.close()
            self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError(f"CacheIndex is closed: {self._path}")

    def __enter__(self) -> "CacheIndex":
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def get_entry(self, cache_key: str) -> CacheEntry | None:
        with self._lock:
            self._ensure_open()
            row = self._conn.execute(
                "SELECT * FROM cache_entries WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def upsert_entry(self, entry: CacheEntry) -> None:
        with self._lock, self._conn:
            self._ensure_open()
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
            self._ensure_open()
            self._conn.execute(
                "UPDATE cache_entries SET is_stale = 1 WHERE cache_key = ?",
                (cache_key,),
            )

    def delete_entry(self, cache_key: str) -> None:
        with self._lock, self._conn:
            self._ensure_open()
            self._conn.execute(
                "DELETE FROM cache_entries WHERE cache_key = ?",
                (cache_key,),
            )

    def update_access(self, cache_key: str, accessed_at: datetime | None = None) -> None:
        accessed_at = accessed_at or _utc_now()
        with self._lock, self._conn:
            self._ensure_open()
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
            self._ensure_open()
            self._conn.execute(
                "UPDATE cache_entries SET pinned = ? WHERE cache_key = ?",
                (1 if pinned else 0, cache_key),
            )

    def list_datasets(self) -> list[str]:
        with self._lock:
            self._ensure_open()
            rows = self._conn.execute(
                "SELECT DISTINCT dataset_id FROM cache_entries",
            ).fetchall()
        return [row["dataset_id"] for row in rows]

    def list_dataset_connectors(self) -> list[tuple[str | None, str]]:
        with self._lock:
            self._ensure_open()
            rows = self._conn.execute(
                "SELECT DISTINCT connector_id, dataset_id FROM cache_entries",
            ).fetchall()
        return [(row["connector_id"], row["dataset_id"]) for row in rows]

    def list_expiring(self, threshold_ts: float) -> list[CacheEntry]:
        with self._lock:
            self._ensure_open()
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
            self._ensure_open()
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [row["cache_key"] for row in rows]

    def get_latest_for_dataset(self, dataset_id: str) -> CacheEntry | None:
        with self._lock:
            self._ensure_open()
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
            self._ensure_open()
            row = self._conn.execute(
                "SELECT COUNT(*) AS count, SUM(payload_size_bytes) AS total, MIN(cached_at) AS oldest FROM cache_entries"
            ).fetchone()
        if row is None:
            return 0, 0, None
        return int(row["count"] or 0), int(row["total"] or 0), row["oldest"]

    def total_size(self) -> int:
        with self._lock:
            self._ensure_open()
            row = self._conn.execute(
                "SELECT SUM(payload_size_bytes) AS total FROM cache_entries"
            ).fetchone()
        return int(row["total"] or 0) if row else 0

    def total_entries(self) -> int:
        with self._lock:
            self._ensure_open()
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
            self._ensure_open()
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
