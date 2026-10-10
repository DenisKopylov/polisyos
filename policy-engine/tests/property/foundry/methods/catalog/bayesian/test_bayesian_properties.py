"""Property-based tests for Bayesian regression methods."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("hypothesis", reason="hypothesis not installed")

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from polisyos.foundry.methods.catalog.bayesian.regression import BayesianLinearRegressionEstimator
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import bayesian_regression_strategy


@pytest.mark.hypothesis
@given(data=bayesian_regression_strategy())
@settings(
    max_examples=25,
    deadline=20_000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_bayesian_regression_output_is_finite(data: dict, property_method_dispatcher) -> None:
    """Bayesian regression must return finite posterior moments."""
    X = data["X"]
    y = data["y"]
    assume(np.isfinite(X).all())
    assume(np.isfinite(y).all())
    assume(np.all(X.std(axis=0) > 0.01))

    result = invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=BayesianLinearRegressionEstimator,
        state={"features": X, "target": y},
        params={},
        seed=0,
    ).output
    posterior = result["result"]
    for key, value in posterior.posterior_means.items():
        assert np.isfinite(value), f"Non-finite posterior mean[{key!r}]"
    predictions = np.asarray(result["prediction_result"].predictions, dtype=float)
    assert predictions.size > 0
    assert np.isfinite(predictions).all()


@pytest.mark.hypothesis
@given(data=bayesian_regression_strategy())
@settings(
    max_examples=20,
    deadline=20_000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_bayesian_regression_posterior_mean_shape(
    data: dict, property_method_dispatcher
) -> None:
    """Posterior mean must have shape (n_features,)."""
    assume(np.isfinite(data["X"]).all())
    assume(np.isfinite(data["y"]).all())
    assume(np.all(data["X"].std(axis=0) > 0.01))

    result = invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=BayesianLinearRegressionEstimator,
        state={"features": data["X"], "target": data["y"]},
        params={},
        seed=0,
    ).output
    posterior_means = result["result"].posterior_means
    if data["n_features"] == 1 and "coefficients" in posterior_means:
        means = np.asarray([posterior_means["coefficients"]], dtype=float)
    else:
        means = np.asarray(
            [posterior_means[f"coefficients_{idx}"] for idx in range(data["n_features"])],
            dtype=float,
        )
    assert means.shape == (data["n_features"],)
    assert np.isfinite(means).all()


@pytest.mark.hypothesis
@given(
    n_obs=st.integers(min_value=50, max_value=150),
    n_features=st.integers(min_value=1, max_value=4),
    seed=st.integers(min_value=0, max_value=50),
)
@settings(
    max_examples=15,
    deadline=20_000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_bayesian_regression_deterministic(
    n_obs: int, n_features: int, seed: int, property_method_dispatcher
) -> None:
    """Same inputs and backend seed produce identical posterior moments."""
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n_obs, n_features))
    y = X @ rng.normal(0, 1, n_features) + rng.normal(0, 0.5, n_obs)
    state = {"features": X, "target": y}

    first = invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=BayesianLinearRegressionEstimator,
        state=state,
        params={},
        seed=seed,
    ).output
    second = invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=BayesianLinearRegressionEstimator,
        state=state,
        params={},
        seed=seed,
    ).output
    mean1 = first["result"].posterior_means
    mean2 = second["result"].posterior_means
    np.testing.assert_allclose(
        [mean1[key] for key in sorted(mean1)],
        [mean2[key] for key in sorted(mean2)],
        rtol=1e-8,
    )
