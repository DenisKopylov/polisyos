from __future__ import annotations

import pytest
from polisyos.scientist.human_review.audit import signature_for_decision
from polisyos.scientist.human_review.models import (
    FundamentalRightsChecklist,
    HumanReviewDecision,
    HumanReviewPacket,
    ReviewAction,
    ReviewControl,
    ReviewRiskTier,
)


def test_high_risk_packet_requires_stop_and_override_controls() -> None:
    with pytest.raises(ValueError, match="stop_release"):
        HumanReviewPacket(
            packet_id="packet_1",
            run_id="run_1",
            risk_tier=ReviewRiskTier.HIGH,
            controls=[ReviewControl.REQUEST_RERUN],
        )


def test_override_decision_requires_override_reason() -> None:
    with pytest.raises(ValueError, match="override_reason"):
        HumanReviewDecision(
            decision_id="decision_1",
            packet_id="packet_1",
            run_id="run_1",
            reviewer_id="reviewer_a",
            action=ReviewAction.OVERRIDE,
            rationale="Override is needed.",
            signature=signature_for_decision(
                reviewer_id="reviewer_a",
                attestation="I accept accountability for this override.",
            ),
        )


def test_fundamental_rights_checklist_surfaces_unresolved_items() -> None:
    checklist = FundamentalRightsChecklist(
        public_sector_use=True,
        affects_fundamental_rights=True,
        automated_decision_support=True,
    )

    assert checklist.unresolved_items == [
        "explanation_available",
        "human_override_available",
        "legal_basis_documented",
        "privacy_impact_considered",
    ]
