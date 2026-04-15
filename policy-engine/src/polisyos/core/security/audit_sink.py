"""Public security audit sink module API."""
from __future__ import annotations

import importlib
import json
import os
import queue
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics

from .audit_models import (
    AuditActor,
    AuditCorrelation,
    AuditEventType,
    AuditResource,
    ChainedLogEntry,
)

logger = get_logger("polisyos.security.audit_sink")

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.observability import MetricsRegistry
    from polisyos.core.trace.record import TraceRecord


class AuditStorageBackend(Protocol):
    """Remote/secondary storage backend for chained audit entries."""

    def write(self, entry: ChainedLogEntry) -> None:  # pragma: no cover - protocol
        ...

    def flush(self) -> None:  # pragma: no cover - protocol
        ...


class LocalJsonlBackend:
    """Durable local append-only audit log backend."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def write(self, entry: ChainedLogEntry) -> None:
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json(exclude_none=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def flush(self) -> None:
        return None

    def read_last_valid(self, *, chain_id: str) -> ChainedLogEntry | None:
        if not self._path.exists() or self._path.stat().st_size == 0:
            return None

        try:
            lines = _read_tail_lines(self._path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            logger.debug("Failed to read audit tail lines: %s", exc)
            return None

        for raw in reversed(lines):
            if not raw.strip():
                continue
            try:
                entry = ChainedLogEntry.model_validate_json(raw)
            except (TypeError, ValueError):
                continue
            if entry.chain_id != chain_id:
                continue
            if entry.compute_hash() != entry.entry_hash:
                continue
            return entry
        return None


class HotTierBackend:
    """Bulk HTTP backend for hot retention tier (e.g. Elasticsearch/Loki)."""

    def __init__(self, endpoint: str, *, index_prefix: str = "polisyos-audit") -> None:
        self._endpoint = endpoint.rstrip("/")
        self._index_prefix = index_prefix
        self._buffer: list[ChainedLogEntry] = []
        self._lock = threading.RLock()
        self._buffer_limit = 128

    def write(self, entry: ChainedLogEntry) -> None:
        with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self._buffer_limit:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer:
            return

        try:
            import httpx

            chunks: list[str] = []
            for item in self._buffer:
                action = {
                    "index": {
                        "_index": f"{self._index_prefix}-{item.timestamp[:10]}"
                    }
                }
                chunks.append(json.dumps(action, sort_keys=True))
                chunks.append(item.model_dump_json(exclude_none=True))

            body = "\n".join(chunks) + "\n"
            response = httpx.post(
                f"{self._endpoint}/_bulk",
                content=body,
                headers={"Content-Type": "application/x-ndjson"},
                timeout=15.0,
            )
            response.raise_for_status()
            self._buffer.clear()
        except Exception:
            logger.error(
                "HotTierBackend flush failed, %d audit entries retained for retry",
                len(self._buffer),
            )
            raise


class ColdTierBackend:
    """S3/Object Lock backend for long-term immutable retention."""

    def __init__(self, bucket: str, *, prefix: str = "audit", region: str = "us-east-1") -> None:
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._region = region
        self._buffer: list[ChainedLogEntry] = []
        self._lock = threading.RLock()
        self._buffer_limit = 512
        self._segment_hour: str | None = None

    @property
    def bucket(self) -> str:
        return self._bucket

    def write(self, entry: ChainedLogEntry) -> None:
        with self._lock:
            hour = entry.timestamp[:13]
            if self._segment_hour is None:
                self._segment_hour = hour
            if self._segment_hour != hour:
                self._flush_locked()
                self._segment_hour = hour
            self._buffer.append(entry)
            if len(self._buffer) >= self._buffer_limit:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer:
            return

        try:
            client = _load_boto3_s3_client(region_name=self._region)
            segment = (self._segment_hour or "unknown").replace(":", "")
            key = f"{self._prefix}/{segment}/audit-{int(time.time() * 1000)}.jsonl"
            body = "\n".join(item.model_dump_json(exclude_none=True) for item in self._buffer) + "\n"

            retain_until = datetime(
                datetime.now(UTC).year + 7,
                1,
                1,
                tzinfo=UTC,
            )
            client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body.encode("utf-8"),
                ContentType="application/x-ndjson",
                ObjectLockMode="COMPLIANCE",
                ObjectLockRetainUntilDate=retain_until,
            )
            self._buffer.clear()
        except Exception:
            logger.error(
                "ColdTierBackend flush failed, %d audit entries retained for retry",
                len(self._buffer),
            )
            raise


class ChainedAuditSink:
    """TraceSink-compatible chained audit sink with restart recovery."""

    def __init__(
        self,
        *,
        chain_id: str,
        local_path: Path,
        backends: list[AuditStorageBackend] | None = None,
        queue_size: int = 50_000,
        enqueue_timeout_seconds: float = 3.0,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._chain_id = chain_id
        self._local = LocalJsonlBackend(local_path)
        self._lock = threading.RLock()
        self._sequence = 0
        self._prev_hash = ChainedLogEntry.genesis_prev_hash()
        self._enqueue_timeout = enqueue_timeout_seconds
        self._metrics = metrics or get_metrics()

        self._replica_backends = backends or []
        self._queue: queue.Queue[ChainedLogEntry | None] = queue.Queue(maxsize=queue_size)
        self._closed = False

        self._recover_state()

        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="polisyos-audit-replica-writer",
            daemon=True,
        )
        self._writer_thread.start()

    def emit(self, rec: TraceRecord) -> None:
        entry = self._chain_entry(
            event_type=AuditEventType.TRACE_RECORD,
            payload=rec.model_dump(mode="json", exclude_none=True),
            correlation=AuditCorrelation(
                run_id=rec.run_id,
                span_id=rec.span_id or "",
            ),
        )
        self._append_and_enqueue(entry)

    def log_audit_event(
        self,
        *,
        event_type: AuditEventType,
        payload: dict[str, Any] | None = None,
        actor: AuditActor | None = None,
        resource: AuditResource | None = None,
        correlation: AuditCorrelation | None = None,
    ) -> ChainedLogEntry:
        entry = self._chain_entry(
            event_type=event_type,
            payload=payload or {},
            actor=actor,
            resource=resource,
            correlation=correlation,
        )
        self._append_and_enqueue(entry)
        return entry

    def _recover_state(self) -> None:
        last = self._local.read_last_valid(chain_id=self._chain_id)
        if last is None:
            return
        self._sequence = last.sequence_number + 1
        self._prev_hash = last.entry_hash
        logger.info(
            "Recovered audit chain state: chain_id=%s sequence=%d",
            self._chain_id,
            self._sequence,
        )

    def _chain_entry(
        self,
        *,
        event_type: AuditEventType,
        payload: dict[str, Any],
        actor: AuditActor | None = None,
        resource: AuditResource | None = None,
        correlation: AuditCorrelation | None = None,
    ) -> ChainedLogEntry:
        with self._lock:
            entry = ChainedLogEntry.build(
                chain_id=self._chain_id,
                sequence_number=self._sequence,
                prev_hash=self._prev_hash,
                event_type=event_type,
                actor=actor,
                resource=resource,
                payload=payload,
                correlation=correlation,
            )
            self._sequence += 1
            self._prev_hash = entry.entry_hash
        return entry

    def _append_and_enqueue(self, entry: ChainedLogEntry) -> None:
        if self._closed:
            raise RuntimeError("ChainedAuditSink is already closed")

        self._local.write(entry)
        self._metrics.record_audit_entry(
            chain_id=entry.chain_id,
            event_type=entry.event_type.value,
        )
        if not self._replica_backends:
            return

        try:
            self._queue.put(entry, timeout=self._enqueue_timeout)
            self._metrics.set_audit_queue_depth(
                chain_id=self._chain_id,
                depth=self._queue.qsize(),
            )
        except queue.Full:
            spill_path = self._local.path.with_suffix(".spill.jsonl")
            with spill_path.open("a", encoding="utf-8") as handle:
                handle.write(entry.model_dump_json(exclude_none=True))
                handle.write("\n")
                handle.flush()
            logger.error(
                "Audit replica queue full, entry spilled to %s (chain_id=%s seq=%d)",
                spill_path,
                entry.chain_id,
                entry.sequence_number,
            )
            self._metrics.set_audit_queue_depth(
                chain_id=self._chain_id,
                depth=self._queue.qsize(),
            )

    def _writer_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                self._metrics.set_audit_queue_depth(
                    chain_id=self._chain_id,
                    depth=self._queue.qsize(),
                )
                break
            try:
                for backend in self._replica_backends:
                    started = time.perf_counter()
                    try:
                        backend.write(item)
                    except (
                        AttributeError,
                        OSError,
                        RuntimeError,
                        TypeError,
                        ValueError,
                        KeyError,
                    ) as exc:
                        logger.error("Audit replica write failed: %s", exc)
                        self._metrics.record_audit_write_latency(
                            backend=type(backend).__name__,
                            duration_seconds=max(time.perf_counter() - started, 0.0),
                            status="error",
                        )
                        if isinstance(backend, ColdTierBackend):
                            self._metrics.record_audit_cold_tier_error(bucket=backend.bucket)
                    else:
                        self._metrics.record_audit_write_latency(
                            backend=type(backend).__name__,
                            duration_seconds=time.perf_counter() - started,
                            status="ok",
                        )
            finally:
                self._queue.task_done()
                self._metrics.set_audit_queue_depth(
                    chain_id=self._chain_id,
                    depth=self._queue.qsize(),
                )

    def flush(self) -> None:
        self._queue.join()
        for backend in self._replica_backends:
            try:
                backend.flush()
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError, KeyError) as exc:
                logger.error("Audit backend flush failed: %s", exc)

    def close(self) -> None:
        if self._closed:
            return
        self.flush()
        self._closed = True
        self._queue.put(None)
        self._writer_thread.join(timeout=10)



def build_default_audit_backends_from_env() -> list[AuditStorageBackend]:
    """Build default audit backends from env."""
    backends: list[AuditStorageBackend] = []

    hot_url = os.getenv("POLISYOS_AUDIT_HOT_TIER_URL", "").strip()
    if hot_url:
        backends.append(HotTierBackend(hot_url))

    cold_bucket = os.getenv("POLISYOS_AUDIT_COLD_TIER_BUCKET", "").strip()
    if cold_bucket:
        backends.append(
            ColdTierBackend(
                cold_bucket,
                prefix=os.getenv("POLISYOS_AUDIT_COLD_TIER_PREFIX", "audit"),
                region=os.getenv("POLISYOS_AUDIT_COLD_TIER_REGION", "us-east-1"),
            )
        )

    return backends


def _read_tail_lines(path: Path, *, chunk_size: int = 8192) -> list[str]:
    """Read trailing lines without loading the entire file into memory."""
    size = path.stat().st_size
    if size <= 0:
        return []

    data = b""
    with path.open("rb") as handle:
        offset = size
        while offset > 0:
            read_size = min(chunk_size, offset)
            offset -= read_size
            handle.seek(offset)
            data = handle.read(read_size) + data
            if b"\n" in data and len(data) > chunk_size:
                break
    return data.decode("utf-8", errors="ignore").splitlines()


def _load_boto3_s3_client(*, region_name: str) -> Any:
    boto3_module = importlib.import_module("boto3")
    return boto3_module.client("s3", region_name=region_name)
