from __future__ import annotations


def test_continuous_governance_shim_points_to_governance_hub() -> None:
    from polisyos.scientist.governance.continuous.monitors import (
        DecisionValidityStatus as LegacyDecisionValidityStatus,
    )
    from polisyos.scientist.governance.continuous.monitors import (
        DecisionValidityStatus as CanonicalDecisionValidityStatus,
    )

    assert LegacyDecisionValidityStatus is CanonicalDecisionValidityStatus


def test_human_review_shim_points_to_governance_hub() -> None:
    from polisyos.scientist.governance.human_review.models import (
        ReviewRiskTier as CanonicalReviewRiskTier,
    )
    from polisyos.scientist.governance.human_review.models import ReviewRiskTier as LegacyReviewRiskTier

    assert LegacyReviewRiskTier is CanonicalReviewRiskTier


def test_policy_verified_shim_points_to_validation_hub() -> None:
    from polisyos.scientist.validation.policy_verified.models import PolicyRequestFrame as LegacyFrame
    from polisyos.scientist.validation.policy_verified.models import (
        PolicyRequestFrame as CanonicalFrame,
    )

    assert LegacyFrame is CanonicalFrame


def test_verification_shim_points_to_validation_hub() -> None:
    from polisyos.scientist.validation.verification.ic import (
        verify_incentive_compatibility as canonical_verify,
    )
    from polisyos.scientist.validation.verification.ic import (
        verify_incentive_compatibility as legacy_verify,
    )

    assert legacy_verify is canonical_verify
