from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier, KeyPair
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.scientist.governance.human_review.admission import (
    HumanReviewAdmission,
    HumanReviewAdmissionStatus,
    resolve_human_review_admission,
)
from polisyos.scientist.governance.human_review.decisions import (
    human_review_status,
    persist_review_decision,
)
from polisyos.scientist.governance.human_review.models import (
    HumanReviewDecision,
    HumanReviewStatus,
    ReviewAction,
    ReviewAssignment,
    ReviewAssignmentStatus,
    ReviewerSignature,
)
from polisyos.scientist.governance.human_review.oversight_policy import (
    HumanReviewRequirement,
    evaluate_human_review_requirement,
    human_review_section,
    validate_human_reviewed_readiness,
)
from polisyos.scientist.governance.human_review.packets import (
    build_review_packet,
    persist_review_packet,
)


def _evidence(
    tmp_path: Path,
    *,
    signed: bool = True,
    assigned_reviewer_id: str = "reviewer_a",
    decision_packet_id: str | None = None,
    decision_run_id: str = "run_1",
    stale: bool = False,
) -> tuple[
    FileSystemCAS,
    ArtifactRef,
    ArtifactRef,
    ArtifactRef,
    Ed25519Verifier | None,
]:
    store = FileSystemCAS(tmp_path)
    decision_packet_ref = store.put_json(
        {
            "schema_version": "3.4",
            "run_id": "run_1",
            "runtime_contracts": {"execution_profile": "profile_1"},
        },
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.DecisionPacket", version="3.4"),
        ),
    )
    packet = build_review_packet(
        run_id="run_1",
        decision_packet_ref=decision_packet_ref,
    )
    assignment = ReviewAssignment(
        assignment_id="assignment_1",
        packet_id=packet.packet_id,
        reviewer_id="reviewer_a",
        status=ReviewAssignmentStatus.COMPLETED,
    )
    packet = packet.model_copy(
        update={
            "assignments": [assignment.model_copy(update={"reviewer_id": assigned_reviewer_id})],
            **({"created_at": datetime(2000, 1, 1, tzinfo=UTC)} if stale else {}),
        }
    )
    review_packet_ref = persist_review_packet(store, packet)
    decision = HumanReviewDecision(
        decision_id="decision_1",
        packet_id=decision_packet_id or packet.packet_id,
        run_id=decision_run_id,
        reviewer_id="reviewer_a",
        action=ReviewAction.APPROVE,
        rationale="Reviewed the selected decision packet.",
        signature=ReviewerSignature(
            reviewer_id="reviewer_a",
            attestation="I reviewed the selected decision packet.",
            signed_at=(datetime(2000, 1, 1, tzinfo=UTC) if stale else datetime.now(UTC)),
        ),
        decided_at=(datetime(2000, 1, 1, tzinfo=UTC) if stale else datetime.now(UTC)),
        packet_ref=review_packet_ref,
    )
    review_decision_ref = persist_review_decision(store, decision)
    verifier = None
    if signed:
        keypair = KeyPair.generate()
        store.sign_artifact(
            review_decision_ref,
            Ed25519Signer(keypair.private_key),
            signer_identity="reviewer_a",
        )
        verifier = Ed25519Verifier(strict_identity=True)
        verifier.add_trusted_key(keypair.public_key, identity="reviewer_a")
    return store, review_packet_ref, review_decision_ref, decision_packet_ref, verifier


def _resolve(
    store: FileSystemCAS,
    packet_ref: ArtifactRef,
    decision_ref: ArtifactRef,
    source_ref: ArtifactRef | None,
    verifier: Ed25519Verifier | None,
    **overrides: object,
) -> HumanReviewAdmission:
    arguments = {
        "review_packet_ref": packet_ref,
        "review_decision_ref": decision_ref,
        "decision_packet_ref": source_ref,
        "run_id": "run_1",
        "context_run_id": "run_1",
        "execution_profile": "profile_1",
        "minimum_time_spent_seconds": 300,
        "verifier": verifier,
    }
    arguments.update(overrides)
    return resolve_human_review_admission(
        store,
        **arguments,
    )


def test_valid_local_cas_signature_still_waits_for_institutional_custody(tmp_path) -> None:
    store, packet_ref, decision_ref, source_ref, verifier = _evidence(tmp_path)

    admission = _resolve(store, packet_ref, decision_ref, source_ref, verifier)

    assert admission.signature_verification is not None
    assert admission.signature_verification.status.value == "valid"
    assert admission.review_packet is not None
    assert admission.decision is not None
    assert admission.status is HumanReviewAdmissionStatus.NOT_ESTABLISHED
    assert admission.is_admitted is False
    assert "reviewer_appointment_authority_not_established" in admission.violations
    assert "review_decision_currentness_not_established" in admission.violations
    assert "review_duration_evidence_not_established" in admission.violations


def test_copied_or_constructed_admission_cannot_promote_public_review_status(
    tmp_path: Path,
) -> None:
    store, packet_ref, decision_ref, source_ref, verifier = _evidence(tmp_path)
    admission = _resolve(store, packet_ref, decision_ref, source_ref, verifier)

    assert admission.signature_verification is not None
    assert admission.signature_verification.status.value == "valid"
    assert admission.review_packet is not None
    assert admission.decision is not None
    promoted_copy = replace(
        admission,
        status=HumanReviewAdmissionStatus.ADMITTED,
        violations=(),
    )
    promoted_constructor = HumanReviewAdmission(
        status=HumanReviewAdmissionStatus.ADMITTED,
        review_packet=admission.review_packet,
        decision=admission.decision,
        review_packet_ref=packet_ref,
        review_decision_ref=decision_ref,
        decision_packet_ref=source_ref,
        signature_verification=admission.signature_verification,
        violations=(),
    )
    requirement = evaluate_human_review_requirement(
        params={"require_human_review_for_publication": True, "risk_tier": "high"}
    )

    for forged in (promoted_copy, promoted_constructor):
        assert forged.status is HumanReviewAdmissionStatus.ADMITTED
        assert forged.is_admitted is False
        assert (
            forged.binds(
                review_packet_ref=packet_ref,
                review_decision_ref=decision_ref,
            )
            is False
        )
        projection = forged.projection()
        assert projection["status"] == HumanReviewAdmissionStatus.NOT_ESTABLISHED.value
        assert projection["candidate_status"] == HumanReviewAdmissionStatus.ADMITTED.value
        assert "reviewer_appointment_authority_not_established" in projection["violations"]
        assert "review_decision_currentness_not_established" in projection["violations"]
        assert "review_duration_source_not_established" in projection["violations"]

        status = human_review_status(
            [admission.decision],
            packet=admission.review_packet,
            admission=forged,
            review_packet_ref=packet_ref,
            review_decision_ref=decision_ref,
        )
        section = human_review_section(
            requirement=requirement,
            review_packet_ref=packet_ref,
            review_decision_ref=decision_ref,
            decisions=[admission.decision],
            packet=admission.review_packet,
            admission=forged,
        )
        readiness = validate_human_reviewed_readiness(
            {"recommendation": "Publish."},
            review_packet_ref=packet_ref,
            review_decision_ref=decision_ref,
            decisions=[admission.decision],
            packet=admission.review_packet,
            requirement=requirement,
            admission=forged,
        )

        assert status is not HumanReviewStatus.APPROVED
        assert section["status"] != HumanReviewStatus.APPROVED.value
        assert section["custody_status"] == HumanReviewAdmissionStatus.NOT_ESTABLISHED.value
        assert "reviewer_appointment_authority_not_established" in section["custody_violations"]
        assert "review_duration_evidence_not_established" in section["custody_violations"]
        assert readiness.passed is False
        assert readiness.human_review_status is not HumanReviewStatus.APPROVED
        assert "human_review_admission_not_established" in readiness.violations
        assert "review_duration_evidence_not_established" in readiness.violations


def test_duration_source_unknown_does_not_invent_a_zero_threshold_requirement(
    tmp_path: Path,
) -> None:
    store, packet_ref, decision_ref, source_ref, verifier = _evidence(tmp_path)
    admission = _resolve(
        store,
        packet_ref,
        decision_ref,
        source_ref,
        verifier,
        minimum_time_spent_seconds=0,
    )
    forged = replace(admission, status=HumanReviewAdmissionStatus.ADMITTED, violations=())
    requirement = HumanReviewRequirement(
        required=True,
        minimum_time_spent_seconds=0,
    )

    projection = forged.projection()
    section = human_review_section(
        requirement=requirement,
        review_packet_ref=packet_ref,
        review_decision_ref=decision_ref,
        admission=forged,
    )
    readiness = validate_human_reviewed_readiness(
        {"recommendation": "Publish."},
        review_packet_ref=packet_ref,
        review_decision_ref=decision_ref,
        requirement=requirement,
        admission=forged,
    )

    assert "review_duration_source_not_established" in projection["violations"]
    assert "review_duration_evidence_not_established" not in projection["violations"]
    assert "review_duration_evidence_not_established" not in section["custody_violations"]
    assert "review_duration_evidence_not_established" not in readiness.violations
    assert readiness.passed is False


def test_unsigned_decision_and_missing_context_remain_held(tmp_path) -> None:
    store, packet_ref, decision_ref, _source_ref, _verifier = _evidence(
        tmp_path,
        signed=False,
    )

    admission = resolve_human_review_admission(
        store,
        review_packet_ref=packet_ref,
        review_decision_ref=decision_ref,
        decision_packet_ref=None,
        run_id="run_1",
        context_run_id="run_1",
        execution_profile=None,
        minimum_time_spent_seconds=0,
    )

    assert admission.status is HumanReviewAdmissionStatus.NOT_ESTABLISHED
    assert admission.signature_verification is None
    assert "reviewed_decision_packet_ref_not_established" in admission.violations
    assert "execution_profile_not_established" in admission.violations
    assert "reviewer_signature_verifier_not_established" in admission.violations


def test_selected_run_mismatch_rejects_decision_admission(tmp_path) -> None:
    store, packet_ref, decision_ref, source_ref, verifier = _evidence(tmp_path)

    admission = resolve_human_review_admission(
        store,
        review_packet_ref=packet_ref,
        review_decision_ref=decision_ref,
        decision_packet_ref=source_ref,
        run_id="run_1",
        context_run_id="another_run",
        execution_profile="profile_1",
        minimum_time_spent_seconds=0,
        verifier=verifier,
    )

    assert admission.status is HumanReviewAdmissionStatus.REJECTED
    assert "review_context_run_id_mismatch" in admission.violations


def test_selected_subject_and_profile_mismatches_reject_candidate(tmp_path) -> None:
    store, packet_ref, decision_ref, _source_ref, verifier = _evidence(tmp_path)
    other_subject = store.put_json(
        {
            "schema_version": "3.4",
            "run_id": "run_1",
            "runtime_contracts": {"execution_profile": "profile_1"},
            "policy_summary": {"title": "different selected subject"},
        },
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.DecisionPacket", version="3.4"),
        ),
    )

    wrong_subject = _resolve(
        store,
        packet_ref,
        decision_ref,
        other_subject,
        verifier,
    )
    wrong_profile = _resolve(
        store,
        packet_ref,
        decision_ref,
        _source_ref,
        verifier,
        execution_profile="another_profile",
    )

    assert wrong_subject.status is HumanReviewAdmissionStatus.REJECTED
    assert "human_review_subject_ref_mismatch" in wrong_subject.violations
    assert wrong_profile.status is HumanReviewAdmissionStatus.REJECTED
    assert "reviewed_decision_execution_profile_mismatch" in wrong_profile.violations


def test_assignment_to_another_reviewer_is_rejected(tmp_path) -> None:
    store, packet_ref, decision_ref, source_ref, verifier = _evidence(
        tmp_path,
        assigned_reviewer_id="reviewer_b",
    )

    admission = _resolve(store, packet_ref, decision_ref, source_ref, verifier)

    assert admission.status is HumanReviewAdmissionStatus.REJECTED
    assert "reviewer_not_assigned_to_packet" in admission.violations


def test_wrong_packet_and_decision_run_bindings_are_rejected(tmp_path) -> None:
    store, packet_ref, decision_ref, source_ref, verifier = _evidence(
        tmp_path,
        decision_packet_id="different_packet",
        decision_run_id="different_run",
    )

    admission = _resolve(store, packet_ref, decision_ref, source_ref, verifier)

    assert admission.status is HumanReviewAdmissionStatus.REJECTED
    assert "human_review_run_id_mismatch" in admission.violations
    assert "human_review_packet_id_mismatch" in admission.violations


def test_stale_caller_timestamps_do_not_establish_currentness_or_duration(tmp_path) -> None:
    store, packet_ref, decision_ref, source_ref, verifier = _evidence(
        tmp_path,
        stale=True,
    )

    admission = _resolve(store, packet_ref, decision_ref, source_ref, verifier)

    assert admission.signature_verification is not None
    assert admission.signature_verification.status.value == "valid"
    assert admission.status is HumanReviewAdmissionStatus.NOT_ESTABLISHED
    assert "review_decision_currentness_not_established" in admission.violations
    assert "review_duration_evidence_not_established" in admission.violations
