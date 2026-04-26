from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def test_exponential_smoothing_emits_conformal_bundle(isolated_registry) -> None:
    method = _method_or_skip(
        isolated_registry, "forecasting.univariate.exponential_smoothing@1.0.0"
    )
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


def test_ensemble_bundle_is_heuristic_when_only_member_paths_are_available(
    isolated_registry,
) -> None:
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
        {
            "series": np.array(
                [10.0, 10.5, 11.0, 11.8, 12.1, 12.6, 13.4, 13.8, 14.2, 14.9, 15.3, 15.7]
            )
        },
        {
            "horizon": 4,
            "period": 4,
            "artifact_store": store,
            "predictive_draws": 8,
            "random_seed": 11,
        },
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
    assert bundle.reconciliation_certificate.status.value == "fallback"
    assert bundle.reconciliation_certificate.coherent_paths is True
    assert "aggregation_gap_by_horizon" in bundle.reconciliation_certificate.diagnostics


def test_bottom_up_bundle_certifies_reconciled_conformal_when_calibration_bank_is_provided(
    isolated_registry,
) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.reconciliation.bottom_up@1.0.0")
    aggregation_matrix = np.array([[1.0, 1.0], [1.0, 0.0], [0.0, 1.0]])
    bottom_forecasts = np.array([[10.0, 11.0], [5.0, 5.5]])
    calibration_bottom_forecasts = np.repeat(bottom_forecasts[None, :, :], 6, axis=0)
    calibration_actuals = np.einsum(
        "ij,pjk->pik",
        aggregation_matrix,
        calibration_bottom_forecasts,
        optimize=True,
    )

    result = method.pure_step(
        {
            "bottom_forecasts": bottom_forecasts,
            "aggregation_matrix": aggregation_matrix,
            "calibration_bottom_forecasts": calibration_bottom_forecasts,
            "calibration_actuals": calibration_actuals,
        },
        {"min_reconciliation_calibration_count": 5},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    assert bundle.schema_version == "2.0"
    assert bundle.calibration_method.value == "conformal_after_reconciliation"
    assert bundle.interval_semantics.value == "conformalized_prediction_interval"
    assert bundle.reconciliation_certificate.status.value == "certified"
    assert bundle.reconciliation_certificate.coverage_scope == "per_series_marginal"
    assert bundle.reconciliation_certificate.diagnostics[
        "max_point_aggregation_error_by_horizon"
    ][1] == 0.0
    receipt = bundle.to_truthfulness_receipt()
    assert receipt.runtime_truthfulness_tier.value == "approximate_calibrated"
    assert receipt.truthfulness_scope.value == "marginal_coverage"


def test_bottom_up_fallback_reports_unreconciled_interval_aggregation_gap(
    isolated_registry,
) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.reconciliation.bottom_up@1.0.0")
    aggregation_matrix = np.array([[1.0, 1.0], [1.0, 0.0], [0.0, 1.0]])

    result = method.pure_step(
        {
            "bottom_forecasts": np.array([[10.0], [5.0]]),
            "aggregation_matrix": aggregation_matrix,
            "unreconciled_interval_lower": np.array([[20.0], [9.0], [5.0]]),
            "unreconciled_interval_upper": np.array([[21.0], [10.0], [6.0]]),
        },
        {},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    diagnostics = bundle.reconciliation_certificate.diagnostics

    assert bundle.schema_version == "2.0"
    assert bundle.horizon_policy.gate_eligible is False
    assert bundle.reconciliation_certificate.status.value == "fallback"
    assert diagnostics["aggregation_gap_by_horizon"][1] == pytest.approx(4.0)
    assert diagnostics["fallback_interval_source"] == "unreconciled_per_series_intervals"
    assert diagnostics["base_interval_point_containment_adjustment_by_horizon"][1] > 0.0
    assert "intervals_not_reconciled" in bundle.coverage_diagnostic.regime_flags


def test_bottom_up_certified_bundle_records_tightening_and_coherent_path_fan_chart(
    isolated_registry,
) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.reconciliation.bottom_up@1.0.0")
    aggregation_matrix = np.array([[1.0, 1.0], [1.0, 0.0], [0.0, 1.0]])
    bottom_forecasts = np.array([[10.0, 11.0], [5.0, 5.5]])
    calibration_bottom_forecasts = np.repeat(bottom_forecasts[None, :, :], 6, axis=0)
    calibration_actuals = np.einsum(
        "ij,pjk->pik",
        aggregation_matrix,
        calibration_bottom_forecasts,
        optimize=True,
    )
    calibration_unreconciled = calibration_actuals + 1.0
    bottom_sample_paths = np.array(
        [
            [[9.5, 10.6], [4.8, 5.1]],
            [[10.0, 11.0], [5.0, 5.5]],
            [[10.5, 11.4], [5.2, 5.9]],
        ]
    )

    result = method.pure_step(
        {
            "bottom_forecasts": bottom_forecasts,
            "aggregation_matrix": aggregation_matrix,
            "bottom_sample_paths": bottom_sample_paths,
            "calibration_bottom_forecasts": calibration_bottom_forecasts,
            "calibration_actuals": calibration_actuals,
            "calibration_unreconciled_forecasts": calibration_unreconciled,
        },
        {"min_reconciliation_calibration_count": 5},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    diagnostics = bundle.reconciliation_certificate.diagnostics

    assert bundle.reconciliation_certificate.status.value == "certified"
    assert bundle.reconciliation_certificate.coherent_paths is True
    assert diagnostics["fan_chart_source"] == "coherent_sample_paths"
    assert diagnostics["width_reduction_vs_unreconciled_by_horizon"][1] > 0.0
    assert diagnostics["unreconciled_mean_interval_width_by_horizon"][1] > diagnostics[
        "mean_interval_width_by_horizon"
    ][1]


def test_general_linear_reconciliation_certifies_constraint_projection(
    isolated_registry,
) -> None:
    method = _method_or_skip(
        isolated_registry,
        "forecasting.reconciliation.general_linear_projection@1.0.0",
    )
    constraints = np.array([[1.0, -1.0, -1.0]])
    base_forecasts = np.array([[20.0, 21.0], [8.0, 9.0], [5.0, 5.5]])
    projection = np.eye(3) - constraints.T @ np.linalg.pinv(constraints @ constraints.T) @ constraints
    calibration_base = np.repeat(base_forecasts[None, :, :], 6, axis=0)
    calibration_actuals = np.einsum(
        "ij,pjk->pik",
        projection,
        calibration_base,
        optimize=True,
    )

    result = method.pure_step(
        {
            "base_forecasts": base_forecasts,
            "constraint_matrix": constraints,
            "constraints_kind": "grouped",
            "calibration_base_forecasts": calibration_base,
            "calibration_actuals": calibration_actuals,
        },
        {"min_reconciliation_calibration_count": 5},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    reconciled = np.asarray(result["result"]["reconciled_forecasts"], dtype=float)
    diagnostics = bundle.reconciliation_certificate.diagnostics

    assert np.max(np.abs(constraints @ reconciled)) < 1e-9
    assert bundle.schema_version == "2.0"
    assert bundle.reconciliation_certificate.status.value == "certified"
    assert bundle.reconciliation_certificate.method.value == "general_linear_projection"
    assert bundle.reconciliation_certificate.constraints_kind == "grouped"
    assert diagnostics["max_point_constraint_error_by_horizon"][1] < 1e-9


def test_guarded_neural_red_zone_routes_to_baseline_source(
    isolated_registry,
    tmp_path,
) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.hybrid.guarded_neural@1.0.0")
    store = FileSystemCAS(tmp_path / "selection-cas")
    t = np.arange(48, dtype=float)
    series = 10.0 + 0.2 * t + 2.0 * np.sin((2.0 * np.pi * t) / 12.0)

    result = method.pure_step(
        {"series": series},
        {
            "horizon": 4,
            "period": 12,
            "neural_family": "nbeats",
            "artifact_store": store,
        },
    )

    bundle = result["forecasting_uncertainty_bundle"]
    selection = bundle.metadata["method_selection"]
    assert bundle.method_fqn == "forecasting.hybrid.guarded_neural@1.0.0"
    assert bundle.source_method == result["result"]["baseline_method"]
    assert result["result"]["source_method"] == result["result"]["baseline_method"]
    assert selection["trust_region_state"] == "red"
    assert selection["shadow_only"] is True
    assert selection["selection_reason"] == "prefit_trust_region_backoff"
    assert selection["neural_backend_status"] == "available"
    assert selection["decision_thresholds"]["red_min_obs"] == 60
    assert selection["selection_artifact_ref"]["kind"] == "ir.forecasting_method_selection"
    assert "neural_outside_trust_region" in bundle.coverage_diagnostic.regime_flags
    assert "shadow_only_neural" in bundle.coverage_diagnostic.regime_flags
    assert result["result"]["shadow_forecast"] is not None


def test_guarded_neural_amber_zone_keeps_nbeats_in_shadow(isolated_registry) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.hybrid.guarded_neural@1.0.0")
    t = np.arange(72, dtype=float)
    series = 20.0 + 0.1 * t + 1.5 * np.sin((2.0 * np.pi * t) / 12.0)

    result = method.pure_step(
        {"series": series},
        {"horizon": 5, "period": 12, "neural_family": "nbeats"},
    )

    bundle = result["forecasting_uncertainty_bundle"]
    selection = bundle.metadata["method_selection"]
    assert selection["trust_region_state"] == "amber"
    assert selection["shadow_only"] is True
    assert selection["neural_method"] == "forecasting.neural.nbeats_like_challenger@1.0.0"
    assert result["result"]["source_method"] == result["result"]["baseline_method"]
    assert result["result"]["shadow_forecast"] is not None
    assert "shadow_only_neural" in bundle.coverage_diagnostic.regime_flags
    assert "neural_outside_trust_region" not in bundle.coverage_diagnostic.regime_flags


def test_guarded_neural_records_global_family_backoff(isolated_registry) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.hybrid.guarded_neural@1.0.0")
    t = np.arange(120, dtype=float)
    series = 30.0 + 0.08 * t + 1.2 * np.sin((2.0 * np.pi * t) / 12.0)

    result = method.pure_step(
        {"series": series},
        {
            "horizon": 4,
            "period": 12,
            "neural_family": "deepar",
            "related_series_count": 3,
        },
    )

    bundle = result["forecasting_uncertainty_bundle"]
    selection = bundle.metadata["method_selection"]
    assert selection["trust_region_state"] == "red"
    assert selection["neural_method"] == "forecasting.neural.deepar_challenger@1.0.0"
    assert selection["neural_backend_status"] == "adapter_not_configured"
    assert "forecasting.neural.deepar_challenger@1.0.0" in selection["candidate_methods"]
    assert "global_pool_insufficient" in selection["trust_region_reasons"]
    assert "global_pool_insufficient" in bundle.coverage_diagnostic.regime_flags
    assert "neural_backend_unavailable" in bundle.coverage_diagnostic.regime_flags
    assert result["result"]["shadow_forecast"] is None


def test_guarded_neural_green_zone_can_emit_guarded_ensemble(isolated_registry) -> None:
    method = _method_or_skip(isolated_registry, "forecasting.hybrid.guarded_neural@1.0.0")
    t = np.arange(120, dtype=float)
    series = 10.0 + 0.2 * t + 2.0 * np.sin((2.0 * np.pi * t) / 12.0)

    result = method.pure_step(
        {"series": series},
        {
            "horizon": 6,
            "period": 12,
            "neural_family": "nbeats",
            "minimum_point_improvement": -1.0,
            "coverage_gap_tolerance": 1.0,
        },
    )

    bundle = result["forecasting_uncertainty_bundle"]
    selection = bundle.metadata["method_selection"]
    assert result["result"]["source_method"] == "forecasting.hybrid.guarded_ensemble@1.0.0"
    assert bundle.source_method == "forecasting.hybrid.guarded_ensemble@1.0.0"
    assert selection["trust_region_state"] == "green"
    assert selection["shadow_only"] is False
    assert selection["selection_reason"] == "guarded_ensemble_serving"
    assert selection["guarded_weights_by_horizon"]["1"] > 0.0
    assert "final_uq" in selection["validation_metrics"]
    assert bundle.interval_semantics.value == "conformalized_prediction_interval"
