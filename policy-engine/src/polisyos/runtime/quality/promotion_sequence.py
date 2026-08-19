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
import copy
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from weakref import WeakKeyDictionary

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import contracts as core_contracts
from polisyos.pdc import (
    GY_PROMOTION_SEQUENCE_SCHEMA_VERSION,
    PROMOTION_RISK_CONDITIONALITY_CAVEAT,
    ArtifactRef,
    AuthorityBoundary,
    AuthorityDerivationTrace,
    EvidenceBasis,
    GyComparisonAdmission,
    GyComparisonOwnerRule,
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
    gy_recorded_content_hash,
    is_gy_declared_non_authority_block,
)
from polisyos.pdc._impl.gy_waist import (
    PromotionObligationDraft,
    promotion_obligation_instance_id,
)
from polisyos.pdc._impl.layer2_design_search import (  # noqa: TC001
    Layer2S6BlindSpotPostureInput,
    Layer2S7DelegationPostureInput,
    Layer2S8ValuePostureInput,
)
from polisyos.runtime.quality.confidence_ledger import (
    DEFAULT_REGISTRY_RELATIVE_PATH,
    CertificateClassRoute,
    ConfidenceLedgerCheck,
    ConfidenceLedgerError,
    ConfidenceLedgerReceipt,
    ConfidenceLedgerRegistry,
    ConfidenceLedgerSession,
    ConfidenceRiskBudgetScope,
    N9PromotionCertificateProjection,
    N9PromotionLedgerRow,
    N9PromotionSemanticLedgerProjection,
    PredictableClaimSpec,
    PromotionCertificateOffer,
    load_confidence_ledger_registry,
    project_n9_promotion_certificate,
    project_n9_promotion_semantic_ledger,
    recompute_confidence_owner_projection_hash,
    validate_confidence_ledger_receipt,
)
from polisyos.runtime.quality.credal_reference import CredalReference
from polisyos.runtime.quality.generation_cycle import (
    CandidateSummary,
    DesignProblem,
    PromotionPortObservation,
    ValueGateReceipt,
)
from polisyos.runtime.quality.grounding_bind import (
    GroundingDecisionCertificate,
    GroundingPromotabilityResolution,
    resolve_grounding_decision_promotability,
    resolve_grounding_decision_promotability_for_contract_testing,
)
from polisyos.runtime.quality.world_model_record import WorldModelRecord  # noqa: TC001

PROMOTION_SEQUENCE_REF = (
    "polisyos.runtime.quality.promotion_sequence.run_canonical_promotion_sequence"
)
PROMOTION_STRANGLE_REF = (
    "polisyos.runtime.quality.promotion_sequence.LegacyPromotionStrangleReceipt"
)
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
_G4_PROMOTION_RECORDS_PATH = Path(
    "architecture/policy_design_case/layer3_g4_promotion_records.json"
)
_VERIFICATION_NON_PROMOTABLE_REASON = "verification_only_replay"
_PROMOTION_OBLIGATION_SCOPE_RULE_VERSION = (
    "polisyos.policy_design_case.layer3_gy.n9_obligation_scope.v1"
)
_PROMOTION_CLASS_GATE_SOURCE_RULE_VERSION = (
    "polisyos.policy_design_case.layer3_gy.n9_class_gate_source.v1"
)


@dataclass(frozen=True)
class _CG2OwnerPromotabilityAttempt:
    resolution: GroundingPromotabilityResolution | None
    owner_ref: str
    error: str | None = None


class _StrictModel(BaseModel):
    """Strict immutable base for N9 runtime DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class N9DesignProblemBinding(_StrictModel):
    """Narrow owner binding from one real design problem into N9 and N11."""

    design_problem_id: str = Field(..., min_length=1)
    problem_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    model_spec_ref: str | None = None
    problem_schema_version: str = Field(..., min_length=1)

    @classmethod
    def from_problem(cls, problem: DesignProblem) -> N9DesignProblemBinding:
        """Derive the binding from the complete typed problem owner."""

        return cls(
            design_problem_id=problem.design_problem_id,
            problem_content_hash=gy_content_hash(problem.model_dump(mode="json")),
            model_spec_ref=problem.model_spec_ref,
            problem_schema_version=problem.schema_version,
        )


class CredalReferencePromotabilityProjection(_StrictModel):
    """Narrow CG2 dependency used by the owner-store promotability resolver."""

    schema_version: str = Field(..., min_length=1)
    reference_epoch: str = Field(..., min_length=1)
    reference_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    as_of: str = Field(..., min_length=1)


class CanonicalPromotionInput(_StrictModel):
    """Complete input to one canonical N9 promotion attempt."""

    schema_version: Literal["policyos.policy_design_case.layer3_gy.n9_promotion.v3"] = (
        GY_PROMOTION_SEQUENCE_SCHEMA_VERSION
    )
    design_problem_binding: N9DesignProblemBinding
    candidate_summary: CandidateSummary
    value_receipt: ValueGateReceipt | None = None
    world_model_record: WorldModelRecord | None = None
    grounding_decision_certificate: GroundingDecisionCertificate | None = Field(
        default=None,
        exclude=True,
    )
    credal_reference: CredalReference | None = Field(default=None, exclude=True)
    s6_blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None
    s7_delegation_posture: Layer2S7DelegationPostureInput | None = None
    s8_value_posture: Layer2S8ValuePostureInput | None = None
    repo_root: Path | None = Field(default=None, exclude=True)
    operation_invocation_id: str = Field(default="n9.promotion.sequence", min_length=1)
    declared_authority_transform: dict[str, Any] = Field(default_factory=dict)
    producer_root_classes: tuple[str, ...] = ("deterministic_producer",)
    producer_root_refs: tuple[ArtifactRef, ...] = ()
    verifier_refs: tuple[str, ...] = ("verifier://n9/canonical-sequence",)
    certificate_offers: tuple[PromotionCertificateOffer, ...] = ()
    g4_governed_promotion_ref: str | None = (
        "g4-promotion-record:g4-request:ua-msme-source-only-valid"
    )
    effective_independence: bool = True
    admissibility: bool = True
    force_proof_timeout: bool = False

    @model_validator(mode="after")
    def _owner_candidates_are_coherent(self) -> CanonicalPromotionInput:
        if (
            self.value_receipt is not None
            and self.value_receipt.candidate_id != self.candidate_summary.candidate_id
        ):
            raise ValueError("promotion_value_candidate_binding_mismatch")
        request_keys = [item.request_key for item in self.certificate_offers]
        if len(request_keys) != len(set(request_keys)):
            raise ValueError("duplicate_promotion_certificate_offer")
        return self


class CanonicalPromotionOwnerProjection(_StrictModel):
    """Content-bound owner inputs sufficient to replay one N9 decision."""

    schema_version: Literal["policyos.policy_design_case.layer3_gy.n9_owner_projection.v1"] = (
        "policyos.policy_design_case.layer3_gy.n9_owner_projection.v1"
    )
    design_problem_binding: N9DesignProblemBinding
    candidate_summary: CandidateSummary
    value_receipt: ValueGateReceipt | None = None
    world_model_record: WorldModelRecord | None = None
    grounding_decision_certificate: GroundingDecisionCertificate | None = None
    credal_reference: CredalReferencePromotabilityProjection | None = None
    s6_blind_spot_posture: Layer2S6BlindSpotPostureInput | None = None
    s7_delegation_posture: Layer2S7DelegationPostureInput | None = None
    s8_value_posture: Layer2S8ValuePostureInput | None = None
    operation_invocation_id: str = Field(..., min_length=1)
    declared_authority_transform: dict[str, Any] = Field(default_factory=dict)
    producer_root_classes: tuple[str, ...]
    producer_root_refs: tuple[ArtifactRef, ...]
    verifier_refs: tuple[str, ...]
    certificate_offers: tuple[PromotionCertificateOffer, ...] = ()
    g4_governed_promotion_ref: str | None
    effective_independence: bool
    admissibility: bool
    force_proof_timeout: bool
    projection_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("value_receipt", mode="before")
    @classmethod
    def _load_persisted_value_receipt(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        value_outer_set = payload.get("value_outer_set")
        if isinstance(value_outer_set, Mapping):
            payload["value_outer_set"] = core_contracts.ValueOuterSet.from_persisted_payload(
                value_outer_set
            )
        return ValueGateReceipt.model_validate(payload)

    @model_validator(mode="after")
    def _projection_hash_is_content_bound(self) -> CanonicalPromotionOwnerProjection:
        expected = gy_content_hash(self.model_dump(mode="json", exclude={"projection_hash"}))
        if self.projection_hash != expected:
            raise ValueError("n9_owner_projection_hash_mismatch")
        return self


class CanonicalPromotionReceipt(_StrictModel):
    """Replay-visible result of the canonical N9 sequence."""

    schema_version: Literal["policyos.policy_design_case.layer3_gy.n9_promotion.v3"] = (
        GY_PROMOTION_SEQUENCE_SCHEMA_VERSION
    )
    owner_projection: CanonicalPromotionOwnerProjection
    candidate_id: str = Field(..., min_length=1)
    status: Literal["grounded_partial_admissible", "shadow", "abstention"]
    promoted: bool
    terminal_kind: SearchTerminalKind
    obligations: tuple[PromotionObligationRecord, ...]
    risk_spend: PromotionRiskSpendSummary
    confidence_ledger_scope_ref: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    confidence_ledger_head_id: str = Field(
        pattern=r"^(?:confidence-event|confidence-ledger-root):sha256:[0-9a-f]{64}$"
    )
    confidence_ledger_head_ref: str = Field(min_length=1, max_length=500)
    confidence_ledger_receipt_id: str = Field(pattern=r"^confidence-ledger:sha256:[0-9a-f]{64}$")
    confidence_ledger_projection: N9PromotionCertificateProjection
    confidence_ledger_semantic_projection: N9PromotionSemanticLedgerProjection | None = None
    computed_authority_boundary: AuthorityBoundary
    authority_derivation_trace: AuthorityDerivationTrace | None = None
    gate_outcome_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    trace_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    refusal_reasons: tuple[str, ...] = ()
    value_receipt_ref: str | None = None
    value_method_family: str | None = None
    promotion_lane: Literal["production", "contract_testing", "unresolved"] = "unresolved"
    consumer_promotable: bool = False
    non_promotable_reason: str | None = None
    cg2_resolution_reason: str | None = None
    sequence_ref: str = PROMOTION_SEQUENCE_REF

    @model_validator(mode="after")
    def _promoted_requires_trace(self) -> CanonicalPromotionReceipt:
        expected_scope = confidence_risk_scope_for_problem(
            self.owner_projection.design_problem_binding
        )
        if (
            self.owner_projection.candidate_summary.candidate_id != self.candidate_id
            or self.confidence_ledger_projection.risk_scope != expected_scope
        ):
            raise ValueError("promotion_receipt_owner_projection_mismatch")
        if (
            self.confidence_ledger_projection.scope_id != self.confidence_ledger_scope_ref
            or self.confidence_ledger_projection.head_event_id != self.confidence_ledger_head_id
            or self.confidence_ledger_projection.head_event_ref != self.confidence_ledger_head_ref
            or self.confidence_ledger_projection.ledger_receipt_id
            != self.confidence_ledger_receipt_id
        ):
            raise ValueError("promotion_receipt_confidence_ledger_locator_mismatch")
        semantic = self.confidence_ledger_semantic_projection
        if semantic is not None:
            projection = self.confidence_ledger_projection
            if (
                semantic.authority_provenance != projection.authority_provenance
                or semantic.risk_scope != projection.risk_scope
                or semantic.scope_id != projection.scope_id
                or semantic.registry_content_hash != projection.registry_content_hash
                or semantic.schedule_projection_hash != projection.schedule_projection_hash
                or semantic.total_spend != projection.total_spend
                or semantic.total_spend_decimal != projection.total_spend_decimal
                or semantic.budget_delta != projection.budget_delta
                or semantic.budget_delta_decimal != projection.budget_delta_decimal
                or semantic.within_budget is not projection.within_budget
                or semantic.good_event_clause != projection.good_event_clause
                or semantic.conditionality_clause != projection.conditionality_clause
                or semantic.maintained_assumptions != projection.maintained_assumptions
            ):
                raise ValueError("promotion_receipt_semantic_ledger_binding_mismatch")
            raw_rows = sorted(
                (
                    row.model_dump(
                        mode="json",
                        exclude={"check_id", "claim_execution_binding_hash"},
                    )
                    for row in projection.promotion_rows
                ),
                key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")),
            )
            semantic_rows = sorted(
                (
                    {
                        "obligation_class": check.obligation_class,
                        "instrument_id": check.instrument_id,
                        "instrument_family": check.instrument_family,
                        "certificate_ref": check.certificate_ref,
                        "certificate_role": check.certificate_role,
                        "claim_polarity": check.claim_polarity,
                        "execution_status": check.execution_status,
                        "outcome": check.outcome,
                        "execution_ordinal": check.execution_ordinal,
                        "execution_id": check.execution_id,
                        "spend": check.spend.model_dump(mode="json"),
                        "spend_decimal": check.spend_decimal,
                        "anytime_valid": check.anytime_valid,
                        "supports_obligation": check.supports_obligation,
                        "eligible_for_promotion": check.eligible_for_promotion,
                    }
                    for check in semantic.checks
                    if check.certificate_role == "promotion"
                    and check.claim_polarity == "false_accept"
                ),
                key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")),
            )
            if raw_rows != semantic_rows:
                raise ValueError("promotion_receipt_semantic_ledger_row_mismatch")
        if self.promoted and self.authority_derivation_trace is None:
            raise ValueError("promoted_receipt_requires_authority_derivation_trace")
        if self.promoted and self.status != "grounded_partial_admissible":
            raise ValueError("promoted_receipt_status_mismatch")
        if self.consumer_promotable and not self.promoted:
            raise ValueError("consumer_promotable_requires_promoted_receipt")
        if self.consumer_promotable and self.promotion_lane != "production":
            raise ValueError("consumer_promotable_requires_production_lane")
        if self.confidence_ledger_projection.authority_provenance == "verification" and (
            self.consumer_promotable
            or self.non_promotable_reason != _VERIFICATION_NON_PROMOTABLE_REASON
        ):
            raise ValueError("verification_receipt_cannot_be_consumer_promotable")
        if self.promotion_lane == "contract_testing" and not self.non_promotable_reason:
            raise ValueError("contract_lane_receipt_requires_non_promotable_reason")
        scope_gaps = [
            obligation
            for obligation in self.obligations
            if obligation.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
        ]
        if (
            self.promoted
            and scope_gaps
            and (self.promotion_lane != "contract_testing" or self.consumer_promotable)
        ):
            raise ValueError("scope_insufficient_cannot_mint_authoritative_promotion")
        return self


class _LegacyCanonicalPromotionReceiptV2(CanonicalPromotionReceipt):
    """Strict v2 custody shape admitted only by the comparison migrator."""

    schema_version: Literal["policyos.policy_design_case.layer3_gy.n9_promotion.v2"] = (
        "policyos.policy_design_case.layer3_gy.n9_promotion.v2"
    )
    obligations: tuple[PromotionObligationDraft, ...]


CANONICAL_PROMOTION_VERIFICATION_COMPARISON_LEGACY_RULE = (
    "polisyos.runtime.quality.promotion_sequence."
    "canonical_promotion_receipt_verification_projection.v1"
)
CANONICAL_PROMOTION_VERIFICATION_COMPARISON_RULE = (
    "polisyos.runtime.quality.promotion_sequence."
    "canonical_promotion_receipt_verification_projection.v2"
)

_PROMOTION_OWNER_PROJECTION_LINEAGE_FIELDS = frozenset({"projection_hash"})
_PROMOTION_RECEIPT_LINEAGE_FIELDS = frozenset(
    {
        "confidence_ledger_scope_ref",
        "confidence_ledger_head_id",
        "confidence_ledger_head_ref",
        "confidence_ledger_receipt_id",
        "gate_outcome_hash",
        "trace_content_hash",
    }
)
_PROMOTION_CERTIFICATE_LINEAGE_FIELDS = frozenset(
    {
        "deployment_identity",
        "scope_id",
        "scope_anchor_ref",
        "ledger_root_id",
        "ledger_root_ref",
        "head_event_id",
        "head_event_ref",
        "ledger_receipt_id",
        "ledger_receipt_ref",
        "projection_hash",
    }
)
_PROMOTION_LEDGER_ROW_LINEAGE_FIELDS = frozenset(
    {
        "check_id",
        "execution_ordinal",
        "execution_id",
        "claim_execution_binding_hash",
    }
)
_PROMOTION_RISK_SPEND_LINEAGE_FIELDS = frozenset({"n11_confidence_ledger_ref"})
_PROMOTION_OBLIGATION_IDENTITY_FIELDS = frozenset(
    {
        "obligation_role",
        "source_obligation_ref",
        "source_obligation_content_hash",
        "instance_scope_content_hash",
        "identity_provenance",
        "obligation_instance_id",
    }
)
_PROMOTION_TRACE_LINEAGE_FIELDS = frozenset(
    {
        "applicability_result_ref",
        "gate_outcome_hash",
        "confidence_ledger_scope_ref",
        "confidence_ledger_head_id",
        "confidence_ledger_receipt_id",
        "confidence_ledger_projection_hash",
        "trace_content_hash",
    }
)


def _project_typed_fields(
    payload: Mapping[str, Any],
    *,
    model_type: type[BaseModel],
    lineage_fields: frozenset[str],
    context: str,
) -> dict[str, Any]:
    """Remove a typed lineage partition while every new field stays governing."""

    model_fields = frozenset(model_type.model_fields)
    if not lineage_fields <= model_fields:
        raise RuntimeError(f"{context}_lineage_partition_schema_drift")
    if frozenset(payload) != model_fields:
        raise ValueError(f"{context}_typed_payload_shape_drift")
    return {str(key): item for key, item in payload.items() if key not in lineage_fields}


def _project_promotion_receipt_payload(
    full_payload: dict[str, Any],
    *,
    model_type: type[BaseModel],
    receipt_lineage_fields: frozenset[str],
) -> dict[str, Any]:
    """Project one already-validated receipt through its typed lineage partitions."""

    projected = _project_typed_fields(
        full_payload,
        model_type=model_type,
        lineage_fields=receipt_lineage_fields,
        context="promotion_receipt",
    )
    projected["owner_projection"] = _project_typed_fields(
        full_payload["owner_projection"],
        model_type=CanonicalPromotionOwnerProjection,
        lineage_fields=_PROMOTION_OWNER_PROJECTION_LINEAGE_FIELDS,
        context="promotion_owner_projection",
    )
    full_certificate = full_payload["confidence_ledger_projection"]
    certificate = _project_typed_fields(
        full_certificate,
        model_type=N9PromotionCertificateProjection,
        lineage_fields=_PROMOTION_CERTIFICATE_LINEAGE_FIELDS,
        context="promotion_certificate_projection",
    )
    certificate["promotion_rows"] = [
        _project_typed_fields(
            row,
            model_type=N9PromotionLedgerRow,
            lineage_fields=_PROMOTION_LEDGER_ROW_LINEAGE_FIELDS,
            context="promotion_ledger_row",
        )
        for row in full_certificate["promotion_rows"]
    ]
    projected["confidence_ledger_projection"] = certificate

    for obligation in projected["obligations"]:
        risk_spend = obligation.get("risk_spend")
        if not isinstance(risk_spend, dict):
            continue
        obligation["risk_spend"] = _project_typed_fields(
            risk_spend,
            model_type=PromotionRiskSpendRecord,
            lineage_fields=_PROMOTION_RISK_SPEND_LINEAGE_FIELDS,
            context="promotion_obligation_risk_spend",
        )
        ledger_ref = risk_spend.get("n11_confidence_ledger_ref")
        if isinstance(ledger_ref, str):
            obligation["evidence_refs"] = [
                ref for ref in obligation["evidence_refs"] if ref != ledger_ref
            ]

    projected["risk_spend"]["spend_records"] = [
        _project_typed_fields(
            spend_record,
            model_type=PromotionRiskSpendRecord,
            lineage_fields=_PROMOTION_RISK_SPEND_LINEAGE_FIELDS,
            context="promotion_risk_spend_record",
        )
        for spend_record in full_payload["risk_spend"]["spend_records"]
    ]

    full_trace = full_payload.get("authority_derivation_trace")
    if isinstance(full_trace, dict):
        trace = _project_typed_fields(
            full_trace,
            model_type=AuthorityDerivationTrace,
            lineage_fields=_PROMOTION_TRACE_LINEAGE_FIELDS,
            context="promotion_authority_trace",
        )
        trace["calibration_refs"] = [
            ref
            for ref in full_trace.get("calibration_refs", [])
            if not str(ref).startswith("confidence-check:")
        ]
        projected["authority_derivation_trace"] = trace
    return projected


def _canonical_promotion_receipt_legacy_semantic_projection(
    value: Mapping[str, object],
) -> dict[str, Any]:
    """Down-project strict v2 or v3 custody solely for the v2-to-v3 migration."""

    schema_version = value.get("schema_version")
    if schema_version == GY_PROMOTION_SEQUENCE_SCHEMA_VERSION:
        current = CanonicalPromotionReceipt.model_validate(value)
        full_payload = current.model_dump(mode="json")
        class_rows = [
            _project_typed_fields(
                row,
                model_type=PromotionObligationRecord,
                lineage_fields=_PROMOTION_OBLIGATION_IDENTITY_FIELDS,
                context="promotion_obligation_v2_migration",
            )
            for row in full_payload["obligations"]
            if row.get("obligation_role") == "class_gate"
        ]
        if tuple(row["obligation_class"] for row in class_rows) != tuple(
            item.value for item in PromotionObligationClass
        ):
            raise ValueError("promotion_legacy_class_denominator_mismatch")
        full_payload["schema_version"] = (
            "policyos.policy_design_case.layer3_gy.n9_promotion.v2"
        )
        full_payload["obligations"] = class_rows
        receipt = _LegacyCanonicalPromotionReceiptV2.model_validate(full_payload)
    elif schema_version == "policyos.policy_design_case.layer3_gy.n9_promotion.v2":
        receipt = _LegacyCanonicalPromotionReceiptV2.model_validate(value)
        full_payload = receipt.model_dump(mode="json")
    else:
        raise ValueError("promotion_legacy_comparison_schema_invalid")
    if not is_gy_declared_non_authority_block(
        receipt.confidence_ledger_projection.model_dump(mode="json")
    ):
        raise ValueError("promotion_comparison_requires_verification_receipt")
    return _project_promotion_receipt_payload(
        full_payload,
        model_type=_LegacyCanonicalPromotionReceiptV2,
        receipt_lineage_fields=(
            _PROMOTION_RECEIPT_LINEAGE_FIELDS
            | frozenset({"confidence_ledger_semantic_projection"})
        ),
    )


def canonical_promotion_receipt_semantic_projection(
    value: Mapping[str, object],
) -> dict[str, Any]:
    """Project a verified receipt onto its v3 producer-owned semantics.

    The complete raw receipt remains the custody record. Physical ledger
    locators are non-decisive only when the confidence-ledger producer's full
    semantic event lineage is present and content-valid.
    """

    receipt = CanonicalPromotionReceipt.model_validate(value)
    semantic = receipt.confidence_ledger_semantic_projection
    if semantic is None:
        raise ValueError("promotion_comparison_semantic_ledger_missing")
    if not is_gy_declared_non_authority_block(
        receipt.confidence_ledger_projection.model_dump(mode="json")
    ):
        raise ValueError("promotion_comparison_requires_verification_receipt")
    return _project_promotion_receipt_payload(
        receipt.model_dump(mode="json"),
        model_type=CanonicalPromotionReceipt,
        receipt_lineage_fields=_PROMOTION_RECEIPT_LINEAGE_FIELDS,
    )


CANONICAL_PROMOTION_VERIFICATION_COMPARISON_LEGACY_OWNER_RULE = GyComparisonOwnerRule(
    projector=_canonical_promotion_receipt_legacy_semantic_projection,
    action="project",
    predicate_provenance="recomputed",
)


CANONICAL_PROMOTION_VERIFICATION_COMPARISON_OWNER_RULE = GyComparisonOwnerRule(
    projector=canonical_promotion_receipt_semantic_projection,
    action="project",
    predicate_provenance="recomputed",
)


class _CanonicalPromotionComparisonProof:
    """Opaque capability issued only after the live promotion owner validates."""

    __slots__ = ("__weakref__",)

    def __init__(self) -> None:
        raise TypeError("canonical_promotion_comparison_proof_owner_required")


_ISSUED_CANONICAL_PROMOTION_COMPARISON_PROOFS: WeakKeyDictionary[
    _CanonicalPromotionComparisonProof, GyComparisonAdmission
] = WeakKeyDictionary()


def _issue_canonical_promotion_comparison_proof(
    admission: GyComparisonAdmission,
) -> _CanonicalPromotionComparisonProof:
    proof = object.__new__(_CanonicalPromotionComparisonProof)
    _ISSUED_CANONICAL_PROMOTION_COMPARISON_PROOFS[proof] = admission
    return proof


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


def confidence_risk_scope_for_problem(
    binding: N9DesignProblemBinding,
) -> ConfidenceRiskBudgetScope:
    """Derive the only N11 risk scope admissible for one N9 problem binding."""

    return ConfidenceRiskBudgetScope(
        scope_owner_ref=PROMOTION_SEQUENCE_REF,
        authority_purpose="n9_promotion",
        owner_scope_key=f"design-problem:{binding.design_problem_id}",
        owner_projection_hash=binding.problem_content_hash,
        epoch_ref=None,
        model_ref=binding.model_spec_ref,
        rule_ref=GY_PROMOTION_SEQUENCE_SCHEMA_VERSION,
        schema_ref=binding.problem_schema_version,
    )


def _owner_projection_from_input(
    promotion_input: CanonicalPromotionInput,
) -> CanonicalPromotionOwnerProjection:
    reference = promotion_input.credal_reference
    payload: dict[str, Any] = {
        "schema_version": "policyos.policy_design_case.layer3_gy.n9_owner_projection.v1",
        "design_problem_binding": promotion_input.design_problem_binding,
        "candidate_summary": promotion_input.candidate_summary,
        "value_receipt": promotion_input.value_receipt,
        "world_model_record": promotion_input.world_model_record,
        "grounding_decision_certificate": (promotion_input.grounding_decision_certificate),
        "credal_reference": (
            CredalReferencePromotabilityProjection(
                schema_version=reference.schema_version,
                reference_epoch=reference.reference_epoch,
                reference_hash=reference.reference_hash,
                as_of=reference.as_of,
            )
            if reference is not None
            else None
        ),
        "s6_blind_spot_posture": promotion_input.s6_blind_spot_posture,
        "s7_delegation_posture": promotion_input.s7_delegation_posture,
        "s8_value_posture": promotion_input.s8_value_posture,
        "operation_invocation_id": promotion_input.operation_invocation_id,
        "declared_authority_transform": promotion_input.declared_authority_transform,
        "producer_root_classes": promotion_input.producer_root_classes,
        "producer_root_refs": promotion_input.producer_root_refs,
        "verifier_refs": promotion_input.verifier_refs,
        "certificate_offers": promotion_input.certificate_offers,
        "g4_governed_promotion_ref": promotion_input.g4_governed_promotion_ref,
        "effective_independence": promotion_input.effective_independence,
        "admissibility": promotion_input.admissibility,
        "force_proof_timeout": promotion_input.force_proof_timeout,
    }
    payload["projection_hash"] = gy_content_hash(
        CanonicalPromotionOwnerProjection.model_construct(
            **payload,
            projection_hash="sha256:" + "0" * 64,
        ).model_dump(mode="json", exclude={"projection_hash"})
    )
    return CanonicalPromotionOwnerProjection.model_validate(payload)


def _input_from_owner_projection(
    projection: CanonicalPromotionOwnerProjection,
    *,
    repo_root: Path | None,
) -> CanonicalPromotionInput:
    reference = projection.credal_reference
    return CanonicalPromotionInput(
        design_problem_binding=projection.design_problem_binding,
        candidate_summary=projection.candidate_summary,
        value_receipt=projection.value_receipt,
        world_model_record=projection.world_model_record,
        grounding_decision_certificate=projection.grounding_decision_certificate,
        credal_reference=(
            CredalReference(
                schema_version=reference.schema_version,
                reference_epoch=reference.reference_epoch,
                reference_hash=reference.reference_hash,
                as_of=reference.as_of,
                component_versions={},
                essential_edges={},
            )
            if reference is not None
            else None
        ),
        s6_blind_spot_posture=projection.s6_blind_spot_posture,
        s7_delegation_posture=projection.s7_delegation_posture,
        s8_value_posture=projection.s8_value_posture,
        repo_root=repo_root,
        operation_invocation_id=projection.operation_invocation_id,
        declared_authority_transform=projection.declared_authority_transform,
        producer_root_classes=projection.producer_root_classes,
        producer_root_refs=projection.producer_root_refs,
        verifier_refs=projection.verifier_refs,
        certificate_offers=projection.certificate_offers,
        g4_governed_promotion_ref=projection.g4_governed_promotion_ref,
        effective_independence=projection.effective_independence,
        admissibility=projection.admissibility,
        force_proof_timeout=projection.force_proof_timeout,
    )


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
        self._ledger_root = (repo_root or Path(__file__).resolve().parents[4]).resolve()

    def _open_confidence_ledger_session(
        self,
        binding: N9DesignProblemBinding,
    ) -> ConfidenceLedgerSession:
        """Open or resume the durable N9 risk scope owned by one design problem."""

        return ConfidenceLedgerSession.from_repo(
            self._ledger_root,
            risk_scope=confidence_risk_scope_for_problem(binding),
        )

    @classmethod
    def _for_verification(
        cls,
        *,
        repo_root: Path,
        confidence_ledger_session: ConfidenceLedgerSession,
    ) -> _VerificationN9PromotionPort:
        """Build a private port whose receipts can never authorize N6."""

        del cls
        if (
            confidence_ledger_session.is_authority_session
            or confidence_ledger_session.authority_provenance != "verification"
        ):
            raise ValueError("confidence_ledger_verification_session_required")
        owner_root = repo_root.resolve()
        if owner_root != Path(__file__).resolve().parents[4]:
            raise ValueError("verification_owner_repo_root_invalid")
        _require_canonical_verification_registry(
            confidence_ledger_session,
            repo_root=owner_root,
        )
        return _VerificationN9PromotionPort(
            repo_root=owner_root,
            confidence_ledger_session=confidence_ledger_session,
        )

    def __call__(
        self,
        *,
        summaries: Sequence[CandidateSummary],
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        """Certify candidates only through the canonical N9 sequence."""

        problem_binding = N9DesignProblemBinding.from_problem(problem)
        try:
            confidence_ledger_session = self._open_confidence_ledger_session(problem_binding)
        except ConfidenceLedgerError as exc:
            return PromotionPortObservation(
                status="not_promoted",
                certified_candidate_ids=(),
                reason=f"confidence_ledger_refused:{exc.code}",
                receipts=(),
                strangle_receipt=LegacyPromotionStrangleReceipt.recompute(
                    self._repo_root
                ).model_dump(mode="json"),
            )
        return _run_n9_promotion_port_batch(
            summaries=summaries,
            problem=problem,
            problem_binding=problem_binding,
            context_provider=self._context_provider,
            repo_root=self._repo_root,
            confidence_ledger_session=confidence_ledger_session,
        )


class _VerificationN9PromotionPort:
    """Private N6 checker port over one isolated verification ledger."""

    def __init__(
        self,
        *,
        repo_root: Path,
        confidence_ledger_session: ConfidenceLedgerSession,
    ) -> None:
        self._repo_root = repo_root.resolve()
        self._confidence_ledger_session = confidence_ledger_session

    def __call__(
        self,
        *,
        summaries: Sequence[CandidateSummary],
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        """Replay owners while emitting no consumer certification."""

        return _run_n9_promotion_port_batch(
            summaries=summaries,
            problem=problem,
            problem_binding=N9DesignProblemBinding.from_problem(problem),
            context_provider=None,
            repo_root=self._repo_root,
            confidence_ledger_session=self._confidence_ledger_session,
        )


def _run_n9_promotion_port_batch(
    *,
    summaries: Sequence[CandidateSummary],
    problem: DesignProblem,
    problem_binding: N9DesignProblemBinding,
    context_provider: PromotionContextProvider | None,
    repo_root: Path | None,
    confidence_ledger_session: ConfidenceLedgerSession,
) -> PromotionPortObservation:
    """Run one adaptive batch against a pre-authorized ledger session."""

    expected_scope = confidence_risk_scope_for_problem(problem_binding)
    if confidence_ledger_session.risk_scope != expected_scope:
        raise ValueError("confidence_ledger_scope_binding_mismatch")
    verification = confidence_ledger_session.authority_provenance == "verification"
    receipts_with_inputs: list[tuple[CanonicalPromotionReceipt, CanonicalPromotionInput]] = []
    for summary in summaries:
        context = dict(context_provider(summary, problem)) if context_provider is not None else {}
        value_receipt = context.get("value_receipt", summary.value_receipt)
        promotion_input = CanonicalPromotionInput(
            design_problem_binding=problem_binding,
            candidate_summary=summary,
            value_receipt=value_receipt,
            world_model_record=context.get("world_model_record"),
            grounding_decision_certificate=context.get("grounding_decision_certificate"),
            credal_reference=context.get("credal_reference"),
            s6_blind_spot_posture=context.get("s6_blind_spot_posture"),
            s7_delegation_posture=context.get("s7_delegation_posture"),
            s8_value_posture=context.get("s8_value_posture"),
            repo_root=repo_root,
            operation_invocation_id=str(
                context.get("operation_invocation_id")
                or f"n9.{problem.design_problem_id}.{summary.candidate_id}"
            ),
            declared_authority_transform=dict(context.get("declared_authority_transform") or {}),
            producer_root_classes=tuple(
                str(item)
                for item in context.get(
                    "producer_root_classes",
                    ("deterministic_producer",),
                )
            ),
            producer_root_refs=tuple(context.get("producer_root_refs") or ()),
            verifier_refs=tuple(context.get("verifier_refs") or ()),
            certificate_offers=tuple(context.get("certificate_offers") or ()),
            g4_governed_promotion_ref=context.get(
                "g4_governed_promotion_ref",
                "g4-promotion-record:g4-request:ua-msme-source-only-valid",
            ),
            effective_independence=bool(context.get("effective_independence", True)),
            admissibility=bool(context.get("admissibility", True)),
            force_proof_timeout=bool(context.get("force_proof_timeout", False)),
        )
        runner = (
            _run_canonical_promotion_sequence_for_verification
            if verification
            else run_canonical_promotion_sequence
        )
        receipts_with_inputs.append(
            (
                runner(
                    promotion_input,
                    confidence_ledger_session=confidence_ledger_session,
                ),
                promotion_input,
            )
        )
    final_ledger_receipt = confidence_ledger_session.receipt()
    final_ledger_projection = project_n9_promotion_certificate(
        final_ledger_receipt,
        session=confidence_ledger_session,
    )
    final_ledger_semantic_projection = project_n9_promotion_semantic_ledger(
        final_ledger_receipt,
        session=confidence_ledger_session,
    )
    receipts = [
        _rebind_promotion_receipt_to_ledger_head(
            receipt,
            promotion_input=promotion_input,
            registry=confidence_ledger_session.registry,
            ledger_receipt=final_ledger_receipt,
            ledger_projection=final_ledger_projection,
            ledger_semantic_projection=final_ledger_semantic_projection,
        )
        for receipt, promotion_input in receipts_with_inputs
    ]
    certified = tuple(
        receipt.candidate_id
        for receipt in receipts
        if (not verification and receipt.promoted and receipt.consumer_promotable)
    )
    return PromotionPortObservation(
        status="certified_current_valid" if certified else "not_promoted",
        certified_candidate_ids=certified,
        reason=(
            "canonical_n9_sequence_certified_current_valid"
            if certified
            else (
                "verification_n9_sequence_non_consumer"
                if verification
                else "canonical_n9_sequence_returned_shadow"
            )
        ),
        receipts=tuple(receipt.model_dump(mode="json") for receipt in receipts),
        strangle_receipt=LegacyPromotionStrangleReceipt.recompute(repo_root).model_dump(
            mode="json"
        ),
    )


def _n11_owner_projection(value: object) -> object:
    """Project owner content onto ledger-canonical scalars without float ambiguity."""

    if isinstance(value, BaseModel):
        return _n11_owner_projection(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {str(key): _n11_owner_projection(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_n11_owner_projection(item) for item in value]
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"n11_owner_projection_value_invalid:{type(value).__name__}")


def _calibration_owner_projection(
    promotion_input: CanonicalPromotionInput,
) -> object:
    receipt = promotion_input.value_receipt
    if receipt is None:
        return {
            "owner_status": "missing",
            "candidate_id": promotion_input.candidate_summary.candidate_id,
        }
    return _n11_owner_projection(receipt.calibration_receipt)


def _data_trust_owner_projection(
    promotion_input: CanonicalPromotionInput,
) -> object:
    receipt = promotion_input.value_receipt
    if receipt is None:
        return {
            "owner_status": "missing",
            "candidate_id": promotion_input.candidate_summary.candidate_id,
        }
    return _n11_owner_projection(receipt.value_outer_set.data_trust)


def _promotion_offer_claim_scope_ref(
    promotion_input: CanonicalPromotionInput,
    *,
    route: CertificateClassRoute,
    certificate_ref: str,
    data_window_ref: str,
    owner_projection_hash: str,
) -> str:
    """Bind a predictable claim to its candidate, route, owner evidence, and window."""

    binding_hash = gy_content_hash(
        {
            "candidate_id": promotion_input.candidate_summary.candidate_id,
            "candidate_content_hash": promotion_input.candidate_summary.content_hash,
            "certificate_class": route.certificate_class,
            "obligation_class": route.obligation_class,
            "owner_ref": route.owner_ref,
            "verifier_kernel_id": route.verifier_kernel_id,
            "verifier_ref": route.verifier_ref,
            "certificate_ref": certificate_ref,
            "data_window_ref": data_window_ref,
            "owner_projection_hash": owner_projection_hash,
        }
    )
    return f"n9://obligation-binding/{binding_hash}"


def _expected_calibration_check(
    promotion_input: CanonicalPromotionInput,
    *,
    route: CertificateClassRoute,
) -> PromotionCertificateOffer:
    value_receipt = promotion_input.value_receipt
    calibration_ref = (
        value_receipt.calibration_receipt.calibration_record_ref
        if value_receipt is not None
        else None
    ) or f"n8://calibration/{promotion_input.candidate_summary.candidate_id}"
    owner_projection_hash = recompute_confidence_owner_projection_hash(
        _calibration_owner_projection(promotion_input)
    )
    claim_scope_ref = _promotion_offer_claim_scope_ref(
        promotion_input,
        route=route,
        certificate_ref=calibration_ref,
        data_window_ref=calibration_ref,
        owner_projection_hash=owner_projection_hash,
    )
    return PromotionCertificateOffer(
        request_key=(
            f"n9://{promotion_input.candidate_summary.candidate_id}/"
            f"{PromotionObligationClass.CALIBRATION.value}/"
            f"{route.certificate_class}/{calibration_ref}/"
            f"binding/{claim_scope_ref.rsplit('/', maxsplit=1)[-1]}"
        ),
        certificate_class=route.certificate_class,
        certificate_ref=calibration_ref,
        owner_projection_hash=owner_projection_hash,
        claim=PredictableClaimSpec(
            claim_ref=(
                f"n9://candidate/{promotion_input.candidate_summary.candidate_id}/"
                "calibration-promotion"
            ),
            null_ref="n9://null/calibration-claim-not-promotion-valid",
            claim_scope_ref=claim_scope_ref,
            data_window_ref=calibration_ref,
            certificate_role="promotion",
            claim_polarity="false_accept",
        ),
    )


def _expected_data_trust_check(
    promotion_input: CanonicalPromotionInput,
    *,
    route: CertificateClassRoute,
) -> PromotionCertificateOffer:
    value_receipt = promotion_input.value_receipt
    data_ref = (
        value_receipt.value_outer_set.data_trust.authority_ref
        if value_receipt is not None
        else f"n8://data-trust/{promotion_input.candidate_summary.candidate_id}"
    )
    owner_projection_hash = recompute_confidence_owner_projection_hash(
        _data_trust_owner_projection(promotion_input)
    )
    claim_scope_ref = _promotion_offer_claim_scope_ref(
        promotion_input,
        route=route,
        certificate_ref=data_ref,
        data_window_ref=data_ref,
        owner_projection_hash=owner_projection_hash,
    )
    return PromotionCertificateOffer(
        request_key=(
            f"n9://{promotion_input.candidate_summary.candidate_id}/"
            f"{route.obligation_class.value}/{route.certificate_class}/"
            f"{data_ref}/binding/{claim_scope_ref.rsplit('/', maxsplit=1)[-1]}"
        ),
        certificate_class=route.certificate_class,
        certificate_ref=data_ref,
        owner_projection_hash=owner_projection_hash,
        claim=PredictableClaimSpec(
            claim_ref=(
                f"n9://candidate/{promotion_input.candidate_summary.candidate_id}/"
                "data-trust-promotion"
            ),
            null_ref="n9://null/data-trust-claim-not-promotion-valid",
            claim_scope_ref=claim_scope_ref,
            data_window_ref=data_ref,
            certificate_role="promotion",
            claim_polarity="false_accept",
        ),
    )


@dataclass(frozen=True)
class _CodeOwnedPromotionOfferProducer:
    """One N9 owner contract independent of registry-selected instruments."""

    verifier_kernel_id: str
    obligation_class: PromotionObligationClass
    owner_ref: str
    verifier_ref: str
    build_offer: Callable[..., PromotionCertificateOffer]

    def route_matches(self, route: CertificateClassRoute) -> bool:
        """Return whether registry data preserves the code-owned provenance contract."""

        return bool(
            route.obligation_class == self.obligation_class
            and route.owner_ref == self.owner_ref
            and route.verifier_ref == self.verifier_ref
        )


def _code_owned_promotion_offer_producers() -> tuple[
    _CodeOwnedPromotionOfferProducer,
    ...,
]:
    """Return the independent N8 owner census; instruments remain registry data."""

    return (
        _CodeOwnedPromotionOfferProducer(
            verifier_kernel_id="n8_calibration_receipt_recompute_v1",
            obligation_class=PromotionObligationClass.CALIBRATION,
            owner_ref=(
                "polisyos.runtime.quality.generation_cycle.ValueCalibrationReceipt"
            ),
            verifier_ref=(
                "polisyos.runtime.quality.promotion_sequence._calibration_obligation"
            ),
            build_offer=_expected_calibration_check,
        ),
        _CodeOwnedPromotionOfferProducer(
            verifier_kernel_id="n8_data_trust_recompute_v1",
            obligation_class=PromotionObligationClass.DATA,
            owner_ref="polisyos.core.contracts.value_outer_set.DataTrust",
            verifier_ref="polisyos.runtime.quality.promotion_sequence._data_obligation",
            build_offer=_expected_data_trust_check,
        ),
    )


def _owner_offer_for_route(
    promotion_input: CanonicalPromotionInput,
    *,
    route: CertificateClassRoute,
) -> PromotionCertificateOffer | None:
    """Derive current N8 promotion offers from their code-owned owner projections."""

    producer = next(
        (
            item
            for item in _code_owned_promotion_offer_producers()
            if item.verifier_kernel_id == route.verifier_kernel_id
        ),
        None,
    )
    return (
        producer.build_offer(promotion_input, route=route)
        if producer is not None
        else None
    )


def _promotion_certificate_offers(
    promotion_input: CanonicalPromotionInput,
    *,
    registry: ConfidenceLedgerRegistry,
) -> tuple[PromotionCertificateOffer, ...]:
    """Recompute the registry routes against an independent code-owned owner census."""

    promotion_routes = tuple(
        route
        for route in registry.certificate_class_routes
        if route.certificate_role == "promotion" and route.claim_polarity == "false_accept"
    )
    for producer in _code_owned_promotion_offer_producers():
        owner_routes = tuple(
            route
            for route in promotion_routes
            if route.verifier_kernel_id == producer.verifier_kernel_id
        )
        if not owner_routes:
            raise ConfidenceLedgerError(
                "promotion_certificate_route_missing_for_owner_producer",
                producer.verifier_kernel_id,
            )
        if any(not producer.route_matches(route) for route in owner_routes):
            raise ConfidenceLedgerError(
                "promotion_certificate_route_owner_contract_mismatch",
                producer.verifier_kernel_id,
            )
    supplied_by_class: dict[str, list[PromotionCertificateOffer]] = {}
    for offer in promotion_input.certificate_offers:
        route = registry.resolve_certificate_route(offer.certificate_class)
        if route not in promotion_routes:
            raise ConfidenceLedgerError(
                "promotion_certificate_offer_route_invalid",
                offer.certificate_class,
            )
        supplied_by_class.setdefault(offer.certificate_class, []).append(offer)
    offers: list[PromotionCertificateOffer] = []
    for route in promotion_routes:
        assertions = list(supplied_by_class.get(route.certificate_class, ()))
        if len(assertions) > 1:
            raise ConfidenceLedgerError(
                "duplicate_promotion_certificate_offer",
                route.certificate_class,
            )
        owner_offer = _owner_offer_for_route(
            promotion_input,
            route=route,
        )
        if owner_offer is None:
            raise ConfidenceLedgerError(
                "promotion_certificate_offer_owner_recomputation_unavailable",
                route.certificate_class,
            )
        if assertions and assertions[0] != owner_offer:
            raise ConfidenceLedgerError(
                "promotion_certificate_offer_assertion_mismatch",
                route.certificate_class,
            )
        offer = owner_offer
        if offer.claim.claim_scope_ref != _promotion_offer_claim_scope_ref(
            promotion_input,
            route=route,
            certificate_ref=offer.certificate_ref,
            data_window_ref=offer.claim.data_window_ref,
            owner_projection_hash=offer.owner_projection_hash,
        ):
            raise ConfidenceLedgerError(
                "promotion_certificate_offer_owner_binding_mismatch",
                route.certificate_class,
            )
        offers.append(offer)
    request_keys = [item.request_key for item in offers]
    if len(request_keys) != len(set(request_keys)):
        raise ConfidenceLedgerError("duplicate_promotion_certificate_offer")
    return tuple(offers)


def _resolve_expected_ledger_check(
    ledger_receipt: ConfidenceLedgerReceipt,
    expected: PromotionCertificateOffer,
) -> ConfidenceLedgerCheck:
    matches = [
        check for check in ledger_receipt.checks if check.request_key == expected.request_key
    ]
    if len(matches) != 1:
        raise ConfidenceLedgerError(
            "promotion_expected_ledger_check_missing",
            expected.request_key,
        )
    check = matches[0]
    claim = expected.claim
    if (
        check.certificate_ref != expected.certificate_ref
        or check.certificate_class != expected.certificate_class
        or check.claim_ref != claim.claim_ref
        or check.null_ref != claim.null_ref
        or check.claim_scope_ref != claim.claim_scope_ref
        or check.data_window_ref != claim.data_window_ref
        or check.certificate_role != claim.certificate_role
        or check.claim_polarity != claim.claim_polarity
    ):
        raise ConfidenceLedgerError("promotion_expected_ledger_check_mismatch")
    return check


def _resolve_expected_ledger_checks(
    ledger_receipt: ConfidenceLedgerReceipt,
    offers: Sequence[PromotionCertificateOffer],
) -> tuple[ConfidenceLedgerCheck, ...]:
    """Resolve all current-candidate rows from the complete ledger receipt."""

    return tuple(_resolve_expected_ledger_check(ledger_receipt, offer) for offer in offers)


def _risk_record_for_check(
    risk_spend: PromotionRiskSpendSummary,
    check: ConfidenceLedgerCheck,
) -> PromotionRiskSpendRecord:
    matches = [
        item
        for item in risk_spend.spend_records
        if item.n11_confidence_ledger_ref == check.check_id
    ]
    if len(matches) != 1:
        raise ConfidenceLedgerError("promotion_risk_record_missing", check.check_id)
    return matches[0]


def _check_binds_compiled_obligation(
    promotion_input: CanonicalPromotionInput,
    *,
    registry: ConfidenceLedgerRegistry,
    obligation: PromotionObligationDraft,
    check: ConfidenceLedgerCheck,
    offers_by_class: Mapping[str, PromotionCertificateOffer],
) -> bool:
    """Recompute the exact owner projection and claim binding for one positive row."""

    certificate_class = check.certificate_class
    if certificate_class is None or check.owner_binding is None:
        return False
    offer = offers_by_class.get(certificate_class)
    if offer is None:
        return False
    route = registry.resolve_certificate_route(certificate_class)
    return bool(
        check.certificate_ref == offer.certificate_ref
        and check.data_window_ref == offer.claim.data_window_ref
        and check.certificate_ref in obligation.evidence_refs
        and check.data_window_ref in obligation.evidence_refs
        and check.owner_binding.owner_projection_hash == offer.owner_projection_hash
        and check.claim_scope_ref
        == _promotion_offer_claim_scope_ref(
            promotion_input,
            route=route,
            certificate_ref=check.certificate_ref,
            data_window_ref=check.data_window_ref,
            owner_projection_hash=offer.owner_projection_hash,
        )
    )


def _bind_certificate_checks_to_obligations(
    promotion_input: CanonicalPromotionInput,
    registry: ConfidenceLedgerRegistry,
    obligations: Sequence[PromotionObligationDraft],
    checks: Sequence[ConfidenceLedgerCheck],
    *,
    risk_spend: PromotionRiskSpendSummary,
) -> tuple[PromotionObligationDraft, ...]:
    """Apply every typed certificate offer through one obligation-class chokepoint."""

    checks_by_class: dict[PromotionObligationClass, list[ConfidenceLedgerCheck]] = {}
    for check in checks:
        checks_by_class.setdefault(check.obligation_class, []).append(check)
    offers_by_class = {
        offer.certificate_class: offer
        for offer in _promotion_certificate_offers(
            promotion_input,
            registry=registry,
        )
    }
    bound: list[PromotionObligationDraft] = []
    for obligation in obligations:
        class_checks = checks_by_class.get(obligation.obligation_class, [])
        if not class_checks or obligation.status != PromotionObligationStatus.SATISFIED:
            bound.append(obligation)
            continue
        supporting = next(
            (
                check
                for check in class_checks
                if check.execution_status == "executed"
                and check.supports_obligation
                and check.eligible_for_promotion
                and _check_binds_compiled_obligation(
                    promotion_input,
                    registry=registry,
                    obligation=obligation,
                    check=check,
                    offers_by_class=offers_by_class,
                )
            ),
            None,
        )
        if supporting is not None:
            bound.append(
                obligation.model_copy(
                    update={
                        "evidence_refs": [*obligation.evidence_refs, supporting.check_id],
                        "risk_spend": _risk_record_for_check(risk_spend, supporting),
                    }
                )
            )
            continue
        refusal = class_checks[-1]
        bound.append(
            _failed_obligation(
                obligation_class=obligation.obligation_class,
                gate_id=obligation.gate_id,
                owner_ref=(
                    "polisyos.runtime.quality.confidence_ledger."
                    "validate_confidence_ledger_receipt"
                ),
                detail=(
                    f"{obligation.obligation_class.value} cannot support promotion: "
                    "confidence ledger refusal or owner-claim binding failure "
                    f"{refusal.refusal_code or refusal.outcome}; check does not bind "
                    "the compiled obligation evidence."
                ),
                reason=PromotionFailClosedReason.SINGLE_OBLIGATION_FAIL,
            ).model_copy(
                update={
                    "evidence_refs": [check.check_id for check in class_checks],
                    "risk_spend": _risk_record_for_check(risk_spend, refusal),
                }
            )
        )
    return tuple(bound)


def _build_promotion_receipt_from_owners(
    promotion_input: CanonicalPromotionInput,
    *,
    registry: ConfidenceLedgerRegistry,
    ledger_receipt: ConfidenceLedgerReceipt,
    ledger_projection: N9PromotionCertificateProjection,
    ledger_semantic_projection: N9PromotionSemanticLedgerProjection,
    cg2_attempt: _CG2OwnerPromotabilityAttempt | None = None,
    base_obligations: tuple[PromotionObligationDraft, ...] | None = None,
) -> CanonicalPromotionReceipt:
    attempt = cg2_attempt or _resolve_cg2_owner_promotability(promotion_input)
    obligations = base_obligations or _compile_obligations(
        promotion_input,
        cg2_attempt=attempt,
    )
    expected_checks = _resolve_expected_ledger_checks(
        ledger_receipt,
        _promotion_certificate_offers(
            promotion_input,
            registry=registry,
        ),
    )
    risk_spend = _risk_spend_summary(expected_checks, ledger_projection)
    class_obligations = _bind_certificate_checks_to_obligations(
        promotion_input,
        registry,
        obligations,
        expected_checks,
        risk_spend=risk_spend,
    )
    obligations = _finalize_obligations(promotion_input, class_obligations)
    promotion_lane = _promotion_lane(attempt)
    gate_hash = _gate_outcome_hash(obligations)
    boundary = _computed_authority_boundary(promotion_input)
    refusal_reasons = _refusal_reasons(
        obligations,
        risk_spend=risk_spend,
        allow_non_authoritative_contract_scope_gaps=(promotion_lane == "contract_testing"),
    )
    promoted = not refusal_reasons
    consumer_promotable = promoted and _cg2_resolution_is_production_promotable(attempt)
    non_promotable_reason = _non_promotable_reason(attempt, promoted=promoted)
    if ledger_projection.authority_provenance == "verification":
        consumer_promotable = False
        non_promotable_reason = _VERIFICATION_NON_PROMOTABLE_REASON
    trace = None
    trace_hash = None
    if promoted:
        trace = _authority_derivation_trace(
            promotion_input,
            obligations=obligations,
            boundary=boundary,
            gate_hash=gate_hash,
            risk_spend=risk_spend,
            confidence_ledger_receipt=ledger_receipt,
            confidence_ledger_projection=ledger_projection,
        )
        trace_hash = recompute_authority_trace_hash(trace)
        trace = trace.model_copy(update={"trace_content_hash": trace_hash})
    return CanonicalPromotionReceipt(
        owner_projection=_owner_projection_from_input(promotion_input),
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
        confidence_ledger_scope_ref=ledger_projection.scope_id,
        confidence_ledger_head_id=ledger_projection.head_event_id,
        confidence_ledger_head_ref=ledger_projection.head_event_ref,
        confidence_ledger_receipt_id=ledger_projection.ledger_receipt_id,
        confidence_ledger_projection=ledger_projection,
        confidence_ledger_semantic_projection=ledger_semantic_projection,
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
        promotion_lane=promotion_lane,
        consumer_promotable=consumer_promotable,
        non_promotable_reason=non_promotable_reason,
        cg2_resolution_reason=(
            attempt.resolution.reason if attempt.resolution is not None else None
        ),
    )


def run_canonical_promotion_sequence(
    promotion_input: CanonicalPromotionInput,
    *,
    confidence_ledger_session: ConfidenceLedgerSession,
) -> CanonicalPromotionReceipt:
    """Run the single canonical N9 sequence over the real owner contracts."""

    if not isinstance(confidence_ledger_session, ConfidenceLedgerSession):
        raise TypeError("confidence_ledger_session_must_be_confidence_ledger_session")
    if not confidence_ledger_session.is_authority_session:
        raise ValueError("confidence_ledger_authority_session_required")
    return _run_promotion_sequence_with_bound_session(
        promotion_input,
        confidence_ledger_session=confidence_ledger_session,
    )


def _run_canonical_promotion_sequence_for_verification(
    promotion_input: CanonicalPromotionInput,
    *,
    confidence_ledger_session: ConfidenceLedgerSession,
) -> CanonicalPromotionReceipt:
    """Replay N9 in an isolated namespace that can never authorize a consumer."""

    if not isinstance(confidence_ledger_session, ConfidenceLedgerSession):
        raise TypeError("confidence_ledger_session_must_be_confidence_ledger_session")
    if (
        confidence_ledger_session.is_authority_session
        or confidence_ledger_session.authority_provenance != "verification"
    ):
        raise ValueError("confidence_ledger_verification_session_required")
    _require_canonical_verification_registry(
        confidence_ledger_session,
        repo_root=Path(__file__).resolve().parents[4],
    )
    return _run_promotion_sequence_with_bound_session(
        promotion_input,
        confidence_ledger_session=confidence_ledger_session,
    )


def _execute_promotion_certificate_offers(
    session: ConfidenceLedgerSession,
    offers: Sequence[PromotionCertificateOffer],
) -> tuple[ConfidenceLedgerCheck, ...]:
    """Prepare then close each predictable offer before advancing the ledger head."""

    checks: list[ConfidenceLedgerCheck] = []
    for offer in offers:
        try:
            check = session.prepare_offer(
                history_token=session.observe_history(),
                offer=offer,
            )
        except ConfidenceLedgerError as exc:
            try:
                check = _ledger_check_for_request(
                    session,
                    request_key=offer.request_key,
                )
            except ConfidenceLedgerError:
                raise exc from None
            if check.outcome != "preflight_refusal":
                raise
        if check.outcome == "prepared":
            check = session.execute_check(check)
        checks.append(check)
    return tuple(checks)


def _run_promotion_sequence_with_bound_session(
    promotion_input: CanonicalPromotionInput,
    *,
    confidence_ledger_session: ConfidenceLedgerSession,
) -> CanonicalPromotionReceipt:
    """Execute one sequence after its authority mode has been checked by a wrapper."""

    expected_scope = confidence_risk_scope_for_problem(promotion_input.design_problem_binding)
    if confidence_ledger_session.risk_scope != expected_scope:
        raise ValueError("confidence_ledger_scope_binding_mismatch")
    _execute_promotion_certificate_offers(
        confidence_ledger_session,
        _promotion_certificate_offers(
            promotion_input,
            registry=confidence_ledger_session.registry,
        ),
    )
    cg2_attempt = _resolve_cg2_owner_promotability(promotion_input)
    obligations = _compile_obligations(promotion_input, cg2_attempt=cg2_attempt)
    ledger_receipt = confidence_ledger_session.receipt()
    ledger_projection = project_n9_promotion_certificate(
        ledger_receipt,
        session=confidence_ledger_session,
    )
    ledger_semantic_projection = project_n9_promotion_semantic_ledger(
        ledger_receipt,
        session=confidence_ledger_session,
    )
    return _build_promotion_receipt_from_owners(
        promotion_input,
        registry=confidence_ledger_session.registry,
        ledger_receipt=ledger_receipt,
        ledger_projection=ledger_projection,
        ledger_semantic_projection=ledger_semantic_projection,
        cg2_attempt=cg2_attempt,
        base_obligations=obligations,
    )


def _rebind_promotion_receipt_to_ledger_head(
    receipt: CanonicalPromotionReceipt,
    *,
    promotion_input: CanonicalPromotionInput,
    registry: ConfidenceLedgerRegistry,
    ledger_receipt: ConfidenceLedgerReceipt,
    ledger_projection: N9PromotionCertificateProjection,
    ledger_semantic_projection: N9PromotionSemanticLedgerProjection,
) -> CanonicalPromotionReceipt:
    """Recompute one candidate decision against the batch's final ledger head."""

    del receipt
    return _build_promotion_receipt_from_owners(
        promotion_input,
        registry=registry,
        ledger_receipt=ledger_receipt,
        ledger_projection=ledger_projection,
        ledger_semantic_projection=ledger_semantic_projection,
    )


def _ledger_check_for_request(
    session: ConfidenceLedgerSession,
    *,
    request_key: str,
) -> ConfidenceLedgerCheck:
    matches = [check for check in session.receipt().checks if check.request_key == request_key]
    if len(matches) != 1:
        raise ConfidenceLedgerError("ledger_request_resolution_failed", request_key)
    return matches[0]


def _open_projected_confidence_ledger_session(
    projection: N9PromotionCertificateProjection,
    *,
    repo_root: Path | None,
) -> ConfidenceLedgerSession:
    root = (repo_root or Path(__file__).resolve().parents[4]).resolve()
    return ConfidenceLedgerSession.from_repo(
        root,
        risk_scope=projection.risk_scope,
    )


def validate_canonical_promotion_receipt(
    receipt: CanonicalPromotionReceipt | Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    candidate_summary: CandidateSummary | None = None,
    design_problem: DesignProblem | None = None,
    value_receipt: ValueGateReceipt | None = None,
) -> tuple[dict[str, Any], ...]:
    """Recompute an authority-bearing N9 receipt from the canonical deployment."""

    return _validate_promotion_receipt_with_bound_session(
        receipt,
        repo_root=repo_root,
        candidate_summary=candidate_summary,
        design_problem=design_problem,
        value_receipt=value_receipt,
        confidence_ledger_session=None,
        expected_authority_provenance="canonical_repo",
    )


def _validate_canonical_promotion_receipt_for_verification(
    receipt: CanonicalPromotionReceipt | Mapping[str, Any],
    *,
    repo_root: Path,
    confidence_ledger_session: ConfidenceLedgerSession,
    candidate_summary: CandidateSummary | None = None,
    design_problem: DesignProblem | None = None,
    value_receipt: ValueGateReceipt | None = None,
) -> tuple[dict[str, Any], ...]:
    """Recompute a non-authority replay receipt against its isolated current head."""

    if repo_root.resolve() != Path(__file__).resolve().parents[4]:
        return ({"code": "verification_owner_repo_root_invalid"},)
    try:
        _require_canonical_verification_registry(
            confidence_ledger_session,
            repo_root=repo_root.resolve(),
        )
    except ValueError:
        return ({"code": "confidence_ledger_verification_registry_invalid"},)
    return _validate_promotion_receipt_with_bound_session(
        receipt,
        repo_root=repo_root,
        candidate_summary=candidate_summary,
        design_problem=design_problem,
        value_receipt=value_receipt,
        confidence_ledger_session=confidence_ledger_session,
        expected_authority_provenance="verification",
    )


def admit_canonical_promotion_receipt_for_comparison(
    receipt: CanonicalPromotionReceipt | Mapping[str, Any],
    *,
    repo_root: Path,
    confidence_ledger_session: ConfidenceLedgerSession,
    candidate_summary: CandidateSummary | None = None,
    design_problem: DesignProblem | None = None,
    value_receipt: ValueGateReceipt | None = None,
) -> GyComparisonAdmission:
    """Return a comparison admission after full verification-owner replay.

    The returned value is ephemeral.  It binds one exact live receipt to the
    typed structural projection owned here; it is never serialized into a
    governed artifact and cannot be reconstructed from a provenance string or a
    self-computed projection hash.
    """

    parsed = (
        receipt
        if isinstance(receipt, CanonicalPromotionReceipt)
        else CanonicalPromotionReceipt.model_validate(receipt)
    )
    issues = _validate_canonical_promotion_receipt_for_verification(
        parsed,
        repo_root=repo_root,
        confidence_ledger_session=confidence_ledger_session,
        candidate_summary=candidate_summary,
        design_problem=design_problem,
        value_receipt=value_receipt,
    )
    if issues:
        raise ValueError(
            "promotion_comparison_admission_failed:"
            + json.dumps(issues, sort_keys=True, default=str)
        )
    payload = parsed.model_dump(mode="json")
    # Exercise the projection while the validating session is still live.
    canonical_promotion_receipt_semantic_projection(payload)

    def migrate_legacy(
        previous: Mapping[str, object],
        current: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Admit only the exact v2-to-v3 identity migration proven by this live run."""

        try:
            current_receipt = CanonicalPromotionReceipt.model_validate(current)
            if current_receipt != parsed:
                raise ValueError("live_receipt_drift")
            previous_schema = previous.get("schema_version")
            if previous_schema == GY_PROMOTION_SEQUENCE_SCHEMA_VERSION:
                previous_receipt = CanonicalPromotionReceipt.model_validate(previous)
                if previous_receipt.confidence_ledger_semantic_projection is not None:
                    if (
                        canonical_promotion_receipt_semantic_projection(previous)
                        != canonical_promotion_receipt_semantic_projection(current)
                    ):
                        raise ValueError("current_governing_projection_drift")
                    return previous
                migrated = {str(key): copy.deepcopy(item) for key, item in previous.items()}
                semantic = current_receipt.confidence_ledger_semantic_projection
                if semantic is None:
                    raise ValueError("semantic_projection_missing")
                migrated["confidence_ledger_semantic_projection"] = semantic.model_dump(
                    mode="json"
                )
                migrated_receipt = CanonicalPromotionReceipt.model_validate(migrated)
                migrated_payload = migrated_receipt.model_dump(mode="json")
                if (
                    canonical_promotion_receipt_semantic_projection(migrated_payload)
                    != canonical_promotion_receipt_semantic_projection(current)
                ):
                    raise ValueError("migrated_semantic_projection_drift")
                return migrated_payload
            if previous_schema != "policyos.policy_design_case.layer3_gy.n9_promotion.v2":
                raise ValueError("legacy_schema_not_admitted")
            _LegacyCanonicalPromotionReceiptV2.model_validate(previous)
            previous_projection = _canonical_promotion_receipt_legacy_semantic_projection(
                previous
            )
            current_projection = _canonical_promotion_receipt_legacy_semantic_projection(
                current
            )
            if previous_projection != current_projection:
                raise ValueError("legacy_governing_projection_drift")
            migrated = {str(key): copy.deepcopy(item) for key, item in current.items()}
            migrated_receipt = CanonicalPromotionReceipt.model_validate(migrated)
            if migrated_receipt != current_receipt:
                raise ValueError("migrated_semantic_projection_drift")
            return migrated_receipt.model_dump(mode="json")
        except (TypeError, ValueError) as exc:
            raise ValueError("promotion_legacy_comparison_semantic_mismatch") from exc

    return GyComparisonAdmission(
        owner_rule=CANONICAL_PROMOTION_VERIFICATION_COMPARISON_RULE,
        source_content_hash=gy_recorded_content_hash(payload),
        projector=canonical_promotion_receipt_semantic_projection,
        action=CANONICAL_PROMOTION_VERIFICATION_COMPARISON_OWNER_RULE.action,
        predicate_provenance=(
            CANONICAL_PROMOTION_VERIFICATION_COMPARISON_OWNER_RULE.predicate_provenance
        ),
        legacy_migrator=migrate_legacy,
    )


def prove_canonical_promotion_receipt_for_comparison(
    receipt: CanonicalPromotionReceipt | Mapping[str, Any],
    *,
    repo_root: Path,
    confidence_ledger_session: ConfidenceLedgerSession,
    candidate_summary: CandidateSummary | None = None,
    design_problem: DesignProblem | None = None,
    value_receipt: ValueGateReceipt | None = None,
) -> object:
    """Issue an opaque proof after the canonical live comparison admission.

    The proof is process-local and cannot be reconstructed from public
    ``GyComparisonAdmission`` fields. Consumers must return it to this module
    for unwrapping, preserving the live session/candidate validation boundary.
    """

    admission = admit_canonical_promotion_receipt_for_comparison(
        receipt,
        repo_root=repo_root,
        confidence_ledger_session=confidence_ledger_session,
        candidate_summary=candidate_summary,
        design_problem=design_problem,
        value_receipt=value_receipt,
    )
    return _issue_canonical_promotion_comparison_proof(admission)


def canonical_promotion_comparison_admission_from_proof(
    proof: object,
) -> GyComparisonAdmission:
    """Resolve one owner-issued proof to its exact comparison admission."""

    if type(proof) is not _CanonicalPromotionComparisonProof:
        raise ValueError("canonical_promotion_comparison_proof_invalid")
    admission = _ISSUED_CANONICAL_PROMOTION_COMPARISON_PROOFS.get(proof)
    if admission is None:
        raise ValueError("canonical_promotion_comparison_proof_invalid")
    return admission


def _require_canonical_verification_registry(
    session: ConfidenceLedgerSession,
    *,
    repo_root: Path,
) -> None:
    """Bind private replay to the registry owned by the loaded checkout."""

    canonical = load_confidence_ledger_registry(repo_root / DEFAULT_REGISTRY_RELATIVE_PATH)
    if (
        session.registry.content_hash != canonical.content_hash
        or session.registry.source_payload() != canonical.source_payload()
    ):
        raise ValueError("confidence_ledger_verification_registry_invalid")


def _validate_promotion_receipt_with_bound_session(
    receipt: CanonicalPromotionReceipt | Mapping[str, Any],
    *,
    repo_root: Path | None,
    candidate_summary: CandidateSummary | None,
    design_problem: DesignProblem | None,
    value_receipt: ValueGateReceipt | None,
    confidence_ledger_session: ConfidenceLedgerSession | None,
    expected_authority_provenance: Literal["canonical_repo", "verification"],
) -> tuple[dict[str, Any], ...]:
    """Recompute one receipt after its authority mode is fixed by a wrapper."""

    if not isinstance(receipt, CanonicalPromotionReceipt):
        try:
            receipt = CanonicalPromotionReceipt.model_validate(receipt)
        except ValueError as exc:
            return ({"code": "promotion_receipt_invalid", "error": str(exc)},)
    if receipt.confidence_ledger_projection.authority_provenance != expected_authority_provenance:
        return ({"code": "confidence_ledger_authority_provenance_invalid"},)
    if expected_authority_provenance == "verification" and (
        confidence_ledger_session is None
        or confidence_ledger_session.is_authority_session
        or confidence_ledger_session.authority_provenance != "verification"
    ):
        return ({"code": "confidence_ledger_verification_session_required"},)
    issues: list[dict[str, Any]] = []
    if candidate_summary is not None and (
        candidate_summary.model_dump(mode="json")
        != receipt.owner_projection.candidate_summary.model_dump(mode="json")
    ):
        issues.append({"code": "promotion_candidate_owner_binding_invalid"})
    try:
        replay_input = _input_from_owner_projection(
            receipt.owner_projection,
            repo_root=repo_root,
        )
    except ValueError as exc:
        issues.append(
            {
                "code": "promotion_owner_projection_invalid",
                "error": str(exc),
            }
        )
        return tuple(issues)
    replay_cg2_attempt = _resolve_cg2_owner_promotability(replay_input)
    replay_base_obligations = _compile_obligations(
        replay_input,
        cg2_attempt=replay_cg2_attempt,
    )
    issues.extend(
        _obligation_instance_issues(
            receipt.obligations,
            replay_input=replay_input,
        )
    )
    expected_scope = confidence_risk_scope_for_problem(replay_input.design_problem_binding)
    if receipt.confidence_ledger_projection.risk_scope != expected_scope:
        issues.append({"code": "confidence_ledger_scope_binding_mismatch"})
    if design_problem is not None and (
        N9DesignProblemBinding.from_problem(design_problem) != replay_input.design_problem_binding
    ):
        issues.append({"code": "promotion_problem_owner_binding_invalid"})
    if value_receipt is not None and (
        receipt.value_receipt_ref != value_receipt.value_ref
        or replay_input.value_receipt != value_receipt
    ):
        issues.append({"code": "promotion_value_owner_binding_invalid"})
    session = confidence_ledger_session
    validated_ledger: ConfidenceLedgerReceipt | None = None
    expected_semantic_projection: N9PromotionSemanticLedgerProjection | None = None
    try:
        if session is None:
            session = _open_projected_confidence_ledger_session(
                receipt.confidence_ledger_projection,
                repo_root=repo_root,
            )
        if session.risk_scope != expected_scope:
            raise ConfidenceLedgerError("confidence_ledger_scope_binding_mismatch")
        validated_ledger = validate_confidence_ledger_receipt(
            session.receipt(),
            session=session,
        )
        expected_projection = project_n9_promotion_certificate(
            validated_ledger,
            session=session,
        )
        expected_semantic_projection = project_n9_promotion_semantic_ledger(
            validated_ledger,
            session=session,
        )
    except (ConfidenceLedgerError, OSError, ValueError) as exc:
        issues.append(
            {
                "code": "confidence_ledger_recomputation_failed",
                "reason": getattr(exc, "code", type(exc).__name__),
                "detail": getattr(exc, "detail", str(exc)),
            }
        )
        expected_projection = None
    if (
        expected_projection is not None
        and receipt.confidence_ledger_projection != expected_projection
    ):
        issues.append({"code": "confidence_ledger_projection_drift"})
    if (
        expected_semantic_projection is not None
        and receipt.confidence_ledger_semantic_projection != expected_semantic_projection
    ):
        issues.append({"code": "confidence_ledger_semantic_projection_drift"})
    if (
        receipt.risk_spend.total_declared_delta
        != float(receipt.confidence_ledger_projection.total_spend.fraction)
        or receipt.risk_spend.budget_delta
        != float(receipt.confidence_ledger_projection.budget_delta.fraction)
        or receipt.risk_spend.within_budget
        is not receipt.confidence_ledger_projection.within_budget
    ):
        issues.append({"code": "risk_spend_not_derived_from_confidence_ledger"})
    ledger_checks = (
        {item.check_id: item for item in validated_ledger.checks}
        if expected_projection is not None
        else {}
    )
    expected_checks_by_class: dict[PromotionObligationClass, list[ConfidenceLedgerCheck]] = {}
    expected_offers_by_class: dict[str, PromotionCertificateOffer] = {}
    if validated_ledger is not None and session is not None:
        try:
            expected_offers = _promotion_certificate_offers(
                replay_input,
                registry=session.registry,
            )
            expected_checks = _resolve_expected_ledger_checks(
                validated_ledger,
                expected_offers,
            )
        except ConfidenceLedgerError as exc:
            issues.append(
                {
                    "code": "promotion_expected_ledger_check_invalid",
                    "reason": exc.code,
                    "detail": exc.detail,
                }
            )
        else:
            expected_offers_by_class = {
                offer.certificate_class: offer for offer in expected_offers
            }
            for check in expected_checks:
                expected_checks_by_class.setdefault(check.obligation_class, []).append(check)
    class_gate_obligations = _class_gate_obligations(receipt.obligations)
    classes = tuple(item.obligation_class for item in class_gate_obligations)
    expected = tuple(PromotionObligationClass)
    denominator_complete = classes == expected
    if not denominator_complete:
        issues.append(
            {
                "code": "promotion_obligation_denominator_mismatch",
                "expected": [item.value for item in expected],
                "actual": [item.value for item in classes],
            }
        )
    for obligation in class_gate_obligations:
        spend = obligation.risk_spend
        if spend is not None:
            check_ref = spend.n11_confidence_ledger_ref
            check = ledger_checks.get(check_ref or "")
            if (
                check is None
                or check.obligation_class != obligation.obligation_class
                or check.certificate_ref != spend.certificate_ref
                or check.instrument_id != spend.instrument
                or float(check.spend.fraction) != spend.declared_delta_spend
            ):
                issues.append(
                    {
                        "code": "obligation_confidence_ledger_binding_invalid",
                        "obligation_class": obligation.obligation_class.value,
                    }
                )
        class_checks = expected_checks_by_class.get(obligation.obligation_class, [])
        ledger_required = bool(class_checks)
        if (
            obligation.status == PromotionObligationStatus.SATISFIED
            and ledger_required
            and not any(
                check.execution_status == "executed"
                and check.supports_obligation
                and check.eligible_for_promotion
                and session is not None
                and _check_binds_compiled_obligation(
                    replay_input,
                    registry=session.registry,
                    obligation=obligation,
                    check=check,
                    offers_by_class=expected_offers_by_class,
                )
                and spend is not None
                and spend.n11_confidence_ledger_ref == check.check_id
                for check in class_checks
            )
        ):
            issues.append(
                {
                    "code": "probabilistic_certificate_bypassed_confidence_ledger",
                    "obligation_class": obligation.obligation_class.value,
                }
            )
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
        if (
            obligation.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
            and obligation.semantic_scope != "scope_insufficient"
        ):
            issues.append(
                {
                    "code": "scope_insufficient_semantic_scope_mismatch",
                    "obligation_class": obligation.obligation_class.value,
                }
            )
    decision_risk_spend = receipt.risk_spend.model_copy(
        update={
            "total_declared_delta": (
                float(expected_projection.total_spend.fraction)
                if expected_projection is not None
                else receipt.risk_spend.total_declared_delta
            ),
            "budget_delta": (
                float(expected_projection.budget_delta.fraction)
                if expected_projection is not None
                else receipt.risk_spend.budget_delta
            ),
            "within_budget": (
                expected_projection.within_budget if expected_projection is not None else False
            ),
        }
    )
    expected_refusal_reasons = _refusal_reasons(
        receipt.obligations,
        risk_spend=decision_risk_spend,
        allow_non_authoritative_contract_scope_gaps=(receipt.promotion_lane == "contract_testing"),
    )
    if not denominator_complete:
        expected_refusal_reasons.append("promotion_obligation_denominator_mismatch")
    if expected_projection is None:
        expected_refusal_reasons.append("confidence_ledger_recomputation_failed")
    expected_refusal_reasons = list(dict.fromkeys(expected_refusal_reasons))
    expected_promoted = not expected_refusal_reasons
    expected_status = "grounded_partial_admissible" if expected_promoted else "shadow"
    expected_terminal_kind = (
        SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE
        if expected_promoted
        else SearchTerminalKind.GROUNDED_ABSTENTION
    )
    expected_consumer_promotable = bool(
        expected_promoted
        and receipt.promotion_lane == "production"
        and receipt.non_promotable_reason is None
    )
    if receipt.refusal_reasons != tuple(expected_refusal_reasons):
        issues.append(
            {
                "code": "promotion_refusal_reasons_drift",
                "expected": expected_refusal_reasons,
                "actual": list(receipt.refusal_reasons),
            }
        )
    if receipt.promoted is not expected_promoted:
        issues.append(
            {
                "code": "promotion_promoted_drift",
                "expected": expected_promoted,
                "actual": receipt.promoted,
            }
        )
    if receipt.status != expected_status:
        issues.append(
            {
                "code": "promotion_status_drift",
                "expected": expected_status,
                "actual": receipt.status,
            }
        )
    if receipt.terminal_kind != expected_terminal_kind:
        issues.append(
            {
                "code": "promotion_terminal_kind_drift",
                "expected": expected_terminal_kind.value,
                "actual": receipt.terminal_kind.value,
            }
        )
    if receipt.consumer_promotable is not expected_consumer_promotable:
        issues.append(
            {
                "code": "promotion_consumer_promotable_drift",
                "expected": expected_consumer_promotable,
                "actual": receipt.consumer_promotable,
            }
        )
    trace_present = receipt.authority_derivation_trace is not None
    trace_hash_present = receipt.trace_content_hash is not None
    if trace_present is not expected_promoted or trace_hash_present is not expected_promoted:
        issues.append(
            {
                "code": "promotion_trace_presence_drift",
                "expected": expected_promoted,
                "trace_present": trace_present,
                "trace_hash_present": trace_hash_present,
            }
        )
    scope_gaps = [
        obligation
        for obligation in receipt.obligations
        if obligation.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
    ]
    if (
        receipt.promoted
        and scope_gaps
        and (receipt.promotion_lane != "contract_testing" or receipt.consumer_promotable)
    ):
        issues.append(
            {
                "code": "scope_insufficient_authority_laundering",
                "obligation_classes": [item.obligation_class.value for item in scope_gaps],
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
        if (
            trace.confidence_ledger_receipt_id != receipt.confidence_ledger_receipt_id
            or trace.confidence_ledger_projection_hash
            != receipt.confidence_ledger_projection.projection_hash
        ):
            issues.append({"code": "authority_trace_confidence_ledger_mismatch"})
    expected_receipt: CanonicalPromotionReceipt | None = None
    if (
        validated_ledger is not None
        and expected_projection is not None
        and expected_semantic_projection is not None
        and session is not None
    ):
        try:
            expected_receipt = _build_promotion_receipt_from_owners(
                replay_input,
                registry=session.registry,
                ledger_receipt=validated_ledger,
                ledger_projection=expected_projection,
                ledger_semantic_projection=expected_semantic_projection,
                cg2_attempt=replay_cg2_attempt,
                base_obligations=replay_base_obligations,
            )
        except ConfidenceLedgerError as exc:
            if exc.code in {
                "promotion_expected_ledger_check_missing",
                "promotion_expected_ledger_check_mismatch",
            }:
                if not any(
                    issue["code"] == "probabilistic_certificate_bypassed_confidence_ledger"
                    for issue in issues
                ):
                    issues.append(
                        {
                            "code": ("probabilistic_certificate_bypassed_confidence_ledger"),
                            "reason": exc.code,
                        }
                    )
            else:
                issues.append(
                    {
                        "code": "promotion_owner_recomputation_failed",
                        "reason": exc.code,
                    }
                )
    owner_fields = (
        "owner_projection",
        "candidate_id",
        "status",
        "promoted",
        "terminal_kind",
        "obligations",
        "risk_spend",
        "computed_authority_boundary",
        "authority_derivation_trace",
        "gate_outcome_hash",
        "trace_content_hash",
        "refusal_reasons",
        "value_receipt_ref",
        "value_method_family",
        "promotion_lane",
        "consumer_promotable",
        "non_promotable_reason",
        "cg2_resolution_reason",
        "sequence_ref",
    )
    if expected_receipt is not None and not issues:
        changed = [
            field
            for field in owner_fields
            if getattr(receipt, field) != getattr(expected_receipt, field)
        ]
        if changed:
            issues.append(
                {
                    "code": "promotion_owner_recomputation_drift",
                    "fields": changed,
                }
            )
    return tuple(issues)


def recompute_authority_trace_hash(trace: AuthorityDerivationTrace) -> str:
    """Return the content hash for a trace excluding its self hash field."""

    return gy_content_hash(trace.model_dump(mode="json", exclude={"trace_content_hash"}))


def _resolve_cg2_owner_promotability(
    promotion_input: CanonicalPromotionInput,
) -> _CG2OwnerPromotabilityAttempt:
    owner_ref = "polisyos.runtime.quality.grounding_bind.resolve_grounding_decision_promotability"
    certificate = promotion_input.grounding_decision_certificate
    reference = promotion_input.credal_reference
    if certificate is None or reference is None:
        return _CG2OwnerPromotabilityAttempt(resolution=None, owner_ref=owner_ref)
    resolver = resolve_grounding_decision_promotability
    if certificate.authority_scope == "contract_testing":
        resolver = resolve_grounding_decision_promotability_for_contract_testing
        owner_ref = (
            "polisyos.runtime.quality.grounding_bind."
            "resolve_grounding_decision_promotability_for_contract_testing"
        )
    try:
        resolution = resolver(certificate, reference)
    except Exception as exc:  # pragma: no cover - reported as typed refusal.
        return _CG2OwnerPromotabilityAttempt(
            resolution=None,
            owner_ref=owner_ref,
            error=repr(exc),
        )
    return _CG2OwnerPromotabilityAttempt(resolution=resolution, owner_ref=owner_ref)


def _cg2_resolution_is_contract_lane_bind(
    resolution: GroundingPromotabilityResolution,
) -> bool:
    return (
        resolution.decision == "bind"
        and resolution.authority_scope == "contract_testing"
        and resolution.store_authority_scope == "contract_testing"
        and resolution.reason == "non_production_anchor_scope"
        and resolution.content_hash_valid
        and resolution.reference_epoch_match
    )


def _cg2_resolution_is_production_promotable(
    attempt: _CG2OwnerPromotabilityAttempt,
) -> bool:
    resolution = attempt.resolution
    return bool(
        resolution is not None
        and resolution.promotable
        and resolution.authority_scope == "production"
        and resolution.store_authority_scope == "production"
    )


def _promotion_lane(
    attempt: _CG2OwnerPromotabilityAttempt,
) -> Literal["production", "contract_testing", "unresolved"]:
    resolution = attempt.resolution
    if resolution is None:
        return "unresolved"
    if (
        resolution.authority_scope == "contract_testing"
        or resolution.store_authority_scope == "contract_testing"
    ):
        return "contract_testing"
    return "production"


def _non_promotable_reason(
    attempt: _CG2OwnerPromotabilityAttempt,
    *,
    promoted: bool,
) -> str | None:
    resolution = attempt.resolution
    del promoted
    if resolution is None or _cg2_resolution_is_production_promotable(attempt):
        return None
    return resolution.reason


def _compile_obligations(
    promotion_input: CanonicalPromotionInput,
    *,
    cg2_attempt: _CG2OwnerPromotabilityAttempt,
) -> tuple[PromotionObligationDraft, ...]:
    receipt = promotion_input.value_receipt
    summary = promotion_input.candidate_summary
    obligations = [
        _syntax_obligation(promotion_input),
        _type_obligation(receipt),
        _slot_obligation(promotion_input),
        _param_obligation(promotion_input),
        _coupling_obligation(summary),
        _effect_obligation(promotion_input),
        _identification_obligation(promotion_input, cg2_attempt=cg2_attempt),
        _calibration_obligation(receipt),
        _measurement_obligation(receipt),
        _data_obligation(receipt),
        _implementation_obligation(promotion_input.s6_blind_spot_posture),
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


def _obligation_instance_scope_content_hash(
    promotion_input: CanonicalPromotionInput,
) -> str:
    binding = promotion_input.design_problem_binding
    summary = promotion_input.candidate_summary
    return gy_content_hash(
        {
            "rule_version": _PROMOTION_OBLIGATION_SCOPE_RULE_VERSION,
            "promotion_rule_version": promotion_input.schema_version,
            "design_problem_id": binding.design_problem_id,
            "problem_content_hash": binding.problem_content_hash,
            "candidate_id": summary.candidate_id,
            "candidate_content_hash": summary.content_hash,
            "operation_invocation_id": promotion_input.operation_invocation_id,
        }
    )


def _class_gate_source(
    draft: PromotionObligationDraft,
) -> tuple[str, str]:
    source_ref = (
        f"{PROMOTION_SEQUENCE_REF}#class_gate/{draft.obligation_class.value}"
    )
    source_content_hash = gy_content_hash(
        {
            "rule_version": _PROMOTION_CLASS_GATE_SOURCE_RULE_VERSION,
            "source_obligation_ref": source_ref,
            "obligation_class": draft.obligation_class.value,
            "gate_id": draft.gate_id.value,
            "owner_ref": draft.owner_ref,
        }
    )
    return source_ref, source_content_hash


def _decisive_predicate_obligations(
    promotion_input: CanonicalPromotionInput,
    *,
    instance_scope_content_hash: str,
) -> tuple[PromotionObligationRecord, ...]:
    receipt = promotion_input.value_receipt
    if receipt is None:
        return ()
    records: list[PromotionObligationRecord] = []
    for predicate in receipt.decisive_consistency_predicates():
        if not predicate.satisfied:
            raise ValueError("decisive_value_receipt_predicate_not_satisfied")
        source_ref = (
            "polisyos.runtime.quality.generation_cycle.ValueGateReceipt#"
            f"{predicate.predicate_id}"
        )
        draft = PromotionObligationDraft(
            obligation_class=PromotionObligationClass.SLOT,
            gate_id=PromotionGateId.N8_TRANSPORT,
            status=PromotionObligationStatus.SATISFIED,
            owner_ref=(
                "polisyos.runtime.quality.generation_cycle."
                "ValueGateReceipt.decisive_consistency_predicates"
            ),
            detail=(
                f"Generation owner recomputed {predicate.predicate_id}; this establishes "
                "receipt-internal consistency only."
            ),
            evidence_refs=list(
                dict.fromkeys(
                    (
                        predicate.content_hash,
                        predicate.observed_ref,
                        predicate.expected_ref,
                    )
                )
            ),
        )
        records.append(
            PromotionObligationRecord.from_draft(
                draft,
                obligation_role="decisive_predicate",
                source_obligation_ref=source_ref,
                source_obligation_content_hash=predicate.content_hash,
                instance_scope_content_hash=instance_scope_content_hash,
            )
        )
    return tuple(records)


def _finalize_obligations(
    promotion_input: CanonicalPromotionInput,
    class_obligations: Sequence[PromotionObligationDraft],
) -> tuple[PromotionObligationRecord, ...]:
    """Add run-scoped identity only after all class-level owner mutations."""

    if tuple(item.obligation_class for item in class_obligations) != tuple(
        PromotionObligationClass
    ):
        raise ValueError("promotion_obligation_denominator_not_total")
    scope_hash = _obligation_instance_scope_content_hash(promotion_input)
    finalized: list[PromotionObligationRecord] = []
    for draft in class_obligations:
        source_ref, source_content_hash = _class_gate_source(draft)
        finalized.append(
            PromotionObligationRecord.from_draft(
                draft,
                obligation_role="class_gate",
                source_obligation_ref=source_ref,
                source_obligation_content_hash=source_content_hash,
                instance_scope_content_hash=scope_hash,
            )
        )
    finalized.extend(
        _decisive_predicate_obligations(
            promotion_input,
            instance_scope_content_hash=scope_hash,
        )
    )
    instance_ids = [item.obligation_instance_id for item in finalized]
    if len(instance_ids) != len(set(instance_ids)):
        raise ValueError("promotion_obligation_instance_identity_collision")
    return tuple(finalized)


def _class_gate_obligations(
    obligations: Sequence[PromotionObligationRecord],
) -> tuple[PromotionObligationRecord, ...]:
    return tuple(item for item in obligations if item.obligation_role == "class_gate")


def _decisive_obligations(
    obligations: Sequence[PromotionObligationRecord],
) -> tuple[PromotionObligationRecord, ...]:
    return tuple(
        item for item in obligations if item.obligation_role == "decisive_predicate"
    )


def _obligation_instance_issues(
    obligations: Sequence[PromotionObligationRecord],
    *,
    replay_input: CanonicalPromotionInput,
) -> tuple[dict[str, Any], ...]:
    issues: list[dict[str, Any]] = []
    ids = [item.obligation_instance_id for item in obligations]
    duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
    for instance_id in duplicate_ids:
        issues.append(
            {
                "code": "duplicate_obligation_instance_id",
                "obligation_instance_id": instance_id,
            }
        )
    for obligation in obligations:
        expected_id = promotion_obligation_instance_id(
            obligation_role=obligation.obligation_role,
            obligation_class=obligation.obligation_class,
            gate_id=obligation.gate_id,
            source_obligation_ref=obligation.source_obligation_ref,
            source_obligation_content_hash=obligation.source_obligation_content_hash,
            instance_scope_content_hash=obligation.instance_scope_content_hash,
        )
        if obligation.obligation_instance_id != expected_id:
            issues.append(
                {
                    "code": "obligation_instance_identity_mismatch",
                    "obligation_instance_id": obligation.obligation_instance_id,
                }
            )

    scope_hash = _obligation_instance_scope_content_hash(replay_input)
    expected_decisive = _decisive_predicate_obligations(
        replay_input,
        instance_scope_content_hash=scope_hash,
    )
    expected_by_id = {item.obligation_instance_id: item for item in expected_decisive}
    actual_decisive = _decisive_obligations(obligations)
    actual_by_id = {item.obligation_instance_id: item for item in actual_decisive}
    for instance_id in expected_by_id.keys() - actual_by_id.keys():
        issues.append(
            {
                "code": "decisive_obligation_omitted",
                "obligation_instance_id": instance_id,
            }
        )
    for instance_id in actual_by_id.keys() - expected_by_id.keys():
        issues.append(
            {
                "code": "unexpected_decisive_obligation_instance",
                "obligation_instance_id": instance_id,
            }
        )
    for instance_id in expected_by_id.keys() & actual_by_id.keys():
        if actual_by_id[instance_id] != expected_by_id[instance_id]:
            issues.append(
                {
                    "code": "decisive_obligation_substituted",
                    "obligation_instance_id": instance_id,
                }
            )
    return tuple(issues)


def _syntax_obligation(promotion_input: CanonicalPromotionInput) -> PromotionObligationDraft:
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


def _type_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationDraft:
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


def _slot_obligation(promotion_input: CanonicalPromotionInput) -> PromotionObligationDraft:
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


def _param_obligation(promotion_input: CanonicalPromotionInput) -> PromotionObligationDraft:
    if promotion_input.declared_authority_transform.get("force_promote") is True:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.PARAM,
            gate_id=PromotionGateId.GY_WAIST,
            owner_ref="polisyos.pdc._impl.gy_waist.AuthorityDerivationTrace",
            detail="Forced promotion knob was declared by the caller.",
        )
    record_ref = promotion_input.g4_governed_promotion_ref
    if not record_ref:
        return _scope_insufficient_obligation(
            obligation_class=PromotionObligationClass.PARAM,
            gate_id=PromotionGateId.G4_GOVERNED_PROMOTION,
            owner_ref=_G4_PROMOTION_RECORDS_PATH.as_posix(),
            detail="G4 governed-promotion record is not resolved for this candidate.",
        )
    record, issue = _resolve_g4_governed_promotion_record(
        record_ref,
        repo_root=promotion_input.repo_root,
    )
    if record is None:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.PARAM,
            gate_id=PromotionGateId.G4_GOVERNED_PROMOTION,
            owner_ref=_G4_PROMOTION_RECORDS_PATH.as_posix(),
            detail=f"G4 owner refused governed-promotion record resolution: {issue}.",
        )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.PARAM,
        gate_id=PromotionGateId.G4_GOVERNED_PROMOTION,
        owner_ref=_G4_PROMOTION_RECORDS_PATH.as_posix(),
        detail=(
            "G4 owner record resolved through the persisted artifact; G4 minting is "
            f"not authoritative for N9 (state={record.get('promotion_state') or 'unknown'})."
        ),
        evidence_refs=[str(record["promotion_record_id"])],
    )


def _coupling_obligation(summary: CandidateSummary) -> PromotionObligationDraft:
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


def _effect_obligation(
    promotion_input: CanonicalPromotionInput,
) -> PromotionObligationDraft:
    if promotion_input.force_proof_timeout:
        return PromotionObligationDraft(
            obligation_class=PromotionObligationClass.EFFECT,
            gate_id=PromotionGateId.GYK_ENTAILMENT,
            status=PromotionObligationStatus.UNKNOWN,
            reason=PromotionFailClosedReason.PROOF_TIMEOUT,
            owner_ref="GY-K entailment witness",
            detail="Entailment proof timed out; N9 carries unknown and keeps the candidate shadow.",
        )
    return _scope_insufficient_obligation(
        obligation_class=PromotionObligationClass.EFFECT,
        gate_id=PromotionGateId.GYK_ENTAILMENT,
        owner_ref="GY-K entailment witness owner",
        detail=(
            "GY-K entailment witness owner is unwired; CG2 bind evidence remains confined "
            "to the identification obligation."
        ),
    )


def _identification_obligation(
    promotion_input: CanonicalPromotionInput,
    *,
    cg2_attempt: _CG2OwnerPromotabilityAttempt,
) -> PromotionObligationDraft:
    summary = promotion_input.candidate_summary
    if not summary.current_valid or summary.grounding_status != "current_valid":
        return _failed_obligation(
            obligation_class=PromotionObligationClass.IDENTIFICATION,
            gate_id=PromotionGateId.CGF_GROUNDING,
            owner_ref="polisyos.runtime.quality.generation_cycle.PolicyGroundingPort",
            detail=(
                f"CGF grounding did not produce current_valid (status={summary.grounding_status})."
            ),
        )
    if cg2_attempt.error is not None:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.IDENTIFICATION,
            gate_id=PromotionGateId.CG2_BIND_PROMOTABILITY,
            owner_ref=cg2_attempt.owner_ref,
            detail=f"CG2 owner resolution raised: {cg2_attempt.error}.",
        )
    resolution = cg2_attempt.resolution
    if resolution is None:
        return _failed_obligation(
            obligation_class=PromotionObligationClass.IDENTIFICATION,
            gate_id=PromotionGateId.CG2_BIND_PROMOTABILITY,
            owner_ref=cg2_attempt.owner_ref,
            detail=(
                "CG2 owner-store resolution could not run because the CG2 decision "
                "certificate or credal reference is missing."
            ),
        )
    if not resolution.promotable and not _cg2_resolution_is_contract_lane_bind(resolution):
        return _failed_obligation(
            obligation_class=PromotionObligationClass.IDENTIFICATION,
            gate_id=PromotionGateId.CG2_BIND_PROMOTABILITY,
            owner_ref=cg2_attempt.owner_ref,
            detail=f"CG2 owner-store refused bind promotability: {resolution.reason}.",
        )
    detail = (
        "CGF current_valid and CG2 production owner-store promotability both resolved."
        if resolution.promotable
        else "CGF current_valid and CG2 contract-test bind resolved with a non-promotable stamp."
    )
    return _satisfied_obligation(
        obligation_class=PromotionObligationClass.IDENTIFICATION,
        gate_id=PromotionGateId.CG2_BIND_PROMOTABILITY,
        owner_ref=cg2_attempt.owner_ref,
        detail=detail,
        evidence_refs=[resolution.certificate_id],
    )


def _calibration_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationDraft:
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


def _measurement_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationDraft:
    del receipt
    return _scope_insufficient_obligation(
        obligation_class=PromotionObligationClass.MEASUREMENT,
        gate_id=PromotionGateId.N8_VALUE,
        owner_ref="measurement-rooted producer owner",
        detail=(
            "Measurement-rooted producer owner is unwired; ValueOuterSet promotion_decision "
            "remains value-class semantics only."
        ),
    )


def _data_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationDraft:
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


def _implementation_obligation(
    blind_spot_posture: Layer2S6BlindSpotPostureInput | None,
) -> PromotionObligationDraft:
    return evaluate_s6_blind_spot_promotion_gate(blind_spot_posture)


def _resolve_g4_governed_promotion_record(
    record_ref: str,
    *,
    repo_root: Path | None,
) -> tuple[Mapping[str, Any] | None, str | None]:
    path = (repo_root or Path.cwd()) / _G4_PROMOTION_RECORDS_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"owner_artifact_missing:{_G4_PROMOTION_RECORDS_PATH.as_posix()}"
    except json.JSONDecodeError as exc:
        return None, f"owner_artifact_invalid_json:{exc}"
    records = payload.get("promotion_records") if isinstance(payload, Mapping) else None
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        return None, "owner_artifact_records_missing"
    wanted = record_ref.rsplit("#", 1)[-1]
    for item in records:
        if not isinstance(item, Mapping):
            continue
        record_id = str(item.get("promotion_record_id") or "")
        if record_ref == record_id or wanted == record_id:
            return item, None
    return None, "governed_promotion_record_not_found"


def _equilibrium_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationDraft:
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


def _eval_safety_obligation(receipt: ValueGateReceipt | None) -> PromotionObligationDraft:
    mode = receipt.evaluation_mode if receipt is not None else None
    if mode in {"sandbox_pilot", "field_pilot", "deployment"}:
        return _scope_insufficient_obligation(
            obligation_class=PromotionObligationClass.EVAL_SAFETY,
            gate_id=PromotionGateId.GY_O0_EVAL_SAFETY,
            owner_ref="GY-O0 eval-safety gate",
            detail="GY-O0 eval-safety owner is not implemented for pilot/deployment promotion.",
        )
    return PromotionObligationDraft(
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


def _value_obligation(promotion_input: CanonicalPromotionInput) -> PromotionObligationDraft:
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
) -> PromotionObligationDraft:
    return PromotionObligationDraft(
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
) -> PromotionObligationDraft:
    return PromotionObligationDraft(
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
) -> PromotionObligationDraft:
    return PromotionObligationDraft(
        obligation_class=obligation_class,
        gate_id=gate_id,
        status=PromotionObligationStatus.SCOPE_INSUFFICIENT,
        reason=PromotionFailClosedReason.SCOPE_INSUFFICIENT,
        owner_ref=owner_ref,
        detail=detail,
        semantic_scope="scope_insufficient",
    )


def _risk_spend_summary(
    checks: Sequence[ConfidenceLedgerCheck],
    projection: N9PromotionCertificateProjection,
) -> PromotionRiskSpendSummary:
    records = [
        PromotionRiskSpendRecord(
            obligation_class=check.obligation_class,
            certificate_ref=check.certificate_ref,
            instrument=check.instrument_id,
            certificate_role=check.certificate_role,
            claim_polarity=check.claim_polarity,
            declared_delta_spend=float(check.spend.fraction),
            deterministic_proof=check.deterministic_proof,
            n11_confidence_ledger_ref=check.check_id,
        )
        for check in checks
    ]
    return PromotionRiskSpendSummary(
        total_declared_delta=float(projection.total_spend.fraction),
        budget_delta=float(projection.budget_delta.fraction),
        within_budget=projection.within_budget,
        spend_records=records,
        caveat=PROMOTION_RISK_CONDITIONALITY_CAVEAT,
    )


def _gate_outcome_hash(obligations: Sequence[PromotionObligationRecord]) -> str:
    return gy_content_hash([item.model_dump(mode="json") for item in obligations])


def _computed_authority_boundary(promotion_input: CanonicalPromotionInput) -> AuthorityBoundary:
    receipt = promotion_input.value_receipt
    value_grade = "unsupported"
    if receipt is not None:
        decision = receipt.value_outer_set.promotion_decision()
        value_grade = "advisory_admissible" if decision.promotable else "unsupported"
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
    allow_non_authoritative_contract_scope_gaps: bool = False,
) -> list[str]:
    reasons: list[str] = []
    for obligation in obligations:
        if obligation.status in {
            PromotionObligationStatus.FAILED,
            PromotionObligationStatus.UNKNOWN,
        } or (
            obligation.status == PromotionObligationStatus.SCOPE_INSUFFICIENT
            and not allow_non_authoritative_contract_scope_gaps
        ):
            reason = obligation.reason.value if obligation.reason else "unknown"
            reasons.append(f"{obligation.obligation_class.value}:{reason}")
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
    confidence_ledger_receipt: ConfidenceLedgerReceipt,
    confidence_ledger_projection: N9PromotionCertificateProjection,
) -> AuthorityDerivationTrace:
    declared = dict(promotion_input.declared_authority_transform)
    requested_grade = declared.get("requested_decision_grade")
    computed_grade = boundary.decision_grade or "unsupported"
    disposition: Literal["matched", "downgraded", "rejected", "upgraded"] = "matched"
    if isinstance(requested_grade, str) and _requested_grade_exceeds_boundary(
        requested_grade,
        boundary,
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
        applicability_result_ref=("n9://obligations/" + gate_hash.removeprefix("sha256:")[:16]),
        calibration_refs=[
            ref
            for obligation in obligations
            if obligation.obligation_role == "class_gate"
            and obligation.obligation_class == PromotionObligationClass.CALIBRATION
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
        confidence_ledger_scope_ref=confidence_ledger_projection.scope_id,
        confidence_ledger_head_id=confidence_ledger_projection.head_event_id,
        confidence_ledger_receipt_id=confidence_ledger_receipt.receipt_id,
        confidence_ledger_projection_hash=confidence_ledger_projection.projection_hash,
        risk_spend_total=risk_spend.total_declared_delta,
        risk_budget_delta=risk_spend.budget_delta,
    )


def _requested_grade_exceeds_boundary(
    requested_grade: str,
    boundary: AuthorityBoundary,
) -> bool:
    try:
        requested_boundary = boundary.model_copy(update={"decision_grade": requested_grade})
    except ValueError:
        return False
    return boundary.permits_at_most(requested_boundary) and not requested_boundary.permits_at_most(
        boundary
    )


def _assert_generic_value_receipt(receipt: ValueGateReceipt) -> None:
    if not receipt.selected_method_fqn:
        raise ValueError("value_receipt_method_family_missing")


def _assert_panel_specific_value_receipt(receipt: ValueGateReceipt) -> None:
    if "did" not in receipt.selected_method_fqn.lower():
        raise ValueError("promotion_coupled_to_first_vertical_shape")


def _legacy_policy_promotion_callers(repo_root: Path) -> tuple[str, ...]:
    roots = [repo_root / "src" / "polisyos"]
    callers: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            relative = path.relative_to(repo_root).as_posix()
            if (
                "autotune" in relative
                or "tests/" in relative
                or relative == "src/polisyos/runtime/quality/promotion_sequence.py"
                or relative.endswith("/proving_ground/governed_promotion_gate.py")
            ):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if _call_name(node.func) in {
                    "consider_promotion",
                    "build_g4_promotion_records",
                }:
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
    "CanonicalPromotionOwnerProjection",
    "CanonicalPromotionReceipt",
    "CredalReferencePromotabilityProjection",
    "LegacyPromotionStrangleReceipt",
    "N9DesignProblemBinding",
    "PromotionCertificateOffer",
    "canonical_promotion_comparison_admission_from_proof",
    "confidence_risk_scope_for_problem",
    "prove_canonical_promotion_receipt_for_comparison",
    "recompute_authority_trace_hash",
    "run_canonical_promotion_sequence",
    "validate_canonical_promotion_receipt",
]
