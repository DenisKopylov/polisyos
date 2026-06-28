"""Layer 2 S10 outcome-prediction support and welfare-comparison contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from polisyos.pdc import AuthorityBoundary, Layer2ReadinessModel
from polisyos.runtime.quality.design_axes.coupling_composition import (  # noqa: TC001
    ForecastClaimScope,
    ForecastSupportBaseOrigin,
    SystemEffectSupportLabel,
)

LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s10_outcome_prediction.v1"
)
LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION = "policyos.layer2.s10.outcome_prediction.v1"
S10_CALIBRATION_FLOOR_ID = "s10_calibration"

ForecastAuthorityDisposition = Literal[
    "observable_calibrated",
    "transported_limited",
    "historical_prior_context",
    "simulation_only_advisory",
    "equilibrium_contested_blocked",
    "blocked",
]
ForecastMethodFamily = Literal[
    "foundry_causal",
    "foundry_optimization",
    "foundry_bayesian",
    "historical_prior",
    "simulation",
    "abstain",
]
ObservableSubsetCalibrationStatus = Literal[
    "pass",
    "limit",
    "blocked",
    "not_applicable_non_observable",
    "insufficient_history",
]
WelfareComparisonStatus = Literal[
    "value_grounded",
    "value_limited",
    "blocked_missing_value_provenance",
    "blocked_hidden_pareto_tradeoff",
]

S10_FALSE_CLEAR_FIELDS: tuple[str, ...] = (
    "equilibrium_contested_single_forecast_false_clear_count",
    "simulation_only_evidence_laundering_false_clear_count",
    "uncalibrated_observable_promotion_false_clear_count",
    "welfare_without_value_provenance_false_clear_count",
    "fail_closed_axis_prediction_promotion_false_clear_count",
    "regime_forecast_tier_laundering_false_clear_count",
    "transported_estimate_without_limitation_false_clear_count",
    "hidden_uncertainty_interval_false_clear_count",
    "non_observable_claim_as_calibrated_false_clear_count",
    "production_authority_from_forecast_false_clear_count",
    "missing_design_graph_context_false_clear_count",
    "observed_outcome_without_credible_evaluation_false_clear_count",
    "validated_local_model_without_method_validity_false_clear_count",
    "scalar_welfare_hides_pareto_tradeoff_false_clear_count",
    "weakest_boundary_ignored_false_clear_count",
)

_S10_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "preference_learning_authority",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
)
_REQUIRED_AUTHORITY_DENIALS = frozenset(
    {
        "production_recommendation",
        "production_claim_authority",
        "claim_authority",
        "closeout_authority",
        "s11_calibration",
    }
)


class ForecastSupport(Layer2ReadinessModel):
    """Replay-visible S10 support record for a bounded forecast posture."""

    schema_version: str = LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION
    support_id: str = Field(..., min_length=1, max_length=180)
    support_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    source_design_record_ref: str = Field(..., min_length=1, max_length=300)
    design_graph_ref: str = Field(..., min_length=1, max_length=300)
    prediction_context_ref: str = Field(..., min_length=1, max_length=300)
    policy_context_ref: str = Field(..., min_length=1, max_length=300)
    candidate_design_ref: str = Field(..., min_length=1, max_length=300)
    baseline_design_ref: str = Field(..., min_length=1, max_length=300)
    alternative_design_refs: list[str] = Field(default_factory=list, max_length=80)
    prediction_horizon_ref: str = Field(..., min_length=1, max_length=300)
    target_outcome_refs: list[str] = Field(..., min_length=1, max_length=80)
    jurisdiction_scope_ref: str = Field(..., min_length=1, max_length=300)
    s5_forecast_support_ref: str = Field(..., min_length=1, max_length=300)
    s5_support_label: SystemEffectSupportLabel
    s5_base_origin: ForecastSupportBaseOrigin
    s5_claim_scope: ForecastClaimScope
    s6_firewall_status_refs: list[str] = Field(..., min_length=1, max_length=80)
    s6_limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    s8_value_choice_provenance_ref: str = Field(..., min_length=1, max_length=300)
    s8_value_tradeoff_disclosure_ref: str = Field(..., min_length=1, max_length=300)
    source_contract_ref: str | None = Field(default=None, max_length=300)
    method_validity_ref: str | None = Field(default=None, max_length=300)
    credible_evaluation_evidence_ref: str | None = Field(default=None, max_length=300)
    source_lineage_refs: list[str] = Field(default_factory=list, max_length=80)
    method_lineage_refs: list[str] = Field(default_factory=list, max_length=80)
    sensitivity_analysis_ref: str | None = Field(default=None, max_length=300)
    dynamic_equilibrium_check_ref: str | None = Field(default=None, max_length=300)
    equilibrium_caveat_refs: list[str] = Field(default_factory=list, max_length=80)
    strategic_response_caveat_refs: list[str] = Field(default_factory=list, max_length=80)
    outcome_distribution_refs: list[str] = Field(default_factory=list, max_length=80)
    welfare_comparison_ref: str | None = Field(default=None, max_length=300)
    forecast_tier: ForecastAuthorityDisposition
    forecast_authority_disposition_reason: str = Field(..., min_length=1, max_length=800)
    method_family: ForecastMethodFamily
    observable_subset_ref: str | None = Field(default=None, max_length=300)
    calibration_record_ref: str | None = Field(default=None, max_length=300)
    uncertainty_interval_refs: list[str] = Field(default_factory=list, max_length=80)
    limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    abstention_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S10_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION

    @model_validator(mode="after")
    def _validate_support_boundary(self) -> ForecastSupport:
        _assert_required_denials(self.may_not_use_for)
        if self.forecast_tier == "observable_calibrated" and (
            not self.observable_subset_ref or not self.calibration_record_ref
        ):
            raise ValueError("observable calibration requires observable calibration refs")
        if self.forecast_tier in {"observable_calibrated", "transported_limited"} and (
            not self.uncertainty_interval_refs
        ):
            raise ValueError("uncertainty interval refs are required for governed forecast tiers")
        if self.s5_base_origin == "simulation_only" and self.forecast_tier != (
            "simulation_only_advisory"
        ):
            raise ValueError("simulation_only support can only be simulation_only_advisory")
        if self.s5_base_origin == "historical_prior" and self.forecast_tier != (
            "historical_prior_context"
        ):
            raise ValueError("historical prior support remains context only")
        if self.s5_base_origin == "transported_scholar_estimate" and not self.limitation_refs:
            raise ValueError("transported estimate requires transport limitation refs")
        return self


class ForecastCalibrationRecord(Layer2ReadinessModel):
    """Observable-subset calibration record for S10 forecast support."""

    schema_version: str = LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION
    calibration_id: str = Field(..., min_length=1, max_length=180)
    calibration_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    forecast_support_ref: str = Field(..., min_length=1, max_length=300)
    observable_subset_ref: str = Field(..., min_length=1, max_length=300)
    prediction_ref: str = Field(..., min_length=1, max_length=300)
    observed_outcome_ref: str = Field(..., min_length=1, max_length=300)
    historical_implementation_ref: str = Field(..., min_length=1, max_length=300)
    evaluation_design_ref: str = Field(..., min_length=1, max_length=300)
    credible_evaluation_evidence_ref: str = Field(..., min_length=1, max_length=300)
    counterfactual_credibility: str = Field(..., min_length=1, max_length=200)
    prediction_time: AwareDatetime
    observation_time: AwareDatetime
    policy_effective_time: AwareDatetime
    data_valid_time: AwareDatetime
    calibration_window_start: AwareDatetime
    calibration_window_end: AwareDatetime
    metric_name: Literal["observable_subset_calibration"] = "observable_subset_calibration"
    denominator: int = Field(..., ge=0)
    numerator: int = Field(..., ge=0)
    pass_rate: float = Field(..., ge=0.0, le=1.0)
    calibration_threshold_ref: str = Field(..., min_length=1, max_length=300)
    floor_passed: bool
    calibration_status: ObservableSubsetCalibrationStatus
    interval_coverage_metric: float | None = Field(default=None, ge=0.0, le=1.0)
    calibration_error_metric: float | None = Field(default=None, ge=0.0)
    source_lineage_refs: list[str] = Field(default_factory=list, max_length=80)
    method_lineage_refs: list[str] = Field(default_factory=list, max_length=80)
    floor_id: Literal["s10_calibration"] = S10_CALIBRATION_FLOOR_ID
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S10_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION

    @model_validator(mode="after")
    def _validate_calibration(self) -> ForecastCalibrationRecord:
        _assert_required_denials(self.may_not_use_for)
        if self.numerator > self.denominator:
            raise ValueError("calibration numerator cannot exceed denominator")
        if self.denominator == 0 and self.calibration_status == "pass":
            raise ValueError("passing calibration requires observable subset denominator")
        if self.denominator:
            expected = self.numerator / self.denominator
            if abs(self.pass_rate - expected) > 0.000001:
                raise ValueError("calibration pass_rate must equal numerator / denominator")
        if self.calibration_status == "pass" and (
            not self.floor_passed or not self.calibration_threshold_ref
        ):
            raise ValueError("passing observable calibration requires governed floor threshold")
        if self.calibration_window_end < self.calibration_window_start:
            raise ValueError("calibration window end cannot precede start")
        return self


class OutcomeDistributionRecord(Layer2ReadinessModel):
    """Forecast outcome distribution row with visible uncertainty semantics."""

    schema_version: str = LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION
    distribution_id: str = Field(..., min_length=1, max_length=180)
    distribution_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    forecast_support_ref: str = Field(..., min_length=1, max_length=300)
    design_graph_ref: str = Field(..., min_length=1, max_length=300)
    prediction_context_ref: str = Field(..., min_length=1, max_length=300)
    policy_context_ref: str = Field(..., min_length=1, max_length=300)
    candidate_design_ref: str = Field(..., min_length=1, max_length=300)
    baseline_design_ref: str = Field(..., min_length=1, max_length=300)
    alternative_design_refs: list[str] = Field(default_factory=list, max_length=80)
    target_outcome_ref: str = Field(..., min_length=1, max_length=300)
    outcome_unit_ref: str = Field(..., min_length=1, max_length=300)
    prediction_horizon_ref: str = Field(..., min_length=1, max_length=300)
    jurisdiction_scope_ref: str = Field(..., min_length=1, max_length=300)
    method_family: ForecastMethodFamily
    source_contract_ref: str | None = Field(default=None, max_length=300)
    method_validity_ref: str | None = Field(default=None, max_length=300)
    point_estimate_ref: str | None = Field(default=None, max_length=300)
    uncertainty_interval_ref: str | None = Field(default=None, max_length=300)
    interval_lower_ref: str | None = Field(default=None, max_length=300)
    interval_upper_ref: str | None = Field(default=None, max_length=300)
    distribution_shape: str = Field(..., min_length=1, max_length=200)
    forecast_tier: ForecastAuthorityDisposition
    s5_support_label: SystemEffectSupportLabel
    non_observable_downgrade_reason: str | None = Field(default=None, max_length=500)
    limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    rule_version_ref: str = LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION

    @model_validator(mode="after")
    def _validate_visible_uncertainty(self) -> OutcomeDistributionRecord:
        if not (
            self.uncertainty_interval_ref and self.interval_lower_ref and self.interval_upper_ref
        ):
            raise ValueError("uncertainty interval lower and upper refs must be visible")
        if self.forecast_tier != "observable_calibrated" and not self.limitation_refs:
            raise ValueError("limited or advisory distributions require limitation refs")
        return self


class WelfareComparisonRecord(Layer2ReadinessModel):
    """S10 welfare comparison grounded in S8 value provenance."""

    schema_version: str = LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION
    comparison_id: str = Field(..., min_length=1, max_length=180)
    comparison_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    forecast_support_ref: str = Field(..., min_length=1, max_length=300)
    candidate_design_ref: str = Field(..., min_length=1, max_length=300)
    baseline_design_ref: str = Field(..., min_length=1, max_length=300)
    alternative_design_refs: list[str] = Field(default_factory=list, max_length=80)
    outcome_distribution_refs: list[str] = Field(..., min_length=1, max_length=80)
    s8_value_choice_provenance_ref: str = Field(..., min_length=1, max_length=300)
    s8_value_tradeoff_disclosure_ref: str = Field(..., min_length=1, max_length=300)
    pareto_archive_ref: str | None = Field(default=None, max_length=300)
    authorized_value_schedule_ref: str | None = Field(default=None, max_length=300)
    social_weight_provenance_refs: list[str] = Field(default_factory=list, max_length=80)
    principal_refs: list[str] = Field(default_factory=list, max_length=80)
    conflict_refs: list[str] = Field(default_factory=list, max_length=80)
    blocking_rights_refs: list[str] = Field(default_factory=list, max_length=80)
    welfare_comparison_status: WelfareComparisonStatus
    ranking_mode: str = Field(..., min_length=1, max_length=160)
    scalar_summary_allowed: bool = False
    scalar_welfare_summary_ref: str | None = Field(default=None, max_length=300)
    pareto_frontier_ref: str | None = Field(default=None, max_length=300)
    rejected_nondominated_alternative_refs: list[str] = Field(
        default_factory=list,
        max_length=80,
    )
    limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S10_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION

    @model_validator(mode="after")
    def _validate_welfare_grounding(self) -> WelfareComparisonRecord:
        _assert_required_denials(self.may_not_use_for)
        if self.scalar_summary_allowed and (
            not self.pareto_frontier_ref or not self.rejected_nondominated_alternative_refs
        ):
            raise ValueError("Pareto tradeoff cannot be hidden by a scalar welfare summary")
        if self.welfare_comparison_status == "value_grounded" and (
            not self.pareto_archive_ref or not self.authorized_value_schedule_ref
        ):
            raise ValueError("value-grounded welfare comparison requires S8 value artifacts")
        return self


class PredictionAuthorityEnvelope(Layer2ReadinessModel):
    """Authority envelope showing S10 forecast support is not recommendation authority."""

    schema_version: str = LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION
    envelope_id: str = Field(..., min_length=1, max_length=180)
    envelope_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    forecast_support_ref: str = Field(..., min_length=1, max_length=300)
    forecast_tier: ForecastAuthorityDisposition
    forecast_authority_disposition_reason: str = Field(..., min_length=1, max_length=800)
    weakest_boundary_source: str = Field(..., min_length=1, max_length=200)
    legal_boundary_ref: str | None = Field(default=None, max_length=300)
    data_boundary_ref: str | None = Field(default=None, max_length=300)
    method_boundary_ref: str | None = Field(default=None, max_length=300)
    participation_boundary_ref: str | None = Field(default=None, max_length=300)
    epistemic_regime_boundary_ref: str | None = Field(default=None, max_length=300)
    coupling_boundary_ref: str | None = Field(default=None, max_length=300)
    prediction_boundary_ref: str = Field(..., min_length=1, max_length=300)
    welfare_value_choice_boundary_ref: str | None = Field(default=None, max_length=300)
    state_capacity_boundary_ref: str | None = Field(default=None, max_length=300)
    reversibility_stakes_boundary_ref: str | None = Field(default=None, max_length=300)
    strategic_response_boundary_ref: str | None = Field(default=None, max_length=300)
    calibration_status: ObservableSubsetCalibrationStatus
    observable_subset_ref: str | None = Field(default=None, max_length=300)
    calibration_record_ref: str | None = Field(default=None, max_length=300)
    source_contract_ref: str | None = Field(default=None, max_length=300)
    method_validity_ref: str | None = Field(default=None, max_length=300)
    credible_evaluation_evidence_ref: str | None = Field(default=None, max_length=300)
    denies_production_authority: bool
    denies_recommendation_authority: bool
    denies_claim_authority: bool
    denies_closeout_authority: bool
    denies_s11_authority: bool
    issue_codes: list[str] = Field(default_factory=list, max_length=80)
    envelope_status: str = Field(..., min_length=1, max_length=120)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S10_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION


class ForecastSupportIntegrityReport(Layer2ReadinessModel):
    """S10 integrity summary for forecast-support and calibration rows."""

    schema_version: str = LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION
    report_id: str = Field(..., min_length=1, max_length=180)
    report_ref: str = Field(..., min_length=1, max_length=300)
    case_count: int = Field(..., ge=0)
    forecast_support_refs: list[str] = Field(default_factory=list, max_length=500)
    forecast_calibration_record_refs: list[str] = Field(default_factory=list, max_length=500)
    observable_subset_calibration_denominator: int = Field(..., ge=0)
    observable_subset_calibration_numerator: int = Field(..., ge=0)
    observable_subset_calibration_pass_rate: float = Field(..., ge=0.0, le=1.0)
    observable_subset_calibration_status: ObservableSubsetCalibrationStatus
    observable_subset_calibration_threshold_ref: str | None = Field(default=None, max_length=300)
    observable_subset_calibration_floor_passed: bool
    non_observable_downgrade_count: int = Field(..., ge=0)
    equilibrium_contested_single_forecast_block_count: int = Field(..., ge=0)
    simulation_only_evidence_block_count: int = Field(..., ge=0)
    weakest_boundary_inheritance_count: int = Field(..., ge=0)
    false_clear_counts: dict[str, int] = Field(default_factory=dict)
    issue_codes: list[str] = Field(default_factory=list, max_length=100)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S10_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION

    @model_validator(mode="after")
    def _validate_false_clear_keys(self) -> ForecastSupportIntegrityReport:
        if set(self.false_clear_counts) != set(S10_FALSE_CLEAR_FIELDS):
            raise ValueError("false_clear_counts keys must exactly match S10_FALSE_CLEAR_FIELDS")
        if self.observable_subset_calibration_numerator > (
            self.observable_subset_calibration_denominator
        ):
            raise ValueError("calibration numerator cannot exceed denominator")
        _assert_required_denials(self.may_not_use_for)
        return self


def build_prediction_authority_boundary(
    *,
    authoritative_for: Sequence[str] = (
        "forecast_support_tiering",
        "observable_subset_calibration",
        "value_grounded_welfare_comparison",
    ),
    may_not_use_for: Sequence[str] = _S10_MAY_NOT_USE_FOR,
    posture: Literal["shadow", "advisory", "governed"] = "shadow",
    rule_version_ref: str = LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION,
) -> AuthorityBoundary:
    """Build the purpose-scoped S10 prediction authority boundary."""

    denials = _merge_denials(may_not_use_for)
    return AuthorityBoundary(
        authoritative_for=[str(item) for item in authoritative_for],
        may_not_use_for=denials,
        source_authority="deterministic_producer",
        posture=posture,
        rule_version_refs=[rule_version_ref],
    )


def build_forecast_calibration_record(**payload: object) -> ForecastCalibrationRecord:
    """Build an observable-subset calibration record or fail closed."""

    if not payload.get("credible_evaluation_evidence_ref") or not payload.get(
        "counterfactual_credibility"
    ):
        raise ValueError("credible_evaluation and counterfactual evidence are required")
    payload = _with_boundary_defaults(payload, authoritative_for=["observable_subset_calibration"])
    if "pass_rate" not in payload and payload.get("denominator"):
        payload["pass_rate"] = int(payload["numerator"]) / int(payload["denominator"])
    return ForecastCalibrationRecord.model_validate(payload)


def build_forecast_support(**payload: object) -> ForecastSupport:
    """Build an S10 forecast-support record from S5/S6/S8 support refs."""

    _require_forecast_support_inputs(payload)
    tier = _derive_forecast_tier(payload)
    payload["forecast_tier"] = tier
    if tier == "observable_calibrated":
        _require_observable_calibration(payload)
    if tier == "equilibrium_contested_blocked":
        _validate_equilibrium_block(payload)
    if payload.get("s5_base_origin") == "validated_local_model":
        _require_validated_local_model_refs(payload)
    if payload.get("s5_base_origin") == "transported_scholar_estimate" and not _sequence(
        payload.get("limitation_refs")
    ):
        raise ValueError("transported estimate requires transport limitation refs")
    if payload.get("s5_claim_scope") == "system_effect":
        _apply_system_effect_requirements(payload)
    payload = _with_boundary_defaults(payload, authoritative_for=["forecast_support_tiering"])
    return ForecastSupport.model_validate(payload)


def build_welfare_comparison_record(**payload: object) -> WelfareComparisonRecord:
    """Build an S10 welfare-comparison record grounded in S8 value provenance."""

    if not payload.get("s8_value_choice_provenance_ref") or not payload.get(
        "s8_value_tradeoff_disclosure_ref"
    ):
        raise ValueError("S8 value provenance and tradeoff disclosure are required")
    if payload.get("scalar_summary_allowed") and (
        not payload.get("pareto_frontier_ref")
        or not _sequence(payload.get("rejected_nondominated_alternative_refs"))
    ):
        raise ValueError("Pareto tradeoff cannot be hidden by a scalar welfare summary")
    payload = _with_boundary_defaults(
        payload,
        authoritative_for=["value_grounded_welfare_comparison"],
    )
    return WelfareComparisonRecord.model_validate(payload)


def verify_prediction_authority_envelope(
    *,
    forecast_support: ForecastSupport | Mapping[str, object],
    calibration_record: ForecastCalibrationRecord | Mapping[str, object] | None = None,
    weakest_boundary_source: str = "prediction_boundary",
    legal_boundary_ref: str | None = None,
    data_boundary_ref: str | None = None,
    method_boundary_ref: str | None = None,
    participation_boundary_ref: str | None = None,
    epistemic_regime_boundary_ref: str | None = None,
    coupling_boundary_ref: str | None = None,
    welfare_value_choice_boundary_ref: str | None = None,
    state_capacity_boundary_ref: str | None = None,
    reversibility_stakes_boundary_ref: str | None = None,
    strategic_response_boundary_ref: str | None = None,
) -> PredictionAuthorityEnvelope:
    """Verify that S10 support remains bounded forecast support."""

    support = _as_forecast_support(forecast_support)
    calibration = _as_calibration_record(calibration_record)
    may_not_use_for = _merge_denials(support.may_not_use_for)
    issues = _prediction_issue_codes(support, calibration)
    calibration_status: ObservableSubsetCalibrationStatus = (
        calibration.calibration_status
        if calibration is not None
        else (
            "not_applicable_non_observable"
            if support.forecast_tier != "observable_calibrated"
            else "blocked"
        )
    )
    return PredictionAuthorityEnvelope(
        envelope_id=f"layer2.s10.prediction_envelope.{_stable_token(support.support_ref)}",
        envelope_ref=f"{support.support_ref}/authority-envelope",
        case_id=support.case_id,
        forecast_support_ref=support.support_ref,
        forecast_tier=support.forecast_tier,
        forecast_authority_disposition_reason=support.forecast_authority_disposition_reason,
        weakest_boundary_source=weakest_boundary_source,
        legal_boundary_ref=legal_boundary_ref,
        data_boundary_ref=data_boundary_ref,
        method_boundary_ref=method_boundary_ref or support.method_validity_ref,
        participation_boundary_ref=participation_boundary_ref,
        epistemic_regime_boundary_ref=epistemic_regime_boundary_ref,
        coupling_boundary_ref=coupling_boundary_ref or support.s5_forecast_support_ref,
        prediction_boundary_ref=support.support_ref,
        welfare_value_choice_boundary_ref=(
            welfare_value_choice_boundary_ref or support.s8_value_choice_provenance_ref
        ),
        state_capacity_boundary_ref=state_capacity_boundary_ref,
        reversibility_stakes_boundary_ref=reversibility_stakes_boundary_ref,
        strategic_response_boundary_ref=(
            strategic_response_boundary_ref
            or _first_or_none(support.strategic_response_caveat_refs)
        ),
        calibration_status=calibration_status,
        observable_subset_ref=support.observable_subset_ref,
        calibration_record_ref=support.calibration_record_ref,
        source_contract_ref=support.source_contract_ref,
        method_validity_ref=support.method_validity_ref,
        credible_evaluation_evidence_ref=(
            support.credible_evaluation_evidence_ref
            or (calibration.credible_evaluation_evidence_ref if calibration else None)
        ),
        denies_production_authority="production_claim_authority" in may_not_use_for,
        denies_recommendation_authority="production_recommendation" in may_not_use_for,
        denies_claim_authority="claim_authority" in may_not_use_for,
        denies_closeout_authority="closeout_authority" in may_not_use_for,
        denies_s11_authority="s11_calibration" in may_not_use_for,
        issue_codes=issues,
        envelope_status="blocked" if issues else "pass",
        authority_boundary=support.authority_boundary,
        may_not_use_for=may_not_use_for,
        rule_version_ref=support.rule_version_ref,
    )


def summarize_forecast_support_integrity(
    *,
    forecast_supports: Sequence[ForecastSupport | Mapping[str, object]],
    calibration_records: Sequence[ForecastCalibrationRecord | Mapping[str, object]] = (),
    report_id: str = "layer2.s10.forecast_support.integrity",
    report_ref: str = "pdc://layer2/s10/forecast-support-integrity",
    threshold_ref: str | None = None,
    rule_version_ref: str = LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION,
) -> ForecastSupportIntegrityReport:
    """Summarize S10 support rows and negative-control counters."""

    supports = [_as_forecast_support(item) for item in forecast_supports]
    calibrations = [_as_calibration_record(item) for item in calibration_records]
    denominator = sum(record.denominator for record in calibrations)
    numerator = sum(record.numerator for record in calibrations)
    pass_rate = numerator / denominator if denominator else 0.0
    non_observable = sum(
        support.forecast_tier
        in {
            "transported_limited",
            "historical_prior_context",
            "simulation_only_advisory",
            "equilibrium_contested_blocked",
            "blocked",
        }
        for support in supports
    )
    equilibrium_blocks = sum(
        support.forecast_tier == "equilibrium_contested_blocked" for support in supports
    )
    simulation_blocks = sum(
        support.forecast_tier == "simulation_only_advisory" for support in supports
    )
    status: ObservableSubsetCalibrationStatus = (
        "pass" if denominator and numerator == denominator else "limit"
    )
    floor_passed = bool(denominator and numerator == denominator)
    return ForecastSupportIntegrityReport(
        report_id=report_id,
        report_ref=report_ref,
        case_count=len(supports),
        forecast_support_refs=[support.support_ref for support in supports],
        forecast_calibration_record_refs=[record.calibration_ref for record in calibrations],
        observable_subset_calibration_denominator=denominator,
        observable_subset_calibration_numerator=numerator,
        observable_subset_calibration_pass_rate=pass_rate,
        observable_subset_calibration_status=status,
        observable_subset_calibration_threshold_ref=threshold_ref,
        observable_subset_calibration_floor_passed=floor_passed,
        non_observable_downgrade_count=non_observable,
        equilibrium_contested_single_forecast_block_count=equilibrium_blocks,
        simulation_only_evidence_block_count=simulation_blocks,
        weakest_boundary_inheritance_count=len(supports),
        false_clear_counts=dict.fromkeys(S10_FALSE_CLEAR_FIELDS, 0),
        issue_codes=[],
        authority_boundary=build_prediction_authority_boundary(
            authoritative_for=["forecast_support_integrity"],
            posture="shadow",
            rule_version_ref=rule_version_ref,
        ),
        may_not_use_for=list(_S10_MAY_NOT_USE_FOR),
        rule_version_ref=rule_version_ref,
    )


def _require_forecast_support_inputs(payload: Mapping[str, object]) -> None:
    if not payload.get("s5_forecast_support_ref"):
        raise ValueError("S5 forecast authority input is required")
    if not _sequence(payload.get("s6_firewall_status_refs")):
        raise ValueError("S6 firewall authority inputs are required")
    if not payload.get("s8_value_choice_provenance_ref"):
        raise ValueError("S8 value authority provenance is required")
    if not payload.get("design_graph_ref") or not payload.get("prediction_context_ref"):
        raise ValueError("design_graph and prediction_context refs are required")


def _require_observable_calibration(payload: Mapping[str, object]) -> None:
    if not payload.get("observable_subset_ref") or not payload.get("calibration_record_ref"):
        raise ValueError("observable calibration requires calibration and observable refs")


def _require_validated_local_model_refs(payload: dict[str, object]) -> None:
    if not payload.get("source_contract_ref") or not payload.get("method_validity_ref"):
        raise ValueError("source_contract and method_validity refs are required")
    if not payload.get("sensitivity_analysis_ref") or not payload.get("calibration_record_ref"):
        raise ValueError("validated local model requires sensitivity and calibration refs")
    if "source_lineage_refs" in payload and not _sequence(payload.get("source_lineage_refs")):
        raise ValueError("validated local model requires source lineage refs")
    if "method_lineage_refs" in payload and not _sequence(payload.get("method_lineage_refs")):
        raise ValueError("validated local model requires method lineage refs")
    payload.setdefault("source_lineage_refs", [str(payload["source_contract_ref"])])
    payload.setdefault("method_lineage_refs", [str(payload["method_validity_ref"])])


def _apply_system_effect_requirements(payload: dict[str, object]) -> None:
    if payload.get("dynamic_equilibrium_check_ref") or _sequence(
        payload.get("equilibrium_caveat_refs")
    ):
        return
    if payload.get("s5_base_origin") == "equilibrium_contested":
        payload["forecast_tier"] = "equilibrium_contested_blocked"
        return
    payload["forecast_tier"] = "simulation_only_advisory"


def _derive_forecast_tier(payload: Mapping[str, object]) -> ForecastAuthorityDisposition:
    base_origin = str(payload.get("s5_base_origin", ""))
    support_label = str(payload.get("s5_support_label", ""))
    if base_origin == "equilibrium_contested" or support_label == "equilibrium_contested":
        return "equilibrium_contested_blocked"
    if base_origin == "simulation_only" or support_label == "simulation_only_system_effect":
        return "simulation_only_advisory"
    if (
        base_origin == "transported_scholar_estimate"
        or support_label == "transported_with_heavy_limitation"
    ):
        return "transported_limited"
    if base_origin == "historical_prior" or support_label == "historical_prior_system_context":
        return "historical_prior_context"
    if _sequence(payload.get("s6_limitation_refs")) and _has_fail_closed_ref(
        payload.get("s6_limitation_refs")
    ):
        return "blocked"
    return "observable_calibrated"


def _validate_equilibrium_block(payload: Mapping[str, object]) -> None:
    if not _sequence(payload.get("uncertainty_interval_refs")):
        raise ValueError("equilibrium contested system effect cannot emit single point forecast")
    if len(_sequence(payload.get("outcome_distribution_refs"))) == 1 and (
        "single-point" in str(_sequence(payload.get("outcome_distribution_refs"))[0])
    ):
        raise ValueError("equilibrium contested system effect cannot emit single point forecast")


def _prediction_issue_codes(
    support: ForecastSupport,
    calibration: ForecastCalibrationRecord | None,
) -> list[str]:
    issues: list[str] = []
    if support.forecast_tier == "simulation_only_advisory":
        issues.append("s10_simulation_only_laundered_as_evidence")
    if support.forecast_tier == "equilibrium_contested_blocked":
        issues.append("s10_equilibrium_contested_single_forecast")
    if support.forecast_tier == "observable_calibrated" and (
        calibration is not None and calibration.calibration_status != "pass"
    ):
        issues.append("s10_uncalibrated_observable_promotion")
    if not set(support.may_not_use_for) >= _REQUIRED_AUTHORITY_DENIALS:
        issues.append("s10_prediction_authority_laundering")
    return issues


def _with_boundary_defaults(
    payload: Mapping[str, object],
    *,
    authoritative_for: Sequence[str],
) -> dict[str, object]:
    prepared = dict(payload)
    prepared["may_not_use_for"] = _merge_denials(_sequence(prepared.get("may_not_use_for")))
    if not prepared.get("authority_boundary"):
        prepared["authority_boundary"] = build_prediction_authority_boundary(
            authoritative_for=authoritative_for,
            may_not_use_for=prepared["may_not_use_for"],
        )
    return prepared


def _assert_required_denials(may_not_use_for: Sequence[str]) -> None:
    missing = _REQUIRED_AUTHORITY_DENIALS - set(may_not_use_for)
    if missing:
        raise ValueError(f"S10 authority boundary missing denials: {sorted(missing)}")


def _merge_denials(values: Sequence[object]) -> list[str]:
    merged = [str(item) for item in values if str(item)]
    for item in _S10_MAY_NOT_USE_FOR:
        if item not in merged:
            merged.append(item)
    return merged


def _as_forecast_support(value: ForecastSupport | Mapping[str, object]) -> ForecastSupport:
    if isinstance(value, ForecastSupport):
        return value
    return ForecastSupport.model_validate(value)


def _as_calibration_record(
    value: ForecastCalibrationRecord | Mapping[str, object] | None,
) -> ForecastCalibrationRecord | None:
    if value is None:
        return None
    if isinstance(value, ForecastCalibrationRecord):
        return value
    return ForecastCalibrationRecord.model_validate(value)


def _sequence(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return list(value)
    return []


def _first_or_none(values: Sequence[str]) -> str | None:
    return values[0] if values else None


def _has_fail_closed_ref(values: object) -> bool:
    rendered = " ".join(str(item).lower() for item in _sequence(values))
    return "block" in rendered or "fail" in rendered


def _stable_token(value: str) -> str:
    return (
        value.replace("pdc://", "")
        .replace("://", "-")
        .replace("/", "-")
        .replace(".", "-")[:96]
    )


__all__ = [
    "LAYER2_S10_OUTCOME_PREDICTION_RULE_VERSION",
    "LAYER2_S10_OUTCOME_PREDICTION_SCHEMA_VERSION",
    "S10_CALIBRATION_FLOOR_ID",
    "S10_FALSE_CLEAR_FIELDS",
    "ForecastAuthorityDisposition",
    "ForecastCalibrationRecord",
    "ForecastMethodFamily",
    "ForecastSupport",
    "ForecastSupportIntegrityReport",
    "ObservableSubsetCalibrationStatus",
    "OutcomeDistributionRecord",
    "PredictionAuthorityEnvelope",
    "WelfareComparisonRecord",
    "WelfareComparisonStatus",
    "build_forecast_calibration_record",
    "build_forecast_support",
    "build_prediction_authority_boundary",
    "build_welfare_comparison_record",
    "summarize_forecast_support_integrity",
    "verify_prediction_authority_envelope",
]
