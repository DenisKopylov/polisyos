from __future__ import annotations

from typing import Any

from polisyos.runtime.http.services.control.admission import (
    _record_control_plane_job_admission_metric,
    _record_control_plane_job_execution_metric,
)


class _RecordingMetrics:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, Any]]] = []

    def record_control_plane_job_admission(self, **values: Any) -> None:
        self.records.append(("admission", values))

    def record_control_plane_job_execution(self, **values: Any) -> None:
        self.records.append(("execution", values))


def test_admission_and_execution_metrics_preserve_the_observed_fields() -> None:
    metrics = _RecordingMetrics()

    _record_control_plane_job_admission_metric(
        metrics=metrics,
        job_kind="fixture.job",
        effective_profile="fixture.profile",
        status="fixture.admission-status",
        duration_seconds=0.125,
    )
    _record_control_plane_job_execution_metric(
        metrics=metrics,
        job_kind="fixture.job",
        status="fixture.execution-status",
        duration_seconds=0.75,
        queue_lag_seconds=0.25,
    )

    assert metrics.records == [
        (
            "admission",
            {
                "job_kind": "fixture.job",
                "effective_profile": "fixture.profile",
                "status": "fixture.admission-status",
                "duration_seconds": 0.125,
            },
        ),
        (
            "execution",
            {
                "job_kind": "fixture.job",
                "status": "fixture.execution-status",
                "duration_seconds": 0.75,
                "queue_lag_seconds": 0.25,
            },
        ),
    ]
