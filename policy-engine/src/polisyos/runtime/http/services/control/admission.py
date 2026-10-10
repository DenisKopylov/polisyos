"""Runtime control-plane admission helpers."""

from __future__ import annotations

from typing import Protocol


class _ControlPlaneJobAdmissionMetrics(Protocol):
    """Metrics surface used by the admission event recorder."""

    def record_control_plane_job_admission(
        self,
        *,
        job_kind: str,
        effective_profile: str,
        status: str,
        duration_seconds: float,
    ) -> None: ...


class _ControlPlaneJobExecutionMetrics(Protocol):
    """Metrics surface used by the execution event recorder."""

    def record_control_plane_job_execution(
        self,
        *,
        job_kind: str,
        status: str,
        duration_seconds: float,
        queue_lag_seconds: float,
    ) -> None: ...


def _record_control_plane_job_admission_metric(
    *,
    metrics: _ControlPlaneJobAdmissionMetrics | None,
    job_kind: str,
    effective_profile: str,
    status: str,
    duration_seconds: float,
) -> None:
    recorder = getattr(metrics, "record_control_plane_job_admission", None)
    if callable(recorder):
        recorder(
            job_kind=job_kind,
            effective_profile=effective_profile,
            status=status,
            duration_seconds=duration_seconds,
        )


def _record_control_plane_job_execution_metric(
    *,
    metrics: _ControlPlaneJobExecutionMetrics | None,
    job_kind: str,
    status: str,
    duration_seconds: float,
    queue_lag_seconds: float,
) -> None:
    recorder = getattr(metrics, "record_control_plane_job_execution", None)
    if callable(recorder):
        recorder(
            job_kind=job_kind,
            status=status,
            duration_seconds=duration_seconds,
            queue_lag_seconds=queue_lag_seconds,
        )


__all__ = [
    "_record_control_plane_job_admission_metric",
    "_record_control_plane_job_execution_metric",
]
