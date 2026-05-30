# ruff: noqa: S101
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
)
from polisyos.scientist.evidence.claims.models import (
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.governance.continuous.lifecycle_bridge import (
    bridge_governance_events_to_claim_lifecycle,
    load_lifecycle_bridge_result,
    persist_lifecycle_bridge_result,
)
from polisyos.scientist.governance.continuous.monitors import (
    DecisionValidityStatus,
    GovernanceMonitorEvent,
    build_drift_monitor_event,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness

if TYPE_CHECKING:
    from pathlib import Path


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def _claim(claim_id: str) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        run_id="run-w9e",
        claim_type=ClaimType.FACTUAL,
        text=f"Claim {claim_id} remains visible in the append-only lifecycle ledger.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
    )


def _ledger(*claim_ids: str) -> AppendOnlyClaimLedger:
    return AppendOnlyClaimLedger(
        run_id="run-w9e",
        current_claims=[_claim(claim_id) for claim_id in claim_ids],
    )


def test_bridge_maps_detector_families_to_claim_lifecycle_and_public_revision() -> None:
    decision_ref = _ref("1", kind="scientist.decision_packet")
    source_event = GovernanceMonitorEvent(
        event_id="source-stale-claim-data",
        decision_packet_ref=decision_ref,
        event_type="source_invalidation",
        severity="warning",
        affected_claim_ids=["claim_data"],
        reason="Source freshness TTL expired for claim_data.",
        occurred_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
        metadata={"invalidation_type": "stale"},
    )
    calibration_event = build_drift_monitor_event(
        decision_packet_ref=decision_ref,
        event_type="calibration_drift",
        severity="block",
        reason="Calibration drift exceeded release envelope for claim_calibration.",
        affected_claim_ids=["claim_calibration"],
    )
    fairness_event = build_drift_monitor_event(
        decision_packet_ref=decision_ref,
        event_type="fairness_drift",
        severity="warning",
        reason="Fairness drift requires reviewer triage for claim_equity.",
        affected_claim_ids=["claim_equity"],
    )
    context_event = build_drift_monitor_event(
        decision_packet_ref=decision_ref,
        event_type="policy_context_drift",
        severity="block",
        reason="The legal authority backing claim_legal was superseded.",
        affected_claim_ids=["claim_legal"],
    ).model_copy(
        update={
            "metadata": {
                "change_kind": "legal_authority_superseded",
                "superseded_by_claim_id": "claim_legal_v2",
            }
        }
    )

    result = bridge_governance_events_to_claim_lifecycle(
        ledger=_ledger(
            "claim_data",
            "claim_calibration",
            "claim_equity",
            "claim_legal",
            "claim_unaffected",
        ),
        decision_packet_ref=decision_ref,
        original_claim_ledger_ref=_ref("2", kind="scientist.claim_ledger_v2"),
        monitor_events=[source_event, calibration_event, fairness_event, context_event],
        monitor_event_refs=[
            _ref("3", kind="scientist.governance_monitor_event"),
            _ref("4", kind="scientist.governance_monitor_event"),
            _ref("5", kind="scientist.governance_monitor_event"),
            _ref("6", kind="scientist.governance_monitor_event"),
        ],
        actor_id="continuous_governance.lifecycle_bridge",
        case_id="case-w9e",
        occurred_at=datetime(2026, 5, 24, 12, 5, tzinfo=UTC),
    )

    transitions = {record.claim_id: record for record in result.transition_records}
    lifecycle_actions = {event.claim_id: event.action for event in result.updated_ledger.events}
    public_statuses = {
        diff.claim_id: diff.public_status for diff in result.public_revision_state.public_diffs
    }

    assert result.status == "pass"
    assert result.blockers == []
    assert transitions["claim_data"].transition == "stale"
    assert transitions["claim_calibration"].transition == "blocked"
    assert transitions["claim_equity"].transition == "review_required"
    assert transitions["claim_legal"].transition == "superseded"
    assert lifecycle_actions["claim_data"] is ClaimLifecycleAction.MARKED_STALE
    assert lifecycle_actions["claim_calibration"] is ClaimLifecycleAction.BLOCKED
    assert lifecycle_actions["claim_equity"] is ClaimLifecycleAction.REVIEW_REQUIRED
    assert lifecycle_actions["claim_legal"] is ClaimLifecycleAction.SUPERSEDED
    assert result.public_revision_state.affected_claim_ids == [
        "claim_data",
        "claim_calibration",
        "claim_equity",
        "claim_legal",
    ]
    assert result.public_revision_state.unaffected_claim_ids == ["claim_unaffected"]
    assert result.public_revision_state.current_case_validity == "partially_current"
    assert result.public_revision_state.authority_role == "projection_only"
    assert public_statuses == {
        "claim_data": "stale",
        "claim_calibration": "blocked",
        "claim_equity": "review_required",
        "claim_legal": "superseded",
    }
    assert result.validity_report.status is DecisionValidityStatus.REVIEW_REQUIRED
    assert result.public_validity_report["status"] == "review_required"


def test_bridge_reissued_transition_uses_partial_reissue_packet_and_persists_result(
    tmp_path: Path,
) -> None:
    decision_ref = _ref("1", kind="scientist.decision_packet")
    reissue_event = build_drift_monitor_event(
        decision_packet_ref=decision_ref,
        event_type="calibration_drift",
        severity="block",
        reason="Calibration drift requires partial reissue for claim_alpha.",
        affected_claim_ids=["claim_alpha"],
    ).model_copy(update={"metadata": {"lifecycle_transition": "reissued"}})

    result = bridge_governance_events_to_claim_lifecycle(
        ledger=_ledger("claim_alpha", "claim_beta"),
        decision_packet_ref=decision_ref,
        original_claim_ledger_ref=_ref("2", kind="scientist.claim_ledger_v2"),
        monitor_events=[reissue_event],
        monitor_event_refs=[_ref("3", kind="scientist.governance_monitor_event")],
        actor_id="continuous_governance.lifecycle_bridge",
        case_id="case-w9e-reissued",
        new_decision_packet_ref=_ref("4", kind="scientist.decision_packet"),
        new_claim_ledger_ref=_ref("5", kind="scientist.claim_ledger_v2"),
        unchanged_records=[_ref("6", kind="scientist.claim_record")],
        superseded_refs=[_ref("7", kind="scientist.claim_record")],
        public_diff_refs=[_ref("8", kind="runtime.public_revision_diff")],
        occurred_at=datetime(2026, 5, 24, 12, 10, tzinfo=UTC),
    )

    assert result.transition_records[0].transition == "reissued"
    assert result.updated_ledger.events[0].action is ClaimLifecycleAction.REISSUED
    assert result.reissue_packet is not None
    assert result.reissue_packet.status is DecisionValidityStatus.REISSUED
    assert result.reissue_packet.scope_to_revise == ["claim_alpha"]
    assert result.reissue_packet.partial_publication_state == result.public_revision_state
    assert result.public_revision_state.unaffected_claim_ids == ["claim_beta"]

    store = FileSystemCAS(tmp_path)
    bridge_ref = persist_lifecycle_bridge_result(store, result)
    loaded = load_lifecycle_bridge_result(store, bridge_ref)

    assert bridge_ref.kind == "scientist.lifecycle_bridge_result"
    assert loaded.transition_records[0].transition == "reissued"
    assert loaded.reissue_packet == result.reissue_packet


def test_unscoped_detector_event_produces_missing_lifecycle_bridge_blocker() -> None:
    decision_ref = _ref("1", kind="scientist.decision_packet")
    unscoped_event = build_drift_monitor_event(
        decision_packet_ref=decision_ref,
        event_type="policy_context_drift",
        severity="block",
        reason="Policy context changed but no affected claim was mapped.",
    )

    result = bridge_governance_events_to_claim_lifecycle(
        ledger=_ledger("claim_alpha", "claim_beta"),
        decision_packet_ref=decision_ref,
        original_claim_ledger_ref=_ref("2", kind="scientist.claim_ledger_v2"),
        monitor_events=[unscoped_event],
        monitor_event_refs=[_ref("3", kind="scientist.governance_monitor_event")],
        actor_id="continuous_governance.lifecycle_bridge",
        case_id="case-w9e-blocked",
    )

    assert result.status == "blocked"
    assert [blocker.code for blocker in result.blockers] == ["event_missing_lifecycle_bridge"]
    assert result.transition_records == []
    assert result.updated_ledger.events == []
    assert result.public_revision_state.affected_claim_ids == []
    assert result.public_revision_state.unaffected_claim_ids == ["claim_alpha", "claim_beta"]
    assert result.public_revision_state.public_diff_required is False
