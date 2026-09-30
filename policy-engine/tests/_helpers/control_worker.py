"""Small production-equivalent dispatch helper for control-worker tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobRecord,
        ControlPlaneStore,
    )


def stop_embedded_control_worker(service: object) -> None:
    """Stop a service-owned worker before a deterministic test dispatch.

    Served tests that inject a caller context must stop the service's polling
    thread before enqueueing work. Otherwise it can claim the job before the
    test worker is dispatched under the context being measured.
    """
    from polisyos.runtime.http.services.control_worker import ControlWorker

    worker = getattr(service, "_worker", None)
    if isinstance(worker, ControlWorker):
        worker.stop()


def dispatch_one_control_job(
    *,
    store: ControlPlaneStore,
    handler: Callable[[ControlJobRecord], None],
    expected_job_id: str | None = None,
) -> str | None:
    """Lease and dispatch one queued job through the real embedded worker.

    Args:
        store: The same control-plane store used by the service under test.
        handler: The service's production job handler.
        expected_job_id: If supplied, fail before invoking the handler when the
            next queued job is not the expected job.

    Returns:
        The dispatched job ID, or ``None`` when no job was available.
    """
    from polisyos.runtime.http.services.control_worker import ControlWorker

    bound_service = getattr(handler, "__self__", None)
    if bound_service is not None:
        stop_embedded_control_worker(bound_service)

    selected_job_ids: list[str] = []

    def dispatch_expected(job: ControlJobRecord) -> None:
        selected_job_ids.append(job.job_id)
        if expected_job_id is not None and job.job_id != expected_job_id:
            raise AssertionError(
                f"expected queued job {expected_job_id}, received {job.job_id}"
            )
        handler(job)

    worker = ControlWorker(
        store=store,
        handler=dispatch_expected,
        worker_id=f"test-control-worker-{uuid4().hex[:12]}",
    )
    try:
        dispatched = worker.dispatch_once()
        if not dispatched:
            if selected_job_ids:
                raise AssertionError("worker handler ran without dispatching a job")
            if expected_job_id is not None:
                raise AssertionError(
                    f"expected queued job {expected_job_id}, but no job was dispatched"
                )
            return None
        if len(selected_job_ids) != 1:
            raise AssertionError(
                f"expected exactly one worker dispatch; selected={selected_job_ids!r}"
            )
        if expected_job_id is not None and selected_job_ids[0] != expected_job_id:
            raise AssertionError(
                f"expected queued job {expected_job_id}, received {selected_job_ids[0]}"
            )
        return selected_job_ids[0]
    finally:
        worker.stop()
