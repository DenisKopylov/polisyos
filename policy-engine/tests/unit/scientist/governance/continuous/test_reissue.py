from __future__ import annotations

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.continuous.monitors import DecisionValidityStatus
from polisyos.scientist.governance.continuous.reissue import (
    ReissuePacket,
    build_reissue_packet,
    load_reissue_packet,
    persist_reissue_packet,
)
from pydantic import ValidationError


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def test_reissue_packet_links_old_and_new_ledgers() -> None:
    packet = build_reissue_packet(
        original_decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        original_claim_ledger_ref=_ref("2", kind="scientist.claim_ledger_v2"),
        new_decision_packet_ref=_ref("3", kind="scientist.decision_packet"),
        new_claim_ledger_ref=_ref("4", kind="scientist.claim_ledger_v2"),
        status=DecisionValidityStatus.REISSUED,
        monitor_event_refs=[_ref("5", kind="scientist.governance_monitor_event")],
        reason="Reissued after source invalidation.",
    )

    assert packet.status is DecisionValidityStatus.REISSUED
    assert packet.original_claim_ledger_ref.artifact_id != packet.new_claim_ledger_ref.artifact_id


def test_reissue_packet_requires_original_claim_ledger_ref() -> None:
    with pytest.raises(ValidationError):
        ReissuePacket(
            original_decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
            status=DecisionValidityStatus.REVIEW_REQUIRED,
            monitor_event_refs=[_ref("5", kind="scientist.governance_monitor_event")],
            reason="Missing original claim ledger.",
        )


def test_reissued_status_requires_new_decision_and_claim_ledger_refs() -> None:
    with pytest.raises(ValidationError, match="new decision and claim ledger refs"):
        ReissuePacket(
            original_decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
            original_claim_ledger_ref=_ref("2", kind="scientist.claim_ledger_v2"),
            status=DecisionValidityStatus.REISSUED,
            monitor_event_refs=[_ref("5", kind="scientist.governance_monitor_event")],
            reason="Incomplete reissue.",
        )


def test_reissue_packet_persists_to_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    packet = build_reissue_packet(
        original_decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        original_claim_ledger_ref=_ref("2", kind="scientist.claim_ledger_v2"),
        new_decision_packet_ref=_ref("3", kind="scientist.decision_packet"),
        new_claim_ledger_ref=_ref("4", kind="scientist.claim_ledger_v2"),
        status=DecisionValidityStatus.REISSUED,
        monitor_event_refs=[_ref("5", kind="scientist.governance_monitor_event")],
        reason="Reissued after source invalidation.",
    )

    ref = persist_reissue_packet(store, packet)
    loaded = load_reissue_packet(store, ref)

    assert loaded == packet
    assert ref.kind == "scientist.reissue_packet"
