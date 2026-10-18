"""
Property-based tests for Difference-in-Differences methods.

These tests verify that the typed DiD request executes and that assertions inspect
its actual report output.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("hypothesis", reason="hypothesis not installed")

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.causal import EstimationStatus
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import panel_data_strategy


def _invoke_standard_did(data, isolated_registry, property_method_dispatcher):
    fqn = "causal.inference.did.standard@1.0.0"
    method_class = isolated_registry.get(fqn)
    bound_inputs = {
        "outcome": np.asarray(data["outcome"], dtype=float),
        "treatment": np.asarray(data["treatment"], dtype=int),
        "time_treatment": int(data["time_treatment"]),
    }
    state = PanelObservationalData.model_validate(bound_inputs)
    return invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=method_class,
        state=state,
        bound_inputs=bound_inputs,
        params={"cov_type": "HC1"},
        seed=42,
    ).output


@pytest.mark.hypothesis
@given(data=panel_data_strategy())
@settings(
    max_examples=30,
    deadline=15_000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_did_standard_no_nan(data, isolated_registry, property_method_dispatcher) -> None:
    """Standard DiD must return finite estimates for generated valid panels."""
    output = _invoke_standard_did(data, isolated_registry, property_method_dispatcher)
    report = output["report"]

    assert report.status is EstimationStatus.SUCCESS
    assert np.isfinite(report.point_estimate)
    assert report.standard_error is not None and np.isfinite(report.standard_error)
    assert np.isfinite(np.asarray(report.confidence_interval, dtype=float)).all()


@pytest.mark.hypothesis
@given(data=panel_data_strategy(min_units=6, max_units=20, min_periods=5))
@settings(
    max_examples=20,
    deadline=15_000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_did_standard_output_has_report(
    data, isolated_registry, property_method_dispatcher
) -> None:
    """The typed consumer returns its DiD report with the requested estimand and basis size."""
    output = _invoke_standard_did(data, isolated_registry, property_method_dispatcher)
    report = output["report"]

    assert isinstance(output, dict)
    assert report.status is EstimationStatus.SUCCESS
    assert report.estimand == "ATT"
    assert report.sample_size == data["n_units"] * data["n_periods"]
    assert report.n_treated > 0
    assert report.n_control > 0


@pytest.mark.hypothesis
@given(
    n_units=st.integers(min_value=6, max_value=20),
    n_periods=st.integers(min_value=6, max_value=16),
    noise_scale=st.floats(min_value=0.1, max_value=2.0, allow_nan=False),
)
@settings(
    max_examples=20,
    deadline=20_000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_did_zero_att_estimate_is_finite(
    n_units: int,
    n_periods: int,
    noise_scale: float,
    isolated_registry,
    property_method_dispatcher,
) -> None:
    """With zero treatment effect, the emitted ATT estimate remains finite."""
    rng = np.random.default_rng(42)
    time_treatment = n_periods // 2
    outcome = rng.normal(0, noise_scale, (n_units, n_periods))
    treatment = np.zeros(n_units, dtype=int)
    treatment[: n_units // 2] = 1
    data = {
        "outcome": outcome,
        "treatment": treatment,
        "time_treatment": time_treatment,
        "n_units": n_units,
        "n_periods": n_periods,
    }
    output = _invoke_standard_did(data, isolated_registry, property_method_dispatcher)
    report = output["report"]

    assert report.status is EstimationStatus.SUCCESS
    assert np.isfinite(report.point_estimate)
