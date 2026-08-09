"""RT7 active grounding controller over CGF gate certificates.

This module owns GY-CG5. It is a consumer/router only: it reads typed CG1-CG4
gate outputs, chooses the next bounded grounding action, and routes action
results back through the gates. It never closes obligations, writes gate
dispositions, injects evidence, or marks anything resolved.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common import serialization
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.credal_reference import (
    AdmissibleCompletion,
    CredalReferenceEdge,
    replace_reference_edge,
)
from polisyos.runtime.quality.grounding_admission import (
    GroundingAdmissionCertificate,
    GroundingAdmissionEngine,
    GroundingAdmissionReason,
)
from polisyos.runtime.quality.grounding_bind import (
    BindReason,
    GroundingBindGate,
    GroundingDecisionCertificate,
)
from polisyos.runtime.quality.grounding_phrasing_defense import GroundingProxyGapRisk  # noqa: TC001
from polisyos.runtime.quality.grounding_relation import (
    RELATION_AXES,
    AxisWitnessProvider,
    GroundingEnginePolicy,
    GroundingRelationCertificate,
    GroundingRelationEngine,
    SelectedRelation,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.credal_reference import CredalReference

GROUNDING_ACTIVE_CONTROLLER_SCHEMA_VERSION = (
    "policyos.runtime.grounding_action_certificate.v1"
)
GROUNDING_ACTIVE_CONTROLLER_VALIDATOR_VERSION = (
    "policyos.runtime.grounding_active_controller.cg5.v1"
)

type GroundingActionFamily = Literal[
    "cheap_verify",
    "elicit_human",
    "acquire_data",
    "adversarial_validate",
    "abstain",
]
type GroundingGateId = Literal["CG1", "CG2", "CG3", "CG4", "UNKNOWN"]
type ActionSelectionReason = Literal[
    "minimal_cost_decisive_dominates_abstain",
    "abstain_no_decisive_action",
    "abstain_budget_exhausted_or_tie",
    "abstain_no_addressable_blocker",
]
type ActionAuthorityScope = Literal["production", "contract_testing"]

ACTION_COST_ORDER: Mapping[GroundingActionFamily, int] = {
    "abstain": 0,
    "cheap_verify": 1,
    "adversarial_validate": 2,
    "acquire_data": 3,
    "elicit_human": 4,
}
DEFAULT_ACTION_BUDGET = 3
_CG2_OBLIGATIONS: tuple[str, ...] = (
    "admissibility_closed",
    "estimand_grounded",
    "unit_scale_consistent",
    "target_writable_wmr_slot",
    "operator_registered_lever",
    "l3_l6_consistency",
    "no_unresolved_critical_axis",
)
_CG3_OBLIGATIONS: tuple[str, ...] = (
    "parse",
    "novel_irreducible",
    "type",
    "world_bindable_or_acquirable",
    "do_semantics",
    "mechanism_witness",
    "estimand",
    "admissibility",
    "data_trust",
    "ambiguity",
    "cg2_novel_handoff",
    "cg1_content_bound",
)
_DECISIVE_ADVANCED_DISPOSITIONS = frozenset(
    {"admit_new_lever", "reject_hallucination", "non_new"}
)


class _StrictModel(BaseModel):
    """Strict immutable base for CG5 runtime DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GroundingActiveControllerPolicy(_StrictModel):
    """Safe public CG5 policy.

    Production exposes no force-action, VOI override, cost override, budget
    inflation, or treat-as-resolved knob. Contract probes use
    ``GroundingActiveController.for_contract_testing``.
    """


class _RuntimeSettings(_StrictModel):
    """Internal CG5 settings, with unsafe switches only for contract probes."""

    authority_scope: ActionAuthorityScope = "production"
    action_budget: int = Field(DEFAULT_ACTION_BUDGET, ge=0)
    disable_decisiveness_sensor: bool = False
    force_most_expensive_action: bool = False
    trust_action_result_claim: bool = False
    allow_counterfactual_authority: bool = False
    remove_counterfactual_stamp: bool = False
    bounded_reference_replay: bool = False
    allow_result_edge_injection_mutation: bool = False


class GroundingControllerCase(_StrictModel):
    """One stalled grounding case supplied as gate-owned certificates."""

    case_id: str = Field(..., min_length=1)
    proposal: dict[str, Any] | str | None = None
    cg1_certificate: GroundingRelationCertificate | None = None
    cg2_certificate: GroundingDecisionCertificate | None = None
    cg3_certificate: GroundingAdmissionCertificate | None = None
    proxy_gap_risk: GroundingProxyGapRisk | None = None


class GroundingSourceCertificateRef(_StrictModel):
    """Stable reference to a consumed gate artifact."""

    gate: GroundingGateId
    certificate_id: str = Field(..., min_length=1)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    disposition: str = Field(..., min_length=1)
    reason: str | None = None


class GroundingBlockerView(_StrictModel):
    """Typed blocker extracted from a real gate certificate."""

    blocker_id: str = Field(..., min_length=1)
    gate: GroundingGateId
    blocker_type: str = Field(..., min_length=1)
    obligation_or_axis: str | None = None
    source_field: str = Field(..., min_length=1)
    gate_certificate_id: str = Field(..., min_length=1)
    action_family: GroundingActionFamily
    evidence: Mapping[str, Any] = Field(default_factory=dict)
    mapping_status: Literal["mapped", "unknown_fail_safe"] = "mapped"


class GroundingBlockerActionRule(_StrictModel):
    """One exhaustive typed blocker-to-action table row."""

    gate: GroundingGateId
    source_field: str = Field(..., min_length=1)
    blocker_type: str = Field(..., min_length=1)
    action_family: GroundingActionFamily
    rule_source: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)


class GroundingBlockerDenominator(_StrictModel):
    """Derived denominator for all typed blocker vocabularies CG5 consumes."""

    cg1_selected_relations: tuple[str, ...]
    cg1_unresolved_axes: tuple[str, ...]
    cg2_decisive_reasons: tuple[str, ...]
    cg2_open_obligations: tuple[str, ...]
    cg3_decisive_reasons: tuple[str, ...]
    cg3_open_obligations: tuple[str, ...]
    cg4_proxy_gap_fields: tuple[str, ...]
    action_family_table_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    fail_safe_for_unknown_blockers: Literal["abstain_with_recorded_gap"] = (
        "abstain_with_recorded_gap"
    )


class GroundingColdStartAssumptions(_StrictModel):
    """Honest cold-start VOI assumptions recorded by CG5."""

    success_probability_interval: tuple[float, float] = (0.0, 1.0)
    success_probability_provenance: Literal["cold_start_unknown_set_valued"] = (
        "cold_start_unknown_set_valued"
    )
    robust_lcb_expected_voi: None = None
    ordering_rule: Literal["dominance_minimal_cost_decisive_action"] = (
        "dominance_minimal_cost_decisive_action"
    )
    ordinal_cost_order: Mapping[str, int] = Field(default_factory=lambda: dict(ACTION_COST_ORDER))
    action_budget: int = Field(DEFAULT_ACTION_BUDGET, ge=0)
    cost_provenance: Literal["cold_start_ordinal_assumption"] = (
        "cold_start_ordinal_assumption"
    )
    cost_currency: None = None


class GroundingDeferredVoiFields(_StrictModel):
    """Deferred VOI features that CG5 must not fabricate at cold start."""

    multi_action_evsi: None = None
    observation_model_learning: None = None
    search_leverage_voi: None = None
    deferred_to: tuple[str, ...] = (
        "multi_action_EVSI",
        "observation_model_learning",
        "two_level_search_leverage_VOI",
    )
    status: Literal["deferred_not_fabricated"] = "deferred_not_fabricated"


class CounterfactualDecisivenessRecord(_StrictModel):
    """Planning-only gate re-entry result used to rank actions."""

    gate: GroundingGateId
    action_family: GroundingActionFamily
    blocker_id: str = Field(..., min_length=1)
    counterfactual: bool = True
    authoritative: bool = False
    persisted_as_gate_certificate: bool = False
    before_disposition: str = Field(..., min_length=1)
    after_disposition: str | None = None
    before_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    after_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    after_reason: str | None = None
    flipped: bool
    decisive: bool
    before_certificate_id: str | None = None
    after_certificate_id: str | None = None
    planning_only_reason: str = Field(..., min_length=1)
    owner_shaped_resolution: Mapping[str, Any] = Field(default_factory=dict)
    redacted_counterfactual_payload: Literal[True] = True

    @model_validator(mode="after")
    def _counterfactual_is_non_authoritative(self) -> CounterfactualDecisivenessRecord:
        if self.counterfactual is not True:
            raise ValueError("cg5_counterfactual_stamp_missing")
        if self.authoritative or self.persisted_as_gate_certificate:
            raise ValueError("cg5_counterfactual_must_not_be_authoritative")
        return self


class GroundingActionCandidate(_StrictModel):
    """One addressable action candidate for one typed blocker."""

    action_family: GroundingActionFamily
    blocker_id: str = Field(..., min_length=1)
    ordinal_cost: int = Field(ge=0)
    within_budget: bool
    success_probability_interval: tuple[float, float] = (0.0, 1.0)
    robust_lcb_expected_voi: None = None
    dominance_argument: str = Field(..., min_length=1)
    decisiveness: CounterfactualDecisivenessRecord


class GroundingActionTicket(_StrictModel):
    """Content-addressed handoff/ticket for the selected action."""

    ticket_id: str = Field(..., pattern=r"^cg5_ticket_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    action_family: GroundingActionFamily
    blocker_id: str = Field(..., min_length=1)
    ticket_kind: str = Field(..., min_length=1)
    target_surface: str = Field(..., min_length=1)
    integration_status: str = Field(..., min_length=1)
    needed_result: tuple[str, ...] = ()
    no_resolution_claim: Literal[True] = True
    payload: Mapping[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _content_hash_matches_payload(self) -> GroundingActionTicket:
        expected = recompute_grounding_action_ticket_hash(self)
        if self.content_hash != expected:
            raise ValueError("grounding_action_ticket_content_hash_mismatch")
        expected_id = f"cg5_ticket_{expected.removeprefix('sha256:')[:16]}"
        if self.ticket_id != expected_id:
            raise ValueError("grounding_action_ticket_id_mismatch")
        if self.no_resolution_claim is not True:
            raise ValueError("grounding_action_ticket_must_not_claim_resolution")
        return self


class OwnerShapedReferenceEdgeResult(_StrictModel):
    """Owner-shaped CG0 data produced by an action result."""

    modality: str = Field(..., min_length=1)
    edge_id: str = Field(..., min_length=1)
    status: Literal["confirmed", "contested", "incomplete", "deprecated", "out_of_scope"]
    completion_kind: Literal[
        "fixed",
        "alternative",
        "may_exist",
        "may_not_exist",
        "partial",
        "excluded",
    ] = "fixed"
    completion_value: Mapping[str, Any]
    completion_reason: str = Field(..., min_length=1)
    provenance: Mapping[str, Any]
    owner_validated: Literal[True] = True
    verifier_provenance: str = Field(..., min_length=1)
    unit: str | None = None
    scale: str | None = None


class GroundingActionResult(_StrictModel):
    """Typed result produced by an action and routed back through gates."""

    action_family: GroundingActionFamily
    result_id: str = Field(..., min_length=1)
    owner_shaped_edges: tuple[OwnerShapedReferenceEdgeResult, ...] = ()
    cg4_verdict: Mapping[str, Any] | None = None
    claimed_resolution: bool = False


class GroundingActionReentryRecord(_StrictModel):
    """Result of routing an action result back through owner gates."""

    action_family: GroundingActionFamily
    result_id: str = Field(..., min_length=1)
    trusted_claimed_resolution: Literal[False] = False
    reentered_gate: GroundingGateId
    before_disposition: str = Field(..., min_length=1)
    after_disposition: str = Field(..., min_length=1)
    after_reason: str | None = None
    advanced_by_gate: bool
    false_bind_or_admit: Literal[False] = False
    final_certificate_id: str | None = None
    final_content_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")


class GroundingActionCertificate(_StrictModel):
    """Content-addressed, non-authoritative CG5 action certificate."""

    schema_version: Literal["policyos.runtime.grounding_action_certificate.v1"] = (
        GROUNDING_ACTIVE_CONTROLLER_SCHEMA_VERSION
    )
    certificate_id: str = Field(..., pattern=r"^cg5_cert_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    case_id: str = Field(..., min_length=1)
    authority_scope: ActionAuthorityScope
    production_authoritative: Literal[False] = False
    reference_epoch: str = Field(..., min_length=1)
    reference_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    source_certificates: tuple[GroundingSourceCertificateRef, ...]
    blockers: tuple[GroundingBlockerView, ...]
    blocker_denominator: GroundingBlockerDenominator
    candidates: tuple[GroundingActionCandidate, ...]
    selected_action: GroundingActionFamily
    selection_reason: ActionSelectionReason
    selected_ticket: GroundingActionTicket | None = None
    remaining_candidate_action: GroundingActionFamily | None = None
    cold_start_assumptions: GroundingColdStartAssumptions
    deferred_voi_fields: GroundingDeferredVoiFields
    never_buy_bind_boundary: Mapping[str, Any]
    validator_version: str = GROUNDING_ACTIVE_CONTROLLER_VALIDATOR_VERSION

    @model_validator(mode="after")
    def _certificate_hash_and_authority_boundary(self) -> GroundingActionCertificate:
        expected = recompute_grounding_action_certificate_hash(self)
        if self.content_hash != expected:
            raise ValueError("grounding_action_certificate_content_hash_mismatch")
        expected_id = f"cg5_cert_{expected.removeprefix('sha256:')[:16]}"
        if self.certificate_id != expected_id:
            raise ValueError("grounding_action_certificate_id_mismatch")
        if self.production_authoritative is not False:
            raise ValueError("grounding_action_certificate_must_be_non_authoritative")
        if self.never_buy_bind_boundary.get("controller_can_resolve_gate") is not False:
            raise ValueError("grounding_action_certificate_claims_gate_authority")
        return self


class GroundingActiveController:
    """RT7 controller that routes blockers to grounding actions."""

    def __init__(
        self,
        credal_reference: CredalReference,
        *,
        policy: GroundingActiveControllerPolicy | None = None,
    ) -> None:
        if policy is not None and not isinstance(policy, GroundingActiveControllerPolicy):
            raise TypeError("policy must be a GroundingActiveControllerPolicy")
        self.reference = credal_reference
        self.policy = policy or GroundingActiveControllerPolicy()
        self._settings = _RuntimeSettings()
        self._axis_witness_provider: AxisWitnessProvider | None = None

    @classmethod
    def for_contract_testing(
        cls,
        credal_reference: CredalReference,
        *,
        action_budget: int = DEFAULT_ACTION_BUDGET,
        axis_witness_provider: AxisWitnessProvider | None = None,
        disable_decisiveness_sensor: bool = False,
        force_most_expensive_action: bool = False,
        trust_action_result_claim: bool = False,
        allow_counterfactual_authority: bool = False,
        remove_counterfactual_stamp: bool = False,
        bounded_reference_replay: bool = False,
        allow_result_edge_injection_mutation: bool = False,
    ) -> GroundingActiveController:
        """Return a non-authoritative CG5 controller for contract probes."""

        controller = cls(credal_reference)
        controller._settings = _RuntimeSettings(
            authority_scope="contract_testing",
            action_budget=action_budget,
            disable_decisiveness_sensor=disable_decisiveness_sensor,
            force_most_expensive_action=force_most_expensive_action,
            trust_action_result_claim=trust_action_result_claim,
            allow_counterfactual_authority=allow_counterfactual_authority,
            remove_counterfactual_stamp=remove_counterfactual_stamp,
            bounded_reference_replay=bounded_reference_replay,
            allow_result_edge_injection_mutation=allow_result_edge_injection_mutation,
        )
        controller._axis_witness_provider = axis_witness_provider
        return controller

    def certificate_for(self, case: GroundingControllerCase) -> GroundingActionCertificate:
        """Return the next non-authoritative grounding action certificate."""

        blockers = extract_grounding_blockers(case)
        source_refs = _source_refs(case)
        candidates = tuple(
            self._candidate_for_blocker(case, blocker)
            for blocker in blockers
            if blocker.action_family != "abstain"
        )
        selected, reason, remaining = self._select(candidates)
        ticket = (
            _ticket_for_action(case, selected, blockers=blockers, candidates=candidates)
            if selected != "abstain"
            else _ticket_for_abstain(blockers, remaining)
        )
        denominator = grounding_blocker_denominator()
        assumptions = GroundingColdStartAssumptions(action_budget=self._settings.action_budget)
        raw_payload = {
            "authority_scope": self._settings.authority_scope,
            "blocker_denominator": denominator.model_dump(mode="json"),
            "blockers": [blocker.model_dump(mode="json") for blocker in blockers],
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            "case_id": case.case_id,
            "cold_start_assumptions": assumptions.model_dump(mode="json"),
            "deferred_voi_fields": GroundingDeferredVoiFields().model_dump(mode="json"),
            "never_buy_bind_boundary": _never_buy_bind_boundary(),
            "production_authoritative": False,
            "reference_epoch": self.reference.reference_epoch,
            "reference_hash": self.reference.reference_hash,
            "remaining_candidate_action": remaining,
            "selected_action": selected,
            "selected_ticket": ticket.model_dump(mode="json") if ticket else None,
            "selection_reason": reason,
            "source_certificates": [ref.model_dump(mode="json") for ref in source_refs],
            "validator_version": GROUNDING_ACTIVE_CONTROLLER_VALIDATOR_VERSION,
        }
        content_hash = gy_content_hash(
            {
                "schema_version": GROUNDING_ACTIVE_CONTROLLER_SCHEMA_VERSION,
                **raw_payload,
            }
        )
        return GroundingActionCertificate(
            certificate_id=f"cg5_cert_{content_hash.removeprefix('sha256:')[:16]}",
            content_hash=content_hash,
            **raw_payload,
        )

    def route_action_result(
        self,
        certificate: GroundingActionCertificate,
        result: GroundingActionResult,
        *,
        case: GroundingControllerCase,
    ) -> GroundingActionReentryRecord:
        """Route an action result reference back through the real gates.

        Production CG5 is a router, not a data carrier. Acquisition data must
        already be present in the owner-built reference used to construct this
        controller; caller-supplied evidence payloads fail closed here.
        """

        before = _case_disposition(case)
        if result.owner_shaped_edges and not (
            self._settings.authority_scope == "contract_testing"
            and self._settings.allow_result_edge_injection_mutation
        ):
            return GroundingActionReentryRecord(
                action_family=result.action_family,
                result_id=result.result_id,
                reentered_gate="CG3",
                before_disposition=before,
                after_disposition=before,
                after_reason="production_result_payload_rejected_owner_data_path",
                advanced_by_gate=False,
            )
        if result.cg4_verdict is not None and self._settings.authority_scope == "production":
            return GroundingActionReentryRecord(
                action_family=result.action_family,
                result_id=result.result_id,
                reentered_gate="CG4",
                before_disposition=before,
                after_disposition=before,
                after_reason="production_result_payload_rejected_cg4_verdict_path",
                advanced_by_gate=False,
            )
        if (
            self._settings.trust_action_result_claim
            and result.claimed_resolution
            and self._settings.authority_scope == "contract_testing"
        ):
            return GroundingActionReentryRecord(
                action_family=result.action_family,
                result_id=result.result_id,
                reentered_gate="CG3",
                before_disposition=before,
                after_disposition="admit_new_lever",
                after_reason="trusted_claimed_resolution_contract_testing_mutation",
                advanced_by_gate=True,
                final_certificate_id=None,
                final_content_hash=None,
            )

        if result.action_family == "adversarial_validate":
            verdict = (
                result.cg4_verdict
                if self._settings.authority_scope == "contract_testing"
                else None
            ) or (case.proxy_gap_risk.model_dump(mode="json") if case.proxy_gap_risk else {})
            after = str(verdict.get("disposition") or "cg4_verdict_recorded")
            return GroundingActionReentryRecord(
                action_family=result.action_family,
                result_id=result.result_id,
                reentered_gate="CG4",
                before_disposition=before,
                after_disposition=after,
                after_reason=str(verdict.get("quarantine_action") or "adversarial_validate"),
                advanced_by_gate=bool(verdict),
            )

        updated_reference = self.reference
        if (
            self._settings.authority_scope == "contract_testing"
            and self._settings.allow_result_edge_injection_mutation
        ):
            for edge in result.owner_shaped_edges:
                updated_reference = replace_reference_edge(
                    updated_reference,
                    _owner_edge_to_credal_edge(edge),
                )
        if result.action_family != "acquire_data" or case.proposal is None:
            return GroundingActionReentryRecord(
                action_family=result.action_family,
                result_id=result.result_id,
                reentered_gate="CG3",
                before_disposition=before,
                after_disposition=before,
                after_reason="no_gate_reentry_path_for_action_result",
                advanced_by_gate=False,
            )

        cg1 = self._relation_engine(updated_reference).certificate_for(
            case.proposal,
            proposal_id=f"{case.case_id}.reentry.cg1",
        )
        cg2 = GroundingBindGate.for_contract_testing(
            updated_reference,
            calibration_seed_anchor=True,
        ).certificate_for(cg1)
        cg3 = GroundingAdmissionEngine(updated_reference).decide(cg2, cg1_certificate=cg1)
        return GroundingActionReentryRecord(
            action_family=result.action_family,
            result_id=result.result_id,
            reentered_gate="CG3",
            before_disposition=before,
            after_disposition=cg3.decision,
            after_reason=cg3.decisive_reason,
            advanced_by_gate=(
                before != cg3.decision and cg3.decision in _DECISIVE_ADVANCED_DISPOSITIONS
            ),
            final_certificate_id=cg3.certificate_id,
            final_content_hash=cg3.content_hash,
        )

    def _candidate_for_blocker(
        self,
        case: GroundingControllerCase,
        blocker: GroundingBlockerView,
    ) -> GroundingActionCandidate:
        action = blocker.action_family
        cost = ACTION_COST_ORDER[action]
        within_budget = cost <= self._settings.action_budget
        decisive = self._counterfactual_decisiveness(case, blocker)
        if self._settings.remove_counterfactual_stamp:
            decisive = decisive.model_copy(update={"counterfactual": False})
        return GroundingActionCandidate(
            action_family=action,
            blocker_id=blocker.blocker_id,
            ordinal_cost=cost,
            within_budget=within_budget,
            dominance_argument=(
                "Cold-start success probability is set-valued [0,1], so robust LCB "
                "of expected VOI is not a point estimate. A gate-safe decisive action "
                "with bounded ordinal cost weakly dominates passive abstain because it "
                "can only produce owner-shaped input that must re-enter the gates."
            ),
            decisiveness=decisive,
        )

    def _counterfactual_decisiveness(
        self,
        case: GroundingControllerCase,
        blocker: GroundingBlockerView,
    ) -> CounterfactualDecisivenessRecord:
        if self._settings.allow_counterfactual_authority:
            return CounterfactualDecisivenessRecord(
                gate=blocker.gate,
                action_family=blocker.action_family,
                blocker_id=blocker.blocker_id,
                authoritative=True,
                persisted_as_gate_certificate=True,
                before_disposition=_case_disposition(case),
                after_disposition="controller_resolved_contract_testing_mutation",
                flipped=True,
                decisive=True,
                planning_only_reason="unsafe_contract_testing_mutation",
            )
        if blocker.action_family == "acquire_data":
            return self._acquire_counterfactual(case, blocker)
        if blocker.action_family == "adversarial_validate":
            return self._adversarial_counterfactual(case, blocker)
        if blocker.action_family == "cheap_verify":
            return self._cheap_verify_counterfactual(case, blocker)
        return CounterfactualDecisivenessRecord(
            gate=blocker.gate,
            action_family=blocker.action_family,
            blocker_id=blocker.blocker_id,
            before_disposition=_case_disposition(case),
            after_disposition=None,
            flipped=False,
            decisive=False,
            before_certificate_id=_case_certificate_id(case),
            planning_only_reason=(
                "No executable owner result is available in CG5 for this action family; "
                "the ticket can only request external resolution."
            ),
        )

    def _acquire_counterfactual(
        self,
        case: GroundingControllerCase,
        blocker: GroundingBlockerView,
    ) -> CounterfactualDecisivenessRecord:
        before = case.cg3_certificate.decision if case.cg3_certificate else _case_disposition(case)
        if case.proposal is None or case.cg3_certificate is None:
            return _non_decisive_record(
                blocker,
                before=before,
                reason="missing_proposal_or_cg3_certificate_for_counterfactual_reentry",
            )
        edge = _hypothetical_mechanism_edge(case.cg3_certificate, blocker)
        if edge is None:
            return _non_decisive_record(
                blocker,
                before=before,
                reason="no_owner_shaped_counterfactual_edge_for_blocker",
            )
        updated_reference = replace_reference_edge(self.reference, edge)
        cg1 = self._relation_engine(updated_reference).certificate_for(
            case.proposal,
            proposal_id=f"{case.case_id}.counterfactual.cg1",
        )
        cg2 = GroundingBindGate.for_contract_testing(
            updated_reference,
            calibration_seed_anchor=True,
        ).certificate_for(cg1)
        cg3 = GroundingAdmissionEngine(updated_reference).decide(cg2, cg1_certificate=cg1)
        flipped = before != cg3.decision
        return CounterfactualDecisivenessRecord(
            gate="CG3",
            action_family="acquire_data",
            blocker_id=blocker.blocker_id,
            before_disposition=before,
            after_disposition=cg3.decision,
            before_content_hash=case.cg3_certificate.content_hash,
            after_content_hash=cg3.content_hash,
            after_reason=cg3.decisive_reason,
            flipped=flipped,
            decisive=flipped and cg3.decision in _DECISIVE_ADVANCED_DISPOSITIONS,
            before_certificate_id=case.cg3_certificate.certificate_id,
            after_certificate_id=cg3.certificate_id,
            planning_only_reason=(
                "Counterfactual owner-shaped acquisition edge re-entered CG1->CG2->CG3; "
                "result is planning-only and not persisted as a gate certificate."
            ),
            owner_shaped_resolution={
                "counterfactual_edge_id": edge.edge_id,
                "counterfactual_edge_content_hash": edge.content_hash,
                "redacted_payload": True,
            },
        )

    def _adversarial_counterfactual(
        self,
        case: GroundingControllerCase,
        blocker: GroundingBlockerView,
    ) -> CounterfactualDecisivenessRecord:
        before = _case_disposition(case)
        verdict = case.proxy_gap_risk
        decisive = verdict is not None and verdict.quarantine_action == "adversarial_validate"
        return CounterfactualDecisivenessRecord(
            gate="CG4",
            action_family="adversarial_validate",
            blocker_id=blocker.blocker_id,
            before_disposition=before,
            after_disposition="cg4_adversarial_validation_recorded" if decisive else None,
            before_content_hash=verdict.content_hash if verdict else None,
            after_content_hash=verdict.content_hash if verdict else None,
            after_reason=verdict.quarantine_action if verdict else None,
            flipped=decisive,
            decisive=decisive,
            before_certificate_id=verdict.risk_id if verdict else _case_certificate_id(case),
            after_certificate_id=verdict.risk_id if verdict else None,
            planning_only_reason=(
                "CG4 proxy-gap quarantine is already gate-owned; CG5 can route the "
                "case to the real CG4 adversarial-validation harness and record the verdict."
            ),
            owner_shaped_resolution={
                "proxy_gap_risk_id": verdict.risk_id,
                "content_hash": verdict.content_hash,
                "quarantine_action": verdict.quarantine_action,
                "redacted_payload": True,
            }
            if verdict
            else {},
        )

    def _cheap_verify_counterfactual(
        self,
        case: GroundingControllerCase,
        blocker: GroundingBlockerView,
    ) -> CounterfactualDecisivenessRecord:
        before = (
            case.cg1_certificate.selected_relation
            if case.cg1_certificate
            else _case_disposition(case)
        )
        if case.proposal is None or self._axis_witness_provider is None:
            return _non_decisive_record(
                blocker,
                before=before,
                reason="structural_only_no_live_gy_k_gateway",
            )
        engine = self._relation_engine(
            self.reference,
            axis_witness_provider=self._axis_witness_provider,
            policy=GroundingEnginePolicy(allow_gy_k_decider=False),
        )
        after = engine.certificate_for(
            case.proposal,
            proposal_id=f"{case.case_id}.counterfactual.gyk",
        )
        flipped = before != after.selected_relation
        return CounterfactualDecisivenessRecord(
            gate="CG1",
            action_family="cheap_verify",
            blocker_id=blocker.blocker_id,
            before_disposition=before,
            after_disposition=after.selected_relation,
            before_content_hash=case.cg1_certificate.content_hash
            if case.cg1_certificate
            else None,
            after_content_hash=after.content_hash,
            after_reason=after.decisive_reason,
            flipped=flipped,
            decisive=flipped,
            before_certificate_id=case.cg1_certificate.certificate_id
            if case.cg1_certificate
            else None,
            after_certificate_id=after.certificate_id,
            planning_only_reason=(
                "Deterministic GY-K replay witness was supplied to CG1 as a witness only; "
                "CG1 remained the decider."
            ),
            owner_shaped_resolution={
                "gy_k_witness_mode": "deterministic_replay_provider",
                "axis": blocker.obligation_or_axis,
            },
        )

    def _relation_engine(
        self,
        reference: CredalReference,
        *,
        axis_witness_provider: AxisWitnessProvider | None = None,
        policy: GroundingEnginePolicy | None = None,
    ) -> GroundingRelationEngine:
        engine = GroundingRelationEngine(
            reference,
            axis_witness_provider=axis_witness_provider,
            policy=policy,
        )
        if self._settings.bounded_reference_replay:
            engine._fts_index = _NoLexicalReferenceIndex(reference)
        return engine

    def _select(
        self,
        candidates: Sequence[GroundingActionCandidate],
    ) -> tuple[GroundingActionFamily, ActionSelectionReason, GroundingActionFamily | None]:
        if not candidates:
            return "abstain", "abstain_no_addressable_blocker", None
        ordered = sorted(
            candidates,
            key=lambda item: (item.ordinal_cost, item.action_family, item.blocker_id),
        )
        over_budget = [item for item in ordered if not item.within_budget]
        remaining = (over_budget[0] if over_budget else ordered[0]).action_family
        if self._settings.force_most_expensive_action:
            expensive = max(
                candidates,
                key=lambda item: (item.ordinal_cost, item.action_family, item.blocker_id),
            )
            return expensive.action_family, "minimal_cost_decisive_dominates_abstain", remaining
        decisive = [
            item
            for item in ordered
            if item.decisiveness.decisive or self._settings.disable_decisiveness_sensor
        ]
        if not decisive:
            return "abstain", "abstain_no_decisive_action", remaining
        eligible = [item for item in decisive if item.within_budget]
        if not eligible:
            return "abstain", "abstain_budget_exhausted_or_tie", decisive[0].action_family
        lowest = eligible[0]
        tied = [item for item in eligible if item.ordinal_cost == lowest.ordinal_cost]
        if len({item.action_family for item in tied}) > 1:
            return "abstain", "abstain_budget_exhausted_or_tie", lowest.action_family
        return lowest.action_family, "minimal_cost_decisive_dominates_abstain", remaining


class _NoLexicalReferenceIndex:
    """Contract-test CG1 index that avoids rebuilding DuckDB FTS."""

    def __init__(self, reference: CredalReference) -> None:
        self.indexed_edge_count = len(reference.essential_edges)

    def search(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        """Return no lexical hits while leaving owner atom/token checks active."""

        _ = (query, limit)
        return []


def extract_grounding_blockers(case: GroundingControllerCase) -> tuple[GroundingBlockerView, ...]:
    """Extract typed blockers from gate-owned certificate fields."""

    blockers: list[GroundingBlockerView] = []
    if case.proxy_gap_risk is not None:
        blockers.append(
            _blocker(
                case_id=case.case_id,
                gate="CG4",
                source_field="proxy_gap_risk.quarantine_action",
                blocker_type="proxy_gap_quarantine",
                obligation_or_axis="quarantine",
                certificate_id=case.proxy_gap_risk.risk_id,
                action_family="adversarial_validate",
                evidence=case.proxy_gap_risk.model_dump(mode="json"),
            )
        )
    if case.cg3_certificate is not None and case.cg3_certificate.decision != "admit_new_lever":
        reason = str(case.cg3_certificate.decisive_reason)
        blockers.append(
            _blocker(
                case_id=case.case_id,
                gate="CG3",
                source_field="decisive_reason",
                blocker_type=reason,
                obligation_or_axis=case.cg3_certificate.acquisition_need.blocker_id
                if case.cg3_certificate.acquisition_need
                else None,
                certificate_id=case.cg3_certificate.certificate_id,
                action_family=_action_for("CG3", "decisive_reason", reason),
                evidence={"decision": case.cg3_certificate.decision},
            )
        )
        for obligation in case.cg3_certificate.obligations:
            if obligation.status == "open":
                blockers.append(
                    _blocker(
                        case_id=case.case_id,
                        gate="CG3",
                        source_field="open_obligations",
                        blocker_type=obligation.obligation_id,
                        obligation_or_axis=obligation.obligation_id,
                        certificate_id=case.cg3_certificate.certificate_id,
                        action_family=_action_for(
                            "CG3",
                            "open_obligations",
                            obligation.obligation_id,
                        ),
                        evidence=obligation.evidence,
                    )
                )
    if case.cg2_certificate is not None and case.cg2_certificate.decision != "bind":
        reason = str(case.cg2_certificate.decisive_reason)
        blockers.append(
            _blocker(
                case_id=case.case_id,
                gate="CG2",
                source_field="decisive_reason",
                blocker_type=reason,
                obligation_or_axis=None,
                certificate_id=case.cg2_certificate.certificate_id,
                action_family=_action_for("CG2", "decisive_reason", reason),
                evidence={"decision": case.cg2_certificate.decision},
            )
        )
        for obligation in case.cg2_certificate.obligations:
            if obligation.status == "open":
                blockers.append(
                    _blocker(
                        case_id=case.case_id,
                        gate="CG2",
                        source_field="open_obligations",
                        blocker_type=obligation.obligation_id,
                        obligation_or_axis=obligation.obligation_id,
                        certificate_id=case.cg2_certificate.certificate_id,
                        action_family=_action_for(
                            "CG2",
                            "open_obligations",
                            obligation.obligation_id,
                        ),
                        evidence=obligation.evidence,
                    )
                )
    if case.cg1_certificate is not None:
        relation = str(case.cg1_certificate.selected_relation)
        if relation not in {"exact", "certified-specialization"}:
            blockers.append(
                _blocker(
                    case_id=case.case_id,
                    gate="CG1",
                    source_field="selected_relation",
                    blocker_type=relation,
                    obligation_or_axis=None,
                    certificate_id=case.cg1_certificate.certificate_id,
                    action_family=_action_for("CG1", "selected_relation", relation),
                    evidence={
                        "recommended_transition": case.cg1_certificate.recommended_transition,
                    },
                )
            )
        for axis in case.cg1_certificate.unresolved_axes:
            blockers.append(
                _blocker(
                    case_id=case.case_id,
                    gate="CG1",
                    source_field="unresolved_axes",
                    blocker_type=axis,
                    obligation_or_axis=axis,
                    certificate_id=case.cg1_certificate.certificate_id,
                    action_family=_action_for("CG1", "unresolved_axes", axis),
                    evidence={"selected_relation": relation},
                )
            )
    deduped: dict[str, GroundingBlockerView] = {}
    for blocker in blockers:
        deduped.setdefault(blocker.blocker_id, blocker)
    return tuple(deduped.values())


def grounding_blocker_action_table() -> tuple[GroundingBlockerActionRule, ...]:
    """Return the typed blocker/action table derived from gate vocabularies."""

    rows: list[GroundingBlockerActionRule] = []
    for relation in _literal_values(SelectedRelation):
        rows.append(
            GroundingBlockerActionRule(
                gate="CG1",
                source_field="selected_relation",
                blocker_type=relation,
                action_family=_cg1_relation_action(relation),
                rule_source="SelectedRelation literal from grounding_relation.py",
                rationale="CG1 relation status is the typed RT1 blocker vocabulary.",
            )
        )
    for axis in RELATION_AXES:
        rows.append(
            GroundingBlockerActionRule(
                gate="CG1",
                source_field="unresolved_axes",
                blocker_type=axis,
                action_family=_cg1_axis_action(axis),
                rule_source="RELATION_AXES from grounding_relation.py",
                rationale="Unresolved RT1 axes are semantic witness gaps.",
            )
        )
    for reason in _literal_values(BindReason):
        rows.append(
            GroundingBlockerActionRule(
                gate="CG2",
                source_field="decisive_reason",
                blocker_type=reason,
                action_family=_cg2_reason_action(reason),
                rule_source="BindReason literal from grounding_bind.py",
                rationale="CG2 decisive_reason is the bind-gate blocker vocabulary.",
            )
        )
    for obligation in _CG2_OBLIGATIONS:
        rows.append(
            GroundingBlockerActionRule(
                gate="CG2",
                source_field="open_obligations",
                blocker_type=obligation,
                action_family=_cg2_obligation_action(obligation),
                rule_source="GroundingBindGate._obligations obligation ids",
                rationale="CG2 open obligations are owner-resolution blockers.",
            )
        )
    for reason in _literal_values(GroundingAdmissionReason):
        rows.append(
            GroundingBlockerActionRule(
                gate="CG3",
                source_field="decisive_reason",
                blocker_type=reason,
                action_family=_cg3_reason_action(reason),
                rule_source="GroundingAdmissionReason literal from grounding_admission.py",
                rationale="CG3 decisive_reason is the admission blocker vocabulary.",
            )
        )
    for obligation in _CG3_OBLIGATIONS:
        rows.append(
            GroundingBlockerActionRule(
                gate="CG3",
                source_field="open_obligations",
                blocker_type=obligation,
                action_family=_cg3_obligation_action(obligation),
                rule_source="GroundingAdmissionEngine._obligations obligation ids",
                rationale="CG3 open obligations are owner-resolution blockers.",
            )
        )
    rows.append(
        GroundingBlockerActionRule(
            gate="CG4",
            source_field="proxy_gap_risk.quarantine_action",
            blocker_type="proxy_gap_quarantine",
            action_family="adversarial_validate",
            rule_source="GroundingProxyGapRisk.quarantine_action",
            rationale="CG4 owns proxy-gap quarantine and adversarial validation routing.",
        )
    )
    return tuple(rows)


def grounding_blocker_denominator() -> GroundingBlockerDenominator:
    """Return the current derived blocker denominator."""

    table = grounding_blocker_action_table()
    return GroundingBlockerDenominator(
        cg1_selected_relations=tuple(_literal_values(SelectedRelation)),
        cg1_unresolved_axes=tuple(RELATION_AXES),
        cg2_decisive_reasons=tuple(_literal_values(BindReason)),
        cg2_open_obligations=_CG2_OBLIGATIONS,
        cg3_decisive_reasons=tuple(_literal_values(GroundingAdmissionReason)),
        cg3_open_obligations=_CG3_OBLIGATIONS,
        cg4_proxy_gap_fields=("proxy_gap_quarantine",),
        action_family_table_hash=gy_content_hash(
            [row.model_dump(mode="json") for row in table]
        ),
    )


def unknown_blocker_fail_safe(
    *,
    case_id: str,
    gate: GroundingGateId = "UNKNOWN",
    blocker_type: str,
) -> GroundingBlockerView:
    """Return the fail-safe route for a future unseen gate blocker."""

    return _blocker(
        case_id=case_id,
        gate=gate,
        source_field="unknown_future_blocker",
        blocker_type=blocker_type,
        obligation_or_axis=None,
        certificate_id=f"{case_id}.unknown",
        action_family="abstain",
        evidence={"routing": "unknown_blocker_fail_safe"},
        mapping_status="unknown_fail_safe",
    )


def recompute_grounding_action_ticket_hash(
    ticket_or_payload: GroundingActionTicket | Mapping[str, Any],
) -> str:
    """Recompute a CG5 ticket content hash."""

    payload = _payload_without_identity(
        ticket_or_payload,
        id_field="ticket_id",
    )
    return gy_content_hash(payload)


def recompute_grounding_action_certificate_hash(
    certificate_or_payload: GroundingActionCertificate | Mapping[str, Any],
) -> str:
    """Recompute a CG5 action certificate content hash."""

    payload = _payload_without_identity(certificate_or_payload)
    return gy_content_hash(payload)


def _action_for(
    gate: GroundingGateId,
    source_field: str,
    blocker_type: str,
) -> GroundingActionFamily:
    table = {
        (row.gate, row.source_field, row.blocker_type): row.action_family
        for row in grounding_blocker_action_table()
    }
    return table.get((gate, source_field, blocker_type), "abstain")


def _blocker(
    *,
    case_id: str,
    gate: GroundingGateId,
    source_field: str,
    blocker_type: str,
    obligation_or_axis: str | None,
    certificate_id: str,
    action_family: GroundingActionFamily,
    evidence: Mapping[str, Any],
    mapping_status: Literal["mapped", "unknown_fail_safe"] = "mapped",
) -> GroundingBlockerView:
    raw_id = gy_content_hash(
        {
            "case_id": case_id,
            "certificate_id": certificate_id,
            "gate": gate,
            "source_field": source_field,
            "blocker_type": blocker_type,
            "obligation_or_axis": obligation_or_axis,
        }
    )
    return GroundingBlockerView(
        blocker_id=f"cg5_blocker_{raw_id.removeprefix('sha256:')[:16]}",
        gate=gate,
        blocker_type=blocker_type,
        obligation_or_axis=obligation_or_axis,
        source_field=source_field,
        gate_certificate_id=certificate_id,
        action_family=action_family,
        evidence=_json_ready(evidence),
        mapping_status=mapping_status,
    )


def _source_refs(case: GroundingControllerCase) -> tuple[GroundingSourceCertificateRef, ...]:
    refs: list[GroundingSourceCertificateRef] = []
    if case.cg1_certificate:
        refs.append(
            GroundingSourceCertificateRef(
                gate="CG1",
                certificate_id=case.cg1_certificate.certificate_id,
                content_hash=case.cg1_certificate.content_hash,
                disposition=case.cg1_certificate.selected_relation,
                reason=case.cg1_certificate.recommended_transition,
            )
        )
    if case.cg2_certificate:
        refs.append(
            GroundingSourceCertificateRef(
                gate="CG2",
                certificate_id=case.cg2_certificate.certificate_id,
                content_hash=case.cg2_certificate.content_hash,
                disposition=case.cg2_certificate.decision,
                reason=case.cg2_certificate.decisive_reason,
            )
        )
    if case.cg3_certificate:
        refs.append(
            GroundingSourceCertificateRef(
                gate="CG3",
                certificate_id=case.cg3_certificate.certificate_id,
                content_hash=case.cg3_certificate.content_hash,
                disposition=case.cg3_certificate.decision,
                reason=case.cg3_certificate.decisive_reason,
            )
        )
    if case.proxy_gap_risk:
        refs.append(
            GroundingSourceCertificateRef(
                gate="CG4",
                certificate_id=case.proxy_gap_risk.risk_id,
                content_hash=case.proxy_gap_risk.content_hash,
                disposition=case.proxy_gap_risk.disposition,
                reason=case.proxy_gap_risk.quarantine_action,
            )
        )
    return tuple(refs)


def _ticket_for_action(
    case: GroundingControllerCase,
    action: GroundingActionFamily,
    *,
    blockers: Sequence[GroundingBlockerView],
    candidates: Sequence[GroundingActionCandidate],
) -> GroundingActionTicket:
    candidate = next(item for item in candidates if item.action_family == action)
    blocker = next(item for item in blockers if item.blocker_id == candidate.blocker_id)
    if action == "acquire_data":
        fields = {
            "action_family": action,
            "blocker_id": blocker.blocker_id,
            "integration_status": "handoff_artifact_gy_n7_direct_intake_not_wired",
            "needed_result": _needed_result_for_blocker(blocker),
            "no_resolution_claim": True,
            "payload": {
                "case_id": case.case_id,
                "integration_gap": (
                    "GY-N7 direct intake is not wired in CG5; owner-shaped data "
                    "must return and re-enter gates."
                ),
                "target_blocker": blocker.model_dump(mode="json"),
            },
            "target_surface": "GY-N7.grounding_acquisition",
            "ticket_kind": "acquisition_ticket",
        }
    elif action == "adversarial_validate":
        fields = {
            "action_family": action,
            "blocker_id": blocker.blocker_id,
            "integration_status": "real_cg4_harness_route",
            "needed_result": ("CG4_adversarial_validation_record",),
            "no_resolution_claim": True,
            "payload": {"case_id": case.case_id, "target_blocker": blocker.model_dump(mode="json")},
            "target_surface": "CG4.grounding_phrasing_defense",
            "ticket_kind": "adversarial_validation_ticket",
        }
    elif action == "cheap_verify":
        fields = {
            "action_family": action,
            "blocker_id": blocker.blocker_id,
            "integration_status": "structural_only_no_live_gy_k_gateway",
            "needed_result": ("GY-K_axis_entailment_witness",),
            "no_resolution_claim": True,
            "payload": {"case_id": case.case_id, "axis": blocker.obligation_or_axis},
            "target_surface": "GY-K.bounded_gateway_entailment_judge",
            "ticket_kind": "cheap_verify_ticket",
        }
    else:
        fields = {
            "action_family": action,
            "blocker_id": blocker.blocker_id,
            "integration_status": "human_ticket_only_not_executed",
            "needed_result": ("proposer_intent_or_normative_resolution",),
            "no_resolution_claim": True,
            "payload": {"case_id": case.case_id, "target_blocker": blocker.model_dump(mode="json")},
            "target_surface": "human_elicitation_queue",
            "ticket_kind": "intent_question_ticket",
        }
    content_hash = gy_content_hash(fields)
    return GroundingActionTicket(
        ticket_id=f"cg5_ticket_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _ticket_for_abstain(
    blockers: Sequence[GroundingBlockerView],
    remaining: GroundingActionFamily | None,
) -> GroundingActionTicket | None:
    if not blockers:
        return None
    blocker = blockers[0]
    fields = {
        "action_family": "abstain",
        "blocker_id": blocker.blocker_id,
        "integration_status": "terminal_for_this_round",
        "needed_result": (),
        "no_resolution_claim": True,
        "payload": {
            "blocker_count": len(blockers),
            "remaining_candidate_action": remaining,
        },
        "target_surface": "CG5.round_closeout",
        "ticket_kind": "abstain_record",
    }
    content_hash = gy_content_hash(fields)
    return GroundingActionTicket(
        ticket_id=f"cg5_ticket_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _needed_result_for_blocker(blocker: GroundingBlockerView) -> tuple[str, ...]:
    if blocker.blocker_type == "mechanism_composition_unverified":
        return ("L2_direct_causal_witness_or_transport_assumptions",)
    if blocker.blocker_type == "data_trust_below_floor":
        return ("higher_trust_L2_direct_causal_witness",)
    if blocker.blocker_type == "world_slot_acquisition_required":
        return ("WMR_WORLD_SLOT_or_GY-N7_NEW_SLOT_measurement",)
    if blocker.obligation_or_axis:
        return (blocker.obligation_or_axis,)
    return (blocker.blocker_type,)


def _hypothetical_mechanism_edge(
    certificate: GroundingAdmissionCertificate,
    blocker: GroundingBlockerView,
) -> CredalReferenceEdge | None:
    if blocker.blocker_type not in {
        "mechanism_witness_missing",
        "mechanism_composition_unverified",
        "data_trust_below_floor",
        "mechanism_witness",
        "data_trust",
    }:
        return None
    signature = certificate.proposal_signature
    target = _first_text(signature.get("X_do") or signature.get("target"))
    outcome = _first_text(signature.get("outcome"))
    if not target or not outcome or target == outcome:
        return None
    return CredalReferenceEdge(
        modality="L2_CAUSAL_CLAIM",
        edge_id=f"cg5_counterfactual_{_slug(target)}_{_slug(outcome)}",
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "direction": "positive",
                    "dst": outcome,
                    "source": target,
                    "src": target,
                    "target": outcome,
                },
                "cg5_counterfactual_owner_shaped_planning_only",
            ),
        ),
        provenance={
            "owner": "L2",
            "source": "cg5_counterfactual_planning_only",
            "signals": {"confidence": 0.92, "strong_design_evidence": True, "trust_score": 0.92},
        },
    ).with_content_hash()


def cg4_action_result_from_proxy_gap(risk: GroundingProxyGapRisk) -> GroundingActionResult:
    """Return a CG4 action result from an existing proxy-gap risk."""

    return GroundingActionResult(
        action_family="adversarial_validate",
        result_id=f"{risk.risk_id}.cg5_result",
        cg4_verdict=risk.model_dump(mode="json"),
    )


def _owner_edge_to_credal_edge(edge: OwnerShapedReferenceEdgeResult) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality=edge.modality,
        edge_id=edge.edge_id,
        status=edge.status,
        admissible_completions=(
            AdmissibleCompletion(
                edge.completion_kind,
                dict(edge.completion_value),
                edge.completion_reason,
            ),
        ),
        provenance={
            **dict(edge.provenance),
            "owner_validated": edge.owner_validated,
            "verifier_provenance": edge.verifier_provenance,
        },
        unit=edge.unit,
        scale=edge.scale,
    ).with_content_hash()


def _non_decisive_record(
    blocker: GroundingBlockerView,
    *,
    before: str,
    reason: str,
) -> CounterfactualDecisivenessRecord:
    return CounterfactualDecisivenessRecord(
        gate=blocker.gate,
        action_family=blocker.action_family,
        blocker_id=blocker.blocker_id,
        before_disposition=before,
        after_disposition=None,
        flipped=False,
        decisive=False,
        before_certificate_id=blocker.gate_certificate_id,
        planning_only_reason=reason,
    )


def _case_disposition(case: GroundingControllerCase) -> str:
    if case.proxy_gap_risk is not None:
        return case.proxy_gap_risk.disposition
    if case.cg3_certificate is not None:
        return case.cg3_certificate.decision
    if case.cg2_certificate is not None:
        return case.cg2_certificate.decision
    if case.cg1_certificate is not None:
        return case.cg1_certificate.selected_relation
    return "unknown"


def _case_certificate_id(case: GroundingControllerCase) -> str | None:
    if case.proxy_gap_risk is not None:
        return case.proxy_gap_risk.risk_id
    if case.cg3_certificate is not None:
        return case.cg3_certificate.certificate_id
    if case.cg2_certificate is not None:
        return case.cg2_certificate.certificate_id
    if case.cg1_certificate is not None:
        return case.cg1_certificate.certificate_id
    return None


def _cg1_relation_action(relation: str) -> GroundingActionFamily:
    if relation in {"exact", "certified-specialization"}:
        return "abstain"
    if relation in {"generalization", "partial", "compositional"}:
        return "cheap_verify"
    if relation == "novel-candidate":
        return "acquire_data"
    if relation == "unknown":
        return "elicit_human"
    return "abstain"


def _cg1_axis_action(axis: str) -> GroundingActionFamily:
    if axis in {"admissibility", "scope", "population"}:
        return "elicit_human"
    return "cheap_verify"


def _cg2_reason_action(reason: str) -> GroundingActionFamily:
    if reason in {"bind_eligible", "false_analog_hard_abstain", "risk_budget_exceeded"}:
        return "abstain"
    if reason == "relation_not_bind_eligible":
        return "cheap_verify"
    return "acquire_data"


def _cg2_obligation_action(obligation: str) -> GroundingActionFamily:
    if obligation == "admissibility_closed":
        return "elicit_human"
    if obligation in {"l3_l6_consistency", "no_unresolved_critical_axis"}:
        return "cheap_verify"
    return "acquire_data"


def _cg3_reason_action(reason: str) -> GroundingActionFamily:
    if reason in {
        "all_obligations_closed",
        "cg2_not_novel_candidate",
        "novel_irreducible_failed_existing_atom",
        "outcome_wish",
        "proxy_manipulation",
        "impossible_type",
    }:
        return "abstain"
    if reason == "open_obligation":
        return "acquire_data"
    return "acquire_data"


def _cg3_obligation_action(obligation: str) -> GroundingActionFamily:
    if obligation == "admissibility":
        return "elicit_human"
    if obligation in {"parse", "estimand"}:
        return "elicit_human"
    return "acquire_data"


def _literal_values(alias: object) -> tuple[str, ...]:
    value = getattr(alias, "__value__", alias)
    return tuple(str(item) for item in get_args(value))


def _payload_without_identity(
    value: BaseModel | Mapping[str, Any],
    *,
    id_field: str = "certificate_id",
) -> dict[str, Any]:
    payload = serialization.artifact_self_identity_projection(value)
    payload.pop(id_field, None)
    return _json_ready(payload)


def _never_buy_bind_boundary() -> dict[str, Any]:
    return {
        "controller_can_resolve_gate": False,
        "controller_can_inject_evidence": False,
        "controller_can_close_obligation": False,
        "controller_can_lower_threshold": False,
        "only_gate_reentry_advances_case": True,
        "counterfactuals_authoritative": False,
    }


def _json_ready(value: object) -> object:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _first_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return _first_text(value[0]) if value else ""
    if value is None:
        return ""
    return str(value)


def _slug(value: str) -> str:
    return "_".join(
        part
        for part in "".join(char.lower() if char.isalnum() else "_" for char in value).split("_")
        if part
    )


__all__ = [
    "ACTION_COST_ORDER",
    "DEFAULT_ACTION_BUDGET",
    "GROUNDING_ACTIVE_CONTROLLER_SCHEMA_VERSION",
    "GROUNDING_ACTIVE_CONTROLLER_VALIDATOR_VERSION",
    "CounterfactualDecisivenessRecord",
    "GroundingActionCandidate",
    "GroundingActionCertificate",
    "GroundingActionReentryRecord",
    "GroundingActionResult",
    "GroundingActionTicket",
    "GroundingActiveController",
    "GroundingActiveControllerPolicy",
    "GroundingBlockerActionRule",
    "GroundingBlockerDenominator",
    "GroundingBlockerView",
    "GroundingColdStartAssumptions",
    "GroundingControllerCase",
    "OwnerShapedReferenceEdgeResult",
    "cg4_action_result_from_proxy_gap",
    "extract_grounding_blockers",
    "grounding_blocker_action_table",
    "grounding_blocker_denominator",
    "recompute_grounding_action_certificate_hash",
    "recompute_grounding_action_ticket_hash",
    "unknown_blocker_fail_safe",
]
