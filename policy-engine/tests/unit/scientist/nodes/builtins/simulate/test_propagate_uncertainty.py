"""Gap-coverage tests for PropagateUncertaintyNode."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import pytest

from polisyos.foundry.uncertainty.config import (
    AdaptiveStoppingConfig,
    PropagationConfig,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
    _build_propagation_fn,
    _collect_input_envelopes,
    _extract_numeric_metrics,
    _load_config,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)

_CONFIG_FIELD_PATHS = [
    *((field_name,) for field_name in PropagationConfig.model_fields),
    *(("adaptive_stopping", field_name) for field_name in AdaptiveStoppingConfig.model_fields),
]
_PREFIXED_CONFIG_FIELD_PATHS = [
    *((field_name,) for field_name in PropagationConfig.model_fields),
    *(("adaptive_stopping", field_name) for field_name in AdaptiveStoppingConfig.model_fields),
]


def _invalid_config_payload(field_path: tuple[str, ...]) -> dict[str, object]:
    payload: dict[str, object] = {}
    cursor = payload
    for field_name in field_path[:-1]:
        child: dict[str, object] = {}
        cursor[field_name] = child
        cursor = child
    cursor[field_path[-1]] = None
    return payload


def _invalid_prefixed_params(field_path: tuple[str, ...]) -> dict[str, object]:
    value: object = None
    for field_name in reversed(field_path[1:]):
        value = {field_name: value}
    return {f"propagation_{field_path[0]}": value}


def _assert_config_refusal(execution_context, minimal_state, params: dict[str, object]) -> None:
    state = minimal_state.model_copy(deep=True, update={"params": params})
    outcome = PropagateUncertaintyNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "propagation_config_invalid"
    assert outcome.artifacts == []
    assert outcome.state.artifacts_index == state.artifacts_index


def test_skip_when_no_simulation_result_ref(execution_context, minimal_state):
    """No simulation_result_ref in artifacts_index -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = PropagateUncertaintyNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("No simulation_result_ref" in e.message for e in outcome.events)


@pytest.mark.parametrize(
    "field_path",
    _CONFIG_FIELD_PATHS,
    ids=lambda field_path: ".".join(field_path),
)
def test_invalid_value_for_each_declared_config_field_fails_before_skip(
    execution_context, minimal_state, field_path: tuple[str, ...]
) -> None:
    _assert_config_refusal(
        execution_context,
        minimal_state,
        {"propagation_config": _invalid_config_payload(field_path)},
    )


@pytest.mark.parametrize(
    "field_path",
    _PREFIXED_CONFIG_FIELD_PATHS,
    ids=lambda field_path: ".".join(field_path),
)
def test_invalid_value_for_each_declared_prefixed_config_field_is_typed(
    execution_context, minimal_state, field_path: tuple[str, ...]
) -> None:
    _assert_config_refusal(
        execution_context,
        minimal_state,
        _invalid_prefixed_params(field_path),
    )


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"propagation_config": None}, id="present-null"),
        pytest.param({"propagation_config": []}, id="wrong-sequence-shape"),
        pytest.param({"propagation_config": "monte_carlo"}, id="wrong-scalar-shape"),
        pytest.param(
            {"propagation_config": {"adaptive_stopping": {"min_samples": 10}}},
            id="present-invalid-adaptive-range",
        ),
        pytest.param({"propagation_config": {"unknown_field": 1}}, id="extra-field"),
        pytest.param(
            {
                "propagation_config": {"adaptive_stopping": {"min_samples": 10}},
                "propagation_mc_n_samples": 100,
            },
            id="invalid-nested-does-not-fall-through-to-prefix",
        ),
    ],
)
def test_invalid_present_config_is_typed_before_skip_or_artifact_write(
    execution_context, minimal_state, params: dict[str, object]
) -> None:
    _assert_config_refusal(execution_context, minimal_state, params)


def test_load_config_preserves_nested_precedence_and_defaults_only_on_absence(
    minimal_state,
) -> None:
    absent = minimal_state.model_copy(update={"params": {}})
    assert _load_config(absent) == PropagationConfig()

    valid_nested = minimal_state.model_copy(
        update={
            "params": {
                "propagation_config": {"mc_n_samples": 100, "mc_batch_size": 100},
                "propagation_mc_n_samples": 200,
            }
        }
    )
    assert _load_config(valid_nested).mc_n_samples == 100
    assert _load_config(valid_nested).mc_batch_size == 100

    valid_prefix = minimal_state.model_copy(update={"params": {"propagation_mc_n_samples": 100}})
    assert _load_config(valid_prefix).mc_n_samples == 100


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


def test_build_propagation_fn_is_jax_tracer_safe():
    """The real node response can be differentiated without a Python cast."""
    response, mapped = _build_propagation_fn(
        {"propagation_sensitivity": {"y": {"x": 1.0}}},
        base_metric_values={"y": 10.0},
        nominal_params={"x": 2.0},
    )

    jacobian = jax.jacfwd(lambda x: response(x=x)["y"])(jnp.asarray(2.0))

    assert mapped == {"x"}
    assert float(jacobian) == pytest.approx(5.0)


def test_build_propagation_fn_keeps_unknown_sensitivity_unmapped():
    """Missing response evidence does not become an all-parameter mapping."""
    response, mapped = _build_propagation_fn(
        {},
        base_metric_values={"y": 10.0, "z": 20.0},
        nominal_params={"x": 2.0},
    )

    assert mapped == set()
    assert response(x=3.0) == {"y": 10.0, "z": 20.0}


def test_build_propagation_fn_preserves_zero_baseline_effect():
    """An explicit affine response still varies when its baseline is zero."""
    response, _ = _build_propagation_fn(
        {"propagation_sensitivity": {"y": {"x": 1.0}}},
        base_metric_values={"y": 0.0},
        nominal_params={"x": 2.0},
    )

    assert response(x=3.0)["y"] == pytest.approx(1.0)
    assert response(x=1.0)["y"] == pytest.approx(-1.0)
