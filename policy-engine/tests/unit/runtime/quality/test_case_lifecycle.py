from __future__ import annotations

from polisyos.runtime.quality.case_lifecycle import build_lifecycle_reissue_report


def test_reissue_report_preserves_event_detection_and_replay_time_roles() -> None:
    """A scoped blocking event revises one claim without rewriting its case peer."""

    report = build_lifecycle_reissue_report(
        report_id="lifecycle-time-roles-2026-10",
        case_id="case-time-role-probe",
        claim_ids=("claim/benefit-access", "claim/fiscal-cost"),
        policy_context_events=(
            {
                "event_id": "eligibility-rule-change",
                "event_type": "policy_context_drift",
                "affected_claim_ids": ["claim/benefit-access"],
                "severity": "block",
                "reason": "A changed eligibility rule affects the benefit-access claim.",
                "evidence_ref": "sha256:" + "a" * 64,
                "runtime_event_ref": "event://policy-context/eligibility-rule-change",
                "occurred_at": "2026-04-01T00:00:00+00:00",
                "detected_at": "2026-10-02T09:30:00+00:00",
                "valid_time": "2026-04-01T00:00:00+00:00",
            },
        ),
        generated_at="2026-10-10T00:00:00+00:00",
    )

    impact = report["event_impacts"][0]
    assert impact["time_roles"] == {
        "event_time": "2026-04-01T00:00:00+00:00",
        "detection_time": "2026-10-02T09:30:00+00:00",
        "valid_time": "2026-04-01T00:00:00+00:00",
        "publication_time": None,
        "closure_time": None,
        "replay_time": "2026-10-10T00:00:00+00:00",
    }
    states = {row["claim_id"]: row for row in report["claim_revision_states"]}
    assert states["claim/benefit-access"]["current_validity"] == "revalidation_required"
    assert states["claim/fiscal-cost"]["current_validity"] == "current"
    assert report["public_revision_state"]["closed_case_historical_meaning"] == "preserved"
