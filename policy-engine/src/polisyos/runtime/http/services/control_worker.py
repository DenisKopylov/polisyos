"""Lease and execute durable control-plane jobs from an embedded worker thread."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from time import monotonic

from polisyos.common.logger import get_logger
from polisyos.runtime.http.errors import (
    RuntimeDependencyTimeoutError,
    RuntimeDependencyUnavailableError,
)
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    SERIOUS_EXECUTION_PROFILES,
    DiagnosticEvent,
)

from .control_plane_store import ControlJobRecord, ControlPlaneStore

logger = get_logger(__name__)

JobHandler = Callable[[ControlJobRecord], None]
MaintenanceCallback = Callable[[], None]


def _job_progress_details(job: ControlJobRecord) -> dict[str, object]:
    progress = job.progress if isinstance(job.progress, dict) else {}
    details = progress.get("details")
    return dict(details) if isinstance(details, dict) else {}


def _worker_trace_context(job: ControlJobRecord) -> dict[str, str | None]:
    details = _job_progress_details(job)
    trace_payload = details.get("runtime_trace")
    if not isinstance(trace_payload, dict):
        trace_payload = details.get("_telemetry")
    trace = trace_payload if isinstance(trace_payload, dict) else {}
    trace_id = trace.get("trace_id") or details.get("trace_id") or f"trace_{job.job_id}"
    parent_span_id = (
        trace.get("parent_span_id")
        or details.get("parent_span_id")
        or trace.get("span_id")
        or details.get("span_id")
    )
    return {
        "trace_id": str(trace_id),
        "span_id": f"span_{uuid.uuid4().hex[:16]}",
        "parent_span_id": str(parent_span_id) if parent_span_id else None,
    }


def _worker_tenant_context(job: ControlJobRecord) -> tuple[str, str]:
    details = _job_progress_details(job)
    tenant_id = details.get("tenant_id") or details.get("tenant")
    cell_id = details.get("cell_id") or details.get("cell")
    return (
        str(tenant_id or "tenant-unknown"),
        str(cell_id or "cell-unknown"),
    )


def _worker_handoff_refs(job: ControlJobRecord) -> tuple[str, ...]:
    progress = job.progress if isinstance(job.progress, dict) else {}
    handoffs = progress.get("evidence_spine_handoffs")
    refs: list[str] = []
    if isinstance(handoffs, list):
        for handoff in handoffs:
            if not isinstance(handoff, dict):
                continue
            for key in ("input_refs", "output_refs", "carrier_ref"):
                value = handoff.get(key)
                values = value if isinstance(value, list) else [value]
                for item in values:
                    text = str(item or "").strip()
                    if text and text not in refs:
                        refs.append(text)
    return tuple(refs)


class ControlWorker:
    """Run a single embedded worker loop with lease renewal and wakeup signaling."""

    def __init__(
        self,
        *,
        store: ControlPlaneStore,
        handler: JobHandler,
        poll_interval_s: float = 0.25,
        lease_seconds: int = 60,
        worker_id: str | None = None,
        maintenance_callback: MaintenanceCallback | None = None,
        maintenance_interval_s: float = 60.0,
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self._store = store
        self._handler = handler
        self._poll_interval_s = max(poll_interval_s, 0.05)
        self._lease_seconds = max(lease_seconds, 1)
        self._heartbeat_interval_s = min(max(self._lease_seconds / 3.0, 0.1), 5.0)
        self._worker_id = worker_id or f"ctrl-worker-{uuid.uuid4().hex[:8]}"
        self._maintenance_callback = maintenance_callback
        self._maintenance_interval_s = max(maintenance_interval_s, self._poll_interval_s)
        self._monotonic_clock = monotonic_clock
        self._next_maintenance_at = 0.0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()

    @property
    def worker_id(self) -> str:
        """Return the stable worker lease identifier registered in the control store."""
        return self._worker_id

    def start(self) -> None:
        """Start the daemon worker thread if it is not already running."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._heartbeat(state="idle")
        self._thread = threading.Thread(
            target=self._run_loop,
            name=self._worker_id,
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, timeout: float = 2.0) -> None:
        """Stop the worker loop, join the thread, and release the lease row."""
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        try:
            self._store.release_worker(worker_id=self._worker_id)
        except (RuntimeDependencyTimeoutError, RuntimeDependencyUnavailableError) as exc:
            logger.debug("Control worker lease release skipped during shutdown: %s", exc)

    def wake(self) -> None:
        """Wake the polling loop so newly queued jobs are leased immediately."""
        self._wake.set()

    def dispatch_once(self) -> bool:
        """Lease and process one job, returning `True` when work was executed."""
        self._heartbeat(state="idle")
        job = self._store.lease_next_job(
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
        )
        if job is None:
            return False
        logger.debug("Control worker %s picked job %s", self._worker_id, job.job_id)
        self._emit_worker_diagnostic_event(
            job=job,
            phase="worker_dispatch",
            state_after="leased",
        )
        self._run_with_lease_heartbeat(job)
        return True

    def run_maintenance_once(self) -> bool:
        """Run one due maintenance callback without requiring a queued control request."""

        if self._maintenance_callback is None:
            return False
        now = self._monotonic_clock()
        if now < self._next_maintenance_at:
            return False
        self._next_maintenance_at = now + self._maintenance_interval_s
        self._maintenance_callback()
        return True

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            ran = False
            try:
                self.run_maintenance_once()
                ran = self.dispatch_once()
            except (RuntimeDependencyTimeoutError, RuntimeDependencyUnavailableError) as exc:
                logger.warning("Control worker dependency unavailable: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive loop guard
                logger.exception("Control worker loop failed: %s", exc)
            if ran:
                continue
            self._wake.wait(timeout=self._poll_interval_s)
            self._wake.clear()

    def _run_with_lease_heartbeat(self, job: ControlJobRecord) -> None:
        stop_heartbeat = threading.Event()

        def _lease_pulse() -> None:
            while not stop_heartbeat.wait(self._heartbeat_interval_s):
                try:
                    self._store.renew_job_lease(
                        job_id=job.job_id,
                        worker_id=self._worker_id,
                        lease_seconds=self._lease_seconds,
                    )
                    self._heartbeat(
                        state="running",
                        active_job_id=job.job_id,
                        metadata={"job_kind": job.kind},
                    )
                except (RuntimeDependencyTimeoutError, RuntimeDependencyUnavailableError) as exc:
                    if self._stop.is_set():
                        return
                    logger.warning(
                        "Control worker heartbeat stopped for job %s because the store "
                        "became unavailable: %s",
                        job.job_id,
                        exc,
                    )
                    return
                except Exception as exc:  # pragma: no cover - defensive loop guard
                    logger.exception(
                        "Control worker heartbeat failed for job %s: %s",
                        job.job_id,
                        exc,
                    )

        self._heartbeat(
            state="running",
            active_job_id=job.job_id,
            metadata={"job_kind": job.kind},
        )
        heartbeat_thread = threading.Thread(
            target=_lease_pulse,
            name=f"{self._worker_id}-heartbeat",
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            self._handler(job)
        finally:
            self._emit_worker_diagnostic_event(
                job=job,
                phase="worker_dispatch",
                state_after="released",
            )
            stop_heartbeat.set()
            with suppress(RuntimeError):
                heartbeat_thread.join(timeout=max(self._heartbeat_interval_s * 2.0, 0.2))
            try:
                self._heartbeat(
                    state="idle",
                    metadata={"last_job_id": job.job_id},
                )
            except (RuntimeDependencyTimeoutError, RuntimeDependencyUnavailableError):
                if not self._stop.is_set():
                    raise

    def _heartbeat(
        self,
        *,
        state: str,
        active_job_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self._store.heartbeat_worker(
            worker_id=self._worker_id,
            state=state,
            backend="embedded",
            active_job_id=active_job_id,
            lease_seconds=self._lease_seconds,
            metadata=metadata or {},
        )

    def _emit_worker_diagnostic_event(
        self,
        *,
        job: ControlJobRecord,
        phase: str,
        state_after: str,
    ) -> None:
        append_event = getattr(self._store, "append_diagnostic_event", None)
        if not callable(append_event):
            return
        trace = _worker_trace_context(job)
        tenant_id, cell_id = _worker_tenant_context(job)
        try:
            append_event(
                event=DiagnosticEvent(
                    event_id=f"evt_worker_{uuid.uuid4().hex[:16]}",
                    event_source="polisyos.runtime.worker",
                    event_type="polisyos.runtime.diagnostic.producer_execution.v1",
                    event_time=datetime.now(UTC).replace(microsecond=0),
                    event_subject=(
                        f"run/{job.run_id or 'run-unknown'}/job/{job.job_id}/phase/{phase}"
                    ),
                    schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
                    schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
                    trace_id=str(trace["trace_id"]),
                    span_id=str(trace["span_id"]),
                    parent_span_id=(
                        str(trace["parent_span_id"]) if trace.get("parent_span_id") else None
                    ),
                    run_id=str(job.run_id or "run-unknown"),
                    job_id=job.job_id,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    producer_component="polisyos.runtime.control_worker",
                    producer_version="2026.05.15+hds-phase2.2",
                    execution_profile=job.effective_execution_profile,
                    phase=phase,
                    state_before=job.state,
                    state_after=state_after,
                    payload_ref=None,
                    artifact_refs=(),
                    input_refs=_worker_handoff_refs(job),
                    blocking_status=None,
                    redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
                    duplicate_of=None,
                    dedupe_key=None,
                    sampling_decision="always_record",
                    sampling_rate=1.0,
                ),
            )
        except Exception as exc:  # pragma: no cover - worker diagnostics are best effort
            if job.effective_execution_profile.strip().casefold() in SERIOUS_EXECUTION_PROFILES:
                raise RuntimeError(
                    f"worker_diagnostic_event_persistence_failed:{job.job_id}:{phase}"
                ) from exc
            logger.debug(
                "Control worker diagnostic event skipped for job %s: %s",
                job.job_id,
                exc,
            )


__all__ = ["ControlWorker"]
