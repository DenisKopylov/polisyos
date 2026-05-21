from __future__ import annotations

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.scientist.governance.continuous.monitors import DecisionValidityStatus
from polisyos.scientist.governance.continuous import reissue
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


def _event_log(tmp_path, store: FileSystemCAS) -> RuntimeDiagnosticEventLog:
    return RuntimeDiagnosticEventLog(
        store=ControlPlaneStore(
            backend="sqlite",
            sqlite_path=tmp_path / "control.sqlite3",
        ),
        artifact_store=store,
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
    event_log = _event_log(tmp_path, store)
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


@pytest.mark.parametrize(
    ("status", "runtime_ref_key"),
    [
        (DecisionValidityStatus.REISSUED, "continuous_governance_reissue_report_ref"),
        (DecisionValidityStatus.SUPERSEDED, "continuous_governance_supersede_report_ref"),
        (DecisionValidityStatus.WITHDRAWN, "continuous_governance_withdraw_report_ref"),
    ],
)
def test_reissue_lifecycle_decisions_emit_runtime_authority_evidence(
    tmp_path,
    status: DecisionValidityStatus,
    runtime_ref_key: str,
) -> None:
    emit = getattr(reissue, "emit_reissue_lifecycle_evidence", None)
    assert emit is not None, "Phase 2.7 must expose reissue lifecycle evidence emission"

    store = FileSystemCAS(tmp_path)
    event_log = _event_log(tmp_path, store)
    packet = build_reissue_packet(
        original_decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        original_claim_ledger_ref=_ref("2", kind="scientist.claim_ledger_v2"),
        new_decision_packet_ref=(
            _ref("3", kind="scientist.decision_packet")
            if status is DecisionValidityStatus.REISSUED
            else None
        ),
        new_claim_ledger_ref=(
            _ref("4", kind="scientist.claim_ledger_v2")
            if status is DecisionValidityStatus.REISSUED
            else None
        ),
        status=status,
        monitor_event_refs=[_ref("5", kind="scientist.governance_monitor_event")],
        human_review_ref=(
            _ref("6", kind="scientist.human_review")
            if status is DecisionValidityStatus.WITHDRAWN
            else None
        ),
        reason=f"{status.value} after continuous governance review.",
    )
    packet_ref = persist_reissue_packet(store, packet)

    result = emit(
        store,
        packet=packet,
        packet_ref=packet_ref,
        run_id="R_lifecycle",
        job_id="job-lifecycle",
        tenant_id="tenant-1",
        cell_id="cell-a",
        trace_id="trace-lifecycle",
        span_id=f"span-{status.value}",
        effective_mode_ref="sha256:" + "7" * 64,
        fallback_degradation_ref="sha256:" + "8" * 64,
        event_log=event_log,
    )

    assert result.runtime_quality_ref_key == runtime_ref_key
    assert result.runtime_quality_refs == {runtime_ref_key: str(result.report_ref.artifact_id)}
    assert result.report["lifecycle_decision"] in {"reissue", "supersede", "withdraw"}
    assert result.report["cas_artifact_refs"]["reissue_packet_ref"] == str(packet_ref.artifact_id)
    assert result.authority_envelope["runtime_event_ref"] == str(
        result.diagnostic_event_ref.artifact_id
    )
