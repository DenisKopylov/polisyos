"""Metric-budget readiness mapping for DDM-15.7."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ddm_15_7.integration.events import (
    DataQualitySignal,
    MetricDirection,
    PerformanceDegradationEvent,
    ReadinessState,
    ReadinessStateEvent,
    ShiftRiskEvent,
)


class MetricBudgetPolicy(BaseModel):
    """Primary metric budget for a deployed model version."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    metric_direction: MetricDirection
    reference_value: float
    minimum_acceptable_value: float | None = None
    maximum_acceptable_value: float | None = None

    @model_validator(mode="after")
    def _validate_floor_or_ceiling(self) -> MetricBudgetPolicy:
        if (
            self.metric_direction is MetricDirection.HIGHER_IS_BETTER
            and self.minimum_acceptable_value is None
        ):
            raise ValueError("higher-is-better budget requires minimum_acceptable_value")
        if (
            self.metric_direction is MetricDirection.LOWER_IS_BETTER
            and self.maximum_acceptable_value is None
        ):
            raise ValueError("lower-is-better budget requires maximum_acceptable_value")
        if (
            self.metric_direction is MetricDirection.HIGHER_IS_BETTER
            and self.minimum_acceptable_value is not None
            and self.reference_value <= self.minimum_acceptable_value
        ):
            raise ValueError("reference_value must be above minimum_acceptable_value")
        if (
            self.metric_direction is MetricDirection.LOWER_IS_BETTER
            and self.maximum_acceptable_value is not None
            and self.reference_value >= self.maximum_acceptable_value
        ):
            raise ValueError("reference_value must be below maximum_acceptable_value")
        return self


class ReadinessPolicy(BaseModel):
    """Configurable thresholds for the readiness mapper."""

    model_config = ConfigDict(extra="forbid")

    ready_threshold: float = Field(default=0.25, gt=0.0, lt=1.0)
    investigate_threshold: float = Field(default=0.50, gt=0.0, lt=1.0)
    exhausted_threshold: float = Field(default=1.0, gt=0.0)
    shift_risk_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    high_risk_shift_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    state_ttl_days: int = Field(default=7, ge=1)


DEFAULT_READINESS_POLICY = ReadinessPolicy()


def metric_budget_used(
    *,
    metric_direction: MetricDirection,
    reference_value: float,
    current_estimate: float,
    confidence_interval_95: tuple[float, float],
    minimum_acceptable_value: float | None = None,
    maximum_acceptable_value: float | None = None,
) -> float:
    """Compute clipped metric budget consumption from the confidence bound."""

    low, high = confidence_interval_95
    if high < low:
        raise ValueError("confidence interval upper bound must be >= lower bound")
    if metric_direction is MetricDirection.HIGHER_IS_BETTER:
        if minimum_acceptable_value is None:
            raise ValueError("higher-is-better metrics require a minimum acceptable value")
        budget = reference_value - minimum_acceptable_value
        if budget <= 0.0:
            raise ValueError("higher-is-better metric budget must be positive")
        value_at_risk = low
        raw_budget_used = (reference_value - value_at_risk) / budget
    else:
        if maximum_acceptable_value is None:
            raise ValueError("lower-is-better metrics require a maximum acceptable value")
        budget = maximum_acceptable_value - reference_value
        if budget <= 0.0:
            raise ValueError("lower-is-better metric budget must be positive")
        value_at_risk = high
        raw_budget_used = (value_at_risk - reference_value) / budget

    return _clip(raw_budget_used)


def map_readiness(
    *,
    model_id: str,
    model_version: str,
    degradation_event: PerformanceDegradationEvent | None = None,
    shift_events: list[ShiftRiskEvent] | None = None,
    data_quality_signals: list[DataQualitySignal] | None = None,
    critical_slice_budget_used: float | None = None,
    policy: ReadinessPolicy | None = None,
    timestamp: datetime | None = None,
) -> ReadinessStateEvent:
    """Convert drift, degradation, and data-quality evidence into registry state."""

    effective_policy = policy or DEFAULT_READINESS_POLICY
    effective_timestamp = timestamp or datetime.now(UTC)
    shifts = [event for event in shift_events or [] if not event.diagnostic_only]
    quality_signals = list(data_quality_signals or [])

    performance_budget = 0.0 if degradation_event is None else degradation_event.budget_used
    critical_budget = _clip(critical_slice_budget_used or 0.0)
    shift_score = max((event.risk_score for event in shifts), default=0.0)
    weighted_shift_score = _clip(effective_policy.shift_risk_weight * shift_score)
    data_quality_risk = max((signal.risk_score for signal in quality_signals), default=0.0)
    hard_data_quality_failure = any(signal.hard_failure for signal in quality_signals)
    high_risk_shift = shift_score >= effective_policy.high_risk_shift_threshold

    readiness_risk = max(
        performance_budget,
        weighted_shift_score,
        data_quality_risk,
        critical_budget,
    )
    state, reason = _state_and_reason(
        performance_budget=performance_budget,
        critical_budget=critical_budget,
        has_shift=bool(shifts),
        high_risk_shift=high_risk_shift,
        hard_data_quality_failure=hard_data_quality_failure,
        policy=effective_policy,
    )
    actions = _actions_for_state(state)
    active_signals = _active_signals(
        degradation_event=degradation_event,
        shift_events=shifts,
        data_quality_signals=quality_signals,
    )

    return ReadinessStateEvent(
        event_id=f"readiness-{model_id}-{model_version}-{effective_timestamp.isoformat()}",
        timestamp=effective_timestamp,
        model_id=model_id,
        model_version=model_version,
        readiness_state=state,
        readiness_score=round(100.0 * (1.0 - _clip(readiness_risk))),
        primary_reason=reason,
        active_signals=active_signals,
        affected_slices=_affected_slices(shifts),
        required_actions=actions,
        expires_at=effective_timestamp + timedelta(days=effective_policy.state_ttl_days),
        promotion_allowed=state in {ReadinessState.R4, ReadinessState.R3},
    )


def _state_and_reason(
    *,
    performance_budget: float,
    critical_budget: float,
    has_shift: bool,
    high_risk_shift: bool,
    hard_data_quality_failure: bool,
    policy: ReadinessPolicy,
) -> tuple[ReadinessState, str]:
    if hard_data_quality_failure:
        return ReadinessState.R0, "hard_data_contract_failure"
    if performance_budget >= policy.exhausted_threshold:
        return ReadinessState.R0, f"metric_budget_exhausted_{performance_budget:.2f}"
    if critical_budget >= policy.exhausted_threshold:
        return ReadinessState.R0, f"critical_slice_budget_exhausted_{critical_budget:.2f}"
    if performance_budget >= policy.investigate_threshold:
        return ReadinessState.R1, f"metric_budget_used_{performance_budget:.2f}"
    if critical_budget >= policy.investigate_threshold:
        return ReadinessState.R1, f"critical_slice_budget_used_{critical_budget:.2f}"
    if performance_budget >= policy.ready_threshold:
        return ReadinessState.R2, f"metric_budget_used_{performance_budget:.2f}"
    if critical_budget >= policy.ready_threshold:
        return ReadinessState.R2, f"critical_slice_budget_used_{critical_budget:.2f}"
    if high_risk_shift:
        return ReadinessState.R2, "persistent_high_risk_shift_without_confirmed_degradation"
    if has_shift:
        return ReadinessState.R3, "calibrated_shift_without_material_degradation"
    return ReadinessState.R4, "within_metric_budget_and_no_active_shift"


def _actions_for_state(state: ReadinessState) -> list[str]:
    if state is ReadinessState.R4:
        return ["continue_monitoring"]
    if state is ReadinessState.R3:
        return ["annotate_dashboard", "increase_label_sampling"]
    if state is ReadinessState.R2:
        return ["open_investigation_ticket", "increase_label_sampling", "run_shadow_retrain"]
    if state is ReadinessState.R1:
        return ["freeze_rollout", "trigger_shadow_retrain", "require_owner_signoff"]
    return ["rollback_or_route_to_fallback", "page_model_owner", "block_registry_promotion"]


def _active_signals(
    *,
    degradation_event: PerformanceDegradationEvent | None,
    shift_events: list[ShiftRiskEvent],
    data_quality_signals: list[DataQualitySignal],
) -> list[str]:
    signals: set[str] = {event.signal for event in shift_events}
    if degradation_event is not None:
        signals.add(
            "estimated_performance_drop"
            if degradation_event.source == "estimated_performance"
            else "realized_performance_drop"
        )
    if data_quality_signals:
        signals.add("data_quality")
    return sorted(signals)


def _affected_slices(shift_events: list[ShiftRiskEvent]) -> list[str]:
    values: set[str] = set()
    for event in shift_events:
        values.update(item.slice for item in event.affected_slices)
    return sorted(values)


def _clip(value: float) -> float:
    return min(1.0, max(0.0, float(value)))
