# ruff: noqa: S101
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.continuous.monitors import (
    DecisionValidityStatus,
    build_drift_monitor_event,
)
from polisyos.scientist.governance.continuous.reissue import (
    PUBLIC_REVISION_STATE_SCHEMA_VERSION,
    ReissuePacket,
    build_partial_scope_reissue_packet,
    load_reissue_packet,
    persist_reissue_packet,
    reissue_packet_inputs,
)

if TYPE_CHECKING:
    from pathlib import Path


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def test_partial_scope_builder_maps_monitor_event_and_preserves_unaffected_refs(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    original_decision_ref = _ref("1", kind="scientist.decision_packet")
    original_ledger_ref = _ref("2", kind="scientist.claim_ledger_v2")
    new_decision_ref = _ref("3", kind="scientist.decision_packet")
    new_ledger_ref = _ref("4", kind="scientist.claim_ledger_v2")
    monitor_event_ref = _ref("5", kind="scientist.governance_monitor_event")
    unchanged_ref = _ref("6", kind="scientist.claim_record")
    superseded_ref = _ref("7", kind="scientist.claim_record")
    public_diff_ref = _ref("8", kind="runtime.public_revision_diff")
    event = build_drift_monitor_event(
        decision_packet_ref=original_decision_ref,
        event_type="calibration_drift",
        severity="block",
        reason="Calibration drift affects only claim_alpha.",
        affected_claim_ids=["claim_alpha"],
    )

    packet = build_partial_scope_reissue_packet(
        original_decision_packet_ref=original_decision_ref,
        original_claim_ledger_ref=original_ledger_ref,
        new_decision_packet_ref=new_decision_ref,
        new_claim_ledger_ref=new_ledger_ref,
        all_claim_ids=["claim_alpha", "claim_beta"],
        monitor_events=[event],
        monitor_event_refs=[monitor_event_ref],
        unchanged_records=[unchanged_ref],
        superseded_refs=[superseded_ref],
        public_diff_refs=[public_diff_ref],
        reason="Scoped reissue after calibration drift.",
        case_id="case-partial-reissue",
    )
    packet_ref = persist_reissue_packet(store, packet)
    loaded = load_reissue_packet(store, packet_ref)
    input_roles = {item.role for item in reissue_packet_inputs(packet)}

    assert loaded == packet
    assert packet.status is DecisionValidityStatus.REISSUED
    assert packet.scope_to_revise == ["claim_alpha"]
    assert packet.unchanged_records == [unchanged_ref]
    assert packet.superseded_refs == [superseded_ref]
    assert packet.public_diff_refs == [public_diff_ref]
    assert packet.partial_publication_state is not None
    assert packet.partial_publication_state.affected_claim_ids == ["claim_alpha"]
    assert packet.partial_publication_state.unaffected_claim_ids == ["claim_beta"]
    assert packet.partial_publication_state.current_case_validity == "partially_current"
    assert packet.partial_publication_state.closed_case_historical_meaning == "preserved"
    assert packet.partial_publication_state.silent_upgrade_allowed is False
    assert "unchanged_record[0]" in input_roles
    assert "superseded_ref[0]" in input_roles
    assert "public_diff[0]" in input_roles


def test_partial_publication_state_requires_scope_to_revise() -> None:
    with pytest.raises(ValidationError, match="scope_to_revise"):
        ReissuePacket(
            original_decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
            original_claim_ledger_ref=_ref("2", kind="scientist.claim_ledger_v2"),
            new_decision_packet_ref=_ref("3", kind="scientist.decision_packet"),
            new_claim_ledger_ref=_ref("4", kind="scientist.claim_ledger_v2"),
            status=DecisionValidityStatus.REISSUED,
            monitor_event_refs=[_ref("5", kind="scientist.governance_monitor_event")],
            reason="Partial state cannot be unscoped.",
            partial_publication_state={
                "schema_version": PUBLIC_REVISION_STATE_SCHEMA_VERSION,
                "case_id": "case-partial-reissue",
                "current_case_validity": "partially_current",
                "closed_case_historical_meaning": "preserved",
                "affected_claim_ids": ["claim_alpha"],
                "unaffected_claim_ids": ["claim_beta"],
                "public_diffs": [
                    {
                        "claim_id": "claim_alpha",
                        "diff_kind": "partial_reissue",
                        "public_status": "revalidation_required",
                        "reason": "Calibration drift affects claim_alpha.",
                    }
                ],
                "public_diff_required": True,
                "silent_upgrade_allowed": False,
                "revalidation_status": "revalidation_required",
                "rule_evolution_public_annotation": {},
                "blocked_structural_policy_ref": None,
                "authority_role": "projection_only",
                "provenance_kind": "runtime_projection",
                "authoritative_for": ["partial_publication_state"],
                "may_not_use_for": [
                    "claim_evidence_authority",
                    "silent_current_logic_upgrade",
                ],
            },
        )


def test_partial_scope_builder_rejects_unscoped_detector_event() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        event_type="policy_context_drift",
        severity="block",
        reason="Policy changed but detector did not map affected claims.",
    )

    with pytest.raises(ValueError, match="affected claim ids"):
        build_partial_scope_reissue_packet(
            original_decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
            original_claim_ledger_ref=_ref("2", kind="scientist.claim_ledger_v2"),
            new_decision_packet_ref=_ref("3", kind="scientist.decision_packet"),
            new_claim_ledger_ref=_ref("4", kind="scientist.claim_ledger_v2"),
            all_claim_ids=["claim_alpha", "claim_beta"],
            monitor_events=[event],
            monitor_event_refs=[_ref("5", kind="scientist.governance_monitor_event")],
            reason="Scoped reissue after policy context drift.",
            case_id="case-partial-reissue",
        )
