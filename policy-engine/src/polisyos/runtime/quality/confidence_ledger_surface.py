"""Exact, scope-local confidence-risk projection over the semantic ledger."""

from __future__ import annotations

import re
from enum import StrEnum
from fractions import Fraction
from typing import TYPE_CHECKING, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from polisyos.core.canon import CanonSpec, fingerprint, to_canonical_bytes
from polisyos.pdc import PromotionObligationClass  # noqa: TC001
from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerRegistry,
    ConfidenceLedgerSemanticReceiptProjection,
    ConfidenceRiskBudgetScope,
    RationalSpec,
)
from polisyos.runtime.quality.obligation_coverage import (
    DECLARED_SET_RIDER,
    LOCALITY_RIDER,
    CoverageAssessment,
    CoverageSourceIdentity,
    ObligationCoverageEnvelope,
    reauthenticate_coverage_envelope,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import Ed25519Verifier, FileSystemCAS

SURFACE_SCHEMA_VERSION = "policyos.runtime.confidence_ledger_surface.v1"
SURFACE_RULE_VERSION = "policyos.runtime.confidence_ledger_surface.exact.v1"
RATIONAL_DISPLAY_VERSION = "policyos.runtime.exact_rational_display.v1"
_CANON = CanonSpec(exclude_none=False)
_REFUSAL_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,127}$")


class _StrictModel(BaseModel):
    """Strict immutable base for public confidence-risk surface contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class InstrumentBlocker(StrEnum):
    """Registry-resolved instrument blockers available at C01."""

    COVERAGE_ARGUMENT_MISSING = "coverage_argument_missing"
    NON_ANYTIME_VALID = "non_anytime_valid"
    OWNER_THEOREM_UNAVAILABLE = "owner_theorem_unavailable"
    OTHER_RUNTIME_REFUSAL = "other_runtime_refusal"


class AppointmentPosture(StrEnum):
    """Institutional authority posture available at C01."""

    INSTITUTIONAL_AUTHORITY_UNAPPOINTED = "institutional_authority_unappointed"


class SharedSafetyBlockedReason(StrEnum):
    """Complete typed reasons that block the shared exact safety evaluator."""

    TIMEOUT = "timeout"
    MISSING_INPUT_OR_INCOMPLETE_HISTORY = "missing_input_or_incomplete_history"
    PARSER_OR_SCHEMA_FAILURE = "parser_or_schema_failure"
    UNSUPPORTED_OR_OUT_OF_MODEL = "unsupported_or_out_of_model"
    EMPTY_CONSISTENCY_SET = "empty_consistency_set"
    MODEL_OBSERVATION_INCONSISTENT = "model_observation_inconsistent"
    UNPROVED_APPROXIMATION = "unproved_approximation"


class ConditionalDeltaAmount(_StrictModel):
    """One exact amount bound to its local envelope, scope, and disclosures."""

    amount: RationalSpec
    rational_display_version: Literal[RATIONAL_DISPLAY_VERSION]
    rational_display: str = Field(pattern=r"^[0-9]+/[1-9][0-9]*$")
    canonical_decimal: str = Field(min_length=1)
    semantic_role: str = Field(min_length=1)
    obligation_class: PromotionObligationClass | None
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    owner_scope_key: str = Field(min_length=1)
    coverage_envelope_ref: str = Field(
        pattern=r"^coverage-envelope:sha256:[0-9a-f]{64}$"
    )
    coverage_envelope_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    declared_obligation_classes_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    maintained_assumptions: tuple[
        Literal["obligation_completeness", "validator_soundness"], ...
    ]
    declared_set_rider: Literal[DECLARED_SET_RIDER]
    locality_rider: Literal[LOCALITY_RIDER]
    amount_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _display_and_hash_are_exact(self) -> Self:
        expected_display = format_exact_rational_v1(self.amount.fraction)
        if self.rational_display != expected_display:
            raise ValueError("conditional_amount_rational_display_mismatch")
        if self.canonical_decimal != format_canonical_decimal_v1(self.amount.fraction):
            raise ValueError("conditional_amount_canonical_decimal_mismatch")
        body = self.model_dump(mode="json", exclude={"amount_hash"})
        if self.amount_hash != fingerprint(body, prefix=True, canon_spec=_CANON):
            raise ValueError("conditional_amount_hash_mismatch")
        return self


class InstrumentClassSpend(_StrictModel):
    """Exact spend grouped by obligation class and instrument."""

    obligation_class: PromotionObligationClass
    instrument_id: str = Field(min_length=1)
    spend: ConditionalDeltaAmount


class ObligationClassRiskSpend(_StrictModel):
    """Exact allocation and observed spend posture for one obligation class."""

    obligation_class: PromotionObligationClass
    allocation: ConditionalDeltaAmount
    spent: ConditionalDeltaAmount
    remaining: ConditionalDeltaAmount
    overspend_amount: ConditionalDeltaAmount
    instrument_refs: tuple[str, ...]
    check_refs: tuple[str, ...]
    good_event_refs: tuple[str, ...]

    @model_validator(mode="after")
    def _arithmetic_is_exact(self) -> Self:
        values = (self.allocation, self.spent, self.remaining, self.overspend_amount)
        if any(item.obligation_class is not self.obligation_class for item in values):
            raise ValueError("class_spend_obligation_binding_mismatch")
        allocation = self.allocation.amount.fraction
        spent = self.spent.amount.fraction
        if self.remaining.amount.fraction != max(allocation - spent, Fraction()):
            raise ValueError("class_spend_remaining_mismatch")
        if self.overspend_amount.amount.fraction != max(spent - allocation, Fraction()):
            raise ValueError("class_spend_overspend_mismatch")
        return self


class ScopeRiskSpend(_StrictModel):
    """Exact allocation and observed spend posture for the one resolved scope."""

    allocation: ConditionalDeltaAmount
    spent: ConditionalDeltaAmount
    remaining: ConditionalDeltaAmount
    overspend_amount: ConditionalDeltaAmount

    @model_validator(mode="after")
    def _arithmetic_is_exact(self) -> Self:
        values = (self.allocation, self.spent, self.remaining, self.overspend_amount)
        if any(item.obligation_class is not None for item in values):
            raise ValueError("scope_spend_must_not_claim_obligation_class")
        allocation = self.allocation.amount.fraction
        spent = self.spent.amount.fraction
        if self.remaining.amount.fraction != max(allocation - spent, Fraction()):
            raise ValueError("scope_spend_remaining_mismatch")
        if self.overspend_amount.amount.fraction != max(spent - allocation, Fraction()):
            raise ValueError("scope_spend_overspend_mismatch")
        return self


class InstrumentDefinitionRow(_StrictModel):
    """Registry definition with its resolved proof posture."""

    instrument_id: str = Field(min_length=1)
    instrument_family: str = Field(min_length=1)
    proof_profile_id: str = Field(min_length=1)
    certificate_roles: tuple[
        Literal["promotion", "promotion_conformance", "refusal", "acquisition", "admission"],
        ...,
    ]
    proof_kernel_id: str = Field(min_length=1)
    guarantee_kind: str = Field(min_length=1)
    deterministic: bool
    anytime_valid: bool
    permits_obligation_satisfaction: bool
    blocker: InstrumentBlocker | None


class CertificateRouteRow(_StrictModel):
    """One canonical certificate route with resolved instrument proof posture."""

    certificate_class: str = Field(min_length=1)
    obligation_class: PromotionObligationClass
    instrument_id: str = Field(min_length=1)
    instrument_family: str = Field(min_length=1)
    certificate_role: Literal[
        "promotion", "promotion_conformance", "refusal", "acquisition", "admission"
    ]
    claim_polarity: Literal[
        "false_accept",
        "confident_wrong_refusal",
        "confident_wrong_admission",
        "conformance_only",
    ]
    owner_ref: str = Field(min_length=1)
    verifier_kernel_id: str = Field(min_length=1)
    verifier_ref: str = Field(min_length=1)
    proof_profile_id: str = Field(min_length=1)
    proof_kernel_id: str = Field(min_length=1)
    guarantee_kind: str = Field(min_length=1)
    deterministic: bool
    anytime_valid: bool
    permits_obligation_satisfaction: bool
    blocker: InstrumentBlocker | None
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    route_binding_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _binding_hash_is_exact(self) -> Self:
        body = self.model_dump(mode="json", exclude={"route_binding_hash"})
        if self.route_binding_hash != fingerprint(body, prefix=True, canon_spec=_CANON):
            raise ValueError("certificate_route_registry_binding_mismatch")
        return self


class InstrumentInstanceRow(_StrictModel):
    """One actual semantic-ledger instance with recomputed proof posture."""

    instance_ref: str = Field(min_length=1)
    obligation_class: PromotionObligationClass
    instrument_id: str = Field(min_length=1)
    instrument_family: str = Field(min_length=1)
    proof_profile_id: str = Field(min_length=1)
    certificate_class: str | None
    certificate_route_ref: str | None
    certificate_ref: str = Field(min_length=1)
    certificate_role: Literal[
        "promotion", "promotion_conformance", "refusal", "acquisition", "admission"
    ]
    execution_status: Literal["prepared", "started", "executed", "refused", "unexecuted"]
    outcome: Literal[
        "prepared",
        "started",
        "supported",
        "not_supported",
        "preflight_refusal",
        "cancelled",
        "owner_refused",
        "owner_error",
        "recovered_crash",
        "refused",
    ]
    spend: ConditionalDeltaAmount
    anytime_valid: bool
    supports_obligation: bool
    eligible_for_promotion: bool
    blocker: InstrumentBlocker | None
    raw_runtime_refusal_source: str | None


class PositiveRegisterPredicate(StrEnum):
    """Complete source-derived predicates needed to populate the register."""

    OWNER_VALIDATED_PROMOTION_ROW = "owner_validated_promotion_row"
    EXECUTION_COMPLETED_SUPPORTED = "execution_completed_supported"
    REGISTRY_PROFILE_ANYTIME_VALID = "registry_profile_anytime_valid"
    OBLIGATION_SUPPORTED_AND_ELIGIBLE = "obligation_supported_and_eligible"
    TOTAL_AND_CLASS_SPEND_WITHIN_BUDGET = "total_and_class_spend_within_budget"
    COVERAGE_SUPPORTS_PROTECTED_USE = "coverage_supports_protected_use"
    INSTITUTIONAL_AUTHORITY_APPOINTED = "institutional_authority_appointed"


class PositiveCertificateRegister(_StrictModel):
    """Explicit honest-zero positive register with no appointed authority."""

    entries: tuple[()] = ()
    population_count: Literal[0] = 0
    population_state: Literal["valid_zero"] = "valid_zero"
    authority_posture: AppointmentPosture = (
        AppointmentPosture.INSTITUTIONAL_AUTHORITY_UNAPPOINTED
    )
    verified_appointment_refs: tuple[()] = ()
    appointment_denominator_state: Literal["recomputed_empty"] = "recomputed_empty"
    appointment_sufficiency_state: Literal["not_established"] = "not_established"
    blockers: tuple[ReasonAlgebraRow, ...]
    would_populate_when: tuple[PositiveRegisterPredicate, ...]


class GoodEventPosture(_StrictModel):
    """Union-bound posture without an independence claim."""

    independence_claim: Literal[False] = False
    composition_rule: Literal["union_bound"] = "union_bound"
    good_event_clause: str = Field(min_length=1)
    executed_probabilistic_good_event_refs: tuple[str, ...]


class ReasonAlgebraRow(_StrictModel):
    """One tagged available-domain reason."""

    slot: Literal["coverage_assessment", "instrument_blocker", "appointment_posture"]
    value: str = Field(min_length=1)

    @model_validator(mode="after")
    def _value_is_legal_for_slot(self) -> Self:
        enum_type = {
            "coverage_assessment": CoverageAssessment,
            "instrument_blocker": InstrumentBlocker,
            "appointment_posture": AppointmentPosture,
        }[self.slot]
        try:
            enum_type(self.value)
        except ValueError as exc:
            raise ValueError("confidence_reason_slot_value_mismatch") from exc
        return self


class DS17ReasonAlgebra(_StrictModel):
    """Reconciliation of typed declarations and independently reachable emitters."""

    declared_rows: tuple[ReasonAlgebraRow, ...]
    reachable_rows: tuple[ReasonAlgebraRow, ...]

    @property
    def rows(self) -> tuple[ReasonAlgebraRow, ...]:
        """Return the reconciled declared denominator."""

        return self.declared_rows

    @model_validator(mode="after")
    def _sets_reconcile(self) -> Self:
        if set(self.declared_rows) != set(self.reachable_rows):
            raise ValueError("DS17_reason_algebra_reachable_mismatch")
        return self


class ConfidenceLedgerRiskSpendProjection(_StrictModel):
    """Candidate scope-local surface; exact admission reauthenticates witnesses."""

    schema_version: Literal[SURFACE_SCHEMA_VERSION]
    rule_version: Literal[SURFACE_RULE_VERSION]
    source_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_basis: ConfidenceLedgerRegistry
    semantic_ledger_basis: ConfidenceLedgerSemanticReceiptProjection
    risk_scope: ConfidenceRiskBudgetScope
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    owner_scope_key: str = Field(min_length=1)
    fixed_scope_disclosure: Literal[LOCALITY_RIDER]
    source_provenance: tuple[CoverageSourceIdentity, ...]
    coverage_envelope: ObligationCoverageEnvelope
    coverage_envelope_ref: str = Field(
        pattern=r"^coverage-envelope:sha256:[0-9a-f]{64}$"
    )
    coverage_assessment: CoverageAssessment
    obligation_class_risk_spend: tuple[ObligationClassRiskSpend, ...]
    scope_total_risk_spend: ScopeRiskSpend
    grouped_spend: tuple[InstrumentClassSpend, ...]
    total_spend: ConditionalDeltaAmount
    budget_posture: Literal["within_budget", "over_spend"]
    instrument_definitions: tuple[InstrumentDefinitionRow, ...]
    certificate_routes: tuple[CertificateRouteRow, ...]
    certificate_route_denominator_count: int = Field(ge=0)
    certificate_route_denominator_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    instrument_instances: tuple[InstrumentInstanceRow, ...]
    refusal_instance_refs: tuple[str, ...]
    acquisition_instance_refs: tuple[str, ...]
    conformance_instance_refs: tuple[str, ...]
    instrument_blockers: tuple[InstrumentBlocker, ...]
    positive_register: PositiveCertificateRegister
    appointment_posture: AppointmentPosture
    good_event_posture: GoodEventPosture
    status: Literal["not_promoted"]
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _sets_and_hash_are_bound(self) -> Self:
        if (
            self.registry_basis.content_hash != self.registry_content_hash
            or self.semantic_ledger_basis.projection_hash
            != self.source_projection_hash
            or self.semantic_ledger_basis.registry_content_hash
            != self.registry_content_hash
            or self.semantic_ledger_basis.risk_scope != self.risk_scope
            or self.semantic_ledger_basis.scope_id != self.scope_id
            or self.risk_scope != self.coverage_envelope.declared_scope
            or self.risk_scope.scope_id != self.scope_id
            or self.risk_scope.owner_scope_key != self.owner_scope_key
            or self.coverage_envelope.scope_id != self.scope_id
            or self.coverage_envelope.owner_scope_key != self.owner_scope_key
            or self.coverage_envelope.envelope_ref != self.coverage_envelope_ref
            or self.coverage_assessment is not self.coverage_envelope.assessment
            or self.source_provenance != self.coverage_envelope.source_identities
            or self.fixed_scope_disclosure != self.coverage_envelope.locality_rider
            or self.registry_content_hash
            != self.coverage_envelope.source_identities[0].content_hash
            or self.source_projection_hash
            != self.coverage_envelope.source_identities[1].content_hash
        ):
            raise ValueError("confidence_risk_surface_top_scope_binding_mismatch")
        role_sets = (
            set(self.refusal_instance_refs),
            set(self.acquisition_instance_refs),
            set(self.conformance_instance_refs),
        )
        if any(role_sets[i] & role_sets[j] for i in range(3) for j in range(i + 1, 3)):
            raise ValueError("confidence_instance_roles_not_disjoint")
        if self.total_spend != self.scope_total_risk_spend.spent:
            raise ValueError("confidence_scope_total_spend_alias_mismatch")
        route_classes = [row.certificate_class for row in self.certificate_routes]
        if (
            len(self.certificate_routes) != self.certificate_route_denominator_count
            or len(route_classes) != len(set(route_classes))
            or any(
                row.registry_content_hash != self.registry_content_hash
                for row in self.certificate_routes
            )
            or self.certificate_route_denominator_hash
            != fingerprint(
                [row.route_binding_hash for row in self.certificate_routes],
                prefix=True,
                canon_spec=_CANON,
            )
        ):
            raise ValueError("confidence_certificate_route_denominator_binding_mismatch")
        amounts = [self.total_spend]
        amounts.extend(
            (
                self.scope_total_risk_spend.allocation,
                self.scope_total_risk_spend.spent,
                self.scope_total_risk_spend.remaining,
                self.scope_total_risk_spend.overspend_amount,
            )
        )
        for row in self.obligation_class_risk_spend:
            amounts.extend((row.allocation, row.spent, row.remaining, row.overspend_amount))
        amounts.extend(row.spend for row in self.grouped_spend)
        amounts.extend(row.spend for row in self.instrument_instances)
        declared_classes_hash = fingerprint(
            [item.value for item in self.coverage_envelope.declared_obligation_classes],
            prefix=True,
            canon_spec=_CANON,
        )
        if any(
            amount.scope_id != self.scope_id
            or amount.owner_scope_key != self.owner_scope_key
            or amount.coverage_envelope_ref != self.coverage_envelope_ref
            or amount.coverage_envelope_hash != self.coverage_envelope.envelope_hash
            or amount.maintained_assumptions
            != self.coverage_envelope.maintained_assumptions
            or amount.declared_obligation_classes_hash != declared_classes_hash
            or amount.declared_set_rider != self.coverage_envelope.declared_set_rider
            or amount.locality_rider != self.coverage_envelope.locality_rider
            for amount in amounts
        ):
            raise ValueError("confidence_risk_surface_nested_amount_binding_mismatch")
        expected_body = _build_projection_body(
            registry=self.registry_basis,
            semantic_ledger=self.semantic_ledger_basis,
            coverage_envelope=self.coverage_envelope,
        )
        observed_body = self.model_dump(mode="json", exclude={"projection_hash"})
        if to_canonical_bytes(observed_body, _CANON) != to_canonical_bytes(
            expected_body, _CANON
        ):
            raise ValueError("confidence_risk_surface_recursive_basis_mismatch")
        body = self.model_dump(mode="json", exclude={"projection_hash"})
        if self.projection_hash != fingerprint(body, prefix=True, canon_spec=_CANON):
            raise ValueError("confidence_risk_surface_hash_mismatch")
        return self


class DomainProjectionExactAdmission(_StrictModel):
    """Exact admission after canonical projection revalidation."""

    status: Literal["exact"] = "exact"
    projection: ConfidenceLedgerRiskSpendProjection


class DomainProjectionBlockedAdmission(_StrictModel):
    """Typed domain-admission rejection derived from a real validation failure."""

    status: Literal["blocked"] = "blocked"
    reason: SharedSafetyBlockedReason


type DomainProjectionAdmission = (
    DomainProjectionExactAdmission | DomainProjectionBlockedAdmission
)


def format_exact_rational_v1(value: Fraction) -> str:
    """Return the versioned exact numerator/denominator display."""

    normalized = Fraction(value)
    return f"{normalized.numerator}/{normalized.denominator}"


def format_canonical_decimal_v1(value: Fraction) -> str:
    """Return an exact canonical decimal, using parentheses for a repetend."""

    normalized = Fraction(value)
    whole, remainder = divmod(normalized.numerator, normalized.denominator)
    if remainder == 0:
        return str(whole)
    digits: list[str] = []
    seen: dict[int, int] = {}
    while remainder and remainder not in seen:
        seen[remainder] = len(digits)
        remainder *= 10
        digit, remainder = divmod(remainder, normalized.denominator)
        digits.append(str(digit))
    if remainder:
        repeat_at = seen[remainder]
        decimal = "".join(digits[:repeat_at]) + "(" + "".join(digits[repeat_at:]) + ")"
    else:
        decimal = "".join(digits)
    return f"{whole}.{decimal}"


def build_conditional_delta_amount(
    *,
    registry: ConfidenceLedgerRegistry,
    envelope: ObligationCoverageEnvelope,
    amount: Fraction | None = None,
    semantic_role: str = "declared_delta",
    obligation_class: PromotionObligationClass | None = None,
) -> ConditionalDeltaAmount:
    """Build an exact amount bound to the canonical registry and envelope."""

    if not isinstance(registry, ConfidenceLedgerRegistry):
        raise TypeError("conditional_amount_registry_must_be_typed")
    if not isinstance(envelope, ObligationCoverageEnvelope):
        raise TypeError("conditional_amount_coverage_envelope_must_be_typed")
    if registry.content_hash != envelope.source_identities[0].content_hash:
        raise ValueError("conditional_amount_registry_envelope_binding_mismatch")
    selected = registry.policy.delta.fraction if amount is None else Fraction(amount)
    if selected < 0:
        raise ValueError("conditional_amount_must_be_nonnegative")
    rational = RationalSpec(numerator=selected.numerator, denominator=selected.denominator)
    body = {
        "amount": rational,
        "rational_display_version": RATIONAL_DISPLAY_VERSION,
        "rational_display": format_exact_rational_v1(selected),
        "canonical_decimal": format_canonical_decimal_v1(selected),
        "semantic_role": semantic_role,
        "obligation_class": obligation_class,
        "scope_id": envelope.scope_id,
        "owner_scope_key": envelope.owner_scope_key,
        "coverage_envelope_ref": envelope.envelope_ref,
        "coverage_envelope_hash": envelope.envelope_hash,
        "declared_obligation_classes_hash": fingerprint(
            [item.value for item in envelope.declared_obligation_classes],
            prefix=True,
            canon_spec=_CANON,
        ),
        "maintained_assumptions": envelope.maintained_assumptions,
        "declared_set_rider": DECLARED_SET_RIDER,
        "locality_rider": LOCALITY_RIDER,
    }
    return ConditionalDeltaAmount.model_validate(
        {**body, "amount_hash": fingerprint(body, prefix=True, canon_spec=_CANON)}
    )


def bind_conditional_delta_amount(
    *,
    amount: ConditionalDeltaAmount,
    envelope: ObligationCoverageEnvelope,
    registry: ConfidenceLedgerRegistry,
) -> ConditionalDeltaAmount:
    """Validate that an existing typed amount is bound to this exact envelope."""

    if not isinstance(amount, ConditionalDeltaAmount):
        raise TypeError("conditional_amount_must_be_typed")
    if not isinstance(envelope, ObligationCoverageEnvelope):
        raise TypeError("coverage_envelope_must_be_typed")
    if not isinstance(registry, ConfidenceLedgerRegistry):
        raise TypeError("conditional_amount_registry_must_be_typed")
    if (
        amount.scope_id != envelope.scope_id
        or amount.owner_scope_key != envelope.owner_scope_key
        or amount.coverage_envelope_ref != envelope.envelope_ref
        or amount.coverage_envelope_hash != envelope.envelope_hash
        or amount.maintained_assumptions != envelope.maintained_assumptions
        or amount.declared_obligation_classes_hash
        != fingerprint(
            [item.value for item in envelope.declared_obligation_classes],
            prefix=True,
            canon_spec=_CANON,
        )
        or registry.content_hash != envelope.source_identities[0].content_hash
    ):
        raise ValueError("conditional_amount_scope_envelope_binding_mismatch")
    return amount


def derive_ds17_reason_algebra(*, registry: ConfidenceLedgerRegistry) -> DS17ReasonAlgebra:
    """Derive tagged declarations and reachable emitters without a seven-row table."""

    declared = tuple(
        ReasonAlgebraRow(slot=slot, value=item.value)
        for slot, enum_type in (
            ("coverage_assessment", CoverageAssessment),
            ("instrument_blocker", InstrumentBlocker),
            ("appointment_posture", AppointmentPosture),
        )
        for item in enum_type
    )
    reachable_blockers = {
        blocker
        for profile in registry.proof_profiles
        for blocker in (_derive_instrument_blocker(profile.refusal_code, None),)
        if blocker is not None
    }
    if any(profile.refusal_code is None for profile in registry.proof_profiles):
        catchall = _derive_instrument_blocker(None, "unrecognized_runtime_refusal")
        if catchall is not None:
            reachable_blockers.add(catchall)
    ordered_reachable_blockers = tuple(
        item for item in InstrumentBlocker if item in reachable_blockers
    )
    reachable = (
        *(
            ReasonAlgebraRow(slot="coverage_assessment", value=item.value)
            for item in CoverageAssessment
        ),
        *(
            ReasonAlgebraRow(slot="instrument_blocker", value=item.value)
            for item in ordered_reachable_blockers
        ),
        *(
            ReasonAlgebraRow(slot="appointment_posture", value=item.value)
            for item in AppointmentPosture
        ),
    )
    return DS17ReasonAlgebra(declared_rows=declared, reachable_rows=reachable)


def _build_projection_body(
    *,
    registry: ConfidenceLedgerRegistry,
    semantic_ledger: ConfidenceLedgerSemanticReceiptProjection,
    coverage_envelope: ObligationCoverageEnvelope,
    caller_eligibility_by_instrument: dict[str, bool] | None = None,
) -> dict[str, object]:
    """Recompute the complete projection body from its typed source basis."""

    del caller_eligibility_by_instrument
    if not isinstance(registry, ConfidenceLedgerRegistry):
        raise TypeError("confidence_surface_registry_must_be_typed")
    if not isinstance(semantic_ledger, ConfidenceLedgerSemanticReceiptProjection):
        raise TypeError("confidence_surface_semantic_ledger_must_be_typed")
    if not isinstance(coverage_envelope, ObligationCoverageEnvelope):
        raise TypeError("confidence_surface_coverage_envelope_must_be_typed")
    if (
        semantic_ledger.registry_content_hash != registry.content_hash
        or semantic_ledger.scope_id != coverage_envelope.scope_id
        or semantic_ledger.risk_scope.owner_scope_key != coverage_envelope.owner_scope_key
    ):
        raise ValueError("confidence_surface_source_scope_binding_mismatch")

    instances: list[InstrumentInstanceRow] = []
    blockers: list[InstrumentBlocker] = []
    grouped: dict[tuple[PromotionObligationClass, str], Fraction] = {}
    refusal_refs: list[str] = []
    acquisition_refs: list[str] = []
    conformance_refs: list[str] = []
    for check in semantic_ledger.checks:
        definition = registry.resolve_instrument(check.instrument_id)
        profile = registry.resolve_proof_profile(definition.proof_profile_id)
        if (
            check.instrument_family != definition.instrument_family
            or check.proof_profile_id != profile.profile_id
            or check.certificate_role not in definition.certificate_roles
        ):
            raise ValueError("confidence_surface_registry_profile_binding_mismatch")
        route_ref: str | None = None
        if check.certificate_class is not None:
            route = registry.resolve_certificate_route(check.certificate_class)
            if (
                route.instrument_id != check.instrument_id
                or route.obligation_class is not check.obligation_class
                or route.certificate_role != check.certificate_role
            ):
                raise ValueError("confidence_surface_certificate_route_binding_mismatch")
            route_ref = route.verifier_ref
        blocker = _derive_instrument_blocker(profile.refusal_code, check.refusal_code)
        if blocker is not None and blocker not in blockers:
            blockers.append(blocker)
        spend = build_conditional_delta_amount(
            registry=registry,
            envelope=coverage_envelope,
            amount=check.spend.fraction,
            semantic_role=f"instrument_instance_spend:{check.request_key}",
            obligation_class=check.obligation_class,
        )
        recomputed_eligible = (
            check.certificate_role == "promotion"
            and check.execution_status == "executed"
            and check.outcome == "supported"
            and profile.anytime_valid
            and profile.permits_obligation_satisfaction
            and check.supports_obligation
            and blocker is None
        )
        instances.append(
            InstrumentInstanceRow(
                instance_ref=check.request_key,
                obligation_class=check.obligation_class,
                instrument_id=check.instrument_id,
                instrument_family=definition.instrument_family,
                proof_profile_id=profile.profile_id,
                certificate_class=check.certificate_class,
                certificate_route_ref=route_ref,
                certificate_ref=check.certificate_ref,
                certificate_role=check.certificate_role,
                execution_status=check.execution_status,
                outcome=check.outcome,
                spend=spend,
                anytime_valid=profile.anytime_valid,
                supports_obligation=check.supports_obligation,
                eligible_for_promotion=recomputed_eligible,
                blocker=blocker,
                raw_runtime_refusal_source=check.refusal_code,
            )
        )
        key = (check.obligation_class, check.instrument_id)
        grouped[key] = grouped.get(key, Fraction()) + check.spend.fraction
        if check.certificate_role == "refusal":
            refusal_refs.append(check.request_key)
        elif check.certificate_role == "acquisition":
            acquisition_refs.append(check.request_key)
        elif check.certificate_role == "promotion_conformance":
            conformance_refs.append(check.request_key)

    grouped_rows = tuple(
        InstrumentClassSpend(
            obligation_class=obligation,
            instrument_id=instrument_id,
            spend=build_conditional_delta_amount(
                registry=registry,
                envelope=coverage_envelope,
                amount=spend,
                semantic_role=f"grouped_spend:{obligation.value}:{instrument_id}",
                obligation_class=obligation,
            ),
        )
        for (obligation, instrument_id), spend in sorted(
            grouped.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
    )
    class_rows: list[ObligationClassRiskSpend] = []
    for obligation, weight in registry.obligation_weights.items():
        allocation_value = registry.policy.delta.fraction * weight
        matching = [
            check
            for check in semantic_ledger.checks
            if check.obligation_class is obligation
        ]
        spent_value = sum((check.spend.fraction for check in matching), Fraction())
        amount_kwargs = {
            "registry": registry,
            "envelope": coverage_envelope,
            "obligation_class": obligation,
        }
        class_rows.append(
            ObligationClassRiskSpend(
                obligation_class=obligation,
                allocation=build_conditional_delta_amount(
                    **amount_kwargs,
                    amount=allocation_value,
                    semantic_role="obligation_class_allocation",
                ),
                spent=build_conditional_delta_amount(
                    **amount_kwargs,
                    amount=spent_value,
                    semantic_role="obligation_class_spent",
                ),
                remaining=build_conditional_delta_amount(
                    **amount_kwargs,
                    amount=max(allocation_value - spent_value, Fraction()),
                    semantic_role="obligation_class_remaining",
                ),
                overspend_amount=build_conditional_delta_amount(
                    **amount_kwargs,
                    amount=max(spent_value - allocation_value, Fraction()),
                    semantic_role="obligation_class_overspend",
                ),
                instrument_refs=tuple(sorted({check.instrument_id for check in matching})),
                check_refs=tuple(check.request_key for check in matching),
                good_event_refs=tuple(
                    check.good_event_id for check in matching if check.good_event_id is not None
                ),
            )
        )
    definition_rows = tuple(
        InstrumentDefinitionRow(
            instrument_id=definition.instrument_id,
            instrument_family=definition.instrument_family,
            proof_profile_id=definition.proof_profile_id,
            certificate_roles=definition.certificate_roles,
            proof_kernel_id=profile.proof_kernel_id,
            guarantee_kind=profile.guarantee_kind,
            deterministic=profile.deterministic,
            anytime_valid=profile.anytime_valid,
            permits_obligation_satisfaction=profile.permits_obligation_satisfaction,
            blocker=(
                InstrumentBlocker(profile.refusal_code)
                if profile.refusal_code is not None
                else None
            ),
        )
        for definition in registry.instruments
        for profile in (registry.resolve_proof_profile(definition.proof_profile_id),)
    )
    route_rows: list[CertificateRouteRow] = []
    for route in registry.certificate_class_routes:
        definition = registry.resolve_instrument(route.instrument_id)
        profile = registry.resolve_proof_profile(definition.proof_profile_id)
        route_body = {
            "certificate_class": route.certificate_class,
            "obligation_class": route.obligation_class,
            "instrument_id": route.instrument_id,
            "instrument_family": definition.instrument_family,
            "certificate_role": route.certificate_role,
            "claim_polarity": route.claim_polarity,
            "owner_ref": route.owner_ref,
            "verifier_kernel_id": route.verifier_kernel_id,
            "verifier_ref": route.verifier_ref,
            "proof_profile_id": profile.profile_id,
            "proof_kernel_id": profile.proof_kernel_id,
            "guarantee_kind": profile.guarantee_kind,
            "deterministic": profile.deterministic,
            "anytime_valid": profile.anytime_valid,
            "permits_obligation_satisfaction": profile.permits_obligation_satisfaction,
            "blocker": (
                InstrumentBlocker(profile.refusal_code)
                if profile.refusal_code is not None
                else None
            ),
            "registry_content_hash": registry.content_hash,
        }
        route_rows.append(
            CertificateRouteRow.model_validate(
                {
                    **route_body,
                    "route_binding_hash": fingerprint(
                        route_body, prefix=True, canon_spec=_CANON
                    ),
                }
            )
        )
    recomputed_total = sum((check.spend.fraction for check in semantic_ledger.checks), Fraction())
    total = build_conditional_delta_amount(
        registry=registry,
        envelope=coverage_envelope,
        amount=recomputed_total,
        semantic_role="scope_total_spend",
    )
    scope_total = ScopeRiskSpend(
        allocation=build_conditional_delta_amount(
            registry=registry,
            envelope=coverage_envelope,
            amount=registry.policy.delta.fraction,
            semantic_role="scope_total_allocation",
        ),
        spent=total,
        remaining=build_conditional_delta_amount(
            registry=registry,
            envelope=coverage_envelope,
            amount=max(registry.policy.delta.fraction - recomputed_total, Fraction()),
            semantic_role="scope_total_remaining",
        ),
        overspend_amount=build_conditional_delta_amount(
            registry=registry,
            envelope=coverage_envelope,
            amount=max(recomputed_total - registry.policy.delta.fraction, Fraction()),
            semantic_role="scope_total_overspend",
        ),
    )
    route_denominator_hash = fingerprint(
        [row.route_binding_hash for row in route_rows],
        prefix=True,
        canon_spec=_CANON,
    )
    positive_blockers = (
        ReasonAlgebraRow(
            slot="coverage_assessment", value=coverage_envelope.assessment.value
        ),
        *(
            ReasonAlgebraRow(slot="instrument_blocker", value=blocker.value)
            for blocker in blockers
        ),
        ReasonAlgebraRow(
            slot="appointment_posture",
            value=AppointmentPosture.INSTITUTIONAL_AUTHORITY_UNAPPOINTED.value,
        ),
    )
    good_event_refs = tuple(
        check.good_event_id
        for check in semantic_ledger.checks
        if not check.deterministic_proof
        and check.execution_status == "executed"
        and check.good_event_id is not None
    )
    body = {
        "schema_version": SURFACE_SCHEMA_VERSION,
        "rule_version": SURFACE_RULE_VERSION,
        "source_projection_hash": semantic_ledger.projection_hash,
        "registry_content_hash": registry.content_hash,
        "registry_basis": registry,
        "semantic_ledger_basis": semantic_ledger,
        "risk_scope": semantic_ledger.risk_scope,
        "scope_id": semantic_ledger.scope_id,
        "owner_scope_key": semantic_ledger.risk_scope.owner_scope_key,
        "fixed_scope_disclosure": LOCALITY_RIDER,
        "source_provenance": coverage_envelope.source_identities,
        "coverage_envelope": coverage_envelope,
        "coverage_envelope_ref": coverage_envelope.envelope_ref,
        "coverage_assessment": coverage_envelope.assessment,
        "obligation_class_risk_spend": tuple(class_rows),
        "scope_total_risk_spend": scope_total,
        "grouped_spend": grouped_rows,
        "total_spend": total,
        "budget_posture": (
            "over_spend" if recomputed_total > registry.policy.delta.fraction else "within_budget"
        ),
        "instrument_definitions": definition_rows,
        "certificate_routes": tuple(route_rows),
        "certificate_route_denominator_count": len(registry.certificate_class_routes),
        "certificate_route_denominator_hash": route_denominator_hash,
        "instrument_instances": tuple(instances),
        "refusal_instance_refs": tuple(refusal_refs),
        "acquisition_instance_refs": tuple(acquisition_refs),
        "conformance_instance_refs": tuple(conformance_refs),
        "instrument_blockers": tuple(blockers),
        "positive_register": PositiveCertificateRegister(
            blockers=positive_blockers,
            would_populate_when=tuple(PositiveRegisterPredicate),
        ),
        "appointment_posture": AppointmentPosture.INSTITUTIONAL_AUTHORITY_UNAPPOINTED,
        "good_event_posture": GoodEventPosture(
            good_event_clause=semantic_ledger.good_event_clause,
            executed_probabilistic_good_event_refs=good_event_refs,
        ),
        "status": "not_promoted",
    }
    return body


def project_confidence_ledger_risk_spend(
    *,
    registry: ConfidenceLedgerRegistry,
    semantic_ledger: ConfidenceLedgerSemanticReceiptProjection,
    coverage_envelope: ObligationCoverageEnvelope,
    witness_store: FileSystemCAS | None = None,
    witness_verifier: Ed25519Verifier | None = None,
    caller_eligibility_by_instrument: dict[str, bool] | None = None,
) -> ConfidenceLedgerRiskSpendProjection:
    """Project exact local spend and registry-derived blockers from typed inputs."""

    coverage_envelope = reauthenticate_coverage_envelope(
        envelope=coverage_envelope,
        witness_store=witness_store,
        witness_verifier=witness_verifier,
    )
    body = _build_projection_body(
        registry=registry,
        semantic_ledger=semantic_ledger,
        coverage_envelope=coverage_envelope,
        caller_eligibility_by_instrument=caller_eligibility_by_instrument,
    )
    return ConfidenceLedgerRiskSpendProjection.model_validate(
        {**body, "projection_hash": fingerprint(body, prefix=True, canon_spec=_CANON)}
    )


def admit_confidence_ledger_risk_spend_projection(
    candidate: object,
    *,
    witness_store: FileSystemCAS | None = None,
    witness_verifier: Ed25519Verifier | None = None,
) -> DomainProjectionAdmission:
    """Revalidate and canonically re-admit one domain projection candidate."""

    try:
        admitted = ConfidenceLedgerRiskSpendProjection.model_validate(candidate)
        reauthenticate_coverage_envelope(
            envelope=admitted.coverage_envelope,
            witness_store=witness_store,
            witness_verifier=witness_verifier,
        )
        canonical = to_canonical_bytes(admitted, _CANON)
        readmitted = ConfidenceLedgerRiskSpendProjection.model_validate_json(canonical)
        reauthenticate_coverage_envelope(
            envelope=readmitted.coverage_envelope,
            witness_store=witness_store,
            witness_verifier=witness_verifier,
        )
    except ValidationError as exc:
        return DomainProjectionBlockedAdmission(reason=_classify_admission_failure(exc))
    except (TypeError, ValueError):
        return DomainProjectionBlockedAdmission(
            reason=SharedSafetyBlockedReason.PARSER_OR_SCHEMA_FAILURE
        )
    if (
        admitted != readmitted
        or admitted.projection_hash != readmitted.projection_hash
        or canonical != to_canonical_bytes(readmitted, _CANON)
    ):
        return DomainProjectionBlockedAdmission(
            reason=SharedSafetyBlockedReason.PARSER_OR_SCHEMA_FAILURE
        )
    return DomainProjectionExactAdmission(projection=readmitted)


def _classify_admission_failure(exc: ValidationError) -> SharedSafetyBlockedReason:
    errors = exc.errors(include_url=False)
    if any(error["type"] == "missing" for error in errors):
        return SharedSafetyBlockedReason.MISSING_INPUT_OR_INCOMPLETE_HISTORY
    unsupported_fields = {
        "schema_version",
        "rule_version",
        "coverage_assessment",
        "budget_posture",
        "status",
    }
    if any(error["type"] == "extra_forbidden" for error in errors) or any(
        error["type"] in {"literal_error", "enum"}
        and any(str(part) in unsupported_fields for part in error["loc"])
        for error in errors
    ):
        return SharedSafetyBlockedReason.UNSUPPORTED_OR_OUT_OF_MODEL
    return SharedSafetyBlockedReason.PARSER_OR_SCHEMA_FAILURE


def _derive_instrument_blocker(
    profile_refusal: str | None, raw_refusal: str | None
) -> InstrumentBlocker | None:
    if raw_refusal is not None and not _REFUSAL_PATTERN.fullmatch(raw_refusal):
        raise ValueError("confidence_surface_refusal_source_malformed")
    if profile_refusal is not None:
        return InstrumentBlocker(profile_refusal)
    if raw_refusal is not None:
        return InstrumentBlocker.OTHER_RUNTIME_REFUSAL
    return None
