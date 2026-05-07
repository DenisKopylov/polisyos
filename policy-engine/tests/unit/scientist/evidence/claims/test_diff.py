from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evidence.claims.diff import diff_claim_ledgers
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    ClaimLifecycleEvent,
)
from polisyos.scientist.evidence.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness


def _ref(suffix: str = "1") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="scientist.test",
        media_type="application/json",
    )


def _claim(
    claim_id: str,
    *,
    support_status: ClaimSupportStatus = ClaimSupportStatus.SUPPORTED,
    readiness_level: DecisionReadiness = DecisionReadiness.RESEARCH_ARTIFACT,
    publishability: ClaimPublishability = ClaimPublishability.INTERNAL_ONLY,
    counterevidence: bool = False,
    reviewer: bool = False,
) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        run_id="run_diff",
        claim_type=ClaimType.FACTUAL,
        text=f"{claim_id} text.",
        support_status=support_status,
        publishability=publishability,
        readiness_level=readiness_level,
        evidence_refs=[_ref("1")],
        counterevidence_refs=[_ref("2")] if counterevidence else [],
        reviewer_refs=[_ref("3")] if reviewer else [],
        blocked_reasons=["blocked"] if publishability is ClaimPublishability.BLOCKED else [],
    )


def test_claim_diff_reports_changed_support_readiness_and_blockers() -> None:
    before = ClaimLedger(run_id="run_diff", claims=[_claim("claim_1")])
    after = AppendOnlyClaimLedger(
        run_id="run_diff",
        current_claims=[
            _claim(
                "claim_1",
                support_status=ClaimSupportStatus.CONTESTED,
                readiness_level=DecisionReadiness.ANALYST_ADVISORY,
                publishability=ClaimPublishability.BLOCKED,
                counterevidence=True,
                reviewer=True,
            ),
            _claim("claim_2"),
        ],
        events=[
            ClaimLifecycleEvent(
                event_id="event_blocked",
                claim_id="claim_1",
                run_id="run_diff",
                action=ClaimLifecycleAction.BLOCKED,
                occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
                actor_id="reviewer",
                reason="Counterevidence found.",
            )
        ],
    )

    diff = diff_claim_ledgers(before, after)

    assert diff.added_claim_ids == ["claim_2"]
    assert diff.changed_claim_ids == ["claim_1"]
    assert diff.changed_support_claim_ids == ["claim_1"]
    assert diff.changed_readiness_claim_ids == ["claim_1"]
    assert diff.blocked_claim_ids == ["claim_1"]
    assert diff.counterevidence_changed_claim_ids == ["claim_1"]
    assert diff.reviewer_attribution_changed_claim_ids == ["claim_1"]
    assert diff.silent_publication_regression_claim_ids == []


def test_claim_diff_flags_silent_publishable_deletion() -> None:
    before = ClaimLedger(
        run_id="run_diff",
        claims=[
            _claim(
                "claim_1",
                publishability=ClaimPublishability.PUBLISHABLE,
                readiness_level=DecisionReadiness.ANALYST_ADVISORY,
            )
        ],
    )
    after = ClaimLedger(run_id="run_diff", claims=[])

    diff = diff_claim_ledgers(before, after)

    assert diff.removed_claim_ids == ["claim_1"]
    assert diff.silent_publication_regression_claim_ids == ["claim_1"]
