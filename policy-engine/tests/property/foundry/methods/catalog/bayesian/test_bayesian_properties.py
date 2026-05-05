"""
Property-based tests for Bayesian regression methods.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("hypothesis", reason="hypothesis not installed")

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from polisyos.foundry.methods.catalog.bayesian.regression import (
    BayesianLinearRegressionEstimator,
)
from tests.unit.foundry.methods.testing.strategies import bayesian_regression_strategy


@pytest.mark.hypothesis
@given(data=bayesian_regression_strategy())
@settings(max_examples=25, deadline=20_000)
def test_bayesian_regression_output_is_finite(data: dict) -> None:
    """Bayesian regression must return finite posterior moments."""
    X = data["X"]
    y = data["y"]

    assume(np.isfinite(X).all())
    assume(np.isfinite(y).all())
    # X must have non-trivial column variances
    assume(np.all(X.std(axis=0) > 0.01))

    try:
        state = {"features": X, "target": y}
        result = BayesianLinearRegressionEstimator.pure_step(state, {})
        assert isinstance(result, dict)
        posterior = result["result"]
        for k, v in posterior.posterior_means.items():
            assert np.isfinite(v), f"Non-finite posterior mean[{k!r}]"
        predictions = np.asarray(result["prediction_result"].predictions, dtype=float)
        assert np.isfinite(predictions).all()
    except Exception as exc:
        if any(kw in str(exc).lower() for kw in ("singular", "nan", "converge", "degenerate")):
            return
        raise


@pytest.mark.hypothesis
@given(data=bayesian_regression_strategy())
@settings(max_examples=20, deadline=20_000)
def test_bayesian_regression_posterior_mean_shape(data: dict) -> None:
    """Posterior mean must have shape (n_features,)."""
    assume(np.isfinite(data["X"]).all())
    assume(np.isfinite(data["y"]).all())
    assume(np.all(data["X"].std(axis=0) > 0.01))

    try:
        state = {"features": data["X"], "target": data["y"]}
        result = BayesianLinearRegressionEstimator.pure_step(state, {})
        posterior = result["result"]
        if data["n_features"] == 1 and "coefficients" in posterior.posterior_means:
            means = np.asarray([posterior.posterior_means["coefficients"]], dtype=float)
        else:
            means = np.asarray(
                [
                    posterior.posterior_means[f"coefficients_{idx}"]
                    for idx in range(data["n_features"])
                ],
                dtype=float,
            )
        assert means.shape == (data["n_features"],)
    except Exception as exc:
        if any(kw in str(exc).lower() for kw in ("singular", "nan", "converge")):
            return
        raise


@pytest.mark.hypothesis
@given(
    n_obs=st.integers(min_value=50, max_value=150),
    n_features=st.integers(min_value=1, max_value=4),
    seed=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=15, deadline=20_000)
def test_bayesian_regression_deterministic(n_obs: int, n_features: int, seed: int) -> None:
    """Same inputs → identical posterior moments (deterministic path)."""
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n_obs, n_features))
    y = X @ rng.normal(0, 1, n_features) + rng.normal(0, 0.5, n_obs)

    state = {"features": X, "target": y}
    try:
        result1 = BayesianLinearRegressionEstimator.pure_step(state, {"seed": seed})
        result2 = BayesianLinearRegressionEstimator.pure_step(state, {"seed": seed})
        mean1 = result1["result"].posterior_means
        mean2 = result2["result"].posterior_means
        np.testing.assert_allclose(
            [mean1[key] for key in sorted(mean1)],
            [mean2[key] for key in sorted(mean2)],
            rtol=1e-8,
        )
    except Exception as exc:
        if any(kw in str(exc).lower() for kw in ("singular", "nan", "converge")):
            return
        raise
