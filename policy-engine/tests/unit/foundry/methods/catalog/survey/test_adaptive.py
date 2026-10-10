from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.survey.adaptive_benchmark import (
    AdaptiveBenchmarkConfig,
    AdaptiveBenchmarkScenarioKind,
    run_adaptive_benchmark_suite,
)


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _adaptive_state() -> dict[str, np.ndarray]:
    return {
        "y_observed": np.array([10.0, 12.0, np.nan, 20.0, 18.0, np.nan]),
        "response_indicator": np.array([1.0, 1.0, 0.0, 1.0, 1.0, 0.0]),
        "base_inclusion_probabilities": np.full(6, 0.5),
        "followup_sampling_probabilities": np.array([1.0, 1.0, 0.5, 1.0, 0.5, 1.0]),
        "X_aux": np.array(
            [
                [1.0, 0.0],
                [1.0, 0.0],
                [1.0, 1.0],
                [1.0, 1.0],
                [1.0, 0.0],
                [1.0, 1.0],
            ]
        ),
        "paradata_matrix": np.array(
            [
                [2.0, 0.20],
                [1.0, 0.10],
                [3.0, 0.40],
                [2.0, 0.30],
                [1.0, 0.20],
                [4.0, 0.50],
            ]
        ),
        "action_matrix": np.array([[0.0], [0.0], [1.0], [0.0], [1.0], [1.0]]),
        "control_totals": np.array([12.0, 6.0]),
        "cost_vector": np.array([1.0, 1.0, 1.5, 1.0, 1.2, 1.5]),
    }


class TestAdaptiveCalibratedIPW:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.adaptive.adaptive_calibrated_ipw@1.0.0")
        result = method.pure_step(
            _adaptive_state(),
            {
                "calibration_method": "linear",
                "decision_rule_id": "rule-v1",
                "adaptation_log_id": "log-v1",
                "control_totals_version": "controls-2026-04-21",
            },
        )

        payload = result["result"]
        assert payload["estimand_type"] == "mean"
        assert np.isfinite(payload["point_estimate"])
        assert payload["final_weights_summary"]["n_respondents"] == 4
        assert payload["audit_refs"]["decision_rule_id"] == "rule-v1"
        assert payload["adaptive_status"]["n_followup"] == 2
        assert payload["diagnostics"]["r_indicator"] >= 0.0
        assert "loss_value" in payload["stop_status"]

    def test_linear_calibration_tracks_control_totals(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.adaptive.adaptive_calibrated_ipw@1.0.0")
        result = method.pure_step(_adaptive_state(), {"calibration_method": "linear"})

        calibration = result["result"]["calibration_status"]
        achieved = np.asarray(calibration["achieved_totals"], dtype=float)
        target = np.asarray(calibration["target_totals"], dtype=float)
        assert np.allclose(achieved, target, atol=1e-5)

    def test_followup_probabilities_inflate_phase_weights(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.adaptive.adaptive_calibrated_ipw@1.0.0")
        result = method.pure_step(_adaptive_state(), {})

        phase_weights = np.asarray(result["result"]["phase_weights"], dtype=float)
        assert phase_weights[4] > phase_weights[0]

    def test_generated_bootstrap_variance_path(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.adaptive.adaptive_calibrated_ipw@1.0.0")
        result = method.pure_step(
            _adaptive_state(),
            {
                "variance_method": "bootstrap",
                "n_replicates": 8,
                "seed": 7,
            },
        )

        payload = result["result"]
        assert payload["variance_method_used"] == "bootstrap"
        assert payload["variance_estimate"] >= 0.0
        assert payload["diagnostics"]["variance_diagnostics"]["n_replicates_used"] == 8

    def test_augmented_estimator_emits_augmentation_status(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.adaptive.adaptive_augmented@1.0.0")
        result = method.pure_step(
            _adaptive_state(),
            {
                "variance_method": "bootstrap",
                "n_replicates": 8,
                "seed": 11,
            },
        )

        payload = result["result"]
        assert np.isfinite(payload["point_estimate"])
        assert payload["augmentation_status"]["outcome_model"] == "linear"
        assert "weighted_r2" in payload["augmentation_status"]


def test_adaptive_benchmark_suite_smoke() -> None:
    suite = run_adaptive_benchmark_suite(
        AdaptiveBenchmarkConfig(
            population_size=1000,
            sample_size=160,
            n_repetitions=4,
            n_bootstrap_replicates=8,
            estimator_names=("adaptive_calibrated_ipw", "adaptive_augmented"),
            scenario_kinds=(
                AdaptiveBenchmarkScenarioKind.FAVORABLE_MAR,
                AdaptiveBenchmarkScenarioKind.WEAK_X,
                AdaptiveBenchmarkScenarioKind.MEASUREMENT_TRADEOFF,
                AdaptiveBenchmarkScenarioKind.INFORMATIVE_CLUSTERED,
            ),
            seed=13,
        )
    )

    assert len(suite.case_results) == 8
    scenario_kinds = {case.scenario_kind for case in suite.case_results}
    assert scenario_kinds == {
        AdaptiveBenchmarkScenarioKind.FAVORABLE_MAR,
        AdaptiveBenchmarkScenarioKind.WEAK_X,
        AdaptiveBenchmarkScenarioKind.MEASUREMENT_TRADEOFF,
        AdaptiveBenchmarkScenarioKind.INFORMATIVE_CLUSTERED,
    }
    assert 0.0 <= suite.aggregate_metrics["mean_coverage_95"] <= 1.0
    assert suite.aggregate_metrics["mean_effective_sample_size"] > 0.0
