"""Strict trust-claim posture contracts and fail-closed authority calculus."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CLAIM_POSTURE_SCHEMA = "policyos.trust.claim_posture_register.v1"
CLAIM_POSTURE_RULE_VERSION = "policyos.trust.claim_posture_rules.v4"
CLAIM_POSTURE_SLICE_BASE_REF = "f935e0c2e9359bc1202ce5d36ea706de58f7aaab"
RATIFIED_IDENTITY_PATH = "docs/system-design-decisions/policyos-identity-and-custody-boundary.md"
RATIFIED_IDENTITY_CONTENT_DIGEST = (
    "sha256:774f6dfb9aa655a079d6c6a2f00ef6442bad9f0ea9b84f370a4e808c5616a332"
)
RATIFIED_IDENTITY_BASIS_DIGEST = (
    "sha256:ebd375b2f2e7c4f3fd0e2f6e02960a842f4e5feeccf84d5a2809c08f47f02682"
)
CUSTODY_APPOINTMENT_SOURCE_PATH = "docs/plans/active/DEBT-REGISTER.md"
CUSTODY_APPOINTMENT_CONTRACT: Mapping[str, tuple[str, str]] = {
    "DS11-CLAIM-LIFECYCLE-ORCHESTRATION": (
        "team-scientist",
        "uv run pytest tests/integration/scientist/governance/"
        "test_claim_lifecycle_orchestration.py::"
        "test_monitor_event_persists_claim_supersession_without_in_place_edit -q",
    ),
    "DS11-PUBLIC-SIGNATURE-POPULATION": (
        "team-design",
        "uv run pytest tests/unit/runtime/http/test_public_export.py::"
        "test_first_governed_public_signature_is_custody_bound -q",
    ),
    "DS11-PUBLISHED-SIGNATURE-WATCHER": (
        "team-runtime",
        "uv run pytest tests/integration/runtime_quality/"
        "test_published_signature_custody.py::"
        "test_every_public_signature_is_watched_for_staleness -q",
    ),
}
CUSTODY_APPOINTMENT_DEBT_IDS: tuple[str, ...] = tuple(CUSTODY_APPOINTMENT_CONTRACT)
MACHINE_LIVE_FRESHNESS_LIMITATION = (
    "MACHINE reconstructs the committed derivation projection; it does not independently "
    "establish live repository freshness."
)
MACHINE_LIVE_FRESHNESS_CHECK = (
    ".venv/bin/python tools/quality/validation/check_trust_claim_posture.py "
    "--repo-root . --check"
)
FIXED_SEMANTIC_BINDING_COUNTS: Mapping[str, int] = {
    "current_accessibility_conformance": 1,
    "external_accessibility_certification": 1,
    "grounded_performance": 1,
    "historical_internal_accessibility_pre_audit": 1,
    "system_identity": 1,
    "universal_custody_commitment": 3,
}
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

_EXECUTABLE_CLOSURE_PREFIXES: tuple[str, ...] = (
    "uv run pytest ",
    "pytest ",
    "corepack pnpm ",
    ".venv/bin/python ",
    "python ",
    "pytest://",
)


def _is_executable_closure_signal(value: str | None) -> bool:
    return bool(
        value
        and value == value.strip()
        and "\n" not in value
        and value.startswith(_EXECUTABLE_CLOSURE_PREFIXES)
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
    may_not_use_for_raw_members: tuple[AdmittedSourceMember, ...]
    may_not_use_for_sites: tuple[LiteralSite, ...]
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
        raw_paths = tuple(member.path for member in self.may_not_use_for_raw_members)
        if raw_paths != tuple(sorted(raw_paths)) or len(raw_paths) != len(set(raw_paths)):
            raise ValueError("may_not_use_for raw members must be sorted and unique")
        if self.may_not_use_for_raw_file_count != len(raw_paths):
            raise ValueError("may_not_use_for raw count differs from carried members")
        if any(site.coordinate.path not in set(raw_paths) for site in self.may_not_use_for_sites):
            raise ValueError("may_not_use_for literal site escapes its raw member set")
        if (
            self.may_not_use_for_literal_site_count != len(self.may_not_use_for_sites)
            or self.may_not_use_for_literal_file_count
            != len({site.coordinate.path for site in self.may_not_use_for_sites})
            or self.may_not_use_for_literal_subject_count
            != len({value for site in self.may_not_use_for_sites for value in site.values})
        ):
            raise ValueError("may_not_use_for literal counts differ from carried sites")
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
        if not _is_executable_closure_signal(self.closure_signal):
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
    may_not_use_for_denied_only_sites: tuple[LiteralSite, ...]
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
        if self.source_state == SourceClaimState.PLANNED and (
            not self.owner.owner
            or not self.owner.source_ref
            or self.owner.establishment_class
            not in {
                EstablishmentClass.RECOMPUTED,
                EstablishmentClass.INDEPENDENTLY_RECONCILED,
            }
            or not _is_executable_closure_signal(self.closure_signal)
        ):
            raise ValueError(
                "every planned source binding requires an established owner and executable "
                "closure signal"
            )
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
    identity_statement: str = Field(min_length=1)
    identity_statement_digest: str
    identity_statement_start_line: int = Field(ge=1)
    identity_statement_end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_content_bindings(self) -> Self:
        """Recompute statement and anti-role receipts from emitted content."""
        if self.paragraph_end_line < self.paragraph_start_line:
            raise ValueError("identity anti-role paragraph line range is reversed")
        if self.identity_statement_end_line < self.identity_statement_start_line:
            raise ValueError("identity statement line range is reversed")
        expected_statement_digest = (
            "sha256:" + hashlib.sha256(self.identity_statement.encode("utf-8")).hexdigest()
        )
        if self.identity_statement_digest != expected_statement_digest:
            raise ValueError("identity statement digest differs from emitted content")
        labels = tuple(item.display_label for item in self.anti_roles)
        roles = tuple(item.role for item in self.anti_roles)
        if not labels or len(labels) != len(set(labels)) or len(roles) != len(set(roles)):
            raise ValueError("identity anti-role set must be nonempty and unique")
        expected_receipt = (
            "sha256:"
            + hashlib.sha256(json.dumps(labels, separators=(",", ":")).encode("utf-8")).hexdigest()
        )
        if self.derivation_receipt_digests != (expected_receipt, expected_receipt):
            raise ValueError("identity anti-role derivation receipts differ from emitted roles")
        for item in self.anti_roles:
            expected_role = re.sub(r"[^a-z0-9]+", "_", item.display_label.casefold()).strip("_")
            if (
                item.role != expected_role
                or item.source_path != self.path
                or item.source_digest != self.content_digest
                or not self.paragraph_start_line <= item.line <= self.paragraph_end_line
            ):
                raise ValueError("identity anti-role source binding differs from its basis")
        return self


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


def _parse_projection_purposes(
    lines: Sequence[str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if not lines or len(lines) % 2:
        raise ValueError("accessibility projection purpose frontmatter is malformed")
    purposes: list[tuple[str, tuple[str, ...]]] = []
    for index in range(0, len(lines), 2):
        purpose = re.fullmatch(r"    - purpose: ([a-z0-9_]+)", lines[index])
        basis = re.fullmatch(r"      basis: \[([a-z0-9_, ]+)\]", lines[index + 1])
        if purpose is None or basis is None:
            raise ValueError("accessibility projection purpose frontmatter is malformed")
        values = tuple(item.strip() for item in basis.group(1).split(","))
        if any(not item for item in values) or len(values) != len(set(values)):
            raise ValueError("accessibility projection purpose basis is malformed")
        purposes.append((purpose.group(1), values))
    return tuple(purposes)


def _parse_projection_frontmatter(
    frontmatter: str,
) -> tuple[
    str,
    dict[str, tuple[str, str, int]],
    tuple[tuple[str, tuple[str, ...]], ...],
    tuple[tuple[str, tuple[str, ...]], ...],
]:
    lines = frontmatter.splitlines()
    body = re.fullmatch(r"  body_sha256: ([0-9a-f]{64})", lines[2] if len(lines) > 2 else "")
    try:
        allowed_start = lines.index("  authoritative_for:")
        denied_start = lines.index("  may_not_use_for:")
    except ValueError as exc:
        raise ValueError("accessibility projection index frontmatter is malformed") from exc
    if (
        len(lines) < 8
        or lines[0] != "ds11_projection_index:"
        or lines[1]
        != "  schema_version: policyos.trust.document_projection_index.v1"
        or body is None
        or lines[3] != "  bindings:"
        or allowed_start <= 4
        or denied_start <= allowed_start + 1
        or denied_start >= len(lines) - 1
    ):
        raise ValueError("accessibility projection index frontmatter is malformed")
    binding_lines = lines[4:allowed_start]
    if not binding_lines or len(binding_lines) % 4:
        raise ValueError("accessibility projection binding frontmatter is malformed")
    selectors: dict[str, tuple[str, str, int]] = {}
    for index in range(0, len(binding_lines), 4):
        key = re.fullmatch(r"    ([a-z0-9_]+):", binding_lines[index])
        value = re.fullmatch(r"      value: (.+)", binding_lines[index + 1])
        exact_text = re.fullmatch(r"      exact_text: (.+)", binding_lines[index + 2])
        occurrence = re.fullmatch(r"      occurrence: ([0-9]+)", binding_lines[index + 3])
        try:
            decoded_value = None if value is None else json.loads(value.group(1))
            decoded_exact = None if exact_text is None else json.loads(exact_text.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError("accessibility projection binding scalar is malformed") from exc
        if (
            key is None
            or not isinstance(decoded_value, str)
            or not isinstance(decoded_exact, str)
            or occurrence is None
            or occurrence.group(1) != "1"
            or key.group(1) in selectors
        ):
            raise ValueError("accessibility projection binding frontmatter is malformed")
        selectors[key.group(1)] = (decoded_value, decoded_exact, 1)
    return (
        body.group(1),
        selectors,
        _parse_projection_purposes(lines[allowed_start + 1 : denied_start]),
        _parse_projection_purposes(lines[denied_start + 1 :]),
    )


class ResolvedDocumentBinding(_StrictModel):
    """One selector independently resolved against complete document body bytes."""

    key: str
    value: str
    exact_text: str
    exact_text_digest: str
    byte_start: int = Field(ge=0)
    byte_end: int = Field(gt=0)
    establishment_class: Literal[EstablishmentClass.RECOMPUTED]


class AccessibilityDocumentBinding(_StrictModel):
    """Content-bound accessibility document and resolved frontmatter basis."""

    path: str
    source_content: str
    content_digest: str
    frontmatter_digest: str
    body_digest: str
    source_as_of: date
    bindings: tuple[ResolvedDocumentBinding, ...]
    authoritative_for: tuple[DocumentProjectionPurpose, ...]
    may_not_use_for: tuple[DocumentProjectionPurpose, ...]
    limitation_refs: tuple[str, ...]

    @model_validator(mode="after")
    def validate_source_content(self) -> Self:
        """Replay selector coordinates and values against carried source bytes."""
        raw = self.source_content.encode("utf-8")
        if "sha256:" + hashlib.sha256(raw).hexdigest() != self.content_digest:
            raise ValueError("accessibility evidence content digest differs from source bytes")
        if not self.source_content.startswith("---\n"):
            raise ValueError("accessibility evidence frontmatter is absent")
        frontmatter_end = self.source_content.find("\n---\n", 4)
        if frontmatter_end < 0:
            raise ValueError("accessibility evidence frontmatter is unterminated")
        frontmatter = self.source_content[4:frontmatter_end]
        body = self.source_content[frontmatter_end + 5 :]
        body_bytes = body.encode("utf-8")
        if (
            "sha256:" + hashlib.sha256(frontmatter.encode("utf-8")).hexdigest()
            != self.frontmatter_digest
            or "sha256:" + hashlib.sha256(body_bytes).hexdigest() != self.body_digest
        ):
            raise ValueError("accessibility evidence sections differ from source bytes")
        body_sha, selectors, allowed_purposes, denied_purposes = (
            _parse_projection_frontmatter(frontmatter)
        )
        if (
            body_sha != self.body_digest.removeprefix("sha256:")
            or allowed_purposes
            != tuple((item.purpose, item.basis) for item in self.authoritative_for)
            or denied_purposes
            != tuple((item.purpose, item.basis) for item in self.may_not_use_for)
        ):
            raise ValueError("accessibility evidence projection differs from source bytes")
        keys = tuple(item.key for item in self.bindings)
        if (
            len(keys) != len(set(keys))
            or tuple(sorted(keys)) != keys
            or set(keys) != set(selectors)
        ):
            raise ValueError("accessibility evidence bindings must be sorted and unique")
        for item in self.bindings:
            selector_value, selector_exact_text, selector_occurrence = selectors[item.key]
            exact = item.exact_text.encode("utf-8")
            if (
                item.value != selector_value
                or item.exact_text != selector_exact_text
                or selector_occurrence != 1
                or body_bytes.count(exact) != 1
                or body_bytes.find(exact) != item.byte_start
                or item.byte_end != item.byte_start + len(exact)
                or item.value.encode("utf-8") not in exact
                or "sha256:" + hashlib.sha256(exact).hexdigest()
                != item.exact_text_digest
            ):
                raise ValueError(
                    f"accessibility evidence selector {item.key} differs from source bytes"
                )
        required = {
            key
            for purpose in (*self.authoritative_for, *self.may_not_use_for)
            for key in purpose.basis
        }
        if not required or not required <= set(keys):
            raise ValueError("accessibility evidence purpose basis is incomplete")
        source_as_of = next(
            (item.value for item in self.bindings if item.key == "source_as_of"), None
        )
        if source_as_of != self.source_as_of.isoformat():
            raise ValueError("accessibility evidence source date differs from source bytes")
        limitation = "It does not replace the planned third-party countersign."
        occurrences = sum(
            " ".join(paragraph.split()).count(limitation)
            for paragraph in re.split(r"\n[ \t]*\n", body)
        )
        if self.limitation_refs != (limitation,) or occurrences != 1:
            raise ValueError("accessibility evidence limitation differs from source bytes")
        return self


class CustodyAppointmentSource(_StrictModel):
    """Exact admitted Markdown row for one custody debt appointment."""

    path: Literal["docs/plans/active/DEBT-REGISTER.md"]
    debt_id: str
    source_content: str
    content_digest: str


class PageA11yFailureBinding(_StrictModel):
    """Stable semantic failure derived from one Playwright spec result."""

    identity: str
    test_id: str
    issue_signature: str


def _page_issue_signature(message: str) -> str:
    plain = re.sub(r"\x1b\[[0-9;]*m", "", message)
    axe = re.search(r'"id"\s*:\s*"([^"]+)"', plain)
    if axe:
        return f"axe:{axe.group(1)}"
    expected = re.search(r'Expected substring:\s*"(?:link|button) \\"([^"\\]+)\\""', plain)
    if expected:
        return f"accessible_name:{expected.group(1)}"
    raise ValueError("page-a11y failure has no admitted semantic issue signature")


def _page_result_rows(
    suites: object,
) -> tuple[tuple[tuple[str, str], ...], tuple[PageA11yFailureBinding, ...]]:
    if not isinstance(suites, list):
        raise ValueError("page-a11y suites must be a list")
    identities: list[tuple[str, str]] = []
    failures: list[PageA11yFailureBinding] = []
    for suite in suites:
        if not isinstance(suite, dict):
            raise ValueError("page-a11y suite must be an object")
        specs = suite.get("specs", [])
        if not isinstance(specs, list):
            raise ValueError("page-a11y specs must be a list")
        for spec in specs:
            if not isinstance(spec, dict):
                raise ValueError("page-a11y spec must be an object")
            identity = f"{spec.get('file')}::{spec.get('title')}"
            tests = spec.get("tests", [])
            if not isinstance(tests, list):
                raise ValueError("page-a11y tests must be a list")
            for test in tests:
                if not isinstance(test, dict):
                    raise ValueError("page-a11y test must be an object")
                raw_status = str(test.get("status"))
                status = (
                    "passed"
                    if raw_status == "expected"
                    else "skipped"
                    if raw_status == "skipped"
                    else "failed"
                )
                identities.append((identity, status))
                if status == "failed":
                    results = test.get("results", [])
                    if not isinstance(results, list):
                        raise ValueError("page-a11y test results must be a list")
                    message = " ".join(
                        str(result.get("error", {}).get("message", ""))
                        for result in results
                        if isinstance(result, dict)
                        and isinstance(result.get("error", {}), dict)
                    )
                    failures.append(
                        PageA11yFailureBinding(
                            identity=identity,
                            test_id=str(spec.get("id")),
                            issue_signature=_page_issue_signature(message),
                        )
                    )
        nested = suite.get("suites", [])
        if not isinstance(nested, list):
            raise ValueError("nested page-a11y suites must be a list")
        nested_identities, nested_failures = _page_result_rows(nested)
        identities.extend(nested_identities)
        failures.extend(nested_failures)
    return tuple(identities), tuple(failures)


class PageA11yReceiptBinding(_StrictModel):
    """Five-file, independently recomputed historical page-a11y receipt."""

    schema_version: Literal["policyos.ds11.page_a11y_base_receipt.v1"]
    authority_purpose: Literal["historical_currentness_limitation"]
    status: Literal["blocked"]
    execution_entry_commit: Literal["8e5832bbdb0f206b6221112f4a1502b45981bd40"]
    policy_source_base_commit: Literal["f935e0c2e9359bc1202ce5d36ea706de58f7aaab"]
    command: Literal[
        "PLAYWRIGHT_JSON_OUTPUT_FILE=<receipt-relative-output> corepack pnpm --filter "
        "@polisyos/runtime-dashboard exec playwright test e2e/a11y --project=chromium "
        "--reporter=json"
    ]
    path: str
    source_contents: Mapping[str, str]
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

    @model_validator(mode="after")
    def validate_source_contents(self) -> Self:
        """Recompute summary, failures, and metadata from all five carried JSON files."""
        expected_names = (
            "environment-after.json",
            "environment-before.json",
            "receipt.json",
            "run-1/.last-run.json",
            "run-1/results.json",
        )
        expected_paths = tuple(f"{self.path}/{name}" for name in expected_names)
        if self.path != "docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base":
            raise ValueError("page-a11y evidence path differs from the admitted owner")
        if set(self.source_contents) != set(expected_paths):
            raise ValueError("page-a11y evidence content set is incomplete")
        derived_sources = tuple(
            AdmittedSourceMember(
                path=path,
                content_digest="sha256:"
                + hashlib.sha256(self.source_contents[path].encode("utf-8")).hexdigest(),
            )
            for path in expected_paths
        )
        if self.admitted_sources != derived_sources:
            raise ValueError("page-a11y evidence digests differ from carried source bytes")
        source_by_name = {
            name: self.source_contents[f"{self.path}/{name}"] for name in expected_names
        }
        if self.content_digest != derived_sources[2].content_digest:
            raise ValueError("page-a11y receipt digest differs from carried source bytes")
        try:
            normalized = json.loads(source_by_name["receipt.json"])
            results = json.loads(source_by_name["run-1/results.json"])
            last_run = json.loads(source_by_name["run-1/.last-run.json"])
            environments = (
                json.loads(source_by_name["environment-before.json"]),
                json.loads(source_by_name["environment-after.json"]),
            )
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("page-a11y evidence contains malformed JSON") from exc
        if not all(
            isinstance(environment, dict)
            and {"captured_at", "node", "platform", "arch", "cwd"} <= set(environment)
            for environment in environments
        ):
            raise ValueError("page-a11y environment evidence is malformed")
        if not isinstance(normalized, dict) or not isinstance(results, dict):
            raise ValueError("page-a11y evidence roots must be objects")
        expected_metadata = {
            "schema_version": self.schema_version,
            "authority_purpose": self.authority_purpose,
            "status": self.status,
            "execution_entry_commit": self.execution_entry_commit,
            "policy_source_base_commit": self.policy_source_base_commit,
            "command": self.command,
        }
        if {key: normalized.get(key) for key in expected_metadata} != expected_metadata:
            raise ValueError("page-a11y authority metadata differs from carried source bytes")
        identities, failures = _page_result_rows(results.get("suites", []))
        stats = results.get("stats", {})
        if not isinstance(stats, dict):
            raise ValueError("page-a11y result stats are malformed")
        observed = {
            "collected": len(identities),
            "passed": sum(item[1] == "passed" for item in identities),
            "failed": sum(item[1] == "failed" for item in identities),
            "skipped": sum(item[1] == "skipped" for item in identities),
            "duration_ms": stats.get("duration"),
            "exit_code": 1 if failures else 0,
        }
        authored_identities = tuple(
            (item["identity"], item["status"])
            for item in normalized.get("collected_identities", ())
        )
        authored_failures = tuple(
            (item["identity"], item["status"])
            for item in normalized.get("inherited_failure_identities", ())
        )
        if normalized.get("result") != observed or authored_identities != identities:
            raise ValueError("page-a11y receipt summary differs from carried result bytes")
        if authored_failures != tuple((item.identity, "failed") for item in failures):
            raise ValueError("page-a11y receipt failures differ from carried result bytes")
        raw_receipts = normalized.get("raw_receipts", {})
        if not isinstance(raw_receipts, dict) or (
            raw_receipts.get("results_sha256")
            != hashlib.sha256(source_by_name["run-1/results.json"].encode("utf-8")).hexdigest()
            or raw_receipts.get("last_run_sha256")
            != hashlib.sha256(source_by_name["run-1/.last-run.json"].encode("utf-8")).hexdigest()
        ):
            raise ValueError("page-a11y raw receipts differ from carried source bytes")
        failure_ids = {item.test_id for item in failures}
        if not isinstance(last_run, dict) or (
            last_run.get("status") != "failed"
            or set(last_run.get("failedTests", ())) != failure_ids
        ):
            raise ValueError("page-a11y last-run failures differ from carried result bytes")
        replay = normalized.get("replay_agreement", {})
        source_date = str(stats.get("startTime"))[:10]
        if (
            not isinstance(replay, dict)
            or replay.get("admissibility") != "not_established"
            or replay.get("committed_raw_runs") != 1
            or self.source_as_of.isoformat() != source_date
            or self.collected != observed["collected"]
            or self.passed != observed["passed"]
            or self.failed != observed["failed"]
            or self.skipped != observed["skipped"]
            or self.duration_ms != observed["duration_ms"]
            or self.exit_code != observed["exit_code"]
            or self.failures != failures
            or self.replay_establishment != EstablishmentClass.NOT_ESTABLISHED
            or self.limitation_refs != (str(replay.get("limitation")),)
        ):
            raise ValueError("page-a11y typed evidence differs from carried source bytes")
        return self


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


class MachineAdmissionBoundary(_StrictModel):
    """Typed limit on what the static MACHINE consumer independently establishes."""

    authority_purpose: Literal["committed_derivation_projection_reconstruction"]
    live_repository_freshness: Literal[EstablishmentClass.NOT_ESTABLISHED]
    owner: Literal["team-architecture"]
    closure_signal: Literal[
        ".venv/bin/python tools/quality/validation/check_trust_claim_posture.py --repo-root . --check"
    ]
    limitation_refs: tuple[
        Literal[
            "MACHINE reconstructs the committed derivation projection; it does not independently "
            "establish live repository freshness."
        ]
    ]


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
    may_not_use_for_denied_only_sites: tuple[LiteralSite, ...]
    identity_boundary: IdentityBoundaryBinding
    custody_appointment_sources: tuple[CustodyAppointmentSource, ...]
    admitted_verifiers: tuple[AdmittedVerifier, ...]
    accessibility_document: AccessibilityDocumentBinding | None
    page_a11y_receipt: PageA11yReceiptBinding | None
    source_inventory: tuple[SourceInventoryRow, ...]
    claims: tuple[ClaimPostureRow, ...]
    projection_groups: tuple[ProjectionGroup, ...]
    machine_admission_boundary: MachineAdmissionBoundary
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
        _validate_source_inventory_basis(self.source_inventory, admitted_by_path)
        _validate_derivation_receipts(
            self.ast_derivation,
            self.token_derivation,
            inventory=self.source_inventory,
            admitted_sources=self.admitted_sources,
            denied_only_sites=self.may_not_use_for_denied_only_sites,
        )
        if (
            admitted_by_path.get(self.identity_boundary.path)
            != self.identity_boundary.content_digest
        ):
            raise ValueError("identity_boundary does not bind admitted source bytes")
        if self.accessibility_document is not None and (
            admitted_by_path.get(self.accessibility_document.path)
            != self.accessibility_document.content_digest
        ):
            raise ValueError("accessibility evidence does not bind admitted source bytes")
        if self.page_a11y_receipt is not None and any(
            admitted_by_path.get(member.path) != member.content_digest
            for member in self.page_a11y_receipt.admitted_sources
        ):
            raise ValueError("page-a11y evidence does not bind admitted source bytes")
        if _identity_basis_digest(self.identity_boundary) != RATIFIED_IDENTITY_BASIS_DIGEST:
            raise ValueError("ratified identity basis differs from the admitted closed receipt")
        _validate_fixed_semantic_basis(self.claims)
        custody_appointments = _validate_custody_appointments(
            self.claims,
            self.custody_appointment_sources,
        )
        all_bindings = tuple(binding for row in self.claims for binding in row.source_bindings)
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
        _validate_fixed_semantic_bindings(
            self.claims,
            identity=self.identity_boundary,
            accessibility_document=self.accessibility_document,
            page_receipt=self.page_a11y_receipt,
            admitted_verifiers=self.admitted_verifiers,
            custody_appointments=custody_appointments,
        )
        actual_source_bindings = tuple(
            binding
            for binding in all_bindings
            if binding.subject not in FIXED_SEMANTIC_BINDING_COUNTS
        )
        expected_source_bindings = _expected_source_bindings(self.source_inventory)
        if _sort_source_bindings(actual_source_bindings) != expected_source_bindings:
            raise ValueError("claim source bindings differ from the complete source inventory")
        expected_claims = _claim_rows(
            all_bindings,
            register_as_of=self.register_as_of,
            identity_boundary=self.identity_boundary,
            admitted_sources=self.admitted_sources,
            admitted_verifiers=self.admitted_verifiers,
        )
        if self.claims != expected_claims:
            raise ValueError("authored claim rows differ from complete binding recomputation")
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
        if planned_owner and _is_executable_closure_signal(closure_signal):
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
        if binding.source_state == SourceClaimState.PLANNED:
            if (
                not binding.owner.owner
                or not binding.owner.source_ref
                or binding.owner.establishment_class
                not in {
                    EstablishmentClass.RECOMPUTED,
                    EstablishmentClass.INDEPENDENTLY_RECONCILED,
                }
            ):
                blockers.add("DS11-OWNER-NOT-ESTABLISHED")
            if not _is_executable_closure_signal(binding.closure_signal):
                blockers.add("DS11-PLANNED-CLOSURE-SIGNAL-MISSING")
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
    may_not_use_for_denied_only_sites: Sequence[LiteralSite],
    identity_boundary: IdentityBoundaryBinding,
    custody_appointment_sources: Sequence[CustodyAppointmentSource],
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
        "may_not_use_for_denied_only_sites": tuple(may_not_use_for_denied_only_sites),
        "identity_boundary": identity_boundary,
        "custody_appointment_sources": tuple(custody_appointment_sources),
        "admitted_verifiers": verifiers,
        "accessibility_document": accessibility_document,
        "page_a11y_receipt": page_a11y_receipt,
        "source_inventory": inventory,
        "claims": claims,
        "projection_groups": groups,
        "machine_admission_boundary": MachineAdmissionBoundary(
            authority_purpose="committed_derivation_projection_reconstruction",
            live_repository_freshness=EstablishmentClass.NOT_ESTABLISHED,
            owner="team-architecture",
            closure_signal=MACHINE_LIVE_FRESHNESS_CHECK,
            limitation_refs=(MACHINE_LIVE_FRESHNESS_LIMITATION,),
        ),
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


def _identity_basis_digest(identity: IdentityBoundaryBinding) -> str:
    encoded = json.dumps(
        identity.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _validate_source_inventory_basis(
    inventory: Sequence[SourceInventoryRow],
    admitted_by_path: Mapping[str, str],
) -> None:
    for row in inventory:
        if admitted_by_path.get(row.path) != row.content_digest:
            raise ValueError("source inventory row differs from admitted source membership")
        coordinates = (
            *row.declaration_coordinates,
            *row.carrier_coordinates,
            *row.consumer_coordinates,
            *(site.coordinate for site in row.authoritative_sites),
            *(site.coordinate for site in row.forbidden_sites),
        )
        if any(coordinate.path != row.path for coordinate in coordinates):
            raise ValueError("source inventory coordinate escapes its source row")


def _validate_derivation_receipts(
    ast_receipt: SourceDerivationReceipt,
    token_receipt: SourceDerivationReceipt,
    *,
    inventory: Sequence[SourceInventoryRow],
    admitted_sources: Sequence[AdmittedSourceMember],
    denied_only_sites: Sequence[LiteralSite],
) -> None:
    """Recompute every inventory-derived complete-set receipt field."""
    if ast_receipt.method != "ast" or token_receipt.method != "tokenize":
        raise ValueError("source derivation methods differ from their admitted lanes")
    ast_payload = ast_receipt.model_dump(mode="json", exclude={"method"})
    token_payload = token_receipt.model_dump(mode="json", exclude={"method"})
    if {
        key: value
        for key, value in ast_payload.items()
        if key not in {"row_digest", "may_not_use_for_sites"}
    } != {
        key: value
        for key, value in token_payload.items()
        if key not in {"row_digest", "may_not_use_for_sites"}
    }:
        raise ValueError("source derivation receipts disagree")
    if ast_receipt.may_not_use_for_sites != token_receipt.may_not_use_for_sites:
        raise ValueError("may_not_use_for source derivations disagree")
    inventory_denied_sites = tuple(
        site
        for row in inventory
        for site in row.forbidden_sites
        if site.declaration_form == "assignment"
        and site.wrapper_kind != "dynamic"
        and site.resolution == SourceResolution.RESOLVED
    )
    inventory_paths = {row.path for row in inventory}
    if any(site.coordinate.path in inventory_paths for site in denied_only_sites):
        raise ValueError("may_not_use_for denied-only site duplicates the source inventory")
    canonical_denied_sites = (*inventory_denied_sites, *denied_only_sites)
    if ast_receipt.may_not_use_for_sites != canonical_denied_sites:
        raise ValueError("may_not_use_for receipts differ from the canonical producer projection")
    admitted_by_path = {member.path: member.content_digest for member in admitted_sources}
    if any(
        admitted_by_path.get(member.path) != member.content_digest
        for receipt in (ast_receipt, token_receipt)
        for member in receipt.may_not_use_for_raw_members
    ):
        raise ValueError("may_not_use_for source receipt differs from admitted bytes")
    raw_paths = {member.path for member in ast_receipt.may_not_use_for_raw_members}
    if any(site.coordinate.path not in raw_paths for site in canonical_denied_sites):
        raise ValueError("may_not_use_for canonical site escapes the raw source denominator")
    role_counts = {role: sum(row.role == role for row in inventory) for role in SourceInventoryRole}
    exact_rows = tuple(
        row
        for row in inventory
        if row.role not in {SourceInventoryRole.SUBSTRING_COLLISION, SourceInventoryRole.AMBIGUOUS}
    )
    direct_sites = tuple(
        site
        for row in inventory
        for site in row.authoritative_sites
        if site.declaration_form == "assignment"
        and site.wrapper_kind == "direct"
        and site.resolution == SourceResolution.RESOLVED
    )
    wrapper_sites = tuple(
        site
        for row in inventory
        for site in row.authoritative_sites
        if site.declaration_form == "assignment"
        and site.wrapper_kind != "dynamic"
        and site.resolution == SourceResolution.RESOLVED
    )
    row_payload = [row.model_dump(mode="json") for row in inventory]
    row_digest = "sha256:" + hashlib.sha256(
        json.dumps(
            row_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    python_member_count = sum(
        member.path.startswith("src/") and member.path.endswith(".py")
        for member in admitted_sources
    )
    expected = {
        "scanned_python_count": python_member_count,
        "raw_candidate_count": len(inventory),
        "exact_field_file_count": len(exact_rows),
        "declaring_file_count": sum(
            row.role
            in {SourceInventoryRole.DECLARES_ONLY, SourceInventoryRole.DECLARES_AND_CONSUMES}
            for row in inventory
        ),
        "consuming_file_count": sum(
            row.role
            in {SourceInventoryRole.CONSUMES_ONLY, SourceInventoryRole.DECLARES_AND_CONSUMES}
            for row in inventory
        ),
        "role_counts": {role.value: count for role, count in role_counts.items()},
        "direct_literal_site_count": len(direct_sites),
        "direct_literal_file_count": len({site.coordinate.path for site in direct_sites}),
        "direct_literal_subject_count": len(
            {value for site in direct_sites for value in site.values}
        ),
        "direct_empty_site_count": sum(not site.values for site in direct_sites),
        "wrapper_literal_site_count": len(wrapper_sites),
        "wrapper_literal_file_count": len({site.coordinate.path for site in wrapper_sites}),
        "wrapper_literal_subject_count": len(
            {value for site in wrapper_sites for value in site.values}
        ),
        "may_not_use_for_raw_file_count": len(ast_receipt.may_not_use_for_raw_members),
        "may_not_use_for_literal_site_count": len(canonical_denied_sites),
        "may_not_use_for_literal_file_count": len(
            {site.coordinate.path for site in canonical_denied_sites}
        ),
        "may_not_use_for_literal_subject_count": len(
            {value for site in canonical_denied_sites for value in site.values}
        ),
        "row_digest": row_digest,
    }
    if any(ast_payload.get(key) != value for key, value in expected.items()):
        raise ValueError("source derivation receipt differs from the complete source inventory")


def _validate_custody_appointments(
    claims: Sequence[ClaimPostureRow],
    sources: Sequence[CustodyAppointmentSource],
) -> tuple[tuple[str, str, str, str], ...]:
    """Recompute custody appointments from their exact admitted Markdown rows."""
    source_ids = tuple(item.debt_id for item in sources)
    if source_ids != CUSTODY_APPOINTMENT_DEBT_IDS:
        raise ValueError("custody appointment sources must be the closed sorted debt set")
    derived: list[tuple[str, str, str, str]] = []
    for source in sources:
        if "\n" in source.source_content or not source.source_content.startswith("|"):
            raise ValueError("custody appointment source must be exactly one Markdown row")
        digest = "sha256:" + hashlib.sha256(source.source_content.encode("utf-8")).hexdigest()
        if source.content_digest != digest:
            raise ValueError("custody appointment digest differs from admitted source bytes")
        cells = [cell.strip() for cell in source.source_content.strip().strip("|").split("|")]
        if len(cells) != 5:
            raise ValueError("custody appointment source row must contain exactly five cells")
        ids = re.findall(r"`([^`]+)`", cells[0])
        owners = tuple(
            token
            for token in re.findall(r"`([^`]+)`", cells[2])
            if re.fullmatch(r"team-[a-z0-9-]+", token)
        )
        statuses = re.findall(r"`([^`]+)`", cells[3])
        commands = tuple(
            token
            for token in re.findall(r"`([^`]+)`", cells[4])
            if _is_executable_closure_signal(token)
        )
        if (
            ids != [source.debt_id]
            or len(owners) != 1
            or statuses != ["open"]
            or len(commands) != 1
        ):
            raise ValueError("custody appointment source row is not exactly appointed and open")
        if (owners[0], commands[0]) != CUSTODY_APPOINTMENT_CONTRACT[source.debt_id]:
            raise ValueError("custody appointment source differs from the accepted contract")
        derived.append(
            (
                source.debt_id,
                owners[0],
                commands[0],
                f"{source.path}#{source.debt_id}@{digest}",
            )
        )

    rows = tuple(row for row in claims if row.subject == "universal_custody_commitment")
    if len(rows) != 1:
        raise ValueError("custody appointment row is absent or duplicated")
    bindings = rows[0].source_bindings
    if len(bindings) != 3:
        raise ValueError("custody appointment set must contain exactly three arms")
    appointments: list[tuple[str, str, str, str]] = []
    for binding in bindings:
        if (
            binding.source_state != SourceClaimState.PLANNED
            or binding.owner.basis != "closure_commitment"
            or binding.owner.establishment_class != EstablishmentClass.RECOMPUTED
            or not binding.owner.source_ref
            or not binding.owner.source_ref.startswith(f"{CUSTODY_APPOINTMENT_SOURCE_PATH}#")
            or len(binding.prerequisite_refs) != 1
            or not binding.owner.owner
            or not binding.closure_signal
            or binding.identity_boundary_ref != RATIFIED_IDENTITY_PATH
        ):
            raise ValueError("custody appointment is not bound to its admitted debt source")
        appointments.append(
            (
                binding.prerequisite_refs[0],
                binding.owner.owner,
                binding.closure_signal,
                binding.owner.source_ref,
            )
        )
    ordered = tuple(sorted(appointments))
    if ordered != tuple(derived):
        raise ValueError("custody appointments differ from admitted source row bytes")
    return ordered


def _validate_fixed_semantic_basis(claims: Sequence[ClaimPostureRow]) -> None:
    rows = [row for row in claims if row.subject in FIXED_SEMANTIC_BINDING_COUNTS]
    subjects = {row.subject for row in rows}
    if len(rows) != len(FIXED_SEMANTIC_BINDING_COUNTS) or subjects != set(
        FIXED_SEMANTIC_BINDING_COUNTS
    ):
        raise ValueError("fixed semantic subject set is incomplete or duplicated")
    if any(
        len(row.source_bindings) != FIXED_SEMANTIC_BINDING_COUNTS[row.subject]
        for row in rows
        if row.subject is not None
    ):
        raise ValueError("fixed semantic binding count differs from the closed basis")


def _expected_semantic_predicates(
    *,
    satisfied: set[str],
    evidence_refs: tuple[str, ...],
) -> tuple[SupportPredicate, ...]:
    issues = {
        "content_bound_source": "DS11-SOURCE-CONTENT-NOT-BOUND",
        "purpose_permission": "DS11-AUTHORITY-PURPOSE-DENIED",
        "accountable_owner": "DS11-OWNER-NOT-ESTABLISHED",
        "applicable_jurisdiction": "DS11-JURISDICTION-NOT-ESTABLISHED",
        "current_review": "DS11-REVIEW-MISSING-OR-STALE",
        "content_bound_evidence": "DS11-EVIDENCE-NOT-INDEPENDENTLY-BOUND",
        "identity_boundary": "DS11-IDENTITY-BOUNDARY-NOT-ESTABLISHED",
        "no_blocker": "DS11-SOURCE-BLOCKER-PRESENT",
    }
    return tuple(
        SupportPredicate(
            kind=kind,
            satisfied=kind in satisfied,
            establishment_class=(
                EstablishmentClass.RECOMPUTED
                if kind in satisfied
                else EstablishmentClass.NOT_ESTABLISHED
            ),
            evidence_refs=evidence_refs if kind in satisfied else (),
            issue_code=None if kind in satisfied else issue,
        )
        for kind, issue in sorted(issues.items())
    )


def _expected_semantic_evidence(
    *,
    subject: str,
    verifier: AdmittedVerifier,
    source_as_of: date,
    establishment_class: EstablishmentClass = EstablishmentClass.RECOMPUTED,
) -> EvidenceBinding:
    return EvidenceBinding(
        ref=verifier.content_ref,
        content_digest=verifier.content_digest,
        subject_binding=subject,
        verifier_ref=verifier.ref,
        verifier_provenance_ref=verifier.provenance_ref,
        establishment_class=establishment_class,
        source_as_of=source_as_of,
        supersession_ref=None,
    )


def _validate_exact_fixed_binding(
    binding: ClaimSourceBinding,
    *,
    coordinate: SourceCoordinate,
    content_digest: str,
    source_state: SourceClaimState,
    subject: str,
    family: str,
    allowed_purposes: tuple[str, ...],
    denied_purposes: tuple[str, ...],
    owner: OwnerBinding,
    jurisdiction: str | None,
    jurisdiction_establishment: EstablishmentClass,
    review_on: date | None,
    review_due: date | None,
    source_as_of: date | None,
    evidence: EvidenceBinding | None,
    limitation_refs: tuple[str, ...],
    prerequisite_refs: tuple[str, ...] = (),
    closure_signal: str | None = None,
    predicate_facts: set[str] | None = None,
) -> None:
    evidence_bindings = () if evidence is None else (evidence,)
    evidence_refs = () if evidence is None else (evidence.ref,)
    actual = (
        binding.coordinate,
        binding.content_digest,
        binding.resolution,
        binding.source_state,
        binding.subject,
        binding.family,
        binding.authoritative_for,
        binding.may_not_use_for,
        binding.authority_purpose,
        binding.owner,
        binding.jurisdiction,
        binding.jurisdiction_establishment,
        binding.review_on,
        binding.review_due,
        binding.source_as_of,
        binding.evidence_refs,
        binding.evidence_bindings,
        binding.limitation_refs,
        binding.prerequisite_refs,
        binding.identity_boundary_ref,
        binding.declared_scope_assumption,
        binding.supersedes_ref,
        binding.superseded_by_ref,
        binding.predicates,
        binding.closure_signal,
    )
    expected = (
        coordinate,
        content_digest,
        SourceResolution.RESOLVED,
        source_state,
        subject,
        family,
        allowed_purposes,
        denied_purposes,
        subject,
        owner,
        jurisdiction,
        jurisdiction_establishment,
        review_on,
        review_due,
        source_as_of,
        evidence_refs,
        evidence_bindings,
        limitation_refs,
        prerequisite_refs,
        RATIFIED_IDENTITY_PATH,
        None,
        None,
        None,
        _expected_semantic_predicates(
            satisfied=predicate_facts or set(),
            evidence_refs=evidence_refs,
        ),
        closure_signal,
    )
    if actual != expected:
        raise ValueError(
            f"fixed semantic binding for {subject} differs from its typed artifact basis"
        )


def _validate_fixed_semantic_bindings(
    claims: Sequence[ClaimPostureRow],
    *,
    identity: IdentityBoundaryBinding,
    accessibility_document: AccessibilityDocumentBinding | None,
    page_receipt: PageA11yReceiptBinding | None,
    admitted_verifiers: Sequence[AdmittedVerifier],
    custody_appointments: Sequence[tuple[str, str, str, str]],
) -> None:
    """Recompute every fixed semantic arm from its admitted typed artifacts."""
    rows = {row.subject: row for row in claims if row.subject in FIXED_SEMANTIC_BINDING_COUNTS}
    verifier_by_kind = {item.verifier_kind: item for item in admitted_verifiers}
    identity_verifier = verifier_by_kind["identity_boundary_derivation"]
    identity_coordinate = SourceCoordinate(
        path=identity.path,
        symbol="ratified_system_identity",
        line=identity.identity_statement_start_line,
        column=0,
        field_name="authoritative_for",
        use_kind="declaration",
    )
    identity_owner = OwnerBinding(
        owner=identity.owner,
        basis="ratified_document",
        source_ref=identity.path,
        establishment_class=EstablishmentClass.RECOMPUTED,
    )
    identity_is_exact = identity.content_digest == RATIFIED_IDENTITY_CONTENT_DIGEST
    review_due = identity.last_reviewed + timedelta(days=365)
    complete_facts = set(REQUIRED_SUPPORT_PREDICATES)
    identity_evidence = _expected_semantic_evidence(
        subject="system_identity",
        verifier=identity_verifier,
        source_as_of=identity.last_reviewed,
        establishment_class=EstablishmentClass.INDEPENDENTLY_RECONCILED,
    )
    _validate_exact_fixed_binding(
        rows["system_identity"].source_bindings[0],
        coordinate=identity_coordinate,
        content_digest=identity.content_digest,
        source_state=(
            SourceClaimState.SUPPORTED if identity_is_exact else SourceClaimState.BLOCKED
        ),
        subject="system_identity",
        family="methodology",
        allowed_purposes=identity.authoritative_for,
        denied_purposes=identity.may_not_use_for,
        owner=identity_owner,
        jurisdiction="non_jurisdiction_specific",
        jurisdiction_establishment=EstablishmentClass.RECOMPUTED,
        review_on=identity.last_reviewed,
        review_due=review_due,
        source_as_of=identity.last_reviewed,
        evidence=identity_evidence,
        limitation_refs=(
            "Bounded to non-jurisdiction-specific system identity."
            if identity_is_exact
            else "System identity source differs from the ratified byte boundary.",
        ),
        predicate_facts=(complete_facts if identity_is_exact else complete_facts - {"no_blocker"}),
    )

    custody_by_id = {
        binding.prerequisite_refs[0]: binding
        for binding in rows["universal_custody_commitment"].source_bindings
    }
    custody_facts = {
        "content_bound_source",
        "purpose_permission",
        "accountable_owner",
        "identity_boundary",
    }
    for debt_id, owner_name, closure_signal, source_ref in custody_appointments:
        _validate_exact_fixed_binding(
            custody_by_id[debt_id],
            coordinate=identity_coordinate,
            content_digest=identity.content_digest,
            source_state=(
                SourceClaimState.PLANNED if identity_is_exact else SourceClaimState.BLOCKED
            ),
            subject="universal_custody_commitment",
            family="custody",
            allowed_purposes=("universal_custody_commitment",),
            denied_purposes=identity.may_not_use_for,
            owner=OwnerBinding(
                owner=owner_name,
                basis="closure_commitment",
                source_ref=source_ref,
                establishment_class=EstablishmentClass.RECOMPUTED,
            ),
            jurisdiction="non_jurisdiction_specific",
            jurisdiction_establishment=EstablishmentClass.RECOMPUTED,
            review_on=identity.last_reviewed,
            review_due=review_due,
            source_as_of=identity.last_reviewed,
            evidence=None,
            limitation_refs=(f"Planned prerequisite: {debt_id}",),
            prerequisite_refs=(debt_id,),
            closure_signal=closure_signal,
            predicate_facts=custody_facts,
        )

    unavailable_digest = "sha256:" + "0" * 64
    accessibility_path = "docs/compliance/A11Y_AUDIT_2026Q2.md"
    accessibility_coordinate = SourceCoordinate(
        path=accessibility_path,
        symbol="ds11_projection_index",
        line=1,
        column=0,
        field_name="authoritative_for",
        use_kind="declaration",
    )
    if accessibility_document is None:
        accessibility_owner = OwnerBinding(
            owner=None,
            basis="not_established",
            source_ref=None,
            establishment_class=EstablishmentClass.NOT_ESTABLISHED,
        )
        historical_evidence = None
        allowed_accessibility_purposes: tuple[str, ...] = ()
        denied_accessibility_purposes = (
            "current_accessibility_conformance",
            "external_accessibility_certification",
        )
        historical_facts = {"identity_boundary"}
        accessibility_digest = unavailable_digest
        accessibility_source_as_of = None
        accessibility_review_due = None
        historical_limitation = "Accessibility document projection basis is unavailable."
    else:
        accessibility_coordinate = accessibility_coordinate.model_copy(
            update={"path": accessibility_document.path}
        )
        selector_values = {item.key: item.value for item in accessibility_document.bindings}
        accessibility_owner = OwnerBinding(
            owner=selector_values.get("assessment_owner"),
            basis="ratified_document",
            source_ref=accessibility_document.path,
            establishment_class=EstablishmentClass.RECOMPUTED,
        )
        historical_evidence = _expected_semantic_evidence(
            subject="historical_internal_accessibility_pre_audit",
            verifier=verifier_by_kind["accessibility_document_derivation"],
            source_as_of=accessibility_document.source_as_of,
        )
        allowed_accessibility_purposes = tuple(
            item.purpose for item in accessibility_document.authoritative_for
        )
        denied_accessibility_purposes = tuple(
            item.purpose for item in accessibility_document.may_not_use_for
        )
        historical_facts = complete_facts - {"applicable_jurisdiction"}
        accessibility_digest = accessibility_document.content_digest
        accessibility_source_as_of = accessibility_document.source_as_of
        accessibility_review_due = accessibility_document.source_as_of + timedelta(days=365)
        historical_limitation = (
            "Historical internal pre-audit only; jurisdiction is not established."
        )
    _validate_exact_fixed_binding(
        rows["historical_internal_accessibility_pre_audit"].source_bindings[0],
        coordinate=accessibility_coordinate,
        content_digest=accessibility_digest,
        source_state=(
            SourceClaimState.SUPPORTED
            if accessibility_document is not None
            else SourceClaimState.BLOCKED
        ),
        subject="historical_internal_accessibility_pre_audit",
        family="accessibility",
        allowed_purposes=allowed_accessibility_purposes,
        denied_purposes=denied_accessibility_purposes,
        owner=accessibility_owner,
        jurisdiction=None,
        jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
        review_on=accessibility_source_as_of,
        review_due=accessibility_review_due,
        source_as_of=accessibility_source_as_of,
        evidence=historical_evidence,
        limitation_refs=(historical_limitation,),
        predicate_facts=historical_facts,
    )

    blocked_owner = OwnerBinding(
        owner="team-design",
        basis="closure_commitment",
        source_ref=identity.path,
        establishment_class=EstablishmentClass.RECOMPUTED,
    )
    if page_receipt is None:
        current_coordinate = accessibility_coordinate
        current_digest = unavailable_digest
        current_date = None
        current_limitation = "Current page-accessibility evidence is unavailable."
    else:
        current_coordinate = accessibility_coordinate.model_copy(
            update={
                "path": f"{page_receipt.path}/receipt.json",
                "symbol": "page_a11y_receipt",
            }
        )
        current_digest = page_receipt.content_digest
        current_date = page_receipt.source_as_of
        current_limitation = (
            "Current accessibility conformance is blocked by the admitted failing page suite."
        )
    _validate_exact_fixed_binding(
        rows["current_accessibility_conformance"].source_bindings[0],
        coordinate=current_coordinate,
        content_digest=current_digest,
        source_state=SourceClaimState.BLOCKED,
        subject="current_accessibility_conformance",
        family="accessibility",
        allowed_purposes=("historical_page_accessibility_result",),
        denied_purposes=("current_accessibility_conformance",),
        owner=blocked_owner,
        jurisdiction=None,
        jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
        review_on=current_date,
        review_due=current_date,
        source_as_of=current_date,
        evidence=None,
        limitation_refs=(current_limitation,),
        predicate_facts={"identity_boundary"},
    )
    _validate_exact_fixed_binding(
        rows["external_accessibility_certification"].source_bindings[0],
        coordinate=accessibility_coordinate,
        content_digest=accessibility_digest,
        source_state=SourceClaimState.BLOCKED,
        subject="external_accessibility_certification",
        family="accessibility",
        allowed_purposes=allowed_accessibility_purposes,
        denied_purposes=tuple(
            sorted(
                {
                    *denied_accessibility_purposes,
                    "external_accessibility_certification",
                }
            )
        ),
        owner=blocked_owner,
        jurisdiction=None,
        jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
        review_on=accessibility_source_as_of,
        review_due=accessibility_review_due,
        source_as_of=accessibility_source_as_of,
        evidence=None,
        limitation_refs=("External accessibility countersign is absent.",),
        prerequisite_refs=("DS11-EXTERNAL-A11Y-COUNTERSIGN",),
        predicate_facts={"identity_boundary"},
    )
    _validate_exact_fixed_binding(
        rows["grounded_performance"].source_bindings[0],
        coordinate=identity_coordinate,
        content_digest=identity.content_digest,
        source_state=SourceClaimState.BLOCKED,
        subject="grounded_performance",
        family="grounded_performance",
        allowed_purposes=(),
        denied_purposes=("grounded_performance",),
        owner=OwnerBinding(
            owner="team-runtime",
            basis="closure_commitment",
            source_ref=identity.path,
            establishment_class=EstablishmentClass.RECOMPUTED,
        ),
        jurisdiction="non_jurisdiction_specific",
        jurisdiction_establishment=EstablishmentClass.RECOMPUTED,
        review_on=identity.last_reviewed,
        review_due=review_due,
        source_as_of=identity.last_reviewed,
        evidence=None,
        limitation_refs=("No governed grounded-performance evidence is admitted.",),
        predicate_facts={
            "content_bound_source",
            "accountable_owner",
            "applicable_jurisdiction",
            "current_review",
            "identity_boundary",
        },
    )


def _sort_source_bindings(
    bindings: Sequence[ClaimSourceBinding],
) -> tuple[ClaimSourceBinding, ...]:
    return tuple(
        sorted(
            bindings,
            key=lambda item: (
                item.coordinate.path,
                item.coordinate.line,
                item.coordinate.column,
                item.subject or "",
            ),
        )
    )


def _expected_source_bindings(
    inventory: Sequence[SourceInventoryRow],
) -> tuple[ClaimSourceBinding, ...]:
    bindings: list[ClaimSourceBinding] = []
    for row in inventory:
        owner = OwnerBinding(
            owner=None,
            basis="not_established",
            source_ref=None,
            establishment_class=EstablishmentClass.NOT_ESTABLISHED,
        )
        if row.resolution == SourceResolution.AMBIGUOUS:
            coordinates = (
                row.declaration_coordinates or row.carrier_coordinates or row.consumer_coordinates
            )
            if coordinates:
                bindings.append(_expected_unresolved_binding(row, coordinates[0], owner))
            continue
        denied = tuple(sorted({value for site in row.forbidden_sites for value in site.values}))
        metadata_by_key = {
            (item.source_symbol, item.subject): item for item in row.producer_metadata
        }
        emitted = False
        for site in row.authoritative_sites:
            if site.resolution == SourceResolution.RESOLVED:
                for subject in site.values:
                    emitted = True
                    metadata = metadata_by_key.get((site.coordinate.symbol, subject))
                    bindings.append(
                        _expected_resolved_source_binding(
                            row,
                            site.coordinate,
                            subject,
                            denied,
                            metadata,
                            owner,
                        )
                    )
            else:
                bindings.append(_expected_unresolved_binding(row, site.coordinate, owner))
                emitted = True
        if not emitted and row.resolution in {
            SourceResolution.RUNTIME_BOUND,
            SourceResolution.AMBIGUOUS,
        }:
            coordinates = (
                row.declaration_coordinates or row.carrier_coordinates or row.consumer_coordinates
            )
            if coordinates:
                bindings.append(_expected_unresolved_binding(row, coordinates[0], owner))
    return _sort_source_bindings(bindings)


def _expected_resolved_source_binding(
    row: SourceInventoryRow,
    coordinate: SourceCoordinate,
    subject: str,
    denied: tuple[str, ...],
    metadata: ProducerPostureMetadata | None,
    default_owner: OwnerBinding,
) -> ClaimSourceBinding:
    if metadata is None:
        owner = default_owner
        source_state = SourceClaimState.NOT_ESTABLISHED
        limitations = ("Missing independent claim metadata",)
        prerequisites: tuple[str, ...] = ()
        closure_signal = None
        predicates = _expected_unestablished_predicates(owner)
    else:
        owner = OwnerBinding(
            owner=metadata.owner,
            basis="closure_commitment",
            source_ref=row.path,
            establishment_class=EstablishmentClass.RECOMPUTED,
        )
        source_state = SourceClaimState(metadata.source_state)
        limitations = tuple(
            dict.fromkeys(
                (
                    "Producer metadata authorizes planning only; support evidence is absent.",
                    *metadata.limitation_refs,
                )
            )
        )
        prerequisites = metadata.prerequisite_refs
        closure_signal = metadata.closure_signal
        predicates = _expected_planned_predicates(owner)
    return ClaimSourceBinding(
        coordinate=coordinate,
        content_digest=row.content_digest,
        resolution=SourceResolution.RESOLVED,
        source_state=source_state,
        subject=subject,
        family="methodology",
        authoritative_for=(subject,),
        may_not_use_for=denied,
        authority_purpose=subject,
        owner=owner,
        jurisdiction=None,
        jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
        review_on=None,
        review_due=None,
        source_as_of=None,
        evidence_refs=(),
        evidence_bindings=(),
        limitation_refs=limitations,
        prerequisite_refs=prerequisites,
        identity_boundary_ref=RATIFIED_IDENTITY_PATH,
        declared_scope_assumption=None,
        supersedes_ref=None,
        superseded_by_ref=None,
        predicates=predicates,
        closure_signal=closure_signal,
    )


def _expected_unresolved_binding(
    row: SourceInventoryRow,
    coordinate: SourceCoordinate,
    owner: OwnerBinding,
) -> ClaimSourceBinding:
    return ClaimSourceBinding(
        coordinate=coordinate,
        content_digest=row.content_digest,
        resolution=row.resolution,
        source_state=SourceClaimState.BLOCKED,
        subject=None,
        family="methodology",
        authoritative_for=(),
        may_not_use_for=tuple(
            sorted({value for site in row.forbidden_sites for value in site.values})
        ),
        authority_purpose=None,
        owner=owner,
        jurisdiction=None,
        jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
        review_on=None,
        review_due=None,
        source_as_of=None,
        evidence_refs=(),
        evidence_bindings=(),
        limitation_refs=("Unresolved source declaration",),
        prerequisite_refs=(),
        identity_boundary_ref=RATIFIED_IDENTITY_PATH,
        declared_scope_assumption=None,
        supersedes_ref=None,
        superseded_by_ref=None,
        predicates=_expected_unestablished_predicates(owner),
        closure_signal=None,
    )


def _expected_unestablished_predicates(
    owner: OwnerBinding,
) -> tuple[SupportPredicate, ...]:
    values = [
        SupportPredicate(
            kind=kind,
            satisfied=True,
            establishment_class=EstablishmentClass.RECOMPUTED,
            evidence_refs=(),
            issue_code=None,
        )
        for kind in (
            "content_bound_source",
            "purpose_permission",
            "identity_boundary",
            "no_blocker",
        )
    ]
    values.extend(
        (
            SupportPredicate(
                kind="accountable_owner",
                satisfied=owner.owner is not None,
                establishment_class=owner.establishment_class,
                evidence_refs=(owner.source_ref,) if owner.source_ref else (),
                issue_code="DS11-OWNER-NOT-ESTABLISHED",
            ),
            SupportPredicate(
                kind="applicable_jurisdiction",
                satisfied=False,
                establishment_class=EstablishmentClass.NOT_ESTABLISHED,
                evidence_refs=(),
                issue_code="DS11-JURISDICTION-NOT-ESTABLISHED",
            ),
            SupportPredicate(
                kind="current_review",
                satisfied=False,
                establishment_class=EstablishmentClass.NOT_ESTABLISHED,
                evidence_refs=(),
                issue_code="DS11-REVIEW-MISSING",
            ),
            SupportPredicate(
                kind="content_bound_evidence",
                satisfied=False,
                establishment_class=EstablishmentClass.NOT_ESTABLISHED,
                evidence_refs=(),
                issue_code="DS11-GATE-PREDICATE-NOT-ESTABLISHED",
            ),
        )
    )
    return tuple(sorted(values, key=lambda item: item.kind))


def _expected_planned_predicates(owner: OwnerBinding) -> tuple[SupportPredicate, ...]:
    planned = set(REQUIRED_PLANNED_PREDICATES)
    issues = {
        "content_bound_source": "DS11-SOURCE-CONTENT-NOT-BOUND",
        "purpose_permission": "DS11-AUTHORITY-PURPOSE-DENIED",
        "accountable_owner": "DS11-OWNER-NOT-ESTABLISHED",
        "applicable_jurisdiction": "DS11-JURISDICTION-NOT-ESTABLISHED",
        "current_review": "DS11-REVIEW-MISSING",
        "content_bound_evidence": "DS11-EVIDENCE-NOT-INDEPENDENTLY-BOUND",
        "identity_boundary": "DS11-IDENTITY-BOUNDARY-NOT-ESTABLISHED",
        "no_blocker": "DS11-SOURCE-BLOCKER-PRESENT",
    }
    return tuple(
        SupportPredicate(
            kind=kind,
            satisfied=kind in planned,
            establishment_class=(
                EstablishmentClass.RECOMPUTED
                if kind in planned
                else EstablishmentClass.NOT_ESTABLISHED
            ),
            evidence_refs=(owner.source_ref,)
            if kind == "accountable_owner" and owner.source_ref
            else (),
            issue_code=None if kind in planned else issue,
        )
        for kind, issue in sorted(issues.items())
    )


def _payload_digest(register: ClaimPostureRegisterV1) -> str:
    payload = register.model_dump(mode="json", exclude={"payload_digest"})
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
