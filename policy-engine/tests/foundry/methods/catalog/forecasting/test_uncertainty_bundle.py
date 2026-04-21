from __future__ import annotations

import numpy as np

from polisyos.core.artifacts.store import FileSystemCAS


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def test_exponential_smoothing_emits_conformal_bundle(isolated_registry) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.univariate.exponential_smoothing@1.0.0")
    result = method.pure_step(
        {"series": np.array([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0])},
        {"horizon": 3, "alpha": 0.4, "beta": 0.2},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    assert bundle.interval_semantics.value == "conformalized_prediction_interval"
    assert bundle.calibration_method.value == "conformal"
    assert len(bundle.prediction_interval) == 3
    assert bundle.horizon_policy.gate_eligible is True
    receipt = bundle.to_truthfulness_receipt()
    assert receipt.truthfulness_scope == "marginal_coverage"
    assert receipt.runtime_truthfulness_tier in {"approximate_calibrated", "unverified"}


def test_ensemble_bundle_is_heuristic_when_only_member_paths_are_available(isolated_registry) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.ensemble.simple_average@1.0.0")
    result = method.pure_step(
        {"forecast_matrix": np.array([[1.0, 2.0, 3.0], [1.5, 2.5, 3.5], [0.5, 1.5, 2.5]])},
        {},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    assert bundle.interval_semantics.value == "heuristic_range"
    assert bundle.horizon_policy.gate_eligible is False
    assert bundle.coverage_diagnostic.recommended_fallback.value == "conformal"
    receipt = bundle.to_truthfulness_receipt()
    assert receipt.runtime_truthfulness_tier == "unverified"
    assert receipt.truthfulness_scope == "predictive_calibration"


def test_stl_bundle_marks_attached_output_only(isolated_registry) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.decomposition.stl@1.0.0")
    result = method.pure_step(
        {"series": np.array([7.0] * 16)},
        {"period": 4},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    assert bundle.prediction_interval == ()
    assert "attached_output_only" in bundle.coverage_diagnostic.regime_flags
    assert bundle.horizon_policy.gate_eligible is False


def test_prophet_bundle_persists_predictive_refs_when_artifact_store_is_available(
    isolated_registry,
    tmp_path,
) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.advanced.prophet@1.0.0")
    store = FileSystemCAS(tmp_path / "cas")

    result = method.pure_step(
        {"series": np.array([10.0, 10.5, 11.0, 11.8, 12.1, 12.6, 13.4, 13.8, 14.2, 14.9, 15.3, 15.7])},
        {"horizon": 4, "period": 4, "artifact_store": store, "predictive_draws": 8, "random_seed": 11},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    assert bundle.posterior_predictive_ref is not None
    assert bundle.posterior_predictive_ref.kind == "ir.forecasting_posterior_predictive"
    assert bundle.coverage_diagnostic.pit_summary_ref is not None
    assert bundle.to_truthfulness_receipt().truthfulness_scope.value == "marginal_coverage"


def test_ensemble_bundle_can_attach_member_path_ref(isolated_registry, tmp_path) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.ensemble.simple_average@1.0.0")
    store = FileSystemCAS(tmp_path / "cas")

    result = method.pure_step(
        {"forecast_matrix": np.array([[1.0, 2.0, 3.0], [1.5, 2.5, 3.5], [0.5, 1.5, 2.5]])},
        {"artifact_store": store},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    assert bundle.posterior_predictive_ref is not None
    assert bundle.coverage_diagnostic.sample_count_by_horizon[1] == 3
    assert bundle.coverage_diagnostic.mean_interval_width_by_horizon[2] == 1.0


def test_bottom_up_bundle_uses_coherent_bootstrap_when_sample_paths_are_provided(
    isolated_registry,
) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.reconciliation.bottom_up@1.0.0")
    bottom_forecasts = np.array([[10.0, 11.0, 12.0], [5.0, 5.5, 6.0]])
    bottom_sample_paths = np.array(
        [
            [[9.8, 10.7, 11.6], [4.9, 5.3, 5.9]],
            [[10.1, 11.2, 12.1], [5.1, 5.6, 6.1]],
            [[10.3, 11.1, 12.4], [5.2, 5.7, 6.3]],
        ]
    )

    result = method.pure_step(
        {
            "bottom_forecasts": bottom_forecasts,
            "aggregation_matrix": np.array([[1.0, 1.0], [1.0, 0.0], [0.0, 1.0]]),
            "bottom_sample_paths": bottom_sample_paths,
        },
        {},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    assert bundle.calibration_method.value == "coherent_bootstrap"
    assert bundle.interval_semantics.value == "prediction_interval"
    assert bundle.coverage_diagnostic.sample_count_by_horizon[1] == 3
