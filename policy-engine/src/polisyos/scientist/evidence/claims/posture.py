"""Strict trust-claim posture contracts and fail-closed authority calculus."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CLAIM_POSTURE_SCHEMA = "policyos.trust.claim_posture_register.v1"
CLAIM_POSTURE_RULE_VERSION = "policyos.trust.claim_posture_rules.v1"
CLAIM_POSTURE_SLICE_BASE_REF = "f935e0c2e9359bc1202ce5d36ea706de58f7aaab"

REQUIRED_SUPPORT_PREDICATES: tuple[str, ...] = (
    "content_bound_source",
    "purpose_permission",
    "accountable_owner",
    "applicable_jurisdiction",
    "current_review",
    "content_bound_evidence",
    "identity_boundary",
    "no_blocker",
)


class _StrictModel(BaseModel):
    """Immutable base for every persisted posture contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ClaimPostureState(str, Enum):
    """Non-ordinal public posture state."""

    SUPPORTED = "supported"
    PLANNED = "planned"
    BLOCKED = "blocked"


class SourceClaimState(str, Enum):
    """Producer-local source state admitted by the posture calculus."""

    SUPPORTED = "supported"
    PLANNED = "planned"
    CANDIDATE = "candidate"
    BLOCKED = "blocked"
    NOT_ESTABLISHED = "not_established"


class EstablishmentClass(str, Enum):
    """Frozen provenance class for a gate predicate."""

    RECOMPUTED = "recomputed"
    INDEPENDENTLY_RECONCILED = "independently_reconciled"
    CONSUMER_ASSERTED = "consumer_asserted"
    INSTITUTIONALLY_SUPPLIED = "institutionally_supplied"
    NOT_ESTABLISHED = "not_established"


class SourceInventoryRole(str, Enum):
    """Mutually exclusive role of one raw source candidate."""

    DECLARES_ONLY = "declares_only"
    CARRIES_ONLY = "carries_only"
    CONSUMES_ONLY = "consumes_only"
    DECLARES_AND_CONSUMES = "declares_and_consumes"
    SUBSTRING_COLLISION = "substring_collision"
    AMBIGUOUS = "ambiguous"


class SourceResolution(str, Enum):
    """Static resolution status for a source candidate."""

    RESOLVED = "resolved"
    RUNTIME_BOUND = "runtime_bound"
    COLLISION = "collision"
    AMBIGUOUS = "ambiguous"


class ClaimPostureAudience(str, Enum):
    """Required posture projection audiences."""

    PUBLIC = "PUBLIC"
    REVIEWER = "REVIEWER"
    EXPERT = "EXPERT"
    MACHINE = "MACHINE"


class SourceCoordinate(_StrictModel):
    """Content coordinate for one posture field use."""

    path: str
    symbol: str | None
    line: int = Field(ge=1)
    column: int = Field(ge=0)
    field_name: Literal["authoritative_for", "may_not_use_for"]
    use_kind: Literal["declaration", "carrier", "consumer", "collision"]


class LiteralSite(_StrictModel):
    """Bounded literal-resolution result for one field site."""

    coordinate: SourceCoordinate
    wrapper_kind: Literal["direct", "field_default", "literal_lambda_factory", "dynamic"]
    values: tuple[str, ...]
    resolution: SourceResolution


class AdmittedSourceMember(_StrictModel):
    """One member of the content-bound source set."""

    path: str
    content_digest: str


class SourceDerivationReceipt(_StrictModel):
    """Complete-set receipt emitted by one independent source derivation."""

    method: Literal["ast", "tokenize"]
    scanned_python_count: int = Field(ge=0)
    raw_candidate_count: int = Field(ge=0)
    exact_field_file_count: int = Field(ge=0)
    declaring_file_count: int = Field(ge=0)
    consuming_file_count: int = Field(ge=0)
    role_counts: Mapping[SourceInventoryRole, int]
    direct_literal_site_count: int = Field(ge=0)
    direct_literal_file_count: int = Field(ge=0)
    direct_literal_subject_count: int = Field(ge=0)
    direct_empty_site_count: int = Field(ge=0)
    wrapper_literal_site_count: int = Field(ge=0)
    wrapper_literal_file_count: int = Field(ge=0)
    wrapper_literal_subject_count: int = Field(ge=0)
    may_not_use_for_raw_file_count: int = Field(ge=0)
    may_not_use_for_literal_site_count: int = Field(ge=0)
    may_not_use_for_literal_file_count: int = Field(ge=0)
    may_not_use_for_literal_subject_count: int = Field(ge=0)
    row_digest: str

    @model_validator(mode="after")
    def validate_partition(self) -> Self:
        """Require role counts to partition the complete raw candidate set."""
        expected = set(SourceInventoryRole)
        observed = set(self.role_counts)
        if observed != expected:
            raise ValueError("role_counts must contain every closed source role")
        if sum(self.role_counts.values()) != self.raw_candidate_count:
            raise ValueError("role_counts must partition raw_candidate_count")
        return self


class SourceInventoryRow(_StrictModel):
    """One reconciled raw candidate and all of its derivation facts."""

    path: str
    content_digest: str
    role: SourceInventoryRole
    resolution: SourceResolution
    declaration_coordinates: tuple[SourceCoordinate, ...]
    carrier_coordinates: tuple[SourceCoordinate, ...]
    consumer_coordinates: tuple[SourceCoordinate, ...]
    authoritative_sites: tuple[LiteralSite, ...]
    forbidden_sites: tuple[LiteralSite, ...]
    runtime_bound: bool
    issue_codes: tuple[str, ...]


class SourceDerivation(_StrictModel):
    """Typed output of one complete filesystem/source walk."""

    admitted_sources: tuple[AdmittedSourceMember, ...]
    rows: tuple[SourceInventoryRow, ...]
    receipt: SourceDerivationReceipt


class ReconciledSourceDerivation(_StrictModel):
    """File-for-file reconciliation of the two independent derivations."""

    admitted_sources: tuple[AdmittedSourceMember, ...]
    rows: tuple[SourceInventoryRow, ...]
    ast_receipt: SourceDerivationReceipt
    token_receipt: SourceDerivationReceipt
    disagreements: tuple[str, ...]


class OwnerBinding(_StrictModel):
    """Accountable owner declaration and its P37 establishment class."""

    owner: str | None
    basis: Literal["package_contract", "ratified_document", "closure_commitment", "not_established"]
    source_ref: str | None
    establishment_class: EstablishmentClass


class EvidenceBinding(_StrictModel):
    """Content-bound evidence with non-producing verifier provenance."""

    ref: str
    content_digest: str
    subject_binding: str
    verifier_ref: str
    verifier_provenance_ref: str
    establishment_class: EstablishmentClass
    source_as_of: date
    supersession_ref: str | None


class SupportPredicate(_StrictModel):
    """One decisive support predicate frozen at admission."""

    kind: str
    satisfied: bool
    establishment_class: EstablishmentClass
    evidence_refs: tuple[str, ...]
    issue_code: str | None


class ClaimSourceBinding(_StrictModel):
    """One producer/source arm contributing to a posture row."""

    coordinate: SourceCoordinate
    content_digest: str
    resolution: SourceResolution
    source_state: SourceClaimState
    subject: str | None
    family: str
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    authority_purpose: str | None
    owner: OwnerBinding
    jurisdiction: str | None
    jurisdiction_establishment: EstablishmentClass
    review_on: date | None
    review_due: date | None
    source_as_of: date | None
    evidence_refs: tuple[str, ...]
    limitation_refs: tuple[str, ...]
    prerequisite_refs: tuple[str, ...]
    identity_boundary_ref: str
    declared_scope_assumption: str | None
    supersedes_ref: str | None
    superseded_by_ref: str | None
    predicates: tuple[SupportPredicate, ...]
    closure_signal: str | None

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        """Keep resolution, subject, time, and supersession semantics coherent."""
        if self.resolution == SourceResolution.RESOLVED and not self.subject:
            raise ValueError("resolved source binding requires subject")
        if self.resolution != SourceResolution.RESOLVED and self.subject is not None:
            raise ValueError("unresolved source binding cannot invent a subject")
        if self.review_on and self.review_due and self.review_due < self.review_on:
            raise ValueError("review_due must not precede review_on")
        if bool(self.supersedes_ref) != bool(self.superseded_by_ref):
            raise ValueError("supersession fields must be paired")
        return self


class ClaimPostureRow(_StrictModel):
    """Derived posture for one subject or unresolved source coordinate."""

    claim_id: str
    subject: str | None
    family: str
    source_bindings: tuple[ClaimSourceBinding, ...]
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    accountable_owner: str | None
    owner_basis: str
    review_on: date | None
    review_due: date | None
    source_as_of: date | None
    audiences: tuple[ClaimPostureAudience, ...]
    closure_signal: str | None
    effective_state: ClaimPostureState
    blocker_codes: tuple[str, ...]
    limitations: tuple[str, ...]


class AntiRoleBinding(_StrictModel):
    """Content-bound anti-role derived from the ratified identity paragraph."""

    role: str
    display_label: str
    source_path: str
    source_digest: str
    line: int = Field(ge=1)
    column: int = Field(ge=0)


class IdentityBoundaryBinding(_StrictModel):
    """Identity-document content and paragraph derivation receipt."""

    path: str
    content_digest: str
    frontmatter_digest: str
    paragraph_digest: str
    paragraph_start_line: int = Field(ge=1)
    paragraph_end_line: int = Field(ge=1)
    anti_roles: tuple[AntiRoleBinding, ...]
    derivation_receipt_digests: tuple[str, str]


class ProjectionGroup(_StrictModel):
    """Closed rendering group for ordered claim identifiers."""

    group_id: Literal["methodology", "evidence_envelope", "limitations", "accessibility", "custody"]
    claim_ids: tuple[str, ...]


class ClaimPostureRegisterV1(_StrictModel):
    """Strict deterministic trust-claim posture register."""

    schema_version: Literal["policyos.trust.claim_posture_register.v1"]
    rule_version: Literal["policyos.trust.claim_posture_rules.v1"]
    slice_base_ref: Literal["f935e0c2e9359bc1202ce5d36ea706de58f7aaab"]
    register_as_of: date
    admitted_sources: tuple[AdmittedSourceMember, ...]
    source_set_digest: str
    ast_derivation: SourceDerivationReceipt
    token_derivation: SourceDerivationReceipt
    identity_boundary: IdentityBoundaryBinding
    source_inventory: tuple[SourceInventoryRow, ...]
    claims: tuple[ClaimPostureRow, ...]
    projection_groups: tuple[ProjectionGroup, ...]
    payload_digest: str

    @model_validator(mode="after")
    def validate_register(self) -> Self:
        """Recompute ordering, uniqueness, row states, and the self digest."""
        paths = tuple(item.path for item in self.admitted_sources)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("admitted_sources must be sorted and unique")
        inventory_paths = tuple(row.path for row in self.source_inventory)
        if inventory_paths != tuple(sorted(inventory_paths)) or len(inventory_paths) != len(
            set(inventory_paths)
        ):
            raise ValueError("source_inventory must be sorted and unique")
        claim_ids = tuple(row.claim_id for row in self.claims)
        if claim_ids != tuple(sorted(claim_ids)) or len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claims must be sorted and unique")
        if tuple(item.group_id for item in self.projection_groups) != (
            "accessibility",
            "custody",
            "evidence_envelope",
            "limitations",
            "methodology",
        ):
            raise ValueError("projection_groups must contain the closed sorted group set")
        if self.source_set_digest != _source_set_digest(self.admitted_sources):
            raise ValueError("source_set_digest does not bind admitted source membership")
        for row in self.claims:
            state, blockers, limitations = evaluate_claim_posture(
                row.source_bindings,
                subject=row.subject,
                family=row.family,
                register_as_of=self.register_as_of,
            )
            if (row.effective_state, row.blocker_codes, row.limitations) != (
                state,
                blockers,
                limitations,
            ):
                raise ValueError("authored effective posture differs from recomputation")
        if self.payload_digest != _payload_digest(self):
            raise ValueError("payload_digest does not bind the canonical payload")
        return self


def compose_effective_state(
    source_states: Iterable[SourceClaimState | str],
    *,
    support_predicates: Iterable[SupportPredicate] = (),
    establishment_classes: Iterable[EstablishmentClass | str] = (),
    planned_owner: str | None = None,
    closure_signal: str | None = None,
    family: str | None = None,
    governed_performance_prerequisite: EvidenceBinding | None = None,
) -> ClaimPostureState:
    """Compose source states without ranking them or laundering weak states."""
    states = tuple(SourceClaimState(item) for item in source_states)
    if not states or any(
        item
        in {SourceClaimState.BLOCKED, SourceClaimState.CANDIDATE, SourceClaimState.NOT_ESTABLISHED}
        for item in states
    ):
        return ClaimPostureState.BLOCKED
    positive_classes = {
        EstablishmentClass.RECOMPUTED,
        EstablishmentClass.INDEPENDENTLY_RECONCILED,
    }
    predicates = tuple(support_predicates)
    if any(
        not predicate.satisfied or predicate.establishment_class not in positive_classes
        for predicate in predicates
    ):
        return ClaimPostureState.BLOCKED
    if any(EstablishmentClass(item) not in positive_classes for item in establishment_classes):
        return ClaimPostureState.BLOCKED
    if SourceClaimState.PLANNED in states:
        if planned_owner and closure_signal:
            return ClaimPostureState.PLANNED
        return ClaimPostureState.BLOCKED
    if predicates:
        kinds = {predicate.kind for predicate in predicates}
        if not set(REQUIRED_SUPPORT_PREDICATES).issubset(kinds):
            return ClaimPostureState.BLOCKED
    if family == "grounded_performance":
        evidence = governed_performance_prerequisite
        if (
            evidence is None
            or evidence.establishment_class not in positive_classes
            or not evidence.content_digest
            or not evidence.verifier_ref
            or not evidence.verifier_provenance_ref
        ):
            return ClaimPostureState.BLOCKED
    return ClaimPostureState.SUPPORTED


def evaluate_claim_posture(
    bindings: Sequence[ClaimSourceBinding],
    *,
    subject: str | None,
    family: str,
    register_as_of: date,
) -> tuple[ClaimPostureState, tuple[str, ...], tuple[str, ...]]:
    """Recompute effective state, blockers, and limitations for source arms."""
    del register_as_of
    blockers: set[str] = set()
    limitations: set[str] = set()
    states: list[SourceClaimState] = []
    predicates: list[SupportPredicate] = []
    owners: list[str] = []
    closure_signals: list[str] = []
    governed: EvidenceBinding | None = None
    for binding in bindings:
        states.append(binding.source_state)
        predicates.extend(binding.predicates)
        if binding.owner.owner:
            owners.append(binding.owner.owner)
        if binding.closure_signal:
            closure_signals.append(binding.closure_signal)
        if binding.declared_scope_assumption:
            limitations.add(f"Declared scope assumption: {binding.declared_scope_assumption}")
            blockers.add("DS11-GATE-PREDICATE-NOT-ESTABLISHED")
        limitations.update(binding.limitation_refs)
        if binding.resolution == SourceResolution.RUNTIME_BOUND:
            blockers.add("DS11-SOURCE-RUNTIME-BOUND")
        elif binding.resolution == SourceResolution.AMBIGUOUS:
            blockers.add("DS11-SOURCE-DERIVATION-DISAGREEMENT")
        if subject and (
            binding.authority_purpose not in binding.authoritative_for
            or binding.authority_purpose in binding.may_not_use_for
        ):
            blockers.add("DS11-AUTHORITY-PURPOSE-DENIED")
        for predicate in binding.predicates:
            if not predicate.satisfied or predicate.establishment_class not in {
                EstablishmentClass.RECOMPUTED,
                EstablishmentClass.INDEPENDENTLY_RECONCILED,
            }:
                blockers.add(predicate.issue_code or "DS11-GATE-PREDICATE-NOT-ESTABLISHED")
    state = compose_effective_state(
        states,
        support_predicates=predicates,
        planned_owner=owners[0] if owners else None,
        closure_signal=closure_signals[0] if closure_signals else None,
        family=family,
        governed_performance_prerequisite=governed,
    )
    if blockers:
        state = ClaimPostureState.BLOCKED
    return state, tuple(sorted(blockers)), tuple(sorted(limitations))


def build_posture_register(
    *,
    register_as_of: date,
    admitted_sources: Sequence[AdmittedSourceMember],
    ast_derivation: SourceDerivationReceipt,
    token_derivation: SourceDerivationReceipt,
    identity_boundary: IdentityBoundaryBinding,
    source_inventory: Sequence[SourceInventoryRow],
    source_bindings: Sequence[ClaimSourceBinding],
    projection_groups: Sequence[ProjectionGroup],
) -> ClaimPostureRegisterV1:
    """Build a canonical register while recomputing every authority-bearing field."""
    members = tuple(sorted(admitted_sources, key=lambda item: item.path))
    inventory = tuple(sorted(source_inventory, key=lambda item: item.path))
    claims = _claim_rows(source_bindings, register_as_of=register_as_of)
    groups = tuple(sorted(projection_groups, key=lambda item: item.group_id))
    payload = {
        "schema_version": CLAIM_POSTURE_SCHEMA,
        "rule_version": CLAIM_POSTURE_RULE_VERSION,
        "slice_base_ref": CLAIM_POSTURE_SLICE_BASE_REF,
        "register_as_of": register_as_of,
        "admitted_sources": members,
        "source_set_digest": _source_set_digest(members),
        "ast_derivation": ast_derivation,
        "token_derivation": token_derivation,
        "identity_boundary": identity_boundary,
        "source_inventory": inventory,
        "claims": claims,
        "projection_groups": groups,
        "payload_digest": "sha256:pending",
    }
    provisional = ClaimPostureRegisterV1.model_construct(**payload)
    payload["payload_digest"] = _payload_digest(provisional)
    return ClaimPostureRegisterV1.model_validate(payload)


def validate_posture_register(
    payload: bytes | Mapping[str, object],
) -> ClaimPostureRegisterV1:
    """Strictly validate canonical register bytes or a decoded payload."""
    decoded: object = json.loads(payload) if isinstance(payload, bytes) else payload
    return ClaimPostureRegisterV1.model_validate(decoded)


def canonical_register_bytes(register: ClaimPostureRegisterV1) -> bytes:
    """Serialize one register with stable JSON options and one final newline."""
    return (
        json.dumps(
            register.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _claim_rows(
    bindings: Sequence[ClaimSourceBinding], *, register_as_of: date
) -> tuple[ClaimPostureRow, ...]:
    grouped: dict[str, list[ClaimSourceBinding]] = {}
    for binding in bindings:
        key = binding.subject or (
            f"unresolved:{binding.coordinate.path}:{binding.coordinate.line}:"
            f"{binding.coordinate.column}"
        )
        grouped.setdefault(key, []).append(binding)
    rows: list[ClaimPostureRow] = []
    for key, group in grouped.items():
        ordered = tuple(
            sorted(
                group,
                key=lambda item: (
                    item.coordinate.path,
                    item.coordinate.line,
                    item.coordinate.column,
                ),
            )
        )
        subject = ordered[0].subject
        family = ordered[0].family
        state, blockers, limitations = evaluate_claim_posture(
            ordered,
            subject=subject,
            family=family,
            register_as_of=register_as_of,
        )
        allowed = set(ordered[0].authoritative_for)
        for binding in ordered[1:]:
            allowed.intersection_update(binding.authoritative_for)
        denied = {purpose for binding in ordered for purpose in binding.may_not_use_for}
        owners = {binding.owner.owner for binding in ordered if binding.owner.owner}
        review_on = [binding.review_on for binding in ordered if binding.review_on]
        review_due = [binding.review_due for binding in ordered if binding.review_due]
        source_dates = [binding.source_as_of for binding in ordered if binding.source_as_of]
        claim_id = "claim-posture:" + hashlib.sha256(key.encode("utf-8")).hexdigest()
        rows.append(
            ClaimPostureRow(
                claim_id=claim_id,
                subject=subject,
                family=family,
                source_bindings=ordered,
                authoritative_for=tuple(sorted(allowed)),
                may_not_use_for=tuple(sorted(denied)),
                accountable_owner=next(iter(owners)) if len(owners) == 1 else None,
                owner_basis=ordered[0].owner.basis,
                review_on=min(review_on) if review_on else None,
                review_due=min(review_due) if review_due else None,
                source_as_of=min(source_dates) if source_dates else None,
                audiences=tuple(ClaimPostureAudience),
                closure_signal=ordered[0].closure_signal,
                effective_state=state,
                blocker_codes=blockers,
                limitations=limitations,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.claim_id))


def _source_set_digest(members: Sequence[AdmittedSourceMember]) -> str:
    payload = [(member.path, member.content_digest) for member in members]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _payload_digest(register: ClaimPostureRegisterV1) -> str:
    payload = register.model_dump(mode="json", exclude={"payload_digest"})
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
