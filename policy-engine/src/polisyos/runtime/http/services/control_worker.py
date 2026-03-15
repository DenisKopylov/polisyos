from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from contextlib import suppress

from polisyos.common.logger import get_logger

from .control_plane_store import ControlJobRecord, ControlPlaneStore

logger = get_logger(__name__)

JobHandler = Callable[[ControlJobRecord], None]


class ControlWorker:
    def __init__(
        self,
        *,
        store: ControlPlaneStore,
        handler: JobHandler,
        poll_interval_s: float = 0.25,
        lease_seconds: int = 60,
        worker_id: str | None = None,
    ) -> None:
        self._store = store
        self._handler = handler
        self._poll_interval_s = max(poll_interval_s, 0.05)
        self._lease_seconds = max(lease_seconds, 1)
        self._heartbeat_interval_s = min(max(self._lease_seconds / 3.0, 0.1), 5.0)
        self._worker_id = worker_id or f"ctrl-worker-{uuid.uuid4().hex[:8]}"
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def start(self) -> None:
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
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._store.release_worker(worker_id=self._worker_id)

    def wake(self) -> None:
        self._wake.set()

    def dispatch_once(self) -> bool:
        self._heartbeat(state="idle")
        job = self._store.lease_next_job(worker_id=self._worker_id, lease_seconds=self._lease_seconds)
        if job is None:
            return False
        logger.debug("Control worker %s picked job %s", self._worker_id, job.job_id)
        self._run_with_lease_heartbeat(job)
        return True

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            ran = False
            try:
                ran = self.dispatch_once()
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
                except Exception as exc:  # pragma: no cover - defensive loop guard
                    logger.exception("Control worker heartbeat failed for job %s: %s", job.job_id, exc)

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
            stop_heartbeat.set()
            with suppress(RuntimeError):
                heartbeat_thread.join(timeout=max(self._heartbeat_interval_s * 2.0, 0.2))
            self._heartbeat(
                state="idle",
                metadata={"last_job_id": job.job_id},
            )

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


__all__ = ["ControlWorker"]
