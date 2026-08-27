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
CLAIM_POSTURE_RULE_VERSION = "policyos.trust.claim_posture_rules.v4"
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

REQUIRED_PLANNED_PREDICATES: tuple[str, ...] = (
    "content_bound_source",
    "purpose_permission",
    "accountable_owner",
    "identity_boundary",
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


class AccessibilityEvidenceKind(str, Enum):
    """Closed evidence kinds admitted to accessibility-purpose evaluation."""

    INTERNAL_PRE_AUDIT = "internal_pre_audit"
    EXTERNAL_COUNTERSIGNED_AUDIT = "external_countersigned_audit"
    PAGE_A11Y_RECEIPT = "page_a11y_receipt"


class AccessibilityPurpose(str, Enum):
    """Closed accessibility purposes with distinct authority requirements."""

    HISTORICAL_INTERNAL_PRE_AUDIT = "historical_internal_accessibility_pre_audit"
    CURRENT_CONFORMANCE = "current_accessibility_conformance"
    EXTERNAL_CERTIFICATION = "external_accessibility_certification"


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
    declaration_form: Literal["assignment", "keyword", "dict_key"]
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


class ProducerPostureMetadata(_StrictModel):
    """Strict candidate/planned posture declared beside one producer subject."""

    schema_version: Literal["policyos.trust.producer_posture.v1"]
    subject: str = Field(min_length=1)
    source_state: Literal[SourceClaimState.CANDIDATE, SourceClaimState.PLANNED]
    owner: str = Field(min_length=1)
    closure_signal: str = Field(min_length=1)
    prerequisite_refs: tuple[str, ...] = ()
    limitation_refs: tuple[str, ...] = ()
    source_symbol: str | None
    line: int = Field(ge=1)
    column: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_declaration(self) -> Self:
        """Reject prose-shaped closure signals and non-canonical string sets."""
        if any(
            value != value.strip() or "\n" in value
            for value in (self.subject, self.owner, self.closure_signal)
        ):
            raise ValueError("producer posture strings must be stripped single lines")
        command_prefixes = (
            "uv run pytest ",
            "pytest ",
            "corepack pnpm ",
            ".venv/bin/python ",
            "python ",
            "pytest://",
        )
        if not self.closure_signal.startswith(command_prefixes):
            raise ValueError("closure_signal must be an executable command or test identity")
        for values in (self.prerequisite_refs, self.limitation_refs):
            if len(values) != len(set(values)) or any(not item.strip() for item in values):
                raise ValueError("producer posture refs must be nonempty and unique")
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
    producer_metadata: tuple[ProducerPostureMetadata, ...] = ()
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


class AdmittedVerifier(_StrictModel):
    """Closed verifier identity derived from one typed admitted basis."""

    ref: str
    verifier_kind: Literal[
        "identity_boundary_derivation",
        "accessibility_document_derivation",
        "page_a11y_receipt_derivation",
    ]
    content_ref: str
    content_digest: str
    provenance_ref: str
    provenance_digest: str
    subject_scope: tuple[str, ...]
    prohibited_subjects: tuple[str, ...]
    establishment_class: Literal[
        EstablishmentClass.RECOMPUTED,
        EstablishmentClass.INDEPENDENTLY_RECONCILED,
    ]


class SupportPredicate(_StrictModel):
    """One decisive support predicate frozen at admission."""

    kind: Literal[
        "content_bound_source",
        "purpose_permission",
        "accountable_owner",
        "applicable_jurisdiction",
        "current_review",
        "content_bound_evidence",
        "identity_boundary",
        "no_blocker",
    ]
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
    evidence_bindings: tuple[EvidenceBinding, ...]
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
        predicate_kinds = tuple(item.kind for item in self.predicates)
        if len(predicate_kinds) != len(set(predicate_kinds)) or set(predicate_kinds) != set(
            REQUIRED_SUPPORT_PREDICATES
        ):
            raise ValueError("predicates must contain the exact closed support set")
        if set(self.evidence_refs) != {item.ref for item in self.evidence_bindings}:
            raise ValueError("evidence_refs must exactly name evidence_bindings")
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
    owner: str
    last_reviewed: date
    decision_status: str
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    identity_statement_digest: str
    identity_statement_start_line: int = Field(ge=1)
    identity_statement_end_line: int = Field(ge=1)


class DocumentProjectionSelector(_StrictModel):
    """One exact-text selector declared by a document projection index."""

    value: str
    exact_text: str
    occurrence: Literal[1]


class DocumentProjectionPurpose(_StrictModel):
    """One purpose and its named body-selector basis."""

    purpose: str
    basis: tuple[str, ...]


class DocumentProjectionIndex(_StrictModel):
    """Strict accessibility frontmatter projection index."""

    schema_version: Literal["policyos.trust.document_projection_index.v1"]
    body_sha256: str
    bindings: Mapping[str, DocumentProjectionSelector]
    authoritative_for: tuple[DocumentProjectionPurpose, ...]
    may_not_use_for: tuple[DocumentProjectionPurpose, ...]


class ResolvedDocumentBinding(_StrictModel):
    """One selector independently resolved against complete document body bytes."""

    key: str
    value: str
    exact_text_digest: str
    byte_start: int = Field(ge=0)
    byte_end: int = Field(gt=0)
    establishment_class: Literal[EstablishmentClass.RECOMPUTED]


class AccessibilityDocumentBinding(_StrictModel):
    """Content-bound accessibility document and resolved frontmatter basis."""

    path: str
    content_digest: str
    frontmatter_digest: str
    body_digest: str
    source_as_of: date
    bindings: tuple[ResolvedDocumentBinding, ...]
    authoritative_for: tuple[DocumentProjectionPurpose, ...]
    may_not_use_for: tuple[DocumentProjectionPurpose, ...]
    limitation_refs: tuple[str, ...]


class PageA11yFailureBinding(_StrictModel):
    """Stable semantic failure derived from one Playwright spec result."""

    identity: str
    test_id: str
    issue_signature: str


class PageA11yReceiptBinding(_StrictModel):
    """Five-file, independently recomputed historical page-a11y receipt."""

    path: str
    content_digest: str
    admitted_sources: tuple[AdmittedSourceMember, ...]
    source_as_of: date
    collected: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    duration_ms: float = Field(ge=0)
    exit_code: int
    failures: tuple[PageA11yFailureBinding, ...]
    replay_establishment: EstablishmentClass
    limitation_refs: tuple[str, ...]


class GeneratedFamilyBinding(_StrictModel):
    """Strict generated-family subset required by the posture writer."""

    family_id: Literal["trust-claim-posture-register"]
    lifecycle: Literal["generated_committed"]
    stale_output_behavior: Literal["fail"]
    outputs: tuple[str, ...]
    default_freshness_check: Literal[True]
    output_probe_command: tuple[str, ...]


class ProjectionGroup(_StrictModel):
    """Closed rendering group for ordered claim identifiers."""

    group_id: Literal["methodology", "evidence_envelope", "limitations", "accessibility", "custody"]
    claim_ids: tuple[str, ...]


class ClaimPostureRegisterV1(_StrictModel):
    """Strict deterministic trust-claim posture register."""

    schema_version: Literal["policyos.trust.claim_posture_register.v1"]
    rule_version: Literal["policyos.trust.claim_posture_rules.v4"]
    slice_base_ref: Literal["f935e0c2e9359bc1202ce5d36ea706de58f7aaab"]
    register_as_of: date
    admitted_sources: tuple[AdmittedSourceMember, ...]
    source_set_digest: str
    ast_derivation: SourceDerivationReceipt
    token_derivation: SourceDerivationReceipt
    identity_boundary: IdentityBoundaryBinding
    admitted_verifiers: tuple[AdmittedVerifier, ...]
    accessibility_document: AccessibilityDocumentBinding | None
    page_a11y_receipt: PageA11yReceiptBinding | None
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
        admitted_by_path = {item.path: item.content_digest for item in self.admitted_sources}
        if (
            admitted_by_path.get(self.identity_boundary.path)
            != self.identity_boundary.content_digest
        ):
            raise ValueError("identity_boundary does not bind admitted source bytes")
        expected_verifiers = derive_admitted_verifiers(
            identity_boundary=self.identity_boundary,
            accessibility_document=self.accessibility_document,
            page_a11y_receipt=self.page_a11y_receipt,
        )
        if self.admitted_verifiers != expected_verifiers:
            raise ValueError("admitted_verifiers differ from typed artifact basis")
        if any(
            admitted_by_path.get(verifier.content_ref) != verifier.content_digest
            for verifier in self.admitted_verifiers
        ):
            raise ValueError("admitted verifier content differs from admitted source bytes")
        for row in self.claims:
            state, blockers, limitations = evaluate_claim_posture(
                row.source_bindings,
                subject=row.subject,
                family=row.family,
                register_as_of=self.register_as_of,
                identity_boundary=self.identity_boundary,
                admitted_sources=self.admitted_sources,
                admitted_verifiers=self.admitted_verifiers,
            )
            if (row.effective_state, row.blocker_codes, row.limitations) != (
                state,
                blockers,
                limitations,
            ):
                raise ValueError("authored effective posture differs from recomputation")
        if self.projection_groups != _projection_groups(self.claims):
            raise ValueError("projection_groups differ from produced semantic rows")
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
    admitted_sources: Sequence[AdmittedSourceMember] = (),
    admitted_verifiers: Sequence[AdmittedVerifier] = (),
    register_as_of: date | None = None,
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
    if any(EstablishmentClass(item) not in positive_classes for item in establishment_classes):
        return ClaimPostureState.BLOCKED
    if SourceClaimState.PLANNED in states:
        if planned_owner and closure_signal:
            return ClaimPostureState.PLANNED
        return ClaimPostureState.BLOCKED
    kinds = tuple(predicate.kind for predicate in predicates)
    if len(kinds) != len(set(kinds)) or set(kinds) != set(REQUIRED_SUPPORT_PREDICATES):
        return ClaimPostureState.BLOCKED
    if any(
        not predicate.satisfied or predicate.establishment_class not in positive_classes
        for predicate in predicates
    ):
        return ClaimPostureState.BLOCKED
    if family == "grounded_performance":
        # The closed DS11 basis has no governed-performance producer or verifier type.
        # Generic admitted evidence cannot substitute for that missing prerequisite.
        return ClaimPostureState.BLOCKED
    return ClaimPostureState.SUPPORTED


def evaluate_claim_posture(
    bindings: Sequence[ClaimSourceBinding],
    *,
    subject: str | None,
    family: str,
    register_as_of: date,
    identity_boundary: IdentityBoundaryBinding | None = None,
    admitted_sources: Sequence[AdmittedSourceMember] = (),
    admitted_verifiers: Sequence[AdmittedVerifier] = (),
) -> tuple[ClaimPostureState, tuple[str, ...], tuple[str, ...]]:
    """Recompute effective state, blockers, and limitations for source arms."""
    blockers: set[str] = set()
    limitations: set[str] = set()
    states: list[SourceClaimState] = []
    owners: list[str] = []
    closure_signals: list[str] = []
    governed: EvidenceBinding | None = None
    for binding in bindings:
        states.append(binding.source_state)
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
        facts = _recomputed_binding_facts(
            binding,
            register_as_of=register_as_of,
            identity_boundary=identity_boundary,
            admitted_sources=admitted_sources,
            admitted_verifiers=admitted_verifiers,
        )
        predicates_by_kind = {item.kind: item for item in binding.predicates}
        if set(predicates_by_kind) != set(REQUIRED_SUPPORT_PREDICATES):
            blockers.add("DS11-GATE-PREDICATE-SET-INCOMPLETE")
        required_facts = (
            REQUIRED_PLANNED_PREDICATES
            if binding.source_state == SourceClaimState.PLANNED
            else REQUIRED_SUPPORT_PREDICATES
        )
        for kind in required_facts:
            predicate = predicates_by_kind.get(kind)
            fact, issue_code = facts[kind]
            if (
                predicate is None
                or not predicate.satisfied
                or not fact
                or predicate.establishment_class
                not in {
                    EstablishmentClass.RECOMPUTED,
                    EstablishmentClass.INDEPENDENTLY_RECONCILED,
                }
            ):
                blockers.add(
                    issue_code if predicate is None else predicate.issue_code or issue_code
                )
    state = compose_effective_state(
        states,
        support_predicates=bindings[0].predicates if bindings else (),
        planned_owner=owners[0] if owners else None,
        closure_signal=closure_signals[0] if closure_signals else None,
        family=family,
        governed_performance_prerequisite=governed,
        admitted_sources=admitted_sources,
        admitted_verifiers=admitted_verifiers,
        register_as_of=register_as_of,
    )
    if blockers:
        state = ClaimPostureState.BLOCKED
    return state, tuple(sorted(blockers)), tuple(sorted(limitations))


def _recomputed_binding_facts(
    binding: ClaimSourceBinding,
    *,
    register_as_of: date,
    identity_boundary: IdentityBoundaryBinding | None,
    admitted_sources: Sequence[AdmittedSourceMember],
    admitted_verifiers: Sequence[AdmittedVerifier],
) -> dict[str, tuple[bool, str]]:
    positive = {
        EstablishmentClass.RECOMPUTED,
        EstablishmentClass.INDEPENDENTLY_RECONCILED,
    }
    admitted_by_path = {item.path: item.content_digest for item in admitted_sources}
    evidence_valid = bool(binding.evidence_bindings) and all(
        evidence.ref in binding.evidence_refs
        and _evidence_is_admitted(
            evidence,
            subject=binding.subject,
            admitted_sources=admitted_sources,
            admitted_verifiers=admitted_verifiers,
            register_as_of=register_as_of,
        )
        for evidence in binding.evidence_bindings
    )
    identity_valid = (
        identity_boundary is not None
        and binding.identity_boundary_ref == identity_boundary.path
        and admitted_by_path.get(identity_boundary.path) == identity_boundary.content_digest
    )
    return {
        "content_bound_source": (
            admitted_by_path.get(binding.coordinate.path) == binding.content_digest
            and binding.resolution == SourceResolution.RESOLVED,
            "DS11-SOURCE-CONTENT-NOT-BOUND",
        ),
        "purpose_permission": (
            binding.subject is not None
            and binding.authority_purpose in binding.authoritative_for
            and binding.authority_purpose not in binding.may_not_use_for,
            "DS11-AUTHORITY-PURPOSE-DENIED",
        ),
        "accountable_owner": (
            bool(binding.owner.owner)
            and bool(binding.owner.source_ref)
            and binding.owner.establishment_class in positive,
            "DS11-OWNER-NOT-ESTABLISHED",
        ),
        "applicable_jurisdiction": (
            bool(binding.jurisdiction) and binding.jurisdiction_establishment in positive,
            "DS11-JURISDICTION-NOT-ESTABLISHED",
        ),
        "current_review": (
            binding.review_on is not None
            and binding.review_due is not None
            and binding.review_on <= register_as_of <= binding.review_due,
            "DS11-REVIEW-MISSING-OR-STALE",
        ),
        "content_bound_evidence": (
            evidence_valid,
            "DS11-EVIDENCE-NOT-INDEPENDENTLY-BOUND",
        ),
        "identity_boundary": (
            identity_valid,
            "DS11-IDENTITY-BOUNDARY-NOT-ESTABLISHED",
        ),
        "no_blocker": (
            binding.resolution == SourceResolution.RESOLVED
            and binding.source_state == SourceClaimState.SUPPORTED
            and binding.declared_scope_assumption is None
            and binding.superseded_by_ref is None,
            "DS11-SOURCE-BLOCKER-PRESENT",
        ),
    }


def build_posture_register(
    *,
    register_as_of: date,
    admitted_sources: Sequence[AdmittedSourceMember],
    ast_derivation: SourceDerivationReceipt,
    token_derivation: SourceDerivationReceipt,
    identity_boundary: IdentityBoundaryBinding,
    accessibility_document: AccessibilityDocumentBinding | None = None,
    page_a11y_receipt: PageA11yReceiptBinding | None = None,
    source_inventory: Sequence[SourceInventoryRow],
    source_bindings: Sequence[ClaimSourceBinding],
) -> ClaimPostureRegisterV1:
    """Build a canonical register while recomputing every authority-bearing field."""
    members = tuple(sorted(admitted_sources, key=lambda item: item.path))
    inventory = tuple(sorted(source_inventory, key=lambda item: item.path))
    claims = _claim_rows(
        source_bindings,
        register_as_of=register_as_of,
        identity_boundary=identity_boundary,
        admitted_sources=members,
        admitted_verifiers=derive_admitted_verifiers(
            identity_boundary=identity_boundary,
            accessibility_document=accessibility_document,
            page_a11y_receipt=page_a11y_receipt,
        ),
    )
    verifiers = derive_admitted_verifiers(
        identity_boundary=identity_boundary,
        accessibility_document=accessibility_document,
        page_a11y_receipt=page_a11y_receipt,
    )
    groups = _projection_groups(claims)
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
        "admitted_verifiers": verifiers,
        "accessibility_document": accessibility_document,
        "page_a11y_receipt": page_a11y_receipt,
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
    bindings: Sequence[ClaimSourceBinding],
    *,
    register_as_of: date,
    identity_boundary: IdentityBoundaryBinding,
    admitted_sources: Sequence[AdmittedSourceMember],
    admitted_verifiers: Sequence[AdmittedVerifier],
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
            identity_boundary=identity_boundary,
            admitted_sources=admitted_sources,
            admitted_verifiers=admitted_verifiers,
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


def derive_admitted_verifiers(
    *,
    identity_boundary: IdentityBoundaryBinding,
    accessibility_document: AccessibilityDocumentBinding | None,
    page_a11y_receipt: PageA11yReceiptBinding | None,
) -> tuple[AdmittedVerifier, ...]:
    """Derive the closed verifier set from typed artifact bases, never supplied names."""
    values = [
        _admitted_verifier(
            ref="verifier:identity-boundary:dual-derivation",
            verifier_kind="identity_boundary_derivation",
            content_ref=identity_boundary.path,
            content_digest=identity_boundary.content_digest,
            provenance_parts=(
                identity_boundary.frontmatter_digest,
                identity_boundary.identity_statement_digest,
                identity_boundary.paragraph_digest,
                *identity_boundary.derivation_receipt_digests,
            ),
            subject_scope=("system_identity",),
            prohibited_subjects=(
                "current_accessibility_conformance",
                "external_accessibility_certification",
                "grounded_performance",
                "historical_internal_accessibility_pre_audit",
                "universal_custody_commitment",
            ),
            establishment_class=EstablishmentClass.INDEPENDENTLY_RECONCILED,
        )
    ]
    if accessibility_document is not None:
        values.append(
            _admitted_verifier(
                ref="verifier:accessibility-document:selector-resolution",
                verifier_kind="accessibility_document_derivation",
                content_ref=accessibility_document.path,
                content_digest=accessibility_document.content_digest,
                provenance_parts=(
                    accessibility_document.frontmatter_digest,
                    accessibility_document.body_digest,
                    *(item.exact_text_digest for item in accessibility_document.bindings),
                ),
                subject_scope=("historical_internal_accessibility_pre_audit",),
                prohibited_subjects=(
                    "current_accessibility_conformance",
                    "external_accessibility_certification",
                    "grounded_performance",
                    "system_identity",
                    "universal_custody_commitment",
                ),
                establishment_class=EstablishmentClass.RECOMPUTED,
            )
        )
    if page_a11y_receipt is not None:
        receipt_ref = f"{page_a11y_receipt.path}/receipt.json"
        values.append(
            _admitted_verifier(
                ref="verifier:page-a11y-receipt:raw-recomputation",
                verifier_kind="page_a11y_receipt_derivation",
                content_ref=receipt_ref,
                content_digest=page_a11y_receipt.content_digest,
                provenance_parts=tuple(
                    item.content_digest for item in page_a11y_receipt.admitted_sources
                ),
                subject_scope=("historical_page_accessibility_result",),
                prohibited_subjects=(
                    "current_accessibility_conformance",
                    "external_accessibility_certification",
                    "grounded_performance",
                    "system_identity",
                    "universal_custody_commitment",
                ),
                establishment_class=EstablishmentClass.RECOMPUTED,
            )
        )
    return tuple(sorted(values, key=lambda item: item.ref))


def _admitted_verifier(
    *,
    ref: str,
    verifier_kind: Literal[
        "identity_boundary_derivation",
        "accessibility_document_derivation",
        "page_a11y_receipt_derivation",
    ],
    content_ref: str,
    content_digest: str,
    provenance_parts: Sequence[str],
    subject_scope: tuple[str, ...],
    prohibited_subjects: tuple[str, ...],
    establishment_class: Literal[
        EstablishmentClass.RECOMPUTED,
        EstablishmentClass.INDEPENDENTLY_RECONCILED,
    ],
) -> AdmittedVerifier:
    encoded = json.dumps(tuple(provenance_parts), separators=(",", ":")).encode("utf-8")
    provenance_digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return AdmittedVerifier(
        ref=ref,
        verifier_kind=verifier_kind,
        content_ref=content_ref,
        content_digest=content_digest,
        provenance_ref=f"provenance:{verifier_kind}:{provenance_digest}",
        provenance_digest=provenance_digest,
        subject_scope=subject_scope,
        prohibited_subjects=prohibited_subjects,
        establishment_class=establishment_class,
    )


def _evidence_is_admitted(
    evidence: EvidenceBinding,
    *,
    subject: str | None,
    admitted_sources: Sequence[AdmittedSourceMember],
    admitted_verifiers: Sequence[AdmittedVerifier],
    register_as_of: date,
) -> bool:
    admitted = {item.path: item.content_digest for item in admitted_sources}
    verifiers = {item.ref: item for item in admitted_verifiers}
    verifier = verifiers.get(evidence.verifier_ref)
    return bool(
        subject is not None
        and evidence.subject_binding == subject
        and admitted.get(evidence.ref) == evidence.content_digest
        and verifier is not None
        and verifier.content_ref == evidence.ref
        and verifier.content_digest == evidence.content_digest
        and verifier.provenance_ref == evidence.verifier_provenance_ref
        and subject in verifier.subject_scope
        and subject not in verifier.prohibited_subjects
        and verifier.establishment_class
        in {EstablishmentClass.RECOMPUTED, EstablishmentClass.INDEPENDENTLY_RECONCILED}
        and evidence.establishment_class
        in {EstablishmentClass.RECOMPUTED, EstablishmentClass.INDEPENDENTLY_RECONCILED}
        and evidence.source_as_of <= register_as_of
        and evidence.supersession_ref is None
    )


def _projection_groups(claims: Sequence[ClaimPostureRow]) -> tuple[ProjectionGroup, ...]:
    grouped: dict[str, set[str]] = {
        "methodology": set(),
        "evidence_envelope": set(),
        "limitations": set(),
        "accessibility": set(),
        "custody": set(),
    }
    for row in claims:
        if row.family == "accessibility":
            grouped["accessibility"].add(row.claim_id)
        elif row.family == "custody":
            grouped["custody"].add(row.claim_id)
        elif row.family == "grounded_performance":
            grouped["evidence_envelope"].add(row.claim_id)
        else:
            grouped["methodology"].add(row.claim_id)
        if (
            row.effective_state != ClaimPostureState.SUPPORTED
            or row.blocker_codes
            or row.limitations
        ):
            grouped["limitations"].add(row.claim_id)
    return tuple(
        ProjectionGroup(group_id=group_id, claim_ids=tuple(sorted(claim_ids)))
        for group_id, claim_ids in sorted(grouped.items())
    )


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
