from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods import ComputeBackend
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.bayesian import PosteriorResult, ensure_bayesian_methods_registered
from polisyos.foundry.methods.catalog.econometrics.protocols import TimeSeriesData
from polisyos.foundry.methods.ml import TabularData
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _make_tabular() -> TabularData:
    rng = np.random.default_rng(301)
    x = rng.normal(size=(80, 4))
    y = 1.1 + 1.8 * x[:, 0] - 0.6 * x[:, 1] + rng.normal(scale=0.3, size=80)
    return TabularData(features=x, target=y, feature_names=["x0", "x1", "x2", "x3"])


def _make_time_series() -> TimeSeriesData:
    rng = np.random.default_rng(303)
    innovations = rng.normal(scale=0.3, size=72)
    series = np.zeros(72, dtype=float)
    for idx in range(2, series.shape[0]):
        series[idx] = 0.4 + 0.55 * series[idx - 1] - 0.15 * series[idx - 2] + innovations[idx]
    return TimeSeriesData(endog=series)


def test_bayesian_linear_regression_runs() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.regression.linear_regression@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={"num_warmup": 40, "num_samples": 56, "num_chains": 2, "proposal_scale": 0.035},
        seed=307,
    )

    posterior = result.output["result"]
    assert isinstance(posterior, PosteriorResult)
    assert posterior.method_name == "bayesian_linear_regression"
    assert "intercept" in posterior.posterior_means
    assert result.output["prediction_result"].method_name == "bayesian_linear_regression"
    assert result.output["uncertainty_envelope"] is not None
    assert result.reproducibility.backend is ComputeBackend.BAYESIAN
    assert 0.0 <= posterior.diagnostics["acceptance_rate"] <= 1.0


def test_bayesian_autoregression_runs() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.timeseries.autoregression@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_time_series(),
        params={"n_lags": 2, "num_warmup": 40, "num_samples": 56, "num_chains": 2, "proposal_scale": 0.03},
        seed=311,
    )

    posterior = result.output["result"]
    assert isinstance(posterior, PosteriorResult)
    assert posterior.method_name == "bayesian_autoregression"
    assert "phi_0" in posterior.posterior_means
    assert result.output["prediction_result"].method_name == "bayesian_autoregression"
    assert result.output["uncertainty_envelope"] is not None
    assert result.reproducibility.backend is ComputeBackend.BAYESIAN
