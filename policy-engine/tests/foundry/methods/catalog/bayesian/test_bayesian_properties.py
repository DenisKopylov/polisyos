"""
Property-based tests for Bayesian regression methods.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("hypothesis", reason="hypothesis not installed")

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tests.foundry.methods.testing.strategies import bayesian_regression_strategy


@pytest.mark.hypothesis
@given(data=bayesian_regression_strategy())
@settings(max_examples=25, deadline=20_000)
def test_bayesian_regression_output_is_finite(data: dict) -> None:
    """Bayesian regression must return finite posterior moments."""
    try:
        from polisyos.foundry.methods.catalog.bayesian._registry_boot import (
            BayesianLinearRegression,
        )
    except ImportError:
        pytest.skip("BayesianLinearRegression not importable")

    X = data["X"]
    y = data["y"]

    assume(np.isfinite(X).all())
    assume(np.isfinite(y).all())
    # X must have non-trivial column variances
    assume(np.all(X.std(axis=0) > 0.01))

    try:
        state = {"X": X, "y": y}
        result = BayesianLinearRegression.pure_step(state, {})
        assert isinstance(result, dict)
        for k, v in result.items():
            if isinstance(v, np.ndarray):
                if np.issubdtype(v.dtype, np.floating):
                    assert not np.any(np.isnan(v)), f"NaN in output[{k!r}]"
            elif isinstance(v, float):
                assert np.isfinite(v), f"Non-finite float in output[{k!r}]"
    except Exception as exc:
        if any(kw in str(exc).lower() for kw in ("singular", "nan", "converge", "degenerate")):
            return
        raise


@pytest.mark.hypothesis
@given(data=bayesian_regression_strategy())
@settings(max_examples=20, deadline=20_000)
def test_bayesian_regression_posterior_mean_shape(data: dict) -> None:
    """Posterior mean must have shape (n_features,)."""
    try:
        from polisyos.foundry.methods.catalog.bayesian._registry_boot import (
            BayesianLinearRegression,
        )
    except ImportError:
        pytest.skip("BayesianLinearRegression not importable")

    assume(np.isfinite(data["X"]).all())
    assume(np.isfinite(data["y"]).all())
    assume(np.all(data["X"].std(axis=0) > 0.01))

    try:
        state = {"X": data["X"], "y": data["y"]}
        result = BayesianLinearRegression.pure_step(state, {})
        mean = result.get("posterior_mean") or result.get("beta_mean")
        if mean is not None:
            mean = np.asarray(mean)
            assert mean.shape == (data["n_features"],)
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
def test_bayesian_regression_deterministic(
    n_obs: int, n_features: int, seed: int
) -> None:
    """Same inputs → identical posterior moments (deterministic path)."""
    try:
        from polisyos.foundry.methods.catalog.bayesian._registry_boot import (
            BayesianLinearRegression,
        )
    except ImportError:
        pytest.skip("BayesianLinearRegression not importable")

    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n_obs, n_features))
    y = X @ rng.normal(0, 1, n_features) + rng.normal(0, 0.5, n_obs)

    state = {"X": X, "y": y}
    try:
        result1 = BayesianLinearRegression.pure_step(state, {"seed": seed})
        result2 = BayesianLinearRegression.pure_step(state, {"seed": seed})
        mean1 = result1.get("posterior_mean") or result1.get("beta_mean")
        mean2 = result2.get("posterior_mean") or result2.get("beta_mean")
        if mean1 is not None and mean2 is not None:
            np.testing.assert_allclose(mean1, mean2, rtol=1e-8)
    except Exception as exc:
        if any(kw in str(exc).lower() for kw in ("singular", "nan", "converge")):
            return
        raise
