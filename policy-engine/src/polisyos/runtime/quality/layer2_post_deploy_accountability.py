"""Layer 2 S13 post-deploy accountability contracts and anti-learning firewalls."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from polisyos.pdc import AuthorityBoundary, Layer2ReadinessModel, TypedDiagnosticRecord
from polisyos.runtime.quality.calibration_ledger import (
    historical_prior_claim_evidence_issues,
    is_historical_prior_ref,
)
from polisyos.runtime.quality.case_lifecycle import validate_ex_post_learning_record
from polisyos.runtime.quality.ddm_monitoring import (
    validate_implementation_monitoring_evaluation_record,
)

LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
)
LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION = (
    "policyos.layer2.s13.post_deploy_accountability.v1"
)
S13_ACCOUNTABILITY_FLOOR_ID = "s13_accountability"
S13_FALSE_CLEAR_FIELDS: tuple[str, ...] = (
    "post_policy_data_as_pre_policy_evidence",
    "learned_prior_in_current_evidence_slot",
    "unattributable_updates_model",
    "silent_closed_case_rewrite",
    "learning_without_attribution",
    "envelope_shrink_without_assurance_delta",
    "b_update_before_a_baseline",
    "implementation_failure_as_theory_refutation",
    "outcome_learning_without_counterfactual",
    "s13_as_production_or_recommendation_authority",
)

DeploymentReadinessDisposition = Literal[
    "deployable",
    "advisory_only",
    "accountability_only",
    "blocked",
]
DivergenceAttributionClass = Literal[
    "design_error",
    "evidence_error",
    "regime_error",
    "coupling_error",
    "world_change",
    "strategic_response",
    "implementation_failure",
    "unattributable",
]
AttributionStatus = Literal["attributed", "unattributable", "pending"]
LearningChangeControlClass = Literal[
    "pre_authorized",
    "reissue_required",
    "envelope_shrink",
    "historical_prior_only",
    "public_accountability_note",
]
LearningUpdateTarget = Literal[
    "substrate",
    "a_firewall",
    "b_prior",
    "calibration",
    "regime_classifier",
    "coupling_classifier",
    "strategic_response_model",
    "capacity_feasibility_model",
    "memory",
    "corpus_label",
    "envelope",
    "public_accountability_note",
]
LifecycleReissueDisposition = Literal[
    "fail",
    "withdraw_required",
    "supersede_required",
    "reissue_required",
    "review_required",
    "pass",
]
EnvelopeRevisionDirection = Literal["expand", "shrink", "hold", "split"]
AssuranceCaseChange = Literal["strengthened", "weakened", "invalidated", "unchanged"]
PostDeployMapeKPhase = Literal["monitor", "analyze", "plan", "execute", "knowledge"]
OversightLinkedAccountabilityState = Literal[
    "not_applicable",
    "effective_oversight_linked",
    "rubber_stamp_divergence_review_required",
]
ActionItemStatus = Literal["open", "closed", "pending", "blocked"]

_S13_AUTHORITY_SCOPE: tuple[str, ...] = (
    "post_deploy_accountability",
    "deployment_monitorability",
    "divergence_attribution",
    "learning_update_proposal",
    "post_deploy_mape_k_trace",
    "envelope_revision",
    "assurance_case_delta",
    "public_accountability_note",
)
_S13_MAY_NOT_USE_FOR: tuple[str, ...] = (
    "production_rollout_authority",
    "recommendation_authority",
    "publication_authority",
    "approval_authority",
    "scorecard_authority",
    "pre_policy_evidence",
    "current_evidence_slot",
    "preference_learning",
    "automated_value_learning",
    "naive_ml_update",
    "s14_universality",
    "llm_attribution_authority",
    "local_governance_enum_for_reissue",
)
_REQUIRED_AUTHORITY_DENIALS = frozenset(_S13_MAY_NOT_USE_FOR)
_FORBIDDEN_AUTHORITY_SCOPE = frozenset(
    {
        "production_authority",
        "production_rollout_authority",
        "rollout_authority",
        "recommendation_authority",
        "production_recommendation",
        "publication_authority",
        "approval_authority",
        "scorecard_authority",
        "pre_policy_evidence",
        "current_evidence_slot",
        "preference_learning",
        "automated_value_learning",
        "naive_ml_update",
        "s14_universality",
        "llm_attribution_authority",
    }
)
_MODEL_UPDATE_TARGETS = frozenset(
    {
        "model",
        "prior",
        "b_prior",
        "calibration",
        "regime_classifier",
        "coupling_classifier",
        "strategic_response_model",
        "capacity_feasibility_model",
        "memory",
        "corpus_label",
        "envelope",
    }
)


class DeploymentDossier(Layer2ReadinessModel):
    """Design-time deployment accountability gate for an otherwise deployable case."""

    schema_version: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION
    dossier_id: str = Field(..., min_length=1, max_length=180)
    dossier_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    deployment_ref: str = Field(..., min_length=1, max_length=300)
    deployment_time: AwareDatetime | None = None
    observation_start_time: AwareDatetime | None = None
    detection_time: AwareDatetime | None = None
    attribution_due_time: AwareDatetime | None = None
    reissue_due_time: AwareDatetime | None = None
    replay_time: AwareDatetime | None = None
    monitoring_design_ref: str | None = Field(default=None, max_length=300)
    implementation_monitoring_evaluation_ref: str | None = Field(default=None, max_length=300)
    implementation_monitoring_evaluation_record: dict[str, Any] | None = None
    signpost_refs: list[str] = Field(default_factory=list, max_length=80)
    complaint_intake_ref: str | None = Field(default=None, max_length=300)
    near_miss_intake_ref: str | None = Field(default=None, max_length=300)
    attribution_plan_ref: str | None = Field(default=None, max_length=300)
    reissue_path_ref: str | None = Field(default=None, max_length=300)
    rollback_path_ref: str | None = Field(default=None, max_length=300)
    owner: str | None = Field(default=None, max_length=200)
    owner_due_date: str | None = Field(default=None, max_length=80)
    readiness_disposition: DeploymentReadinessDisposition
    monitorability_floor_passed: bool
    learning_allowed: bool
    mape_k_trace_ref: str | None = Field(default=None, max_length=300)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S13_MAY_NOT_USE_FOR))
    replay_digest: str = Field(default="", max_length=96)
    rule_version_ref: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION

    @model_validator(mode="after")
    def _validate_dossier(self) -> DeploymentDossier:
        _assert_required_denials(self.may_not_use_for)
        _assert_no_forbidden_authority(self.authority_boundary)
        if self.implementation_monitoring_evaluation_record is not None:
            validate_implementation_monitoring_evaluation_record(
                self.implementation_monitoring_evaluation_record
            )
        if self.readiness_disposition == "deployable":
            missing = [
                field
                for field, value in (
                    ("monitoring_design_ref", self.monitoring_design_ref),
                    ("owner", self.owner),
                    ("owner_due_date", self.owner_due_date),
                    ("reissue_path_ref", self.reissue_path_ref),
                    ("rollback_path_ref", self.rollback_path_ref),
                )
                if not _text(value)
            ]
            if missing:
                raise ValueError(
                    "deployable DeploymentDossier missing " + ", ".join(missing)
                )
            if not self.monitorability_floor_passed:
                raise ValueError("deployable DeploymentDossier requires monitorability floor")
        if self.readiness_disposition == "accountability_only":
            if not self.monitorability_floor_passed:
                raise ValueError("accountability_only requires monitorability floor")
            if self.learning_allowed:
                raise ValueError("accountability_only cannot allow governed learning")
        return self


class DivergenceRecord(Layer2ReadinessModel):
    """Post-deploy divergence record with attribution and owned closure semantics."""

    schema_version: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION
    divergence_id: str = Field(..., min_length=1, max_length=180)
    divergence_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    deployment_dossier_ref: str = Field(..., min_length=1, max_length=300)
    diagnostic: TypedDiagnosticRecord
    attribution_class: DivergenceAttributionClass
    attribution_status: AttributionStatus
    severity: str = Field(..., min_length=1, max_length=80)
    failed_axis: str | None = Field(default=None, max_length=200)
    failed_firewall: str | None = Field(default=None, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=120)
    attribution_owner: str | None = Field(default=None, max_length=200)
    allowed_moves: list[str] = Field(default_factory=list, max_length=80)
    learning_eligible: bool
    authority_boundary: AuthorityBoundary
    replay_refs: list[str] = Field(default_factory=list, max_length=80)
    b_may_learn_from_divergence: bool = False
    a_repair_required_before_b_learning: bool = False
    observation_time: AwareDatetime | None = None
    detection_time: AwareDatetime | None = None
    attribution_time: AwareDatetime | None = None
    replay_time: AwareDatetime | None = None
    action_item_owner: str | None = Field(default=None, max_length=200)
    action_item_due_date: str | None = Field(default=None, max_length=80)
    action_item_status: ActionItemStatus | None = None
    action_item_closure_ref: str | None = Field(default=None, max_length=300)
    human_review_ref: str | None = Field(default=None, max_length=300)
    oversight_effectiveness_ref: str | None = Field(default=None, max_length=300)
    effective_oversight: bool | None = None
    rubber_stamp_risk: str | None = Field(default=None, max_length=80)
    oversight_accountability_state: OversightLinkedAccountabilityState = "not_applicable"
    policy_theory_refuted: bool = False
    independent_theory_refutation_ref: str | None = Field(default=None, max_length=300)
    rule_version_ref: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION

    @model_validator(mode="after")
    def _validate_divergence(self) -> DivergenceRecord:
        _assert_no_forbidden_authority(self.authority_boundary)
        if self.learning_eligible and self.attribution_status != "attributed":
            raise ValueError("divergence learning requires attributed attribution status")
        if self.learning_eligible and not self.attribution_owner:
            raise ValueError("attributed learning requires attribution owner")
        if not self.action_item_owner or not self.action_item_due_date:
            raise ValueError("divergence accountability requires owned action-item deadline")
        if self.action_item_status == "closed" and not self.action_item_closure_ref:
            raise ValueError("closed action item requires closure ref")
        if (
            self.attribution_class == "design_error"
            and (
                self.effective_oversight is False
                or _text(self.rubber_stamp_risk) == "high"
            )
            and self.oversight_accountability_state
            != "rubber_stamp_divergence_review_required"
        ):
            raise ValueError(
                "design_error after ineffective review requires rubber-stamp accountability"
            )
        if (
            self.attribution_class == "implementation_failure"
            and self.policy_theory_refuted
            and not self.independent_theory_refutation_ref
        ):
            raise ValueError(
                "implementation_failure cannot refute policy theory without independent ref"
            )
        return self


class PostDeployMapeKTrace(Layer2ReadinessModel):
    """Embedded S13 MAPE-K trace over monitor, analyze, plan, execute, knowledge refs."""

    schema_version: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION
    trace_id: str = Field(..., min_length=1, max_length=180)
    trace_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    monitor_refs: list[str] = Field(..., min_length=1, max_length=120)
    analyze_refs: list[str] = Field(..., min_length=1, max_length=120)
    plan_refs: list[str] = Field(..., min_length=1, max_length=120)
    execute_refs: list[str] = Field(..., min_length=1, max_length=120)
    knowledge_refs: list[str] = Field(..., min_length=1, max_length=120)
    rule_version_ref: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION


class LearningUpdateProposal(Layer2ReadinessModel):
    """Attribution-gated S13 learning proposal wrapping the lifecycle substrate."""

    schema_version: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION
    proposal_id: str = Field(..., min_length=1, max_length=180)
    proposal_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    divergence_record_ref: str = Field(..., min_length=1, max_length=300)
    ex_post_learning_record: dict[str, Any]
    attribution_class: DivergenceAttributionClass
    attribution_status: AttributionStatus
    change_control_class: LearningChangeControlClass
    learning_update_target: LearningUpdateTarget
    learning_allowed: bool
    a_before_b_status: Literal["pass", "fail"]
    deployment_baseline_ref: str | None = Field(default=None, max_length=300)
    post_deploy_signal_refs: list[str] = Field(default_factory=list, max_length=120)
    governance_decision_class_ref: str | None = Field(default=None, max_length=300)
    human_decision_request_refs: list[str] = Field(default_factory=list, max_length=80)
    human_decision_record_refs: list[str] = Field(default_factory=list, max_length=80)
    historical_prior_influence_refs: list[str] = Field(default_factory=list, max_length=80)
    historical_prior_provenance_ref: str | None = Field(default=None, max_length=300)
    historical_prior_ttl: str | None = Field(default=None, max_length=80)
    historical_prior_decay: str | None = Field(default=None, max_length=80)
    contamination_control_refs: list[str] = Field(default_factory=list, max_length=80)
    lifecycle_reissue_disposition: LifecycleReissueDisposition | None = None
    assurance_case_delta_ref: str | None = Field(default=None, max_length=300)
    public_accountability_note_ref: str | None = Field(default=None, max_length=300)
    observation_time: AwareDatetime | None = None
    detection_time: AwareDatetime | None = None
    attribution_time: AwareDatetime | None = None
    reissue_time: AwareDatetime | None = None
    replay_time: AwareDatetime | None = None
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S13_MAY_NOT_USE_FOR))
    replay_digest: str = Field(default="", max_length=96)
    rule_version_ref: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION

    @model_validator(mode="after")
    def _validate_learning_proposal(self) -> LearningUpdateProposal:
        _assert_required_denials(self.may_not_use_for)
        _assert_no_forbidden_authority(self.authority_boundary)
        if self.learning_allowed and self.a_before_b_status != "pass":
            raise ValueError("A-before-B barrier must pass before post-deploy learning")
        if self.learning_allowed and self.attribution_status != "attributed":
            raise ValueError("learning update requires attributed divergence")
        if self.learning_allowed and not self.deployment_baseline_ref:
            raise ValueError("A-before-B learning requires deployment baseline ref")
        if self.learning_allowed and not self.post_deploy_signal_refs:
            raise ValueError("learning update requires post-deploy signal refs")
        if (
            self.learning_allowed
            and self.learning_update_target != "public_accountability_note"
            and not self.assurance_case_delta_ref
        ):
            raise ValueError("learning update requires assurance case delta")
        if self.change_control_class == "reissue_required":
            if self.lifecycle_reissue_disposition is None:
                raise ValueError("reissue change control requires lifecycle disposition")
            if not self.human_decision_record_refs:
                raise ValueError("reissue requires HumanDecisionRecord human_decision_record ref")
        if (
            self.change_control_class in {"envelope_shrink", "reissue_required"}
            and not (self.human_decision_record_refs or self.governance_decision_class_ref)
        ):
            raise ValueError("high-stakes envelope revision requires governance refs")
        if self.historical_prior_influence_refs:
            if not all(
                is_historical_prior_ref(ref)
                for ref in self.historical_prior_influence_refs
            ):
                raise ValueError("historical prior influence refs require recognized prefix")
            if not (
                self.historical_prior_provenance_ref
                and self.historical_prior_ttl
                and self.historical_prior_decay
                and self.contamination_control_refs
            ):
                raise ValueError(
                    "historical prior influence requires provenance, ttl, decay, "
                    "and contamination controls"
                )
        try:
            validate_ex_post_learning_record(self.ex_post_learning_record)
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        return self


class CertifiedEnvelopeDelta(Layer2ReadinessModel):
    """S13 materialization of a certified envelope delta, including S12 growth refs."""

    schema_version: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION
    delta_id: str = Field(..., min_length=1, max_length=180)
    delta_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    s12_certified_envelope_delta_ref: str | None = Field(default=None, max_length=300)
    materialized_from_s12_growth_entry_ref: str | None = Field(default=None, max_length=300)
    direction: EnvelopeRevisionDirection
    certified_scope_refs: list[str] = Field(default_factory=list, max_length=120)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION

    @model_validator(mode="after")
    def _validate_certified_delta(self) -> CertifiedEnvelopeDelta:
        _assert_no_forbidden_authority(self.authority_boundary)
        if self.direction != "expand":
            raise ValueError("CertifiedEnvelopeDelta materializes certified growth only")
        if self.s12_certified_envelope_delta_ref and not (
            self.materialized_from_s12_growth_entry_ref
        ):
            raise ValueError("S12 certified delta materialization requires growth entry ref")
        return self


class AssuranceCaseDelta(Layer2ReadinessModel):
    """Assurance-case delta required for non-hold S13 envelope revisions."""

    schema_version: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION
    delta_id: str = Field(..., min_length=1, max_length=180)
    delta_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    assurance_case_change: AssuranceCaseChange
    affected_claim_refs: list[str] = Field(default_factory=list, max_length=120)
    unaffected_claim_refs: list[str] = Field(default_factory=list, max_length=120)
    public_revision_state_ref: str | None = Field(default=None, max_length=300)
    closed_case_historical_meaning: Literal["preserved", "changed"] = "preserved"
    silent_upgrade_allowed: bool = False
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION

    @model_validator(mode="after")
    def _validate_assurance_delta(self) -> AssuranceCaseDelta:
        _assert_no_forbidden_authority(self.authority_boundary)
        if self.silent_upgrade_allowed:
            raise ValueError("S13 assurance deltas cannot allow silent closed-case upgrade")
        if self.closed_case_historical_meaning != "preserved":
            raise ValueError("S13 assurance deltas must preserve closed-case meaning")
        return self


class EnvelopeRevision(Layer2ReadinessModel):
    """S13 bidirectional envelope revision with asymmetric shrink/split gating."""

    schema_version: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION
    revision_id: str = Field(..., min_length=1, max_length=180)
    revision_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    direction: EnvelopeRevisionDirection
    reason: str = Field(..., min_length=1, max_length=800)
    divergence_record_ref: str | None = Field(default=None, max_length=300)
    learning_update_proposal_ref: str | None = Field(default=None, max_length=300)
    assurance_case_delta_ref: str | None = Field(default=None, max_length=300)
    certified_envelope_delta_ref: str | None = Field(default=None, max_length=300)
    disconfirming_signal_time: AwareDatetime | None = None
    revision_effective_time: AwareDatetime | None = None
    shrink_latency_days: int | None = Field(default=None, ge=0)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION

    @model_validator(mode="after")
    def _validate_revision(self) -> EnvelopeRevision:
        _assert_no_forbidden_authority(self.authority_boundary)
        if self.direction != "hold" and not self.assurance_case_delta_ref:
            raise ValueError("non-hold envelope revision requires assurance case delta")
        if self.direction == "expand" and not self.certified_envelope_delta_ref:
            raise ValueError("expand envelope revision requires certified envelope delta")
        if self.direction in {"shrink", "split"}:
            missing_latency = (
                self.disconfirming_signal_time is None
                or self.revision_effective_time is None
                or self.shrink_latency_days is None
            )
            if missing_latency:
                raise ValueError("shrink/split envelope revision requires latency fields")
        return self


class PostDeployAccountabilitySummary(Layer2ReadinessModel):
    """S13 closure metrics and exact anti-learning false-clear counts."""

    schema_version: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION
    summary_id: str = Field(..., min_length=1, max_length=180)
    slice: Literal["S13"] = "S13"
    cells_closed: list[str] = Field(default_factory=list, max_length=0)
    layer_cells_advanced: list[str] = Field(default_factory=list, max_length=5)
    current_open_cell_count: int = Field(default=0, ge=0)
    case_count: int = Field(..., ge=0)
    monitorability_rate: float = Field(..., ge=0.0, le=1.0)
    a_before_b_ratio: float = Field(..., ge=0.0, le=1.0)
    attribution_resolution_rate: float = Field(..., ge=0.0, le=1.0)
    envelope_shrink_count: int = Field(..., ge=0)
    envelope_expansion_count: int = Field(..., ge=0)
    envelope_shrink_latency_recorded_count: int = Field(..., ge=0)
    unattributable_accountability_without_training_count: int = Field(..., ge=0)
    mape_k_trace_completeness_rate: float = Field(..., ge=0.0, le=1.0)
    action_item_closure_rate: float = Field(..., ge=0.0, le=1.0)
    oversight_effectiveness_link_rate: float = Field(..., ge=0.0, le=1.0)
    rubber_stamp_divergence_review_required_count: int = Field(..., ge=0)
    learning_without_attribution_count: int = Field(..., ge=0)
    growth_without_assurance_delta_count: int = Field(..., ge=0)
    false_clear_counts: dict[str, int] = Field(default_factory=dict)
    post_policy_data_as_pre_policy_evidence_false_clear_count: int = 0
    learned_prior_in_current_evidence_slot_false_clear_count: int = 0
    unattributable_updates_model_false_clear_count: int = 0
    silent_closed_case_rewrite_false_clear_count: int = 0
    learning_without_attribution_false_clear_count: int = 0
    envelope_shrink_without_assurance_delta_false_clear_count: int = 0
    b_update_before_a_baseline_false_clear_count: int = 0
    implementation_failure_as_theory_refutation_false_clear_count: int = 0
    outcome_learning_without_counterfactual_false_clear_count: int = 0
    s13_as_production_or_recommendation_authority_false_clear_count: int = 0
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION

    @model_validator(mode="after")
    def _validate_summary(self) -> PostDeployAccountabilitySummary:
        if tuple(self.false_clear_counts) != S13_FALSE_CLEAR_FIELDS:
            raise ValueError("false_clear_counts keys must exactly match S13_FALSE_CLEAR_FIELDS")
        if any(value < 0 for value in self.false_clear_counts.values()):
            raise ValueError("false_clear_counts cannot be negative")
        for field in S13_FALSE_CLEAR_FIELDS:
            flat_value = getattr(self, f"{field}_false_clear_count")
            if flat_value != self.false_clear_counts[field]:
                raise ValueError(f"{field}_false_clear_count must match false_clear_counts")
        if self.cells_closed:
            raise ValueError("S13 must not close a new Layer 2 cell")
        if self.layer_cells_advanced != ["DESIGNER_ITSELF.envelope_growth"]:
            raise ValueError("S13 must advance DESIGNER_ITSELF.envelope_growth")
        _assert_no_forbidden_authority(self.authority_boundary)
        return self


def build_s13_accountability_authority_boundary(
    *,
    authoritative_for: Sequence[str] = _S13_AUTHORITY_SCOPE,
    may_not_use_for: Sequence[str] = _S13_MAY_NOT_USE_FOR,
    posture: Literal["shadow", "advisory", "governed"] = "shadow",
    rule_version_ref: str = LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION,
) -> AuthorityBoundary:
    """Build the purpose-scoped S13 accountability authority boundary."""

    boundary = AuthorityBoundary(
        authoritative_for=_dedupe([str(item) for item in authoritative_for]),
        may_not_use_for=_merge_denials(may_not_use_for),
        source_authority="deterministic_producer",
        posture=posture,
        rule_version_refs=[rule_version_ref],
    )
    _assert_no_forbidden_authority(boundary)
    return boundary


def build_deployment_dossier(**payload: object) -> DeploymentDossier:
    """Build a strict deployment dossier and attach a deterministic replay digest."""

    normalized = dict(payload)
    normalized["replay_digest"] = _digest_payload(
        normalized,
        exclude={"replay_digest"},
    )
    return DeploymentDossier.model_validate(normalized)


def classify_post_deploy_divergence(**payload: object) -> DivergenceRecord:
    """Classify a post-deploy divergence without granting learning authority."""

    return DivergenceRecord.model_validate(payload)


def build_post_deploy_mape_k_trace(**payload: object) -> PostDeployMapeKTrace:
    """Build the embedded S13 MAPE-K trace."""

    return PostDeployMapeKTrace.model_validate(payload)


def build_learning_update_proposal(**payload: object) -> LearningUpdateProposal:
    """Build an attribution-gated learning proposal with replay digest."""

    normalized = dict(payload)
    normalized["replay_digest"] = _digest_payload(
        normalized,
        exclude={"replay_digest"},
    )
    return LearningUpdateProposal.model_validate(normalized)


def build_certified_envelope_delta(**payload: object) -> CertifiedEnvelopeDelta:
    """Build a certified envelope delta that may materialize an S12 growth ref."""

    return CertifiedEnvelopeDelta.model_validate(payload)


def build_assurance_case_delta(**payload: object) -> AssuranceCaseDelta:
    """Build an S13 assurance-case delta for an envelope revision."""

    return AssuranceCaseDelta.model_validate(payload)


def build_envelope_revision(**payload: object) -> EnvelopeRevision:
    """Build an S13 envelope revision with assurance and latency gates."""

    return EnvelopeRevision.model_validate(payload)


def verify_post_deploy_learning_authority(
    probe_or_payload: Mapping[str, object] | None = None,
) -> tuple[str, ...]:
    """Return S13 anti-learning firewall issue keys for a probe or payload."""

    payload = dict(probe_or_payload or {})
    issue_codes: list[str] = []
    explicit = _text(payload.get("false_clear_field"))
    if explicit in set(S13_FALSE_CLEAR_FIELDS):
        issue_codes.append(explicit)
    if _post_policy_data_in_pre_policy_slots(payload):
        issue_codes.append("post_policy_data_as_pre_policy_evidence")
    if _learned_prior_in_current_evidence(payload):
        issue_codes.append("learned_prior_in_current_evidence_slot")
    if _unattributable_updates_model(payload):
        issue_codes.append("unattributable_updates_model")
    if (
        payload.get("silent_upgrade_allowed") is True
        or _text(payload.get("closed_case_historical_meaning")) == "changed"
    ):
        issue_codes.append("silent_closed_case_rewrite")
    if _learning_without_attribution(payload):
        issue_codes.append("learning_without_attribution")
    if _envelope_shrink_without_assurance(payload):
        issue_codes.append("envelope_shrink_without_assurance_delta")
    if _b_update_before_a_baseline(payload):
        issue_codes.append("b_update_before_a_baseline")
    if _implementation_failure_as_theory_refutation(payload):
        issue_codes.append("implementation_failure_as_theory_refutation")
    if _outcome_learning_without_counterfactual(payload):
        issue_codes.append("outcome_learning_without_counterfactual")
    if _s13_mints_forbidden_authority(payload):
        issue_codes.append("s13_as_production_or_recommendation_authority")
    return tuple(_dedupe([code for code in issue_codes if code in S13_FALSE_CLEAR_FIELDS]))


def summarize_post_deploy_accountability(
    *,
    dossiers: Sequence[DeploymentDossier | Mapping[str, object]] = (),
    divergences: Sequence[DivergenceRecord | Mapping[str, object]] = (),
    learning_update_proposals: Sequence[LearningUpdateProposal | Mapping[str, object]] = (),
    envelope_revisions: Sequence[EnvelopeRevision | Mapping[str, object]] = (),
    assurance_case_deltas: Sequence[AssuranceCaseDelta | Mapping[str, object]] = (),
    certified_envelope_deltas: Sequence[CertifiedEnvelopeDelta | Mapping[str, object]] = (),
    mape_k_traces: Sequence[PostDeployMapeKTrace | Mapping[str, object]] = (),
    case_count: int | None = None,
    summary_id: str = "layer2.s13.post_deploy_accountability.summary",
) -> PostDeployAccountabilitySummary:
    """Summarize S13 accountability metrics over runtime artifacts."""

    dossier_rows = [_as_dossier(row) for row in dossiers]
    divergence_rows = [_as_divergence(row) for row in divergences]
    proposal_rows = [_as_learning_proposal(row) for row in learning_update_proposals]
    revision_rows = [_as_envelope_revision(row) for row in envelope_revisions]
    # Validate side artifacts even when metrics do not directly aggregate them.
    [_as_assurance_delta(row) for row in assurance_case_deltas]
    [_as_certified_delta(row) for row in certified_envelope_deltas]
    trace_rows = [_as_mape_k_trace(row) for row in mape_k_traces]

    resolved_case_count = case_count if case_count is not None else len(dossier_rows)
    monitorability_rate = _ratio(
        sum(row.monitorability_floor_passed for row in dossier_rows),
        len(dossier_rows),
        default=1.0,
    )
    a_before_b_ratio = _ratio(
        sum(row.a_before_b_status == "pass" for row in proposal_rows),
        len(proposal_rows),
        default=1.0,
    )
    attribution_resolution_rate = _ratio(
        sum(row.attribution_status == "attributed" for row in proposal_rows),
        len(proposal_rows),
        default=1.0,
    )
    false_clear_counts = dict.fromkeys(S13_FALSE_CLEAR_FIELDS, 0)
    summary_payload: dict[str, object] = {
        "summary_id": summary_id,
        "slice": "S13",
        "cells_closed": [],
        "layer_cells_advanced": ["DESIGNER_ITSELF.envelope_growth"],
        "current_open_cell_count": 0,
        "case_count": resolved_case_count,
        "monitorability_rate": monitorability_rate,
        "a_before_b_ratio": a_before_b_ratio,
        "attribution_resolution_rate": attribution_resolution_rate,
        "envelope_shrink_count": sum(row.direction == "shrink" for row in revision_rows),
        "envelope_expansion_count": sum(row.direction == "expand" for row in revision_rows),
        "envelope_shrink_latency_recorded_count": sum(
            row.direction in {"shrink", "split"} and row.shrink_latency_days is not None
            for row in revision_rows
        ),
        "unattributable_accountability_without_training_count": sum(
            row.attribution_status == "unattributable" and not row.learning_eligible
            for row in divergence_rows
        ),
        "mape_k_trace_completeness_rate": _ratio(
            sum(_trace_complete(row) for row in trace_rows),
            len(trace_rows),
            default=1.0,
        ),
        "action_item_closure_rate": _action_item_closure_rate(divergence_rows),
        "oversight_effectiveness_link_rate": _oversight_link_rate(divergence_rows),
        "rubber_stamp_divergence_review_required_count": sum(
            row.oversight_accountability_state
            == "rubber_stamp_divergence_review_required"
            for row in divergence_rows
        ),
        "learning_without_attribution_count": sum(
            row.learning_allowed and row.attribution_status != "attributed"
            for row in proposal_rows
        ),
        "growth_without_assurance_delta_count": sum(
            row.direction != "hold" and not row.assurance_case_delta_ref
            for row in revision_rows
        ),
        "false_clear_counts": false_clear_counts,
        "authority_boundary": build_s13_accountability_authority_boundary().model_dump(
            mode="json"
        ),
        "rule_version_ref": LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION,
    }
    for field in S13_FALSE_CLEAR_FIELDS:
        summary_payload[f"{field}_false_clear_count"] = false_clear_counts[field]
    return PostDeployAccountabilitySummary.model_validate(summary_payload)


def build_s13_post_deploy_accountability_posture(
    *,
    deployment_dossier: DeploymentDossier | Mapping[str, object],
    divergences: Sequence[DivergenceRecord | Mapping[str, object]] = (),
    learning_update_proposals: Sequence[LearningUpdateProposal | Mapping[str, object]] = (),
    envelope_revision: EnvelopeRevision | Mapping[str, object] | None = None,
    certified_envelope_delta: CertifiedEnvelopeDelta | Mapping[str, object] | None = None,
    assurance_case_delta: AssuranceCaseDelta | Mapping[str, object] | None = None,
    mape_k_trace: PostDeployMapeKTrace | Mapping[str, object] | None = None,
    phase: Literal["design_time_gate", "post_deploy_finalized"] = "post_deploy_finalized",
) -> dict[str, Any]:
    """Build the compact S13 posture mapping consumed by downstream bridges."""

    dossier = _as_dossier(deployment_dossier)
    divergence_rows = [_as_divergence(row) for row in divergences]
    proposal_rows = [_as_learning_proposal(row) for row in learning_update_proposals]
    revision = _as_envelope_revision(envelope_revision) if envelope_revision else None
    certified_delta = (
        _as_certified_delta(certified_envelope_delta)
        if certified_envelope_delta
        else None
    )
    assurance_delta = _as_assurance_delta(assurance_case_delta) if assurance_case_delta else None
    trace = _as_mape_k_trace(mape_k_trace) if mape_k_trace else None
    finalized = phase == "post_deploy_finalized"
    return {
        "schema_version": LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION,
        "phase": phase,
        "accountability_posture_ref": f"pdc://layer2/s13/{dossier.case_id}/posture",
        "deployment_dossier_ref": dossier.dossier_ref,
        "divergence_record_refs": [row.divergence_ref for row in divergence_rows]
        if finalized
        else [],
        "learning_update_proposal_refs": [row.proposal_ref for row in proposal_rows]
        if finalized
        else [],
        "envelope_revision_ref": revision.revision_ref if finalized and revision else None,
        "certified_envelope_delta_ref": (
            certified_delta.delta_ref if finalized and certified_delta else None
        ),
        "assurance_case_delta_ref": (
            assurance_delta.delta_ref if finalized and assurance_delta else None
        ),
        "attribution_status": _first_value([row.attribution_status for row in divergence_rows])
        if finalized
        else None,
        "attribution_classes": [row.attribution_class for row in divergence_rows]
        if finalized
        else [],
        "learning_change_control_classes": [
            row.change_control_class for row in proposal_rows
        ]
        if finalized
        else [],
        "lifecycle_reissue_disposition": _first_value(
            [row.lifecycle_reissue_disposition for row in proposal_rows]
        )
        if finalized
        else None,
        "envelope_revision_direction": revision.direction if finalized and revision else None,
        "assurance_case_change": (
            assurance_delta.assurance_case_change if finalized and assurance_delta else None
        ),
        "mape_k_trace_ref": trace.trace_ref if finalized and trace else None,
        "public_revision_state_ref": (
            assurance_delta.public_revision_state_ref
            if finalized and assurance_delta
            else None
        ),
        "public_accountability_note_ref": _first_value(
            [row.public_accountability_note_ref for row in proposal_rows]
        )
        if finalized
        else None,
        "action_item_status": _first_value([row.action_item_status for row in divergence_rows])
        if finalized
        else None,
        "action_item_closure_refs": [
            row.action_item_closure_ref
            for row in divergence_rows
            if row.action_item_closure_ref
        ]
        if finalized
        else [],
        "human_decision_request_refs": _dedupe(
            [ref for row in proposal_rows for ref in row.human_decision_request_refs]
        )
        if finalized
        else [],
        "human_decision_record_refs": _dedupe(
            [ref for row in proposal_rows for ref in row.human_decision_record_refs]
        )
        if finalized
        else [],
        "oversight_effectiveness_ref": _first_value(
            [row.oversight_effectiveness_ref for row in divergence_rows]
        )
        if finalized
        else None,
        "oversight_accountability_state": _first_value(
            [row.oversight_accountability_state for row in divergence_rows]
        )
        if finalized
        else None,
        "a_before_b_status": _first_value([row.a_before_b_status for row in proposal_rows])
        if finalized
        else None,
        "historical_prior_influence_refs": _dedupe(
            [ref for row in proposal_rows for ref in row.historical_prior_influence_refs]
        )
        if finalized
        else [],
        "replay_digest": _digest_payload(
            {
                "dossier": dossier.dossier_ref,
                "divergences": [row.divergence_ref for row in divergence_rows],
                "proposals": [row.proposal_ref for row in proposal_rows],
                "revision": revision.revision_ref if revision else None,
                "phase": phase,
            }
        ),
        "authority_boundary": dossier.authority_boundary.model_dump(mode="json"),
        "may_not_use_for": list(dossier.may_not_use_for),
        "canonical_outcome_effect": "post_deploy_accountability_only_not_production_authority",
        "rule_version_ref": LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION,
    }


def _as_dossier(value: DeploymentDossier | Mapping[str, object]) -> DeploymentDossier:
    if isinstance(value, DeploymentDossier):
        return value
    return DeploymentDossier.model_validate(value)


def _as_divergence(value: DivergenceRecord | Mapping[str, object]) -> DivergenceRecord:
    if isinstance(value, DivergenceRecord):
        return value
    return DivergenceRecord.model_validate(value)


def _as_learning_proposal(
    value: LearningUpdateProposal | Mapping[str, object],
) -> LearningUpdateProposal:
    if isinstance(value, LearningUpdateProposal):
        return value
    return LearningUpdateProposal.model_validate(value)


def _as_envelope_revision(
    value: EnvelopeRevision | Mapping[str, object],
) -> EnvelopeRevision:
    if isinstance(value, EnvelopeRevision):
        return value
    return EnvelopeRevision.model_validate(value)


def _as_assurance_delta(
    value: AssuranceCaseDelta | Mapping[str, object],
) -> AssuranceCaseDelta:
    if isinstance(value, AssuranceCaseDelta):
        return value
    return AssuranceCaseDelta.model_validate(value)


def _as_certified_delta(
    value: CertifiedEnvelopeDelta | Mapping[str, object],
) -> CertifiedEnvelopeDelta:
    if isinstance(value, CertifiedEnvelopeDelta):
        return value
    return CertifiedEnvelopeDelta.model_validate(value)


def _as_mape_k_trace(
    value: PostDeployMapeKTrace | Mapping[str, object],
) -> PostDeployMapeKTrace:
    if isinstance(value, PostDeployMapeKTrace):
        return value
    return PostDeployMapeKTrace.model_validate(value)


def _post_policy_data_in_pre_policy_slots(payload: Mapping[str, object]) -> bool:
    pre_policy_refs = _text_values(payload.get("pre_policy_evidence_refs"))
    post_policy_refs = set(_text_values(payload.get("post_deploy_signal_refs")))
    return any(
        ref.startswith("post-policy-")
        or ref.startswith("post_policy_")
        or ref in post_policy_refs
        for ref in pre_policy_refs
    )


def _learned_prior_in_current_evidence(payload: Mapping[str, object]) -> bool:
    current_refs = _text_values(payload.get("current_evidence_refs"))
    if any(is_historical_prior_ref(ref) for ref in current_refs):
        return True
    row = dict(payload)
    if current_refs and "data_refs" not in row:
        row["data_refs"] = current_refs
    return bool(historical_prior_claim_evidence_issues(row, claim_id=_text(row.get("claim_id"))))


def _unattributable_updates_model(payload: Mapping[str, object]) -> bool:
    attribution_status = _text(payload.get("attribution_status"))
    target = _text(payload.get("learning_update_target"))
    return (
        attribution_status in {"unattributable", "pending"}
        and payload.get("learning_allowed") is True
        and target in _MODEL_UPDATE_TARGETS
    )


def _learning_without_attribution(payload: Mapping[str, object]) -> bool:
    return (
        payload.get("learning_allowed") is True
        and _text(payload.get("attribution_status")) != "attributed"
    )


def _envelope_shrink_without_assurance(payload: Mapping[str, object]) -> bool:
    return _text(payload.get("envelope_revision_direction")) in {"shrink", "split"} and not (
        _text(payload.get("assurance_case_delta_ref"))
    )


def _b_update_before_a_baseline(payload: Mapping[str, object]) -> bool:
    return _text(payload.get("a_before_b_status")) == "fail" or (
        bool(_text_values(payload.get("post_deploy_signal_refs")))
        and not _text(payload.get("deployment_baseline_ref"))
    )


def _implementation_failure_as_theory_refutation(payload: Mapping[str, object]) -> bool:
    return (
        _text(payload.get("attribution_class")) == "implementation_failure"
        and payload.get("policy_theory_refuted") is True
        and not _text(payload.get("independent_theory_refutation_ref"))
    )


def _outcome_learning_without_counterfactual(payload: Mapping[str, object]) -> bool:
    return (
        payload.get("learning_allowed") is True
        and bool(_text(payload.get("observed_outcome_ref")))
        and not _text(payload.get("counterfactual_credibility_ref"))
    )


def _s13_mints_forbidden_authority(payload: Mapping[str, object]) -> bool:
    boundary = payload.get("authority_boundary")
    authoritative_for: list[str] = []
    may_not_use_for = _text_values(payload.get("may_not_use_for"))
    if isinstance(boundary, AuthorityBoundary):
        authoritative_for = [str(item) for item in boundary.authoritative_for]
        may_not_use_for = [*may_not_use_for, *boundary.may_not_use_for]
    elif isinstance(boundary, Mapping):
        authoritative_for = _text_values(boundary.get("authoritative_for"))
        may_not_use_for = [*may_not_use_for, *_text_values(boundary.get("may_not_use_for"))]
    if set(authoritative_for).intersection(_FORBIDDEN_AUTHORITY_SCOPE):
        return True
    return not set(may_not_use_for) >= _REQUIRED_AUTHORITY_DENIALS


def _assert_required_denials(may_not_use_for: Sequence[str]) -> None:
    if not set(may_not_use_for) >= _REQUIRED_AUTHORITY_DENIALS:
        raise ValueError("S13 authority boundary missing required denials")


def _assert_no_forbidden_authority(authority_boundary: AuthorityBoundary) -> None:
    if set(authority_boundary.authoritative_for).intersection(_FORBIDDEN_AUTHORITY_SCOPE):
        raise ValueError("S13 artifact cannot carry production or recommendation authority")
    _assert_required_denials(authority_boundary.may_not_use_for)


def _merge_denials(may_not_use_for: Sequence[str]) -> list[str]:
    return _dedupe([*may_not_use_for, *_S13_MAY_NOT_USE_FOR])


def _trace_complete(trace: PostDeployMapeKTrace) -> bool:
    return bool(
        trace.monitor_refs
        and trace.analyze_refs
        and trace.plan_refs
        and trace.execute_refs
        and trace.knowledge_refs
    )


def _action_item_closure_rate(divergences: Sequence[DivergenceRecord]) -> float:
    owned = [
        row
        for row in divergences
        if row.action_item_owner and row.action_item_due_date
    ]
    return _ratio(
        sum(
            row.action_item_status == "closed" and bool(row.action_item_closure_ref)
            for row in owned
        ),
        len(owned),
        default=1.0,
    )


def _oversight_link_rate(divergences: Sequence[DivergenceRecord]) -> float:
    review_linked = [row for row in divergences if row.human_review_ref]
    return _ratio(
        sum(bool(row.oversight_effectiveness_ref) for row in review_linked),
        len(review_linked),
        default=1.0,
    )


def _ratio(numerator: int, denominator: int, *, default: float) -> float:
    return default if denominator == 0 else numerator / denominator


def _digest_payload(
    payload: Mapping[str, Any],
    *,
    exclude: set[str] | None = None,
) -> str:
    excluded = exclude or set()
    stable_payload = {
        key: value
        for key, value in payload.items()
        if key not in excluded
    }
    rendered = json.dumps(stable_payload, sort_keys=True, default=str, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _first_value(values: Sequence[object]) -> object | None:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _text_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_text(item) for item in value if _text(item)]
    return [_text(value)] if _text(value) else []


def _dedupe(values: Sequence[Any]) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


__all__ = [
    "LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION",
    "LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_SCHEMA_VERSION",
    "S13_ACCOUNTABILITY_FLOOR_ID",
    "S13_FALSE_CLEAR_FIELDS",
    "ActionItemStatus",
    "AssuranceCaseChange",
    "AssuranceCaseDelta",
    "AttributionStatus",
    "CertifiedEnvelopeDelta",
    "DeploymentDossier",
    "DeploymentReadinessDisposition",
    "DivergenceAttributionClass",
    "DivergenceRecord",
    "EnvelopeRevision",
    "EnvelopeRevisionDirection",
    "LearningChangeControlClass",
    "LearningUpdateProposal",
    "LearningUpdateTarget",
    "LifecycleReissueDisposition",
    "OversightLinkedAccountabilityState",
    "PostDeployAccountabilitySummary",
    "PostDeployMapeKPhase",
    "PostDeployMapeKTrace",
    "build_assurance_case_delta",
    "build_certified_envelope_delta",
    "build_deployment_dossier",
    "build_envelope_revision",
    "build_learning_update_proposal",
    "build_post_deploy_mape_k_trace",
    "build_s13_accountability_authority_boundary",
    "build_s13_post_deploy_accountability_posture",
    "classify_post_deploy_divergence",
    "summarize_post_deploy_accountability",
    "verify_post_deploy_learning_authority",
]
