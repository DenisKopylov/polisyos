"""Public services control plane store module API."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.control import ControlJobKind, ControlJobResponse, ControlJobState, ExecutionProfile
from polisyos.core.contracts.runtime import ApiMeta


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return None


def _job_event_topic(event_type: str) -> str:
    normalized = event_type.strip().lower()
    if normalized.startswith("job_"):
        normalized = normalized[4:]
    return f"control.job.{normalized}"


@dataclass(frozen=True)
class ControlJobRecord:
    """Control job record data model."""
    job_id: str
    kind: ControlJobKind
    state: ControlJobState
    run_id: str | None
    pipeline_id: str | None
    requested_execution_profile: ExecutionProfile | None
    effective_execution_profile: ExecutionProfile
    policy_flags: dict[str, Any]
    capability_manifest_ref: str | None
    payload_ref: str | None
    submitted_by: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    lease_owner: str | None
    lease_expires_at: datetime | None
    attempt: int
    error_message: str | None
    progress: dict[str, Any]

    def to_response(self, *, request_id: str | None = None) -> ControlJobResponse:
        manifest_ref = None
        if self.capability_manifest_ref:
            manifest_ref = ArtifactRef(
                artifact_id=ArtifactID.model_validate(self.capability_manifest_ref),
                kind="runtime.capability_manifest",
                media_type="application/json",
            )
        return ControlJobResponse(
            meta=ApiMeta(request_id=request_id or "control-job"),
            job_id=self.job_id,
            kind=self.kind,
            state=self.state,
            run_id=self.run_id,
            pipeline_id=self.pipeline_id,
            requested_execution_profile=self.requested_execution_profile,
            effective_execution_profile=self.effective_execution_profile,
            capability_manifest_ref=manifest_ref,
            submitted_at=self.created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error_message=self.error_message,
            progress=dict(self.progress),
        )


@dataclass(frozen=True)
class ControlWorkerLeaseRecord:
    """Control worker lease record data model."""
    worker_id: str
    state: str
    backend: str | None
    active_job_id: str | None
    metadata: dict[str, Any]
    heartbeat_at: datetime
    lease_expires_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ControlOutboxRecord:
    """Control outbox record data model."""
    event_id: str
    topic: str
    event_key: str | None
    state: str
    job_id: str | None
    run_id: str | None
    payload: dict[str, Any]
    created_at: datetime
    published_at: datetime | None
    attempt: int
    error_message: str | None


class ControlPlaneStore:
    """Control plane store implementation."""
    def __init__(
        self,
        *,
        backend: str,
        sqlite_path: str | Path,
        postgres_dsn: str | None = None,
    ) -> None:
        self.backend = backend.strip().lower()
        self._sqlite_path = Path(sqlite_path)
        self._postgres_dsn = postgres_dsn
        self._lock = threading.Lock()
        self._sqlite_conn: sqlite3.Connection | None = None
        if self.backend == "sqlite":
            self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self._sqlite_conn = sqlite3.connect(str(self._sqlite_path), check_same_thread=False)
            self._sqlite_conn.row_factory = sqlite3.Row
            self._sqlite_conn.execute("PRAGMA journal_mode=WAL")
            self._sqlite_conn.execute("PRAGMA foreign_keys=ON")
            self._ensure_sqlite_schema()
        elif self.backend == "postgres":
            if not self._postgres_dsn:
                raise RuntimeError("PostgreSQL control-plane store requires a DSN")
            self._ensure_postgres_schema()
        else:
            raise RuntimeError(f"Unsupported control-plane store backend: {backend!r}")

    def create_job(
        self,
        *,
        job_id: str,
        kind: ControlJobKind,
        run_id: str | None,
        pipeline_id: str | None,
        requested_execution_profile: ExecutionProfile | None,
        effective_execution_profile: ExecutionProfile,
        policy_flags: dict[str, Any],
        capability_manifest_ref: str | None,
        payload_ref: str | None,
        submitted_by: str | None,
    ) -> ControlJobRecord:
        created_at = _utc_now()
        progress = {}
        sql = """
            INSERT INTO control_jobs (
                job_id, job_kind, state, run_id, pipeline_id,
                requested_profile, effective_profile, policy_flags_json,
                capability_manifest_ref, payload_ref, submitted_by,
                created_at, started_at, finished_at,
                lease_owner, lease_expires_at, attempt, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, 0, NULL)
        """
        params = (
            job_id,
            kind,
            "pending",
            run_id,
            pipeline_id,
            requested_execution_profile,
            effective_execution_profile,
            json.dumps(policy_flags, sort_keys=True),
            capability_manifest_ref,
            payload_ref,
            submitted_by,
            _iso(created_at),
        )
        self._execute(sql, params)
        self.upsert_progress(job_id=job_id, progress=progress)
        self.append_event(job_id=job_id, event_type="job_created", payload={"state": "pending"})
        record = self.get_job(job_id)
        if record is None:
            raise RuntimeError(f"Failed to persist control job {job_id}")
        self._emit_job_outbox_event(
            record=record,
            event_type="job_created",
            payload={"state": "pending"},
        )
        return record

    def get_job(self, job_id: str) -> ControlJobRecord | None:
        row = self._fetchone(
            """
            SELECT
                j.job_id,
                j.job_kind,
                j.state,
                j.run_id,
                j.pipeline_id,
                j.requested_profile,
                j.effective_profile,
                j.policy_flags_json,
                j.capability_manifest_ref,
                j.payload_ref,
                j.submitted_by,
                j.created_at,
                j.started_at,
                j.finished_at,
                j.lease_owner,
                j.lease_expires_at,
                j.attempt,
                j.error_message,
                p.progress_json
            FROM control_jobs j
            LEFT JOIN control_job_progress p ON p.job_id = j.job_id
            WHERE j.job_id = ?
            """,
            (job_id,),
        )
        if row is None:
            return None
        return self._row_to_record(row)

    def get_job_by_pipeline(self, pipeline_id: str) -> ControlJobRecord | None:
        row = self._fetchone(
            """
            SELECT
                j.job_id,
                j.job_kind,
                j.state,
                j.run_id,
                j.pipeline_id,
                j.requested_profile,
                j.effective_profile,
                j.policy_flags_json,
                j.capability_manifest_ref,
                j.payload_ref,
                j.submitted_by,
                j.created_at,
                j.started_at,
                j.finished_at,
                j.lease_owner,
                j.lease_expires_at,
                j.attempt,
                j.error_message,
                p.progress_json
            FROM control_jobs j
            LEFT JOIN control_job_progress p ON p.job_id = j.job_id
            WHERE j.pipeline_id = ?
            """,
            (pipeline_id,),
        )
        if row is None:
            return None
        return self._row_to_record(row)

    def append_event(self, *, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self._execute(
            """
            INSERT INTO control_job_events (job_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, event_type, json.dumps(payload, sort_keys=True), _iso(_utc_now())),
        )

    def upsert_progress(self, *, job_id: str, progress: dict[str, Any]) -> None:
        now = _iso(_utc_now())
        progress_json = json.dumps(progress, sort_keys=True)
        if self.backend == "sqlite":
            self._execute(
                """
                INSERT INTO control_job_progress (job_id, progress_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    progress_json = excluded.progress_json,
                    updated_at = excluded.updated_at
                """,
                (job_id, progress_json, now),
            )
            return
        self._execute(
            """
            INSERT INTO control_job_progress (job_id, progress_json, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (job_id) DO UPDATE SET
                progress_json = EXCLUDED.progress_json,
                updated_at = EXCLUDED.updated_at
            """,
            (job_id, progress_json, now),
        )

    def lease_next_job(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> ControlJobRecord | None:
        if self.backend == "sqlite":
            record = self._lease_next_sqlite(worker_id=worker_id, lease_seconds=lease_seconds)
        else:
            record = self._lease_next_postgres(worker_id=worker_id, lease_seconds=lease_seconds)
        if record is not None:
            payload = {
                "state": "running",
                "lease_owner": worker_id,
                "lease_expires_at": _iso(record.lease_expires_at),
            }
            self.append_event(job_id=record.job_id, event_type="job_running", payload=payload)
            self._emit_job_outbox_event(
                record=record,
                event_type="job_running",
                payload=payload,
            )
        return record

    def mark_running(self, *, job_id: str, worker_id: str, lease_seconds: int = 60) -> None:
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        self._execute(
            """
            UPDATE control_jobs
            SET state = ?, started_at = COALESCE(started_at, ?),
                lease_owner = ?, lease_expires_at = ?, attempt = attempt + 1
            WHERE job_id = ?
            """,
            ("running", _iso(now), worker_id, _iso(lease_expires_at), job_id),
        )
        self.append_event(
            job_id=job_id,
            event_type="job_running",
            payload={
                "state": "running",
                "lease_owner": worker_id,
                "lease_expires_at": _iso(lease_expires_at),
            },
        )
        record = self.get_job(job_id)
        if record is not None:
            self._emit_job_outbox_event(
                record=record,
                event_type="job_running",
                payload={
                    "state": "running",
                    "lease_owner": worker_id,
                    "lease_expires_at": _iso(lease_expires_at),
                },
            )

    def complete_job(
        self,
        *,
        job_id: str,
        run_id: str | None = None,
        pipeline_id: str | None = None,
        capability_manifest_ref: str | None = None,
        progress: dict[str, Any] | None = None,
    ) -> None:
        now = _utc_now()
        self._execute(
            """
            UPDATE control_jobs
            SET state = ?, run_id = COALESCE(?, run_id), pipeline_id = COALESCE(?, pipeline_id),
                capability_manifest_ref = COALESCE(?, capability_manifest_ref),
                finished_at = ?, lease_owner = NULL, lease_expires_at = NULL, error_message = NULL
            WHERE job_id = ?
            """,
            ("completed", run_id, pipeline_id, capability_manifest_ref, _iso(now), job_id),
        )
        if progress is not None:
            self.upsert_progress(job_id=job_id, progress=progress)
        self.append_event(job_id=job_id, event_type="job_completed", payload={"state": "completed"})
        record = self.get_job(job_id)
        if record is not None:
            self._emit_job_outbox_event(
                record=record,
                event_type="job_completed",
                payload={"state": "completed", "progress": dict(progress or record.progress)},
            )

    def fail_job(
        self,
        *,
        job_id: str,
        error_message: str,
        capability_manifest_ref: str | None = None,
        progress: dict[str, Any] | None = None,
    ) -> None:
        now = _utc_now()
        self._execute(
            """
            UPDATE control_jobs
            SET state = ?, capability_manifest_ref = COALESCE(?, capability_manifest_ref),
                finished_at = ?, lease_owner = NULL, lease_expires_at = NULL, error_message = ?
            WHERE job_id = ?
            """,
            ("failed", capability_manifest_ref, _iso(now), error_message[:2000], job_id),
        )
        if progress is not None:
            self.upsert_progress(job_id=job_id, progress=progress)
        self.append_event(
            job_id=job_id,
            event_type="job_failed",
            payload={"state": "failed", "error_message": error_message[:500]},
        )
        record = self.get_job(job_id)
        if record is not None:
            self._emit_job_outbox_event(
                record=record,
                event_type="job_failed",
                payload={
                    "state": "failed",
                    "error_message": error_message[:500],
                    "progress": dict(progress or record.progress),
                },
            )

    def update_manifest_ref(self, *, job_id: str, capability_manifest_ref: str) -> None:
        self._execute(
            "UPDATE control_jobs SET capability_manifest_ref = ? WHERE job_id = ?",
            (capability_manifest_ref, job_id),
        )

    def update_progress_state(
        self,
        *,
        job_id: str,
        state: str,
        progress: dict[str, Any],
        error_message: str | None = None,
    ) -> None:
        self.upsert_progress(job_id=job_id, progress=progress)
        self._execute(
            "UPDATE control_jobs SET error_message = COALESCE(?, error_message) WHERE job_id = ?",
            (error_message, job_id),
        )
        self.append_event(job_id=job_id, event_type="job_progress", payload={"state": state, **progress})
        record = self.get_job(job_id)
        if record is not None:
            self._emit_job_outbox_event(
                record=record,
                event_type="job_progress",
                payload={"state": state, **progress},
            )

    def renew_job_lease(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> None:
        lease_expires_at = _utc_now() + timedelta(seconds=max(lease_seconds, 1))
        self._execute(
            """
            UPDATE control_jobs
            SET lease_expires_at = ?
            WHERE job_id = ? AND state = 'running' AND lease_owner = ?
            """,
            (_iso(lease_expires_at), job_id, worker_id),
        )

    def heartbeat_worker(
        self,
        *,
        worker_id: str,
        state: str,
        lease_seconds: int,
        backend: str | None = None,
        active_job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        metadata_json = json.dumps(metadata or {}, sort_keys=True)
        if self.backend == "sqlite":
            self._execute(
                """
                INSERT INTO control_worker_leases (
                    worker_id, state, backend, active_job_id, metadata_json,
                    heartbeat_at, lease_expires_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    state = excluded.state,
                    backend = excluded.backend,
                    active_job_id = excluded.active_job_id,
                    metadata_json = excluded.metadata_json,
                    heartbeat_at = excluded.heartbeat_at,
                    lease_expires_at = excluded.lease_expires_at,
                    updated_at = excluded.updated_at
                """,
                (
                    worker_id,
                    state,
                    backend,
                    active_job_id,
                    metadata_json,
                    _iso(now),
                    _iso(lease_expires_at),
                    _iso(now),
                    _iso(now),
                ),
            )
            return
        self._execute(
            """
            INSERT INTO control_worker_leases (
                worker_id, state, backend, active_job_id, metadata_json,
                heartbeat_at, lease_expires_at, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (worker_id) DO UPDATE SET
                state = EXCLUDED.state,
                backend = EXCLUDED.backend,
                active_job_id = EXCLUDED.active_job_id,
                metadata_json = EXCLUDED.metadata_json,
                heartbeat_at = EXCLUDED.heartbeat_at,
                lease_expires_at = EXCLUDED.lease_expires_at,
                updated_at = EXCLUDED.updated_at
            """,
            (
                worker_id,
                state,
                backend,
                active_job_id,
                metadata_json,
                _iso(now),
                _iso(lease_expires_at),
                _iso(now),
                _iso(now),
            ),
        )

    def release_worker(self, *, worker_id: str, state: str = "stopped") -> None:
        now = _utc_now()
        self._execute(
            """
            UPDATE control_worker_leases
            SET state = ?, active_job_id = NULL, heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
            WHERE worker_id = ?
            """,
            (state, _iso(now), _iso(now), _iso(now), worker_id),
        )

    def list_worker_leases(self, *, active_only: bool = True) -> list[ControlWorkerLeaseRecord]:
        sql = """
            SELECT
                worker_id,
                state,
                backend,
                active_job_id,
                metadata_json,
                heartbeat_at,
                lease_expires_at,
                created_at,
                updated_at
            FROM control_worker_leases
        """
        params: tuple[Any, ...] = ()
        if active_only:
            sql += " WHERE lease_expires_at IS NOT NULL AND lease_expires_at > ?"
            params = (_iso(_utc_now()),)
        sql += " ORDER BY worker_id ASC"
        rows = self._fetchall(sql, params)
        return [self._row_to_worker_lease(row) for row in rows]

    def enqueue_outbox_event(
        self,
        *,
        topic: str,
        payload: dict[str, Any],
        job_id: str | None = None,
        run_id: str | None = None,
        event_key: str | None = None,
    ) -> ControlOutboxRecord:
        if event_key:
            existing = self._get_outbox_event_by_key(topic=topic, event_key=event_key)
            if existing is not None:
                return existing
        event_id = f"outbox_{uuid.uuid4().hex[:16]}"
        created_at = _utc_now()
        self._execute(
            """
            INSERT INTO control_outbox_events (
                event_id, topic, event_key, state, job_id, run_id,
                payload_json, created_at, published_at, attempt, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL)
            """,
            (
                event_id,
                topic,
                event_key,
                "pending",
                job_id,
                run_id,
                json.dumps(payload, sort_keys=True),
                _iso(created_at),
            ),
        )
        record = self.get_outbox_event(event_id)
        if record is None:
            raise RuntimeError(f"Failed to persist control outbox event {event_id}")
        return record

    def get_outbox_event(self, event_id: str) -> ControlOutboxRecord | None:
        row = self._fetchone(
            """
            SELECT
                event_id,
                topic,
                event_key,
                state,
                job_id,
                run_id,
                payload_json,
                created_at,
                published_at,
                attempt,
                error_message
            FROM control_outbox_events
            WHERE event_id = ?
            """,
            (event_id,),
        )
        if row is None:
            return None
        return self._row_to_outbox_record(row)

    def list_outbox_events(
        self,
        *,
        state: str | None = "pending",
        limit: int = 100,
    ) -> list[ControlOutboxRecord]:
        page_size = max(1, min(int(limit), 500))
        sql = """
            SELECT
                event_id,
                topic,
                event_key,
                state,
                job_id,
                run_id,
                payload_json,
                created_at,
                published_at,
                attempt,
                error_message
            FROM control_outbox_events
        """
        params: tuple[Any, ...]
        if state is not None:
            sql += " WHERE state = ?"
            params = (state, page_size)
            sql += " ORDER BY created_at ASC LIMIT ?"
        else:
            params = (page_size,)
            sql += " ORDER BY created_at ASC LIMIT ?"
        rows = self._fetchall(sql, params)
        return [self._row_to_outbox_record(row) for row in rows]

    def mark_outbox_published(self, *, event_id: str) -> None:
        now = _utc_now()
        self._execute(
            """
            UPDATE control_outbox_events
            SET state = ?, published_at = ?, attempt = attempt + 1, error_message = NULL
            WHERE event_id = ?
            """,
            ("published", _iso(now), event_id),
        )

    def _get_outbox_event_by_key(self, *, topic: str, event_key: str) -> ControlOutboxRecord | None:
        row = self._fetchone(
            """
            SELECT
                event_id,
                topic,
                event_key,
                state,
                job_id,
                run_id,
                payload_json,
                created_at,
                published_at,
                attempt,
                error_message
            FROM control_outbox_events
            WHERE topic = ? AND event_key = ?
            """,
            (topic, event_key),
        )
        if row is None:
            return None
        return self._row_to_outbox_record(row)

    def _row_to_record(self, row: Any) -> ControlJobRecord:
        progress_json = row["progress_json"] if "progress_json" in row.keys() else "{}"
        policy_flags_json = row["policy_flags_json"] if "policy_flags_json" in row.keys() else "{}"
        return ControlJobRecord(
            job_id=str(row["job_id"]),
            kind=str(row["job_kind"]),  # type: ignore[arg-type]
            state=str(row["state"]),  # type: ignore[arg-type]
            run_id=row["run_id"],
            pipeline_id=row["pipeline_id"],
            requested_execution_profile=row["requested_profile"],
            effective_execution_profile=row["effective_profile"],
            policy_flags=json.loads(policy_flags_json or "{}"),
            capability_manifest_ref=row["capability_manifest_ref"],
            payload_ref=row["payload_ref"],
            submitted_by=row["submitted_by"],
            created_at=_parse_dt(row["created_at"]) or _utc_now(),
            started_at=_parse_dt(row["started_at"]),
            finished_at=_parse_dt(row["finished_at"]),
            lease_owner=row["lease_owner"],
            lease_expires_at=_parse_dt(row["lease_expires_at"]),
            attempt=int(row["attempt"] or 0),
            error_message=row["error_message"],
            progress=json.loads(progress_json or "{}"),
        )

    def _row_to_worker_lease(self, row: Any) -> ControlWorkerLeaseRecord:
        metadata_json = row["metadata_json"] if "metadata_json" in row.keys() else "{}"
        return ControlWorkerLeaseRecord(
            worker_id=str(row["worker_id"]),
            state=str(row["state"] or "unknown"),
            backend=row["backend"],
            active_job_id=row["active_job_id"],
            metadata=json.loads(metadata_json or "{}"),
            heartbeat_at=_parse_dt(row["heartbeat_at"]) or _utc_now(),
            lease_expires_at=_parse_dt(row["lease_expires_at"]) or _utc_now(),
            created_at=_parse_dt(row["created_at"]) or _utc_now(),
            updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
        )

    def _row_to_outbox_record(self, row: Any) -> ControlOutboxRecord:
        payload_json = row["payload_json"] if "payload_json" in row.keys() else "{}"
        return ControlOutboxRecord(
            event_id=str(row["event_id"]),
            topic=str(row["topic"]),
            event_key=row["event_key"],
            state=str(row["state"] or "pending"),
            job_id=row["job_id"],
            run_id=row["run_id"],
            payload=json.loads(payload_json or "{}"),
            created_at=_parse_dt(row["created_at"]) or _utc_now(),
            published_at=_parse_dt(row["published_at"]),
            attempt=int(row["attempt"] or 0),
            error_message=row["error_message"],
        )

    def _emit_job_outbox_event(
        self,
        *,
        record: ControlJobRecord,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        topic = _job_event_topic(event_type)
        event_key = None if event_type == "job_progress" else f"{record.job_id}:{event_type}"
        outbox_payload = {
            "job_id": record.job_id,
            "job_kind": record.kind,
            "run_id": record.run_id,
            "pipeline_id": record.pipeline_id,
            "effective_execution_profile": record.effective_execution_profile,
            **payload,
        }
        self.enqueue_outbox_event(
            topic=topic,
            event_key=event_key,
            job_id=record.job_id,
            run_id=record.run_id,
            payload=outbox_payload,
        )

    def _lease_next_sqlite(self, *, worker_id: str, lease_seconds: int) -> ControlJobRecord | None:
        assert self._sqlite_conn is not None
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        with self._lock:
            self._sqlite_conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._sqlite_conn.execute(
                    """
                    SELECT job_id
                    FROM control_jobs
                    WHERE state = 'pending'
                       OR (state = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?)
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (_iso(now),),
                ).fetchone()
                if row is None:
                    self._sqlite_conn.execute("COMMIT")
                    return None
                job_id = str(row["job_id"])
                self._sqlite_conn.execute(
                    """
                    UPDATE control_jobs
                    SET state = 'running',
                        started_at = COALESCE(started_at, ?),
                        lease_owner = ?,
                        lease_expires_at = ?,
                        attempt = attempt + 1
                    WHERE job_id = ?
                    """,
                    (_iso(now), worker_id, _iso(lease_expires_at), job_id),
                )
                self._sqlite_conn.execute("COMMIT")
            except Exception:
                self._sqlite_conn.execute("ROLLBACK")
                raise
        return self.get_job(job_id)

    def _lease_next_postgres(self, *, worker_id: str, lease_seconds: int) -> ControlJobRecord | None:
        now = _utc_now()
        lease_expires_at = now + timedelta(seconds=max(lease_seconds, 1))
        with self._postgres_cursor() as cur:
            cur.execute(
                """
                WITH candidate AS (
                    SELECT job_id
                    FROM control_jobs
                    WHERE state = 'pending'
                       OR (state = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= %s)
                    ORDER BY created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE control_jobs j
                SET state = 'running',
                    started_at = COALESCE(started_at, %s),
                    lease_owner = %s,
                    lease_expires_at = %s,
                    attempt = attempt + 1
                FROM candidate
                WHERE j.job_id = candidate.job_id
                RETURNING j.job_id
                """,
                (_iso(now), _iso(now), worker_id, _iso(lease_expires_at)),
            )
            row = cur.fetchone()
            if row is None:
                return None
            job_id = row[0]
        return self.get_job(str(job_id))

    def _ensure_sqlite_schema(self) -> None:
        assert self._sqlite_conn is not None
        self._sqlite_conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS control_jobs (
                job_id TEXT PRIMARY KEY,
                job_kind TEXT NOT NULL,
                state TEXT NOT NULL,
                run_id TEXT,
                pipeline_id TEXT,
                requested_profile TEXT,
                effective_profile TEXT NOT NULL,
                policy_flags_json TEXT NOT NULL,
                capability_manifest_ref TEXT,
                payload_ref TEXT,
                submitted_by TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                lease_owner TEXT,
                lease_expires_at TEXT,
                attempt INTEGER NOT NULL DEFAULT 0,
                error_message TEXT
            );
            CREATE TABLE IF NOT EXISTS control_job_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS control_job_progress (
                job_id TEXT PRIMARY KEY,
                progress_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS control_worker_leases (
                worker_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                backend TEXT,
                active_job_id TEXT,
                metadata_json TEXT NOT NULL,
                heartbeat_at TEXT NOT NULL,
                lease_expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS control_outbox_events (
                event_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                event_key TEXT,
                state TEXT NOT NULL,
                job_id TEXT,
                run_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                published_at TEXT,
                attempt INTEGER NOT NULL DEFAULT 0,
                error_message TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_control_jobs_state_created_at
                ON control_jobs(state, created_at);
            CREATE INDEX IF NOT EXISTS idx_control_jobs_pipeline_id
                ON control_jobs(pipeline_id);
            CREATE INDEX IF NOT EXISTS idx_control_worker_leases_expires_at
                ON control_worker_leases(lease_expires_at);
            CREATE INDEX IF NOT EXISTS idx_control_outbox_state_created_at
                ON control_outbox_events(state, created_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_control_outbox_topic_event_key
                ON control_outbox_events(topic, event_key)
                WHERE event_key IS NOT NULL;
            """
        )
        self._sqlite_conn.commit()

    def _ensure_postgres_schema(self) -> None:
        with self._postgres_cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_kind TEXT NOT NULL,
                    state TEXT NOT NULL,
                    run_id TEXT,
                    pipeline_id TEXT,
                    requested_profile TEXT,
                    effective_profile TEXT NOT NULL,
                    policy_flags_json TEXT NOT NULL,
                    capability_manifest_ref TEXT,
                    payload_ref TEXT,
                    submitted_by TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    started_at TIMESTAMPTZ,
                    finished_at TIMESTAMPTZ,
                    lease_owner TEXT,
                    lease_expires_at TIMESTAMPTZ,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_job_events (
                    event_id BIGSERIAL PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_job_progress (
                    job_id TEXT PRIMARY KEY,
                    progress_json TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_worker_leases (
                    worker_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    backend TEXT,
                    active_job_id TEXT,
                    metadata_json TEXT NOT NULL,
                    heartbeat_at TIMESTAMPTZ NOT NULL,
                    lease_expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS control_outbox_events (
                    event_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    event_key TEXT,
                    state TEXT NOT NULL,
                    job_id TEXT,
                    run_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    published_at TIMESTAMPTZ,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_control_worker_leases_expires_at
                ON control_worker_leases(lease_expires_at)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_control_outbox_state_created_at
                ON control_outbox_events(state, created_at)
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_control_outbox_topic_event_key
                ON control_outbox_events(topic, event_key)
                WHERE event_key IS NOT NULL
                """
            )

    def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        if self.backend == "sqlite":
            assert self._sqlite_conn is not None
            with self._lock:
                self._sqlite_conn.execute(sql, params)
                self._sqlite_conn.commit()
            return
        with self._postgres_cursor() as cur:
            cur.execute(self._translate_sql(sql), params)

    def _fetchone(self, sql: str, params: tuple[Any, ...]) -> Any:
        if self.backend == "sqlite":
            assert self._sqlite_conn is not None
            with self._lock:
                return self._sqlite_conn.execute(sql, params).fetchone()
        with self._postgres_cursor() as cur:
            cur.execute(self._translate_sql(sql), params)
            row = cur.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in (cur.description or ())]
            return {column: value for column, value in zip(columns, row, strict=False)}

    def _fetchall(self, sql: str, params: tuple[Any, ...]) -> list[Any]:
        if self.backend == "sqlite":
            assert self._sqlite_conn is not None
            with self._lock:
                return list(self._sqlite_conn.execute(sql, params).fetchall())
        with self._postgres_cursor() as cur:
            cur.execute(self._translate_sql(sql), params)
            rows = cur.fetchall()
            columns = [desc[0] for desc in (cur.description or ())]
            return [
                {column: value for column, value in zip(columns, row, strict=False)}
                for row in rows
            ]

    @staticmethod
    def _translate_sql(sql: str) -> str:
        return sql.replace("?", "%s")

    @contextmanager
    def _postgres_cursor(self) -> Iterator[Any]:
        if not self._postgres_dsn:
            raise RuntimeError("PostgreSQL control-plane store requires a DSN")
        try:
            import psycopg
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgreSQL control-plane store") from exc
        with psycopg.connect(self._postgres_dsn, autocommit=False) as conn:
            with conn.cursor() as cur:
                try:
                    yield cur
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise


__all__ = [
    "ControlJobRecord",
    "ControlOutboxRecord",
    "ControlPlaneStore",
    "ControlWorkerLeaseRecord",
]
