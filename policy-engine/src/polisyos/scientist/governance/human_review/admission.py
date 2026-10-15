"""Fail-closed resolution of human-review evidence for release projections.

The existing review packet and decision DTOs are candidates until the exact
decision subject and a trusted reviewer signature are resolved. This module
verifies those source bindings and records the institutional facts that remain
unestablished; it does not appoint reviewers or infer review authority from a
packet field.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from polisyos.core.artifacts.canonical_profile import load_core_json_artifact
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.signing import (
    Ed25519Verifier,
    SignatureVerificationResult,
    SignatureVerificationStatus,
)
from polisyos.scientist.governance.human_review.decisions import (
    HUMAN_REVIEW_DECISION_KIND,
    HUMAN_REVIEW_DECISION_SCHEMA_NAME,
    HUMAN_REVIEW_DECISION_SCHEMA_VERSION,
)
from polisyos.scientist.governance.human_review.models import (
    HumanReviewDecision,
    HumanReviewPacket,
    ReviewAssignmentStatus,
    ReviewRiskTier,
)
from polisyos.scientist.governance.human_review.packets import (
    HUMAN_REVIEW_PACKET_KIND,
    HUMAN_REVIEW_PACKET_SCHEMA_NAME,
    HUMAN_REVIEW_PACKET_SCHEMA_VERSION,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore


class _SignatureVerifyingStore(Protocol):
    """Optional CAS signature capability used by the admission resolver."""

    def verify_signature(
        self,
        artifact_id: ArtifactRef,
        verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult: ...


_DECISION_PACKET_KIND = "scientist.decision_packet"
_DECISION_PACKET_SCHEMA_NAME = "polisyos.scientist.DecisionPacket"
_DECISION_PACKET_SCHEMA_VERSION = "3.4"

_PUBLIC_CUSTODY_LIMITATIONS = (
    "reviewer_appointment_authority_not_established",
    "review_decision_currentness_not_established",
    "reviewer_assignment_issuer_not_established",
    "review_duration_source_not_established",
)


class HumanReviewAdmissionStatus(StrEnum):
    """Outcome of resolving review artifacts against the current decision."""

    ADMITTED = "admitted"
    NOT_ESTABLISHED = "not_established"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class HumanReviewAdmission:
    """Resolved review evidence plus explicit custody limitations.

    This is candidate evidence, not an authority-bearing capability. The
    current source contract has no authenticated reviewer appointment,
    currentness, or review-duration source, so no instance can currently
    establish protected release authority. Valid CAS signatures alone
    intentionally remain held.
    """

    status: HumanReviewAdmissionStatus
    review_packet: HumanReviewPacket | None
    decision: HumanReviewDecision | None
    review_packet_ref: ArtifactRef | None
    review_decision_ref: ArtifactRef | None
    decision_packet_ref: ArtifactRef | None
    signature_verification: SignatureVerificationResult | None
    violations: tuple[str, ...]

    @property
    def public_status(self) -> HumanReviewAdmissionStatus:
        """Return the effective authority status supported by current inputs.

        ``status`` is a resolver diagnostic and can be copied or constructed by
        callers. Until authenticated appointment and currentness sources are
        part of this intake, it must not be projected as release authority.
        """

        return HumanReviewAdmissionStatus.NOT_ESTABLISHED

    @property
    def is_admitted(self) -> bool:
        """Return whether current source inputs can establish reviewer authority.

        The resolver currently has no authenticated reviewer appointment or
        currentness source. Its output therefore cannot authorize release,
        regardless of a caller-constructed or copied diagnostic status.
        """

        return False

    def binds(
        self,
        *,
        review_packet_ref: ArtifactRef | None,
        review_decision_ref: ArtifactRef | None,
    ) -> bool:
        """Check the result still selects the exact refs supplied to a consumer."""

        if (
            not self.is_admitted
            or self.review_packet_ref is None
            or self.review_decision_ref is None
            or review_packet_ref is None
            or review_decision_ref is None
        ):
            return False
        return artifact_ref_identity_key(self.review_packet_ref) == artifact_ref_identity_key(
            review_packet_ref
        ) and artifact_ref_identity_key(self.review_decision_ref) == artifact_ref_identity_key(
            review_decision_ref
        )

    def projection(self) -> dict[str, Any]:
        """Return a held custody projection and clearly labeled diagnostics."""

        return {
            "status": self.public_status.value,
            "candidate_status": self.status.value,
            "violations": sorted({*self.violations, *_PUBLIC_CUSTODY_LIMITATIONS}),
            "candidate_signature_status": (
                self.signature_verification.status.value
                if self.signature_verification is not None
                else None
            ),
            "candidate_signer_identity": (
                self.signature_verification.signer_identity
                if self.signature_verification is not None
                else None
            ),
        }


def resolve_human_review_admission(
    store: ArtifactStore,
    *,
    review_packet_ref: ArtifactRef | None,
    review_decision_ref: ArtifactRef | None,
    decision_packet_ref: ArtifactRef | None,
    run_id: str,
    context_run_id: str,
    execution_profile: str | None,
    minimum_time_spent_seconds: int,
    expected_risk_tier: ReviewRiskTier | None = None,
    verifier: Ed25519Verifier | None = None,
) -> HumanReviewAdmission:
    """Resolve selected review artifacts against the exact current decision.

    This performs content/profile and CAS-signature verification when the
    caller supplies a scoped verifier. Missing reviewer appointment,
    institutional currentness, and required duration evidence remain typed
    limitations; a CAS signature alone does not supply those facts.
    """

    violations: list[str] = []
    signature_verification: SignatureVerificationResult | None = None
    packet: HumanReviewPacket | None = None
    decision: HumanReviewDecision | None = None
    rejections: list[str] = []

    if not run_id or not context_run_id:
        violations.append("review_run_context_not_established")
    elif run_id != context_run_id:
        rejections.append("review_context_run_id_mismatch")
    if review_packet_ref is None:
        violations.append("human_review_packet_ref_not_established")
    if review_decision_ref is None:
        violations.append("human_review_decision_ref_not_established")
    if decision_packet_ref is None:
        violations.append("reviewed_decision_packet_ref_not_established")
    if not execution_profile:
        violations.append("execution_profile_not_established")
    if minimum_time_spent_seconds < 0:
        rejections.append("minimum_review_duration_invalid")

    if review_packet_ref is not None:
        error = _validate_selected_ref(
            store,
            review_packet_ref,
            expected_kind=HUMAN_REVIEW_PACKET_KIND,
            expected_schema_name=HUMAN_REVIEW_PACKET_SCHEMA_NAME,
            expected_schema_version=HUMAN_REVIEW_PACKET_SCHEMA_VERSION,
        )
        if error is not None:
            rejections.append(error)
        else:
            try:
                packet = HumanReviewPacket.model_validate(
                    load_core_json_artifact(store, review_packet_ref)
                )
            except Exception:
                rejections.append("human_review_packet_content_invalid")

    if review_decision_ref is not None:
        error = _validate_selected_ref(
            store,
            review_decision_ref,
            expected_kind=HUMAN_REVIEW_DECISION_KIND,
            expected_schema_name=HUMAN_REVIEW_DECISION_SCHEMA_NAME,
            expected_schema_version=HUMAN_REVIEW_DECISION_SCHEMA_VERSION,
        )
        if error is not None:
            rejections.append(error)
        else:
            try:
                decision = HumanReviewDecision.model_validate(
                    load_core_json_artifact(store, review_decision_ref)
                )
            except Exception:
                rejections.append("human_review_decision_content_invalid")

    if decision_packet_ref is not None:
        error = _validate_selected_ref(
            store,
            decision_packet_ref,
            expected_kind=_DECISION_PACKET_KIND,
            expected_schema_name=_DECISION_PACKET_SCHEMA_NAME,
            expected_schema_version=_DECISION_PACKET_SCHEMA_VERSION,
        )
        if error is not None:
            rejections.append(error)
        else:
            try:
                decision_payload = load_core_json_artifact(store, decision_packet_ref)
            except Exception:
                rejections.append("reviewed_decision_packet_content_invalid")
            else:
                _validate_decision_context(
                    decision_payload,
                    run_id=run_id,
                    execution_profile=execution_profile,
                    rejections=rejections,
                    violations=violations,
                )

    if packet is not None and decision is not None:
        if packet.run_id != run_id or decision.run_id != run_id:
            rejections.append("human_review_run_id_mismatch")
        if packet.packet_id != decision.packet_id:
            rejections.append("human_review_packet_id_mismatch")
        if decision.packet_ref is None or review_packet_ref is None:
            violations.append("human_review_decision_packet_ref_not_established")
        elif not _same_ref(decision.packet_ref, review_packet_ref):
            rejections.append("human_review_decision_packet_ref_mismatch")
        if decision_packet_ref is None or packet.decision_packet_ref is None:
            violations.append("human_review_subject_ref_not_established")
        elif not _same_ref(packet.decision_packet_ref, decision_packet_ref):
            rejections.append("human_review_subject_ref_mismatch")
        _validate_reviewer_assignment(packet, decision, violations, rejections)

    if (
        packet is not None
        and expected_risk_tier is not None
        and packet.risk_tier is not expected_risk_tier
    ):
        rejections.append("human_review_risk_tier_binding_mismatch")

    if decision is not None and review_decision_ref is not None:
        signature_verification, signature_violation, signature_rejection = (
            _verify_reviewer_signature(
                store,
                review_decision_ref,
                decision,
                verifier=verifier,
            )
        )
        if signature_violation is not None:
            violations.append(signature_violation)
        if signature_rejection is not None:
            rejections.append(signature_rejection)

    # These institutional predicates have no authenticated source in the
    # current intake. Do not derive them from caller-controlled packet fields.
    violations.append("reviewer_appointment_authority_not_established")
    violations.append("review_decision_currentness_not_established")
    if minimum_time_spent_seconds > 0:
        violations.append("review_duration_evidence_not_established")

    if rejections:
        status = HumanReviewAdmissionStatus.REJECTED
        violations.extend(rejections)
    else:
        status = HumanReviewAdmissionStatus.NOT_ESTABLISHED

    return HumanReviewAdmission(
        status=status,
        review_packet=packet,
        decision=decision,
        review_packet_ref=review_packet_ref,
        review_decision_ref=review_decision_ref,
        decision_packet_ref=decision_packet_ref,
        signature_verification=signature_verification,
        violations=tuple(sorted(set(violations))),
    )


def _validate_selected_ref(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    expected_kind: str,
    expected_schema_name: str,
    expected_schema_version: str,
) -> str | None:
    """Validate the selected CAS view's identity, kind, media, and schema."""

    if ref.kind != expected_kind or ref.media_type != "application/json":
        return "human_review_artifact_abi_mismatch"
    try:
        manifest = store.get_manifest(ref)
    except Exception:
        return "human_review_artifact_manifest_unavailable"
    if (
        str(manifest.artifact_id) != str(ref.artifact_id)
        or manifest.kind != expected_kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != expected_schema_name
        or manifest.artifact_schema.version != expected_schema_version
    ):
        return "human_review_artifact_abi_mismatch"
    selected_ref = ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    if artifact_ref_identity_key(selected_ref) != artifact_ref_identity_key(ref):
        return "human_review_artifact_selected_view_mismatch"
    return None


def _validate_decision_context(
    payload: object,
    *,
    run_id: str,
    execution_profile: str | None,
    rejections: list[str],
    violations: list[str],
) -> None:
    """Match source packet run and execution profile to selected context."""

    if not isinstance(payload, Mapping):
        rejections.append("reviewed_decision_packet_content_invalid")
        return
    if payload.get("run_id") != run_id:
        rejections.append("reviewed_decision_packet_run_id_mismatch")
    runtime_contracts = payload.get("runtime_contracts")
    actual_profile = (
        runtime_contracts.get("execution_profile")
        if isinstance(runtime_contracts, Mapping)
        else None
    )
    if not execution_profile or not actual_profile:
        violations.append("reviewed_decision_execution_profile_not_established")
    elif actual_profile != execution_profile:
        rejections.append("reviewed_decision_execution_profile_mismatch")


def _validate_reviewer_assignment(
    packet: HumanReviewPacket,
    decision: HumanReviewDecision,
    violations: list[str],
    rejections: list[str],
) -> None:
    """Check candidate assignment consistency without granting it authority."""

    if not packet.assignments:
        violations.append("reviewer_assignment_not_established")
        return
    matching = [item for item in packet.assignments if item.reviewer_id == decision.reviewer_id]
    if not matching:
        rejections.append("reviewer_not_assigned_to_packet")
        return
    if len(matching) != 1 or matching[0].role is not decision.signature.role:
        rejections.append("reviewer_assignment_role_mismatch")
        return
    assignment = matching[0]
    if assignment.status is ReviewAssignmentStatus.CANCELLED:
        rejections.append("reviewer_assignment_cancelled")
    elif assignment.status is not ReviewAssignmentStatus.COMPLETED:
        violations.append("reviewer_assignment_not_completed")
    violations.append("reviewer_assignment_issuer_not_established")


def _verify_reviewer_signature(
    store: ArtifactStore,
    decision_ref: ArtifactRef,
    decision: HumanReviewDecision,
    *,
    verifier: Ed25519Verifier | None,
) -> tuple[
    SignatureVerificationResult | None,
    str | None,
    str | None,
]:
    """Verify the selected decision artifact's CAS signature if a scoped keyring exists."""

    if verifier is None:
        return None, "reviewer_signature_verifier_not_established", None
    verify = getattr(store, "verify_signature", None)
    if not callable(verify):
        return None, "cas_signature_verification_unavailable", None
    try:
        result = cast("_SignatureVerifyingStore", store).verify_signature(
            decision_ref,
            verifier,
            strict_identity=True,
        )
    except Exception:
        return None, "cas_signature_verification_failed", None
    if result.status is SignatureVerificationStatus.VALID:
        if result.expected_identity != decision.reviewer_id:
            return result, None, "reviewer_signature_identity_not_bound"
        if result.signer_identity != decision.reviewer_id:
            return result, None, "reviewer_signature_identity_mismatch"
        return result, None, None
    if result.status in {
        SignatureVerificationStatus.INVALID,
        SignatureVerificationStatus.REVOKED,
    }:
        return result, None, "reviewer_cas_signature_invalid_or_revoked"
    if result.status is SignatureVerificationStatus.UNTRUSTED:
        return result, "reviewer_cas_signing_key_not_trusted", None
    if result.status is SignatureVerificationStatus.UNSIGNED:
        return result, "reviewer_decision_cas_signature_missing", None
    return result, "reviewer_cas_signature_verification_not_established", None


def _same_ref(left: ArtifactRef, right: ArtifactRef) -> bool:
    return artifact_ref_identity_key(left) == artifact_ref_identity_key(right)
