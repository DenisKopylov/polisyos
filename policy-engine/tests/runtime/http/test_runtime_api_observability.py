from __future__ import annotations

from contextlib import contextmanager

import pytest

from polisyos.core.contracts.control import DataSourceBinding, WorkflowRunRequest
from polisyos.runtime.http import app as runtime_app_module
from polisyos.runtime.http.services import control as control_module


class _FakeTracer:
    @contextmanager
    def start_as_current_span(self, _name: str, attributes=None):  # noqa: ANN001
        _ = attributes
        yield


class _CaptureMetrics:
    def __init__(self) -> None:
        self.runtime_calls: list[dict[str, object]] = []
        self.control_calls: list[dict[str, object]] = []

    def record_runtime_api_request(
        self,
        *,
        route: str,
        method: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        self.runtime_calls.append(
            {
                "route": route,
                "method": method,
                "status": status,
                "duration_seconds": duration_seconds,
            }
        )

    def record_control_plane_job_admission(
        self,
        *,
        job_kind: str,
        effective_profile: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        self.control_calls.append(
            {
                "job_kind": job_kind,
                "effective_profile": effective_profile,
                "status": status,
                "duration_seconds": duration_seconds,
            }
        )


def test_runtime_api_request_metrics_use_templated_route_labels(
    monkeypatch,
    runtime_api_env,
) -> None:
    metrics = _CaptureMetrics()
    monkeypatch.setattr(runtime_app_module, "get_metrics", lambda: metrics)
    monkeypatch.setattr(runtime_app_module, "get_tracer", lambda: _FakeTracer())

    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}")

    assert response.status_code == 200
    assert metrics.runtime_calls
    assert metrics.runtime_calls[-1]["route"] == "/api/v1/runs/{run_id}"
    assert metrics.runtime_calls[-1]["method"] == "GET"
    assert metrics.runtime_calls[-1]["status"] == "200"
    assert isinstance(metrics.runtime_calls[-1]["duration_seconds"], float)


def test_control_plane_admission_metrics_record_success(
    monkeypatch,
    runtime_api_env,
) -> None:
    metrics = _CaptureMetrics()
    monkeypatch.setattr(control_module, "get_metrics", lambda: metrics)

    service = runtime_api_env["app"].state._control_service
    response = service.launch_workflow_run(
        WorkflowRunRequest(
            data_source=DataSourceBinding(
                data_snapshot_ref=runtime_api_env["root_artifact_id"],
            )
        )
    )

    assert response.status == "accepted"
    assert metrics.control_calls
    assert metrics.control_calls[-1]["job_kind"] == "workflow_run"
    assert metrics.control_calls[-1]["effective_profile"] == "dev"
    assert metrics.control_calls[-1]["status"] == "success"
    assert isinstance(metrics.control_calls[-1]["duration_seconds"], float)


def test_control_plane_admission_metrics_record_errors(
    monkeypatch,
    runtime_api_env,
) -> None:
    metrics = _CaptureMetrics()
    monkeypatch.setattr(control_module, "get_metrics", lambda: metrics)

    service = runtime_api_env["app"].state._control_service

    def _fail_create_job(**_kwargs):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr(service._control_store, "create_job", _fail_create_job)  # noqa: SLF001

    with pytest.raises(RuntimeError, match="boom"):
        service.launch_workflow_run(
            WorkflowRunRequest(
                data_source=DataSourceBinding(
                    data_snapshot_ref=runtime_api_env["root_artifact_id"],
                )
            )
        )

    assert metrics.control_calls
    assert metrics.control_calls[-1]["job_kind"] == "workflow_run"
    assert metrics.control_calls[-1]["effective_profile"] == "dev"
    assert metrics.control_calls[-1]["status"] == "error"
    assert isinstance(metrics.control_calls[-1]["duration_seconds"], float)
