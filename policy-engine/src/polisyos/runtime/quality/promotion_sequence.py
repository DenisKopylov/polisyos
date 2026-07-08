"""Canonical in-cycle N9 promotion sequence over real enforcement owners.

Owner breadcrumbs: promotion vocabulary and derivation traces live in
``polisyos.pdc._impl.gy_waist``; S6/S7/S8 posture gates live in
``polisyos.pdc._impl.layer2_design_search``; value/calibration/transport
receipts are emitted by N8 in ``runtime.quality.generation_cycle``; CG2 bind
promotability is resolved by ``runtime.quality.grounding_bind``. This module is
the single N6/N9 sequence over those owners, not a second champion or G4 engine.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc import (
    GY_PROMOTION_SEQUENCE_SCHEMA_VERSION,
    ArtifactRef,
    AuthorityBoundary,
    AuthorityDerivationTrace,
    EvidenceBasis,
    PromotionFailClosedReason,
    PromotionGateId,
    PromotionObligationClass,
    PromotionObligationRecord,
    PromotionObligationStatus,
    PromotionRiskSpendRecord,
    PromotionRiskSpendSummary,
    SearchTerminalKind,
    evaluate_s6_blind_spot_promotion_gate,
    evaluate_s7_mandate_delegation_promotion_gate,
    evaluate_s8_value_posture_promotion_gate,
    gy_content_hash,
)
from polisyos.pdc._impl.layer2_design_search import (  # noqa: TC001
    Layer2S6BlindSpotPostureInput,
    Layer2S7DelegationPostureInput,
    Layer2S8ValuePostureInput,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateSummary,
    DesignProblem,
    PromotionPortObservation,
    ValueGateReceipt,
)
from polisyos.runtime.quality.grounding_bind import (  # noqa: TC001
    GroundingPromotabilityResolution,
)
from polisyos.runtime.quality.world_model_record import WorldModelRecord  # noqa: TC001

PROMOTION_SEQUENCE_REF = (
    "polisyos.runtime.quality.promotion_sequence.run_canonical_promotion_sequence"
)
PROMOTION_STRANGLE_REF = (
    "polisyos.runtime.quality.promotion_sequence.LegacyPromotionStrangleReceipt"
)
_DECISION_GRADE_RANK: dict[str | None, int] = {
    None: 0,
    "unsupported": 0,
    "descriptive_only": 1,
    "advisory_admissible": 2,
    "decision_admissible": 3,
}
_SELF_PROMOTION_ROOTS = frozenset(
    {
        "llm_candidate",
        "llm_critic",
        "llm_drafter",
        "surrogate_score",
        "evidence_count",
        "candidate_supplied",
    }
)
_ALLOWED_POLICY_PROMOTION_CALLERS = frozenset(
    {
        "src/polisyos/scientist/nodes/builtins/decide/run_policy_promotion.py",
    }
)


class _StrictModel(BaseModel):
    """Strict immutable base for N9 runtime DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class CanonicalPromotionInput(_StrictModel):
    """Complete input to one canonical N9 promotion attempt."""

    schema_version: Literal["policyos.policy_design_case.layer3_gy.n9_promotion.v1"] = (
        GY_PROMOTION_SEQUENCE_SCHEMA_VERSION
    )
    candidate_summary: CandidateSummary
    value_receipt: ValueGateReceipt | None = None
    world_model_record: WorldModelRecord | None = None
    grounding_promotability: GroundingPromotabilityResolution | None = None
    s6_blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None
    s7_delegation_posture: Layer2S7DelegationPostureInput | None = None
    s8_value_posture: Layer2S8ValuePostureInput | None = None
    operation_invocation_id: str = Field(default="n9.promotion.sequence", min_length=1)
    declared_authority_transform: dict[str, Any] = Field(default_factory=dict)
    producer_root_classes: tuple[str, ...] = ("deterministic_producer",)
    producer_root_refs: tuple[ArtifactRef, ...] = ()
    verifier_refs: tuple[str, ...] = ("verifier://n9/canonical-sequence",)
    entailment_witness_ref: str | None = "gyk://entailment-witness/current"
    g4_governed_promotion_ref: str | None = "pdc://layer3/g4/governed-promotion"
    effective_independence: bool = True
    admissibility: bool = True
    force_proof_timeout: bool = False
    risk_budget_delta: float = Field(default=0.01, ge=0.0)
    risk_spends: tuple[PromotionRiskSpendRecord, ...] = ()
    promotion_mode: Literal["production", "contract_testing"] = "production"

    @model_validator(mode="after")
    def _contract_testing_cannot_claim_production(self) -> CanonicalPromotionInput:
        if self.promotion_mode == "contract_testing":
            return self
        if self.declared_authority_transform.get("for_contract_testing") is True:
            raise ValueError("contract_testing_transform_not_allowed_in_production")
        return self


class CanonicalPromotionReceipt(_StrictModel):
    """Replay-visible result of the canonical N9 sequence."""

    schema_version: Literal["policyos.policy_design_case.layer3_gy.n9_promotion.v1"] = (
        GY_PROMOTION_SEQUENCE_SCHEMA_VERSION
    )
    candidate_id: str = Field(..., min_length=1)
    status: Literal["grounded_partial_admissible", "shadow", "abstention"]
    promoted: bool
    terminal_kind: SearchTerminalKind
    obligations: tuple[PromotionObligationRecord, ...]
    risk_spend: PromotionRiskSpendSummary
    computed_authority_boundary: AuthorityBoundary
    authority_derivation_trace: AuthorityDerivationTrace | None = None
    gate_outcome_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    trace_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    refusal_reasons: tuple[str, ...] = ()
    value_receipt_ref: str | None = None
    value_method_family: str | None = None
    sequence_ref: str = PROMOTION_SEQUENCE_REF

    @model_validator(mode="after")
    def _promoted_requires_trace(self) -> CanonicalPromotionReceipt:
        if self.promoted and self.authority_derivation_trace is None:
            raise ValueError("promoted_receipt_requires_authority_derivation_trace")
        if self.promoted and self.status != "grounded_partial_admissible":
            raise ValueError("promoted_receipt_status_mismatch")
        return self


class LegacyPromotionStrangleReceipt(_StrictModel):
    """Source-scan receipt proving policy champion promotion is not live for N9."""

    status: Literal["strangled", "drift"]
    default_sequence_ref: str = PROMOTION_SEQUENCE_REF
    predecessor_ref: str = (
        "polisyos.scientist.methods.search.judge_stack.PolicyPromotionCoordinator"
    )
    live_policy_champion_callers: tuple[str, ...] = ()
    allowed_legacy_helpers: tuple[str, ...] = tuple(sorted(_ALLOWED_POLICY_PROMOTION_CALLERS))
    verified_by: str = PROMOTION_STRANGLE_REF

    @classmethod
    def recompute(cls, repo_root: Path | None = None) -> LegacyPromotionStrangleReceipt:
        """Return the current policy champion-path strangle state."""

        callers = _legacy_policy_promotion_callers((repo_root or Path.cwd()).resolve())
        production_callers = tuple(
            caller
            for caller in callers
            if caller.split(":", 1)[0] not in _ALLOWED_POLICY_PROMOTION_CALLERS
        )
        return cls(
            status="strangled" if not production_callers else "drift",
            live_policy_champion_callers=production_callers,
        )


PromotionContextProvider = Callable[
    [CandidateSummary, DesignProblem],
    Mapping[str, Any],
]


class CanonicalN9PromotionPort:
    """N6 PromotionPort implementation backed by the canonical N9 sequence."""

    def __init__(
        self,
        *,
        context_provider: PromotionContextProvider | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._context_provider = context_provider
        self._repo_root = repo_root

    def __call__(
        self,
        *,
        summaries: Sequence[CandidateSummary],
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        """Certify candidates only through the canonical N9 sequence."""

        receipts: list[CanonicalPromotionReceipt] = []
        for summary in summaries:
            context = (
                dict(self._context_provider(summary, problem))
                if self._context_provider is not None
                else {}
            )
            value_receipt = context.get("value_receipt", summary.value_receipt)
            promotion_input = CanonicalPromotionInput(
                candidate_summary=summary,
                value_receipt=value_receipt,
                world_model_record=context.get("world_model_record"),
                grounding_promotability=context.get("grounding_promotability"),
                s6_blind_spot_posture=context.get("s6_blind_spot_posture"),
                s7_delegation_posture=context.get("s7_delegation_posture"),
                s8_value_posture=context.get("s8_value_posture"),
                operation_invocation_id=str(
                    context.get("operation_invocation_id")
                    or f"n9.{problem.design_problem_id}.{summary.candidate_id}"
                ),
                declared_authority_transform=dict(
                    context.get("declared_authority_transform") or {}
                ),
                producer_root_classes=tuple(
                    str(item)
                    for item in context.get(
                        "producer_root_classes",
                        ("deterministic_producer",),
                    )
                ),
                producer_root_refs=tuple(context.get("producer_root_refs") or ()),
                verifier_refs=tuple(context.get("verifier_refs") or ()),
                entailment_witness_ref=context.get(
                    "entailment_witness_ref",
                    "gyk://entailment-witness/current",
                ),
                g4_governed_promotion_ref=context.get(
                    "g4_governed_promotion_ref",
                    "pdc://layer3/g4/governed-promotion",
                ),
                effective_independence=bool(context.get("effective_independence", True)),
                admissibility=bool(context.get("admissibility", True)),
                risk_budget_delta=float(context.get("risk_budget_delta", 0.01)),
                risk_spends=tuple(context.get("risk_spends") or ()),
                force_proof_timeout=bool(context.get("force_proof_timeout", False)),
                promotion_mode="production",
            )
            receipts.append(run_canonical_promotion_sequence(promotion_input))
        certified = tuple(receipt.candidate_id for receipt in receipts if receipt.promoted)
        return PromotionPortObservation(
            status="certified_current_valid" if certified else "not_promoted",
            certified_candidate_ids=certified,
            reason=(
                "canonical_n9_sequence_certified_current_valid"
                if certified
                else "canonical_n9_sequence_returned_shadow"
            ),
            receipts=tuple(receipt.model_dump(mode="json") for receipt in receipts),
            strangle_receipt=LegacyPromotionStrangleReceipt.recompute(
                self._repo_root
            ).model_dump(mode="json"),
        )


def run_canonical_promotion_sequence(
    promotion_input: CanonicalPromotionInput,
) -> CanonicalPromotionReceipt:
    """Run the single canonical N9 sequence over the real owner contracts."""

    obligations = _compile_obligations(promotion_input)
    risk_spend = _risk_spend_summary(promotion_input)
    if not risk_spend.within_budget:
        obligations = _replace_obligation(
            obligations,
            PromotionObligationClass.CALIBRATION,
            _failed_obligation(
                obligation_class=PromotionObligationClass.CALIBRATION,
                gate_id=PromotionGateId.N8_CALIBRATION,
                owner_ref="polisyos.runtime.quality.promotion_sequence._risk_spend_summary",
                detail=(
                    "Declared probabilistic promotion spends exceed the N9 budget delta "
                    f"({risk_spend.total_declared_delta} > {risk_spend.budget_delta})."
                ),
                reason=PromotionFailClosedReason.JOINT_OBLIGATION_INCONSISTENCY,
            ),
        )
    gate_hash = _gate_outcome_hash(obligations)
    boundary = _computed_authority_boundary(promotion_input)
    refusal_reasons = _refusal_reasons(obligations, risk_spend=risk_spend)
    promoted = not refusal_reasons
    trace = None
    trace_hash = None
    if promoted:
        trace = _authority_derivation_trace(
            promotion_input,
            obligations=obligations,
            boundary=boundary,
            gate_hash=gate_hash,
            risk_spend=risk_spend,
        )
        trace_hash = recompute_authority_trace_hash(trace)
        trace = trace.model_copy(update={"trace_content_hash": trace_hash})
    return CanonicalPromotionReceipt(
        candidate_id=promotion_input.candidate_summary.candidate_id,
        status="grounded_partial_admissible" if promoted else "shadow",
        promoted=promoted,
        terminal_kind=(
            SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE
            if promoted
            else SearchTerminalKind.GROUNDED_ABSTENTION
        ),
        obligations=obligations,
        risk_spend=risk_spend,
        computed_authority_boundary=boundary,
        authority_derivation_trace=trace,
        gate_outcome_hash=gate_hash,
        trace_content_hash=trace_hash,
        refusal_reasons=tuple(refusal_reasons),
        value_receipt_ref=(
            promotion_input.value_receipt.value_ref
            if promotion_input.value_receipt is not None
            else None
        ),
        value_method_family=(
            promotion_input.value_receipt.selected_method_fqn
            if promotion_input.value_receipt is not None
            else None
        ),
    )


def validate_canonical_promotion_receipt(
    receipt: CanonicalPromotionReceipt | Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Behaviorally validate a frozen N9 receipt without live re-derivation."""

    if not isinstance(receipt, CanonicalPromotionReceipt):
        try:
            receipt = CanonicalPromotionReceipt.model_validate(receipt)
        except ValueError as exc:
            return ({"code": "promotion_receipt_invalid", "error": str(exc)},)
    issues: list[dict[str, Any]] = []
    classes = tuple(item.obligation_class for item in receipt.obligations)
    expected = tuple(PromotionObligationClass)
    if classes != expected:
        issues.append(
            {
                "code": "promotion_obligation_denominator_mismatch",
                "expected": [item.value for item in expected],
                "actual": [item.value for item in classes],
            }
        )
    for obligation in receipt.obligations:
        if (
            obligation.status == PromotionObligationStatus.SATISFIED
            and obligation.semantic_scope == "scope_insufficient"
        ):
            issues.append(
                {
                    "code": "obligation_class_vacuously_passed",
                    "obligation_class": obligation.obligation_class.value,
                }
            )
    expected_gate_hash = _gate_outcome_hash(receipt.obligations)
    if receipt.gate_outcome_hash != expected_gate_hash:
        issues.append(
            {
                "code": "gate_outcome_hash_drift",
                "expected": expected_gate_hash,
                "actual": receipt.gate_outcome_hash,
            }
        )
    trace = receipt.authority_derivation_trace
    if receipt.promoted and trace is None:
        issues.append({"code": "promoted_receipt_missing_trace"})
    if trace is not None:
        expected_hash = recompute_authority_trace_hash(trace)
        if trace.trace_content_hash != expected_hash or receipt.trace_content_hash != expected_hash:
            issues.append(
                {
                    "code": "authority_derivation_trace_hash_drift",
                    "expected": expected_hash,
                    "actual": trace.trace_content_hash,
                }
            )
        if trace.gate_outcome_hash != receipt.gate_outcome_hash:
            issues.append({"code": "authority_trace_gate_hash_mismatch"})
    return tuple(issues)


def recompute_authority_trace_hash(trace: AuthorityDerivationTrace) -> str:
    """Return the content hash for a trace excluding its self hash field."""

    return gy_content_hash(trace.model_dump(mode="json", exclude={"trace_content_hash"}))


def _compile_obligations(
    promotion_input: CanonicalPromotionInput,
) -> tuple[PromotionObligationRecord, ...]:
    receipt = promotion_input.value_receipt
    summary = promotion_input.candidate_summary
    obligations = [
        _syntax_obligation(promotion_input),
        _type_obligation(receipt),
        _slot_obligation(promotion_input),
        _param_obligation(promotion_input),
        _coupling_obligation(summary),
        _effect_obligation(promotion_input),
        _identification_obligation(promotion_input),
        _calibration_obligation(receipt),
        _measurement_obligation(receipt),
        _data_obligation(receipt),
        evaluate_s6_blind_spot_promotion_gate(promotion_input.s6_blind_spot_posture),
        _equilibrium_obligation(receipt),
        evaluate_s7_mandate_delegation_promotion_gate(
            promotion_input.s7_delegation_posture,
            blind_spot_posture=promotion_input.s6_blind_spot_posture,
        ),
        _eval_safety_obligation(receipt),
        _value_obligation(promotion_input),
    ]
    if tuple(item.obligation_class for item in obligations) != tuple(PromotionObligationClass):
        raise ValueError("promotion_obligation_denominator_not_total")
    return tuple(obligations)


def _syntax_obligation(promotion_input: CanonicalPromotionInput) -> PromotionObligationRecord:
    roots = {item.strip().lower() for item in promotion_input.producer_root_classes}
    if roots & _SELF_PROMOTION_ROOTS:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.SYNTAX,
            gate_id=PromotionGateId.RING2_WAIST,
            owner_ref="polisyos.pdc._impl.gy_waist.AuthorityDerivationTrace",
            detail="Candidate, LLM, surrogate score, or evidence count attempted self-promotion.",
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.SYNTAX,
        gate_id=PromotionGateId.GY_WAIST,
        owner_ref="polisyos.pdc._impl.gy_waist.PromotionObligationRecord",
        detail="Strict N9 input model validated with extra fields forbidden.",
    )


def _type_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationRecord:
    if receipt is None:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.TYPE,
            gate_id=PromotionGateId.N8_VALUE,
            owner_ref="polisyos.runtime.quality.generation_cycle.ValueGateReceipt",
            detail="N8 value receipt is missing.",
        )
    _assert_generic_value_receipt(receipt)
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.TYPE,
        gate_id=PromotionGateId.N8_VALUE,
        owner_ref="polisyos.runtime.quality.generation_cycle.ValueGateReceipt",
        detail="N8 value receipt validated as its typed contract.",
        evidence_refs=[receipt.value_ref],
    )


def _slot_obligation(promotion_input: CanonicalPromotionInput) -> PromotionObligationRecord:
    receipt = promotion_input.value_receipt
    world = promotion_input.world_model_record
    if receipt is None:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.SLOT,
            gate_id=PromotionGateId.N8_TRANSPORT,
            owner_ref="polisyos.runtime.quality.generation_cycle.ValueGateReceipt",
            detail="Slot/world binding cannot be checked without the N8 receipt.",
        )
    if world is not None and receipt.world_model_record_content_hash != world.content_hash:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.SLOT,
            gate_id=PromotionGateId.N8_TRANSPORT,
            owner_ref="polisyos.runtime.quality.world_model_record.WorldModelRecord",
            detail="Value receipt names a different world-model version than the resolved WMR.",
        )
    if receipt.transport_receipt.status == "blocked":
        return _failed_obligation(
            obligation_class=PromotionObligationClass.SLOT,
            gate_id=PromotionGateId.N8_TRANSPORT,
            owner_ref="polisyos.runtime.quality.generation_cycle.ValueTransportReceipt",
            detail=(
                "N8 transport owner refused the current world: "
                f"{receipt.transport_receipt.transport_status}."
            ),
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.SLOT,
        gate_id=PromotionGateId.N8_TRANSPORT,
        owner_ref="polisyos.runtime.quality.generation_cycle.ValueGateReceipt",
        detail="Value receipt, transport receipt, and WMR content hash agree.",
        evidence_refs=[receipt.world_model_record_content_hash],
    )


def _param_obligation(promotion_input: CanonicalPromotionInput) -> PromotionObligationRecord:
    if promotion_input.declared_authority_transform.get("force_promote") is True:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.PARAM,
            gate_id=PromotionGateId.GY_WAIST,
            owner_ref="polisyos.pdc._impl.gy_waist.AuthorityDerivationTrace",
            detail="Forced promotion knob was declared by the caller.",
        )
    if not promotion_input.g4_governed_promotion_ref:
        return _scope_insufficient_obligation(
            obligation_class=PromotionObligationClass.PARAM,
            gate_id=PromotionGateId.G4_GOVERNED_PROMOTION,
            owner_ref="architecture/policy_design_case/layer3_g4_promotion_records.json",
            detail="G4 governed-promotion record is not resolved for this candidate.",
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.PARAM,
        gate_id=PromotionGateId.G4_GOVERNED_PROMOTION,
        owner_ref="architecture/policy_design_case/layer3_g4_promotion_records.json",
        detail="G4 governed-promotion record is present for the sequence.",
        evidence_refs=[promotion_input.g4_governed_promotion_ref],
    )


def _coupling_obligation(summary: CandidateSummary) -> PromotionObligationRecord:
    blockers = set(summary.value_blockers)
    if "n5_coupling_blocked" in blockers or "joint_obligation_inconsistency" in blockers:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.COUPLING,
            gate_id=PromotionGateId.N5_COUPLING,
            owner_ref="polisyos.runtime.quality.joint_simulation_horizon",
            detail="N5 coupling owner recorded a promotion blocker.",
            reason=PromotionFailClosedReason.JOINT_OBLIGATION_INCONSISTENCY,
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.COUPLING,
        gate_id=PromotionGateId.N5_COUPLING,
        owner_ref="polisyos.runtime.quality.joint_simulation_horizon",
        detail="No N5 coupling blocker is present on the candidate summary.",
    )


def _effect_obligation(promotion_input: CanonicalPromotionInput) -> PromotionObligationRecord:
    if promotion_input.force_proof_timeout:
        return PromotionObligationRecord(
            obligation_class=PromotionObligationClass.EFFECT,
            gate_id=PromotionGateId.GYK_ENTAILMENT,
            status=PromotionObligationStatus.UNKNOWN,
            reason=PromotionFailClosedReason.PROOF_TIMEOUT,
            owner_ref="GY-K entailment witness",
            detail="Entailment proof timed out; N9 carries unknown and keeps the candidate shadow.",
        )
    if not promotion_input.entailment_witness_ref:
        return PromotionObligationRecord(
            obligation_class=PromotionObligationClass.EFFECT,
            gate_id=PromotionGateId.GYK_ENTAILMENT,
            status=PromotionObligationStatus.UNKNOWN,
            reason=PromotionFailClosedReason.UNKNOWN,
            owner_ref="GY-K entailment witness",
            detail="Entailment witness is absent; N9 cannot derive effect authority.",
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.EFFECT,
        gate_id=PromotionGateId.GYK_ENTAILMENT,
        owner_ref="GY-K entailment witness",
        detail="Entailment/grounding witness is present as a witness, not the decider.",
        evidence_refs=[promotion_input.entailment_witness_ref],
    )


def _identification_obligation(
    promotion_input: CanonicalPromotionInput,
) -> PromotionObligationRecord:
    summary = promotion_input.candidate_summary
    resolution = promotion_input.grounding_promotability
    if not summary.current_valid or summary.grounding_status != "current_valid":
        return _failed_obligation(
            obligation_class=PromotionObligationClass.IDENTIFICATION,
            gate_id=PromotionGateId.CGF_GROUNDING,
            owner_ref="polisyos.runtime.quality.generation_cycle.PolicyGroundingPort",
            detail=(
                "CGF grounding did not produce current_valid "
                f"(status={summary.grounding_status})."
            ),
        )
    if resolution is None:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.IDENTIFICATION,
            gate_id=PromotionGateId.CG2_BIND_PROMOTABILITY,
            owner_ref="polisyos.runtime.quality.grounding_bind.resolve_grounding_decision_promotability",
            detail="CG2 owner-store promotability resolution is missing.",
        )
    if resolution is not None and not resolution.promotable:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.IDENTIFICATION,
            gate_id=PromotionGateId.CG2_BIND_PROMOTABILITY,
            owner_ref="polisyos.runtime.quality.grounding_bind.resolve_grounding_decision_promotability",
            detail=f"CG2 owner-store refused bind promotability: {resolution.reason}.",
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.IDENTIFICATION,
        gate_id=PromotionGateId.CG2_BIND_PROMOTABILITY,
        owner_ref="polisyos.runtime.quality.grounding_bind.resolve_grounding_decision_promotability",
        detail="CGF current_valid and CG2 owner-store promotability both resolved.",
        evidence_refs=[resolution.certificate_id],
    )


def _calibration_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationRecord:
    if receipt is None:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.CALIBRATION,
            gate_id=PromotionGateId.N8_CALIBRATION,
            owner_ref="polisyos.runtime.quality.generation_cycle.ValueCalibrationReceipt",
            detail="N8 calibration receipt is missing.",
        )
    if receipt.calibration_receipt.status != "pass":
        return _failed_obligation(
            obligation_class=PromotionObligationClass.CALIBRATION,
            gate_id=PromotionGateId.N8_CALIBRATION,
            owner_ref="polisyos.runtime.quality.generation_cycle.ValueCalibrationReceipt",
            detail=(
                "N8/S10 calibration owner refused value authority: "
                + ",".join(receipt.calibration_receipt.issue_codes or ("blocked",))
            ),
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.CALIBRATION,
        gate_id=PromotionGateId.N8_CALIBRATION,
        owner_ref="polisyos.runtime.quality.generation_cycle.ValueCalibrationReceipt",
        detail="N8/S10 calibration receipt passed.",
        evidence_refs=(
            [receipt.calibration_receipt.calibration_record_ref]
            if receipt.calibration_receipt.calibration_record_ref
            else []
        ),
    )


def _measurement_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationRecord:
    if receipt is None:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.MEASUREMENT,
            gate_id=PromotionGateId.N8_VALUE,
            owner_ref="polisyos.core.contracts.value_outer_set.ValueOuterSet",
            detail="Value outer set is missing.",
        )
    decision = receipt.value_outer_set.promotion_decision()
    if not decision.promotable:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.MEASUREMENT,
            gate_id=PromotionGateId.N8_VALUE,
            owner_ref="polisyos.core.contracts.value_outer_set.ValueOuterSet.promotion_decision",
            detail="Value outer set refused promotion: " + ",".join(decision.reasons),
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.MEASUREMENT,
        gate_id=PromotionGateId.N8_VALUE,
        owner_ref="polisyos.core.contracts.value_outer_set.ValueOuterSet.promotion_decision",
        detail="Value outer set promotion decision is content-derived and promotable.",
        evidence_refs=[receipt.value_ref],
    )


def _data_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationRecord:
    if receipt is None:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.DATA,
            gate_id=PromotionGateId.N8_VALUE,
            owner_ref="polisyos.core.contracts.value_outer_set.DataTrust",
            detail="Data-trust record is missing.",
        )
    trust = receipt.value_outer_set.data_trust
    if trust.effective_score < trust.resolved_promotion_floor:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.DATA,
            gate_id=PromotionGateId.N8_VALUE,
            owner_ref="polisyos.core.contracts.value_outer_set.DataTrust",
            detail="Data trust is below the value promotion floor.",
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.DATA,
        gate_id=PromotionGateId.N8_VALUE,
        owner_ref="polisyos.core.contracts.value_outer_set.DataTrust",
        detail="Data trust meets the value promotion floor.",
        evidence_refs=[trust.authority_ref],
    )


def _equilibrium_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationRecord:
    if receipt is not None and receipt.value_outer_set.assumption_status == "violated":
        return _failed_obligation(
            obligation_class=PromotionObligationClass.EQUILIBRIUM,
            gate_id=PromotionGateId.N5_COUPLING,
            owner_ref="polisyos.core.contracts.value_outer_set.ValueOuterSet",
            detail="Value assumptions are violated; equilibrium/response cannot be promoted.",
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.EQUILIBRIUM,
        gate_id=PromotionGateId.N5_COUPLING,
        owner_ref="polisyos.core.contracts.value_outer_set.ValueOuterSet",
        detail="No violated equilibrium or strategic-response assumption is present.",
    )


def _eval_safety_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationRecord:
    mode = receipt.evaluation_mode if receipt is not None else None
    if mode in {"sandbox_pilot", "field_pilot", "deployment"}:
        return _scope_insufficient_obligation(
            obligation_class=PromotionObligationClass.EVAL_SAFETY,
            gate_id=PromotionGateId.GY_O0_EVAL_SAFETY,
            owner_ref="GY-O0 eval-safety gate",
            detail="GY-O0 eval-safety owner is not implemented for pilot/deployment promotion.",
        )
    return PromotionObligationRecord(
        obligation_class=PromotionObligationClass.EVAL_SAFETY,
        gate_id=PromotionGateId.GY_O0_EVAL_SAFETY,
        status=PromotionObligationStatus.NOT_APPLICABLE_DATA_ONLY,
        owner_ref="GY-O0 eval-safety gate",
        detail=(
            "No pilot/deployment action is attempted; eval-safety remains scope_insufficient "
            "for future pilot/deployment verticals."
        ),
        semantic_scope="data_only_not_required",
    )


def _value_obligation(promotion_input: CanonicalPromotionInput) -> PromotionObligationRecord:
    receipt = promotion_input.value_receipt
    if receipt is None:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.VALUE,
            gate_id=PromotionGateId.N8_VALUE,
            owner_ref="polisyos.runtime.quality.generation_cycle.ValueGateReceipt",
            detail="N8 value receipt is missing.",
        )
    decision = receipt.value_outer_set.promotion_decision()
    if not decision.promotable:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.VALUE,
            gate_id=PromotionGateId.N8_VALUE,
            owner_ref="polisyos.core.contracts.value_outer_set.ValueOuterSet.promotion_decision",
            detail="Value owner refused promotion: " + ",".join(decision.reasons),
        )
    s8 = evaluate_s8_value_posture_promotion_gate(promotion_input.s8_value_posture)
    if s8.status != PromotionObligationStatus.SATISFIED:
        return s8
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.VALUE,
        gate_id=PromotionGateId.S8_VALUE_POSTURE,
        owner_ref=s8.owner_ref,
        detail="N8 value receipt and S8 value-posture owner both accepted.",
        evidence_refs=[*s8.evidence_refs, receipt.value_ref],
    )


def _satisfied_obligation(
    *,
    obligation_class: PromotionObligationClass,
    gate_id: PromotionGateId,
    owner_ref: str,
    detail: str,
    evidence_refs: Sequence[str] = (),
) -> PromotionObligationRecord:
    return PromotionObligationRecord(
        obligation_class=obligation_class,
        gate_id=gate_id,
        status=PromotionObligationStatus.SATISFIED,
        owner_ref=owner_ref,
        detail=detail,
        evidence_refs=[str(item) for item in evidence_refs if item],
    )


def _failed_obligation(
    *,
    obligation_class: PromotionObligationClass,
    gate_id: PromotionGateId,
    owner_ref: str,
    detail: str,
    reason: PromotionFailClosedReason = PromotionFailClosedReason.SINGLE_OBLIGATION_FAIL,
) -> PromotionObligationRecord:
    return PromotionObligationRecord(
        obligation_class=obligation_class,
        gate_id=gate_id,
        status=PromotionObligationStatus.FAILED,
        reason=reason,
        owner_ref=owner_ref,
        detail=detail,
    )


def _scope_insufficient_obligation(
    *,
    obligation_class: PromotionObligationClass,
    gate_id: PromotionGateId,
    owner_ref: str,
    detail: str,
) -> PromotionObligationRecord:
    return PromotionObligationRecord(
        obligation_class=obligation_class,
        gate_id=gate_id,
        status=PromotionObligationStatus.SCOPE_INSUFFICIENT,
        reason=PromotionFailClosedReason.SCOPE_INSUFFICIENT,
        owner_ref=owner_ref,
        detail=detail,
        semantic_scope="scope_insufficient",
    )


def _replace_obligation(
    obligations: Sequence[PromotionObligationRecord],
    obligation_class: PromotionObligationClass,
    replacement: PromotionObligationRecord,
) -> tuple[PromotionObligationRecord, ...]:
    return tuple(
        replacement if item.obligation_class == obligation_class else item for item in obligations
    )


def _risk_spend_summary(promotion_input: CanonicalPromotionInput) -> PromotionRiskSpendSummary:
    records = tuple(promotion_input.risk_spends)
    total = round(sum(float(item.declared_delta_spend) for item in records), 12)
    budget = float(promotion_input.risk_budget_delta)
    return PromotionRiskSpendSummary(
        total_declared_delta=total,
        budget_delta=budget,
        within_budget=total <= budget,
        spend_records=list(records),
    )


def _gate_outcome_hash(obligations: Sequence[PromotionObligationRecord]) -> str:
    return gy_content_hash([item.model_dump(mode="json") for item in obligations])


def _computed_authority_boundary(promotion_input: CanonicalPromotionInput) -> AuthorityBoundary:
    receipt = promotion_input.value_receipt
    value_grade = "unsupported"
    if receipt is not None:
        decision = receipt.value_outer_set.promotion_decision()
        value_grade = (
            "advisory_admissible" if decision.promotable else "unsupported"
        )
    boundary = AuthorityBoundary(
        boundary_id=f"n9.{_slug(promotion_input.candidate_summary.candidate_id)}.base",
        authoritative_for=["grounded_partial_admissible_policy_design"],
        may_not_use_for=["production_deployment", "unguarded_champion_promotion"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[GY_PROMOTION_SEQUENCE_SCHEMA_VERSION],
        evidence_kind="transport",
        decision_grade=value_grade,  # type: ignore[arg-type]
        evidence_basis=EvidenceBasis(
            producer_roots=[
                item.model_dump(mode="json") for item in promotion_input.producer_root_refs
            ],
            method_refs=[
                receipt.selected_method_fqn if receipt is not None else "n8_value_receipt_missing"
            ],
            calibration_refs=(
                [receipt.calibration_receipt.calibration_record_ref]
                if receipt is not None and receipt.calibration_receipt.calibration_record_ref
                else []
            ),
        ),
    )
    for posture in (promotion_input.s7_delegation_posture, promotion_input.s8_value_posture):
        posture_boundary = getattr(posture, "authority_boundary", None)
        if isinstance(posture_boundary, AuthorityBoundary):
            boundary = boundary.meet(
                posture_boundary,
                boundary_id=f"n9.{_slug(promotion_input.candidate_summary.candidate_id)}.meet",
            )
    return boundary


def _refusal_reasons(
    obligations: Sequence[PromotionObligationRecord],
    *,
    risk_spend: PromotionRiskSpendSummary,
) -> list[str]:
    reasons: list[str] = []
    for obligation in obligations:
        if obligation.status in {
            PromotionObligationStatus.FAILED,
            PromotionObligationStatus.UNKNOWN,
            PromotionObligationStatus.SCOPE_INSUFFICIENT,
        }:
            reason = obligation.reason.value if obligation.reason else "unknown"
            reasons.append(
                f"{obligation.obligation_class.value}:{reason}"
            )
    if not risk_spend.within_budget:
        reasons.append("risk_budget_delta_exceeded")
    return list(dict.fromkeys(reasons))


def _authority_derivation_trace(
    promotion_input: CanonicalPromotionInput,
    *,
    obligations: Sequence[PromotionObligationRecord],
    boundary: AuthorityBoundary,
    gate_hash: str,
    risk_spend: PromotionRiskSpendSummary,
) -> AuthorityDerivationTrace:
    declared = dict(promotion_input.declared_authority_transform)
    requested_grade = declared.get("requested_decision_grade")
    computed_grade = boundary.decision_grade or "unsupported"
    disposition: Literal["matched", "downgraded", "rejected", "upgraded"] = "matched"
    if (
        isinstance(requested_grade, str)
        and _DECISION_GRADE_RANK.get(requested_grade, 0)
        > _DECISION_GRADE_RANK.get(computed_grade, 0)
    ):
        disposition = "downgraded"
    output_ref = ArtifactRef(
        artifact_id=f"n9.{_slug(promotion_input.candidate_summary.candidate_id)}",
        artifact_type="runtime.quality.n9_promotion_receipt",
        content_hash=promotion_input.candidate_summary.content_hash,
        schema_ref=GY_PROMOTION_SEQUENCE_SCHEMA_VERSION,
        uri=f"pdc://n9/{promotion_input.candidate_summary.candidate_id}",
        version="v1",
    )
    return AuthorityDerivationTrace(
        operation_invocation_id=_slug(promotion_input.operation_invocation_id),
        output_artifact_ref=output_ref,
        declared_authority_transform=declared,
        computed_evidence_kind=boundary.evidence_kind or "transport",
        computed_decision_grade=computed_grade,  # type: ignore[arg-type]
        producer_root_classes=list(promotion_input.producer_root_classes),
        method_classification="canonical_n9_owner_sequence",
        applicability_result_ref=(
            "n9://obligations/" + gate_hash.removeprefix("sha256:")[:16]
        ),
        calibration_refs=[
            ref
            for obligation in obligations
            if obligation.obligation_class == PromotionObligationClass.CALIBRATION
            for ref in obligation.evidence_refs
        ],
        counterexamples_closed=[],
        certified_envelope_ref=None,
        unresolved_blockers=[],
        resulting_authority_boundary_ref=boundary.boundary_id
        or f"n9.{_slug(promotion_input.candidate_summary.candidate_id)}.boundary",
        transform_mismatch_disposition=disposition,
        promotion_sequence_ref=PROMOTION_SEQUENCE_REF,
        gate_outcome_hash=gate_hash,
        risk_spend_total=risk_spend.total_declared_delta,
        risk_budget_delta=risk_spend.budget_delta,
    )


def _assert_generic_value_receipt(receipt: ValueGateReceipt) -> None:
    if not receipt.selected_method_fqn:
        raise ValueError("value_receipt_method_family_missing")


def _assert_panel_specific_value_receipt(receipt: ValueGateReceipt) -> None:
    if "did" not in receipt.selected_method_fqn.lower():
        raise ValueError("promotion_coupled_to_first_vertical_shape")


def _legacy_policy_promotion_callers(repo_root: Path) -> tuple[str, ...]:
    roots = [repo_root / "src" / "polisyos" / "scientist"]
    callers: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            relative = path.relative_to(repo_root).as_posix()
            if "autotune" in relative or "tests/" in relative:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_name(node.func) == "consider_promotion":
                    callers.append(f"{relative}:{node.lineno}")
    return tuple(sorted(dict.fromkeys(callers)))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "." for char in str(value)]
    slug = "".join(chars).strip(".")
    while ".." in slug:
        slug = slug.replace("..", ".")
    if not slug or not slug[0].isalpha():
        slug = f"n9.{slug or 'candidate'}"
    return slug[:80]


__all__ = [
    "PROMOTION_SEQUENCE_REF",
    "PROMOTION_STRANGLE_REF",
    "CanonicalN9PromotionPort",
    "CanonicalPromotionInput",
    "CanonicalPromotionReceipt",
    "LegacyPromotionStrangleReceipt",
    "recompute_authority_trace_hash",
    "run_canonical_promotion_sequence",
    "validate_canonical_promotion_receipt",
]
