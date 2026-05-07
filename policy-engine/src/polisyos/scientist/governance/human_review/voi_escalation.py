"""VOI-based, auditable human-review escalation recommendations."""

from __future__ import annotations

from collections.abc import Sequence

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.governance.human_review.oversight_policy import HumanReviewRequirement
from polisyos.scientist.methods.search.voi_models import (
    VOIDecisionRecord,
    VOIDecisionType,
    stable_voi_decision_id,
)

HUMAN_REVIEW_MANDATORY_GATE = "human_review_required"


def build_human_escalation_voi_decision(
    *,
    run_id: str,
    requirement: HumanReviewRequirement,
    expected_harm: float = 0.0,
    reversal_risk: float = 0.0,
    review_cost: float = 1.0,
    input_refs: Sequence[ArtifactRef] = (),
    sequence: int = 0,
) -> VOIDecisionRecord:
    """Recommend whether to escalate to human review without waiving hard gates."""

    risk_reduction = _risk_reduction(
        requirement=requirement,
        expected_harm=expected_harm,
        reversal_risk=reversal_risk,
    )
    expected_cost = max(review_cost, 0.0)
    expected_value = risk_reduction - expected_cost
    if requirement.required:
        action = "request_human_review"
        expected_value = max(expected_value, 0.0)
    else:
        action = "request_human_review" if expected_value >= 0.0 and risk_reduction > 0 else "defer"
    return VOIDecisionRecord(
        decision_id=stable_voi_decision_id(
            run_id=run_id,
            decision_type=VOIDecisionType.HUMAN_ESCALATION,
            subject_id=requirement.risk_tier.value,
            sequence=sequence,
        ),
        run_id=run_id,
        decision_type=VOIDecisionType.HUMAN_ESCALATION,
        recommended_action=action,
        expected_value=expected_value,
        expected_cost=expected_cost,
        expected_risk_reduction=risk_reduction,
        explanation=(
            f"{action}: risk_tier={requirement.risk_tier.value}, "
            f"required={requirement.required}, reasons={','.join(requirement.reasons) or 'none'}."
        ),
        input_refs=list(input_refs),
        metadata={
            "risk_tier": requirement.risk_tier.value,
            "required": requirement.required,
            "required_reviewer_count": requirement.required_reviewer_count,
            "reasons": list(requirement.reasons),
            "overrideable_by_human": True,
        },
    )


def validate_human_escalation_voi_decision(
    decision: VOIDecisionRecord,
    *,
    requirement: HumanReviewRequirement,
) -> list[str]:
    """Return violations when VOI tries to suppress mandatory human review."""

    if decision.decision_type is not VOIDecisionType.HUMAN_ESCALATION:
        return [f"not_human_escalation_decision:{decision.decision_id}"]
    action = decision.recommended_action.strip().lower()
    if requirement.required and action not in {"request_human_review", "run_required_gate"}:
        return [f"required_human_review_suppressed:{decision.decision_id}"]
    return []


def _risk_reduction(
    *,
    requirement: HumanReviewRequirement,
    expected_harm: float,
    reversal_risk: float,
) -> float:
    tier_multiplier = {
        "low": 0.3,
        "medium": 0.6,
        "high": 1.0,
        "public_sector_high": 1.2,
    }.get(requirement.risk_tier.value, 0.6)
    required_bonus = 0.5 if requirement.required else 0.0
    return max(
        0.0,
        min(
            2.0,
            (max(expected_harm, 0.0) * max(reversal_risk, 0.0) * tier_multiplier)
            + required_bonus,
        ),
    )


__all__ = [
    "HUMAN_REVIEW_MANDATORY_GATE",
    "build_human_escalation_voi_decision",
    "validate_human_escalation_voi_decision",
]
