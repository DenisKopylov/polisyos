from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.governance.human_review.audit import signature_for_decision
from polisyos.scientist.governance.human_review.decisions import human_review_status
from polisyos.scientist.governance.human_review.models import (
    HumanReviewDecision,
    HumanReviewStatus,
    ReviewAction,
)
from polisyos.scientist.governance.human_review.oversight_policy import (
    evaluate_human_review_requirement,
    validate_human_reviewed_readiness,
)
from polisyos.scientist.governance.human_review.packets import build_review_packet


def _ref(ch: str, *, kind: str = "scientist.human_review_packet") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + ch * 64,
        kind=kind,
        media_type="application/json",
    )


def _approve(packet_id: str, reviewer_id: str) -> HumanReviewDecision:
    return HumanReviewDecision(
        decision_id=f"decision_{reviewer_id}",
        packet_id=packet_id,
        run_id="run_1",
        reviewer_id=reviewer_id,
        action=ReviewAction.APPROVE,
        rationale="Reviewed and approved.",
        signature=signature_for_decision(
            reviewer_id=reviewer_id,
            attestation="I reviewed the packet.",
        ),
    )


def test_high_risk_public_sector_path_requires_two_person_review() -> None:
    requirement = evaluate_human_review_requirement(
        params={"public_sector": True, "risk_tier": "high"}
    )

    assert requirement.required is True
    assert requirement.risk_tier.value == "public_sector_high"
    assert requirement.required_reviewer_count == 2
    assert "high_risk_public_sector" in requirement.reasons


def test_human_reviewed_readiness_without_review_ref_is_blocked() -> None:
    result = validate_human_reviewed_readiness(
        {"readiness": "human_reviewed", "recommendation": "Publish."}
    )

    assert result.passed is False
    assert result.violations == ["human_reviewed_readiness_without_review_ref"]


def test_two_person_verification_requires_distinct_approvals() -> None:
    packet = build_review_packet(
        run_id="run_1",
        risk_tier="public_sector_high",
        required_reviewer_count=2,
    )

    assert human_review_status([_approve(packet.packet_id, "a")], packet=packet) is (
        HumanReviewStatus.PENDING
    )
    assert (
        human_review_status(
            [_approve(packet.packet_id, "a"), _approve(packet.packet_id, "b")],
            packet=packet,
        )
        is HumanReviewStatus.APPROVED
    )


def test_reject_rerun_interrupt_and_override_have_explicit_release_statuses() -> None:
    packet = build_review_packet(run_id="run_1")
    reject = HumanReviewDecision(
        decision_id="decision_reject",
        packet_id=packet.packet_id,
        run_id="run_1",
        reviewer_id="reviewer_a",
        action=ReviewAction.REJECT,
        rationale="Release is not acceptable.",
        signature=signature_for_decision(
            reviewer_id="reviewer_a",
            attestation="I reviewed the packet.",
        ),
    )
    rerun = HumanReviewDecision(
        decision_id="decision_rerun",
        packet_id=packet.packet_id,
        run_id="run_1",
        reviewer_id="reviewer_a",
        action=ReviewAction.REQUEST_RERUN,
        rationale="Run must be repeated with updated evidence.",
        requested_changes=["Refresh source verification."],
        signature=signature_for_decision(
            reviewer_id="reviewer_a",
            attestation="I reviewed the packet.",
        ),
    )
    interrupt = HumanReviewDecision(
        decision_id="decision_interrupt",
        packet_id=packet.packet_id,
        run_id="run_1",
        reviewer_id="reviewer_a",
        action=ReviewAction.INTERRUPT_RELEASE,
        rationale="Stop release while legal review is pending.",
        signature=signature_for_decision(
            reviewer_id="reviewer_a",
            attestation="I reviewed the packet.",
        ),
    )
    override = HumanReviewDecision(
        decision_id="decision_override",
        packet_id=packet.packet_id,
        run_id="run_1",
        reviewer_id="reviewer_a",
        action=ReviewAction.OVERRIDE,
        rationale="Override with explicit release-owner accountability.",
        override_reason="Known issue accepted under emergency release policy.",
        signature=signature_for_decision(
            reviewer_id="reviewer_a",
            attestation="I accept accountability for this override.",
        ),
    )

    assert human_review_status([reject], packet=packet) is HumanReviewStatus.REJECTED
    assert human_review_status([rerun], packet=packet) is HumanReviewStatus.RERUN_REQUESTED
    assert human_review_status([interrupt], packet=packet) is HumanReviewStatus.INTERRUPTED
    assert human_review_status([override], packet=packet) is HumanReviewStatus.OVERRIDDEN


def test_required_review_with_explanation_insufficient_decision_blocks_release() -> None:
    packet = build_review_packet(run_id="run_1")
    decision = HumanReviewDecision(
        decision_id="decision_gap",
        packet_id=packet.packet_id,
        run_id="run_1",
        reviewer_id="reviewer_a",
        action=ReviewAction.EXPLANATION_INSUFFICIENT,
        rationale="Explanation is not enough for affected users.",
        explanation_gap="Missing plain-language right-to-explanation section.",
        signature=signature_for_decision(
            reviewer_id="reviewer_a",
            attestation="I reviewed the explanation.",
        ),
    )
    requirement = evaluate_human_review_requirement(
        params={"require_human_review_for_publication": True}
    )

    result = validate_human_reviewed_readiness(
        {"recommendation": "Publish."},
        review_packet_ref=_ref("1"),
        review_decision_ref=_ref("2", kind="scientist.human_review_decision"),
        decisions=[decision],
        packet=packet,
        requirement=requirement,
    )

    assert result.passed is False
    assert result.human_review_status is HumanReviewStatus.EXPLANATION_INSUFFICIENT
    assert result.violations == ["human_review_not_release_approved:explanation_insufficient"]
