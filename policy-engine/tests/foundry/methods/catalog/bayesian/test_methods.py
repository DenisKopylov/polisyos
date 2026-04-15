from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods import ComputeBackend
from polisyos.foundry.methods.backends.bayesian_runner import bayesian_backend_health
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


def _make_sbi_state() -> dict[str, object]:
    rng = np.random.default_rng(321)
    parameters = rng.normal(size=(32, 2))
    simulations = np.column_stack(
        [
            parameters[:, 0] + 0.5 * parameters[:, 1],
            parameters[:, 0] ** 2 + rng.normal(scale=0.05, size=parameters.shape[0]),
        ]
    )
    return {
        "parameters": parameters,
        "simulations": simulations,
        "observed_summary": np.array([0.2, 0.1], dtype=float),
        "parameter_names": ["tax_elasticity", "takeup_slope"],
    }


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
    assert posterior.metadata["partial_pooling"] is True
    assert posterior.metadata["runtime_backend_used"] in {"numpy", "numpyro"}
    assert "uncertainty_decomposition" in posterior.metadata


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
    assert posterior.metadata["runtime_backend_used"] in {"numpy", "numpyro"}
    assert "uncertainty_decomposition" in posterior.metadata


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
    assert posterior.metadata["runtime_backend_used"] in {"numpy", "numpyro"}
    assert "uncertainty_decomposition" in posterior.metadata


def test_bayesian_hmc_explicit_numpyro_request_fails_closed_when_unavailable() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.sampling.hmc@1.0.0")
    health = bayesian_backend_health(method_cls)
    if health.default_runtime == "numpyro":
        pytest.skip("NumPyro is available in this environment")

    with pytest.raises(RuntimeError, match="numpyro"):
        dispatcher.dispatch(
            method_class=method_cls,
            signature=method_cls.signature,
            state=_make_tabular(),
            params={"runtime_backend": "numpyro"},
            seed=999,
        )


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


def test_ep_svgd_flow_and_factor_graph_frontier_methods_run() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    ep_cls = registry.get("bayesian.approximation.expectation_propagation_gaussian@1.0.0")
    ep_result = dispatcher.dispatch(
        method_class=ep_cls,
        signature=ep_cls.signature,
        state={
            "site_means": np.array([[0.2, 1.0], [0.4, 0.8], [0.3, 1.2]], dtype=float),
            "site_variances": np.array([[0.4, 0.5], [0.6, 0.4], [0.5, 0.7]], dtype=float),
            "parameter_names": ["tax_rate", "elasticity"],
        },
        params={"credible_mass": 0.9},
        seed=331,
    )
    assert isinstance(ep_result.output["result"], PosteriorResult)
    assert ep_result.output["result"].metadata["truthfulness_tier"] == "gaussian_ep_site_approximation"

    svgd_cls = registry.get("bayesian.variational.svgd_regression@1.0.0")
    svgd_result = dispatcher.dispatch(
        method_class=svgd_cls,
        signature=svgd_cls.signature,
        state=_make_tabular(),
        params={"num_particles": 10, "num_steps": 6, "step_size": 0.004},
        seed=333,
    )
    assert svgd_result.output["result"].method_name == "svgd_regression"
    assert svgd_result.output["prediction_result"].method_name == "svgd_regression"

    flow_cls = registry.get("bayesian.flow.affine_normalizing_flow@1.0.0")
    rng = np.random.default_rng(335)
    flow_result = dispatcher.dispatch(
        method_class=flow_cls,
        signature=flow_cls.signature,
        state={
            "posterior_samples": rng.normal(size=(48, 2)),
            "parameter_names": ["theta_tax", "theta_takeup"],
        },
        params={"num_flow_samples": 40},
        seed=337,
    )
    assert flow_result.output["result"].metadata["flow_family"] == "affine_gaussian"
    assert np.asarray(flow_result.output["posterior_samples"]).shape == (40, 2)

    factor_cls = registry.get("bayesian.graphical.factor_graph_belief_propagation@1.0.0")
    factor_result = dispatcher.dispatch(
        method_class=factor_cls,
        signature=factor_cls.signature,
        state={
            "unary_log_potentials": np.log(np.array([[0.7, 0.3], [0.4, 0.6], [0.55, 0.45]])),
            "edges": np.array([[0, 1], [1, 2]], dtype=int),
            "pairwise_log_potentials": np.log(
                np.array(
                    [
                        [[0.85, 0.15], [0.15, 0.85]],
                        [[0.8, 0.2], [0.2, 0.8]],
                    ],
                    dtype=float,
                )
            ),
        },
        params={"max_iter": 20, "tol": 1e-8},
        seed=339,
    )
    marginals = np.asarray(factor_result.output["marginals"], dtype=float)
    assert factor_result.output["result"].method_name == "factor_graph_belief_propagation"
    assert marginals.shape == (3, 2)
    assert np.allclose(np.sum(marginals, axis=1), np.ones(3))


@pytest.mark.parametrize(
    "fqn, expected_variant",
    [
        ("bayesian.sbi.npe@1.0.0", "npe"),
        ("bayesian.sbi.nle@1.0.0", "nle"),
        ("bayesian.sbi.nre@1.0.0", "nre"),
    ],
)
def test_sbi_methods_fail_closed_when_runtime_stack_unavailable(
    fqn: str,
    expected_variant: str,
) -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get(fqn)
    health = bayesian_backend_health(method_cls)
    assert health.preferred_engine == "sbi"
    if health.default_runtime == "sbi":
        pytest.skip("SBI runtime stack is available in this environment")

    with pytest.raises(RuntimeError, match=expected_variant):
        dispatcher.dispatch(
            method_class=method_cls,
            signature=method_cls.signature,
            state=_make_sbi_state(),
            params={},
            seed=323,
        )


def test_bart_method_fails_closed_when_pymc_bart_stack_unavailable() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.nonparametric.bart_regression@1.0.0")
    health = bayesian_backend_health(method_cls)
    assert health.preferred_engine == "pymc_bart"
    if health.default_runtime == "pymc_bart":
        pytest.skip("PyMC-BART runtime stack is available in this environment")

    with pytest.raises(RuntimeError, match="bart"):
        dispatcher.dispatch(
            method_class=method_cls,
            signature=method_cls.signature,
            state=_make_tabular(),
            params={},
            seed=329,
        )
