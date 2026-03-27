"""Tests for the public scientist API (run_experiment)."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from polisyos.scientist.engine.state import ExperimentState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_run_selected_workflow(final_state: ExperimentState | None = None):
    """Return a mock that simulates run_selected_workflow."""
    mock = MagicMock()
    state = final_state or ExperimentState(run_id="R_mock_result")
    mock.return_value.state = state
    mock.return_value.report.status = "ok"
    return mock


def _mock_metrics():
    m = MagicMock()

    @contextmanager
    def _time_slo_dag(labels=None, **kw):
        yield

    m.time_slo_dag = _time_slo_dag
    return m


def _mock_tracer():
    t = MagicMock()
    span = MagicMock()
    t.start_as_current_span.return_value.__enter__ = MagicMock(return_value=span)
    t.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
    return t, span


# ---------------------------------------------------------------------------
# Tests for _prepare_initial_state
# ---------------------------------------------------------------------------

class TestPrepareInitialState:
    def test_none_input(self):
        from polisyos.scientist.api import _prepare_initial_state
        state = _prepare_initial_state(None)
        assert isinstance(state, ExperimentState)
        assert state.run_id  # auto-generated

    def test_dict_input(self):
        from polisyos.scientist.api import _prepare_initial_state
        state = _prepare_initial_state({"run_id": "R_dict"})
        assert state.run_id == "R_dict"

    def test_experiment_state_input(self):
        from polisyos.scientist.api import _prepare_initial_state
        original = ExperimentState(run_id="R_obj")
        state = _prepare_initial_state(original)
        assert state.run_id == "R_obj"

    def test_auto_generates_run_id(self):
        from polisyos.scientist.api import _prepare_initial_state
        state = _prepare_initial_state({"run_id": ""})
        assert state.run_id
        assert state.run_id != ""

    def test_preserves_given_run_id(self):
        from polisyos.scientist.api import _prepare_initial_state
        state = _prepare_initial_state({"run_id": "R_given"})
        assert state.run_id == "R_given"


# ---------------------------------------------------------------------------
# Tests for run_experiment
# ---------------------------------------------------------------------------

class TestRunExperiment:
    @patch("polisyos.scientist.api.run_selected_workflow" if False else "polisyos.scientist.workflows.builder.run_selected_workflow")
    @patch("polisyos.scientist.api._resolve_observability")
    def test_dict_state_returns_dict(self, mock_obs, mock_run):
        tracer, span = _mock_tracer()
        mock_obs.return_value = (tracer, _mock_metrics())
        result_state = ExperimentState(run_id="R_result")
        mock_run.return_value = MagicMock(state=result_state, report=MagicMock(status="ok"))

        from polisyos.scientist.api import run_experiment
        result = run_experiment({"run_id": "R_test"})
        assert isinstance(result, dict)
        assert result["run_id"] == "R_result"

    @patch("polisyos.scientist.workflows.builder.run_selected_workflow")
    @patch("polisyos.scientist.api._resolve_observability")
    def test_none_state_returns_dict(self, mock_obs, mock_run):
        tracer, span = _mock_tracer()
        mock_obs.return_value = (tracer, _mock_metrics())
        result_state = ExperimentState(run_id="R_auto")
        mock_run.return_value = MagicMock(state=result_state, report=MagicMock(status="ok"))

        from polisyos.scientist.api import run_experiment
        result = run_experiment(None)
        assert isinstance(result, dict)

    def test_extra_keys_raises_value_error(self):
        from polisyos.scientist.api import run_experiment
        with pytest.raises(ValueError, match="Unsupported Scientist state keys"):
            run_experiment({"run_id": "R_bad", "nonexistent_field_xyz": 123})

    @patch("polisyos.scientist.workflows.builder.run_selected_workflow")
    @patch("polisyos.scientist.api._resolve_observability")
    def test_records_metrics_on_success(self, mock_obs, mock_run):
        tracer, span = _mock_tracer()
        metrics = _mock_metrics()
        mock_obs.return_value = (tracer, metrics)
        result_state = ExperimentState(run_id="R_metrics")
        mock_run.return_value = MagicMock(state=result_state, report=MagicMock(status="ok"))

        from polisyos.scientist.api import run_experiment
        run_experiment({"run_id": "R_metrics"})

        metrics.increment_active_runs.assert_called_once()
        metrics.decrement_active_runs.assert_called_once()
        metrics.record_workflow_run.assert_called_once()

    @patch("polisyos.scientist.workflows.builder.run_selected_workflow")
    @patch("polisyos.scientist.api._resolve_observability")
    def test_records_error_metrics_on_failure(self, mock_obs, mock_run):
        tracer, span = _mock_tracer()
        metrics = _mock_metrics()
        mock_obs.return_value = (tracer, metrics)
        mock_run.side_effect = RuntimeError("boom")

        from polisyos.scientist.api import run_experiment
        with pytest.raises(RuntimeError, match="boom"):
            run_experiment({"run_id": "R_error"})

        metrics.record_workflow_run.assert_called_once_with("error", "UNKNOWN", "orchestrator")
        metrics.decrement_active_runs.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for _estimate_run_cost_usd
# ---------------------------------------------------------------------------

class TestEstimateRunCost:
    def test_direct_run_cost(self):
        from polisyos.scientist.api import _estimate_run_cost_usd
        state = ExperimentState(run_id="R_cost", params={"run_cost_usd": 5.0})
        assert _estimate_run_cost_usd(state) == 5.0

    def test_direct_llm_cost(self):
        from polisyos.scientist.api import _estimate_run_cost_usd
        state = ExperimentState(run_id="R_llm", params={"llm_cost_usd": 3.5})
        assert _estimate_run_cost_usd(state) == 3.5

    def test_no_cost_returns_none(self):
        from polisyos.scientist.api import _estimate_run_cost_usd
        state = ExperimentState(run_id="R_none")
        assert _estimate_run_cost_usd(state) is None

    def test_variant_costs(self):
        from polisyos.scientist.api import _estimate_run_cost_usd
        state = ExperimentState(
            run_id="R_variants",
            params={
                "llm_model_variants": [
                    {"cost_usd": 1.0},
                    {"cost_usd": 2.5},
                ]
            },
        )
        assert _estimate_run_cost_usd(state) == 3.5
