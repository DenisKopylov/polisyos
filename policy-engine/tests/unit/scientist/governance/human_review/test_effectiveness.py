from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.human_review.effectiveness import (
    build_review_effectiveness_report,
    load_review_effectiveness_report,
    persist_review_effectiveness_report,
    review_effectiveness_public_export,
)
from polisyos.scientist.methods.search.voi_models import (
    VOIDecisionRecord,
    VOIDecisionType,
)


def _human_escalation(decision_id: str, metadata: dict[str, object]) -> VOIDecisionRecord:
    return VOIDecisionRecord(
        decision_id=decision_id,
        run_id="run_review_effectiveness",
        decision_type=VOIDecisionType.HUMAN_ESCALATION,
        recommended_action="request_human_review",
        expected_value=0.4,
        expected_cost=0.1,
        expected_risk_reduction=0.5,
        explanation="Human review requested for elevated policy risk.",
        metadata=metadata,
    )


def test_effectiveness_pipeline_measures_voi_metadata_as_advisory_only() -> None:
    report = build_review_effectiveness_report(
        voi_decisions=[
            _human_escalation(
                "voi_override",
                {
                    "review_outcome": "override",
                    "expected_outcome": "reject",
                    "reviewer_identity": "producer@example.test",
                    "producer_identity": "producer@example.test",
                    "reviewer_independent": False,
                    "separation_of_duty_attested": False,
                    "time_spent_seconds": 45,
                    "dissent": False,
                    "change_request_count": 0,
                    "override_correct": False,
                    "completed_at": "2026-05-24T09:00:00+00:00",
                },
            ),
            _human_escalation(
                "voi_no_delta",
                {
                    "review_outcome": "approve",
                    "expected_outcome": "approve",
                    "reviewer_id": "reviewer.beta@example.test",
                    "producer_id": "producer.beta@example.test",
                    "reviewer_independent": True,
                    "separation_of_duty_attested": False,
                    "review_time_seconds": 30,
                    "approved_without_change": True,
                    "dissent": False,
                    "requested_changes": [],
                    "completed_at": "2026-05-24T09:04:00+00:00",
                },
            ),
        ],
        run_id="run_review_effectiveness",
        now=datetime(2026, 5, 24, 9, 10, tzinfo=UTC),
    )

    assert report.status == "pass"
    assert report.threshold_status == "fail"
    assert report.measured_event_count == 2
    assert report.source_decision_ids == ["voi_no_delta", "voi_override"]
    assert report.observation_gap_decision_ids == []

    telemetry = report.review_effectiveness_telemetry
    assert telemetry["posture"] == "advisory"
    assert telemetry["blocking_permitted"] is False
    assert telemetry["report_status_effect"] == "pass_advisory_only"
    assert telemetry["authority_boundary"]["may_not_use_for"] == [
        "current_run_closeout_block",
        "publication_block",
        "claim_support_downgrade",
    ]

    measured = telemetry["measured_signals"]
    assert measured["review_time_seconds_average"] == 37.5
    assert measured["low_time_review_count"] == 2
    assert measured["override_rate"] == 0.5
    assert measured["override_count"] == 1
    assert measured["no_delta_review_count"] == 1
    assert measured["separation_of_duty_failure_count"] == 2

    note_codes = {note.code for note in report.advisory_notes}
    assert "override_rate_above_warn_threshold" in note_codes
    assert "separation_of_duty_below_fail_threshold" in note_codes
    assert {note.blocking for note in report.advisory_notes} == {False}


def test_missing_observed_review_metadata_is_visible_but_non_blocking() -> None:
    report = build_review_effectiveness_report(
        voi_decisions=[
            _human_escalation(
                "voi_requirement_only",
                {
                    "required": True,
                    "reviewer_independence_required": True,
                    "separation_of_duty_required": True,
                    "minimum_time_spent_seconds": 300,
                    "require_change_request_or_dissent": True,
                },
            ),
            VOIDecisionRecord(
                decision_id="voi_source",
                run_id="run_review_effectiveness",
                decision_type=VOIDecisionType.SOURCE_VERIFICATION,
                recommended_action="defer",
                expected_value=-0.1,
                expected_cost=0.0,
                expected_risk_reduction=0.0,
                explanation="Not a human review escalation.",
            ),
        ],
        run_id="run_review_effectiveness",
        now=datetime(2026, 5, 24, 9, 10, tzinfo=UTC),
    )

    assert report.status == "pass"
    assert report.threshold_status == "pass"
    assert report.measured_event_count == 0
    assert report.ignored_decision_ids == ["voi_source"]
    assert report.observation_gap_decision_ids == ["voi_requirement_only"]
    assert report.review_effectiveness_telemetry["measured_signals"]["review_count"] == 0

    assert [note.code for note in report.advisory_notes] == [
        "review_effectiveness_observation_missing"
    ]
    assert report.advisory_notes[0].blocking is False
    assert report.advisory_notes[0].authority_effect == "advisory_measurement"


def test_effectiveness_report_round_trips_through_cas_public_surface(tmp_path) -> None:
    report = build_review_effectiveness_report(
        voi_decisions=[
            _human_escalation(
                "voi_persisted",
                {
                    "review_outcome": "approve",
                    "reviewer_identity": "reviewer@example.test",
                    "time_spent_seconds": 180,
                    "separation_of_duty_attested": True,
                    "dissent": True,
                    "private_notes": "raw reviewer note must not leak",
                },
            )
        ],
        run_id="run_review_effectiveness",
        now=datetime(2026, 5, 24, 9, 10, tzinfo=UTC),
    )

    store = FileSystemCAS(tmp_path)
    ref = persist_review_effectiveness_report(store, report)
    loaded = load_review_effectiveness_report(store, ref)

    assert loaded == report
    public_export = review_effectiveness_public_export(loaded)
    assert public_export["schema_version"] == report.schema_version
    assert public_export["review_effectiveness_telemetry"]["posture"] == "advisory"
    assert "raw reviewer note" not in str(public_export)
