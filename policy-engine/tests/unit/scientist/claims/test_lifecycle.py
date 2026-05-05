from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    ClaimLifecycleEvent,
    append_lifecycle_event,
    build_initial_append_only_ledger,
    lifecycle_status_for_ledger,
    validate_claim_transition,
)
from polisyos.scientist.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.search.readiness import DecisionReadiness
from pydantic import ValidationError


def _ref(suffix: str = "1") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="scientist.test",
        media_type="application/json",
    )


def _claim(
    claim_id: str = "claim_1",
    *,
    publishability: ClaimPublishability = ClaimPublishability.INTERNAL_ONLY,
    support_status: ClaimSupportStatus = ClaimSupportStatus.SUPPORTED,
    readiness_level: DecisionReadiness = DecisionReadiness.RESEARCH_ARTIFACT,
) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        run_id="run_lifecycle",
        claim_type=ClaimType.FACTUAL,
        text=f"{claim_id} text.",
        support_status=support_status,
        publishability=publishability,
        readiness_level=readiness_level,
        evidence_refs=[_ref("1")],
        source_attribution=["fixture"],
        blocked_reasons=["blocked"] if publishability is ClaimPublishability.BLOCKED else [],
    )


def test_initial_append_only_ledger_records_created_events() -> None:
    ledger = ClaimLedger(run_id="run_lifecycle", claims=[_claim()])

    append_only = build_initial_append_only_ledger(
        ledger,
        actor_id="node",
        reason="Initial projection.",
        occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
    )

    assert append_only.schema_version == "2.0"
    assert lifecycle_status_for_ledger(append_only) == "available"
    assert append_only.events[0].action is ClaimLifecycleAction.CREATED
    assert append_only.events[0].reason == "Initial projection."


def test_transition_without_reason_fails() -> None:
    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        ClaimLifecycleEvent(
            event_id="event_1",
            claim_id="claim_1",
            run_id="run_lifecycle",
            action=ClaimLifecycleAction.UPDATED_READINESS,
            actor_id="reviewer",
            reason="",
        )
    with pytest.raises(ValidationError, match="cannot be blank"):
        ClaimLifecycleEvent(
            event_id="event_1",
            claim_id="claim_1",
            run_id="run_lifecycle",
            action=ClaimLifecycleAction.UPDATED_READINESS,
            actor_id="reviewer",
            reason="   ",
        )


def test_merge_and_split_events_preserve_source_claim_ids() -> None:
    with pytest.raises(ValidationError, match="metadata.source_claim_ids"):
        ClaimLifecycleEvent(
            event_id="event_merge",
            claim_id="claim_merged",
            run_id="run_lifecycle",
            action=ClaimLifecycleAction.MERGED,
            actor_id="reviewer",
            reason="Merge duplicate claims.",
            metadata={"target_claim_ids": ["claim_merged"]},
        )

    with pytest.raises(ValidationError, match="source claim_id"):
        ClaimLifecycleEvent(
            event_id="event_split",
            claim_id="claim_source",
            run_id="run_lifecycle",
            action=ClaimLifecycleAction.SPLIT,
            actor_id="reviewer",
            reason="Split compound claim.",
            metadata={
                "source_claim_ids": ["other_claim"],
                "target_claim_ids": ["claim_a", "claim_b"],
            },
        )


def test_append_only_event_order_is_checked() -> None:
    ledger = AppendOnlyClaimLedger(
        run_id="run_lifecycle",
        current_claims=[_claim()],
        events=[
            ClaimLifecycleEvent(
                event_id="event_1",
                claim_id="claim_1",
                run_id="run_lifecycle",
                action=ClaimLifecycleAction.CREATED,
                occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
                actor_id="node",
                reason="Created.",
            )
        ],
    )
    older_event = ClaimLifecycleEvent(
        event_id="event_2",
        claim_id="claim_1",
        run_id="run_lifecycle",
        action=ClaimLifecycleAction.REVIEWED,
        occurred_at=datetime(2026, 4, 28, tzinfo=UTC) - timedelta(seconds=1),
        actor_id="reviewer",
        reason="Reviewed.",
    )

    with pytest.raises(ValueError, match="reordered"):
        append_lifecycle_event(ledger, older_event)


def test_superseded_claim_must_remain_visible_in_current_claims() -> None:
    with pytest.raises(ValidationError, match="remain visible"):
        AppendOnlyClaimLedger(
            run_id="run_lifecycle",
            current_claims=[_claim("claim_new")],
            events=[
                ClaimLifecycleEvent(
                    event_id="event_superseded",
                    claim_id="claim_old",
                    run_id="run_lifecycle",
                    action=ClaimLifecycleAction.SUPERSEDED,
                    occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
                    actor_id="reviewer",
                    reason="Replaced by a narrower claim.",
                    metadata={"superseded_by_claim_id": "claim_new"},
                )
            ],
        )


def test_publishable_claim_cannot_be_silently_downgraded_or_deleted() -> None:
    previous = _claim(
        publishability=ClaimPublishability.PUBLISHABLE,
        readiness_level=DecisionReadiness.ANALYST_ADVISORY,
    )
    downgraded = previous.model_copy(update={"publishability": ClaimPublishability.INTERNAL_ONLY})

    with pytest.raises(ValueError, match="silently downgraded"):
        validate_claim_transition(
            previous,
            downgraded,
            action=ClaimLifecycleAction.UPDATED_READINESS,
            reason="Changed.",
        )
    with pytest.raises(ValueError, match="silently deleted"):
        validate_claim_transition(
            previous,
            None,
            action=ClaimLifecycleAction.INVALIDATED,
            reason="Changed.",
        )


def test_publishability_change_requires_release_lifecycle_action() -> None:
    previous = _claim()
    blocked = previous.model_copy(
        update={
            "publishability": ClaimPublishability.BLOCKED,
            "blocked_reasons": ["counterevidence_found"],
        }
    )

    with pytest.raises(ValueError, match="blocking a claim requires blocked action"):
        validate_claim_transition(
            previous,
            blocked,
            action=ClaimLifecycleAction.UPDATED_SUPPORT,
            reason="Counterevidence found.",
        )


def test_blocked_transition_can_record_support_and_readiness_changes_with_reason() -> None:
    previous = _claim(
        publishability=ClaimPublishability.INTERNAL_ONLY,
        support_status=ClaimSupportStatus.SUPPORTED,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
    )
    blocked = previous.model_copy(
        update={
            "support_status": ClaimSupportStatus.CONTESTED,
            "publishability": ClaimPublishability.BLOCKED,
            "readiness_level": DecisionReadiness.ANALYST_ADVISORY,
            "counterevidence_refs": [_ref("2")],
            "blocked_reasons": ["counterevidence_found"],
        }
    )

    validate_claim_transition(
        previous,
        blocked,
        action=ClaimLifecycleAction.BLOCKED,
        reason="Counterevidence found.",
    )


def test_legacy_ledger_renders_legacy_no_events() -> None:
    assert lifecycle_status_for_ledger(ClaimLedger(run_id="run_lifecycle")) == ("legacy_no_events")


def test_legacy_append_only_wrapper_renders_legacy_no_events() -> None:
    wrapped = build_initial_append_only_ledger(
        ClaimLedger(run_id="run_lifecycle", claims=[_claim()]),
        actor_id="legacy_loader",
        reason="Loaded legacy ledger.",
        retention_policy={"legacy_status": "legacy_no_events"},
    )

    assert lifecycle_status_for_ledger(wrapped) == "legacy_no_events"
