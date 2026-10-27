"""Source-owned observation/basis controls for current registry admission."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from polisyos.ddm.calibration import CalibrationReport, build_calibration_audit
from polisyos.ddm.calibration.audit import _canonical_report_digest
from polisyos.ddm.calibration.observations import (
    CalibrationObservationWindow,
    FiniteCalibrationObservationSource,
)
from polisyos.ddm.detectors.track_2_2_shift_adapter import adapt_shift_event
from polisyos.ddm.integration import (
    DriftAndDegradationMonitor,
    MetricDirection,
    ModelRegistryReadinessRecord,
    MonitoringWindow,
    ShiftDetectedEvent,
    evaluate_registry_gate,
)
from polisyos.ddm.integration.model_registry import rebind_calibration_validity
from polisyos.ddm.readiness import MetricBudgetPolicy

if TYPE_CHECKING:
    from pathlib import Path

NOW = datetime(2026, 4, 26, tzinfo=UTC)


def _report() -> CalibrationReport:
    return CalibrationReport.model_validate(
        {
            "model_id": "model",
            "model_version": "v1",
            "detector_id": "detector",
            "stationarity_regime_id": "regime",
            "fp_target": {"horizon": "30d", "alpha": 0.05},
            "threshold": 0.2,
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
                "synthetic_concept_shift": {"min_detectable_shift": 0.5, "median_delay_windows": 1},
            },
            "expiration": {
                "valid_until": "2026-05-01T00:00:00Z",
                "invalidation_triggers": ["model_version_change"],
            },
        }
    )


def _budget() -> MetricBudgetPolicy:
    return MetricBudgetPolicy(
        model_id="model",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.9,
        minimum_acceptable_value=0.8,
    )


def _shift() -> ShiftDetectedEvent:
    window = MonitoringWindow(start=NOW, end=NOW, n=100)
    return ShiftDetectedEvent(
        event_id="shift-1",
        timestamp=NOW,
        model_id="model",
        model_version="v1",
        detector_id="detector",
        detector_family="online_mmd",
        signal="input_shift",
        representation="features",
        reference_window=window,
        current_window=window,
        stationarity_regime_id="regime",
        calibration_id="calib",
        test_statistic=0.1,
        ert=10000,
        empirical_fp_rate=0.001,
        shift_severity=0.1,
    )


def _source(path: Path, *, shifts: bool = False) -> FiniteCalibrationObservationSource:
    report = _report()
    window = CalibrationObservationWindow(
        schema_version="polisyos.ddm.finite_observation_window.v1",
        source_id="fixture-owned-log",
        profile="finite_replay",
        model_id="model",
        model_version="v1",
        calibration_id="calib",
        detector_id="detector",
        stationarity_regime_id="regime",
        report_digest=_canonical_report_digest(report),
        observed_from=NOW,
        observed_through=NOW,
        invalidation_events=(),
        shift_events=(adapt_shift_event(_shift()),) if shifts else (),
        degradation_event=None,
        metric_budget=_budget(),
        data_quality_signals=(),
        critical_slice_budget_used=None,
    )
    path.write_text(window.model_dump_json())
    return FiniteCalibrationObservationSource(path=path, source_id="fixture-owned-log")


def _produce(source: FiniteCalibrationObservationSource | None, *, shifts: bool = False):
    report = _report()
    audit = build_calibration_audit(calibration_id="calib", report=report)
    result = DriftAndDegradationMonitor(observation_source=source).evaluate_window(
        model_id="model",
        model_version="v1",
        metric_budget=_budget(),
        calibration_audit=audit,
        _calibration_report=report,
        _observed_invalidation_triggers=[],
        timestamp=NOW,
        shift_events=[_shift()] if shifts else [],
    )
    assert result.registry_record is not None
    return report, audit, result.registry_record


def test_enumerated_empty_replay_is_valid_but_cannot_grant_production(tmp_path: Path) -> None:
    _, _, record = _produce(_source(tmp_path / "observations.json"))
    assert record.calibration_validity is not None
    assert record.calibration_validity.status == "valid"
    assert record.calibration_validity.observed_invalidation_triggers == []
    assert record.applicability_binding is not None
    assert record.applicability_binding.observation_binding.completeness_provenance == "recomputed"
    decision = evaluate_registry_gate(record)
    assert not decision.promotion_allowed
    assert decision.reason == "finite_replay_observation_not_production_authority"


def test_raw_empty_list_does_not_establish_observed_emptiness() -> None:
    _, _, record = _produce(None)
    assert record.calibration_validity.observation_status == "unavailable"
    assert evaluate_registry_gate(record).reason == "calibration_validity_not_established"


def test_omitted_trigger_is_read_from_source_and_stale_evidence_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "observations.json"
    source = _source(path)
    report, audit, record = _produce(source)
    payload = json.loads(path.read_text())
    payload["invalidation_events"].append(
        {
            "event_id": "real-trigger",
            "timestamp": NOW.isoformat(),
            "trigger": "model_version_change",
        }
    )
    path.write_text(json.dumps(payload))
    assert (
        evaluate_registry_gate(record).reason
        == "calibration_observation_source_changed_or_unavailable"
    )
    fresh = ModelRegistryReadinessRecord.model_validate_json(record.model_dump_json())
    rebound = rebind_calibration_validity(
        fresh,
        report=report,
        calibration_audit=audit,
        now=NOW,
        observed_invalidation_triggers=[],
        observation_source=source,
    )
    assert rebound.calibration_validity.status == "invalidated"
    assert rebound.calibration_validity.observed_invalidation_triggers == ["model_version_change"]
    assert evaluate_registry_gate(rebound).reason == "calibration_model_version_change"


def test_resigning_empty_projection_cannot_drop_source_shift_denominator(tmp_path: Path) -> None:
    source = _source(tmp_path / "observations.json", shifts=True)
    report, audit, record = _produce(source, shifts=True)
    payload = json.loads(record.model_dump_json())
    payload["applicability_binding"]["shift_event_digests"] = []
    fresh = ModelRegistryReadinessRecord.model_validate(payload)
    rebound = rebind_calibration_validity(
        fresh,
        report=report,
        calibration_audit=audit,
        now=NOW,
        observed_invalidation_triggers=[],
        observation_source=source,
        metric_budget=_budget(),
        shift_events=[],
    )
    assert rebound._applicability_evidence is not None
    assert "registry_applicability_projection_mismatch" in rebound._applicability_evidence.reasons
    assert "caller_shift_basis_mismatch" in rebound._applicability_evidence.reasons
    assert not evaluate_registry_gate(rebound).promotion_allowed


def test_frozen_binding_and_last_event_consistency_are_independent_controls(tmp_path: Path) -> None:
    source = _source(tmp_path / "observations.json", shifts=True)
    _, _, record = _produce(source, shifts=True)
    with pytest.raises(ValueError, match="frozen"):
        record.applicability_binding.shift_event_digests = ()
    changed = record.model_copy(update={"last_shift_event": None})
    assert evaluate_registry_gate(changed).reason == "registry_last_shift_projection_mismatch"


@pytest.mark.parametrize("field", ["source_id", "report_digest", "observed_through"])
def test_wrong_selected_source_context_cannot_issue_validity(tmp_path: Path, field: str) -> None:
    path = tmp_path / "observations.json"
    source = _source(path)
    payload = json.loads(path.read_text())
    payload[field] = {
        "source_id": "another-source",
        "report_digest": "0" * 64,
        "observed_through": "2026-04-25T00:00:00Z",
    }[field]
    path.write_text(json.dumps(payload))
    _, _, record = _produce(source)
    assert record.calibration_validity.status == "not_established"
    assert not evaluate_registry_gate(record).promotion_allowed


def test_source_quality_signal_cannot_be_omitted_from_consumed_window(tmp_path: Path) -> None:
    path = tmp_path / "observations.json"
    source = _source(path)
    payload = json.loads(path.read_text())
    payload["data_quality_signals"].append(
        {
            "signal_id": "actual-owner-dq",
            "timestamp": NOW.isoformat(),
            "model_id": "model",
            "model_version": "v1",
            "risk_score": 1.0,
            "hard_failure": True,
        }
    )
    path.write_text(json.dumps(payload))
    _, _, record = _produce(source)
    assert evaluate_registry_gate(record).reason == "window_source_data_quality_basis_mismatch"


def test_wrong_budget_consumption_is_recomputed_despite_matching_source_labels(
    tmp_path: Path,
) -> None:
    from polisyos.ddm.integration import PerformanceDegradationEvent

    path = tmp_path / "observations.json"
    source = _source(path)
    payload = json.loads(path.read_text())
    degradation = PerformanceDegradationEvent(
        event_id="degradation",
        timestamp=NOW,
        model_id="model",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        source="estimated_performance",
        estimator="cbpe",
        reference_value=0.9,
        minimum_acceptable_value=0.8,
        current_estimate=0.84,
        confidence_interval_95=(0.82, 0.86),
        budget_used=0.0,
        calibration_id="calib",
    )
    payload["degradation_event"] = degradation.model_dump(mode="json")
    path.write_text(json.dumps(payload))
    report = _report()
    audit = build_calibration_audit(calibration_id="calib", report=report)
    result = DriftAndDegradationMonitor(observation_source=source).evaluate_window(
        model_id="model",
        model_version="v1",
        metric_budget=_budget(),
        calibration_audit=audit,
        _calibration_report=report,
        _observed_invalidation_triggers=[],
        timestamp=NOW,
        degradation_event=degradation,
    )
    assert result.registry_record is not None
    assert (
        evaluate_registry_gate(result.registry_record).reason
        == "degradation_budget_consumption_mismatch"
    )


def test_direct_builder_last_event_cannot_escape_consumed_basis(tmp_path: Path) -> None:
    from polisyos.ddm.integration.model_registry import build_model_registry_record
    from polisyos.ddm.readiness.readiness_mapper import map_readiness

    source = _source(tmp_path / "observations.json", shifts=True)
    _, audit, original = _produce(source, shifts=True)
    last = adapt_shift_event(_shift())
    record = build_model_registry_record(
        readiness_event=map_readiness(model_id="model", model_version="v1", timestamp=NOW),
        calibration_audit=audit,
        metric_budget=_budget(),
        shift_events=[],
        last_shift_event=last,
        _calibration_validity_evidence=original._calibration_validity_evidence,
    )
    assert "last_shift_event_not_in_consumed_basis" in record._applicability_evidence.reasons
    assert "window_source_shift_basis_mismatch" in record._applicability_evidence.reasons
    assert not evaluate_registry_gate(record).promotion_allowed


def test_registry_schema_accepts_bound_projection_and_rejects_corruption(tmp_path: Path) -> None:
    from pathlib import Path

    from jsonschema import Draft202012Validator, ValidationError

    _, _, record = _produce(_source(tmp_path / "observations.json", shifts=True), shifts=True)
    schema_path = (
        Path(__file__).resolve().parents[3]
        / "src/polisyos/ddm/integration/model_registry_record.schema.json"
    )
    validator = Draft202012Validator(json.loads(schema_path.read_text()))
    payload = json.loads(record.model_dump_json())
    validator.validate(payload)
    payload["applicability_binding"]["unowned_authority"] = True
    with pytest.raises(ValidationError):
        validator.validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("readiness_state", "R4"),
        ("readiness_score", 100),
        ("primary_reason", "within_metric_budget_and_no_active_shift"),
        ("active_signals", []),
        ("required_actions", []),
        ("event_id", "another-readiness"),
        ("timestamp", "2026-04-25T00:00:00Z"),
        ("expires_at", "2026-05-20T00:00:00Z"),
    ],
)
def test_direct_builder_reconciles_complete_readiness_projection(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    from polisyos.ddm.integration import DataQualitySignal, ReadinessStateEvent
    from polisyos.ddm.integration.model_registry import build_model_registry_record
    from polisyos.ddm.readiness.readiness_mapper import map_readiness

    path = tmp_path / "observations.json"
    source = _source(path)
    quality = DataQualitySignal(
        signal_id="real-hard-dq",
        model_id="model",
        model_version="v1",
        timestamp=NOW,
        risk_score=1.0,
        hard_failure=True,
    )
    payload = json.loads(path.read_text())
    payload["data_quality_signals"] = [quality.model_dump(mode="json")]
    path.write_text(json.dumps(payload))
    _, audit, original = _produce(source)
    source_readiness = map_readiness(
        model_id="model", model_version="v1", data_quality_signals=[quality], timestamp=NOW
    )
    corrupted = source_readiness.model_dump(mode="json")
    corrupted[field] = value
    record = build_model_registry_record(
        readiness_event=ReadinessStateEvent.model_validate(corrupted),
        calibration_audit=audit,
        metric_budget=_budget(),
        shift_events=[],
        data_quality_signals=[quality],
        _calibration_validity_evidence=original._calibration_validity_evidence,
    )
    assert "window_source_readiness_projection_mismatch" in record._applicability_evidence.reasons
    assert not evaluate_registry_gate(record).promotion_allowed


def test_closed_snapshot_cannot_be_replayed_before_its_observation_checkpoint(
    tmp_path: Path,
) -> None:
    path = tmp_path / "observations.json"
    source = _source(path)
    payload = json.loads(path.read_text())
    payload["observed_from"] = "2026-04-25T00:00:00Z"
    payload["observed_through"] = "2026-04-27T00:00:00Z"
    path.write_text(json.dumps(payload))
    _, _, record = _produce(source)
    assert record.calibration_validity.status == "not_established"
    assert not evaluate_registry_gate(record).promotion_allowed


def test_future_fact_is_not_admitted_at_earlier_snapshot_checkpoint(tmp_path: Path) -> None:
    path = tmp_path / "observations.json"
    source = _source(path, shifts=True)
    payload = json.loads(path.read_text())
    payload["shift_events"][0]["timestamp"] = "2026-04-27T00:00:00Z"
    path.write_text(json.dumps(payload))
    _, _, record = _produce(source, shifts=True)
    assert record.calibration_validity.status == "not_established"
    assert not evaluate_registry_gate(record).promotion_allowed
