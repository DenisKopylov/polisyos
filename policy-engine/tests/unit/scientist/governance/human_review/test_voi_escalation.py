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
