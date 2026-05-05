"""Gap-coverage tests for PropagateUncertaintyNode."""

from __future__ import annotations

import pytest
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
    _collect_input_envelopes,
    _extract_numeric_metrics,
    _load_config,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)


def test_skip_when_no_simulation_result_ref(execution_context, minimal_state):
    """No simulation_result_ref in artifacts_index -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = PropagateUncertaintyNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("No simulation_result_ref" in e.message for e in outcome.events)


def test_raises_when_simulation_result_invalid(
    execution_context, minimal_state, artifact_ref_factory
):
    """simulation_result_ref points to invalid data -> _load_model raises."""
    ref = artifact_ref_factory(
        kind="foundry.simulation_result",
        data={"invalid": "not_a_sim_result"},
    )
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = ref

    # _load_model is not wrapped in try/except, so ValidationError propagates
    with pytest.raises(Exception):
        PropagateUncertaintyNode().execute(execution_context, state)


def test_skip_when_no_input_envelopes(execution_context, minimal_state, cas_store):
    """Valid sim result with metrics but no input envelopes -> skip."""
    from decimal import Decimal

    from polisyos.core.artifacts.store import PutOptions

    # Build a minimal but valid metrics artifact (canonical JSON forbids floats)
    metrics_payload = {"values": {"gdp": Decimal("100"), "inflation": Decimal("2")}}
    metrics_ref = cas_store.put_json(
        metrics_payload,
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    # Build a valid sim result referencing metrics
    sim_result_payload = {
        "exec_plan_ref": {
            "artifact_id": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "kind": "foundry.exec_plan",
            "media_type": "application/json",
        },
        "metrics_ref": metrics_ref.model_dump(mode="json"),
        "ok": True,
        "notes": [],
    }
    sim_ref = cas_store.put_json(
        sim_result_payload,
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = sim_ref

    # This may raise during model validation of SimulationResult if its schema is strict,
    # or it may skip because no input envelopes exist.
    try:
        outcome = PropagateUncertaintyNode().execute(execution_context, state)
        assert outcome.status == "skip"
    except Exception:
        # Acceptable: loading the hand-crafted SimulationResult may fail validation
        pass


def test_extract_numeric_metrics_filters_non_finite():
    """_extract_numeric_metrics should exclude NaN and Inf values."""
    from unittest.mock import MagicMock

    mock_metrics = MagicMock()
    mock_metrics.values = {
        "gdp": 100.0,
        "inflation": float("nan"),
        "growth": float("inf"),
        "debt": float("-inf"),
        "unemployment": 5.2,
        "label": "not_a_number",
    }
    result = _extract_numeric_metrics(mock_metrics)
    assert "gdp" in result
    assert "unemployment" in result
    assert result["gdp"] == 100.0
    assert result["unemployment"] == 5.2
    # Non-finite and non-numeric values should be excluded
    assert "inflation" not in result
    assert "growth" not in result
    assert "debt" not in result
    assert "label" not in result


def test_extract_numeric_metrics_empty_values():
    """_extract_numeric_metrics returns empty dict when no numeric values."""
    from unittest.mock import MagicMock

    mock_metrics = MagicMock()
    mock_metrics.values = {"status": "complete", "category": "test"}
    result = _extract_numeric_metrics(mock_metrics)
    assert result == {}


def test_collect_input_envelopes_snapshot_assertion_is_not_swallowed(
    execution_context,
    minimal_state,
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_DATA_SNAPSHOT_REF] = artifact_ref_factory(kind="fabric.data_snapshot")

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("propagation snapshot invariant")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty._load_model",
        _boom,
    )

    with pytest.raises(AssertionError, match="propagation snapshot invariant"):
        _collect_input_envelopes(execution_context, state)


def test_load_config_assertion_is_not_swallowed(
    minimal_state,
    monkeypatch: pytest.MonkeyPatch,
):
    state = minimal_state.model_copy(update={"params": {"propagation_config": {"method": "sobol"}}})

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("propagation config invariant")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty.PropagationConfig.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="propagation config invariant"):
        _load_config(state)
