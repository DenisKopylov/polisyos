from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.continuous_governance.incident import (
    IncidentReport,
    IncidentSeverity,
    build_withdrawal_record,
    incident_monitor_event,
    load_incident_report,
    load_withdrawal_record,
    persist_incident_report,
    persist_withdrawal_record,
)
from polisyos.scientist.continuous_governance.monitors import recommend_validity_action


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def test_blocking_incident_triggers_withdrawal_review() -> None:
    incident = IncidentReport(
        incident_id="incident_1",
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        severity=IncidentSeverity.BLOCK,
        reason="Published artifact relied on withdrawn evidence.",
        affected_claim_ids=["claim_1"],
    )

    event = incident_monitor_event(incident=incident)
    recommendation = recommend_validity_action(event)

    assert recommendation.withdrawal_review_required is True
    assert recommendation.human_review_required is True


def test_withdrawal_record_requires_actor_reason_and_audit_event() -> None:
    monitor_ref = _ref("2", kind="scientist.governance_monitor_event")
    withdrawal = build_withdrawal_record(
        withdrawal_id="withdrawal_1",
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        actor_id="reviewer_1",
        reason="Withdraw after incident review.",
        audit_event_ref=_ref("3", kind="scientist.audit_event"),
        monitor_event_refs=[monitor_ref],
    )

    assert withdrawal.status.value == "withdrawn"
    assert withdrawal.actor_id == "reviewer_1"
    assert withdrawal.monitor_event_refs == [monitor_ref]

    with pytest.raises(ValidationError):
        build_withdrawal_record(
            withdrawal_id="withdrawal_2",
            decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
            actor_id="",
            reason="Missing actor.",
            audit_event_ref=_ref("3", kind="scientist.audit_event"),
            monitor_event_refs=[monitor_ref],
        )

    with pytest.raises(ValidationError):
        build_withdrawal_record(
            withdrawal_id="withdrawal_3",
            decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
            actor_id="reviewer_1",
            reason="",
            audit_event_ref=_ref("3", kind="scientist.audit_event"),
            monitor_event_refs=[monitor_ref],
        )


def test_incident_and_withdrawal_records_persist_to_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    incident = IncidentReport(
        incident_id="incident_1",
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        severity=IncidentSeverity.WARNING,
        reason="Reviewer found a post-publication issue.",
        affected_claim_ids=["claim_1"],
    )
    incident_ref = persist_incident_report(store, incident)
    withdrawal = build_withdrawal_record(
        withdrawal_id="withdrawal_1",
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        actor_id="reviewer_1",
        reason="Withdraw after incident review.",
        audit_event_ref=_ref("3", kind="scientist.audit_event"),
        monitor_event_refs=[_ref("2", kind="scientist.governance_monitor_event")],
    )
    withdrawal_ref = persist_withdrawal_record(store, withdrawal)

    assert load_incident_report(store, incident_ref) == incident
    assert load_withdrawal_record(store, withdrawal_ref) == withdrawal
    assert incident_ref.kind == "scientist.incident_report"
    assert withdrawal_ref.kind == "scientist.withdrawal_record"
