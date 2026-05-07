"""Claim-level readiness helpers layered over the existing DecisionReadiness ladder."""

from __future__ import annotations

from collections import Counter

from polisyos.scientist.evidence.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimReadinessAssessment,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness

READINESS_ORDER: tuple[DecisionReadiness, ...] = (
    DecisionReadiness.RESEARCH_ARTIFACT,
    DecisionReadiness.ANALYST_ADVISORY,
    DecisionReadiness.EXTERNAL_BRIEFING,
    DecisionReadiness.SIMULATION_READY,
    DecisionReadiness.RECOMMENDATION_READY,
    DecisionReadiness.DEPLOYMENT_READY,
)

HIGH_STAKES_CLAIM_TYPES: frozenset[ClaimType] = frozenset(
    {
        ClaimType.CAUSAL,
        ClaimType.LEGAL,
        ClaimType.FORECAST,
        ClaimType.DISTRIBUTIONAL,
        ClaimType.WELFARE,
    }
)

DECISION_BEARING_CLAIM_TYPES: frozenset[ClaimType] = frozenset(
    {
        ClaimType.CAUSAL,
        ClaimType.LEGAL,
        ClaimType.NORMATIVE,
        ClaimType.FORECAST,
        ClaimType.DISTRIBUTIONAL,
        ClaimType.WELFARE,
        ClaimType.IMPLEMENTATION,
    }
)


def readiness_rank(level: DecisionReadiness) -> int:
    """Return the stable ordinal for the public DecisionReadiness level."""

    return READINESS_ORDER.index(level)


def readiness_at_least(level: DecisionReadiness, minimum: DecisionReadiness) -> bool:
    """Return whether `level` is at least as strong as `minimum`."""

    return readiness_rank(level) >= readiness_rank(minimum)


def assess_claim_readiness(claim: ClaimRecord) -> ClaimReadinessAssessment:
    """Resolve claim publishability from support, counterevidence, and readiness."""

    blocking: list[str] = list(claim.blocked_reasons)
    review: list[str] = []

    if claim.support_status is ClaimSupportStatus.REFUTED:
        blocking.append("claim_refuted")
    if claim.counterevidence_refs:
        review.append("counterevidence_requires_review")
    if claim.claim_type in HIGH_STAKES_CLAIM_TYPES and not claim.evidence_refs:
        review.append("high_stakes_claim_missing_evidence")
    if (
        claim.claim_type in DECISION_BEARING_CLAIM_TYPES
        and claim.support_status
        in {
            ClaimSupportStatus.UNSUPPORTED,
            ClaimSupportStatus.NOT_EVALUABLE,
        }
    ):
        review.append("decision_bearing_claim_not_supported")
    if claim.support_status is ClaimSupportStatus.WEAKLY_SUPPORTED:
        review.append("weak_support_requires_review")
    if claim.support_status is ClaimSupportStatus.CONTESTED:
        review.append("contested_claim_requires_review")
    if (
        readiness_at_least(claim.readiness_level, DecisionReadiness.EXTERNAL_BRIEFING)
        and not claim.source_attribution
        and not claim.evidence_refs
    ):
        review.append("external_claim_missing_source_attribution")

    if blocking:
        publishability = ClaimPublishability.BLOCKED
    elif review:
        publishability = ClaimPublishability.REVIEW_REQUIRED
    elif claim.support_status is ClaimSupportStatus.SUPPORTED:
        publishability = (
            ClaimPublishability.PUBLISHABLE
            if readiness_at_least(claim.readiness_level, DecisionReadiness.ANALYST_ADVISORY)
            and (claim.evidence_refs or claim.claim_type is ClaimType.SOURCE_QUALITY)
            else ClaimPublishability.INTERNAL_ONLY
        )
    else:
        publishability = ClaimPublishability.DRAFT

    return ClaimReadinessAssessment(
        claim_id=claim.claim_id,
        support_status=claim.support_status,
        publishability=publishability,
        readiness_level=claim.readiness_level,
        blocking_reasons=sorted(set(blocking)),
        review_required_reasons=sorted(set(review)),
    )


def normalize_claim_readiness(claim: ClaimRecord) -> ClaimRecord:
    """Return a copy whose publishability and blocked reasons match current rules."""

    assessment = assess_claim_readiness(claim)
    blocked_reasons = list(claim.blocked_reasons)
    blocked_reasons.extend(assessment.blocking_reasons)
    if assessment.publishability is ClaimPublishability.REVIEW_REQUIRED:
        blocked_reasons.extend(
            f"review_required:{reason}" for reason in assessment.review_required_reasons
        )
    updated = claim.model_copy(
        update={
            "publishability": assessment.publishability,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )
    return ClaimRecord.model_validate(updated.model_dump(mode="python"))


def ledger_publishability_counts(ledger: ClaimLedger) -> dict[str, int]:
    """Return counts by claim publishability for dashboards and gates."""

    counts = Counter(claim.publishability.value for claim in ledger.claims)
    return {item.value: counts.get(item.value, 0) for item in ClaimPublishability}


def ledger_has_publication_blockers(ledger: ClaimLedger) -> bool:
    """Return whether a ledger contains any blocked or review-required claim."""

    return any(
        claim.publishability
        in {
            ClaimPublishability.BLOCKED,
            ClaimPublishability.REVIEW_REQUIRED,
        }
        for claim in ledger.claims
    )


def summarize_ledger_readiness(ledger: ClaimLedger) -> dict[str, object]:
    """Build the compact claim-spine status surface for packets and reports."""

    blocked = [
        claim.claim_id
        for claim in ledger.claims
        if claim.publishability is ClaimPublishability.BLOCKED
    ]
    review_required = [
        claim.claim_id
        for claim in ledger.claims
        if claim.publishability is ClaimPublishability.REVIEW_REQUIRED
    ]
    return {
        "schema_version": ledger.schema_version,
        "run_id": ledger.run_id,
        "claim_count": len(ledger.claims),
        "publishability_counts": ledger_publishability_counts(ledger),
        "blocked_claim_ids": blocked,
        "review_required_claim_ids": review_required,
        "publication_ready": not blocked and not review_required,
    }


__all__ = [
    "DECISION_BEARING_CLAIM_TYPES",
    "HIGH_STAKES_CLAIM_TYPES",
    "READINESS_ORDER",
    "assess_claim_readiness",
    "ledger_has_publication_blockers",
    "ledger_publishability_counts",
    "normalize_claim_readiness",
    "readiness_at_least",
    "readiness_rank",
    "summarize_ledger_readiness",
]
