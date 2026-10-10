"""Property-based tests for Instrumental Variables econometrics methods."""

from __future__ import annotations

import importlib.metadata

import numpy as np
import pytest

pytest.importorskip("hypothesis", reason="hypothesis not installed")

from hypothesis import given, settings
from hypothesis import strategies as st

from polisyos.foundry.methods.catalog.econometrics.iv import TwoStageLeastSquaresEstimator
from polisyos.foundry.methods.catalog.econometrics.protocols import EconometricResult
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method

try:
    importlib.metadata.distribution("linearmodels")
except importlib.metadata.PackageNotFoundError:
    pytest.skip("linearmodels distribution not installed", allow_module_level=True)


def _iv_state(data: dict) -> dict:
    outcome = np.asarray(data["outcome"], dtype=float)
    treatment = np.asarray(data["treatment"], dtype=float).reshape(-1, 1)
    covariates = np.asarray(data["covariates"], dtype=float)
    instrument = np.asarray(data["instrument"], dtype=float)[:, None]
    return {
        "dependent": outcome,
        "exog": np.column_stack([treatment, covariates]),
        "instrument_ids": instrument,
        "entity_ids": np.arange(outcome.shape[0]),
        "time_ids": np.arange(outcome.shape[0]) % 2,
    }


def _iv_result(invocation) -> tuple[dict, EconometricResult]:
    output = invocation.output
    assert isinstance(output, dict)
    assert set(output) == {"result", "uncertainty_envelope"}
    result = output["result"]
    assert isinstance(result, EconometricResult)
    assert result.method_name == "iv_2sls"
    assert result.params
    assert set(result.std_errors) == set(result.params)
    standard_errors = np.asarray(list(result.std_errors.values()), dtype=float)
    assert np.isfinite(standard_errors).all()
    assert (standard_errors > 0.0).all()
    return output, result


def _fresh_iv_dispatcher():
    """Create isolated dispatcher and breaker state for one Hypothesis example."""
    from polisyos.foundry.methods.backends.circuit_breaker import CircuitBreakerRegistry
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    CircuitBreakerRegistry.reset_instance()
    return MethodDispatcher(enable_runtime_selection=False)


def _identified_iv_candidate(
    *, n_obs: int, beta_true: float
) -> dict[str, np.ndarray | float | int]:
    """Build a test-local, strongly identified IV candidate with nonzero noise."""
    angle = 2.0 * np.pi * np.arange(n_obs, dtype=float) / n_obs
    instrument = np.sin(angle)
    first_exog = np.cos(angle)
    second_exog = np.sin(2.0 * angle)
    first_stage_noise = np.cos(2.0 * angle)
    structural_error = 0.5 * np.sin(3.0 * angle)
    covariates = np.column_stack((first_exog, second_exog))
    treatment = 0.9 * instrument + 0.2 * first_exog + 0.15 * first_stage_noise
    outcome = (
        beta_true * treatment
        + covariates @ np.asarray([0.35, -0.2], dtype=float)
        + structural_error
    )
    candidate: dict[str, np.ndarray | float | int] = {
        "outcome": outcome,
        "treatment": treatment,
        "instrument": instrument,
        "covariates": covariates,
        "structural_error": structural_error,
        "n_obs": n_obs,
        "beta_true": beta_true,
    }

    state = _iv_state(candidate)
    regressors = np.asarray(state["exog"], dtype=float)
    instruments = np.asarray(state["instrument_ids"], dtype=float)
    instrument_design = np.column_stack((covariates, instruments))
    assert np.linalg.matrix_rank(regressors) == regressors.shape[1]
    assert np.linalg.matrix_rank(instrument_design) == instrument_design.shape[1]
    assert float(np.std(instrument)) > 0.0
    assert float(np.std(treatment)) > 0.0
    assert float(np.std(outcome)) > 0.0
    assert float(np.std(structural_error)) > 0.0

    instrument_residual = instruments[:, 0] - covariates @ np.linalg.lstsq(
        covariates, instruments[:, 0], rcond=None
    )[0]
    treatment_residual = regressors[:, 0] - covariates @ np.linalg.lstsq(
        covariates, regressors[:, 0], rcond=None
    )[0]
    partial_relevance = float(np.corrcoef(instrument_residual, treatment_residual)[0, 1])
    assert partial_relevance > 0.8
    return candidate


def _identified_iv_case_strategy():
    """Generate only the selected full-rank candidate over modest size/effect ranges."""
    return st.tuples(
        st.integers(min_value=80, max_value=120),
        st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    ).map(lambda values: _identified_iv_candidate(n_obs=values[0], beta_true=values[1]))


@pytest.mark.hypothesis
@given(data=_identified_iv_case_strategy())
@settings(max_examples=30, deadline=15_000)
def test_iv_2sls_output_is_finite(data: dict[str, np.ndarray | float | int]) -> None:
    """A selected full-rank 2SLS candidate returns finite coefficient summaries."""
    state = _iv_state(data)
    invocation = invoke_property_method(
        dispatcher=_fresh_iv_dispatcher(),
        method_class=TwoStageLeastSquaresEstimator,
        state=state,
        params={},
        seed=0,
    )
    _, result = _iv_result(invocation)
    assert result.n_obs == len(state["dependent"])
    assert result.params
    for field_name, values in (
        ("params", result.params),
        ("std_errors", result.std_errors),
        ("t_stats", result.t_stats),
        ("p_values", result.p_values),
    ):
        assert np.isfinite(np.asarray(list(values.values()), dtype=float)).all(), field_name


@pytest.mark.hypothesis
@given(data=_identified_iv_case_strategy())
@settings(max_examples=20, deadline=15_000)
def test_iv_output_has_report_key(data: dict[str, np.ndarray | float | int]) -> None:
    """The typed IV report and uncertainty projection share one selected estimate."""
    state = _iv_state(data)
    invocation = invoke_property_method(
        dispatcher=_fresh_iv_dispatcher(),
        method_class=TwoStageLeastSquaresEstimator,
        state=state,
        params={"envelope_param": "x0"},
        seed=0,
    )
    output, result = _iv_result(invocation)
    assert result.n_obs == len(data["outcome"])
    assert "x0" in result.params
    envelope = output["uncertainty_envelope"]
    assert envelope is not None
    assert envelope.point_estimate == pytest.approx(result.params["x0"])


@pytest.mark.hypothesis
@given(data=_identified_iv_case_strategy())
@settings(max_examples=20, deadline=20_000)
def test_iv_strong_instrument_estimate_near_true(
    data: dict[str, np.ndarray | float | int],
) -> None:
    """A selected strong-instrument candidate recovers its known effect within 3 SEs."""
    n_obs = int(data["n_obs"])
    beta_true = float(data["beta_true"])
    state = _iv_state(data)
    invocation = invoke_property_method(
        dispatcher=_fresh_iv_dispatcher(),
        method_class=TwoStageLeastSquaresEstimator,
        state=state,
        params={"envelope_param": "x0"},
        seed=0,
    )
    _, result = _iv_result(invocation)
    assert result.n_obs == n_obs
    estimate = result.params["x0"]
    standard_error = result.std_errors["x0"]
    assert np.isfinite(estimate)
    assert np.isfinite(standard_error) and standard_error > 0.0
    assert abs(estimate - beta_true) <= 3.0 * standard_error


def test_iv_rejects_rank_deficient_regressors() -> None:
    """The real 2SLS path refuses an endogenous column duplicated in its controls."""
    candidate = _identified_iv_candidate(n_obs=80, beta_true=1.0)
    covariates = np.asarray(candidate["covariates"], dtype=float)
    candidate["treatment"] = covariates[:, 0].copy()
    candidate["outcome"] = (
        float(candidate["beta_true"]) * np.asarray(candidate["treatment"], dtype=float)
        + covariates @ np.asarray([0.35, -0.2], dtype=float)
        + np.asarray(candidate["structural_error"], dtype=float)
    )
    state = _iv_state(candidate)
    regressors = np.asarray(state["exog"], dtype=float)
    instruments = np.asarray(state["instrument_ids"], dtype=float)
    instrument_design = np.column_stack((covariates, instruments))
    assert np.linalg.matrix_rank(regressors) < regressors.shape[1]
    assert np.linalg.matrix_rank(instrument_design) == instrument_design.shape[1]

    with pytest.raises(
        ValueError,
        match=r"regressors \[exog endog\] do not have full column rank",
    ):
        invoke_property_method(
            dispatcher=_fresh_iv_dispatcher(),
            method_class=TwoStageLeastSquaresEstimator,
            state=state,
            params={},
            seed=0,
        )
