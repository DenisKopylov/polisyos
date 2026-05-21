from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime, timedelta

from polisyos.runtime.quality.diagnostic_slos import (
    DIAGNOSTIC_SLO_METRIC_IDS,
    build_diagnostic_slo_report,
    build_diagnostic_slo_report_from_quality_context,
    diagnostic_slo_gates,
    pass_observations_for_all_diagnostic_slos,
)


def test_diagnostic_slo_report_covers_every_phase_44_metric() -> None:
    observed_at = datetime(2026, 5, 15, 8, 30, tzinfo=UTC)

    report = build_diagnostic_slo_report(
        observations=pass_observations_for_all_diagnostic_slos(
            observed_at=observed_at,
            evidence_ref="cas://sha256/" + "a" * 64,
        ),
        run_id="R_hds",
        owner="team-assurance",
        now=observed_at,
    )

    assert report["status"] == "pass"
    assert report["readiness_decision"] == "pass"
    assert {metric["metric_id"] for metric in report["metrics"]} == set(
        DIAGNOSTIC_SLO_METRIC_IDS
    )
    assert report["error_budget_policy"]["decision"] == "pass"
    assert diagnostic_slo_gates(report, canary_kind="production", now=observed_at) == []


def test_missing_stale_and_over_budget_slos_block_serious_closeout() -> None:
    now = datetime(2026, 5, 15, 8, 30, tzinfo=UTC)
    stale_at = now - timedelta(days=3)
    observations = pass_observations_for_all_diagnostic_slos(
        observed_at=now,
        evidence_ref="cas://sha256/" + "a" * 64,
    )
    observations.pop("evidence_completeness")
    observations["false_pass_rate_from_negative_controls"] = {
        "value": 0.2,
        "observed_at": now.isoformat(),
        "evidence_ref": "cas://sha256/" + "b" * 64,
    }
    observations["trace_continuity"] = {
        "value": 1.0,
        "observed_at": stale_at.isoformat(),
        "evidence_ref": "cas://sha256/" + "c" * 64,
    }

    report = build_diagnostic_slo_report(
        observations=observations,
        run_id="R_hds",
        owner="team-assurance",
        now=now,
    )
    gates = diagnostic_slo_gates(report, canary_kind="production", now=now)

    assert report["status"] == "fail"
    assert report["readiness_decision"] == "quarantine_closeout"
    assert {blocker["code"] for blocker in report["blockers"]} >= {
        "diagnostic_slo_evidence_missing",
        "diagnostic_slo_evidence_stale",
        "diagnostic_slo_error_budget_burned",
    }
    assert {gate["code"] for gate in gates} >= {
        "diagnostic_slo_evidence_missing",
        "diagnostic_slo_evidence_stale",
        "diagnostic_slo_error_budget_burned",
    }


def test_observed_self_deception_failure_requires_active_fitness_control() -> None:
    now = datetime(2026, 5, 15, 8, 30, tzinfo=UTC)
    report = build_diagnostic_slo_report(
        observations=pass_observations_for_all_diagnostic_slos(
            observed_at=now,
            evidence_ref="cas://sha256/" + "d" * 64,
        ),
        observed_self_deception_failures=["new_false_pass_mode"],
        fitness_registry_payload={
            "fitness_functions": [
                {
                    "fitness_id": "fitness.retired",
                    "fitness_type": "negative_control",
                    "failure_code": "new_false_pass_mode",
                    "retired_by_adr": "ADR-9999",
                }
            ]
        },
        run_id="R_hds",
        owner="team-assurance",
        now=now,
    )

    assert report["status"] == "fail"
    assert report["fitness_registry"]["missing_active_controls"] == [
        "new_false_pass_mode"
    ]
    assert {
        blocker["code"] for blocker in report["blockers"]
    } >= {"diagnostic_fitness_control_missing"}


def test_context_builder_requires_real_control_and_redaction_observations() -> None:
    now = datetime(2026, 5, 15, 8, 30, tzinfo=UTC)
    report = build_diagnostic_slo_report_from_quality_context(
        quality_evidence={
            "policy_grounding_matrix": {
                "claims": [{"claim_id": "rec_1", "data_refs": ["dataset"]}]
            },
            "fabric_retrieval_trace": {"candidate_sources": []},
        },
        required_report_keys=("policy_grounding_matrix", "fabric_retrieval_trace"),
        required_runtime_ref_keys=("policy_grounding_matrix_ref",),
        runtime_refs={"policy_grounding_matrix_ref": "cas://sha256/" + "1" * 64},
        evidence_bundle_path="bundle",
        now=now,
    )

    missing_metrics = {
        metric["metric_id"] for metric in report["metrics"] if metric["status"] == "missing"
    }
    assert {
        "blocker_precision",
        "blocker_recall",
        "false_pass_rate_from_negative_controls",
        "false_block_rate_from_positive_controls",
        "redaction_coverage",
        "operator_time_to_root_cause",
    } <= missing_metrics
    assert "diagnostic_slo_evidence_missing" in {
        blocker["code"] for blocker in report["blockers"]
    }


def test_context_builder_accepts_explicit_wave4_slo_observations() -> None:
    now = datetime(2026, 5, 15, 8, 30, tzinfo=UTC)
    explicit = pass_observations_for_all_diagnostic_slos(
        observed_at=now,
        evidence_ref="cas://sha256/" + "9" * 64,
    )

    report = build_diagnostic_slo_report_from_quality_context(
        quality_evidence={
            "policy_grounding_matrix": {"claims": []},
            "diagnostic_slo_observations": explicit,
        },
        required_report_keys=("policy_grounding_matrix",),
        required_runtime_ref_keys=(),
        runtime_refs={},
        evidence_bundle_path="bundle",
        now=now,
    )

    assert report["status"] == "pass"
