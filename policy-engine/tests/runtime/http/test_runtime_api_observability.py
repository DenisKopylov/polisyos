from __future__ import annotations

import json
import time
from contextlib import contextmanager

import pytest
from polisyos_tests_runtime_http_conftest import build_runtime_api_env

from polisyos.core.contracts.control import DataSourceBinding, WorkflowRunRequest
from polisyos.core.observability import get_tracer
from polisyos.runtime.http import container as runtime_container
from polisyos.runtime.http.services.control import ControlPlaneService


class _FakeTracer:
    class _Span:
        def set_attribute(self, _name: str, _value: object) -> None:
            return None

    @contextmanager
    def start_as_current_span(self, _name: str, attributes=None):
        _ = attributes
        yield self._Span()


class _CaptureMetrics:
    def __init__(self) -> None:
        self.runtime_calls: list[dict[str, object]] = []
        self.control_calls: list[dict[str, object]] = []
        self.data_access_calls: list[dict[str, object]] = []
        self.cache_events: list[dict[str, object]] = []
        self.cache_rebuilds: list[dict[str, object]] = []
        self.cache_staleness: list[dict[str, object]] = []
        self.rate_limit_events: list[dict[str, object]] = []
        self.live_streams: list[dict[str, object]] = []
        self.audit_events: list[dict[str, object]] = []
        self.control_execution_calls: list[dict[str, object]] = []
        self.ensure_initialized_calls = 0
        self.exporter_health = {"metrics": {"status": "ok", "failures": []}}
        self.artifact_cache_hits_total = None
        self.artifact_cache_misses_total = None
        self.artifact_io_bytes = None
        self.artifact_io_duration_seconds = None
        self.artifact_operations_total = None

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

    def record_runtime_data_access(
        self,
        *,
        resource_kind: str,
        endpoint: str,
        outcome: str,
        tenant_scoped: bool,
    ) -> None:
        self.data_access_calls.append(
            {
                "resource_kind": resource_kind,
                "endpoint": endpoint,
                "outcome": outcome,
                "tenant_scoped": tenant_scoped,
            }
        )

    def record_runtime_cache_event(
        self,
        *,
        cache_name: str,
        operation: str,
        outcome: str,
    ) -> None:
        self.cache_events.append(
            {
                "cache_name": cache_name,
                "operation": operation,
                "outcome": outcome,
            }
        )

    def record_runtime_cache_rebuild(
        self,
        *,
        cache_name: str,
        duration_seconds: float,
        item_count: int,
    ) -> None:
        self.cache_rebuilds.append(
            {
                "cache_name": cache_name,
                "duration_seconds": duration_seconds,
                "item_count": item_count,
            }
        )

    def set_runtime_cache_staleness(
        self,
        *,
        cache_name: str,
        staleness_seconds: float,
    ) -> None:
        self.cache_staleness.append(
            {
                "cache_name": cache_name,
                "staleness_seconds": staleness_seconds,
            }
        )

    def record_runtime_rate_limit_event(
        self,
        *,
        endpoint: str,
        mode: str,
        outcome: str,
    ) -> None:
        self.rate_limit_events.append(
            {
                "endpoint": endpoint,
                "mode": mode,
                "outcome": outcome,
            }
        )

    def set_runtime_live_streams(
        self,
        *,
        endpoint: str,
        active_streams: int,
    ) -> None:
        self.live_streams.append(
            {
                "endpoint": endpoint,
                "active_streams": active_streams,
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

    def record_control_plane_job_execution(
        self,
        *,
        job_kind: str,
        status: str,
        duration_seconds: float,
        queue_lag_seconds: float,
    ) -> None:
        self.control_execution_calls.append(
            {
                "job_kind": job_kind,
                "status": status,
                "duration_seconds": duration_seconds,
                "queue_lag_seconds": queue_lag_seconds,
            }
        )

    def record_audit_entry(self, *, chain_id: str, event_type: str) -> None:
        self.audit_events.append({"chain_id": chain_id, "event_type": event_type})

    def ensure_initialized(self) -> None:
        self.ensure_initialized_calls += 1

    def get_exporter_health(self) -> dict[str, object]:
        return self.exporter_health


def _launch_payload(env: dict[str, object]) -> dict[str, object]:
    return {
        "data_source": {"data_snapshot_ref": env["root_artifact_id"]},
    }


def test_runtime_api_request_metrics_use_templated_route_labels(
    runtime_api_env,
) -> None:
    metrics = _CaptureMetrics()
    tracer = _FakeTracer()
    runtime_api_env["app"].state.runtime_metrics = metrics
    runtime_api_env["app"].state.runtime_tracer = tracer
    runtime_api_env["app"].state.runtime_container.runtime_metrics = metrics
    runtime_api_env["app"].state.runtime_container.runtime_tracer = tracer

    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}")

    assert response.status_code == 200
    assert metrics.runtime_calls
    assert metrics.runtime_calls[-1]["route"] == "/api/v1/runs/{run_id}"
    assert metrics.runtime_calls[-1]["method"] == "GET"
    assert metrics.runtime_calls[-1]["status"] == "200"
    assert isinstance(metrics.runtime_calls[-1]["duration_seconds"], float)


def test_control_plane_admission_metrics_record_success(
    runtime_api_env,
) -> None:
    metrics = _CaptureMetrics()
    service = runtime_api_env["app"].state._control_service
    service._metrics = metrics
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
    service = runtime_api_env["app"].state._control_service
    service._metrics = metrics

    def _fail_create_job(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(service._control_store, "create_job", _fail_create_job)

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


def test_runtime_app_supports_observability_provider_injection(tmp_path) -> None:
    metrics = _CaptureMetrics()
    tracer = _FakeTracer()
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={
            "metrics_factory": lambda: metrics,
            "tracer_factory": lambda: tracer,
        },
    )

    response = env["client"].get(f"/api/v1/runs/{env['core_run_id']}")

    assert response.status_code == 200
    assert env["app"].state.runtime_metrics is metrics
    assert env["app"].state.runtime_tracer is tracer
    assert metrics.ensure_initialized_calls == 1
    assert metrics.runtime_calls


def test_runtime_request_telemetry_keeps_working_without_legacy_state_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    metrics = _CaptureMetrics()
    tracer = _FakeTracer()

    def _explode() -> object:
        raise AssertionError("global observability fallback should not be used")

    monkeypatch.setattr(runtime_container, "get_metrics", _explode)
    monkeypatch.setattr(runtime_container, "get_tracer", _explode)

    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={
            "metrics_factory": lambda: metrics,
            "tracer_factory": lambda: tracer,
        },
    )
    env["app"].state.runtime_metrics = None
    env["app"].state.runtime_tracer = None
    env["app"].state.runtime_container.runtime_metrics = None
    env["app"].state.runtime_container.runtime_tracer = None

    response = env["client"].get(f"/api/v1/runs/{env['core_run_id']}")

    assert response.status_code == 200
    assert metrics.runtime_calls


def test_runtime_data_access_audit_trail_records_reads(tmp_path) -> None:
    metrics = _CaptureMetrics()
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"metrics_factory": lambda: metrics, "tracer_factory": lambda: _FakeTracer()},
    )

    client = env["client"]
    run_response = client.get(f"/api/v1/runs/{env['core_run_id']}")
    artifact_response = client.get(f"/api/v1/artifacts/{env['workflow_report_artifact_id']}")

    assert run_response.status_code == 200
    assert artifact_response.status_code == 200

    audit_path = env["cas_root"] / "runtime" / "audit" / "access.jsonl"
    entries = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]

    assert any(
        entry["resource_kind"] == "runtime.run" and entry["resource_id"] == env["core_run_id"]
        for entry in entries
    )
    assert any(
        entry["resource_kind"] == "runtime.artifact_manifest"
        and entry["resource_id"] == env["workflow_report_artifact_id"]
        for entry in entries
    )
    assert metrics.data_access_calls
    assert any(
        call["resource_kind"] == "runtime.run"
        and call["endpoint"] == f"/api/v1/runs/{env['core_run_id']}"
        for call in metrics.data_access_calls
    )
    assert {"chain_id": "runtime.data_access", "event_type": "read"} in metrics.audit_events


def test_run_index_metrics_capture_rebuild_and_lookup_events(tmp_path) -> None:
    metrics = _CaptureMetrics()
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=False,
        app_kwargs={"metrics_factory": lambda: metrics, "tracer_factory": lambda: _FakeTracer()},
    )
    run_index = env["app"].state.runtime_api_ctx.run_index

    run_index.refresh(force=True)
    _ = run_index.get_run(env["core_run_id"])
    _ = run_index.get_artifact_tenant(env["workflow_report_artifact_id"])

    assert any(
        event["operation"] == "refresh" and event["outcome"] == "incremental_rebuild"
        for event in metrics.cache_events
    )
    assert any(
        event["operation"] == "lookup_run" and event["outcome"] == "hit"
        for event in metrics.cache_events
    )
    assert any(
        event["operation"] == "lookup_artifact_tenant" and event["outcome"] == "hit"
        for event in metrics.cache_events
    )
    assert metrics.cache_rebuilds
    assert metrics.cache_rebuilds[-1]["cache_name"] == "run_index"
    assert metrics.cache_rebuilds[-1]["item_count"] >= 1


def test_ready_endpoint_reports_observability_degradation(tmp_path) -> None:
    metrics = _CaptureMetrics()
    metrics.exporter_health = {
        "metrics": {
            "status": "degraded",
            "failures": ["prometheus exporter dependency missing"],
        }
    }
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"metrics_factory": lambda: metrics, "tracer_factory": lambda: _FakeTracer()},
    )

    response = env["client"].get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["observability"]["metrics"]["status"] == "degraded"
    assert payload["observability"]["metrics"]["failures"] == [
        "prometheus exporter dependency missing"
    ]


def test_runtime_live_stream_rate_limit_metrics_capture_acquire_and_release(tmp_path) -> None:
    metrics = _CaptureMetrics()
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"metrics_factory": lambda: metrics, "tracer_factory": lambda: _FakeTracer()},
    )

    with env["client"].websocket_connect(
        f"/api/v1/review/live?channel=review.presence"
        f"&review_id=run:{env['core_run_id']}:governance"
    ) as websocket:
        assert websocket.receive_json()["type"] == "presence.snapshot"
        assert {
            "endpoint": "live:/api/v1/review/live",
            "mode": "request",
            "outcome": "allowed",
        } in metrics.rate_limit_events
        assert {
            "endpoint": "live:/api/v1/review/live",
            "mode": "concurrency",
            "outcome": "acquired",
        } in metrics.rate_limit_events
        assert any(
            entry["endpoint"] == "live:/api/v1/review/live" and entry["active_streams"] == 1
            for entry in metrics.live_streams
        )

    assert any(
        entry["endpoint"] == "live:/api/v1/review/live" and entry["active_streams"] == 0
        for entry in metrics.live_streams
    )


def test_runs_sse_live_stream_updates_flow_control_metrics(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_LIVE_MIN_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("POLISYOS_RUNTIME_LIVE_MAX_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("POLISYOS_RUNTIME_LIVE_KEEPALIVE_SECONDS", "10")
    monkeypatch.setenv("POLISYOS_RUNTIME_LIVE_MAX_DURATION_SECONDS", "0.15")
    metrics = _CaptureMetrics()
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"metrics_factory": lambda: metrics, "tracer_factory": lambda: _FakeTracer()},
    )

    with env["client"].stream("GET", "/api/v1/runs/live") as response:
        assert response.status_code == 200
        iterator = response.iter_text()
        first_chunk = next(iterator)
        assert "event: snapshot" in first_chunk
        assert {
            "endpoint": "live:/api/v1/runs/live",
            "mode": "request",
            "outcome": "allowed",
        } in metrics.rate_limit_events
        assert {
            "endpoint": "live:/api/v1/runs/live",
            "mode": "concurrency",
            "outcome": "acquired",
        } in metrics.rate_limit_events
        assert any(
            entry["endpoint"] == "live:/api/v1/runs/live" and entry["active_streams"] == 1
            for entry in metrics.live_streams
        )

    assert any(
        entry["endpoint"] == "live:/api/v1/runs/live" and entry["active_streams"] == 0
        for entry in metrics.live_streams
    )


def test_runtime_rate_limit_metrics_capture_throttle(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_WRITE_RATE_LIMIT", "1")
    metrics = _CaptureMetrics()
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"metrics_factory": lambda: metrics, "tracer_factory": lambda: _FakeTracer()},
    )

    first = env["client"].post("/api/v1/control/runs", json=_launch_payload(env))
    second = env["client"].post("/api/v1/control/runs", json=_launch_payload(env))

    assert first.status_code == 200
    assert second.status_code == 429
    assert {
        "endpoint": "POST:/api/v1/control/runs",
        "mode": "request",
        "outcome": "throttled",
    } in metrics.rate_limit_events


def test_control_job_execution_metrics_preserve_trace_context(
    monkeypatch: pytest.MonkeyPatch,
    test_tracer_provider,
    tmp_path,
) -> None:
    metrics = _CaptureMetrics()
    tracer = get_tracer()
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=False,
        app_kwargs={"metrics_factory": lambda: metrics, "tracer_factory": lambda: tracer},
    )
    service = env["app"].state._control_service
    seen: dict[str, str | None] = {"trace_id": None}

    def _capture_workflow(_state_payload, _checkpoint_policy):
        seen["trace_id"] = tracer.get_current_trace_id()

    monkeypatch.setattr(
        ControlPlaneService,
        "_execute_workflow",
        staticmethod(_capture_workflow),
    )

    with tracer.start_as_current_span("runtime.http.test.request"):
        parent_trace_id = tracer.get_current_trace_id()
        response = service.launch_workflow_run(
            WorkflowRunRequest(
                data_source=DataSourceBinding(
                    data_snapshot_ref=env["root_artifact_id"],
                )
            ),
            request_id="req-trace-001",
        )

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        record = service.get_job_status(response.job_id)
        if record.state == "completed":
            break
        time.sleep(0.05)
    else:
        pytest.fail("control job did not complete within timeout")

    assert seen["trace_id"] == parent_trace_id
    assert metrics.control_execution_calls
    assert metrics.control_execution_calls[-1]["job_kind"] == "workflow_run"
    assert metrics.control_execution_calls[-1]["status"] == "success"
    assert metrics.control_execution_calls[-1]["queue_lag_seconds"] >= 0.0
