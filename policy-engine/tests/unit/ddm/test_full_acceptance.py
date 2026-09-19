"""Full DDM acceptance-surface tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.ddm.calibration import (
    CalibrationReport,
    build_calibration_audit,
    check_calibration_validity,
)
from polisyos.ddm.integration import (
    AffectedFeature,
    AffectedSlice,
    CalibrationAudit,
    DriftAndDegradationMonitor,
    MetricDirection,
    MonitoringWindow,
    PerformanceDegradationEvent,
    ReadinessState,
    ReadinessStateEvent,
    ShiftDetectedEvent,
    ShiftRiskEvent,
    build_model_registry_record,
    evaluate_registry_gate,
)
from polisyos.ddm.readiness import MetricBudgetPolicy, map_readiness


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


def test_full_acceptance_boundary_consumes_forwarded_contracts() -> None:
    """The existing monitor surface must consume relocated contracts unchanged."""

    from polisyos.ddm.contracts.events import ShiftDetectedEvent as CanonicalShiftDetectedEvent
    from polisyos.ddm.contracts.metric_budget import (
        MetricBudgetPolicy as CanonicalMetricBudgetPolicy,
    )
    from polisyos.ddm.integration import ShiftDetectedEvent as PublicShiftDetectedEvent
    from polisyos.ddm.readiness import MetricBudgetPolicy as PublicMetricBudgetPolicy

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


def _calibration_report(
    *,
    valid_until: datetime,
    invalidation_triggers: list[str] | None = None,
    detector_id: str = "input_mmd_global_v3",
    stationarity_regime_id: str = "SR-1-model-v1",
) -> CalibrationReport:
    """Build a real calibration report for hostile applicability witnesses."""

    return CalibrationReport.model_validate(
        {
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
                "invalidation_triggers": invalidation_triggers or [],
            },
            "calibration_method": "moving_block_bootstrap_quantile",
            "random_seed": 0,
            "block_length": 2,
        }
    )


def _readiness_event(
    *,
    state: ReadinessState = ReadinessState.R4,
    promotion_allowed: bool | None = None,
    model_id: str = "model",
    model_version: str = "v1",
    primary_reason: str = "within_metric_budget_and_no_active_shift",
) -> ReadinessStateEvent:
    """Create a typed readiness projection without bypassing validation."""

    return ReadinessStateEvent(
        event_id=f"readiness-{model_id}-{model_version}-{state.value}",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        model_id=model_id,
        model_version=model_version,
        readiness_state=state,
        readiness_score=100 if state in {ReadinessState.R4, ReadinessState.R3} else 20,
        primary_reason=primary_reason,
        required_actions=[] if state in {ReadinessState.R4, ReadinessState.R3} else [
            "block_registry_promotion"
        ],
        promotion_allowed=(
            state in {ReadinessState.R4, ReadinessState.R3}
            if promotion_allowed is None
            else promotion_allowed
        ),
    )


def _calibration_audit(
    *,
    calibration_id: str = "calib-1",
    detector_id: str = "input_mmd_global_v3",
    stationarity_regime_id: str = "SR-1-model-v1",
    pass_: bool = True,
) -> CalibrationAudit:
    """Create a historical certificate used by registry-bound witnesses."""

    return CalibrationAudit(
        calibration_id=calibration_id,
        detector_id=detector_id,
        stationarity_regime_id=stationarity_regime_id,
        horizon="30d",
        alpha=0.05,
        ert=10000,
        empirical_fp_rate=0.0,
        empirical_fp_upper_95=0.03,
        pass_=pass_,
    )


def _metric_budget(
    *,
    model_id: str = "model",
    model_version: str = "v1",
) -> MetricBudgetPolicy:
    """Create the canonical metric budget for the target model version."""

    return MetricBudgetPolicy(
        model_id=model_id,
        model_version=model_version,
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.90,
        minimum_acceptable_value=0.80,
    )


def _shift_risk_event(
    *,
    model_id: str = "model",
    model_version: str = "v1",
    detector_id: str = "input_mmd_global_v3",
    stationarity_regime_id: str = "SR-1-model-v1",
    calibration_id: str = "calib-1",
) -> ShiftRiskEvent:
    """Create an already-normalized risk event for identity-binding tests."""

    return ShiftRiskEvent(
        event_id="risk-1",
        shift_event_id="shift-1",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        model_id=model_id,
        model_version=model_version,
        detector_id=detector_id,
        signal="input_shift",
        stationarity_regime_id=stationarity_regime_id,
        calibration_id=calibration_id,
        evidence_kind="ert",
        risk_score=0.25,
        risk_level="watch",
    )


@pytest.mark.parametrize(
    ("valid_until", "observed_triggers", "expected_valid"),
    [
        (datetime(2026, 5, 1, tzinfo=UTC), [], True),
        (datetime(2026, 4, 1, tzinfo=UTC), [], False),
        (datetime(2026, 5, 1, tzinfo=UTC), ["model_version_change"], False),
        (datetime(2026, 5, 1, tzinfo=UTC), ["unrelated_trigger"], True),
    ],
)
def test_registry_gate_requires_current_bound_calibration(
    valid_until: datetime,
    observed_triggers: list[str],
    expected_valid: bool,
) -> None:
    """Historical FP pass must not launder an expired or triggered certificate."""

    report = _calibration_report(
        valid_until=valid_until,
        invalidation_triggers=["model_version_change"],
    )
    validity = check_calibration_validity(
        calibration_id="calib-1",
        report=report,
        now=datetime(2026, 4, 26, tzinfo=UTC),
        observed_invalidation_triggers=observed_triggers,
    )
    audit = build_calibration_audit(calibration_id="calib-1", report=report)
    record = build_model_registry_record(
        readiness_event=_readiness_event(),
        calibration_audit=audit,
        metric_budget=_metric_budget(),
    )
    gate = evaluate_registry_gate(record)

    assert validity.valid is expected_valid
    assert audit.pass_ is True  # historical certificate, not current authority
    assert gate.promotion_allowed is expected_valid


@pytest.mark.parametrize(
    "mismatch",
    [
        "model_id",
        "model_version",
        "detector_id",
        "stationarity_regime_id",
        "calibration_id",
        "metric_budget",
    ],
)
def test_registry_gate_fails_closed_on_foreign_binding(mismatch: str) -> None:
    """A foreign subject/ref/budget cannot inherit the target model's permission."""

    shift = _shift_risk_event()
    audit = _calibration_audit()
    budget = _metric_budget()
    if mismatch == "model_id":
        shift = shift.model_copy(update={"model_id": "foreign-model"})
    elif mismatch == "model_version":
        shift = shift.model_copy(update={"model_version": "foreign-v2"})
    elif mismatch == "detector_id":
        shift = shift.model_copy(update={"detector_id": "foreign-detector"})
    elif mismatch == "stationarity_regime_id":
        shift = shift.model_copy(update={"stationarity_regime_id": "foreign-regime"})
    elif mismatch == "calibration_id":
        shift = shift.model_copy(update={"calibration_id": "foreign-calibration"})
    else:
        budget = _metric_budget(model_id="foreign-model", model_version="foreign-v2")

    record = build_model_registry_record(
        readiness_event=_readiness_event(),
        calibration_audit=audit,
        metric_budget=budget,
        last_shift_event=shift,
    )
    gate = evaluate_registry_gate(record)

    assert record.model_id == "model"
    assert record.model_version == "v1"
    assert gate.promotion_allowed is False


@pytest.mark.parametrize("state", [ReadinessState.R4, ReadinessState.R3])
def test_registry_gate_honours_persisted_veto_for_r4_and_r3(state: ReadinessState) -> None:
    """The final gate must consume the persisted policy veto, not state membership."""

    readiness = _readiness_event(state=state, promotion_allowed=False)
    record = build_model_registry_record(
        readiness_event=readiness,
        calibration_audit=_calibration_audit(),
        metric_budget=_metric_budget(),
    )

    assert record.promotion_allowed is False
    assert evaluate_registry_gate(record).promotion_allowed is False


@pytest.mark.parametrize(
    ("state", "promotion_allowed", "owner_signoff", "expected"),
    [
        (ReadinessState.R2, False, False, False),
        (ReadinessState.R2, False, True, True),
        (ReadinessState.R2, True, False, False),
        (ReadinessState.R2, True, True, True),
        (ReadinessState.R1, False, True, False),
        (ReadinessState.R0, False, True, False),
    ],
)
def test_registry_gate_keeps_r2_override_and_non_overridable_vetoes(
    state: ReadinessState,
    promotion_allowed: bool,
    owner_signoff: bool,
    expected: bool,
) -> None:
    """R2 is the only limited signoff override; R1/R0 remain blocked."""

    record = build_model_registry_record(
        readiness_event=_readiness_event(
            state=state,
            promotion_allowed=promotion_allowed,
        ),
        calibration_audit=_calibration_audit(),
        metric_budget=_metric_budget(),
    )

    decision = evaluate_registry_gate(record, owner_signoff=owner_signoff)

    assert decision.promotion_allowed is expected


@pytest.mark.parametrize("state", [ReadinessState.R4, ReadinessState.R3, ReadinessState.R2])
def test_failed_certificate_cannot_be_laundered_by_signoff(state: ReadinessState) -> None:
    """A failed empirical certificate is an independent veto in every state."""

    record = build_model_registry_record(
        readiness_event=_readiness_event(
            state=state,
            promotion_allowed=state in {ReadinessState.R4, ReadinessState.R3},
        ),
        calibration_audit=_calibration_audit(pass_=False),
        metric_budget=_metric_budget(),
    )

    assert evaluate_registry_gate(record, owner_signoff=True).promotion_allowed is False


@pytest.mark.parametrize("state", [ReadinessState.R4, ReadinessState.R3])
def test_mapper_builder_and_gate_share_one_policy_projection(state: ReadinessState) -> None:
    """A downstream gate must not reconstruct permission from the readiness state."""

    readiness = map_readiness(
        model_id="model",
        model_version="v1",
        shift_events=[] if state is ReadinessState.R4 else [_shift_risk_event()],
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    ).model_copy(
        update={
            "promotion_allowed": False,
            "primary_reason": "foreign_identity_or_unavailable_observation",
        }
    )
    record = build_model_registry_record(
        readiness_event=readiness,
        calibration_audit=_calibration_audit(),
        metric_budget=_metric_budget(),
    )

    assert record.promotion_allowed is False
    assert evaluate_registry_gate(record).promotion_allowed is False
