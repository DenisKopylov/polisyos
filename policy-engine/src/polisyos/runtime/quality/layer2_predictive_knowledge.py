"""Layer 2 S11 predictive-knowledge contracts and authority verifier."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from polisyos.pdc import AuthorityBoundary, Layer2ReadinessModel
from polisyos.runtime.quality.ir_analytics_bridge import build_ir_analytics_claim_bridge

LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s11_predictive_knowledge.v1"
)
LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION = (
    "policyos.layer2.s11.predictive_knowledge.v1"
)
S11_AXIS_CALIBRATION_FLOOR_ID = "s11_axis_calibration"
S11_PREDICTIVE_AXES: tuple[str, ...] = (
    "strategic_response",
    "state_capacity_feasibility",
    "measurability",
    "subject_granularity",
)
S11_FALSE_CLEAR_FIELDS: tuple[str, ...] = (
    "stale_calibration_relaxation",
    "scope_mismatched_historical_prior",
    "unbound_ir_analytics",
    "negative_certificate_ignored",
    "missing_method_validity",
    "missing_s6_floor_ref",
    "mandate_axis_predictive_upgrade",
    "production_authority_from_predictive_upgrade",
    "rich_simulation_authority_laundering",
    "weakest_boundary_bypass",
)

PredictiveAxis = Literal[
    "strategic_response",
    "state_capacity_feasibility",
    "measurability",
    "subject_granularity",
    "mandate_legitimacy",
]
PredictiveMaturity = Literal["fail_closed", "predictive"]
RelaxationDecision = Literal["relaxed_to_predictive", "reverted_fail_closed"]
S11CalibrationStatus = Literal["pass", "limit", "blocked", "stale", "out_of_scope"]
ForecastQualityDisposition = Literal[
    "unchanged_s10_tier_consumed",
    "downgraded_by_s11_calibration",
    "proof_blocked",
]
ProofStatus = Literal[
    "identified",
    "bounded",
    "partial",
    "limited",
    "contested",
    "not_identified",
    "blocked",
    "negative",
    "refuted",
    "failed",
]
ProofComposabilityStatus = Literal["reusable", "revalidate", "unknown", "rederive"]

_S11_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "production_authority",
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "calibrated_equilibrium_prediction",
    "rich_simulation_authority",
    "portfolio_optimization_authority",
    "preference_learning_authority",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
    "mandate_legitimacy_predictive_upgrade",
    "historical_prior_current_evidence",
    "llm_method_authority",
)
_REQUIRED_AUTHORITY_DENIALS = frozenset(
    {
        "production_authority",
        "production_recommendation",
        "production_claim_authority",
        "claim_authority",
        "rich_simulation_authority",
        "mandate_legitimacy_predictive_upgrade",
    }
)
_BLOCKING_PROOF_STATUSES = frozenset(
    {"blocked", "negative", "not_identified", "refuted", "failed"}
)
_BLOCKING_COMPOSABILITY_STATUSES = frozenset({"rederive"})
_CURRENT_CONTEXT_MARKERS = ("current", "ua-msme", "2022")
_CAPACITY_GROUNDING_MARKERS = frozenset(
    {
        "administrative",
        "fiscal",
        "enforcement",
        "delivery",
        "coordination",
        "political_feasibility",
        "political-feasibility",
    }
)
_STRATEGIC_CHANNEL_MARKERS = frozenset(
    {
        "goodhart",
        "lucas",
        "performativity",
        "capture",
        "gaming",
        "adaptation",
        "compliance_response",
        "compliance-response",
    }
)


class PredictiveAxisCalibrationRecord(Layer2ReadinessModel):
    """Per-axis S11 calibration record for governed predictive relaxation."""

    schema_version: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION
    calibration_id: str = Field(..., min_length=1, max_length=180)
    calibration_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    axis: PredictiveAxis
    cell_ref: str = Field(..., min_length=3, max_length=200)
    s6_floor_record_ref: str = Field(..., min_length=1, max_length=300)
    s10_forecast_support_ref: str = Field(..., min_length=1, max_length=300)
    s10_forecast_calibration_record_ref: str | None = Field(default=None, max_length=300)
    calibration_ledger_ref: str = Field(..., min_length=1, max_length=300)
    calibration_scope_ref: str = Field(..., min_length=1, max_length=300)
    prediction_context_ref: str = Field(..., min_length=1, max_length=300)
    policy_context_ref: str = Field(..., min_length=1, max_length=300)
    model_family: str = Field(..., min_length=1, max_length=160)
    source_contract_ref: str = Field(..., min_length=1, max_length=300)
    method_validity_ref: str = Field(..., min_length=1, max_length=300)
    method_infrastructure_refs: list[str] = Field(default_factory=list, max_length=80)
    source_lineage_refs: list[str] = Field(default_factory=list, max_length=80)
    method_lineage_refs: list[str] = Field(default_factory=list, max_length=80)
    effective_independence_refs: list[str] = Field(default_factory=list, max_length=80)
    sensitivity_analysis_ref: str = Field(..., min_length=1, max_length=300)
    credible_evaluation_evidence_ref: str | None = Field(default=None, max_length=300)
    counterfactual_credibility_ref: str | None = Field(default=None, max_length=300)
    prediction_time: AwareDatetime
    observation_time: AwareDatetime
    policy_effective_time: AwareDatetime
    data_valid_time: AwareDatetime
    calibration_window_start: AwareDatetime
    calibration_window_end: AwareDatetime
    denominator: int = Field(..., ge=0)
    numerator: int = Field(..., ge=0)
    pass_rate: float = Field(..., ge=0.0, le=1.0)
    threshold: float = Field(..., ge=0.0, le=1.0)
    threshold_ref: str = Field(..., min_length=1, max_length=300)
    floor_id: Literal["s11_axis_calibration"] = S11_AXIS_CALIBRATION_FLOOR_ID
    floor_passed: bool
    calibration_status: S11CalibrationStatus
    residual_limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S11_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_calibration_record(self) -> PredictiveAxisCalibrationRecord:
        _assert_required_denials(self.may_not_use_for)
        if self.numerator > self.denominator:
            raise ValueError("calibration numerator cannot exceed denominator")
        if self.denominator == 0 and self.calibration_status == "pass":
            raise ValueError("passing calibration requires denominator")
        if self.denominator:
            expected = self.numerator / self.denominator
            if abs(self.pass_rate - expected) > 0.000001:
                raise ValueError("pass_rate must equal numerator / denominator")
        if self.calibration_status == "pass" and (
            not self.floor_passed or self.pass_rate < self.threshold
        ):
            raise ValueError("passing S11 calibration requires governed floor pass")
        if self.calibration_window_end < self.calibration_window_start:
            raise ValueError("calibration window end cannot precede start")
        _validate_current_context(self)
        return self


class PredictiveAxisUpgradeRecord(Layer2ReadinessModel):
    """S11 overlay record deciding whether one S6 axis can relax to predictive."""

    schema_version: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION
    upgrade_id: str = Field(..., min_length=1, max_length=180)
    upgrade_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    axis: PredictiveAxis
    cell_ref: str = Field(..., min_length=3, max_length=200)
    from_maturity: Literal["fail_closed"] = "fail_closed"
    target_maturity: Literal["predictive"] = "predictive"
    effective_maturity: PredictiveMaturity
    relaxation_decision: RelaxationDecision
    s6_floor_record_ref: str = Field(..., min_length=1, max_length=300)
    s6_floor_disposition: str = Field(..., min_length=1, max_length=120)
    s10_forecast_support_ref: str = Field(..., min_length=1, max_length=300)
    predictive_model_ref: str | None = Field(default=None, max_length=300)
    axis_model_evidence_refs: list[str] = Field(default_factory=list, max_length=80)
    capacity_dimension_rows: list[dict[str, object]] = Field(default_factory=list, max_length=40)
    strategic_response_channel_rows: list[dict[str, object]] = Field(
        default_factory=list,
        max_length=40,
    )
    calibration_record_ref: str | None = Field(default=None, max_length=300)
    proof_carrying_analytics_ref: str | None = Field(default=None, max_length=300)
    dynamic_equilibrium_check_ref: str | None = Field(default=None, max_length=300)
    equilibrium_caveat_refs: list[str] = Field(default_factory=list, max_length=80)
    forecast_quality_disposition: ForecastQualityDisposition
    regime_strategy_constraint_ref: str | None = Field(default=None, max_length=300)
    residual_limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    constraint_store_update_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S11_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_upgrade_record(self) -> PredictiveAxisUpgradeRecord:
        _assert_required_denials(self.may_not_use_for)
        _validate_axis_maturity(self.axis, self.effective_maturity)
        if self.relaxation_decision == "relaxed_to_predictive":
            _validate_predictive_upgrade_requirements(self)
        if self.effective_maturity == "fail_closed":
            if self.relaxation_decision != "reverted_fail_closed":
                raise ValueError("fail_closed S11 maturity requires reverted_fail_closed decision")
            if (
                self.forecast_quality_disposition == "downgraded_by_s11_calibration"
                and not self.regime_strategy_constraint_ref
            ):
                raise ValueError("S11 calibration downgrade requires regime strategy constraint")
        return self


class ProofCarryingAnalyticsRecord(Layer2ReadinessModel):
    """S11 traceability wrapper around claim-bound proof-carrying IR analytics."""

    schema_version: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION
    proof_id: str = Field(..., min_length=1, max_length=180)
    proof_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    claim_id: str = Field(..., min_length=1, max_length=200)
    design_comparison_ref: str = Field(..., min_length=1, max_length=300)
    baseline_design_ref: str = Field(..., min_length=1, max_length=300)
    alternative_design_refs: list[str] = Field(default_factory=list, max_length=80)
    ir_analytics_refs: list[str] = Field(default_factory=list, max_length=80)
    method_output_refs: list[str] = Field(default_factory=list, max_length=80)
    ir_certificate_refs: list[str] = Field(default_factory=list, max_length=80)
    negative_certificate_refs: list[str] = Field(default_factory=list, max_length=80)
    proof_status: ProofStatus
    proof_composability_status: ProofComposabilityStatus
    proof_composability_refs: list[str] = Field(default_factory=list, max_length=80)
    method_requirement_refs: list[str] = Field(default_factory=list, max_length=80)
    uncertainty_refs: list[str] = Field(default_factory=list, max_length=80)
    independence_refs: list[str] = Field(default_factory=list, max_length=80)
    effective_independence_collapse_refs: list[str] = Field(default_factory=list, max_length=80)
    counter_evidence_refs: list[str] = Field(default_factory=list, max_length=80)
    limitation_refs: list[str] = Field(default_factory=list, max_length=80)
    blocker_refs: list[str] = Field(default_factory=list, max_length=80)
    ir_analytics_bridge_ref: str = Field(..., min_length=1, max_length=300)
    claim_registry_entry_ref: str = Field(..., min_length=1, max_length=300)
    comparison_consumer_ref: str = Field(..., min_length=1, max_length=300)
    source_lineage_refs: list[str] = Field(default_factory=list, max_length=80)
    method_lineage_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S11_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_proof_record(self) -> ProofCarryingAnalyticsRecord:
        _assert_required_denials(self.may_not_use_for)
        if not any(
            (
                self.ir_analytics_refs,
                self.method_output_refs,
                self.ir_certificate_refs,
                self.negative_certificate_refs,
                self.proof_composability_refs,
                self.uncertainty_refs,
            )
        ):
            raise ValueError("proof-carrying analytics requires proof or certificate refs")
        if self.proof_blocks and not self.blocker_refs and not self.negative_certificate_refs:
            raise ValueError("blocking proof status requires blocker or negative certificate refs")
        return self

    @property
    def proof_blocks(self) -> bool:
        """Return whether this proof record blocks authority upgrade."""

        return (
            bool(self.negative_certificate_refs)
            or self.proof_status in _BLOCKING_PROOF_STATUSES
            or self.proof_composability_status in _BLOCKING_COMPOSABILITY_STATUSES
        )


class S11PredictiveKnowledgeAuthorityEnvelope(Layer2ReadinessModel):
    """Authority-envelope verification for S11 predictive knowledge artifacts."""

    schema_version: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION
    envelope_id: str = Field(..., min_length=1, max_length=180)
    envelope_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    proof_ref: str | None = Field(default=None, max_length=300)
    proof_blocked: bool = False
    blocker_refs: list[str] = Field(default_factory=list, max_length=80)
    issue_codes: list[str] = Field(default_factory=list, max_length=80)
    envelope_status: str = Field(..., min_length=1, max_length=120)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S11_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION


class S11PredictiveKnowledgeIntegrityReport(Layer2ReadinessModel):
    """S11 integrity summary for per-axis calibration and proof-bound upgrades."""

    schema_version: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION
    report_id: str = Field(..., min_length=1, max_length=180)
    case_count: int = Field(..., ge=0)
    axis_count: int = Field(..., ge=0)
    predictive_axis_count: int = Field(..., ge=0)
    reverted_fail_closed_axis_count: int = Field(..., ge=0)
    per_axis_predictive_calibration_numerator: int = Field(..., ge=0)
    per_axis_predictive_calibration_denominator: int = Field(..., ge=0)
    per_axis_predictive_calibration_pass_rate: float = Field(..., ge=0.0, le=1.0)
    per_axis_predictive_calibration_threshold: float = Field(..., ge=0.0, le=1.0)
    per_axis_predictive_calibration_threshold_ref: str = Field(..., min_length=1, max_length=300)
    per_axis_predictive_calibration_status: S11CalibrationStatus
    per_axis_predictive_calibration_floor_passed: bool
    proof_bound_claim_count: int = Field(..., ge=0)
    unbound_analytics_rejected_count: int = Field(..., ge=0)
    negative_certificate_block_count: int = Field(..., ge=0)
    forecast_quality_downgrade_count: int = Field(..., ge=0)
    regime_strategy_constraint_count: int = Field(..., ge=0)
    method_infrastructure_consumed_count: int = Field(..., ge=0)
    weakest_boundary_inheritance_count: int = Field(..., ge=0)
    false_clear_counts: dict[str, int] = Field(default_factory=dict)
    cells_closed: list[str] = Field(default_factory=list, max_length=20)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S11_MAY_NOT_USE_FOR))
    rule_version_ref: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION

    @model_validator(mode="after")
    def _validate_integrity_report(self) -> S11PredictiveKnowledgeIntegrityReport:
        if set(self.false_clear_counts) != set(S11_FALSE_CLEAR_FIELDS):
            raise ValueError("false_clear_counts keys must exactly match S11_FALSE_CLEAR_FIELDS")
        if self.predictive_axis_count + self.reverted_fail_closed_axis_count != (
            self.axis_count
        ):
            raise ValueError("predictive and reverted axes must sum to axis_count")
        if self.per_axis_predictive_calibration_numerator > (
            self.per_axis_predictive_calibration_denominator
        ):
            raise ValueError("S11 calibration numerator cannot exceed denominator")
        if self.per_axis_predictive_calibration_denominator:
            expected = (
                self.per_axis_predictive_calibration_numerator
                / self.per_axis_predictive_calibration_denominator
            )
            if abs(self.per_axis_predictive_calibration_pass_rate - expected) > 0.000001:
                raise ValueError("S11 calibration pass rate must equal numerator / denominator")
        _assert_required_denials(self.may_not_use_for)
        return self


def build_s11_predictive_authority_boundary(
    *,
    authoritative_for: Sequence[str] = (
        "per_axis_predictive_calibration",
        "predictive_axis_maturity_upgrade",
        "proof_carrying_analytics_validity",
    ),
    may_not_use_for: Sequence[str] = _S11_MAY_NOT_USE_FOR,
    posture: Literal["shadow", "advisory", "governed"] = "shadow",
    rule_version_ref: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION,
) -> AuthorityBoundary:
    """Build the purpose-scoped S11 predictive-knowledge authority boundary."""

    return AuthorityBoundary(
        authoritative_for=[str(item) for item in authoritative_for],
        may_not_use_for=_merge_denials(may_not_use_for),
        source_authority="deterministic_producer",
        posture=posture,
        rule_version_refs=[rule_version_ref],
    )


def build_predictive_axis_calibration_record(
    **payload: object,
) -> PredictiveAxisCalibrationRecord:
    """Build a governed per-axis S11 calibration record."""

    _require_calibration_refs(payload)
    prepared = _with_boundary_defaults(
        payload,
        authoritative_for=["per_axis_predictive_calibration"],
    )
    return PredictiveAxisCalibrationRecord.model_validate(prepared)


def build_predictive_axis_upgrade_record(**payload: object) -> PredictiveAxisUpgradeRecord:
    """Build an S11 per-axis maturity upgrade or fail-closed reversion."""

    _require_upgrade_refs(payload)
    prepared = _with_boundary_defaults(
        payload,
        authoritative_for=["predictive_axis_maturity_upgrade"],
    )
    return PredictiveAxisUpgradeRecord.model_validate(prepared)


def build_proof_carrying_analytics_record(**payload: object) -> ProofCarryingAnalyticsRecord:
    """Build the S11 proof-carrying analytics traceability artifact."""

    _require_bound_ir_analytics(payload)
    prepared = _with_boundary_defaults(
        payload,
        authoritative_for=["proof_carrying_analytics_validity"],
    )
    return ProofCarryingAnalyticsRecord.model_validate(prepared)


def verify_s11_predictive_knowledge_authority_envelope(
    *,
    proof_carrying_analytics_record: (
        ProofCarryingAnalyticsRecord | Mapping[str, object] | None
    ) = None,
    axis_upgrade_record: PredictiveAxisUpgradeRecord | Mapping[str, object] | None = None,
) -> S11PredictiveKnowledgeAuthorityEnvelope:
    """Verify S11 artifacts do not mint production, claim, or simulation authority."""

    proof = _as_proof_record(proof_carrying_analytics_record)
    upgrade = _as_upgrade_record(axis_upgrade_record)
    may_not_use_for = _merge_denials(
        proof.may_not_use_for
        if proof is not None
        else upgrade.may_not_use_for
        if upgrade is not None
        else _S11_MAY_NOT_USE_FOR
    )
    blocker_refs = _proof_blocker_refs(proof) if proof is not None else []
    issue_codes = []
    if proof is not None and proof.proof_blocks:
        issue_codes.append("s11_proof_carrying_analytics_blocked")
    if not set(may_not_use_for) >= _REQUIRED_AUTHORITY_DENIALS:
        issue_codes.append("s11_authority_boundary_missing_denials")
    case_id = (
        proof.case_id
        if proof is not None
        else upgrade.case_id
        if upgrade is not None
        else "unknown"
    )
    ref = (
        proof.proof_ref
        if proof is not None
        else upgrade.upgrade_ref
        if upgrade is not None
        else "pdc://layer2/s11/unknown"
    )
    return S11PredictiveKnowledgeAuthorityEnvelope(
        envelope_id=f"layer2.s11.authority.{_stable_token(ref)}",
        envelope_ref=f"{ref}/authority-envelope",
        case_id=case_id,
        proof_ref=proof.proof_ref if proof is not None else None,
        proof_blocked=bool(proof and proof.proof_blocks),
        blocker_refs=blocker_refs,
        issue_codes=issue_codes,
        envelope_status="blocked" if issue_codes else "pass",
        authority_boundary=(
            proof.authority_boundary
            if proof is not None
            else upgrade.authority_boundary
            if upgrade is not None
            else build_s11_predictive_authority_boundary()
        ),
        may_not_use_for=may_not_use_for,
        rule_version_ref=LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION,
    )


def build_s11_predictive_knowledge_posture(
    *,
    case_id: str,
    calibration_records: Sequence[PredictiveAxisCalibrationRecord | Mapping[str, object]],
    proof_records: Sequence[ProofCarryingAnalyticsRecord | Mapping[str, object]],
    axis_upgrade_rows: Sequence[PredictiveAxisUpgradeRecord | Mapping[str, object]],
    s6_floor_status_refs: Sequence[str],
    s6_axis_rows: Sequence[Mapping[str, object]],
    s6_bridge_consumer_rows: Sequence[Mapping[str, object]],
    s6_constraint_store_update_refs: Sequence[str] | None = None,
    s6_c3_authority_dimension_refs: Sequence[str] | None = None,
    post_intervention_dgp_update_ref: str | None = None,
    system_dynamics_handoff_required: bool = False,
    s10_forecast_support_ref: str | None = None,
    s10_forecast_tier: str = "observable_calibrated",
    predictive_knowledge_ref: str | None = None,
    rule_version_ref: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION,
) -> dict[str, object]:
    """Build a replayable S11 posture from S6/S10/calibration/proof refs."""

    calibrations = [_as_calibration_record(record) for record in calibration_records]
    proofs = [_as_proof_record(record) for record in proof_records]
    upgrades = [_as_upgrade_record(row) for row in axis_upgrade_rows]
    floor_refs = [str(ref) for ref in s6_floor_status_refs if str(ref)]
    if not floor_refs:
        raise ValueError("S11 posture requires S6 floor status refs")
    proof_bindings = [
        _proof_bridge_binding(proof)
        for proof in proofs
        if proof is not None and proof.ir_analytics_refs
    ]
    bridge = build_ir_analytics_claim_bridge(
        claim_bindings=proof_bindings,
        run_id=f"layer2-s11-{case_id}",
        bridge_ref=proofs[0].ir_analytics_bridge_ref if proofs else None,
    )
    denominator = sum(record.denominator for record in calibrations)
    numerator = sum(record.numerator for record in calibrations)
    pass_rate = numerator / denominator if denominator else 0.0
    calibration_status = "pass" if calibrations and all(
        record.calibration_status == "pass" and record.floor_passed for record in calibrations
    ) else "limit"
    forecast_quality = _forecast_quality_disposition(upgrades, calibrations)
    regime_ref = _first_present(
        [upgrade.regime_strategy_constraint_ref for upgrade in upgrades]
    )
    residuals = _dedupe(
        [
            *[ref for upgrade in upgrades for ref in upgrade.residual_limitation_refs],
            *[ref for record in calibrations for ref in record.residual_limitation_refs],
        ]
    )
    posture_ref = predictive_knowledge_ref or f"pdc://layer2/s11/{case_id}/predictive-knowledge"
    return {
        "schema_version": LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION,
        "case_id": case_id,
        "predictive_knowledge_ref": posture_ref,
        "axis_upgrade_refs": [upgrade.upgrade_ref for upgrade in upgrades],
        "axis_upgrade_rows": [upgrade.model_dump(mode="json") for upgrade in upgrades],
        "proof_carrying_analytics_ref": proofs[0].proof_ref if proofs else None,
        "ir_analytics_bridge_ref": bridge["ir_analytics_bridge_ref"],
        "s10_forecast_support_ref": (
            s10_forecast_support_ref
            or _first_present([upgrade.s10_forecast_support_ref for upgrade in upgrades])
        ),
        "s10_forecast_tier": s10_forecast_tier,
        "s6_floor_status_refs": floor_refs,
        "s6_axis_rows": [dict(row) for row in s6_axis_rows],
        "s6_bridge_consumer_rows": [dict(row) for row in s6_bridge_consumer_rows],
        "s6_constraint_store_update_refs": list(s6_constraint_store_update_refs or ()),
        "s6_c3_authority_dimension_refs": list(s6_c3_authority_dimension_refs or ()),
        "post_intervention_dgp_update_ref": post_intervention_dgp_update_ref,
        "system_dynamics_handoff_required": system_dynamics_handoff_required,
        "s11_calibration_record_refs": [record.calibration_ref for record in calibrations],
        "method_infrastructure_refs": _dedupe(
            [ref for record in calibrations for ref in record.method_infrastructure_refs]
        ),
        "forecast_quality_disposition": forecast_quality,
        "regime_strategy_constraint_ref": regime_ref,
        "per_axis_predictive_calibration_denominator": denominator,
        "per_axis_predictive_calibration_numerator": numerator,
        "per_axis_predictive_calibration_pass_rate": pass_rate,
        "per_axis_predictive_calibration_status": calibration_status,
        "effective_predictive_posture": _effective_posture(upgrades),
        "residual_limitation_refs": residuals,
        "authority_boundary": build_s11_predictive_authority_boundary(
            authoritative_for=["per_axis_predictive_calibration"],
            rule_version_ref=rule_version_ref,
        ).model_dump(mode="json"),
        "may_not_use_for": list(_S11_MAY_NOT_USE_FOR),
        "canonical_outcome_effect": "predictive_relaxation_only_not_production_authority",
        "rule_version_ref": rule_version_ref,
    }


def summarize_s11_predictive_knowledge_integrity(
    *,
    case_count: int,
    axis_upgrade_records: Sequence[PredictiveAxisUpgradeRecord | Mapping[str, object]],
    calibration_records: Sequence[PredictiveAxisCalibrationRecord | Mapping[str, object]] = (),
    proof_records: Sequence[ProofCarryingAnalyticsRecord | Mapping[str, object]] = (),
    method_infrastructure_refs: Sequence[str] = (),
    cells_closed: Sequence[str] = (),
    report_id: str = "layer2.s11.predictive_knowledge.integrity",
    threshold: float = 0.75,
    threshold_ref: str = "repo://architecture/policy_design_case/layer2_floor_governance.toml#s11",
    rule_version_ref: str = LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION,
) -> S11PredictiveKnowledgeIntegrityReport:
    """Summarize S11 per-axis calibration and proof-bound upgrade decisions."""

    upgrades = [_as_upgrade_record(record) for record in axis_upgrade_records]
    calibrations = [_as_calibration_record(record) for record in calibration_records]
    proofs = [_as_proof_record(record) for record in proof_records]
    denominator = (
        sum(record.denominator for record in calibrations) if calibrations else len(upgrades)
    )
    numerator = (
        sum(record.numerator for record in calibrations)
        if calibrations
        else sum(record.effective_maturity == "predictive" for record in upgrades)
    )
    pass_rate = numerator / denominator if denominator else 0.0
    status: S11CalibrationStatus = "pass" if denominator and pass_rate >= threshold else "limit"
    predictive_count = sum(record.effective_maturity == "predictive" for record in upgrades)
    reverted_count = sum(record.effective_maturity == "fail_closed" for record in upgrades)
    return S11PredictiveKnowledgeIntegrityReport(
        report_id=report_id,
        case_count=case_count,
        axis_count=len(upgrades),
        predictive_axis_count=predictive_count,
        reverted_fail_closed_axis_count=reverted_count,
        per_axis_predictive_calibration_numerator=numerator,
        per_axis_predictive_calibration_denominator=denominator,
        per_axis_predictive_calibration_pass_rate=pass_rate,
        per_axis_predictive_calibration_threshold=threshold,
        per_axis_predictive_calibration_threshold_ref=threshold_ref,
        per_axis_predictive_calibration_status=status,
        per_axis_predictive_calibration_floor_passed=status == "pass",
        proof_bound_claim_count=sum(not proof.proof_blocks for proof in proofs),
        unbound_analytics_rejected_count=0,
        negative_certificate_block_count=sum(
            bool(proof.negative_certificate_refs) for proof in proofs
        ),
        forecast_quality_downgrade_count=sum(
            record.forecast_quality_disposition == "downgraded_by_s11_calibration"
            for record in upgrades
        ),
        regime_strategy_constraint_count=sum(
            bool(record.regime_strategy_constraint_ref) for record in upgrades
        ),
        method_infrastructure_consumed_count=len(_dedupe(method_infrastructure_refs)),
        weakest_boundary_inheritance_count=len(upgrades),
        false_clear_counts=dict.fromkeys(S11_FALSE_CLEAR_FIELDS, 0),
        cells_closed=[
            str(cell)
            for cell in cells_closed
            if str(cell) != "CROSS_CUTTING.method_infrastructure"
        ],
        authority_boundary=build_s11_predictive_authority_boundary(
            authoritative_for=["per_axis_predictive_calibration"],
            rule_version_ref=rule_version_ref,
        ),
        may_not_use_for=list(_S11_MAY_NOT_USE_FOR),
        rule_version_ref=rule_version_ref,
    )


def _require_calibration_refs(payload: Mapping[str, object]) -> None:
    if not payload.get("s6_floor_record_ref"):
        raise ValueError("S6 floor record ref is required for S11 calibration")
    if not payload.get("s10_forecast_support_ref"):
        raise ValueError("S10 forecast support ref is required for S11 calibration")
    if not payload.get("source_contract_ref") or not payload.get("method_validity_ref"):
        raise ValueError("source_contract and method_validity refs are required")


def _require_upgrade_refs(payload: Mapping[str, object]) -> None:
    if not payload.get("s6_floor_record_ref"):
        raise ValueError("S6 floor record ref is required for S11 predictive upgrade")
    if not payload.get("s10_forecast_support_ref"):
        raise ValueError("S10 forecast support ref is required for S11 predictive upgrade")
    if (
        payload.get("relaxation_decision") == "relaxed_to_predictive"
        and not payload.get("calibration_record_ref")
    ):
        raise ValueError("calibration record ref is required for S11 predictive upgrade")


def _require_bound_ir_analytics(payload: Mapping[str, object]) -> None:
    if (
        not payload.get("claim_id")
        or not payload.get("design_comparison_ref")
        or not payload.get("ir_analytics_bridge_ref")
    ):
        raise ValueError(
            "claim-bound IR analytics require claim, comparison, and bridge refs"
        )


def _validate_current_context(record: PredictiveAxisCalibrationRecord) -> None:
    rendered = " ".join(
        [
            record.calibration_ledger_ref,
            record.calibration_scope_ref,
            record.policy_context_ref,
        ]
    ).lower()
    if "historical" in rendered and not all(
        marker in rendered for marker in _CURRENT_CONTEXT_MARKERS
    ):
        raise ValueError("historical prior outside current context cannot improve authority")
    if record.calibration_status in {"stale", "out_of_scope"} and record.floor_passed:
        raise ValueError("stale or out-of-scope calibration cannot pass S11 floor")


def _validate_axis_maturity(axis: str, effective_maturity: str) -> None:
    if axis == "mandate_legitimacy" and effective_maturity == "predictive":
        raise ValueError("mandate_legitimacy cannot become predictive without matrix row")
    if effective_maturity == "predictive" and axis not in S11_PREDICTIVE_AXES:
        raise ValueError("predictive maturity is restricted to S11 matrix axes")


def _validate_predictive_upgrade_requirements(record: PredictiveAxisUpgradeRecord) -> None:
    if record.effective_maturity != "predictive":
        raise ValueError("relaxed_to_predictive requires predictive effective_maturity")
    missing = []
    for field_name in (
        "calibration_record_ref",
        "proof_carrying_analytics_ref",
        "predictive_model_ref",
        "s6_floor_record_ref",
        "s10_forecast_support_ref",
    ):
        if not getattr(record, field_name):
            missing.append(field_name)
    if not record.axis_model_evidence_refs:
        missing.append("axis_model_evidence_refs")
    if missing:
        raise ValueError(f"S11 predictive upgrade missing required refs: {missing}")
    if record.axis == "state_capacity_feasibility":
        _validate_capacity_grounding(record.capacity_dimension_rows)
    if record.axis == "strategic_response":
        _validate_strategic_grounding(record)


def _validate_capacity_grounding(rows: Sequence[Mapping[str, object]]) -> None:
    rendered = " ".join(str(row).lower() for row in rows)
    if not rows or not any(marker in rendered for marker in _CAPACITY_GROUNDING_MARKERS):
        raise ValueError("capacity predictive upgrade requires dimension grounding")


def _validate_strategic_grounding(record: PredictiveAxisUpgradeRecord) -> None:
    rendered = " ".join(str(row).lower() for row in record.strategic_response_channel_rows)
    if not record.dynamic_equilibrium_check_ref and not record.equilibrium_caveat_refs:
        raise ValueError("strategic response predictive upgrade requires equilibrium check")
    if not record.strategic_response_channel_rows or not any(
        marker in rendered for marker in _STRATEGIC_CHANNEL_MARKERS
    ):
        raise ValueError(
            "strategic response predictive upgrade requires Goodhart/Lucas channel rows"
        )


def _with_boundary_defaults(
    payload: Mapping[str, object],
    *,
    authoritative_for: Sequence[str],
) -> dict[str, object]:
    prepared = dict(payload)
    prepared["may_not_use_for"] = _merge_denials(_sequence(prepared.get("may_not_use_for")))
    if not prepared.get("authority_boundary"):
        prepared["authority_boundary"] = build_s11_predictive_authority_boundary(
            authoritative_for=authoritative_for,
            may_not_use_for=prepared["may_not_use_for"],
        )
    return prepared


def _assert_required_denials(may_not_use_for: Sequence[str]) -> None:
    missing = _REQUIRED_AUTHORITY_DENIALS - set(may_not_use_for)
    if missing:
        raise ValueError(f"S11 authority boundary missing denials: {sorted(missing)}")


def _merge_denials(values: Sequence[object]) -> list[str]:
    merged = [str(item) for item in values if str(item)]
    for item in _S11_MAY_NOT_USE_FOR:
        if item not in merged:
            merged.append(item)
    return merged


def _as_calibration_record(
    value: PredictiveAxisCalibrationRecord | Mapping[str, object],
) -> PredictiveAxisCalibrationRecord:
    if isinstance(value, PredictiveAxisCalibrationRecord):
        return value
    return build_predictive_axis_calibration_record(**dict(value))


def _as_upgrade_record(
    value: PredictiveAxisUpgradeRecord | Mapping[str, object] | None,
) -> PredictiveAxisUpgradeRecord | None:
    if value is None:
        return None
    if isinstance(value, PredictiveAxisUpgradeRecord):
        return value
    return build_predictive_axis_upgrade_record(**dict(value))


def _as_proof_record(
    value: ProofCarryingAnalyticsRecord | Mapping[str, object] | None,
) -> ProofCarryingAnalyticsRecord | None:
    if value is None:
        return None
    if isinstance(value, ProofCarryingAnalyticsRecord):
        return value
    return build_proof_carrying_analytics_record(**dict(value))


def _proof_bridge_binding(proof: ProofCarryingAnalyticsRecord) -> dict[str, object]:
    return {
        "claim_id": proof.claim_id,
        "analytics_ref": proof.ir_analytics_refs[0] if proof.ir_analytics_refs else proof.proof_ref,
        "method_output_refs": proof.method_output_refs,
        "certificate_refs": proof.ir_certificate_refs,
        "negative_certificate_refs": proof.negative_certificate_refs,
        "proof_status": proof.proof_status,
        "proof_composability_status": proof.proof_composability_status,
        "proof_composability_refs": proof.proof_composability_refs,
        "uncertainty_refs": proof.uncertainty_refs,
        "baseline_refs": [proof.baseline_design_ref],
        "comparison_refs": [proof.design_comparison_ref],
        "alternative_refs": proof.alternative_design_refs,
        "independence_refs": proof.independence_refs,
        "limitation_refs": proof.limitation_refs,
        "blocker_refs": proof.blocker_refs,
    }


def _proof_blocker_refs(proof: ProofCarryingAnalyticsRecord | None) -> list[str]:
    if proof is None:
        return []
    return _dedupe(
        [
            *proof.blocker_refs,
            *proof.negative_certificate_refs,
            *(
                proof.proof_composability_refs
                if proof.proof_composability_status in _BLOCKING_COMPOSABILITY_STATUSES
                else []
            ),
        ]
    )


def _forecast_quality_disposition(
    upgrades: Sequence[PredictiveAxisUpgradeRecord],
    calibrations: Sequence[PredictiveAxisCalibrationRecord],
) -> str:
    if any(
        upgrade.forecast_quality_disposition == "downgraded_by_s11_calibration"
        for upgrade in upgrades
    ):
        return "downgraded_by_s11_calibration"
    if any(
        record.calibration_status != "pass" or not record.floor_passed
        for record in calibrations
    ):
        return "downgraded_by_s11_calibration"
    return "unchanged_s10_tier_consumed"


def _effective_posture(upgrades: Sequence[PredictiveAxisUpgradeRecord]) -> str:
    if any(upgrade.effective_maturity == "fail_closed" for upgrade in upgrades):
        return "limited_by_weakest_boundary"
    return "predictive"


def _sequence(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return list(value)
    return []


def _first_present(values: Sequence[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _dedupe(values: Sequence[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _stable_token(value: str) -> str:
    return (
        value.replace("pdc://", "")
        .replace("://", "-")
        .replace("/", "-")
        .replace(".", "-")[:96]
    )


__all__ = [
    "LAYER2_S11_PREDICTIVE_KNOWLEDGE_RULE_VERSION",
    "LAYER2_S11_PREDICTIVE_KNOWLEDGE_SCHEMA_VERSION",
    "S11_AXIS_CALIBRATION_FLOOR_ID",
    "S11_FALSE_CLEAR_FIELDS",
    "S11_PREDICTIVE_AXES",
    "ForecastQualityDisposition",
    "PredictiveAxis",
    "PredictiveAxisCalibrationRecord",
    "PredictiveAxisUpgradeRecord",
    "PredictiveMaturity",
    "ProofCarryingAnalyticsRecord",
    "ProofComposabilityStatus",
    "ProofStatus",
    "RelaxationDecision",
    "S11CalibrationStatus",
    "S11PredictiveKnowledgeAuthorityEnvelope",
    "S11PredictiveKnowledgeIntegrityReport",
    "build_predictive_axis_calibration_record",
    "build_predictive_axis_upgrade_record",
    "build_proof_carrying_analytics_record",
    "build_s11_predictive_authority_boundary",
    "build_s11_predictive_knowledge_posture",
    "summarize_s11_predictive_knowledge_integrity",
    "verify_s11_predictive_knowledge_authority_envelope",
]
