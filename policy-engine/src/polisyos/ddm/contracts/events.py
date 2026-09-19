"""Typed DDM-15.7 event contracts.

The monitor deliberately keeps drift evidence, degradation evidence, data
quality failures, and readiness decisions separate. This lets production
systems treat drift as a calibrated risk signal instead of a retraining trigger.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PrivateAttr, model_validator


class MetricDirection(StrEnum):
    """Supported metric monotonicity directions."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class ReadinessState(StrEnum):
    """Operational readiness states emitted by DDM-15.7."""

    R4 = "R4"
    R3 = "R3"
    R2 = "R2"
    R1 = "R1"
    R0 = "R0"


DEFAULT_READINESS_POLICY_ID = "ddm_15_7_default_readiness_policy_v1"
DEFAULT_READINESS_POLICY_VERSION = "v1"
OBSERVATION_WINDOW_UNAVAILABLE = "observation_window_unavailable"


class ApplicabilityStatus(StrEnum):
    """Status of the calibration/report applicability predicate."""

    VALID = "valid"
    INVALID = "invalid"
    NOT_ESTABLISHED = "not_established"


class ObservationWindowStatus(StrEnum):
    """Whether the observation window was actually delivered and observed."""

    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"
    NOT_ESTABLISHED = "not_established"


class GatePredicateProvenance(StrEnum):
    """Provenance class for a predicate used by a promotion gate."""

    RECOMPUTED = "recomputed"
    INDEPENDENTLY_RECONCILED = "independently_reconciled"
    CONSUMER_ASSERTED = "consumer_asserted"
    INSTITUTIONALLY_SUPPLIED = "institutionally_supplied"
    NOT_ESTABLISHED = "not_established"


class DDMApplicabilityProjection(BaseModel):
    """Shared typed applicability and precedence projection.

    This is an in-memory decision artifact. The registry record deliberately
    keeps its existing serialized shape; the final boolean fields are derived
    from this projection and therefore remain safe to persist without hiding
    authority in an untyped dictionary.
    """

    model_config = ConfigDict(extra="forbid")

    policy_id: str = Field(default=DEFAULT_READINESS_POLICY_ID, min_length=1)
    policy_version: str = Field(default=DEFAULT_READINESS_POLICY_VERSION, min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    detector_id: str | None = None
    stationarity_regime_id: str | None = None
    calibration_id: str | None = None
    metric: str | None = None
    metric_budget_model_id: str | None = None
    metric_budget_model_version: str | None = None
    valid_until: AwareDatetime | None = None
    validity: ApplicabilityStatus = ApplicabilityStatus.NOT_ESTABLISHED
    invalidation_reasons: list[str] = Field(default_factory=list)
    invalidation_triggers: list[str] = Field(default_factory=list)
    observed_invalidation_triggers: list[str] = Field(default_factory=list)
    observation_window: ObservationWindowStatus = ObservationWindowStatus.NOT_ESTABLISHED
    effective_at: AwareDatetime | None = None
    identity_bound: bool = False
    baseline_allowed: bool = False
    persisted_veto: bool = False
    policy_provenance: GatePredicateProvenance = GatePredicateProvenance.NOT_ESTABLISHED
    validity_provenance: GatePredicateProvenance = GatePredicateProvenance.NOT_ESTABLISHED
    identity_provenance: GatePredicateProvenance = GatePredicateProvenance.NOT_ESTABLISHED
    observation_provenance: GatePredicateProvenance = GatePredicateProvenance.NOT_ESTABLISHED

    def is_authority_ready(self) -> bool:
        """Return whether all load-bearing predicates are established."""

        return (
            self.policy_id == DEFAULT_READINESS_POLICY_ID
            and self.policy_version == DEFAULT_READINESS_POLICY_VERSION
            and self.validity is ApplicabilityStatus.VALID
            and self.observation_window is ObservationWindowStatus.OBSERVED
            and self.effective_at is not None
            and self.identity_bound
            and self.policy_provenance is GatePredicateProvenance.RECOMPUTED
            and self.validity_provenance is GatePredicateProvenance.RECOMPUTED
            and self.identity_provenance
            is GatePredicateProvenance.INDEPENDENTLY_RECONCILED
            and self.observation_provenance is GatePredicateProvenance.RECOMPUTED
        )


class MonitoringWindow(BaseModel):
    """Reference or current monitoring window."""

    model_config = ConfigDict(extra="forbid")

    start: AwareDatetime
    end: AwareDatetime
    n: int = Field(ge=0)

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.end < self.start:
            raise ValueError("window end must not be before start")
        return self


class AffectedFeature(BaseModel):
    """Localized feature-level shift evidence."""

    model_config = ConfigDict(extra="forbid")

    feature: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    direction: str | None = None


class AffectedSlice(BaseModel):
    """Localized slice-level shift evidence."""

    model_config = ConfigDict(extra="forbid")

    slice: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)


class ShiftDetectedEvent(BaseModel):
    """Calibrated Track 2.2 shift-detection event consumed by DDM-15.7."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["ml.track_2_2.shift_detected.v1"] = "ml.track_2_2.shift_detected.v1"
    event_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    detector_id: str = Field(min_length=1)
    detector_family: str = Field(min_length=1)
    signal: Literal[
        "input_shift",
        "prediction_drift",
        "embedding_shift",
        "attribution_drift",
        "slice_shift",
        "feature_shift",
    ]
    representation: str = Field(min_length=1)
    reference_window: MonitoringWindow
    current_window: MonitoringWindow
    stationarity_regime_id: str = Field(min_length=1)
    calibration_id: str = Field(min_length=1)
    test_statistic: float
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    e_value: float | None = Field(default=None, ge=0.0)
    ert: float | None = Field(default=None, gt=0.0)
    threshold: float | None = None
    empirical_fp_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    shift_severity: float = Field(ge=0.0, le=1.0)
    affected_features: list[AffectedFeature] = Field(default_factory=list)
    affected_slices: list[AffectedSlice] = Field(default_factory=list)
    diagnostic_only: bool = False

    @model_validator(mode="after")
    def _requires_calibrated_evidence(self) -> Self:
        if self.p_value is None and self.e_value is None and self.ert is None:
            raise ValueError("shift event must include p_value, e_value, or ert evidence")
        if self.empirical_fp_rate is None:
            raise ValueError("shift event must include empirical_fp_rate")
        return self


class ShiftRiskEvent(BaseModel):
    """Track 2.2 shift evidence normalized into readiness risk units."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["ml.problem_15_7.shift_risk.v1"] = "ml.problem_15_7.shift_risk.v1"
    event_id: str = Field(min_length=1)
    shift_event_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    detector_id: str = Field(min_length=1)
    signal: str = Field(min_length=1)
    stationarity_regime_id: str = Field(min_length=1)
    calibration_id: str = Field(min_length=1)
    evidence_kind: Literal["p_value", "e_value", "ert"]
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "watch", "investigate"]
    diagnostic_only: bool = False
    affected_features: list[AffectedFeature] = Field(default_factory=list)
    affected_slices: list[AffectedSlice] = Field(default_factory=list)


class PerformanceDegradationEvent(BaseModel):
    """Estimated or realized model-performance degradation event."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["ml.problem_15_7.degradation.v1"] = "ml.problem_15_7.degradation.v1"
    event_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    metric_direction: MetricDirection
    source: Literal["estimated_performance", "realized_performance"]
    estimator: str = Field(min_length=1)
    reference_value: float
    minimum_acceptable_value: float | None = None
    maximum_acceptable_value: float | None = None
    current_estimate: float
    confidence_interval_95: tuple[float, float]
    budget_used: float = Field(ge=0.0, le=1.0)
    label_delay_days_p50: float | None = Field(default=None, ge=0.0)
    label_delay_days_p90: float | None = Field(default=None, ge=0.0)
    corroborating_shift_event_ids: list[str] = Field(default_factory=list)
    readiness_state: ReadinessState | None = None
    recommended_action: str | None = None
    calibration_id: str | None = None

    @model_validator(mode="after")
    def _requires_matching_metric_floor(self) -> Self:
        if (
            self.metric_direction is MetricDirection.HIGHER_IS_BETTER
            and self.minimum_acceptable_value is None
        ):
            raise ValueError("higher-is-better metrics require minimum_acceptable_value")
        if (
            self.metric_direction is MetricDirection.LOWER_IS_BETTER
            and self.maximum_acceptable_value is None
        ):
            raise ValueError("lower-is-better metrics require maximum_acceptable_value")
        low, high = self.confidence_interval_95
        if high < low:
            raise ValueError("confidence_interval_95 upper bound must be >= lower bound")
        return self


class DataQualitySignal(BaseModel):
    """Deterministic contract-check signal used by readiness mapping."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    risk_score: float = Field(ge=0.0, le=1.0)
    hard_failure: bool = False
    violations: list[str] = Field(default_factory=list)
    affected_features: list[str] = Field(default_factory=list)


class ReadinessStateEvent(BaseModel):
    """Registry-facing readiness decision."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["ml.problem_15_7.readiness_state.v1"] = "ml.problem_15_7.readiness_state.v1"
    event_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    readiness_state: ReadinessState
    readiness_score: int = Field(ge=0, le=100)
    primary_reason: str = Field(min_length=1)
    active_signals: list[str] = Field(default_factory=list)
    affected_slices: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    expires_at: AwareDatetime | None = None
    promotion_allowed: bool

    _applicability_projection: DDMApplicabilityProjection | None = PrivateAttr(default=None)

    @property
    def applicability(self) -> DDMApplicabilityProjection | None:
        """Return the in-memory applicability projection for this event."""

        return self._applicability_projection

    def attach_applicability(self, projection: DDMApplicabilityProjection) -> Self:
        """Bind the typed projection without changing the readiness wire shape."""

        self._applicability_projection = projection
        return self


class CalibrationAudit(BaseModel):
    """False-positive certification under a declared stationarity regime."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    calibration_id: str = Field(min_length=1)
    model_id: str | None = Field(default=None, min_length=1)
    model_version: str | None = Field(default=None, min_length=1)
    detector_id: str = Field(min_length=1)
    stationarity_regime_id: str = Field(min_length=1)
    horizon: str = Field(min_length=1)
    alpha: float = Field(gt=0.0, lt=1.0)
    ert: float | None = Field(default=None, gt=0.0)
    empirical_fp_rate: float = Field(ge=0.0, le=1.0)
    empirical_fp_upper_95: float = Field(ge=0.0, le=1.0)
    pass_: bool = Field(alias="pass")
    valid_until: AwareDatetime | None = None
    invalidation_triggers: list[str] = Field(default_factory=list)
    observed_invalidation_triggers: list[str] = Field(default_factory=list)
    validity: ApplicabilityStatus = ApplicabilityStatus.NOT_ESTABLISHED
    validity_reasons: list[str] = Field(default_factory=list)
    validity_checked_at: AwareDatetime | None = None


class RootCauseBundle(BaseModel):
    """Compact bundle for drift/degradation incident localization."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["ml.problem_15_7.root_cause_bundle.v1"] = (
        "ml.problem_15_7.root_cause_bundle.v1"
    )
    event_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    shift_event_ids: list[str] = Field(default_factory=list)
    degradation_event_ids: list[str] = Field(default_factory=list)
    affected_features: list[AffectedFeature] = Field(default_factory=list)
    affected_slices: list[str] = Field(default_factory=list)
    upstream_versions: dict[str, str] = Field(default_factory=dict)
    data_quality_violations: list[str] = Field(default_factory=list)
    stationarity_regime_ids: list[str] = Field(default_factory=list)
    calibration_ids: list[str] = Field(default_factory=list)


class IncidentPayload(BaseModel):
    """Automation payload for tickets, paging, retraining, and rollback hooks."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["ml.problem_15_7.incident_payload.v1"] = (
        "ml.problem_15_7.incident_payload.v1"
    )
    event_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    readiness_event_id: str = Field(min_length=1)
    readiness_state: ReadinessState
    severity: Literal["none", "watch", "investigate", "retrain", "rollback"]
    root_cause_bundle_id: str | None = None
    required_actions: list[str] = Field(default_factory=list)
    attach_event_ids: list[str] = Field(default_factory=list)
    create_ticket: bool = False
    notify_owner: bool = False
    page_owner: bool = False
    trigger_shadow_retrain: bool = False
    freeze_rollout: bool = False
    rollback_or_fallback: bool = False
