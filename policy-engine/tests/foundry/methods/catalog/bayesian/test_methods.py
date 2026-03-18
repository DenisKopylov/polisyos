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


def _make_hierarchical_state() -> dict[str, object]:
    rng = np.random.default_rng(305)
    x = rng.normal(size=(72, 3))
    group_ids = np.repeat(np.array(["north", "center", "south"]), 24)
    group_effect = np.repeat(np.array([0.8, -0.2, 0.4]), 24)
    y = 1.5 + x @ np.array([1.2, -0.7, 0.25]) + group_effect + rng.normal(scale=0.35, size=72)
    return {
        "features": x,
        "target": y,
        "group_ids": group_ids,
        "feature_names": ["x0", "x1", "x2"],
    }


def _make_mixture_state() -> dict[str, object]:
    rng = np.random.default_rng(309)
    cluster_a = rng.normal(loc=(-1.5, 0.2), scale=(0.25, 0.2), size=(40, 2))
    cluster_b = rng.normal(loc=(1.2, 1.5), scale=(0.3, 0.25), size=(35, 2))
    cluster_c = rng.normal(loc=(0.0, -1.2), scale=(0.2, 0.3), size=(25, 2))
    return {"observations": np.vstack([cluster_a, cluster_b, cluster_c])}


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


def test_bayesian_hierarchical_regression_runs() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.regression.hierarchical@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_hierarchical_state(),
        params={"num_warmup": 32, "num_samples": 48, "proposal_scale": 0.025},
        seed=313,
    )

    posterior = result.output["result"]
    assert isinstance(posterior, PosteriorResult)
    assert posterior.method_name == "bayesian_hierarchical_regression"
    assert "group_scale" in posterior.posterior_means
    assert result.output["prediction_result"].method_name == "bayesian_hierarchical_regression"
    assert result.output["uncertainty_envelope"] is not None


def test_bayesian_hmc_regression_runs() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.sampling.hmc@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={"num_warmup": 32, "num_samples": 48, "num_chains": 2, "step_size": 0.015, "n_leapfrog": 10},
        seed=314,
    )

    posterior = result.output["result"]
    assert isinstance(posterior, PosteriorResult)
    assert posterior.method_name == "bayesian_hmc_regression"
    assert "sigma" in posterior.posterior_means
    assert 0.0 <= posterior.diagnostics["acceptance_rate"] <= 1.0
    assert result.output["prediction_result"].method_name == "bayesian_hmc_regression"
    assert result.output["uncertainty_envelope"] is not None


def test_bayesian_nuts_regression_runs() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.sampling.nuts@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={"num_warmup": 32, "num_samples": 40, "num_chains": 2, "max_depth": 4, "step_size": 0.012},
        seed=315,
    )

    posterior = result.output["result"]
    assert isinstance(posterior, PosteriorResult)
    assert posterior.method_name == "bayesian_nuts_regression"
    assert "sigma" in posterior.posterior_means
    assert 0.0 <= posterior.diagnostics["acceptance_rate"] <= 1.0
    assert posterior.diagnostics["max_depth"] == 4.0
    assert result.output["prediction_result"].method_name == "bayesian_nuts_regression"
    assert result.output["uncertainty_envelope"] is not None


def test_bayesian_nonparametric_mixture_methods_run() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    state = _make_mixture_state()

    gmm_cls = registry.get("bayesian.nonparametric.gaussian_mixture@1.0.0")
    gmm_result = dispatcher.dispatch(
        method_class=gmm_cls,
        signature=gmm_cls.signature,
        state=state,
        params={"n_components": 3, "max_iter": 40},
        seed=317,
    )
    assert isinstance(gmm_result.output["result"], PosteriorResult)
    assert gmm_result.output["result"].method_name == "bayesian_gaussian_mixture"
    assert np.asarray(gmm_result.output["cluster_assignments"], dtype=float).shape[0] == 100
    assert np.asarray(gmm_result.output["cluster_probabilities"], dtype=float).shape[0] == 100

    dpm_cls = registry.get("bayesian.nonparametric.dirichlet_process_mixture@1.0.0")
    dpm_result = dispatcher.dispatch(
        method_class=dpm_cls,
        signature=dpm_cls.signature,
        state=state,
        params={"max_components": 6, "prune_threshold": 0.08, "max_iter": 48},
        seed=319,
    )
    assert isinstance(dpm_result.output["result"], PosteriorResult)
    assert dpm_result.output["result"].method_name == "dirichlet_process_mixture"
    assert dpm_result.output["result"].metadata["active_components"] >= 1
    assert dpm_result.output["uncertainty_envelope"] is not None
