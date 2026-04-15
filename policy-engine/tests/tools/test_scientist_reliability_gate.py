from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_reliability


def _write_benchmark_json(path: Path, names: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "benchmarks": [
                    {
                        "name": name,
                        "stats": {
                            "mean": 1.0,
                            "stddev": 0.1,
                            "min": 0.9,
                            "max": 1.1,
                            "rounds": 5,
                        },
                    }
                    for name in names
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_junit_xml(path: Path, names: list[str]) -> None:
    testcases = "\n".join(
        f'    <testcase classname="scientist.evidence" name="{name}" />'
        for name in names
    )
    path.write_text(
        "<testsuite name=\"scientist\">"
        f"\n{testcases}\n"
        "</testsuite>\n",
        encoding="utf-8",
    )


def test_scientist_reliability_gate_builds_passing_json_scorecard(tmp_path: Path) -> None:
    benchmark_json = tmp_path / "benchmarks.json"
    scenario_xml = tmp_path / "scenarios.xml"
    operational_xml = tmp_path / "operational.xml"
    output_json = tmp_path / "scorecard.json"
    _write_benchmark_json(
        benchmark_json,
        [
            "test_scientist_node_chain_latency",
            "test_scientist_checkpoint_io_hot_path",
            "test_scientist_state_serialization_hot_path",
            "test_scientist_state_branch_hot_path",
            "test_scientist_fan_out_merge_hot_path",
            "test_scientist_failure_index_search_hot_path",
            "test_scientist_search_pareto_hot_path",
        ],
    )
    _write_junit_xml(
        scenario_xml,
        [
            "test_linear_scientist_workflow_happy_path",
            "test_linear_scientist_workflow_tool_failure_retries_and_succeeds",
            "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes",
            "test_linear_scientist_workflow_governance_rejection_stops_decision_publication",
            "test_linear_scientist_workflow_post_deploy_regression_triggers_alerts_and_reissue",
        ],
    )
    _write_junit_xml(
        operational_xml,
        [
            "test_metrics_exporter_operational_signal",
            "test_trace_correlation_operational_signal",
            "test_dlq_replay_operational_signal",
            "test_bounded_retention_operational_signal",
            "test_monitoring_alerts_operational_signal",
        ],
    )

    exit_code = check_scientist_reliability.main(
        [
            "--benchmark-json",
            str(benchmark_json),
            "--junit-xml",
            str(scenario_xml),
            "--junit-xml",
            str(operational_xml),
            "--output",
            str(output_json),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["assessment_id"] == "scientist_gate2_reliability"
    assert payload["passes_all"] is True
    assert payload["scenario_results"]["happy_path"] is True
    assert payload["benchmark_results"]["fan_out_merge"] is True
    assert payload["operational_results"]["dlq_replay"] is True


def test_scientist_reliability_gate_fails_when_required_evidence_is_missing(
    tmp_path: Path,
) -> None:
    benchmark_json = tmp_path / "benchmarks.json"
    scenario_xml = tmp_path / "scenarios.xml"
    output_json = tmp_path / "scorecard.json"
    _write_benchmark_json(benchmark_json, ["test_scientist_node_chain_latency"])
    _write_junit_xml(scenario_xml, ["test_linear_scientist_workflow_happy_path"])

    exit_code = check_scientist_reliability.main(
        [
            "--benchmark-json",
            str(benchmark_json),
            "--junit-xml",
            str(scenario_xml),
            "--output",
            str(output_json),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["passes_all"] is False
    assert "scenario_missing:tool_failure_with_retry" in payload["notes"]
    assert "operational_gap:metrics_exporter" in payload["notes"]
