from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from polisyos.core.observability import get_metrics


class _FakeCounter:
    def __init__(self) -> None:
        self.calls: list[tuple[int | float, dict[str, object] | None]] = []

    def add(self, value: int | float, attrs: dict[str, object] | None = None) -> None:
        self.calls.append((value, attrs))


class _FakeHistogram:
    def __init__(self) -> None:
        self.calls: list[tuple[int | float, dict[str, object] | None]] = []

    def record(self, value: int | float, attrs: dict[str, object] | None = None) -> None:
        self.calls.append((value, attrs))


def test_slo_metric_recording_helpers(monkeypatch) -> None:
    metrics = get_metrics()
    if not callable(getattr(metrics, "record_slo_dag_run", None)):
        pytest.skip("OTel metrics backend is unavailable in this environment")
    monkeypatch.setattr(metrics, "_ensure_initialized", lambda: None)
    metrics._config = SimpleNamespace(environment="test")  # type: ignore[attr-defined]

    dag_runs = _FakeCounter()
    run_cost = _FakeHistogram()
    nan_counter = _FakeCounter()
    sim_runs = _FakeCounter()
    connector_counter = _FakeCounter()
    dag_duration = _FakeHistogram()

    metrics.slo_dag_runs_total = dag_runs  # type: ignore[assignment]
    metrics.slo_run_cost_usd = run_cost  # type: ignore[assignment]
    metrics.slo_simulation_nan_total = nan_counter  # type: ignore[assignment]
    metrics.slo_simulation_runs_total = sim_runs  # type: ignore[assignment]
    metrics.slo_connector_requests_total = connector_counter  # type: ignore[assignment]
    metrics.slo_dag_duration_seconds = dag_duration  # type: ignore[assignment]

    metrics.record_slo_dag_run("success", workflow_id="wf")
    metrics.record_slo_run_cost(1.23, workflow_id="wf")
    metrics.record_slo_simulation_nan(method="jax_scan")
    metrics.record_slo_simulation_run("ok", method="jax_scan")
    metrics.record_slo_connector_request("ok", connector_id="int.world_bank@1.0.0")
    with metrics.time_slo_dag({"workflow_id": "wf"}):
        time.sleep(0.001)

    assert dag_runs.calls[-1][1] == {"status": "success", "workflow_id": "wf", "env": "test"}
    assert run_cost.calls[-1][1] == {"workflow_id": "wf", "env": "test"}
    assert nan_counter.calls[-1][1] == {"method": "jax_scan", "env": "test"}
    assert sim_runs.calls[-1][1] == {"status": "ok", "method": "jax_scan", "env": "test"}
    assert connector_counter.calls[-1][1] == {
        "status": "ok",
        "connector_id": "int.world_bank@1.0.0",
        "env": "test",
    }
    assert dag_duration.calls and dag_duration.calls[-1][1] == {"workflow_id": "wf", "env": "test"}
