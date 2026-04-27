from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.claims.readiness import (
    normalize_claim_readiness,
    readiness_at_least,
    summarize_ledger_readiness,
)
from polisyos.scientist.search.readiness import DecisionReadiness


def _ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="scientist.evidence",
        media_type="application/json",
    )


def test_legal_claim_without_evidence_requires_review() -> None:
    claim = ClaimRecord(
        claim_id="claim_legal",
        run_id="run_1",
        claim_type=ClaimType.LEGAL,
        text="The policy has a legal basis.",
        support_status=ClaimSupportStatus.UNSUPPORTED,
        publishability=ClaimPublishability.DRAFT,
        readiness_level=DecisionReadiness.EXTERNAL_BRIEFING,
    )

    normalized = normalize_claim_readiness(claim)

    assert normalized.publishability is ClaimPublishability.REVIEW_REQUIRED
    assert "review_required:high_stakes_claim_missing_evidence" in normalized.blocked_reasons


def test_supported_claim_with_evidence_becomes_publishable() -> None:
    claim = ClaimRecord(
        claim_id="claim_supported",
        run_id="run_1",
        claim_type=ClaimType.FACTUAL,
        text="The validation report passed.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.DRAFT,
        readiness_level=DecisionReadiness.ANALYST_ADVISORY,
        evidence_refs=[_ref()],
        source_attribution=["validation_report"],
    )

    normalized = normalize_claim_readiness(claim)

    assert normalized.publishability is ClaimPublishability.PUBLISHABLE


def test_ledger_summary_surfaces_blockers_and_counts() -> None:
    supported = normalize_claim_readiness(
        ClaimRecord(
            claim_id="claim_supported",
            run_id="run_1",
            claim_type=ClaimType.FACTUAL,
            text="Metric exists.",
            support_status=ClaimSupportStatus.SUPPORTED,
            publishability=ClaimPublishability.DRAFT,
            readiness_level=DecisionReadiness.ANALYST_ADVISORY,
            evidence_refs=[_ref()],
        )
    )
    unsupported = normalize_claim_readiness(
        ClaimRecord(
            claim_id="claim_unsupported",
            run_id="run_1",
            claim_type=ClaimType.LEGAL,
            text="Legal authority exists.",
            support_status=ClaimSupportStatus.UNSUPPORTED,
            publishability=ClaimPublishability.DRAFT,
            readiness_level=DecisionReadiness.EXTERNAL_BRIEFING,
        )
    )

    summary = summarize_ledger_readiness(
        ClaimLedger(run_id="run_1", claims=[supported, unsupported])
    )

    assert summary["claim_count"] == 2
    assert summary["publication_ready"] is False
    assert summary["publishability_counts"]["publishable"] == 1
    assert summary["publishability_counts"]["review_required"] == 1


def test_claim_readiness_uses_existing_decision_readiness_ladder() -> None:
    assert readiness_at_least(
        DecisionReadiness.RECOMMENDATION_READY,
        DecisionReadiness.ANALYST_ADVISORY,
    )
