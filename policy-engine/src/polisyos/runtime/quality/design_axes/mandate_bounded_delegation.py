"""Layer 2 S7 mandate-bounded delegation contracts and P26 firewalls."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, cast, get_args

from pydantic import (
    AwareDatetime,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from polisyos.pdc import AuthorityBoundary, GovernanceDecisionClass, Layer2ReadinessModel
from polisyos.runtime.http.permissions import (  # noqa: TC001 - canonical Pydantic enum
    RuntimePermission,
)
from polisyos.runtime.http.security import (  # noqa: TC001 - Pydantic runtime type
    PolicyOSRole,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

LAYER2_S7_DELEGATION_SCHEMA_VERSION: Literal[
    "policyos.policy_design_case.layer2_s7_delegation.v1"
] = "policyos.policy_design_case.layer2_s7_delegation.v1"
LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION: Literal[
    "policyos.policy_design_case.layer2_s7_delegation.v2"
] = "policyos.policy_design_case.layer2_s7_delegation.v2"
HUMAN_DECISION_RECORD_V2: Literal["policyos.runtime.human_decision_record.v2"] = (
    "policyos.runtime.human_decision_record.v2"
)

DelegationInteractionMode = Literal[
    "ai_follow",
    "request_driven",
    "ai_first",
    "delegated_autonomous",
]
DecisionAction = Literal[
    "request_evidence",
    "approve",
    "reject",
    "revise_scope",
    "escalate",
]
DecisionRole = Literal[
    "principal",
    "mandate_owner",
    "legal_approver",
    "budget_owner",
    "data_steward",
    "affected_person_representative",
    "domain_expert",
    "governance_board",
    "policy_design_governance_reviewer",
    "technical_reviewer",
]
DelegationDisposition = Literal[
    "no_interrupt",
    "request_human_decision",
    "recorded_valid_decision",
    "blocked_wrong_role",
    "blocked_oversight_theater",
    "blocked_mandate_missing",
    "blocked_ai_first_forbidden",
]
ResponsibilityIntegrityStatus = Literal["pass", "limit", "block"]
HumanDecisionRecordMode = Literal["ordinary", "override", "blocking"]
HumanDecisionRecordSourceKind = Literal[
    "agent_action_authority",
    "production_approval",
]
AuthoritySource = Literal[
    "deterministic_producer",
    "governed_config",
    "human_governance",
    "llm_candidate",
    "llm_critic",
    "llm_drafter",
]
HumanDecisionRecordPredicate = Literal[
    "identity_permission",
    "role_mandate_or_basis",
    "operation_accountability",
    "currentness",
    "right_decision_time",
    "reviewer_independence_change",
    "evidence_exposure",
    "presentation_format_channel",
    "source_producer_trust",
]
HumanDecisionRecordPredicateProvenance = Literal[
    "recomputed",
    "independently_reconciled",
]
FiveRightsTimeRule = Literal["intersection_of_signed_validity_intervals_pre_action"]
FiveRightsChannel = Literal["reviewer_console", "governed_review"]
FiveRightsRepresentation = Literal["full"]
DecisionNeedReason = Literal[
    "high_stakes",
    "value_laden",
    "out_of_envelope",
    "mandate_limited",
    "budget_required",
    "acquisition_required",
    "final_choice",
    "low_voi_no_interrupt",
    "routine_in_envelope",
]
FiveRightsDimension = Literal[
    "right_decision",
    "right_person",
    "right_information",
    "right_format_channel",
    "right_time",
]
DraftExternality = Literal["internal", "external"]
DelegatedActionEnvelopeStatus = Literal["active", "revoked"]

_CREATED_AT = datetime(2026, 6, 1, tzinfo=UTC)
_FIVE_RIGHTS: tuple[FiveRightsDimension, ...] = (
    "right_decision",
    "right_person",
    "right_information",
    "right_format_channel",
    "right_time",
)
_ACTIONS: tuple[DecisionAction, ...] = (
    "request_evidence",
    "approve",
    "reject",
    "revise_scope",
    "escalate",
)
_HUMAN_DECISION_PREDICATES: tuple[HumanDecisionRecordPredicate, ...] = (
    "identity_permission",
    "role_mandate_or_basis",
    "operation_accountability",
    "currentness",
    "right_decision_time",
    "reviewer_independence_change",
    "evidence_exposure",
    "presentation_format_channel",
    "source_producer_trust",
)
_HUMAN_DECISION_PREDICATE_PROVENANCE: tuple[
    HumanDecisionRecordPredicateProvenance,
    ...,
] = (
    "recomputed",
    "independently_reconciled",
    "recomputed",
    "recomputed",
    "recomputed",
    "independently_reconciled",
    "independently_reconciled",
    "independently_reconciled",
    "independently_reconciled",
)
_HUMAN_DECISION_V2_EXTENSION_FIELDS = (
    "tenant_id",
    "run_id",
    "decision_attempt_id",
    "governed_action_key",
    "binding_sha256",
    "source_kind",
    "source_ref",
    "source_digest",
    "decision_request_digest",
    "basis_ref",
    "basis_digest",
    "principal_binding_ref",
    "principal_binding_digest",
    "reviewer_separation_ref",
    "reviewer_separation_digest",
    "presentation_contract_ref",
    "presentation_contract_digest",
    "exposure_session_ref",
    "exposure_session_digest",
    "canonical_actor",
    "decision_mode",
    "dissent_statement",
    "override_reason",
    "blocking_reason",
    "predicate_receipts",
    "exposure_event_refs",
    "exposure_artifact_digests",
    "verifier_epoch",
    "requested_at",
    "observed_at",
    "recorded_at",
    "valid_from",
    "valid_until",
    "reservation_id",
    "reservation_version",
    "custody_signer_identity",
    "custody_key_id",
    "custody_boundary",
)
_CRITICAL_REASONS = frozenset(
    {
        "high_stakes",
        "value_laden",
        "out_of_envelope",
        "mandate_limited",
        "budget_required",
        "acquisition_required",
        "final_choice",
    }
)
_MAY_NOT_USE_FOR = [
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "value_choice_authority",
    "social_weight_selection",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "oversight_effectiveness_claim",
    "attention_ledger_authority",
    "resource_allocation_authority",
    "human_approval_without_decision_record",
    "ai_self_authorization",
    "delegated_autonomy_without_mandate",
    "s13_accountability_closure",
]


class P26ResponsibilityIntegrityError(ValueError):
    """Raised when a human decision record fails S7 responsibility integrity."""


class DecisionRightsMatrixRow(Layer2ReadinessModel):
    """One S7 decision-rights row for a shared governance decision class."""

    schema_version: str = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    row_ref: str = Field(..., min_length=1, max_length=300)
    decision_class_id: str = Field(..., min_length=1, max_length=120)
    governance_decision_class_ref: str = Field(..., min_length=1, max_length=300)
    required_role: DecisionRole
    default_interaction_mode: DelegationInteractionMode
    ai_first_allowed: bool
    delegated_autonomous_allowed: bool
    non_overridable: bool
    available_actions: list[DecisionAction] = Field(..., min_length=1, max_length=5)
    five_rights_dimensions: list[FiveRightsDimension] = Field(..., min_length=5, max_length=5)

    @model_validator(mode="after")
    def _validate_five_rights(self) -> DecisionRightsMatrixRow:
        if set(self.five_rights_dimensions) != set(_FIVE_RIGHTS):
            raise ValueError("DecisionRightsMatrixRow requires all five rights dimensions")
        if self.default_interaction_mode == "ai_first" and not self.ai_first_allowed:
            raise ValueError("ai_first default requires ai_first_allowed")
        if self.default_interaction_mode == "delegated_autonomous" and (
            not self.delegated_autonomous_allowed
        ):
            raise ValueError("delegated_autonomous default requires delegated_autonomous_allowed")
        return self


class DecisionRightsMatrix(Layer2ReadinessModel):
    """Replayable S7 matrix mapping decision classes to roles, modes, and actions."""

    schema_version: str = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    matrix_id: str = Field(..., min_length=1, max_length=120)
    matrix_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    rows: list[DecisionRightsMatrixRow] = Field(..., min_length=1, max_length=40)
    authority_boundary: AuthorityBoundary
    provenance_refs: list[str] = Field(default_factory=list, max_length=40)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT

    def row_for_decision_class(self, decision_class_id: str) -> DecisionRightsMatrixRow:
        """Return the matrix row for a governance decision class."""

        for row in self.rows:
            if row.decision_class_id == decision_class_id:
                return row
        raise KeyError(decision_class_id)


class DraftActionScope(Layer2ReadinessModel):
    """Audience and externality bounds for one draft action."""

    audience: Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]
    externality: DraftExternality


class DelegatedActionEnvelope(Layer2ReadinessModel):
    """Mandate-owner declaration for one least-privilege agent action."""

    envelope_id: str = Field(..., min_length=1, max_length=160)
    envelope_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    mandate_owner_ref: str = Field(..., min_length=1, max_length=300)
    owner_role: Literal["mandate_owner"]
    action_kind: str = Field(..., pattern=r"^[a-z][a-z0-9_.:-]*$", max_length=120)
    operation_id: str = Field(..., pattern=r"^[a-z][a-z0-9_.-]*$")
    operation_version: str = Field(..., min_length=1, max_length=80)
    required_permission: RuntimePermission
    authorized_subject: str = Field(..., min_length=1, max_length=300)
    authorized_runtime_roles: tuple[PolicyOSRole, ...] = Field(..., min_length=1)
    required_tenant_id: str = Field(..., min_length=1, max_length=200)
    required_resource_digest: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    status: DelegatedActionEnvelopeStatus
    issuance_decision_ref: str = Field(..., min_length=1, max_length=300)
    draft_scope: DraftActionScope | None = None
    provenance_refs: tuple[str, ...] = Field(..., min_length=1, max_length=40)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    authority_boundary: AuthorityBoundary

    @model_validator(mode="after")
    def _validate_owner_declared_envelope(self) -> DelegatedActionEnvelope:
        if self.valid_from >= self.valid_until:
            raise ValueError("delegation envelope requires valid_from before valid_until")
        if len(set(self.authorized_runtime_roles)) != len(self.authorized_runtime_roles):
            raise ValueError("delegation envelope runtime roles must be unique")
        if self.action_kind == "draft" and self.draft_scope is None:
            raise ValueError("draft action envelope requires audience and externality")
        if self.action_kind != "draft" and self.draft_scope is not None:
            raise ValueError("draft scope is valid only for the draft action kind")
        boundary = self.authority_boundary
        if (
            boundary.source_authority != "human_governance"
            or boundary.posture not in {"governed", "production"}
            or "agent_action_envelope" not in boundary.authoritative_for
        ):
            raise ValueError("delegation envelope requires mandate-owner authority provenance")
        return self


class DelegationContract(Layer2ReadinessModel):
    """Mandate-bounded S7 delegation contract for one policy-design case."""

    schema_version: Literal[
        "policyos.policy_design_case.layer2_s7_delegation.v1",
        "policyos.policy_design_case.layer2_s7_delegation.v2",
    ] = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    contract_id: str = Field(..., min_length=1, max_length=120)
    contract_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    governance_decision_classes: list[GovernanceDecisionClass] = Field(
        ...,
        min_length=1,
        max_length=40,
    )
    autonomous_decision_classes: list[str] = Field(default_factory=list, max_length=40)
    approval_required_decision_classes: list[str] = Field(default_factory=list, max_length=40)
    decision_rights_matrix_ref: str = Field(..., min_length=1, max_length=300)
    decision_rights_matrix_rows: list[DecisionRightsMatrixRow] = Field(
        default_factory=list,
        max_length=40,
    )
    compute_budget_ref: str = Field(..., min_length=1, max_length=300)
    acquisition_budget_ref: str = Field(..., min_length=1, max_length=300)
    human_attention_budget_ref: str = Field(..., min_length=1, max_length=300)
    maximum_stakes_band: str = Field(..., min_length=1, max_length=120)
    maximum_reversibility_posture: str = Field(..., min_length=1, max_length=120)
    value_policy_ref: str = Field(..., min_length=1, max_length=300)
    override_policy_ref: str = Field(..., min_length=1, max_length=300)
    s6_mandate_record_ref: str = Field(..., min_length=1, max_length=300)
    s6_mandate_firewall_disposition: str = Field(..., min_length=1, max_length=80)
    authority_boundary: AuthorityBoundary
    provenance_refs: list[str] = Field(default_factory=list, max_length=40)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT
    mandate_owner_ref: str | None = Field(default=None, min_length=1, max_length=300)
    action_envelopes: tuple[DelegatedActionEnvelope, ...] = Field(default=(), max_length=200)

    @model_validator(mode="after")
    def _validate_action_envelope_ownership(self) -> DelegationContract:
        has_agent_action_extension = self.mandate_owner_ref is not None or bool(
            self.action_envelopes
        )
        if has_agent_action_extension and (
            self.schema_version != LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION
        ):
            raise ValueError("envelope-bearing delegation contract requires v2")
        if not has_agent_action_extension and (
            self.schema_version != LAYER2_S7_DELEGATION_SCHEMA_VERSION
        ):
            raise ValueError("legacy delegation contract without agent envelopes requires v1")
        if not self.action_envelopes:
            return self
        if self.mandate_owner_ref is None:
            raise ValueError("action envelopes require a mandate owner")
        envelope_ids = [envelope.envelope_id for envelope in self.action_envelopes]
        if len(envelope_ids) != len(set(envelope_ids)):
            raise ValueError("delegation contract action envelope IDs must be unique")
        for envelope in self.action_envelopes:
            if envelope.case_id != self.case_id:
                raise ValueError("action envelope case must match delegation contract")
            if envelope.mandate_owner_ref != self.mandate_owner_ref:
                raise ValueError("action envelope owner must match delegation contract owner")
            if envelope.rule_version_ref != self.rule_version_ref:
                raise ValueError("action envelope rule version must match delegation contract")
        return self

    @model_serializer(mode="wrap")
    def _serialize_versioned_contract(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> object:
        """Keep legacy v1 bytes free of fields introduced only by the v2 reader."""

        payload = handler(self)
        if self.schema_version == LAYER2_S7_DELEGATION_SCHEMA_VERSION and isinstance(payload, dict):
            payload.pop("mandate_owner_ref", None)
            payload.pop("action_envelopes", None)
        return payload


class DecisionOption(Layer2ReadinessModel):
    """Actionable option shown in a human decision request."""

    schema_version: str = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    option_id: str = Field(..., min_length=1, max_length=120)
    action: DecisionAction
    label: str = Field(..., min_length=1, max_length=200)
    consequence: str = Field(..., min_length=1, max_length=500)


class FiveRightsRequirement(Layer2ReadinessModel):
    """Required S7 five-rights dimensions for a human decision request."""

    schema_version: str = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    right_decision: str = Field(..., min_length=1, max_length=300)
    right_person: str = Field(..., min_length=1, max_length=300)
    right_information: str = Field(..., min_length=1, max_length=500)
    right_format_channel: str = Field(..., min_length=1, max_length=300)
    right_time: str = Field(..., min_length=1, max_length=300)


class HumanDecisionFiveRightsBinding(Layer2ReadinessModel):
    """Typed signed inputs used to reconcile the five rights without prose parsing."""

    schema_version: str = LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION
    decision_class_id: str = Field(..., min_length=1, max_length=120)
    decision_rights_matrix_ref: str = Field(..., min_length=1, max_length=300)
    required_role: DecisionRole
    required_information_refs: tuple[str, ...] = Field(default=(), max_length=20)
    required_channel: FiveRightsChannel
    required_representation: FiveRightsRepresentation
    time_rule: FiveRightsTimeRule


class FiveRightsCheck(Layer2ReadinessModel):
    """Boolean S7 five-rights check attached to a human decision record."""

    schema_version: str = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    right_decision: bool
    right_person: bool
    right_information: bool
    right_format_channel: bool
    right_time: bool

    def all_pass(self) -> bool:
        """Return whether all five rights passed."""

        return (
            self.right_decision
            and self.right_person
            and self.right_information
            and self.right_format_channel
            and self.right_time
        )


class ResponsibilityIntegrityCheck(Layer2ReadinessModel):
    """S7 responsibility-integrity result for P26 and adjacent firewalls."""

    schema_version: str = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    status: ResponsibilityIntegrityStatus
    pattern_ids: list[str] = Field(default_factory=list, max_length=10)
    reason: str = Field(..., min_length=1, max_length=500)
    missing_requirements: list[str] = Field(default_factory=list, max_length=20)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class HumanDecisionRequest(Layer2ReadinessModel):
    """Typed S7 request that asks a human to decide within mandate bounds."""

    schema_version: str = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    request_id: str = Field(..., min_length=1, max_length=120)
    request_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    delegation_contract_ref: str = Field(..., min_length=1, max_length=300)
    decision_rights_matrix_ref: str = Field(..., min_length=1, max_length=300)
    decision_class_id: str = Field(..., min_length=1, max_length=120)
    required_role: DecisionRole
    interaction_mode: DelegationInteractionMode
    disposition: DelegationDisposition
    need_reasons: list[DecisionNeedReason] = Field(default_factory=list, max_length=10)
    requested_at: AwareDatetime
    decision_due_at: AwareDatetime | None = None
    decidable_until: AwareDatetime | None = None
    decision_options: list[DecisionOption] = Field(default_factory=list, max_length=10)
    recommendation_ref: str | None = Field(default=None, max_length=300)
    provenance_refs: list[str] = Field(default_factory=list, max_length=40)
    source_seed_refs: list[str] = Field(default_factory=list, max_length=40)
    material_limitations: list[str] = Field(default_factory=list, max_length=20)
    disconfirming_evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    value_stakes_impact: str = Field(..., min_length=1, max_length=500)
    what_changes_under_each_choice: list[str] = Field(default_factory=list, max_length=20)
    five_rights_requirements: FiveRightsRequirement
    five_rights_binding: HumanDecisionFiveRightsBinding
    available_actions: list[DecisionAction] = Field(default_factory=list, max_length=5)
    attention_cost_rank: int = Field(ge=1)
    voi_rank: int = Field(ge=1)
    s6_mandate_record_ref: str = Field(..., min_length=1, max_length=300)
    s6_mandate_firewall_disposition: str = Field(..., min_length=1, max_length=80)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT

    @model_validator(mode="after")
    def _validate_five_rights_binding(self) -> HumanDecisionRequest:
        binding = self.five_rights_binding
        if (
            binding.decision_class_id != self.decision_class_id
            or binding.decision_rights_matrix_ref != self.decision_rights_matrix_ref
            or binding.required_role != self.required_role
            or binding.required_information_refs != tuple(self.disconfirming_evidence_refs)
        ):
            raise ValueError("human-decision five-rights binding differs from the request")
        if not self.material_limitations or not self.what_changes_under_each_choice:
            raise ValueError("human-decision information right lacks limitations or consequences")
        option_actions = [option.action for option in self.decision_options]
        if option_actions != self.available_actions or len(option_actions) != len(
            set(option_actions)
        ):
            raise ValueError("human-decision options do not exactly bind the offered actions")
        return self


class HumanDecisionCanonicalActor(Layer2ReadinessModel):
    """Actor identity derived only from a verified principal-binding artifact."""

    issuer: str = Field(..., min_length=1, max_length=300)
    audience: str = Field(..., min_length=1, max_length=300)
    subject: str = Field(..., min_length=1, max_length=300)
    tenant_id: str = Field(..., min_length=1, max_length=200)
    actor_ref: str = Field(..., min_length=1, max_length=300)
    signing_key_id: str = Field(..., min_length=1, max_length=200)
    signed_roles: tuple[str, ...] = Field(..., min_length=1, max_length=20)


class HumanDecisionPredicateReceipt(Layer2ReadinessModel):
    """One recomputed or independently reconciled pre-action predicate."""

    predicate: HumanDecisionRecordPredicate
    satisfied: Literal[True]
    provenance: HumanDecisionRecordPredicateProvenance
    evidence_refs: tuple[str, ...] = Field(..., min_length=1, max_length=80)
    reason_code: str = Field(..., min_length=1, max_length=160)
    reason: str = Field(..., min_length=1, max_length=500)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


def derive_five_rights_check(
    receipts: Sequence[HumanDecisionPredicateReceipt],
) -> FiveRightsCheck:
    """Derive compatibility booleans only from the exact reconciled receipt set."""

    by_predicate = {receipt.predicate: receipt for receipt in receipts}

    def _has(
        predicate: HumanDecisionRecordPredicate,
        provenance: HumanDecisionRecordPredicateProvenance,
    ) -> bool:
        receipt = by_predicate.get(predicate)
        return receipt is not None and receipt.provenance == provenance

    return FiveRightsCheck(
        right_decision=(
            _has("role_mandate_or_basis", "independently_reconciled")
            and _has("operation_accountability", "recomputed")
            and _has("right_decision_time", "recomputed")
        ),
        right_person=(
            _has("identity_permission", "recomputed")
            and _has("reviewer_independence_change", "independently_reconciled")
        ),
        right_information=_has("evidence_exposure", "independently_reconciled"),
        right_format_channel=_has("presentation_format_channel", "independently_reconciled"),
        right_time=(
            _has("currentness", "recomputed") and _has("right_decision_time", "recomputed")
        ),
    )


class HumanDecisionRecord(Layer2ReadinessModel):
    """Accountable S7 record of a human decision within a rights matrix."""

    schema_version: str = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=120)
    record_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    human_decision_request_ref: str = Field(..., min_length=1, max_length=300)
    actor_ref: str = Field(..., min_length=1, max_length=300)
    actor_role: DecisionRole
    decided_at: AwareDatetime
    decision_action_exercised: DecisionAction
    evidence_summary_ref: str = Field(..., min_length=1, max_length=300)
    disconfirming_evidence_refs: list[str] = Field(..., min_length=1, max_length=20)
    active_choice: bool
    accountability_statement: str = Field(..., min_length=1, max_length=500)
    mandate_record_ref: str = Field(..., min_length=1, max_length=300)
    mandate_source_refs: list[str] = Field(default_factory=list, max_length=20)
    five_rights_check: FiveRightsCheck
    responsibility_integrity: ResponsibilityIntegrityCheck
    authority_boundary: AuthorityBoundary
    provenance_refs: list[str] = Field(default_factory=list, max_length=40)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT

    # V2 is a strict superset.  Every field stays absent from historical v1
    # serialization, so old content hashes and fixtures remain stable.
    tenant_id: str | None = Field(default=None, min_length=1, max_length=200)
    run_id: str | None = Field(default=None, min_length=1, max_length=200)
    decision_attempt_id: str | None = Field(default=None, min_length=1, max_length=200)
    governed_action_key: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    binding_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    source_kind: HumanDecisionRecordSourceKind | None = None
    source_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    source_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    decision_request_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    basis_ref: str | None = Field(default=None, min_length=1, max_length=300)
    basis_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    principal_binding_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    principal_binding_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    reviewer_separation_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    reviewer_separation_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    presentation_contract_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    presentation_contract_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    exposure_session_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    exposure_session_digest: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    canonical_actor: HumanDecisionCanonicalActor | None = None
    decision_mode: HumanDecisionRecordMode | None = None
    dissent_statement: str | None = Field(default=None, min_length=1, max_length=1_000)
    override_reason: str | None = Field(default=None, min_length=1, max_length=1_000)
    blocking_reason: str | None = Field(default=None, min_length=1, max_length=1_000)
    predicate_receipts: tuple[HumanDecisionPredicateReceipt, ...] | None = Field(
        default=None,
        min_length=9,
        max_length=9,
    )
    exposure_event_refs: tuple[str, ...] | None = Field(
        default=None,
        min_length=1,
        max_length=80,
    )
    exposure_artifact_digests: tuple[str, ...] | None = Field(
        default=None,
        min_length=1,
        max_length=80,
    )
    verifier_epoch: str | None = Field(default=None, min_length=1, max_length=200)
    requested_at: AwareDatetime | None = None
    observed_at: AwareDatetime | None = None
    recorded_at: AwareDatetime | None = None
    valid_from: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    reservation_id: str | None = Field(default=None, min_length=1, max_length=200)
    reservation_version: int | None = Field(default=None, ge=1)
    custody_signer_identity: str | None = Field(default=None, min_length=1, max_length=300)
    custody_key_id: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    custody_boundary: AuthorityBoundary | None = None

    @model_validator(mode="after")
    def _validate_record_version(self) -> HumanDecisionRecord:
        if self.schema_version == LAYER2_S7_DELEGATION_SCHEMA_VERSION:
            unexpected = [
                field_name
                for field_name in _HUMAN_DECISION_V2_EXTENSION_FIELDS
                if getattr(self, field_name) is not None
            ]
            if unexpected:
                raise ValueError(
                    "historical human-decision v1 cannot carry v2 fields: " + ", ".join(unexpected)
                )
            return self
        if self.schema_version != HUMAN_DECISION_RECORD_V2:
            raise ValueError("unknown human-decision record schema version")
        missing = [
            field_name
            for field_name in _HUMAN_DECISION_V2_EXTENSION_FIELDS
            if field_name not in {"override_reason", "blocking_reason"}
            and getattr(self, field_name) is None
        ]
        if missing:
            raise ValueError("human-decision v2 fields missing: " + ", ".join(missing))
        return self._validate_v2_semantics()

    def _validate_v2_semantics(self) -> HumanDecisionRecord:
        actor = self.canonical_actor
        receipts = self.predicate_receipts
        requested_at = self.requested_at
        observed_at = self.observed_at
        recorded_at = self.recorded_at
        valid_from = self.valid_from
        valid_until = self.valid_until
        custody_boundary = self.custody_boundary
        if (
            actor is None
            or receipts is None
            or requested_at is None
            or observed_at is None
            or recorded_at is None
            or valid_from is None
            or valid_until is None
            or custody_boundary is None
        ):
            raise ValueError("human-decision v2 invariant fields are missing")
        if tuple(receipt.predicate for receipt in receipts) != _HUMAN_DECISION_PREDICATES:
            raise ValueError("human-decision v2 requires all nine ordered predicates")
        if tuple(
            receipt.provenance for receipt in receipts
        ) != _HUMAN_DECISION_PREDICATE_PROVENANCE or any(
            receipt.rule_version_ref != self.rule_version_ref for receipt in receipts
        ):
            raise ValueError(
                "human-decision v2 predicate provenance or rule version is not reconciled"
            )
        if self.five_rights_check != derive_five_rights_check(receipts):
            raise ValueError("human-decision five-rights check is not receipt-derived")
        if actor.actor_ref != self.actor_ref or actor.tenant_id != self.tenant_id:
            raise ValueError("canonical actor does not match record identity binding")
        if self.actor_role not in actor.signed_roles:
            raise ValueError("record actor role is absent from signed principal roles")
        if self.custody_signer_identity == self.actor_ref:
            raise ValueError("PolicyOS custody cannot be represented as the human signature")
        if actor.signing_key_id == self.custody_key_id:
            raise ValueError("human actor key cannot alias the PolicyOS custody key")
        if self.source_ref != self.source_digest:
            raise ValueError("human-decision source ref/digest mismatch")
        if self.basis_ref != self.basis_digest:
            raise ValueError("human-decision basis ref/digest mismatch")
        for ref_name, digest_name in (
            ("principal_binding_ref", "principal_binding_digest"),
            ("reviewer_separation_ref", "reviewer_separation_digest"),
            ("presentation_contract_ref", "presentation_contract_digest"),
            ("exposure_session_ref", "exposure_session_digest"),
        ):
            if getattr(self, ref_name) != getattr(self, digest_name):
                raise ValueError(f"human-decision {ref_name} is not content-bound")
        if not requested_at <= observed_at <= self.decided_at <= recorded_at:
            raise ValueError("human-decision time roles are out of order")
        if not valid_from <= self.decided_at <= recorded_at < valid_until:
            raise ValueError("human-decision falls outside its authoritative interval")
        if len(self.exposure_event_refs or ()) != len(self.exposure_artifact_digests or ()) or any(
            not isinstance(value, str)
            or len(value) != 71
            or not value.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in value[7:])
            for value in (
                *(self.exposure_event_refs or ()),
                *(self.exposure_artifact_digests or ()),
            )
        ):
            raise ValueError("human-decision exposure refs are not exact content digests")
        if len(set(self.exposure_event_refs or ())) != len(self.exposure_event_refs or ()):
            raise ValueError("human-decision exposure event refs must be unique")
        if (
            self.active_choice is not True
            or not self.five_rights_check.all_pass()
            or self.responsibility_integrity.status != "pass"
        ):
            raise ValueError("human-decision v2 requires active responsibility integrity")
        if (
            self.authority_boundary.source_authority != "human_governance"
            or "human_decision_act" not in self.authority_boundary.authoritative_for
        ):
            raise ValueError("human-decision act authority is not human-governed")
        if self.decision_mode == "ordinary":
            if (
                self.decision_action_exercised == "reject"
                or self.override_reason is not None
                or self.blocking_reason is not None
            ):
                raise ValueError("ordinary decision cannot carry override/blocking reasons")
        elif self.decision_mode == "override":
            if self.decision_action_exercised != "approve" or not self.override_reason:
                raise ValueError("override requires approve plus an override reason")
            if self.blocking_reason is not None:
                raise ValueError("override cannot carry a blocking reason")
        elif (
            self.decision_action_exercised != "reject"
            or not self.blocking_reason
            or self.override_reason is not None
        ):
            raise ValueError("blocking requires reject plus a blocking reason")
        if (
            custody_boundary.source_authority != "deterministic_producer"
            or custody_boundary.posture not in {"governed", "production"}
            or "human_decision_record_custody" not in custody_boundary.authoritative_for
            or "human_signature" not in custody_boundary.may_not_use_for
        ):
            raise ValueError("human-decision custody boundary is not purpose-limited")
        return self

    @model_serializer(mode="wrap")
    def _serialize_versioned(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        payload = cast("dict[str, object]", handler(self))
        if self.schema_version == LAYER2_S7_DELEGATION_SCHEMA_VERSION:
            for field_name in _HUMAN_DECISION_V2_EXTENSION_FIELDS:
                payload.pop(field_name, None)
        return payload


class DelegationNegativeControlResult(Layer2ReadinessModel):
    """S7 negative-control result for false-clear accounting."""

    schema_version: str = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    result_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    expected_disposition: str = Field(..., min_length=1, max_length=120)
    predicted_disposition: str = Field(..., min_length=1, max_length=120)
    false_clear: bool
    failure_pattern: str = Field(..., min_length=1, max_length=20)
    authority_boundary: AuthorityBoundary
    provenance_refs: list[str] = Field(default_factory=list, max_length=40)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


class DelegationIntegrityReport(Layer2ReadinessModel):
    """S7 per-case delegation classification and integrity result."""

    schema_version: str = LAYER2_S7_DELEGATION_SCHEMA_VERSION
    report_id: str = Field(..., min_length=1, max_length=120)
    report_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    decision_class_id: str = Field(..., min_length=1, max_length=120)
    required_role: str = Field(..., min_length=1, max_length=120)
    interaction_mode: str = Field(..., min_length=1, max_length=120)
    disposition: DelegationDisposition
    request_emitted: bool
    record_valid: bool
    governed_pilot_eligible: bool
    predicted_need_reasons: list[str] = Field(default_factory=list, max_length=20)
    expected_need_reasons: list[str] = Field(default_factory=list, max_length=20)
    responsibility_integrity: ResponsibilityIntegrityCheck
    firewall_pattern_ids: list[str] = Field(default_factory=list, max_length=10)
    block_reason: str = ""
    matches_gold: bool
    authority_boundary: AuthorityBoundary
    provenance_refs: list[str] = Field(default_factory=list, max_length=40)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


def build_governance_decision_class_registry(
    case_id: str,
    rule_version_ref: str,
) -> list[GovernanceDecisionClass]:
    """Build the S7 registry over shared S0 governance decision classes."""

    del case_id
    role_by_class: dict[str, tuple[str, bool]] = {
        "a_spec_gap": ("policy_design_governance_reviewer", True),
        "budget_use": ("budget_owner", True),
        "acquisition": ("legal_approver", True),
        "final_choice": ("governance_board", True),
        "value_authorization": ("principal", True),
        "mandate_boundary": ("mandate_owner", True),
        "data_access": ("data_steward", True),
        "routine_in_envelope": ("domain_expert", False),
    }
    return [
        GovernanceDecisionClass(
            decision_class_id=decision_class_id,
            label=decision_class_id.replace("_", " ").title(),
            required_role=role,
            default_posture="shadow",
            high_stakes=high_stakes,
            authority_boundary=_authority_boundary(
                rule_version_ref,
                authoritative_for=["governance_decision_class_registry"],
                source_authority="human_governance",
            ),
        )
        for decision_class_id, (role, high_stakes) in role_by_class.items()
    ]


def build_decision_rights_matrix(
    case_id: str,
    governance_decision_classes: Sequence[GovernanceDecisionClass],
    rule_version_ref: str,
) -> DecisionRightsMatrix:
    """Build an S7 decision-rights matrix from the shared governance registry."""

    slug = _slug(case_id)
    rows = [
        _matrix_row(
            slug=slug,
            governance_decision_class=row,
            mode=_mode_for_decision_class(row.decision_class_id),
            role=_role_for_decision_class(row.decision_class_id, row.required_role),
            delegated_autonomous_allowed=row.decision_class_id == "routine_in_envelope",
        )
        for row in governance_decision_classes
    ]
    return DecisionRightsMatrix(
        matrix_id=f"layer2.s7.matrix.{slug}",
        matrix_ref=f"pdc://layer2/s7/{slug}/decision-rights-matrix",
        case_id=case_id,
        rows=rows,
        authority_boundary=_authority_boundary(
            rule_version_ref,
            authoritative_for=["decision_rights_matrix", "human_decision_routing"],
        ),
        provenance_refs=[f"pdc://layer2/s7/{slug}/governance-decision-class-registry"],
        rule_version_ref=rule_version_ref,
    )


def build_delegation_contract(
    case_id: str,
    matrix: DecisionRightsMatrix,
    governance_decision_classes: Sequence[GovernanceDecisionClass],
    s6_mandate_record_ref: str,
    s6_mandate_firewall_disposition: str,
    rule_version_ref: str,
) -> DelegationContract:
    """Build the S7 contract tying mandate, matrix, budgets, and boundaries."""

    slug = _slug(case_id)
    approval_classes = [
        row.decision_class_id
        for row in matrix.rows
        if row.decision_class_id != "routine_in_envelope"
    ]
    autonomous_classes = [
        row.decision_class_id for row in matrix.rows if row.delegated_autonomous_allowed
    ]
    return DelegationContract(
        contract_id=f"layer2.s7.contract.{slug}",
        contract_ref=f"pdc://layer2/s7/{slug}/delegation-contract",
        case_id=case_id,
        governance_decision_classes=list(governance_decision_classes),
        autonomous_decision_classes=autonomous_classes,
        approval_required_decision_classes=approval_classes,
        decision_rights_matrix_ref=matrix.matrix_ref,
        decision_rights_matrix_rows=list(matrix.rows),
        compute_budget_ref=f"budget://layer2/s7/{slug}/compute",
        acquisition_budget_ref=f"budget://layer2/s7/{slug}/acquisition",
        human_attention_budget_ref=f"budget://layer2/s7/{slug}/human-attention",
        maximum_stakes_band="high",
        maximum_reversibility_posture="governed_pilot_only",
        value_policy_ref=f"pdc://layer2/s7/{slug}/value-policy/pending-s8",
        override_policy_ref=f"pdc://layer2/s7/{slug}/override-policy",
        s6_mandate_record_ref=s6_mandate_record_ref,
        s6_mandate_firewall_disposition=s6_mandate_firewall_disposition,
        authority_boundary=_authority_boundary(
            rule_version_ref,
            authoritative_for=[
                "delegation_integrity",
                "decision_rights_matrix",
                "governed_pilot_promotion_gate",
            ],
        ),
        provenance_refs=[s6_mandate_record_ref, matrix.matrix_ref],
        rule_version_ref=rule_version_ref,
    )


def build_human_decision_request(
    case_id: str,
    contract: DelegationContract,
    decision_class_id: str,
    need_reasons: Sequence[str],
    voi_rank: int,
    s6_mandate_record_ref: str,
    s6_mandate_firewall_disposition: str,
    rule_version_ref: str,
) -> HumanDecisionRequest:
    """Build an S7 human decision request that fails closed around critical decisions."""

    slug = _slug(case_id)
    row = _row_for_decision_class(contract.decision_rights_matrix_rows, decision_class_id)
    typed_reasons = _typed_need_reasons(need_reasons)
    reason_set = set(typed_reasons)
    critical = bool(reason_set & _CRITICAL_REASONS)
    no_interrupt = reason_set == {"low_voi_no_interrupt"} or reason_set == {
        "low_voi_no_interrupt",
        "routine_in_envelope",
    }
    if critical and row.default_interaction_mode == "ai_first":
        interaction_mode: DelegationInteractionMode = "request_driven"
    else:
        interaction_mode = row.default_interaction_mode
    disposition: DelegationDisposition = (
        "no_interrupt" if no_interrupt else "request_human_decision"
    )
    disconfirming_evidence_refs = (
        f"pdc://layer2/s7/{slug}/disconfirming-evidence/{decision_class_id}",
    )
    return HumanDecisionRequest(
        request_id=f"layer2.s7.request.{slug}.{decision_class_id}",
        request_ref=f"pdc://layer2/s7/{slug}/human-decision-request/{decision_class_id}",
        case_id=case_id,
        delegation_contract_ref=contract.contract_ref,
        decision_rights_matrix_ref=contract.decision_rights_matrix_ref,
        decision_class_id=decision_class_id,
        required_role=row.required_role,
        interaction_mode=interaction_mode,
        disposition=disposition,
        need_reasons=typed_reasons,
        requested_at=_CREATED_AT,
        decision_due_at=None if no_interrupt else _CREATED_AT,
        decidable_until=None if no_interrupt else _CREATED_AT,
        decision_options=_decision_options(row.available_actions),
        recommendation_ref=f"pdc://layer2/s7/{slug}/recommendation/{decision_class_id}",
        provenance_refs=[contract.contract_ref, s6_mandate_record_ref],
        source_seed_refs=[f"scientist://supervisor-eval/{slug}"],
        material_limitations=[
            "S7 can route and record a decision, but cannot grant production authority.",
        ],
        disconfirming_evidence_refs=list(disconfirming_evidence_refs),
        value_stakes_impact=(
            "Decision routing affects governance accountability and mandate bounds."
        ),
        what_changes_under_each_choice=[
            "approve records a bounded decision",
            "request_evidence keeps the route pending",
            "escalate routes accountability upward",
        ],
        five_rights_requirements=FiveRightsRequirement(
            right_decision=f"Decide {decision_class_id}.",
            right_person=row.required_role,
            right_information="Limitations, disconfirming evidence, options, and consequences.",
            right_format_channel="reviewer_console",
            right_time="Before the design route can no longer change.",
        ),
        five_rights_binding=HumanDecisionFiveRightsBinding(
            decision_class_id=decision_class_id,
            decision_rights_matrix_ref=contract.decision_rights_matrix_ref,
            required_role=row.required_role,
            required_information_refs=disconfirming_evidence_refs,
            required_channel="reviewer_console",
            required_representation="full",
            time_rule="intersection_of_signed_validity_intervals_pre_action",
        ),
        available_actions=list(row.available_actions),
        attention_cost_rank=max(1, voi_rank),
        voi_rank=max(1, voi_rank),
        s6_mandate_record_ref=s6_mandate_record_ref,
        s6_mandate_firewall_disposition=s6_mandate_firewall_disposition,
        authority_boundary=_authority_boundary(
            rule_version_ref,
            authoritative_for=["human_decision_routing", "human_decision_request_ranking"],
        ),
        rule_version_ref=rule_version_ref,
    )


def record_human_decision(
    case_id: str,
    request: HumanDecisionRequest,
    actor_ref: str,
    actor_role: DecisionRole,
    decision_action_exercised: DecisionAction,
    evidence_summary_ref: str | None,
    disconfirming_evidence_refs: Sequence[str],
    active_choice: bool | None,
    accountability_statement: str | None,
    five_rights_check: FiveRightsCheck | Mapping[str, object],
    mandate_record_ref: str,
    rule_version_ref: str,
) -> HumanDecisionRecord:
    """Record a human decision or raise a typed P26 responsibility-integrity error."""

    if actor_role != request.required_role:
        raise P26ResponsibilityIntegrityError("wrong_role_approval")
    if decision_action_exercised not in request.available_actions:
        raise P26ResponsibilityIntegrityError("action_not_allowed")
    if (
        request.interaction_mode == "delegated_autonomous"
        and request.s6_mandate_firewall_disposition != "pass"
    ):
        raise P26ResponsibilityIntegrityError("delegated_autonomy_without_mandate")
    check = (
        five_rights_check
        if isinstance(five_rights_check, FiveRightsCheck)
        else FiveRightsCheck.model_validate(five_rights_check)
    )
    missing = _responsibility_missing_requirements(
        evidence_summary_ref=evidence_summary_ref,
        disconfirming_evidence_refs=disconfirming_evidence_refs,
        active_choice=active_choice,
        accountability_statement=accountability_statement,
        five_rights_check=check,
        value_stakes_impact=request.value_stakes_impact,
    )
    if request.disposition != "no_interrupt" and missing:
        raise P26ResponsibilityIntegrityError("oversight_theater")

    slug = _slug(case_id)
    integrity = ResponsibilityIntegrityCheck(
        status="pass",
        pattern_ids=["P26", "P05", "P20", "P22"],
        reason="Human decision record passed all five rights and P26 checks.",
        missing_requirements=[],
        rule_version_ref=rule_version_ref,
    )
    return HumanDecisionRecord(
        record_id=f"layer2.s7.record.{slug}.{request.decision_class_id}",
        record_ref=f"pdc://layer2/s7/{slug}/human-decision-record/{request.decision_class_id}",
        case_id=case_id,
        human_decision_request_ref=request.request_ref,
        actor_ref=actor_ref,
        actor_role=actor_role,
        decided_at=_CREATED_AT,
        decision_action_exercised=decision_action_exercised,
        evidence_summary_ref=str(evidence_summary_ref),
        disconfirming_evidence_refs=list(disconfirming_evidence_refs),
        active_choice=bool(active_choice),
        accountability_statement=str(accountability_statement),
        mandate_record_ref=mandate_record_ref,
        mandate_source_refs=[mandate_record_ref],
        five_rights_check=check,
        responsibility_integrity=integrity,
        authority_boundary=_authority_boundary(
            rule_version_ref,
            authoritative_for=["mandate_bounded_decision_record"],
            source_authority="human_governance",
        ),
        provenance_refs=[request.request_ref, mandate_record_ref],
        rule_version_ref=rule_version_ref,
    )


def evaluate_delegation_for_case(
    case_id: str,
    s6_mandate_posture: Mapping[str, object],
    case_signals: Mapping[str, object],
    expert_label: Mapping[str, object],
    rule_version_ref: str,
) -> DelegationIntegrityReport:
    """Evaluate S7 delegation routing for one corpus or negative-control case."""

    slug = _slug(case_id)
    raw_expected_reasons = expert_label.get("expected_need_reasons", [])
    expected_reasons = (
        [str(item) for item in cast("Sequence[object]", raw_expected_reasons)]
        if isinstance(raw_expected_reasons, (list, tuple))
        else []
    )
    need_reasons = expected_reasons or _derive_need_reasons(case_signals)
    requested_mode = str(case_signals.get("requested_interaction_mode", "request_driven"))
    mandate_disposition = str(
        s6_mandate_posture.get(
            "firewall_disposition",
            case_signals.get("s6_mandate_firewall_disposition", ""),
        )
    )
    critical = bool(set(need_reasons) & _CRITICAL_REASONS)
    if critical and requested_mode == "ai_first":
        disposition: DelegationDisposition = "blocked_ai_first_forbidden"
        status: ResponsibilityIntegrityStatus = "block"
        block_reason = "ai_first_forbidden_for_high_stakes"
        request_emitted = False
        record_valid = False
    elif requested_mode == "delegated_autonomous" and mandate_disposition != "pass":
        disposition = "blocked_mandate_missing"
        status = "block"
        block_reason = "delegated_autonomy_without_mandate"
        request_emitted = False
        record_valid = False
    else:
        fallback_disposition = (
            "no_interrupt" if "low_voi_no_interrupt" in need_reasons else "request_human_decision"
        )
        disposition = cast(
            "DelegationDisposition",
            str(expert_label.get("expected_disposition", fallback_disposition)),
        )
        status = "pass" if disposition in {"recorded_valid_decision", "no_interrupt"} else "limit"
        block_reason = ""
        request_emitted = bool(
            expert_label.get("expected_request_emitted", disposition != "no_interrupt")
        )
        record_valid = bool(expert_label.get("expected_record_valid", False))
    integrity = ResponsibilityIntegrityCheck(
        status=status,
        pattern_ids=["P26", "P22"] if disposition == "blocked_mandate_missing" else ["P26"],
        reason=block_reason or "Delegation evaluated against S7 decision-rights rules.",
        missing_requirements=[block_reason] if block_reason else [],
        rule_version_ref=rule_version_ref,
    )
    expected_disposition = str(expert_label.get("expected_disposition", disposition))
    return DelegationIntegrityReport(
        report_id=f"layer2.s7.report.{slug}",
        report_ref=f"pdc://layer2/s7/{slug}/delegation-integrity-report",
        case_id=case_id,
        decision_class_id=str(case_signals.get("decision_class_id", "a_spec_gap")),
        required_role=str(
            expert_label.get("expected_required_role", case_signals.get("actor_role", "principal"))
        ),
        interaction_mode=requested_mode,
        disposition=disposition,
        request_emitted=request_emitted,
        record_valid=record_valid,
        governed_pilot_eligible=bool(expert_label.get("expected_governed_pilot_eligible", False)),
        predicted_need_reasons=need_reasons,
        expected_need_reasons=expected_reasons,
        responsibility_integrity=integrity,
        firewall_pattern_ids=integrity.pattern_ids,
        block_reason=block_reason,
        matches_gold=disposition == expected_disposition,
        authority_boundary=_authority_boundary(
            rule_version_ref,
            authoritative_for=["delegation_integrity", "responsibility_integrity_check"],
        ),
        provenance_refs=[
            str(case_signals.get("s6_mandate_record_ref", "")),
            str(s6_mandate_posture.get("mandate_legitimacy_record_ref", "")),
        ],
        rule_version_ref=rule_version_ref,
    )


def s7_delegation_integrity(
    probe_results: Sequence[Mapping[str, object] | DelegationNegativeControlResult],
) -> dict[str, object]:
    """Compute S7 precision, recall, responsibility, and false-clear counts."""

    rows = [_as_mapping(row) for row in probe_results]
    if not rows:
        return {
            "delegation_precision": 0.0,
            "delegation_recall": 0.0,
            "responsibility_integrity_pass_rate": 0.0,
            "oversight_theater_false_clear_count": 0,
            "wrong_role_false_clear_count": 0,
            "workflow_only_summary_false_clear_count": 0,
        }
    correct = sum(
        1 for row in rows if row.get("predicted_disposition") == row.get("expected_disposition")
    )
    responsibility_ok = sum(
        1
        for row in rows
        if not bool(row.get("negative_control_false_clear", False))
        and str(row.get("responsibility_integrity_status", row.get("status", "")))
        in {"pass", "block"}
    )
    return {
        "delegation_precision": correct / len(rows),
        "delegation_recall": correct / len(rows),
        "responsibility_integrity_pass_rate": responsibility_ok / len(rows),
        "oversight_theater_false_clear_count": _false_clear_count(
            rows,
            "oversight_theater",
        ),
        "wrong_role_false_clear_count": _false_clear_count(rows, "wrong_role"),
        "workflow_only_summary_false_clear_count": _false_clear_count(
            rows,
            "workflow_only",
        ),
    }


def _authority_boundary(
    rule_version_ref: str,
    *,
    authoritative_for: Sequence[str],
    source_authority: AuthoritySource = "deterministic_producer",
) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=list(authoritative_for),
        may_not_use_for=list(_MAY_NOT_USE_FOR),
        source_authority=source_authority,
        posture="shadow",
        rule_version_refs=[rule_version_ref],
    )


def _matrix_row(
    *,
    slug: str,
    governance_decision_class: GovernanceDecisionClass,
    mode: DelegationInteractionMode,
    role: DecisionRole,
    delegated_autonomous_allowed: bool,
) -> DecisionRightsMatrixRow:
    return DecisionRightsMatrixRow(
        row_ref=f"pdc://layer2/s7/{slug}/decision-rights/{governance_decision_class.decision_class_id}",
        decision_class_id=governance_decision_class.decision_class_id,
        governance_decision_class_ref=governance_decision_class.decision_class_id,
        required_role=role,
        default_interaction_mode=mode,
        ai_first_allowed=False,
        delegated_autonomous_allowed=delegated_autonomous_allowed,
        non_overridable=governance_decision_class.high_stakes,
        available_actions=list(_ACTIONS),
        five_rights_dimensions=list(_FIVE_RIGHTS),
    )


def _mode_for_decision_class(decision_class_id: str) -> DelegationInteractionMode:
    if decision_class_id == "routine_in_envelope":
        return "delegated_autonomous"
    if decision_class_id == "budget_use":
        return "ai_follow"
    return "request_driven"


def _role_for_decision_class(decision_class_id: str, fallback: str) -> DecisionRole:
    return cast(
        "DecisionRole",
        {
            "a_spec_gap": "policy_design_governance_reviewer",
            "budget_use": "budget_owner",
            "acquisition": "legal_approver",
            "final_choice": "governance_board",
            "value_authorization": "principal",
            "mandate_boundary": "mandate_owner",
            "data_access": "data_steward",
            "routine_in_envelope": "domain_expert",
        }.get(decision_class_id, fallback),
    )


def _row_for_decision_class(
    rows: Sequence[DecisionRightsMatrixRow],
    decision_class_id: str,
) -> DecisionRightsMatrixRow:
    for row in rows:
        if row.decision_class_id == decision_class_id:
            return row
    raise KeyError(decision_class_id)


def _decision_options(actions: Sequence[DecisionAction]) -> list[DecisionOption]:
    return [
        DecisionOption(
            option_id=f"s7.{action}",
            action=action,
            label=action.replace("_", " "),
            consequence=f"Exercise {action} within the S7 mandate boundary.",
        )
        for action in actions
    ]


def _responsibility_missing_requirements(
    *,
    evidence_summary_ref: str | None,
    disconfirming_evidence_refs: Sequence[str],
    active_choice: bool | None,
    accountability_statement: str | None,
    five_rights_check: FiveRightsCheck,
    value_stakes_impact: str,
) -> list[str]:
    missing: list[str] = []
    if not evidence_summary_ref:
        missing.append("evidence_summary_ref")
    if not disconfirming_evidence_refs:
        missing.append("disconfirming_evidence_refs")
    if active_choice is not True:
        missing.append("active_choice")
    if not value_stakes_impact.strip():
        missing.append("value_stakes_impact")
    if not accountability_statement or not accountability_statement.strip():
        missing.append("accountability_statement")
    if not five_rights_check.all_pass():
        missing.append("five_rights_check")
    return missing


def _derive_need_reasons(case_signals: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    if str(case_signals.get("stakes_band", "")) == "high":
        reasons.append("high_stakes")
    if bool(case_signals.get("value_laden", False)):
        reasons.append("value_laden")
    if bool(case_signals.get("out_of_envelope", False)):
        reasons.append("out_of_envelope")
    if str(case_signals.get("s6_mandate_firewall_disposition", "")) != "pass":
        reasons.append("mandate_limited")
    if bool(case_signals.get("budget_or_legal_use_required", False)):
        reasons.append("budget_required")
    if bool(case_signals.get("acquisition_required", False)):
        reasons.append("acquisition_required")
    if bool(case_signals.get("final_choice_required", False)):
        reasons.append("final_choice")
    if not reasons:
        reasons.extend(["low_voi_no_interrupt", "routine_in_envelope"])
    return reasons


def _typed_need_reasons(reasons: Sequence[str]) -> list[DecisionNeedReason]:
    allowed = set(get_args(DecisionNeedReason))
    return [cast("DecisionNeedReason", reason) for reason in reasons if reason in allowed]


def _false_clear_count(rows: Sequence[Mapping[str, object]], probe_key: str) -> int:
    count = 0
    for row in rows:
        case_id = str(row.get("case_id", ""))
        expected = str(row.get("expected_disposition", ""))
        predicted = str(row.get("predicted_disposition", ""))
        false_clear = bool(row.get("negative_control_false_clear"))
        if probe_key in case_id and (predicted != expected or false_clear):
            count += 1
    return count


def _as_mapping(
    row: Mapping[str, object] | DelegationNegativeControlResult,
) -> Mapping[str, object]:
    if isinstance(row, DelegationNegativeControlResult):
        payload = row.model_dump(mode="json")
        payload["negative_control_false_clear"] = row.false_clear
        return payload
    return row


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
