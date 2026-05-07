"""Full DDM acceptance-surface tests."""

from __future__ import annotations

from datetime import UTC, datetime

from polisyos.ddm.calibration import CalibrationReport, build_calibration_audit
from polisyos.ddm.integration import (
    AffectedFeature,
    AffectedSlice,
    DriftAndDegradationMonitor,
    MetricDirection,
    MonitoringWindow,
    PerformanceDegradationEvent,
    ReadinessState,
    ShiftDetectedEvent,
    evaluate_registry_gate,
)
from polisyos.ddm.readiness import MetricBudgetPolicy


def _window() -> MonitoringWindow:
    return MonitoringWindow(
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 2, tzinfo=UTC),
        n=100,
    )


def test_monitor_emits_all_runtime_outputs_and_registry_gate_blocks_r1() -> None:
    calibration_report = CalibrationReport.model_validate(
        {
            "detector_id": "input_mmd_global_v3",
            "stationarity_regime_id": "SR-1-model-v1",
            "fp_target": {"horizon": "30d", "alpha": 0.05, "ert": 10000},
            "threshold": 0.2,
            "time_varying_thresholds": [0.2, 0.21],
            "observed_average_run_length": 10000,
            "empirical_stationary_holdout": {
                "alerts": 0,
                "windows": 100,
                "empirical_fp_rate": 0.0,
                "confidence_interval_95": [0.0, 0.03],
                "pass": True,
            },
            "detection_delay_tests": {
                "synthetic_covariate_shift": {
                    "min_detectable_shift": 0.25,
                    "median_delay_windows": 2,
                },
                "synthetic_concept_shift": {
                    "min_detectable_shift": 0.50,
                    "median_delay_windows": 1,
                },
            },
            "expiration": {
                "valid_until": "2026-05-01T00:00:00Z",
                "invalidation_triggers": ["model_version_change"],
            },
            "calibration_method": "moving_block_bootstrap_quantile",
            "random_seed": 0,
            "block_length": 2,
        }
    )
    shift = ShiftDetectedEvent(
        event_id="shift-1",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        model_id="model",
        model_version="v1",
        detector_id="input_mmd_global_v3",
        detector_family="online_mmd",
        signal="input_shift",
        representation="feature_embedding_v2",
        reference_window=_window(),
        current_window=_window(),
        stationarity_regime_id="SR-1-model-v1",
        calibration_id="calib-1",
        test_statistic=0.3,
        ert=10000,
        empirical_fp_rate=0.001,
        shift_severity=0.72,
        affected_features=[
            AffectedFeature(feature="age_band", score=0.31, direction="category_mix_changed")
        ],
        affected_slices=[AffectedSlice(slice="region=west", score=0.44)],
    )
    degradation = PerformanceDegradationEvent(
        event_id="degrade-1",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        model_id="model",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        source="estimated_performance",
        estimator="cbpe",
        reference_value=0.90,
        minimum_acceptable_value=0.80,
        current_estimate=0.84,
        confidence_interval_95=(0.82, 0.86),
        budget_used=0.80,
        calibration_id="calib-1",
    )
    metric_budget = MetricBudgetPolicy(
        model_id="model",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.90,
        minimum_acceptable_value=0.80,
    )

    result = DriftAndDegradationMonitor().evaluate_window(
        model_id="model",
        model_version="v1",
        shift_events=[shift],
        degradation_event=degradation,
        metric_budget=metric_budget,
        calibration_audit=build_calibration_audit(
            calibration_id="calib-1",
            report=calibration_report,
        ),
        upstream_versions={"feature_store": "2026-04-26"},
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert result.shift_risk_events[0].risk_level == "investigate"
    assert result.degradation_event is not None
    assert result.degradation_event.readiness_state == ReadinessState.R1
    assert result.readiness_event.readiness_state == ReadinessState.R1
    assert result.root_cause_bundle.affected_slices == ["region=west"]
    assert result.root_cause_bundle.upstream_versions == {"feature_store": "2026-04-26"}
    assert result.incident_payload.freeze_rollout is True
    assert result.incident_payload.trigger_shadow_retrain is True
    assert result.registry_record is not None
    assert result.registry_record.promotion_allowed is False

    gate = evaluate_registry_gate(result.registry_record)

    assert gate.promotion_allowed is False
    assert gate.reason == "R1_blocks_promotion"
