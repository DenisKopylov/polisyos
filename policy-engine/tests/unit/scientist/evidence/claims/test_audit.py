from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.evidence.claims.audit import (
    CLAIM_LEDGER_V2_KIND,
    append_and_persist_claim_event,
    append_only_audit_summary,
    claim_ledger_v2_inputs,
    load_append_only_claim_ledger,
    load_claim_ledger_as_append_only,
    persist_append_only_claim_ledger,
    retention_window_for_export,
)
from polisyos.scientist.evidence.claims.ledger import persist_claim_ledger
from polisyos.scientist.evidence.claims.lifecycle import (
    ClaimLifecycleAction,
    ClaimLifecycleEvent,
    build_initial_append_only_ledger,
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


def _ledger() -> ClaimLedger:
    return ClaimLedger(
        run_id="run_audit",
        claims=[
            ClaimRecord(
                claim_id="claim_1",
                run_id="run_audit",
                claim_type=ClaimType.FACTUAL,
                text="Claim text.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.INTERNAL_ONLY,
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                evidence_refs=[_ref("1")],
            )
        ],
    )


def test_append_only_claim_ledger_persists_and_loads(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    legacy_ref = persist_claim_ledger(store, _ledger())
    append_only = build_initial_append_only_ledger(
        _ledger(),
        actor_id="node",
        reason="Initial projection.",
        occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
        base_ledger_ref=legacy_ref,
    )

    ref = persist_append_only_claim_ledger(
        store,
        append_only,
        inputs=claim_ledger_v2_inputs(base_ledger_ref=legacy_ref),
    )
    loaded = load_append_only_claim_ledger(store, ref)
    manifest = store.get_manifest(ref.artifact_id)

    assert ref.kind == CLAIM_LEDGER_V2_KIND
    assert loaded == append_only
    assert {item.role for item in manifest.inputs} == {"base_claim_ledger"}


def test_legacy_claim_ledger_loads_as_append_only_compatibility_view(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    legacy_ref = persist_claim_ledger(store, _ledger())

    loaded = load_claim_ledger_as_append_only(store, legacy_ref)

    assert loaded.schema_version == "2.0"
    assert loaded.base_ledger_ref == legacy_ref
    assert loaded.retention_policy["legacy_status"] == "legacy_no_events"


def test_append_and_persist_claim_event_preserves_actor_and_order(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    append_only = build_initial_append_only_ledger(
        _ledger(),
        actor_id="node",
        reason="Initial projection.",
        occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
    )
    event = ClaimLifecycleEvent(
        event_id="event_reviewed",
        claim_id="claim_1",
        run_id="run_audit",
        action=ClaimLifecycleAction.REVIEWED,
        occurred_at=datetime(2026, 4, 29, tzinfo=UTC),
        actor_id="reviewer_1",
        reason="Reviewed by policy owner.",
        reviewer_refs=[_ref("2")],
    )

    updated, ref = append_and_persist_claim_event(store, append_only, event)
    loaded = load_append_only_claim_ledger(store, ref)
    summary = append_only_audit_summary(loaded)

    assert updated.events[-1] == event
    assert summary["event_count"] == 2
    assert summary["actor_ids"] == ["node", "reviewer_1"]
    assert summary["append_only_ordered"] is True


def test_retention_window_is_bounded_without_mutating_ledger() -> None:
    append_only = build_initial_append_only_ledger(
        _ledger(),
        actor_id="node",
        reason="Initial projection.",
        occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
        retention_policy={"max_events": 1},
    )
    event = ClaimLifecycleEvent(
        event_id="event_reviewed",
        claim_id="claim_1",
        run_id="run_audit",
        action=ClaimLifecycleAction.REVIEWED,
        occurred_at=datetime(2026, 4, 29, tzinfo=UTC),
        actor_id="reviewer_1",
        reason="Reviewed by policy owner.",
    )
    append_only = append_only.model_copy(update={"events": [*append_only.events, event]})

    window = retention_window_for_export(append_only)

    assert window["retention_applied"] is True
    assert window["included_event_ids"] == ["event_reviewed"]
    assert window["omitted_event_ids"] == [append_only.events[0].event_id]
