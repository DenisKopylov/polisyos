from __future__ import annotations

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.continuous.monitors import build_drift_monitor_event
from polisyos.scientist.governance.continuous.reports import (
    build_validity_report,
    export_public_validity_report,
    load_validity_report,
    persist_validity_report,
)


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/json",
    )


def test_validity_report_public_export_redacts_internal_refs() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        event_type="fairness_drift",
        severity="warning",
        reason="Fairness drift requires reviewer triage.",
        affected_claim_ids=["claim_1"],
    )
    report = build_validity_report(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        monitor_events=[event],
        hidden_internal_ref_ids=["hidden_holdout_suite_42"],
        metadata={"internal_monitor_ref": "hidden_eval_answer_ref"},
    )

    public = export_public_validity_report(report)

    assert public["status"] == "review_required"
    assert public["event_count"] == 1
    assert "hidden_holdout_suite_42" not in str(public)
    assert "internal_monitor_ref" not in str(public)


def test_public_export_rejects_hidden_decision_packet_ref() -> None:
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        event_type="calibration_drift",
        severity="info",
        reason="Calibration is being monitored.",
    )
    report = build_validity_report(
        decision_packet_ref=ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="scientist.hidden_eval.decision_packet",
            media_type="application/json",
        ),
        monitor_events=[event],
    )

    with pytest.raises(ValueError, match="hidden/internal"):
        export_public_validity_report(report)


def test_validity_report_persists_to_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    event = build_drift_monitor_event(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        event_type="policy_context_drift",
        severity="warning",
        reason="Policy context changed.",
        affected_claim_ids=["claim_1"],
    )
    report = build_validity_report(
        decision_packet_ref=_ref("1", kind="scientist.decision_packet"),
        monitor_events=[event],
        reissue_packet_ref=_ref("2", kind="scientist.reissue_packet"),
    )

    ref = persist_validity_report(store, report)
    loaded = load_validity_report(store, ref)

    assert loaded == report
    assert ref.kind == "scientist.continuous_governance_report"
