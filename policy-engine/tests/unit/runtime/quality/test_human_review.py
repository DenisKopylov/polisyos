from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.runtime.quality.human_review import (
    build_human_review_calibration_report,
    deterministic_review_fixtures,
    evaluate_review_packet,
    human_review_public_export,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def test_deterministic_review_fixtures_cover_governance_outcomes_without_private_exports() -> None:
    fixtures = deterministic_review_fixtures(
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert {event["outcome"] for event in fixtures} == {
        "approve",
        "reject",
        "escalate",
        "override",
        "reissue",
        "withdraw",
    }

    report = build_human_review_calibration_report(
        review_events=fixtures,
        run_id="R_review",
        job_id="job-review",
        now=datetime(2026, 5, 13, 10, 5, tzinfo=UTC),
        report_ref=_sha("h"),
    )

    assert report["schema_version"] == "policyos.human_review_calibration_report.v1"
    assert report["human_review_calibration_report_ref"] == _sha("h")
    assert report["summary"]["review_count"] == 6
    assert report["summary"]["outcome_counts"]["withdraw"] == 1
    assert report["summary"]["unresolved_disagreement_count"] == 1
    assert report["reviewer_burden"]["total_minutes"] > 0
    assert {
        decision["reviewer_identity"]
        for decision in report["reviewer_attributed_decisions"]
    } >= {"reviewer.alpha@example.test", "reviewer.beta@example.test"}

    public_export = human_review_public_export(report)
    assert "private_notes" not in str(public_export)
    assert "raw reviewer note" not in str(public_export)
    assert public_export["summary"]["unresolved_disagreement_count"] == 1
    assert public_export["reviewer_burden"]["total_minutes"] == report["reviewer_burden"][
        "total_minutes"
    ]


def test_low_agreement_and_high_override_rate_emit_fail_quality_signals() -> None:
    events = [
        {
            "review_id": "review-1",
            "flow": "override",
            "outcome": "override",
            "expected_outcome": "reject",
            "reviewer_identity": "reviewer.alpha@example.test",
            "decision_ref": _sha("1"),
            "completed_at": "2026-05-13T10:00:00+00:00",
            "burden_minutes": 12,
            "disagreement_reason_code": "policy_scope_mismatch",
            "override_correct": False,
            "unresolved": True,
            "private_notes": "raw reviewer note: keep this internal",
        },
        {
            "review_id": "review-2",
            "flow": "override",
            "outcome": "override",
            "expected_outcome": "reject",
            "reviewer_identity": "reviewer.beta@example.test",
            "decision_ref": _sha("2"),
            "completed_at": "2026-05-13T10:05:00+00:00",
            "burden_minutes": 14,
            "disagreement_reason_code": "unsupported_exception",
            "override_correct": False,
            "unresolved": True,
        },
        {
            "review_id": "review-3",
            "flow": "approval",
            "outcome": "approve",
            "expected_outcome": "approve",
            "reviewer_identity": "reviewer.gamma@example.test",
            "decision_ref": _sha("3"),
            "completed_at": "2026-05-13T10:10:00+00:00",
            "burden_minutes": 7,
        },
    ]

    report = build_human_review_calibration_report(
        review_events=events,
        run_id="R_review",
        job_id="job-review",
        now=datetime(2026, 5, 13, 10, 15, tzinfo=UTC),
    )

    assert report["status"] == "fail"
    signals = {signal["code"]: signal for signal in report["quality_signals"]}
    assert signals["reviewer_agreement_below_fail_threshold"]["status"] == "fail"
    assert signals["override_rate_above_fail_threshold"]["status"] == "fail"
    assert signals["override_correctness_below_fail_threshold"]["status"] == "fail"
    assert signals["unresolved_disagreements_above_fail_threshold"]["status"] == "fail"
    assert report["summary"]["agreement_rate"] == 1 / 3
    assert report["summary"]["override_rate"] == 2 / 3
    assert report["disagreement_reason_codes"] == {
        "policy_scope_mismatch": 1,
        "unsupported_exception": 1,
    }


def test_nominal_approval_without_effective_oversight_is_rubber_stamp_risk() -> None:
    events = [
        {
            "review_id": "review-fast-1",
            "flow": "approval",
            "outcome": "approve",
            "expected_outcome": "approve",
            "reviewer_identity": "producer@example.test",
            "producer_identity": "producer@example.test",
            "reviewer_independent": False,
            "separation_of_duty_attested": False,
            "exposure_order": 1,
            "time_spent_seconds": 35,
            "dissent": False,
            "change_requests": [],
            "approved_without_change": True,
            "decision_ref": _sha("4"),
            "completed_at": "2026-05-13T10:00:00+00:00",
        },
        {
            "review_id": "review-fast-2",
            "flow": "approval",
            "outcome": "approve",
            "expected_outcome": "approve",
            "reviewer_identity": "producer@example.test",
            "producer_identity": "producer@example.test",
            "reviewer_independent": False,
            "separation_of_duty_attested": False,
            "exposure_order": 2,
            "time_spent_seconds": 42,
            "dissent": False,
            "change_requests": [],
            "approved_without_change": True,
            "decision_ref": _sha("5"),
            "completed_at": "2026-05-13T10:01:00+00:00",
        },
    ]

    report = build_human_review_calibration_report(
        review_events=events,
        run_id="R_review",
        job_id="job-review",
        now=datetime(2026, 5, 13, 10, 5, tzinfo=UTC),
    )

    assert report["status"] == "fail"
    assert report["summary"]["approve_without_change_rate"] == 1.0
    assert report["oversight_effectiveness"]["rubber_stamp_risk"] == "high"
    assert report["oversight_effectiveness"]["reviewer_independence_rate"] == 0.0
    assert report["producer_independence"]["separation_of_duty_attestation_rate"] == 0.0
    signals = {signal["code"]: signal["status"] for signal in report["quality_signals"]}
    assert signals["reviewer_independence_below_fail_threshold"] == "fail"
    assert signals["rubber_stamp_risk_above_fail_threshold"] == "fail"


def test_review_packet_evaluation_checks_override_completeness() -> None:
    now = datetime(2026, 5, 13, 10, 0, tzinfo=UTC)
    packet = {
        "schema_version": "policyos.production_approval_packet.v1",
        "decision": "approved_with_override",
        "run_id": "R_review",
        "job_id": "job-review",
        "generated_at": now.isoformat(),
        "override": {
            "reviewer_identity": "",
            "reason": "OK",
            "scope": "run:other",
            "expires_at": (now - timedelta(minutes=1)).isoformat(),
            "evidence_refs": [],
            "signed_at": now.isoformat(),
            "signature": "",
        },
    }

    evaluation = evaluate_review_packet(
        packet,
        expected_scope="run:R_review",
        now=now,
    )

    assert evaluation["status"] == "fail"
    checks = {check["code"]: check["status"] for check in evaluation["checks"]}
    assert checks == {
        "reviewer_attribution": "fail",
        "packet_completeness": "fail",
        "override_expiry": "fail",
        "override_scope": "fail",
        "rationale_quality": "fail",
    }

    packet["override"] = {
        "reviewer_identity": "reviewer.alpha@example.test",
        "reason": "Emergency release accepted for this run after attached evidence review.",
        "scope": "run:R_review",
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "evidence_refs": [_sha("a")],
        "signed_at": now.isoformat(),
        "signature": "sig-reviewer-alpha",
    }
    evaluation = evaluate_review_packet(
        packet,
        expected_scope="run:R_review",
        now=now,
    )

    assert evaluation["status"] == "pass"
    assert {check["status"] for check in evaluation["checks"]} == {"pass"}
