# ruff: noqa: S101
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.decision_validity import (
    EpochValidityBatchReceipt,
    EpochValidityBatchTarget,
    PersistedEpochValidityBatchEvidence,
)
from polisyos.scientist.evidence.claims.head_index import (
    ClaimBridgePendingStatement,
    ClaimDependencyDenominatorReceipt,
    ClaimLifecycleBridgeNonReceipt,
    UnappointedClaimLedgerOwner,
)
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
)
from polisyos.scientist.evidence.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.governance.continuous.lifecycle_bridge import (
    EpochClaimLifecycleBridgeService,
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


@dataclass(frozen=True, slots=True)
class _CompletedBatchResolver:
    evidence: PersistedEpochValidityBatchEvidence

    def resolve_completed_epoch_batch_evidence(
        self,
        *,
        batch_receipt_ref: ArtifactRef,
    ) -> PersistedEpochValidityBatchEvidence:
        if batch_receipt_ref != self.evidence.batch_receipt_ref:
            raise ValueError("decision_validity_epoch_receipt_unresolved")
        return self.evidence


def _completed_claim_bridge_fixture(
    tmp_path: Path,
    *,
    mapped: bool = True,
) -> tuple[
    FileSystemCAS,
    EpochClaimLifecycleBridgeService,
    ArtifactRef,
    ArtifactRef,
    str,
    EpochValidityBatchReceipt,
]:
    store = FileSystemCAS(tmp_path / "cas")
    evidence_ref = store.put_bytes(
        b"mapped epoch dependency",
        PutOptions(kind="fixture.epoch-dependency", media_type="application/octet-stream"),
    )
    ledger = ClaimLedger(
        run_id="run-epoch-claim-bridge",
        claims=[
            _claim("claim-epoch").model_copy(
                update={
                    "run_id": "run-epoch-claim-bridge",
                    "evidence_refs": [evidence_ref],
                }
            )
        ],
    )
    owner = UnappointedClaimLedgerOwner(store=store)
    ledger_ref = owner.persist_candidate_ledger(ledger=ledger)
    packet_ref = store.put_json(
        {
            "schema_version": "fixture.decision-packet.v1",
            "claims_ref": str(ledger_ref.artifact_id),
        },
        PutOptions(kind="scientist.decision_packet", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    transition_ref = store.put_bytes(
        b"verified epoch transition",
        PutOptions(kind="chronology.epoch_transition", media_type="application/octet-stream"),
    )
    completion_ref = store.put_bytes(
        b"verified completion",
        PutOptions(
            kind="scientist.decision_validity_epoch_batch_completion",
            media_type="application/octet-stream",
        ),
    )
    verifier_ref = store.put_bytes(
        b"decision validity verifier",
        PutOptions(
            kind="chronology.epoch_transition_verifier", media_type="application/octet-stream"
        ),
    )
    query_ref = "sha256:" + "9" * 64
    dependency_key = str(evidence_ref.artifact_id) if mapped else "sha256:" + "8" * 64
    receipt = EpochValidityBatchReceipt(
        batch_id="epoch-batch-claim-bridge",
        transition_artifact_ref=transition_ref,
        transition_content_hash=str(transition_ref.artifact_id),
        requested_query_context_ref=query_ref,
        dependency_denominator_ref="sha256:" + "7" * 64,
        adjudication_denominator_ref="sha256:" + "6" * 64,
        verifier_provenance_ref=verifier_ref,
        completion_receipt_ref=completion_ref,
        affected_packet_refs=(str(packet_ref.artifact_id),),
        targets=(
            EpochValidityBatchTarget(
                packet_ref=str(packet_ref.artifact_id),
                decision_lineage_key="lineage-claim-bridge",
                dependency_key=dependency_key,
                status="stale",
                reason="epoch advanced beyond the packet basis",
            ),
        ),
    )
    receipt_ref = store.put_json(
        receipt.model_dump(mode="json"),
        PutOptions(
            kind="scientist.decision_validity_epoch_batch_receipt",
            media_type="application/json",
        ),
    )
    receipt_raw = store.get_bytes(receipt_ref.artifact_id)
    evidence = PersistedEpochValidityBatchEvidence(
        batch_receipt_ref=receipt_ref,
        batch_receipt_content_hash="sha256:" + hashlib.sha256(receipt_raw).hexdigest(),
        receipt_bytes=receipt_raw,
        receipt=receipt,
    )
    service = EpochClaimLifecycleBridgeService(
        completed_batches=_CompletedBatchResolver(evidence),
        claim_owner=owner,
        artifacts=store,
        dependency_registry_path=Path(
            "architecture/policy_design_case/layer3_gy_claim_dependency_field_registry.json"
        ),
    )
    return store, service, receipt_ref, packet_ref, query_ref, receipt


def test_completed_epoch_batch_is_only_authority_input_to_claim_bridge(
    tmp_path: Path,
) -> None:
    store, service, receipt_ref, packet_ref, query_ref, _ = _completed_claim_bridge_fixture(
        tmp_path
    )

    result = service.bridge_completed_batch(
        batch_receipt_ref=receipt_ref,
        decision_packet_ref=packet_ref,
        requested_query_context_ref=query_ref,
    )

    assert isinstance(result, ClaimLifecycleBridgeNonReceipt)
    assert result.code == "claim_ledger_owner_not_established"
    assert result.pending is not None
    assert result.pending.statement.mapping_status == "resolved"
    assert result.pending.statement.ordered_affected_claim_ids == ("claim-epoch",)
    assert result.pending.statement.expected_head_ref is None
    pending_raw = store.get_bytes(result.pending.pending_ref.artifact_id)
    assert ClaimBridgePendingStatement.model_validate(from_canonical_bytes(pending_raw)) == (
        result.pending.statement
    )
    persisted_kinds = {
        store.get_manifest(artifact_id).kind for artifact_id in store.iter_artifact_ids()
    }
    assert "scientist.claims.ledger_root" not in persisted_kinds
    assert "scientist.claims.ledger_head" not in persisted_kinds
    assert "scientist.claims.bridge_result" not in persisted_kinds


def test_unmapped_dependency_emits_claim_target_denominator_unresolved(
    tmp_path: Path,
) -> None:
    store, service, receipt_ref, packet_ref, query_ref, _ = _completed_claim_bridge_fixture(
        tmp_path, mapped=False
    )

    result = service.bridge_completed_batch(
        batch_receipt_ref=receipt_ref,
        decision_packet_ref=packet_ref,
        requested_query_context_ref=query_ref,
    )

    assert isinstance(result, ClaimLifecycleBridgeNonReceipt)
    assert result.code == "claim_target_denominator_unresolved"
    assert result.pending is not None
    assert result.pending.statement.mapping_status == "unresolved"
    assert result.pending.statement.ordered_affected_claim_ids == ()
    denominator = ClaimDependencyDenominatorReceipt.model_validate(
        from_canonical_bytes(
            store.get_bytes(result.pending.statement.target_mapping_ref.artifact_id)
        )
    )
    assert denominator.declared_path_count == 15
    assert denominator.observed_path_count == 15
    assert denominator.unresolved_requested_dependency_keys() == ("sha256:" + "8" * 64,)


def test_fabricated_completed_batch_dto_and_matching_ref_cannot_bridge(
    tmp_path: Path,
) -> None:
    store, service, _, packet_ref, query_ref, receipt = _completed_claim_bridge_fixture(tmp_path)
    fake_ref = store.put_json(
        {"state": "completed", "looks_like": "a receipt"},
        PutOptions(
            kind="scientist.decision_validity_epoch_batch_receipt",
            media_type="application/json",
        ),
    )
    fake_raw = store.get_bytes(fake_ref.artifact_id)
    forged = PersistedEpochValidityBatchEvidence(
        batch_receipt_ref=fake_ref,
        batch_receipt_content_hash=str(fake_ref.artifact_id),
        receipt_bytes=fake_raw,
        receipt=receipt,
    )
    forged_service = EpochClaimLifecycleBridgeService(
        completed_batches=_CompletedBatchResolver(forged),
        claim_owner=service.claim_owner,
        artifacts=store,
        dependency_registry_path=service.dependency_registry_path,
    )

    result = forged_service.bridge_completed_batch(
        batch_receipt_ref=fake_ref,
        decision_packet_ref=packet_ref,
        requested_query_context_ref=query_ref,
    )

    assert isinstance(result, ClaimLifecycleBridgeNonReceipt)
    assert result.code == "claim_batch_evidence_rejected"
    assert result.pending is None


def test_raw_detector_event_cannot_establish_epoch_claim_transition(
    tmp_path: Path,
) -> None:
    _, service, receipt_ref, packet_ref, query_ref, _ = _completed_claim_bridge_fixture(tmp_path)
    raw_event = GovernanceMonitorEvent(
        event_id="advisory-only",
        decision_packet_ref=packet_ref,
        event_type="source_invalidation",
        severity="warning",
        affected_claim_ids=["claim-epoch"],
        reason="An advisory detector cannot stand in for Decision Validity.",
    )

    with pytest.raises(TypeError):
        service.bridge_completed_batch(
            batch_receipt_ref=receipt_ref,
            decision_packet_ref=packet_ref,
            requested_query_context_ref=query_ref,
            monitor_event=raw_event,  # type: ignore[call-arg]
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
