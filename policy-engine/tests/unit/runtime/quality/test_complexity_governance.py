from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime, timedelta

from polisyos.runtime.quality.complexity_governance import (
    COMPLEXITY_GOVERNANCE_SCHEMA_VERSION,
    build_complexity_governance_report,
    complexity_governance_scorecard_gates,
    compute_net_mav,
    evaluate_blocking_frontier_control,
    review_controls_for_pruning,
)
from tests._helpers.hds_quality import complete_quality_evidence, scorecard_for


def _telemetry(
    *,
    generated_at: datetime,
    prune_decisions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.soft_gate_telemetry.v1",
        "run_id": "R_complexity",
        "job_id": "job-complexity",
        "generated_at": generated_at.isoformat(),
        "complexity_budget_telemetry": {
            "input_source": "runtime_telemetry",
            "status": "advisory_over_budget" if prune_decisions else "advisory_within_budget",
            "authority_effect": "advisory_complexity_budget",
            "measurements": {
                "gate_count": 3,
                "warning_count": 1,
                "tool_count": 2,
                "repair_decision_count": 1,
                "repair_fmea_annotation_count": 1,
                "review_count": 1,
                "total_actual_cost_usd": 12.5,
                "elapsed_seconds": 120.0,
                "human_review_hours": 0.5,
            },
            "prune_or_merge_decisions": prune_decisions or [],
        },
    }


def test_net_mav_formula_subtracts_cost_and_block_penalties() -> None:
    assert compute_net_mav(
        decision_gain=4.0,
        falsification_value=3.0,
        authority_gain=2.0,
        auditability_gain=1.0,
        human_time_cost=0.5,
        latency_penalty=0.25,
        rerun_penalty=0.75,
        false_block_penalty=1.0,
    ) == 7.5


def test_new_blocking_frontier_control_requires_net_mav_and_telemetry_refs() -> None:
    decision = evaluate_blocking_frontier_control(
        {
            "control_id": "new_authority_gate",
            "owner": "team-runtime-quality",
            "frontier": "blocking",
        }
    )

    assert decision["can_enter_blocking_frontier"] is False
    assert decision["status"] == "rejected"
    assert {
        "expected_net_mav_missing",
        "telemetry_refs_missing",
    } <= {issue["code"] for issue in decision["issues"]}


def test_new_blocking_frontier_control_rejects_non_positive_net_mav() -> None:
    decision = evaluate_blocking_frontier_control(
        {
            "control_id": "zero_value_gate",
            "owner": "team-runtime-quality",
            "frontier": "blocking",
            "expected_net_mav": 0.0,
            "telemetry_refs": ["artifact://runtime/soft-gate-telemetry/R_complexity"],
        }
    )

    assert decision["can_enter_blocking_frontier"] is False
    assert decision["expected_net_mav"] == 0.0
    assert {issue["code"] for issue in decision["issues"]} == {
        "expected_net_mav_non_positive"
    }


def test_new_blocking_frontier_control_with_positive_net_mav_and_refs_is_admitted() -> None:
    decision = evaluate_blocking_frontier_control(
        {
            "control_id": "new_authority_gate",
            "owner": "team-runtime-quality",
            "frontier": "blocking",
            "decision_gain": 3.0,
            "falsification_value": 2.0,
            "authority_gain": 1.0,
            "auditability_gain": 1.0,
            "human_time_cost": 0.5,
            "latency_penalty": 0.25,
            "rerun_penalty": 0.25,
            "false_block_penalty": 0.5,
            "telemetry_refs": [
                "artifact://runtime/soft-gate-telemetry/R_complexity",
                "event://runtime/complexity/new-authority-gate",
            ],
        }
    )

    assert decision["can_enter_blocking_frontier"] is True
    assert decision["status"] == "admitted"
    assert decision["expected_net_mav"] == 5.5
    assert decision["mav_components"]["decision_gain"] == 3.0


def test_periodic_prune_review_marks_inactive_controls_after_measurement_window() -> None:
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    review = review_controls_for_pruning(
        [
            {
                "control_id": "duplicated_warning_gate",
                "owner": "team-quality-closeout",
                "status": "active",
                "first_measured_at": (now - timedelta(days=45)).isoformat(),
                "decision_effect_count": 0,
                "merge_candidate_with": ["provider_warning_gate"],
                "telemetry_refs": ["artifact://runtime/soft-gate-telemetry/R_complexity"],
            },
            {
                "control_id": "authority_boundary_gate",
                "owner": "team-runtime-quality",
                "status": "active",
                "first_measured_at": (now - timedelta(days=45)).isoformat(),
                "decision_effect_count": 2,
                "telemetry_refs": ["artifact://runtime/soft-gate-telemetry/R_complexity"],
            },
        ],
        generated_at=now,
        measurement_window_days=30,
    )

    by_id = {item["control_id"]: item for item in review}
    assert by_id["duplicated_warning_gate"]["recommendation"] == "merge_candidate"
    assert by_id["duplicated_warning_gate"]["decision_effect_count"] == 0
    assert by_id["authority_boundary_gate"]["recommendation"] == "retain"


def test_complexity_governance_is_itself_retirement_candidate_without_prune_decisions() -> None:
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    report = build_complexity_governance_report(
        run_id="R_complexity",
        soft_gate_telemetry=_telemetry(generated_at=now, prune_decisions=[]),
        controls=[
            {
                "control_id": "new_authority_gate",
                "owner": "team-runtime-quality",
                "frontier": "blocking",
                "expected_net_mav": 1.25,
                "telemetry_refs": ["artifact://runtime/soft-gate-telemetry/R_complexity"],
            }
        ],
        generated_at=now,
        measurement_window_started_at=now - timedelta(days=40),
        measurement_window_days=30,
    )

    assert report["schema_version"] == COMPLEXITY_GOVERNANCE_SCHEMA_VERSION
    assert report["input_source"] == "w2d_self_fmea_telemetry"
    assert report["summary"]["blocking_frontier_admitted_count"] == 1
    assert report["self_application"]["recommendation"] == "retire_candidate"
    assert report["self_application"]["reason"] == "no_prune_decisions_after_measurement_window"
    assert "claim_support" in report["authority_boundary"]["may_not_use_for"]


def test_complexity_governance_retains_itself_when_it_causes_prune_decisions() -> None:
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    report = build_complexity_governance_report(
        run_id="R_complexity",
        soft_gate_telemetry=_telemetry(
            generated_at=now,
            prune_decisions=[
                {
                    "decision": "soft_gate_warning_prune_or_merge",
                    "owner": "team-quality-closeout",
                    "measurement": "warning_count",
                    "value": 12,
                    "budget": 10,
                }
            ],
        ),
        controls=[],
        generated_at=now,
        measurement_window_started_at=now - timedelta(days=40),
        measurement_window_days=30,
    )

    assert report["self_application"]["recommendation"] == "retain"
    assert report["self_application"]["decision_effect_count"] == 1
    assert report["summary"]["prune_or_merge_candidate_count"] == 0


def test_complexity_governance_scorecard_gate_blocks_new_frontier_growth_only() -> None:
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    report = build_complexity_governance_report(
        run_id="R_complexity",
        soft_gate_telemetry=_telemetry(generated_at=now),
        controls=[
            {
                "control_id": "new_unpriced_blocking_gate",
                "owner": "team-runtime-quality",
                "frontier": "blocking",
            }
        ],
        generated_at=now,
    )

    gates = complexity_governance_scorecard_gates(
        {"complexity_governance": report}
    )

    assert gates == [
        {
            "name": "policy_design_w10e_complexity_governance",
            "stage": "governance",
            "code": "complexity_governance_blocking_frontier_rejected",
            "status": "fail",
            "layer": "runtime_quality",
            "phase": "policy_design_w10e_complexity_governance",
            "message": (
                "Complexity governance rejected proposed blocking-frontier control "
                "growth without positive Net-MAV and telemetry refs."
            ),
            "evidence_ref": "quality_evidence/complexity_governance.json",
            "next_action": (
                "Add expected Net-MAV and telemetry refs, or keep the control "
                "advisory until measured."
            ),
            "blocking": True,
            "owner": "team-runtime-quality",
            "closeout_effect": "blocking_frontier_admission_blocked",
            "current_run_closeout_effect": "none",
            "blocking_frontier_rejected_count": 1,
            "prune_or_merge_candidate_count": 0,
        }
    ]


def test_complexity_governance_report_is_consumed_by_quality_scorecard() -> None:
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    report = build_complexity_governance_report(
        run_id="R_complexity",
        soft_gate_telemetry=_telemetry(generated_at=now),
        controls=[
            {
                "control_id": "new_unpriced_blocking_gate",
                "owner": "team-runtime-quality",
                "frontier": "blocking",
            }
        ],
        generated_at=now,
    )
    evidence = complete_quality_evidence()
    evidence["complexity_governance"] = report

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "complexity_governance_blocking_frontier_rejected" in {
        gate["code"] for gate in scorecard["quality_gates"]
    }
    assert "complexity_governance_blocking_frontier_rejected" in {
        failure["code"] for failure in scorecard["blocking_quality_failures"]
    }
