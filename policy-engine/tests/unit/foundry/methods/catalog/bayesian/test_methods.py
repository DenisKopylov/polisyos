from __future__ import annotations

import numpy as np
import pytest
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
)
from polisyos.core.observability.truthfulness import (
    TruthfulnessTier as ReceiptTruthfulnessTier,
)
from polisyos.foundry.methods.backends.bayesian_runner import bayesian_backend_health
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import ComputeBackend
from polisyos.foundry.methods.bayesian import (
    PosteriorResult,
    SimulatorDiagnosticArtifact,
    TruthfulnessTier,
    canonical_simulator_diagnostic_artifact,
    ensure_bayesian_methods_registered,
)
from polisyos.foundry.methods.catalog.bayesian.frontier import (
    _build_sbi_diagnostic_artifact,
    _sbi_regime_training_view,
    _simulation_regimes_from_sources,
)
from polisyos.foundry.methods.catalog.bayesian.protocols import MultimodalityState
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


def _pin_single_thread_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    keys: tuple[str, ...] | None = None,
) -> None:
    all_keys = (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS",
    )
    for key in all_keys:
        monkeypatch.delenv(key, raising=False)
    for key in all_keys if keys is None else keys:
        monkeypatch.setenv(key, "1")


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
    assert posterior.truthfulness.basis == "asymptotic_sampler_runtime_diagnostics"
    assert posterior.truthfulness_tier in {
        TruthfulnessTier.ASYMPTOTIC,
        TruthfulnessTier.APPROXIMATE_UNCALIBRATED,
    }


def test_bayesian_autoregression_runs() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.timeseries.autoregression@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_time_series(),
        params={
            "n_lags": 2,
            "num_warmup": 40,
            "num_samples": 56,
            "num_chains": 2,
            "proposal_scale": 0.03,
        },
        seed=311,
    )

    posterior = result.output["result"]
    assert isinstance(posterior, PosteriorResult)
    assert posterior.method_name == "bayesian_autoregression"
    assert "phi_0" in posterior.posterior_means
    assert result.output["prediction_result"].method_name == "bayesian_autoregression"
    assert result.output["uncertainty_envelope"] is not None
    assert result.reproducibility.backend is ComputeBackend.BAYESIAN
    assert posterior.truthfulness.basis == "asymptotic_sampler_runtime_diagnostics"
    assert posterior.truthfulness_tier in {
        TruthfulnessTier.ASYMPTOTIC,
        TruthfulnessTier.APPROXIMATE_UNCALIBRATED,
    }


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
    assert posterior.truthfulness.basis == "asymptotic_sampler_runtime_diagnostics"
    assert posterior.truthfulness_tier in {
        TruthfulnessTier.ASYMPTOTIC,
        TruthfulnessTier.APPROXIMATE_UNCALIBRATED,
    }


def test_bayesian_hmc_regression_runs() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.sampling.hmc@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={
            "num_warmup": 32,
            "num_samples": 48,
            "num_chains": 2,
            "step_size": 0.015,
            "n_leapfrog": 10,
        },
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
    assert posterior.truthfulness.basis == "asymptotic_sampler_runtime_diagnostics"
    assert posterior.truthfulness_tier in {
        TruthfulnessTier.ASYMPTOTIC,
        TruthfulnessTier.APPROXIMATE_UNCALIBRATED,
    }
    assert posterior.sampler_kernel == "hmc"
    assert posterior.reproducibility["effective_runtime_backend"] in {"numpy", "numpyro"}


def test_bayesian_nuts_regression_runs() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.sampling.nuts@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={
            "num_warmup": 32,
            "num_samples": 40,
            "num_chains": 2,
            "max_depth": 4,
            "step_size": 0.012,
        },
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
    assert posterior.truthfulness.basis == "asymptotic_sampler_runtime_diagnostics"
    assert posterior.truthfulness_tier in {
        TruthfulnessTier.ASYMPTOTIC,
        TruthfulnessTier.APPROXIMATE_UNCALIBRATED,
    }
    assert posterior.sampler_kernel == "nuts"
    assert posterior.reproducibility["effective_runtime_backend"] in {"numpy", "numpyro"}


def test_bayesian_hmc_reference_numpy_backend_emits_replay_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_single_thread_env(monkeypatch)
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.sampling.hmc@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={
            "runtime_backend": "numpy",
            "num_warmup": 32,
            "num_samples": 48,
            "num_chains": 4,
            "step_size": 0.015,
            "n_leapfrog": 10,
        },
        seed=1314,
    )

    posterior = result.output["result"]
    assert isinstance(posterior, PosteriorResult)
    assert result.reproducibility.determinism_tier is DeterminismTier.LIBRARY_DETERMINISTIC
    assert (
        result.artifacts["backend_runtime_fingerprint"]["determinism_tier"]
        == "library_deterministic"
    )
    assert posterior.draws_ref == result.artifacts["posterior_draws"]["artifact_ref"]
    assert posterior.warmup_draws_ref == result.artifacts["warmup_draws"]["artifact_ref"]
    assert posterior.reproducibility["effective_runtime_backend"] == "numpy"
    assert posterior.reproducibility["effective_determinism_tier"] == "library_deterministic"
    assert posterior.reproducibility["route_key"]["backend_route"] == "bayesian:numpy"
    assert (
        posterior.reproducibility["observed_tolerance_budget"]["route_key"]["backend_route"]
        == "bayesian:numpy"
    )
    assert posterior.reproducibility["observed_tolerance_budget"]["budget_source"] == "seed_prior"
    assert posterior.reproducibility["replay_output_hash"].startswith("sha256:")
    assert (
        posterior.reproducibility["determinism_envelope"]["thread_configuration"][
            "single_thread_pinned"
        ]
        is True
    )
    assert (
        posterior.reproducibility["determinism_envelope"]["rng_partitioning"]["scheme"]
        == "seedsequence_substreams"
    )
    assert posterior.sampler_family == "mcmc"
    assert "minimum_chains" in posterior.diagnostic_gates


def test_bayesian_hmc_reference_numpy_backend_replays_identical_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_single_thread_env(monkeypatch)
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.sampling.hmc@1.0.0")
    params = {
        "runtime_backend": "numpy",
        "num_warmup": 32,
        "num_samples": 48,
        "num_chains": 4,
        "step_size": 0.015,
        "n_leapfrog": 10,
    }

    first = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params=params,
        seed=1316,
    )
    second = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params=params,
        seed=1316,
    )

    first_posterior = first.output["result"]
    second_posterior = second.output["result"]
    assert isinstance(first_posterior, PosteriorResult)
    assert isinstance(second_posterior, PosteriorResult)
    assert (
        first_posterior.reproducibility["replay_output_hash"]
        == second_posterior.reproducibility["replay_output_hash"]
    )
    assert (
        first.artifacts["posterior_draws"]["payload"]
        == second.artifacts["posterior_draws"]["payload"]
    )
    assert first.artifacts["warmup_draws"]["payload"] == second.artifacts["warmup_draws"]["payload"]


def test_bayesian_hmc_reference_numpy_requires_full_thread_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_single_thread_env(monkeypatch, keys=("OMP_NUM_THREADS",))
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.sampling.hmc@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={
            "runtime_backend": "numpy",
            "num_warmup": 32,
            "num_samples": 48,
            "num_chains": 4,
            "step_size": 0.015,
            "n_leapfrog": 10,
        },
        seed=1317,
    )

    posterior = result.output["result"]
    assert isinstance(posterior, PosteriorResult)
    assert result.reproducibility.determinism_tier is DeterminismTier.STATISTICAL
    assert posterior.degradation_reason == "thread_configuration_not_pinned_single_thread"
    assert (
        "determinism_degraded:thread_configuration_not_pinned_single_thread" in posterior.warnings
    )


def test_bayesian_hmc_reference_contract_marks_gate_failures_in_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_single_thread_env(monkeypatch)
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.sampling.hmc@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={
            "runtime_backend": "numpy",
            "num_warmup": 32,
            "num_samples": 48,
            "num_chains": 2,
            "step_size": 0.015,
            "n_leapfrog": 10,
        },
        seed=1318,
    )

    posterior = result.output["result"]
    assert isinstance(posterior, PosteriorResult)
    assert posterior.status == "diagnostics_failed"
    assert posterior.diagnostic_gates["minimum_chains"] is False
    assert "diagnostic_gate_failed:minimum_chains" in posterior.warnings
    assert posterior.multimodality_status.state is MultimodalityState.INCONCLUSIVE_SAMPLING_GEOMETRY
    assert "posterior_geometry:inconclusive_sampling_geometry" in posterior.warnings


def test_bayesian_nuts_auto_backend_degrades_from_exact_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pin_single_thread_env(monkeypatch)
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("bayesian.sampling.nuts@1.0.0")
    health = bayesian_backend_health(method_cls)
    if health.default_runtime != "numpy":
        pytest.skip("Auto backend resolves to an accelerated runtime in this environment")

    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_tabular(),
        params={
            "runtime_backend": "auto",
            "num_warmup": 32,
            "num_samples": 40,
            "num_chains": 4,
            "max_depth": 4,
            "step_size": 0.012,
        },
        seed=1315,
    )

    posterior = result.output["result"]
    assert isinstance(posterior, PosteriorResult)
    assert posterior.metadata["runtime_backend_used"] == "numpy"
    assert result.reproducibility.determinism_tier is DeterminismTier.STATISTICAL
    assert result.artifacts["backend_runtime_fingerprint"]["determinism_tier"] == "statistical"
    assert posterior.degradation_reason == "runtime_backend_auto_not_allowed"
    assert posterior.reproducibility["route_key"]["backend_route"] == "bayesian:numpy"
    assert posterior.reproducibility["observed_tolerance_budget"]["mode"] == "distributional"
    assert "determinism_degraded:runtime_backend_auto_not_allowed" in posterior.warnings


def test_posterior_result_exposes_truthfulness_receipt_from_metadata() -> None:
    posterior = PosteriorResult(
        method_name="toy_posterior",
        metadata={
            "truthfulness_receipt": TruthfulnessReceipt(
                runtime_truthfulness_tier=ReceiptTruthfulnessTier.ASYMPTOTIC,
                truthfulness_scope=TruthfulnessScope.POSTERIOR,
            ).model_dump(mode="json")
        },
    )

    receipt = posterior.to_truthfulness_receipt()
    assert receipt is not None
    assert receipt.runtime_truthfulness_tier == "asymptotic"
    assert receipt.truthfulness_scope == "posterior"


def test_mean_field_vi_earns_runtime_calibrated_tier_on_conjugate_case() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    calibrated_state = TabularData(
        features=np.array([[0.0], [0.5], [1.0], [1.5], [2.0], [2.5], [3.0], [3.5]], dtype=float),
        target=np.array([1.0, 2.0, 2.7, 3.75, 4.55, 5.5, 6.5, 7.2], dtype=float),
        feature_names=["x"],
    )

    method_cls = registry.get("bayesian.variational.mean_field_vi@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=calibrated_state,
        params={"prior_scale": 1.0, "noise_variance": 0.1, "max_iter": 200, "tol": 1e-8},
        seed=42,
    )

    posterior = result.output["result"]
    assert posterior.truthfulness_tier is TruthfulnessTier.APPROXIMATE_CALIBRATED
    assert posterior.truthfulness.basis == "variational_reference_posterior_calibration"
    assert posterior.diagnostics["joint_psis_pareto_k"] < 0.7
    assert posterior.diagnostics["offline_coverage_error_max"] <= 1e-8


def test_posterior_result_infers_family_specific_approximate_calibration() -> None:
    benchmark_metadata = {
        "benchmark_regime": "phase0_suite",
        "coverage_tolerance": 0.05,
        "offline_calibration_passed": True,
    }
    cases = [
        (
            "expectation_propagation_gaussian",
            {
                "cavity_precision_min": 0.2,
                "site_precision_cv": 0.5,
                "site_mean_z_residual_max": 0.25,
                "site_skewness_proxy": 0.1,
                "site_kurtosis_proxy": 0.2,
            },
            benchmark_metadata,
        ),
        (
            "svgd_regression",
            {
                "ksd_rbf": 0.05,
                "unique_particle_fraction": 0.95,
                "split_interval_shift_max": 0.01,
                "posthoc_interval_shift_max": 0.01,
            },
            benchmark_metadata,
        ),
        (
            "affine_normalizing_flow",
            {
                "source_mean_shift_max": 0.05,
                "source_covariance_error_fro": 0.1,
                "source_interval_shift_max": 0.01,
                "jacobian_condition_number": 12.0,
            },
            {"source_truthfulness_tier": "exact"},
        ),
        (
            "simulation_based_npe",
            {
                "observed_neighborhood_count": 32.0,
                "observed_neighborhood_radius_quantile": 0.1,
                "posterior_sbc_error": 0.02,
                "local_c2st_score": 0.55,
                "ppc_mahalanobis": 1.2,
            },
            benchmark_metadata,
        ),
        (
            "bayesian_gaussian_mixture",
            {
                "multistart_weight_shift_max": 0.01,
                "multistart_mean_shift_max": 0.1,
                "component_collapse_fraction": 0.0,
                "entropy": 0.2,
            },
            benchmark_metadata,
        ),
        (
            "factor_graph_belief_propagation",
            {
                "final_delta": 1e-8,
                "message_residual_tolerance": 1e-6,
                "subgraph_crosscheck_max_error": 0.01,
            },
            benchmark_metadata,
        ),
    ]

    for method_name, diagnostics, metadata in cases:
        posterior = PosteriorResult(
            method_name=method_name,
            diagnostics=diagnostics,
            metadata=metadata,
        )
        assert posterior.truthfulness_tier is TruthfulnessTier.APPROXIMATE_CALIBRATED
        assert posterior.truthfulness.downgrade_reasons == []


def test_sbi_regime_contract_requires_simulator_diagnostic_ref() -> None:
    diagnostics = {
        "observed_neighborhood_count": 32.0,
        "observed_neighborhood_radius_quantile": 0.1,
        "support_quantile": 0.2,
        "knn_radius_mahalanobis": 1.4,
        "effective_local_simulations": 48.0,
        "posterior_sbc_error": 0.02,
        "tarp_coverage_error": 0.02,
        "local_c2st_score": 0.55,
        "ppc_mahalanobis": 1.2,
    }
    metadata = {
        "benchmark_regime": "phase0_suite",
        "coverage_tolerance": 0.05,
        "offline_calibration_passed": True,
        "diagnostic_contract": {"support_required": True},
        "observed_regime": {"calendar_period": "2024Q3", "policy_regime": "benefit-v2"},
    }

    missing_ref = PosteriorResult(
        method_name="simulation_based_npe",
        diagnostics=diagnostics,
        metadata=metadata,
    )
    assert missing_ref.truthfulness_tier is TruthfulnessTier.APPROXIMATE_UNCALIBRATED
    assert "simulator_diagnostic_ref_missing" in missing_ref.truthfulness.downgrade_reasons

    with_ref = PosteriorResult(
        method_name="simulation_based_npe",
        diagnostics=diagnostics,
        metadata=metadata,
        simulator_diagnostic_ref="artifact://foundry/sbi/diagnostic/example",
    )
    assert with_ref.truthfulness_tier is TruthfulnessTier.APPROXIMATE_CALIBRATED
    assert with_ref.to_truthfulness_receipt().evidence_ref == (
        "artifact://foundry/sbi/diagnostic/example"
    )


def test_sbi_support_failure_degrades_posterior_status() -> None:
    diagnostic = SimulatorDiagnosticArtifact(
        observed_regime={
            "calendar_period": "2024Q3",
            "policy_regime": "benefit-v2",
            "admin_schema": "admin-v2",
        },
        support_quantile=0.001,
        knn_radius_mahalanobis=8.0,
        effective_local_simulations=4,
        local_c2st_score=0.55,
        posterior_sbc_error=0.02,
        tarp_coverage_error=0.02,
        ppc_mahalanobis=1.2,
        status="fail",
        failure_mode=("regime_extrapolation",),
        artifact_ref="artifact://foundry/sbi/diagnostic/fail",
    )

    posterior = PosteriorResult(
        method_name="simulation_based_npe",
        diagnostics={
            "observed_neighborhood_count": 32.0,
            "observed_neighborhood_radius_quantile": 0.1,
            "posterior_sbc_error": 0.02,
            "local_c2st_score": 0.55,
            "ppc_mahalanobis": 1.2,
        },
        metadata={
            "benchmark_regime": "phase0_suite",
            "coverage_tolerance": 0.05,
            "offline_calibration_passed": True,
            "diagnostic_contract": {"support_required": True},
            "simulator_diagnostic": diagnostic.model_dump(mode="python", by_alias=True),
            "simulator_diagnostic_ref": "artifact://foundry/sbi/diagnostic/fail",
        },
    )

    assert posterior.status == "degraded"
    assert posterior.degradation_reason == "simulator_support_failure"
    assert posterior.truthfulness_tier is TruthfulnessTier.APPROXIMATE_UNCALIBRATED
    assert "simulator_support_failure" in posterior.truthfulness.downgrade_reasons


def test_sbi_regime_training_view_uses_local_simulation_budget() -> None:
    parameters = np.arange(80, dtype=float).reshape(40, 2)
    simulations = parameters[:, :1]
    regimes = [{"calendar_period": "2024Q3", "policy_regime": "benefit-v2"} for _ in range(20)] + [
        {"calendar_period": "2024Q4", "policy_regime": "benefit-v3"} for _ in range(20)
    ]
    observed_regime = {"calendar_period": "2024Q3", "policy_regime": "benefit-v2"}

    simulation_regimes = _simulation_regimes_from_sources(
        ({"simulation_regimes": regimes},),
        n_rows=40,
    )
    local_parameters, local_simulations, diagnostics = _sbi_regime_training_view(
        parameters=parameters,
        simulations=simulations,
        observed_regime=observed_regime,
        simulation_regimes=simulation_regimes,
        min_local=16,
    )

    assert local_parameters.shape[0] == 20
    assert local_simulations.shape[0] == 20
    assert diagnostics["effective_local_simulations"] == 20
    assert diagnostics["regime_local_training_used"] is True

    pooled_parameters, _, pooled_diagnostics = _sbi_regime_training_view(
        parameters=parameters,
        simulations=simulations,
        observed_regime={"calendar_period": "2025Q1", "policy_regime": "benefit-v9"},
        simulation_regimes=simulation_regimes,
        min_local=16,
    )

    assert pooled_parameters.shape[0] == 40
    assert pooled_diagnostics["effective_local_simulations"] == 0
    assert pooled_diagnostics["pooled_training_used"] is True


def test_sbi_runtime_diagnostic_artifact_is_canonical_and_gate_aware() -> None:
    diagnostics = {
        "support_quantile": 0.2,
        "knn_radius_mahalanobis": 1.2,
        "effective_local_simulations": 32.0,
        "simulation_regimes_declared": True,
        "posterior_sbc_error": 0.02,
        "tarp_coverage_error": 0.02,
        "local_c2st_score": 0.55,
        "ppc_mahalanobis": 1.2,
    }
    observed_regime = {"calendar_period": "2024Q3", "policy_regime": "benefit-v2"}
    metadata = {
        "coverage_tolerance": 0.05,
        "diagnostic_contract": {
            "thresholds": {
                "support_quantile_min": 0.01,
                "knn_radius_mahalanobis_max": 4.0,
                "min_effective_local_simulations": 16,
            }
        },
    }

    ref, artifact, digest = _build_sbi_diagnostic_artifact(
        observed_regime=observed_regime,
        diagnostics=diagnostics,
        metadata=metadata,
    )

    assert ref.startswith("artifact://foundry/sbi/simulator_diagnostic/")
    assert digest in ref
    assert artifact["schema"] == SimulatorDiagnosticArtifact.contract_id
    assert artifact["status"] == "pass"
    assert artifact.get("failure_mode") in (None, [], ())

    failing_ref, failing_artifact, _ = _build_sbi_diagnostic_artifact(
        observed_regime=observed_regime,
        diagnostics={**diagnostics, "effective_local_simulations": 4.0},
        metadata=metadata,
    )

    assert failing_ref != ref
    assert failing_artifact["status"] == "fail"
    assert "regime_extrapolation" in failing_artifact["failure_mode"]


def test_simulator_diagnostic_artifact_hash_is_stable() -> None:
    diagnostic = SimulatorDiagnosticArtifact(
        observed_regime={"calendar_period": "2024Q3", "policy_regime": "benefit-v2"},
        support_quantile=0.2,
        knn_radius_mahalanobis=1.2,
        effective_local_simulations=32,
        local_c2st_score=0.55,
        posterior_sbc_error=0.02,
        tarp_coverage_error=0.02,
        ppc_mahalanobis=1.2,
        status="pass",
    )

    first_ref, first_artifact, first_digest = canonical_simulator_diagnostic_artifact(diagnostic)
    second_ref, second_artifact, second_digest = canonical_simulator_diagnostic_artifact(
        diagnostic.model_dump(mode="python", by_alias=True)
    )

    assert first_ref == second_ref
    assert first_digest == second_digest
    assert first_artifact == second_artifact


def test_sbi_method_metadata_declares_regime_aware_contract() -> None:
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("bayesian.sbi.npe@1.0.0")

    metadata = method_cls.metadata
    assert metadata.simulator_regime_schema["stationarity_assumption"] == (
        "piecewise_stationary_given_regime"
    )
    assert metadata.summary_schema_ref == "artifact://foundry/sbi/summary_schema/regime-aware-v1"
    assert metadata.identifiable_target["equivalence_classes_allowed"] is True
    assert metadata.coverage_contract["locality"] == "conditional_on_regime"
    assert "effective_local_simulations" in metadata.diagnostic_contract["required_metrics"]
    assert "observed_regime" in method_cls.signature.input_slot_names
    assert "simulation_regimes" in method_cls.signature.input_slot_names
    assert "simulator_diagnostic_ref" in method_cls.signature.output_slot_names


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
    assert ep_result.output["result"].truthfulness_tier is TruthfulnessTier.APPROXIMATE_UNCALIBRATED

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
    assert (
        svgd_result.output["result"].truthfulness_tier is TruthfulnessTier.APPROXIMATE_UNCALIBRATED
    )

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
    assert (
        flow_result.output["result"].truthfulness_tier is TruthfulnessTier.APPROXIMATE_UNCALIBRATED
    )

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
    assert factor_result.output["result"].truthfulness_tier is TruthfulnessTier.EXACT


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
