from __future__ import annotations

from polisyos.scientist.governance.human_review.models import ReviewRiskTier
from polisyos.scientist.governance.human_review.oversight_policy import HumanReviewRequirement
from polisyos.scientist.governance.human_review.voi_escalation import (
    build_human_escalation_voi_decision,
    validate_human_escalation_voi_decision,
)
from polisyos.scientist.methods.search.voi_models import VOIDecisionRecord, VOIDecisionType


def test_required_human_review_is_escalated_and_auditable() -> None:
    requirement = HumanReviewRequirement(
        required=True,
        risk_tier=ReviewRiskTier.PUBLIC_SECTOR_HIGH,
        reasons=["high_risk_public_sector"],
        required_reviewer_count=2,
    )

    decision = build_human_escalation_voi_decision(
        run_id="run_voi",
        requirement=requirement,
        expected_harm=2.0,
        reversal_risk=0.5,
        review_cost=0.25,
    )

    assert decision.recommended_action == "request_human_review"
    assert decision.metadata["required_reviewer_count"] == 2
    assert decision.metadata["overrideable_by_human"] is True
    assert validate_human_escalation_voi_decision(decision, requirement=requirement) == []


def test_voi_cannot_suppress_required_human_review() -> None:
    requirement = HumanReviewRequirement(required=True, reasons=["feature_flag_required"])
    decision = VOIDecisionRecord(
        decision_id="voi_human_1",
        run_id="run_voi",
        decision_type=VOIDecisionType.HUMAN_ESCALATION,
        recommended_action="defer",
        expected_value=-0.1,
        expected_cost=0.0,
        expected_risk_reduction=0.0,
        explanation="Do not review.",
    )

    assert validate_human_escalation_voi_decision(decision, requirement=requirement) == [
        "required_human_review_suppressed:voi_human_1"
    ]


def test_voi_escalation_preserves_independence_and_effectiveness_requirements() -> None:
    requirement = HumanReviewRequirement(
        required=True,
        reasons=["two_person_review_requested"],
        reviewer_independence_required=True,
        separation_of_duty_required=True,
        minimum_time_spent_seconds=300,
        require_change_request_or_dissent=True,
    )

    decision = build_human_escalation_voi_decision(
        run_id="run_voi",
        requirement=requirement,
        expected_harm=1.0,
        reversal_risk=0.6,
        review_cost=0.1,
    )

    assert decision.recommended_action == "request_human_review"
    assert decision.metadata["reviewer_independence_required"] is True
    assert decision.metadata["separation_of_duty_required"] is True
    assert decision.metadata["minimum_time_spent_seconds"] == 300
    assert decision.metadata["require_change_request_or_dissent"] is True

    suppressed = VOIDecisionRecord(
        decision_id="voi_human_independence",
        run_id="run_voi",
        decision_type=VOIDecisionType.HUMAN_ESCALATION,
        recommended_action="request_human_review",
        expected_value=0.1,
        expected_cost=0.0,
        expected_risk_reduction=0.1,
        explanation="Review without independence controls.",
        metadata={
            "reviewer_independent": False,
            "separation_of_duty_attested": False,
            "time_spent_seconds": 90,
            "dissent": False,
            "change_request_count": 0,
        },
    )

    assert validate_human_escalation_voi_decision(
        suppressed,
        requirement=requirement,
    ) == [
        "reviewer_independence_missing:voi_human_independence",
        "separation_of_duty_missing:voi_human_independence",
        "effective_review_time_missing:voi_human_independence",
        "review_challenge_signal_missing:voi_human_independence",
    ]


def test_voi_required_independence_and_time_metadata_must_be_observed() -> None:
    requirement = HumanReviewRequirement(
        required=True,
        reasons=["material_policy_claim"],
        reviewer_independence_required=True,
        separation_of_duty_required=True,
        minimum_time_spent_seconds=300,
    )
    decision = VOIDecisionRecord(
        decision_id="voi_human_missing_observed_metadata",
        run_id="run_voi",
        decision_type=VOIDecisionType.HUMAN_ESCALATION,
        recommended_action="request_human_review",
        expected_value=0.1,
        expected_cost=0.0,
        expected_risk_reduction=0.1,
        explanation="Review requested but no observed reviewer controls are attached.",
        metadata={},
    )

    assert validate_human_escalation_voi_decision(
        decision,
        requirement=requirement,
    ) == [
        "reviewer_independence_missing:voi_human_missing_observed_metadata",
        "separation_of_duty_missing:voi_human_missing_observed_metadata",
        "effective_review_time_missing:voi_human_missing_observed_metadata",
    ]
