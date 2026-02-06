from __future__ import annotations

from contextlib import contextmanager
import sys
import types

import pytest

import polisyos.scientist as scientist_api
from polisyos.scientist.engine.state import ExperimentState


class _FakeSpan:
    def __init__(self) -> None:
        self.statuses: list[object] = []
        self.exceptions: list[Exception] = []

    def __enter__(self) -> "_FakeSpan":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def set_status(self, status: object) -> None:
        self.statuses.append(status)

    def record_exception(self, exc: Exception) -> None:
        self.exceptions.append(exc)


class _FakeTracer:
    def start_as_current_span(self, _name: str, attributes=None):  # noqa: ANN001
        _ = attributes
        return _FakeSpan()


class _FakeMetrics:
    def __init__(self) -> None:
        self.workflow_calls: list[tuple[str, str, str]] = []
        self.slo_dag_calls: list[tuple[str, str]] = []
        self.cost_calls: list[tuple[float, str]] = []
        self.active = 0
        self.timed = 0

    @contextmanager
    def time_slo_dag(self, _attrs):  # noqa: ANN001
        self.timed += 1
        yield

    def increment_active_runs(self) -> None:
        self.active += 1

    def decrement_active_runs(self) -> None:
        self.active -= 1

    def record_workflow_run(self, status: str, phase: str, agent: str) -> None:
        self.workflow_calls.append((status, phase, agent))

    def record_slo_dag_run(self, status: str, workflow_id: str) -> None:
        self.slo_dag_calls.append((status, workflow_id))

    def record_slo_run_cost(self, cost_usd: float, workflow_id: str) -> None:
        self.cost_calls.append((cost_usd, workflow_id))


def test_run_experiment_records_slo_success(monkeypatch) -> None:
    fake_metrics = _FakeMetrics()
    monkeypatch.setattr(scientist_api, "get_metrics", lambda: fake_metrics)
    monkeypatch.setattr(scientist_api, "get_tracer", lambda: _FakeTracer())

    final_state = ExperimentState(
        run_id="R_test",
        params={
            "llm_model": "gpt-4o",
            "llm_prompt_tokens": 100,
            "llm_completion_tokens": 50,
        },
    )

    class _Result:
        state = final_state
        report = type("Report", (), {"status": "ok"})

    stub_pkg = types.ModuleType("polisyos.scientist.workflows")
    stub_builder = types.ModuleType("polisyos.scientist.workflows.builder")
    stub_builder.run_default_workflow = lambda _initial_state: _Result()  # type: ignore[attr-defined]
    stub_pkg.builder = stub_builder  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "polisyos.scientist.workflows", stub_pkg)
    monkeypatch.setitem(sys.modules, "polisyos.scientist.workflows.builder", stub_builder)

    result = scientist_api.run_experiment({"run_id": "R_test"})
    assert result["run_id"] == "R_test"
    assert fake_metrics.workflow_calls[-1] == ("success", "EXECUTE", "orchestrator")
    assert fake_metrics.slo_dag_calls[-1] == ("success", "scientist_default")
    assert fake_metrics.cost_calls and fake_metrics.cost_calls[-1][1] == "scientist_default"
    assert fake_metrics.timed == 1
    assert fake_metrics.active == 0


def test_run_experiment_records_slo_error(monkeypatch) -> None:
    fake_metrics = _FakeMetrics()
    monkeypatch.setattr(scientist_api, "get_metrics", lambda: fake_metrics)
    monkeypatch.setattr(scientist_api, "get_tracer", lambda: _FakeTracer())

    def _raise(_initial_state):  # noqa: ANN001
        raise RuntimeError("boom")

    stub_pkg = types.ModuleType("polisyos.scientist.workflows")
    stub_builder = types.ModuleType("polisyos.scientist.workflows.builder")
    stub_builder.run_default_workflow = _raise  # type: ignore[attr-defined]
    stub_pkg.builder = stub_builder  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "polisyos.scientist.workflows", stub_pkg)
    monkeypatch.setitem(sys.modules, "polisyos.scientist.workflows.builder", stub_builder)

    with pytest.raises(RuntimeError, match="boom"):
        scientist_api.run_experiment({"run_id": "R_fail"})

    assert fake_metrics.slo_dag_calls[-1] == ("error", "scientist_default")
    assert fake_metrics.active == 0
