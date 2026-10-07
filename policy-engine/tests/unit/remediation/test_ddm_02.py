"""DDM report/source binding and persisted temporal-consumer regressions."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from polisyos.ddm.calibration.audit import build_calibration_audit
from polisyos.ddm.calibration.calibrate import (
    FpTarget,
    Period,
    StationarityRegime,
    calibrate_detector,
)
from polisyos.ddm.contracts.events import (
    MetricDirection,
    MonitoringWindow,
    PerformanceDegradationEvent,
    ShiftDetectedEvent,
)
from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy
from polisyos.ddm.integration.model_registry import (
    ModelRegistryReadinessRecord,
    evaluate_registry_gate,
    rebind_calibration_validity,
)
from polisyos.ddm.integration.monitor import DriftAndDegradationMonitor
from polisyos.ddm.readiness.readiness_mapper import metric_budget_used

NOW = datetime(2026, 4, 26, tzinfo=UTC)


def _context():
    regime = StationarityRegime(
        id="regime-1",
        model_id="model-1",
        model_version="v1",
        reference_period=Period(start=NOW - timedelta(days=30), end=NOW - timedelta(days=20)),
        calibration_period=Period(start=NOW - timedelta(days=20), end=NOW - timedelta(days=10)),
        holdout_stationary_period=Period(start=NOW - timedelta(days=10), end=NOW),
        invalidation_triggers=["model_version_change"],
    )
    report = calibrate_detector(
        detector_id="detector-1",
        stationarity_regime=regime,
        fp_target=FpTarget(horizon="30d", alpha=0.05),
        calibration_streams=[[0.1, 0.2, 0.3] for _ in range(100)],
        holdout_streams=[[0.01, 0.02, 0.03] for _ in range(100)],
        seed=7,
    )
    audit = build_calibration_audit(calibration_id="calibration-1", report=report)
    budget = MetricBudgetPolicy(
        model_id="model-1",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.9,
        minimum_acceptable_value=0.8,
    )
    return report, audit, budget


def _shift(**changes):
    payload = {
        "event_id": "shift-1",
        "timestamp": NOW,
        "model_id": "model-1",
        "model_version": "v1",
        "detector_id": "detector-1",
        "detector_family": "mmd",
        "signal": "input_shift",
        "representation": "features-v1",
        "reference_window": MonitoringWindow(
            start=NOW - timedelta(days=2), end=NOW - timedelta(days=1), n=3
        ),
        "current_window": MonitoringWindow(start=NOW - timedelta(days=1), end=NOW, n=3),
        "stationarity_regime_id": "regime-1",
        "calibration_id": "calibration-1",
        "test_statistic": 0.1,
        "p_value": 0.7,
        "empirical_fp_rate": 0.0,
        "shift_severity": 0.1,
    }
    payload.update(changes)
    return ShiftDetectedEvent(**payload)


def _degradation(**changes):
    payload = {
        "event_id": "degradation-1",
        "timestamp": NOW,
        "model_id": "model-1",
        "model_version": "v1",
        "metric": "accuracy",
        "metric_direction": MetricDirection.HIGHER_IS_BETTER,
        "source": "realized_performance",
        "estimator": "realized_accuracy_v1",
        "reference_value": 0.9,
        "minimum_acceptable_value": 0.8,
        "current_estimate": 0.89,
        "confidence_interval_95": (0.88, 0.90),
        "budget_used": 0.1,
        "calibration_id": "calibration-1",
    }
    payload.update(changes)
    if "budget_used" not in changes:
        payload["budget_used"] = metric_budget_used(
            metric_direction=payload["metric_direction"],
            reference_value=payload["reference_value"],
            current_estimate=payload["current_estimate"],
            confidence_interval_95=payload["confidence_interval_95"],
            minimum_acceptable_value=payload["minimum_acceptable_value"],
            maximum_acceptable_value=payload.get("maximum_acceptable_value"),
        )
    return PerformanceDegradationEvent(**payload)


def _run(*, shift_events=None, degradation_event=None):
    report, audit, budget = _context()
    result = DriftAndDegradationMonitor().evaluate_window(
        model_id="model-1",
        model_version="v1",
        shift_events=shift_events,
        degradation_event=degradation_event,
        metric_budget=budget,
        calibration_audit=audit,
        _calibration_report=report,
        _observed_invalidation_triggers=[],
        timestamp=NOW,
    )
    assert result.registry_record is not None
    return report, audit, budget, result


@pytest.mark.parametrize("field", ["detector_id", "calibration_id", "stationarity_regime_id"])
def test_monitor_reconciles_every_shared_calibration_identity(field):
    with pytest.raises(ValueError, match=r"calibration.*binding|binding.*calibration"):
        _run(shift_events=[_shift(**{field: "foreign-source"})])


@pytest.mark.parametrize(
    "changes",
    [
        {"metric": "latency"},
        {"reference_value": 0.95},
        {"minimum_acceptable_value": 0.7},
        {"maximum_acceptable_value": 1.0},
        {"metric_direction": MetricDirection.LOWER_IS_BETTER, "maximum_acceptable_value": 1.0},
    ],
)
def test_monitor_reconciles_every_declared_metric_budget_field(changes):
    with pytest.raises(ValueError, match=r"metric.*binding|binding.*metric"):
        _run(degradation_event=_degradation(**changes))


def test_readiness_recomputes_budget_quantity_before_accepting_source():
    event = _degradation(
        current_estimate=0.70, confidence_interval_95=(0.69, 0.71), budget_used=0.0
    )
    # Independent bounded-ratio oracle; no statistical/backend assumption.
    expected = min(1.0, max(0.0, (0.9 - 0.69) / (0.9 - 0.8)))
    assert expected == 1.0
    with pytest.raises(ValueError, match="budget_used_mismatch"):
        _run(degradation_event=event)


def test_nonfinite_budget_inputs_do_not_become_clean_readiness():
    event = _degradation(current_estimate=float("nan"), budget_used=0.0)
    with pytest.raises(ValueError, match="budget_used_not_established"):
        _run(degradation_event=event)


def _reopen(report, audit, budget, result, *, now=NOW, payload=None):
    record = result.registry_record
    assert record is not None
    reloaded = ModelRegistryReadinessRecord.model_validate_json(
        json.dumps(record.model_dump(mode="json") if payload is None else payload)
    )
    assert not evaluate_registry_gate(reloaded).promotion_allowed
    return rebind_calibration_validity(
        reloaded,
        report=report,
        calibration_audit=audit,
        now=now,
        observed_invalidation_triggers=[],
        metric_budget=budget,
        readiness_event=result.readiness_event,
        shift_events=result.shift_risk_events,
        last_degradation_event=result.degradation_event,
    )


def test_real_calibration_producer_json_readback_reconciles_sources_and_time(tmp_path):
    report, audit, budget, result = _run(degradation_event=_degradation())
    record = result.registry_record
    assert record is not None
    assert report.empirical_stationary_holdout.windows == 100
    assert report.empirical_stationary_holdout.alerts == 0
    assert report.empirical_stationary_holdout.pass_
    assert record.readiness_effective_at == result.readiness_event.timestamp
    assert record.readiness_expires_at == result.readiness_event.expires_at
    path = tmp_path / "registry.json"
    path.write_text(record.model_dump_json())
    payload = json.loads(path.read_text())
    rebound = _reopen(report, audit, budget, result, payload=payload)
    assert evaluate_registry_gate(rebound).promotion_allowed
    assert rebound.calibration_validity.report_digest == record.calibration_validity.report_digest


def test_readiness_expiry_remains_distinct_from_report_expiry():
    report, audit, budget, result = _run(degradation_event=_degradation())
    expires_at = result.readiness_event.expires_at
    assert expires_at is not None
    assert expires_at < report.expiration.valid_until
    boundary = _reopen(report, audit, budget, result, now=expires_at)
    assert evaluate_registry_gate(boundary).promotion_allowed
    later = _reopen(report, audit, budget, result, now=expires_at + timedelta(microseconds=1))
    assert not evaluate_registry_gate(later).promotion_allowed
    assert evaluate_registry_gate(later).reason == "readiness_expired"
    assert later.calibration_validity.status == "valid"


def test_fresh_read_refuses_present_but_fake_metric_payload():
    report, audit, budget, result = _run(degradation_event=_degradation())
    payload = result.registry_record.model_dump(mode="json")
    payload["primary_metric_budget"]["metric"] = "latency"
    assert payload["empirical_fp_certificate"] and payload["promotion_allowed"]
    rebound = _reopen(report, audit, budget, result, payload=payload)
    assert not evaluate_registry_gate(rebound).promotion_allowed
    assert evaluate_registry_gate(rebound).reason == "registry_source_binding_not_established"


def test_source_context_is_required_after_reload():
    report, audit, _, result = _run(degradation_event=_degradation())
    record = ModelRegistryReadinessRecord.model_validate_json(
        result.registry_record.model_dump_json()
    )
    rebound = rebind_calibration_validity(
        record, report=report, calibration_audit=audit, now=NOW, observed_invalidation_triggers=[]
    )
    assert not evaluate_registry_gate(rebound).promotion_allowed
    assert evaluate_registry_gate(rebound).reason == "registry_source_binding_not_established"


def test_persisted_veto_cannot_be_restored_by_mutating_rebound_permission():
    report, audit, budget, result = _run(degradation_event=_degradation())
    payload = result.registry_record.model_dump(mode="json")
    payload["promotion_allowed"] = False
    rebound = _reopen(report, audit, budget, result, payload=payload)
    assert not rebound.promotion_allowed
    assert evaluate_registry_gate(rebound).reason == "persisted_readiness_veto"
    rebound.promotion_allowed = True
    assert not evaluate_registry_gate(rebound).promotion_allowed
    assert evaluate_registry_gate(rebound).reason == "registry_source_binding_not_established"


def test_public_projection_mutation_does_not_mutate_checker_evidence():
    _, _, _, result = _run(degradation_event=_degradation())
    record = result.registry_record
    assert record is not None and record.calibration_validity is not None
    assert evaluate_registry_gate(record).promotion_allowed
    record.calibration_validity.valid_until += timedelta(days=100)
    assert not evaluate_registry_gate(record).promotion_allowed
    assert evaluate_registry_gate(record).reason == "calibration_validity_projection_mismatch"


def test_rule_change_with_same_pass_refuses_exact_report_rebind():
    report, audit, budget, result = _run(degradation_event=_degradation())
    changed = report.model_copy(update={"calibration_method": "different-rule-v2"})
    assert changed.empirical_stationary_holdout.pass_
    rebound = _reopen(changed, audit, budget, result)
    assert not evaluate_registry_gate(rebound).promotion_allowed
    assert evaluate_registry_gate(rebound).reason == "calibration_report_binding_not_established"
