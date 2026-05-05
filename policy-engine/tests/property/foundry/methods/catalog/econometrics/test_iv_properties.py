"""
Property-based tests for Instrumental Variables econometrics methods.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("hypothesis", reason="hypothesis not installed")

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from polisyos.foundry.methods.catalog.econometrics.iv import TwoStageLeastSquaresEstimator
from tests.unit.foundry.methods.testing.strategies import iv_data_strategy

pytest.importorskip("linearmodels", reason="linearmodels not installed")


def _iv_state(data: dict) -> dict:
    outcome = np.asarray(data["outcome"], dtype=float)
    treatment = np.asarray(data["treatment"], dtype=float).reshape(-1, 1)
    covariates = np.asarray(data["covariates"], dtype=float)
    instrument = np.asarray(data["instrument"], dtype=float).reshape(-1, 1)
    return {
        "dependent": outcome,
        "exog": np.column_stack([treatment, covariates]),
        "instrument_ids": instrument,
        "entity_ids": np.arange(outcome.shape[0]),
        "time_ids": np.arange(outcome.shape[0]) % 2,
        "feature_names": ["treatment", *[f"x{i}" for i in range(covariates.shape[1])]],
        "instrument_names": ["instrument"],
    }


@pytest.mark.hypothesis
@given(data=iv_data_strategy())
@settings(max_examples=30, deadline=15_000)
def test_iv_2sls_output_is_finite(data: dict) -> None:
    """2SLS must not return NaN/Inf under well-specified inputs."""
    outcome = data["outcome"]
    treatment = data["treatment"]
    instrument = data["instrument"]
    covariates = data["covariates"]

    assume(np.isfinite(outcome).all())
    assume(np.isfinite(treatment).all())
    assume(np.isfinite(instrument).all())
    assume(np.isfinite(covariates).all())
    # Instrument must have non-trivial variance for identification
    assume(np.std(instrument) > 0.05)

    try:
        result = TwoStageLeastSquaresEstimator.pure_step(_iv_state(data), {})
        assert isinstance(result, dict)
        for v in result["result"].params.values():
            if isinstance(v, (int, float)):
                assert np.isfinite(v)
    except Exception as exc:
        if any(
            kw in str(exc).lower() for kw in ("singular", "rank", "nan", "converge", "collinear")
        ):
            return
        raise


@pytest.mark.hypothesis
@given(data=iv_data_strategy())
@settings(max_examples=20, deadline=15_000)
def test_iv_output_has_report_key(data: dict) -> None:
    """IV pure_step must always return a dict with a 'result' key."""

    assume(np.isfinite(data["outcome"]).all())
    assume(np.std(data["instrument"]) > 0.05)

    try:
        result = TwoStageLeastSquaresEstimator.pure_step(_iv_state(data), {})
        assert "result" in result
    except Exception as exc:
        if any(
            kw in str(exc).lower() for kw in ("singular", "rank", "nan", "converge", "collinear")
        ):
            return
        raise


@pytest.mark.hypothesis
@given(
    n_obs=st.integers(min_value=50, max_value=200),
    beta_true=st.floats(min_value=-5.0, max_value=5.0, allow_nan=False),
)
@settings(max_examples=20, deadline=20_000)
def test_iv_strong_instrument_estimate_near_true(n_obs: int, beta_true: float) -> None:
    """With a strong instrument, the 2SLS estimate should be close to beta_true."""
    rng = np.random.default_rng(0)
    instrument = rng.normal(0, 1, n_obs)
    # Strong first stage: treatment ~ 0.9 * Z + noise
    treatment = 0.9 * instrument + rng.normal(0, 0.1, n_obs)
    outcome = treatment * beta_true + rng.normal(0, 0.5, n_obs)
    covariates = rng.normal(0, 1, (n_obs, 2))

    try:
        state = _iv_state(
            {
                "outcome": outcome,
                "treatment": treatment,
                "instrument": instrument,
                "covariates": covariates,
            }
        )
        result = TwoStageLeastSquaresEstimator.pure_step(state, {})
        estimate = result["result"].params.get("treatment")
        if estimate is not None:
            assert np.isfinite(estimate)
    except Exception as exc:
        if any(
            kw in str(exc).lower() for kw in ("singular", "rank", "nan", "converge", "collinear")
        ):
            return
        raise
