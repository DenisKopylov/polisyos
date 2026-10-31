"""Calibration producer and model-registry persistence composition tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from polisyos.ddm.calibration import (
    CalibrationReport,
    FpTarget,
    Period,
    StationarityRegime,
    build_calibration_audit,
    calibrate_detector,
)
from polisyos.ddm.calibration.audit import _canonical_report_digest
from polisyos.ddm.calibration.observations import (
    CalibrationObservationWindow,
    FiniteCalibrationObservationSource,
)
from polisyos.ddm.integration import (
    CalibrationAudit,
    DriftAndDegradationMonitor,
    MetricDirection,
    ModelRegistryReadinessRecord,
    evaluate_registry_gate,
)
from polisyos.ddm.integration.model_registry import rebind_calibration_validity
from polisyos.ddm.readiness import MetricBudgetPolicy

_MODEL_ID = "calibration-round-trip-model"
_MODEL_VERSION = "v1"
_DETECTOR_ID = "input_mmd_global_v3"
_CALIBRATION_ID = "calib-round-trip-1"
_SOURCE_ID = "finite-calibration-round-trip"
_NOW = datetime(2026, 4, 10, tzinfo=UTC)


def _regime() -> StationarityRegime:
    return StationarityRegime(
        id="SR-calibration-round-trip-v1",
        model_id=_MODEL_ID,
        model_version=_MODEL_VERSION,
        reference_period=Period(
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 2, 1, tzinfo=UTC),
        ),
        calibration_period=Period(
            start=datetime(2026, 2, 1, tzinfo=UTC),
            end=datetime(2026, 3, 1, tzinfo=UTC),
        ),
        holdout_stationary_period=Period(
            start=datetime(2026, 3, 1, tzinfo=UTC),
            end=datetime(2026, 4, 1, tzinfo=UTC),
        ),
        block_length=2,
        invalidation_triggers=["model_version_change"],
    )


def _registry_case(
    tmp_path: Path,
) -> tuple[
    CalibrationReport,
    CalibrationAudit,
    FiniteCalibrationObservationSource,
    ModelRegistryReadinessRecord,
]:
    calibration_streams = [[0.10, 0.12, 0.11, 0.13] for _ in range(100)]
    holdout_streams = [[0.05, 0.07, 0.08, 0.09] for _ in range(100)]
    produced_report = calibrate_detector(
        detector_id=_DETECTOR_ID,
        stationarity_regime=_regime(),
        fp_target=FpTarget(horizon="30d", alpha=0.05, ert=10000),
        calibration_streams=calibration_streams,
        holdout_streams=holdout_streams,
        seed=7,
    )

    report_path = tmp_path / "calibration-report.json"
    report_path.write_text(produced_report.model_dump_json(), encoding="utf-8")
    report = CalibrationReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    assert report == produced_report
    assert report.expiration.valid_until > _NOW
    audit = build_calibration_audit(calibration_id=_CALIBRATION_ID, report=report)
    metric_budget = MetricBudgetPolicy(
        model_id=_MODEL_ID,
        model_version=_MODEL_VERSION,
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.90,
        minimum_acceptable_value=0.80,
    )

    observation_window = CalibrationObservationWindow(
        schema_version="polisyos.ddm.finite_observation_window.v1",
        source_id=_SOURCE_ID,
        profile="finite_replay",
        model_id=_MODEL_ID,
        model_version=_MODEL_VERSION,
        calibration_id=_CALIBRATION_ID,
        detector_id=_DETECTOR_ID,
        stationarity_regime_id=report.stationarity_regime_id,
        report_digest=_canonical_report_digest(report),
        observed_from=_NOW,
        observed_through=_NOW,
        invalidation_events=(),
        shift_events=(),
        degradation_event=None,
        metric_budget=metric_budget,
        data_quality_signals=(),
        critical_slice_budget_used=None,
    )
    observation_path = tmp_path / "calibration-observations.json"
    observation_path.write_text(observation_window.model_dump_json(), encoding="utf-8")
    observation_source = FiniteCalibrationObservationSource(
        path=observation_path,
        source_id=_SOURCE_ID,
    )

    result = DriftAndDegradationMonitor(
        observation_source=observation_source,
    ).evaluate_window(
        model_id=_MODEL_ID,
        model_version=_MODEL_VERSION,
        metric_budget=metric_budget,
        calibration_audit=audit,
        _calibration_report=report,
        _observed_invalidation_triggers=[],
        timestamp=_NOW,
    )
    assert result.registry_record is not None

    registry_path = tmp_path / "model-registry-record.json"
    registry_path.write_text(result.registry_record.model_dump_json(), encoding="utf-8")
    reloaded_record = ModelRegistryReadinessRecord.model_validate_json(
        registry_path.read_text(encoding="utf-8")
    )
    assert reloaded_record.model_dump(mode="json") == result.registry_record.model_dump(
        mode="json"
    )
    return report, audit, observation_source, reloaded_record


def test_produced_report_and_registry_round_trip_rebind_exact_context(
    tmp_path: Path,
) -> None:
    report, audit, observation_source, record = _registry_case(tmp_path)

    rebound = rebind_calibration_validity(
        record,
        report=report,
        calibration_audit=audit,
        now=_NOW,
        observed_invalidation_triggers=[],
        observation_source=observation_source,
    )

    assert rebound.calibration_validity is not None
    assert rebound.calibration_validity.status == "valid"
    assert rebound.calibration_validity.effective_at == _NOW
    assert rebound.calibration_validity.observation_status == "observed"
    assert rebound.calibration_validity.observed_invalidation_triggers == []
    assert rebound.calibration_validity.report_digest == _canonical_report_digest(report)
    decision = evaluate_registry_gate(rebound)
    assert decision.promotion_allowed is False
    assert decision.reason == "finite_replay_observation_not_production_authority"


def test_registry_rebind_rejects_changed_report_bound_threshold(tmp_path: Path) -> None:
    report, audit, observation_source, record = _registry_case(tmp_path)
    changed_report = report.model_copy(update={"threshold": report.threshold + 0.01})

    rebound = rebind_calibration_validity(
        record,
        report=changed_report,
        calibration_audit=audit,
        now=_NOW,
        observed_invalidation_triggers=[],
        observation_source=observation_source,
    )

    decision = evaluate_registry_gate(rebound)
    assert decision.promotion_allowed is False
    assert decision.reason == "calibration_report_binding_not_established"
