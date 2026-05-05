from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.ml.protocols import PredictionResultConsumerInput
from polisyos.ir.analytics.shift_diagnostics import (
    CalibrationInfo,
    DetectorResult,
    OperatingCharacteristicKey,
    OperatingCharacteristicLibrary,
    OperatingCharacteristicRecord,
    ReadinessImpact,
    ShiftComponent,
    ShiftDiagnosticReport,
    build_readiness_impact,
    load_shift_diagnostic_report,
    persist_shift_diagnostic_report,
    readiness_downgrade,
)
from pydantic import ValidationError


def _component(
    *,
    status: str = "not_detected",
    bucket: str = "none",
    score: float | None = 0.0,
) -> ShiftComponent:
    return ShiftComponent(
        status=status,
        severity_bucket=bucket,
        severity_score=score,
        power=0.82 if bucket == "none" else 0.9,
    )


def _calibration() -> CalibrationInfo:
    return CalibrationInfo(
        operating_characteristic_library_version="ocl-test-v1",
        calibration_id="cal-test",
        reference_comparison_type="training_vs_current",
        target_report_fpr=0.05,
        null_regime="stable_adjacent_months",
        min_detectable_effect_summary={"global_x": "medium"},
        power_summary={"global_x_medium": 0.84},
    )


def _detector() -> DetectorResult:
    key = OperatingCharacteristicKey(
        modality="tabular_administrative",
        task_type="classification",
        n_reference_bucket="n_ref_1k_10k",
        n_current_bucket="n_cur_1k_10k",
        feature_count_bucket="p_10_100",
        categorical_cardinality_bucket="cat_medium",
        sparsity_missingness_bucket="missing_low",
        label_lag_bucket="no_labels",
        detector_family="univariate",
        reference_comparison_type="training_vs_current",
        windowing_strategy="calendar_month",
        calibration_version="test",
    )
    return DetectorResult(
        detector_name="feature_wise_ks",
        detector_family="univariate",
        data_view="raw_features",
        statistic=0.04,
        p_value=0.31,
        q_value=0.42,
        operating_characteristic_key=key.to_cache_key(),
    )


def test_operating_characteristic_library_is_queryable() -> None:
    key = OperatingCharacteristicKey(
        modality="tabular_administrative",
        task_type="classification",
        n_reference_bucket="n_ref_1k_10k",
        n_current_bucket="n_cur_1k_10k",
        feature_count_bucket="p_10_100",
        categorical_cardinality_bucket="cat_medium",
        sparsity_missingness_bucket="missing_low",
        label_lag_bucket="no_labels",
        detector_family="classifier_two_sample",
        reference_comparison_type="training_vs_current",
        windowing_strategy="calendar_month",
        calibration_version="test",
    )
    record = OperatingCharacteristicRecord(
        key=key,
        false_positive_rate_by_no_shift_regime={"stable_adjacent_months": 0.04},
        power_curve_by_shift_type_and_severity={"marginal": {"medium": 0.82}},
        minimum_detectable_effect={"standardized_mean_difference": 0.20},
        recommended_thresholds={"report_score": 0.55},
    )

    library = OperatingCharacteristicLibrary(version="ocl-test-v1", records=(record,))

    assert library.lookup(key) == record
    assert library.lookup(key.to_cache_key()) == record
    assert library.by_detector_family("classifier_two_sample") == (record,)


def _report(
    *,
    concept_status: str = "unassessable_until_labels",
    concept_bucket: str = "unassessable",
    label_availability: str = "none",
    global_verdict: str = "no_shift_detected",
    power_status: str = "sufficient",
    readiness_impact: ReadinessImpact | None = None,
    schema_shift: ShiftComponent | None = None,
    marginal_shift: ShiftComponent | None = None,
    support_shift: ShiftComponent | None = None,
    label_prior_shift: ShiftComponent | None = None,
    harmful_shift_risk: ShiftComponent | None = None,
) -> ShiftDiagnosticReport:
    if readiness_impact is None:
        readiness_impact = build_readiness_impact(
            base_readiness="ready",
            downgrade_level=0,
            downgrade_reasons=(),
            required_actions=(),
        )
    return ShiftDiagnosticReport(
        report_id="shift-report-1",
        generated_at="2026-04-26T00:00:00Z",
        prediction_result_id="prediction-1",
        model_id="benefits-risk-model",
        model_version="2026.04",
        task_type="classification",
        modality="tabular_administrative",
        training_reference_id="train-2025",
        validation_reference_id="valid-2025",
        current_window_id="deploy-2026-04",
        current_window_start="2026-04-01",
        current_window_end="2026-04-30",
        n_reference=1200,
        n_current=900,
        effective_n_reference=1190.0,
        effective_n_current=880.0,
        label_availability=label_availability,
        label_lag_days=None,
        power_status=power_status,
        calibration=_calibration(),
        schema_shift=schema_shift or _component(),
        marginal_shift=marginal_shift or _component(),
        support_shift=support_shift or _component(),
        label_prior_shift=label_prior_shift or _component(),
        concept_shift=_component(status=concept_status, bucket=concept_bucket, score=None),
        prediction_output_shift=_component(),
        harmful_shift_risk=harmful_shift_risk or _component(),
        global_verdict=global_verdict,
        detector_results=(_detector(),),
        readiness_impact=readiness_impact,
        human_summary="No material covariate shift detected; concept shift awaits labels.",
        machine_summary={"top_level": global_verdict},
        limitations=("concept_shift_unassessable_without_labels",),
        recommended_next_checks=("attach_delayed_outcomes_when_available",),
    )


def test_shift_report_round_trips_through_artifact_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report = _report()

    ref = persist_shift_diagnostic_report(store, report)
    restored = load_shift_diagnostic_report(store, ref)

    assert ref.kind == "ir.shift_diagnostic_report"
    assert restored.report_id == report.report_id
    assert restored.concept_shift.status == "unassessable_until_labels"
    assert readiness_downgrade(restored) == 0


def test_no_shift_detected_requires_power_statement() -> None:
    with pytest.raises(ValidationError, match="power_status='sufficient'"):
        _report(power_status="unknown")


def test_label_free_report_cannot_confirm_concept_shift() -> None:
    with pytest.raises(ValidationError, match="confirmed concept shift requires"):
        _report(
            concept_status="confirmed",
            concept_bucket="high",
            label_availability="none",
            global_verdict="concept_shift",
            readiness_impact=build_readiness_impact(
                base_readiness="ready",
                downgrade_level=3,
                downgrade_reasons=("concept_shift_confirmed",),
                required_actions=("block_automated_recommendation",),
            ),
        )


def test_high_support_shift_downgrades_to_restricted() -> None:
    report = _report(
        global_verdict="support_shift",
        power_status="unknown",
        support_shift=_component(status="detected", bucket="high", score=0.77),
        readiness_impact=build_readiness_impact(
            base_readiness="ready",
            downgrade_level=2,
            downgrade_reasons=("support_shift_high",),
            required_actions=("require_recent_validation",),
        ),
    )

    assert readiness_downgrade(report) == 2
    assert report.readiness_impact.resulting_readiness == "restricted"


def test_prediction_consumer_enforces_attached_shift_report() -> None:
    blocked = _report(
        concept_status="confirmed",
        concept_bucket="high",
        label_availability="delayed",
        global_verdict="concept_shift",
        power_status="unknown",
        readiness_impact=build_readiness_impact(
            base_readiness="ready",
            downgrade_level=3,
            downgrade_reasons=("concept_shift_confirmed",),
            required_actions=("block_automated_recommendation",),
        ),
    )

    consumer_input = PredictionResultConsumerInput(
        prediction_result_id="prediction-1",
        prediction_result_payload={"predictions": [0.1, 0.9]},
        shift_diagnostic_report=blocked,
    )

    assert consumer_input.resulting_readiness() == "blocked"
    assert consumer_input.refuses_automated_action() is True
    assert consumer_input.audit_shift_report_id() == "shift-report-1"


def test_prediction_consumer_without_report_caps_high_stakes_readiness() -> None:
    consumer_input = PredictionResultConsumerInput(
        prediction_result_id="prediction-1",
        prediction_result_payload={"predictions": [0.2]},
        high_stakes=True,
    )

    assert consumer_input.resulting_readiness() == "monitor"
    assert consumer_input.refuses_automated_action() is False
