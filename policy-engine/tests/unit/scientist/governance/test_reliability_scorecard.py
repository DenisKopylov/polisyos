from __future__ import annotations

import pytest

from polisyos.scientist.validation.reliability_scorecard import (
    BENCHMARK_EVIDENCE_CASES,
    OPERATIONAL_EVIDENCE_CASES,
    REQUIRED_BENCHMARKS,
    REQUIRED_OPERATIONAL_SIGNALS,
    REQUIRED_SCENARIOS,
    SCENARIO_EVIDENCE_CASES,
    build_scientist_reliability_scorecard,
    build_scientist_reliability_scorecard_from_evidence,
)


def test_scientist_reliability_scorecard_passes_when_all_required_evidence_is_present() -> None:
    scorecard = build_scientist_reliability_scorecard(
        scenario_results=dict.fromkeys(REQUIRED_SCENARIOS, True),
        benchmark_results=dict.fromkeys(REQUIRED_BENCHMARKS, True),
        operational_results=dict.fromkeys(REQUIRED_OPERATIONAL_SIGNALS, True),
    )

    assert scorecard.passes_all is True
    assert scorecard.weighted_score == 1.0
    assert scorecard.notes == []


def test_scientist_reliability_scorecard_records_missing_gates() -> None:
    scorecard = build_scientist_reliability_scorecard(
        scenario_results={"happy_path": True},
        benchmark_results={"node_latency": True},
        operational_results={"metrics_exporter": True},
    )

    assert scorecard.passes_all is False
    assert scorecard.scenario_results["checkpoint_resume"] is False
    assert scorecard.benchmark_results["fan_out_merge"] is False
    assert scorecard.operational_results["monitoring_alerts"] is False
    assert "scenario_missing:checkpoint_resume" in scorecard.notes
    assert "benchmark_missing:fan_out_merge" in scorecard.notes
    assert "operational_gap:monitoring_alerts" in scorecard.notes


def test_scientist_reliability_scorecard_from_evidence_maps_required_cases() -> None:
    scorecard = build_scientist_reliability_scorecard_from_evidence(
        passed_test_cases={
            *SCENARIO_EVIDENCE_CASES["happy_path"],
            *SCENARIO_EVIDENCE_CASES["tool_failure_with_retry"],
            *SCENARIO_EVIDENCE_CASES["checkpoint_resume"],
            *SCENARIO_EVIDENCE_CASES["governance_rejection"],
            *SCENARIO_EVIDENCE_CASES["fairness_calibration_regression"],
            *OPERATIONAL_EVIDENCE_CASES["metrics_exporter"],
            *OPERATIONAL_EVIDENCE_CASES["trace_correlation"],
            *OPERATIONAL_EVIDENCE_CASES["dlq_replay"],
            *OPERATIONAL_EVIDENCE_CASES["bounded_retention"],
            *OPERATIONAL_EVIDENCE_CASES["monitoring_alerts"],
        },
        benchmark_names={
            BENCHMARK_EVIDENCE_CASES["node_latency"][0],
            BENCHMARK_EVIDENCE_CASES["checkpoint_io"][0],
            BENCHMARK_EVIDENCE_CASES["state_serialization"][0],
            BENCHMARK_EVIDENCE_CASES["state_copy"][0],
            BENCHMARK_EVIDENCE_CASES["fan_out_merge"][0],
            BENCHMARK_EVIDENCE_CASES["failure_index_search"][0],
            BENCHMARK_EVIDENCE_CASES["search_pareto"][0],
        },
    )

    payload = scorecard.to_dict()

    assert scorecard.passes_all is True
    assert payload["scenario_evidence"]["happy_path"] == [
        "test_linear_scientist_workflow_happy_path"
    ]
    assert payload["scenario_evidence"]["checkpoint_resume"] == [
        "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes[incomplete]"
    ]
    assert payload["operational_evidence"]["metrics_exporter"] == [
        "test_metrics_exporter_operational_signal"
    ]


def test_scientist_reliability_scorecard_counts_successful_checkpoint_resume_parameter() -> None:
    expected_case = (
        "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes[incomplete]"
    )
    assert SCENARIO_EVIDENCE_CASES["checkpoint_resume"] == (expected_case,)

    scorecard = build_scientist_reliability_scorecard_from_evidence(
        passed_test_cases={expected_case},
        benchmark_names=set(),
    )

    assert scorecard.scenario_results["checkpoint_resume"] is True
    assert "scenario_missing:checkpoint_resume" not in scorecard.notes


@pytest.mark.parametrize(
    "observed_case",
    [
        "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes",
        "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes[terminal]",
        "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes[corrupt_registry]",
        "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes[unbound_registry]",
        "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes_nearby[incomplete]",
    ],
)
def test_scientist_reliability_scorecard_rejects_nonpositive_checkpoint_resume_evidence(
    observed_case: str,
) -> None:
    scorecard = build_scientist_reliability_scorecard_from_evidence(
        passed_test_cases={observed_case},
        benchmark_names=set(),
    )

    assert scorecard.scenario_results["checkpoint_resume"] is False
    assert "scenario_missing:checkpoint_resume" in scorecard.notes


def test_scientist_reliability_scorecard_from_evidence_marks_missing_inputs() -> None:
    scorecard = build_scientist_reliability_scorecard_from_evidence(
        passed_test_cases={"test_linear_scientist_workflow_happy_path"},
        benchmark_names={"test_scientist_node_chain_latency"},
    )

    assert scorecard.passes_all is False
    assert scorecard.scenario_results["tool_failure_with_retry"] is False
    assert scorecard.operational_results["metrics_exporter"] is False
    assert "scenario_missing:tool_failure_with_retry" in scorecard.notes
    assert "operational_gap:metrics_exporter" in scorecard.notes
