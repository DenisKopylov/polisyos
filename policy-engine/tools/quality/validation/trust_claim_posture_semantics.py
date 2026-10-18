"""Owner for extracted DS11 trust-claim posture logic."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.scientist.evidence.claims.posture import (
    CUSTODY_APPOINTMENT_SOURCE_PATH,
    RATIFIED_IDENTITY_CONTENT_DIGEST,
    AccessibilityDocumentBinding,
    AdmittedSourceMember,
    AdmittedVerifier,
    ClaimPostureRegisterV1,
    ClaimSourceBinding,
    CustodyAppointmentSource,
    CustodyAppointmentStatus,
    EstablishmentClass,
    EvidenceBinding,
    IdentityBoundaryBinding,
    OwnerBinding,
    PageA11yReceiptBinding,
    SourceClaimState,
    SourceCoordinate,
    SourceResolution,
    SupportPredicate,
    build_posture_register,
    canonical_register_bytes,
    derive_admitted_verifiers,
    validate_posture_register,
)
from tools.quality.validation.trust_claim_posture_sources import (
    compile_source_claim_bindings,
    derive_ast_sources,
)


@dataclass(frozen=True, slots=True)
class SemanticDependencies:
    """Bind this owner to the active facade collaborators."""

    admitted_is_dir: Callable[..., Any]
    admitted_is_file: Callable[..., Any]
    admitted_read_bytes: Callable[..., Any]
    reject_owner_predicate: Callable[..., Any]
    require_contained_path: Callable[..., Any]
    derive_accessibility_document: Callable[..., Any]
    derive_custody_appointments: Callable[..., Any]
    derive_identity_boundary: Callable[..., Any]
    derive_page_a11y_receipt: Callable[..., Any]
    derive_token_sources: Callable[..., Any]
    reconcile_source_derivations: Callable[..., Any]
    a11y_path: Path
    default_register_as_of: date
    identity_path: Path
    output_path: Path
    page_receipt_path: Path


if TYPE_CHECKING:
    from tools.quality.validation.trust_claim_posture_contracts import (
        CustodyAppointment,
    )


def _semantic_predicates(
    *, satisfied: set[str], evidence_refs: tuple[str, ...], dependencies: SemanticDependencies
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
            issue_code=None if kind in satisfied else issues[kind],
        )
        for kind in sorted(issues)
    )


def _semantic_evidence(
    *,
    subject: str,
    verifier: AdmittedVerifier,
    source_as_of: date,
    establishment_class: EstablishmentClass = EstablishmentClass.RECOMPUTED,
    dependencies: SemanticDependencies,
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


def _semantic_binding(
    *,
    coordinate: SourceCoordinate,
    content_digest: str,
    source_state: SourceClaimState,
    subject: str,
    family: str,
    authoritative_for: tuple[str, ...],
    may_not_use_for: tuple[str, ...],
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
    dependencies: SemanticDependencies,
) -> ClaimSourceBinding:
    evidence_bindings = () if evidence is None else (evidence,)
    evidence_refs = () if evidence is None else (evidence.ref,)
    return ClaimSourceBinding(
        coordinate=coordinate,
        content_digest=content_digest,
        resolution=SourceResolution.RESOLVED,
        source_state=source_state,
        subject=subject,
        family=family,
        authoritative_for=authoritative_for,
        may_not_use_for=may_not_use_for,
        authority_purpose=subject,
        owner=owner,
        jurisdiction=jurisdiction,
        jurisdiction_establishment=jurisdiction_establishment,
        review_on=review_on,
        review_due=review_due,
        source_as_of=source_as_of,
        evidence_refs=evidence_refs,
        evidence_bindings=evidence_bindings,
        limitation_refs=limitation_refs,
        prerequisite_refs=prerequisite_refs,
        identity_boundary_ref=dependencies.identity_path.as_posix(),
        declared_scope_assumption=None,
        supersedes_ref=None,
        superseded_by_ref=None,
        predicates=_semantic_predicates(
            satisfied=predicate_facts or set(),
            evidence_refs=evidence_refs,
        ),
        closure_signal=closure_signal,
    )


def _compile_semantic_bindings(
    *,
    identity: IdentityBoundaryBinding,
    custody_appointments: Sequence[CustodyAppointment],
    accessibility_document: AccessibilityDocumentBinding | None,
    page_receipt: PageA11yReceiptBinding | None,
    dependencies: SemanticDependencies,
) -> tuple[ClaimSourceBinding, ...]:
    """Produce the fixed C02 posture rows from admitted typed facts."""
    verifiers = derive_admitted_verifiers(
        identity_boundary=identity,
        accessibility_document=accessibility_document,
        page_a11y_receipt=page_receipt,
    )
    verifier_by_kind = {item.verifier_kind: item for item in verifiers}
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
    identity_is_exact_ratified_source = identity.content_digest == RATIFIED_IDENTITY_CONTENT_DIGEST
    review_due = identity.last_reviewed + timedelta(days=365)
    complete_facts = {
        "content_bound_source",
        "purpose_permission",
        "accountable_owner",
        "applicable_jurisdiction",
        "current_review",
        "content_bound_evidence",
        "identity_boundary",
        "no_blocker",
    }
    identity_evidence = _semantic_evidence(
        subject="system_identity",
        verifier=identity_verifier,
        source_as_of=identity.last_reviewed,
        establishment_class=EstablishmentClass.INDEPENDENTLY_RECONCILED,
    )
    bindings: list[ClaimSourceBinding] = [
        _semantic_binding(
            coordinate=identity_coordinate,
            content_digest=identity.content_digest,
            source_state=(
                SourceClaimState.SUPPORTED
                if identity_is_exact_ratified_source
                else SourceClaimState.BLOCKED
            ),
            subject="system_identity",
            family="methodology",
            authoritative_for=identity.authoritative_for,
            may_not_use_for=identity.may_not_use_for,
            owner=identity_owner,
            jurisdiction="non_jurisdiction_specific",
            jurisdiction_establishment=EstablishmentClass.RECOMPUTED,
            review_on=identity.last_reviewed,
            review_due=review_due,
            source_as_of=identity.last_reviewed,
            evidence=identity_evidence,
            limitation_refs=(
                "Bounded to non-jurisdiction-specific system identity."
                if identity_is_exact_ratified_source
                else "System identity source differs from the ratified byte boundary.",
            ),
            predicate_facts=(
                complete_facts
                if identity_is_exact_ratified_source
                else complete_facts - {"no_blocker"}
            ),
        )
    ]

    custody_facts = {
        "content_bound_source",
        "purpose_permission",
        "accountable_owner",
        "identity_boundary",
    }
    for appointment in custody_appointments:
        if appointment.status == CustodyAppointmentStatus.OPEN:
            custody_state = SourceClaimState.PLANNED
            custody_limitation = f"Planned prerequisite: {appointment.debt_id}"
        elif appointment.status == CustodyAppointmentStatus.BLOCKED:
            custody_state = SourceClaimState.BLOCKED
            custody_limitation = f"Blocked prerequisite: {appointment.debt_id}"
        else:
            custody_state = SourceClaimState.BLOCKED
            custody_limitation = (
                f"Closed appointment lacks an admitted closure receipt: {appointment.debt_id}"
            )
        bindings.append(
            _semantic_binding(
                coordinate=identity_coordinate,
                content_digest=identity.content_digest,
                source_state=(
                    custody_state if identity_is_exact_ratified_source else SourceClaimState.BLOCKED
                ),
                subject="universal_custody_commitment",
                family="custody",
                authoritative_for=("universal_custody_commitment",),
                may_not_use_for=identity.may_not_use_for,
                owner=OwnerBinding(
                    owner=appointment.owner,
                    basis="closure_commitment",
                    source_ref=appointment.source_ref,
                    establishment_class=EstablishmentClass.RECOMPUTED,
                ),
                jurisdiction="non_jurisdiction_specific",
                jurisdiction_establishment=EstablishmentClass.RECOMPUTED,
                review_on=identity.last_reviewed,
                review_due=review_due,
                source_as_of=identity.last_reviewed,
                evidence=None,
                limitation_refs=(custody_limitation,),
                prerequisite_refs=(appointment.debt_id,),
                closure_signal=appointment.closure_signal,
                predicate_facts=custody_facts,
            )
        )

    unavailable_digest = "sha256:" + "0" * 64
    a11y_path = dependencies.a11y_path.as_posix()
    a11y_coordinate = SourceCoordinate(
        path=a11y_path,
        symbol="ds11_projection_index",
        line=1,
        column=0,
        field_name="authoritative_for",
        use_kind="declaration",
    )
    if accessibility_document is not None:
        selector_values = {item.key: item.value for item in accessibility_document.bindings}
        a11y_owner = OwnerBinding(
            owner=selector_values.get("assessment_owner"),
            basis="ratified_document",
            source_ref=accessibility_document.path,
            establishment_class=EstablishmentClass.RECOMPUTED,
        )
        a11y_verifier = verifier_by_kind["accessibility_document_derivation"]
        historical_evidence = _semantic_evidence(
            subject="historical_internal_accessibility_pre_audit",
            verifier=a11y_verifier,
            source_as_of=accessibility_document.source_as_of,
        )
        a11y_authoritative = tuple(
            item.purpose for item in accessibility_document.authoritative_for
        )
        a11y_denied = tuple(item.purpose for item in accessibility_document.may_not_use_for)
        historical_facts = complete_facts - {"applicable_jurisdiction"}
        a11y_digest = accessibility_document.content_digest
        a11y_source_as_of = accessibility_document.source_as_of
        a11y_review_due = accessibility_document.source_as_of + timedelta(days=365)
    else:
        a11y_owner = OwnerBinding(
            owner=None,
            basis="not_established",
            source_ref=None,
            establishment_class=EstablishmentClass.NOT_ESTABLISHED,
        )
        historical_evidence = None
        a11y_authoritative = ()
        a11y_denied = (
            "current_accessibility_conformance",
            "external_accessibility_certification",
        )
        historical_facts = {"identity_boundary"}
        a11y_digest = unavailable_digest
        a11y_source_as_of = None
        a11y_review_due = None
    bindings.append(
        _semantic_binding(
            coordinate=a11y_coordinate,
            content_digest=a11y_digest,
            source_state=(
                SourceClaimState.SUPPORTED
                if accessibility_document is not None
                else SourceClaimState.BLOCKED
            ),
            subject="historical_internal_accessibility_pre_audit",
            family="accessibility",
            authoritative_for=a11y_authoritative,
            may_not_use_for=a11y_denied,
            owner=a11y_owner,
            jurisdiction=None,
            jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
            review_on=a11y_source_as_of,
            review_due=a11y_review_due,
            source_as_of=a11y_source_as_of,
            evidence=historical_evidence,
            limitation_refs=(
                "Historical internal pre-audit only; jurisdiction is not established."
                if accessibility_document is not None
                else "Accessibility document projection basis is unavailable.",
            ),
            predicate_facts=historical_facts,
        )
    )

    if page_receipt is not None:
        current_evidence = None
        receipt_path = f"{page_receipt.path}/receipt.json"
        current_coordinate = a11y_coordinate.model_copy(
            update={"path": receipt_path, "symbol": "page_a11y_receipt"}
        )
        current_digest = page_receipt.content_digest
        current_date = page_receipt.source_as_of
    else:
        current_evidence = None
        current_coordinate = a11y_coordinate
        current_digest = unavailable_digest
        current_date = None
    blocked_owner = OwnerBinding(
        owner="team-design",
        basis="closure_commitment",
        source_ref=identity.path,
        establishment_class=EstablishmentClass.RECOMPUTED,
    )
    bindings.append(
        _semantic_binding(
            coordinate=current_coordinate,
            content_digest=current_digest,
            source_state=SourceClaimState.BLOCKED,
            subject="current_accessibility_conformance",
            family="accessibility",
            authoritative_for=("historical_page_accessibility_result",),
            may_not_use_for=("current_accessibility_conformance",),
            owner=blocked_owner,
            jurisdiction=None,
            jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
            review_on=current_date,
            review_due=current_date,
            source_as_of=current_date,
            evidence=current_evidence,
            limitation_refs=(
                "Current accessibility conformance is blocked by the admitted failing page suite."
                if page_receipt is not None
                else "Current page-accessibility evidence is unavailable.",
            ),
            predicate_facts={"identity_boundary"},
        )
    )
    bindings.append(
        _semantic_binding(
            coordinate=a11y_coordinate,
            content_digest=a11y_digest,
            source_state=SourceClaimState.BLOCKED,
            subject="external_accessibility_certification",
            family="accessibility",
            authoritative_for=a11y_authoritative,
            may_not_use_for=tuple(sorted({*a11y_denied, "external_accessibility_certification"})),
            owner=blocked_owner,
            jurisdiction=None,
            jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
            review_on=a11y_source_as_of,
            review_due=a11y_review_due,
            source_as_of=a11y_source_as_of,
            evidence=None,
            limitation_refs=("External accessibility countersign is absent.",),
            prerequisite_refs=("DS11-EXTERNAL-A11Y-COUNTERSIGN",),
            predicate_facts={"identity_boundary"},
        )
    )
    bindings.append(
        _semantic_binding(
            coordinate=identity_coordinate,
            content_digest=identity.content_digest,
            source_state=SourceClaimState.BLOCKED,
            subject="grounded_performance",
            family="grounded_performance",
            authoritative_for=(),
            may_not_use_for=("grounded_performance",),
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
    )
    return tuple(bindings)


def compile_claim_posture_register(
    repo_root: Path, *, register_as_of: date, dependencies: SemanticDependencies
) -> tuple[ClaimPostureRegisterV1, bytes]:
    """Compile, reconcile, assemble, validate, and canonically serialize live sources."""
    root = repo_root.resolve()
    token_result = dependencies.derive_token_sources(root)
    ast_result = derive_ast_sources(
        root,
        read_bytes=lambda path, admitted_root: dependencies.admitted_read_bytes(
            path,
            admitted_root,
            code="DS11-SOURCE-SET-CONTAINMENT",
            stage="ast_source_member_read",
            label="AST source member",
        ),
    )
    reconciled = dependencies.reconcile_source_derivations(ast_result, token_result)
    identity = dependencies.derive_identity_boundary(root)
    custody_appointments = dependencies.derive_custody_appointments(root)
    source_bindings = compile_source_claim_bindings(reconciled, package_owners={})
    identity_member = AdmittedSourceMember(
        path=identity.path,
        content_digest=identity.content_digest,
    )
    accessibility_document = None
    accessibility_members: tuple[AdmittedSourceMember, ...] = ()
    accessibility_path = root / dependencies.a11y_path
    if dependencies.admitted_is_file(
        accessibility_path,
        root,
        code="DS11-ACCESSIBILITY-CONTRACT",
        stage="accessibility_source_presence",
        label="accessibility document",
    ) and dependencies.admitted_read_bytes(
        accessibility_path,
        root,
        code="DS11-ACCESSIBILITY-CONTRACT",
        stage="accessibility_source_read",
        label="accessibility document",
    ).startswith(b"---\n"):
        accessibility_document = dependencies.derive_accessibility_document(root)
        accessibility_members = (
            AdmittedSourceMember(
                path=accessibility_document.path,
                content_digest=accessibility_document.content_digest,
            ),
        )
    page_receipt = None
    page_members: tuple[AdmittedSourceMember, ...] = ()
    page_present = dependencies.admitted_is_dir(
        root / dependencies.page_receipt_path,
        root,
        code="DS11-PAGE-A11Y-RECEIPT-CONTRACT",
        stage="page_a11y_root_presence",
        label="page-a11y receipt source",
    )
    if page_present:
        page_receipt = dependencies.derive_page_a11y_receipt(root)
        page_members = page_receipt.admitted_sources
    semantic_bindings = _compile_semantic_bindings(
        identity=identity,
        custody_appointments=custody_appointments,
        accessibility_document=accessibility_document,
        page_receipt=page_receipt,
    )
    register = build_posture_register(
        register_as_of=register_as_of,
        admitted_sources=(
            *reconciled.admitted_sources,
            identity_member,
            *accessibility_members,
            *page_members,
        ),
        ast_derivation=ast_result.receipt,
        token_derivation=token_result.receipt,
        may_not_use_for_denied_only_sites=reconciled.may_not_use_for_denied_only_sites,
        identity_boundary=identity,
        custody_appointment_sources=tuple(
            CustodyAppointmentSource(
                path=CUSTODY_APPOINTMENT_SOURCE_PATH,
                debt_id=item.debt_id,
                status=item.status,
                source_content=item.source_content,
                content_digest="sha256:"
                + hashlib.sha256(item.source_content.encode("utf-8")).hexdigest(),
            )
            for item in custody_appointments
        ),
        accessibility_document=accessibility_document,
        page_a11y_receipt=page_receipt,
        source_inventory=reconciled.rows,
        source_bindings=(*source_bindings, *semantic_bindings),
    )
    payload = canonical_register_bytes(register)
    try:
        validate_posture_register(payload)
    except ValidationError:
        dependencies.reject_owner_predicate(
            "DS11-POSTURE-REGISTER-CONTRACT",
            "compiled_posture_typed_artifact",
            "compiled trust posture register violates its typed artifact schema",
        )
    return register, payload


def write_claim_posture_register(
    register: ClaimPostureRegisterV1, *, output_root: Path, dependencies: SemanticDependencies
) -> Path:
    """Write only the fixed generated target contained by ``output_root``."""
    root = output_root.resolve()
    target = (root / dependencies.output_path).resolve()
    dependencies.require_contained_path(
        target,
        root,
        code="DS11-GENERATED-FAMILY-CONTRACT",
        stage="generated_output_containment",
        label="generated output target",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_register_bytes(register))
    return target
