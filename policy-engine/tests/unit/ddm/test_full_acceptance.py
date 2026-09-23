"""Full DDM acceptance-surface tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.ddm.calibration import CalibrationReport, build_calibration_audit
from polisyos.ddm.integration import (
    AffectedFeature,
    AffectedSlice,
    CalibrationAudit,
    DataQualitySignal,
    DriftAndDegradationMonitor,
    MetricDirection,
    MonitoringWindow,
    ModelRegistryReadinessRecord,
    PerformanceDegradationEvent,
    ReadinessState,
    ShiftDetectedEvent,
    evaluate_registry_gate,
)
from polisyos.ddm.integration.model_registry import rebind_calibration_validity
from polisyos.ddm.readiness import MetricBudgetPolicy


def _window() -> MonitoringWindow:
    return MonitoringWindow(
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 2, tzinfo=UTC),
        n=100,
    )


def _valid_calibration_report(
    *,
    detector_id: str = "input_mmd_global_v3",
    stationarity_regime_id: str = "SR-1-model-v1",
    valid_until: str = "2026-05-01T00:00:00Z",
    invalidation_triggers: list[str] | None = None,
) -> CalibrationReport:
    return CalibrationReport.model_validate(
        {
            "model_id": "model",
            "model_version": "v1",
            "detector_id": detector_id,
            "stationarity_regime_id": stationarity_regime_id,
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
                "valid_until": valid_until,
                "invalidation_triggers": (
                    ["model_version_change"]
                    if invalidation_triggers is None
                    else invalidation_triggers
                ),
            },
            "calibration_method": "moving_block_bootstrap_quantile",
            "random_seed": 0,
            "block_length": 2,
        }
    )


def _registry_context(
    *,
    report: CalibrationReport | None = None,
    timestamp: datetime = datetime(2026, 4, 26, tzinfo=UTC),
    observed_triggers: list[str] | None = None,
) -> tuple[CalibrationReport, CalibrationAudit, ModelRegistryReadinessRecord]:
    report = _valid_calibration_report() if report is None else report
    audit = build_calibration_audit(calibration_id="calib-1", report=report)
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
        metric_budget=metric_budget,
        calibration_audit=audit,
        _calibration_report=report,
        _observed_invalidation_triggers=observed_triggers,
        timestamp=timestamp,
    )
    assert result.registry_record is not None
    return report, audit, result.registry_record


def _valid_checker_bound_registry_record() -> ModelRegistryReadinessRecord:
    _, _, record = _registry_context(observed_triggers=[])
    assert evaluate_registry_gate(record).promotion_allowed is True
    return record


def test_monitor_emits_all_runtime_outputs_and_registry_gate_blocks_r1() -> None:
    calibration_report = CalibrationReport.model_validate(
        {
            "model_id": "model",
            "model_version": "v1",
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
        _calibration_report=calibration_report,
        _observed_invalidation_triggers=[],
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


def test_full_acceptance_boundary_consumes_forwarded_contracts() -> None:
    """The existing monitor surface must consume relocated contracts unchanged."""

    from polisyos.ddm.contracts.events import (
        CalibrationValidityProjection as CanonicalCalibrationValidityProjection,
        ShiftDetectedEvent as CanonicalShiftDetectedEvent,
    )
    from polisyos.ddm.contracts.metric_budget import (
        MetricBudgetPolicy as CanonicalMetricBudgetPolicy,
    )
    from polisyos.ddm.integration import (
        CalibrationValidityProjection as PublicCalibrationValidityProjection,
        ShiftDetectedEvent as PublicShiftDetectedEvent,
    )
    from polisyos.ddm.readiness import MetricBudgetPolicy as PublicMetricBudgetPolicy

    assert PublicCalibrationValidityProjection is CanonicalCalibrationValidityProjection
    assert PublicShiftDetectedEvent is CanonicalShiftDetectedEvent
    assert PublicMetricBudgetPolicy is CanonicalMetricBudgetPolicy

    event = CanonicalShiftDetectedEvent(
        event_id="shift-boundary",
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
        test_statistic=0.2,
        ert=10000,
        empirical_fp_rate=0.001,
        shift_severity=0.72,
    )
    budget = CanonicalMetricBudgetPolicy(
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
        shift_events=[event],
        metric_budget=budget,
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert result.shift_risk_events[0].shift_event_id == "shift-boundary"
    assert result.readiness_event.readiness_state == ReadinessState.R3


def test_monitor_rejects_foreign_metric_budget_identity() -> None:
    foreign_budget = MetricBudgetPolicy(
        model_id="foreign-model",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.90,
        minimum_acceptable_value=0.80,
    )

    with pytest.raises(ValueError, match="metric_budget"):
        DriftAndDegradationMonitor().evaluate_window(
            model_id="model",
            model_version="v1",
            metric_budget=foreign_budget,
            timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        )


def test_monitor_rejects_foreign_shift_event_identity() -> None:
    foreign_shift = ShiftDetectedEvent(
        event_id="shift-foreign",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        model_id="foreign-model",
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
    )

    with pytest.raises(ValueError, match="shift_events"):
        DriftAndDegradationMonitor().evaluate_window(
            model_id="model",
            model_version="v1",
            shift_events=[foreign_shift],
            timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        )


def test_monitor_rejects_foreign_degradation_event_identity() -> None:
    foreign_degradation = PerformanceDegradationEvent(
        event_id="degrade-foreign",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        model_id="foreign-model",
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

    with pytest.raises(ValueError, match="degradation_event"):
        DriftAndDegradationMonitor().evaluate_window(
            model_id="model",
            model_version="v1",
            degradation_event=foreign_degradation,
            timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        )


def test_monitor_rejects_foreign_data_quality_identity() -> None:
    foreign_signal = DataQualitySignal(
        signal_id="dq-foreign",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        model_id="foreign-model",
        model_version="v1",
        risk_score=0.0,
    )

    with pytest.raises(ValueError, match="data_quality_signals"):
        DriftAndDegradationMonitor().evaluate_window(
            model_id="model",
            model_version="v1",
            data_quality_signals=[foreign_signal],
            timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        )


def test_registry_gate_blocks_legacy_calibration_without_model_identity() -> None:
    legacy_payload = _valid_calibration_report().model_dump(mode="python")
    legacy_payload.pop("model_id")
    legacy_payload.pop("model_version")
    legacy_report = CalibrationReport.model_validate(legacy_payload)
    audit = build_calibration_audit(calibration_id="calib-legacy", report=legacy_report)
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
        metric_budget=metric_budget,
        calibration_audit=audit,
        _calibration_report=legacy_report,
        _observed_invalidation_triggers=[],
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert result.registry_record is not None
    gate = evaluate_registry_gate(result.registry_record)
    assert gate.promotion_allowed is False
    assert gate.reason == "calibration_model_identity_not_established"


def test_registry_gate_blocks_historical_audit_without_validity_owner() -> None:
    """A shaped historical FP pass is not current calibration authority."""

    # The current audit contract has no checker result or report binding. A
    # caller-supplied, otherwise valid-looking audit must therefore remain
    # NOT_ESTABLISHED rather than authorize an R4 registry decision.
    audit = CalibrationAudit(
        calibration_id="calib-unchecked",
        detector_id="input_mmd_global_v3",
        stationarity_regime_id="SR-1-model-v1",
        horizon="30d",
        alpha=0.05,
        ert=10000,
        empirical_fp_rate=0.0,
        empirical_fp_upper_95=0.03,
        pass_=True,
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
        metric_budget=metric_budget,
        calibration_audit=audit,
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert result.registry_record is not None
    gate = evaluate_registry_gate(result.registry_record)

    assert gate.promotion_allowed is False


@pytest.mark.parametrize("readiness_state", [ReadinessState.R4, ReadinessState.R3])
def test_registry_gate_rejects_persisted_readiness_veto_for_r4_r3(
    readiness_state: ReadinessState,
) -> None:
    """A persisted upstream veto remains binding despite owner signoff."""

    record = _valid_checker_bound_registry_record().model_copy(
        update={"readiness_state": readiness_state, "promotion_allowed": False}
    )

    gate = evaluate_registry_gate(record, owner_signoff=True)

    assert gate.promotion_allowed is False
    assert gate.reason == "persisted_readiness_veto"


def test_registry_gate_preserves_r2_owner_signoff_exception_after_veto() -> None:
    """R2 may still use its documented limited owner-signoff exception."""

    record = _valid_checker_bound_registry_record().model_copy(
        update={"readiness_state": ReadinessState.R2, "promotion_allowed": False}
    )

    gate = evaluate_registry_gate(record, owner_signoff=True)

    assert gate.promotion_allowed is True
    assert gate.reason == "R2_owner_signoff_allows_limited_expansion"


def test_registry_public_round_trip_fails_closed_without_durable_validity() -> None:
    """Public registry reload loses private checker authority and fails closed."""

    record = _valid_checker_bound_registry_record()
    assert evaluate_registry_gate(record).promotion_allowed is True

    payload = record.model_dump(mode="json")
    assert payload["calibration_validity"]["status"] == "valid"
    assert payload["calibration_validity"]["observation_status"] == "observed"
    for non_durable_field in {
        "_calibration_validity_evidence",
        "calibration_validity_evidence",
        "report_digest",
        "effective_at",
        "expires_at",
        "expiration",
        "valid_until",
        "invalidation_triggers",
    }:
        assert non_durable_field not in payload

    reloaded = ModelRegistryReadinessRecord.model_validate(payload)
    gate = evaluate_registry_gate(reloaded)

    assert gate.promotion_allowed is False
    assert gate.reason == "calibration_validity_not_established"


def test_registry_public_round_trip_rebinds_with_exact_context() -> None:
    """A public projection becomes current only after exact checker rebind."""

    report, audit, record = _registry_context(observed_triggers=[])
    projection = record.calibration_validity
    assert projection is not None

    reloaded = ModelRegistryReadinessRecord.model_validate(record.model_dump(mode="json"))
    assert evaluate_registry_gate(reloaded).promotion_allowed is False

    rebound = rebind_calibration_validity(
        reloaded,
        report=report,
        calibration_audit=audit,
        now=projection.effective_at,
        observed_invalidation_triggers=[],
    )

    assert rebound.calibration_validity == projection
    assert evaluate_registry_gate(rebound).promotion_allowed is True


def test_registry_rebind_refreshes_projection_for_current_context() -> None:
    """Rebind replaces stale dynamic fields with the current checker result."""

    report, audit, record = _registry_context(observed_triggers=[])
    projection = record.calibration_validity
    assert projection is not None
    reloaded = ModelRegistryReadinessRecord.model_validate(record.model_dump(mode="json"))
    current_time = datetime(2026, 4, 27, tzinfo=UTC)

    rebound = rebind_calibration_validity(
        reloaded,
        report=report,
        calibration_audit=audit,
        now=current_time,
        observed_invalidation_triggers=["model_version_change"],
    )

    current_projection = rebound.calibration_validity
    assert current_projection is not None
    assert current_projection.calibration_id == projection.calibration_id
    assert current_projection.report_digest == projection.report_digest
    assert current_projection.effective_at == current_time
    assert current_projection.observed_invalidation_triggers == ["model_version_change"]
    assert current_projection.status == "invalidated"
    assert current_projection.reasons == ["model_version_change"]
    gate = evaluate_registry_gate(rebound)
    assert gate.promotion_allowed is False
    assert gate.reason == "calibration_model_version_change"


def test_registry_legacy_payload_stays_not_established_after_rebind() -> None:
    """Missing legacy projection cannot be synthesized into authority."""

    report, audit, record = _registry_context(observed_triggers=[])
    payload = record.model_dump(mode="json")
    payload.pop("calibration_validity")
    legacy = ModelRegistryReadinessRecord.model_validate(payload)

    rebound = rebind_calibration_validity(
        legacy,
        report=report,
        calibration_audit=audit,
        now=datetime(2026, 4, 26, tzinfo=UTC),
        observed_invalidation_triggers=[],
    )

    gate = evaluate_registry_gate(rebound)
    assert gate.promotion_allowed is False
    assert gate.reason == "calibration_validity_not_established"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("report_digest", "0" * 64),
        ("calibration_id", "foreign-calibration"),
        ("detector_id", "foreign-detector"),
        ("stationarity_regime_id", "foreign-regime"),
    ],
)
def test_registry_rebind_rejects_tampered_validity_projection(
    field: str,
    value: str,
) -> None:
    """Tampered public identity or digest cannot restore checker authority."""

    report, audit, record = _registry_context(observed_triggers=[])
    payload = record.model_dump(mode="json")
    assert payload["calibration_validity"] is not None
    payload["calibration_validity"][field] = value
    tampered = ModelRegistryReadinessRecord.model_validate(payload)

    rebound = rebind_calibration_validity(
        tampered,
        report=report,
        calibration_audit=audit,
        now=datetime(2026, 4, 26, tzinfo=UTC),
        observed_invalidation_triggers=[],
    )

    gate = evaluate_registry_gate(rebound)
    assert gate.promotion_allowed is False
    assert gate.reason == "calibration_report_binding_not_established"


def test_registry_distinguishes_unavailable_from_observed_empty_triggers() -> None:
    """Missing trigger context is not equivalent to an observed empty set."""

    report = _valid_calibration_report()
    _, _, unavailable = _registry_context(report=report, observed_triggers=None)
    unavailable_projection = unavailable.calibration_validity
    assert unavailable_projection is not None
    assert unavailable_projection.observation_status == "unavailable"
    assert unavailable_projection.status == "not_established"
    assert evaluate_registry_gate(unavailable).reason == "calibration_validity_not_established"

    _, _, observed_empty = _registry_context(report=report, observed_triggers=[])
    observed_projection = observed_empty.calibration_validity
    assert observed_projection is not None
    assert observed_projection.observation_status == "observed"
    assert observed_projection.observed_invalidation_triggers == []
    assert observed_projection.status == "valid"
    assert evaluate_registry_gate(observed_empty).promotion_allowed is True


def test_registry_rebind_preserves_expiry_reason_without_trigger_observation() -> None:
    """Unavailable triggers still expose a deterministic expiry block reason."""

    report, audit, record = _registry_context(observed_triggers=[])
    reloaded = ModelRegistryReadinessRecord.model_validate(record.model_dump(mode="json"))
    rebound = rebind_calibration_validity(
        reloaded,
        report=report,
        calibration_audit=audit,
        now=datetime(2026, 5, 1, 0, 0, 1, tzinfo=UTC),
        observed_invalidation_triggers=None,
    )

    projection = rebound.calibration_validity
    assert projection is not None
    assert projection.observation_status == "unavailable"
    assert projection.status == "not_established"
    assert projection.reasons == [
        "calibration_expired",
        "invalidation_observation_unavailable",
    ]
    gate = evaluate_registry_gate(rebound)
    assert gate.promotion_allowed is False
    assert gate.reason == "calibration_expired"


@pytest.mark.parametrize(
    ("timestamp", "expected_status", "allowed"),
    [
        (datetime(2026, 4, 30, 23, 59, 59, tzinfo=UTC), "valid", True),
        (datetime(2026, 5, 1, tzinfo=UTC), "valid", True),
        (datetime(2026, 5, 1, 0, 0, 1, tzinfo=UTC), "expired", False),
    ],
)
def test_registry_projection_preserves_expiry_boundary(
    timestamp: datetime,
    expected_status: str,
    allowed: bool,
) -> None:
    """Expiry uses strict now > valid_until semantics in the public projection."""

    _, _, record = _registry_context(timestamp=timestamp, observed_triggers=[])
    projection = record.calibration_validity
    assert projection is not None
    assert projection.status == expected_status
    assert evaluate_registry_gate(record).promotion_allowed is allowed


def test_registry_projection_records_matching_invalidation_trigger() -> None:
    """Configured and observed trigger intersection invalidates the record."""

    _, _, record = _registry_context(
        observed_triggers=["model_version_change", "unconfigured_trigger"]
    )
    projection = record.calibration_validity
    assert projection is not None
    assert projection.configured_invalidation_triggers == ["model_version_change"]
    assert projection.observed_invalidation_triggers == [
        "model_version_change",
        "unconfigured_trigger",
    ]
    assert projection.status == "invalidated"
    assert projection.reasons == ["model_version_change"]
    gate = evaluate_registry_gate(record)
    assert gate.promotion_allowed is False
    assert gate.reason == "calibration_model_version_change"
