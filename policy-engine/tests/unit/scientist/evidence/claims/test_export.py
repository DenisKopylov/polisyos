from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evidence.claims.export import (
    ClaimExportAudience,
    blocked_claim_summary,
    claim_ledger_summary,
    export_claim_ledger,
    legacy_claim_ledger_export_status,
)
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
    publishability: ClaimPublishability,
) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        run_id="run_export",
        claim_type=ClaimType.FACTUAL,
        text=f"{claim_id} text.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=publishability,
        readiness_level=DecisionReadiness.ANALYST_ADVISORY,
        evidence_refs=[_ref("1")],
        blocked_reasons=["blocked"] if publishability is ClaimPublishability.BLOCKED else [],
    )


def test_reviewer_and_machine_exports_keep_blocked_and_superseded_claims_visible() -> None:
    ledger = AppendOnlyClaimLedger(
        run_id="run_export",
        current_claims=[
            _claim("claim_public", publishability=ClaimPublishability.PUBLISHABLE),
            _claim("claim_blocked", publishability=ClaimPublishability.BLOCKED),
        ],
        events=[
            ClaimLifecycleEvent(
                event_id="event_superseded",
                claim_id="claim_blocked",
                run_id="run_export",
                action=ClaimLifecycleAction.SUPERSEDED,
                occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
                actor_id="reviewer",
                reason="Replaced with narrower claim.",
                metadata={"superseded_by_claim_id": "claim_public"},
            )
        ],
    )

    reviewer = export_claim_ledger(ledger, audience=ClaimExportAudience.REVIEWER)
    machine = export_claim_ledger(ledger, audience=ClaimExportAudience.MACHINE)
    public = export_claim_ledger(ledger, audience=ClaimExportAudience.PUBLIC)

    assert all(claim.visible for claim in reviewer.claims)
    assert all(claim.visible for claim in machine.claims)
    assert "claim_blocked" in public.omitted_claim_ids
    assert reviewer.blocked_claim_ids == ["claim_blocked"]
    assert reviewer.superseded_claim_ids == ["claim_blocked"]


def test_machine_export_includes_bounded_retention_window() -> None:
    ledger = AppendOnlyClaimLedger(
        run_id="run_export",
        current_claims=[
            _claim("claim_public", publishability=ClaimPublishability.PUBLISHABLE),
        ],
        events=[
            ClaimLifecycleEvent(
                event_id="event_created",
                claim_id="claim_public",
                run_id="run_export",
                action=ClaimLifecycleAction.CREATED,
                occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
                actor_id="node",
                reason="Initial projection.",
            ),
            ClaimLifecycleEvent(
                event_id="event_reviewed",
                claim_id="claim_public",
                run_id="run_export",
                action=ClaimLifecycleAction.REVIEWED,
                occurred_at=datetime(2026, 4, 29, tzinfo=UTC),
                actor_id="reviewer",
                reason="Reviewed for publication.",
            ),
        ],
        retention_policy={"max_events": 1},
    )

    machine = export_claim_ledger(ledger, audience=ClaimExportAudience.MACHINE)

    assert machine.metadata["retention_window"] == {
        "retention_applied": True,
        "included_event_ids": ["event_reviewed"],
        "omitted_event_ids": ["event_created"],
    }


def test_packet_summaries_include_blocked_claims_and_lifecycle_status() -> None:
    ledger = ClaimLedger(
        run_id="run_export",
        claims=[
            _claim("claim_public", publishability=ClaimPublishability.PUBLISHABLE),
            _claim("claim_blocked", publishability=ClaimPublishability.BLOCKED),
        ],
    )

    summary = claim_ledger_summary(ledger)
    blocked = blocked_claim_summary(ledger)

    assert summary["lifecycle_status"] == "legacy_no_events"
    assert summary["blocked_claim_ids"] == ["claim_blocked"]
    assert blocked["blocked_count"] == 1
    assert blocked["blocked_claims"][0]["claim_id"] == "claim_blocked"
    assert legacy_claim_ledger_export_status(ledger) == "legacy_no_events"
