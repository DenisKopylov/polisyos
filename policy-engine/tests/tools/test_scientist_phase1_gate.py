from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_phase1_gate


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


def _write_junit_xml(path: Path, names: list[str | tuple[str, str]]) -> None:
    testcases = "\n".join(
        (
            f'    <testcase classname="{item[0]}" name="{item[1]}" />'
            if isinstance(item, tuple)
            else f'    <testcase classname="scientist.phase1" name="{item}" />'
        )
        for item in names
    )
    path.write_text(
        "<testsuite name=\"scientist-phase1\">"
        f"\n{testcases}\n"
        "</testsuite>\n",
        encoding="utf-8",
    )


def _write_source_tree(repo_root: Path) -> None:
    targets = [
        "src/polisyos/scientist/agent/code_verifier.py",
        "src/polisyos/scientist/agent/data_need_extractor.py",
        "src/polisyos/scientist/agent/drafter_factory.py",
        "src/polisyos/scientist/agent/_drafter_formatting.py",
        "src/polisyos/scientist/agent/router.py",
        "src/polisyos/scientist/agent/supervisor.py",
        "src/polisyos/scientist/agent/rag.py",
        "src/polisyos/scientist/agent/norm_loader.py",
        "src/polisyos/scientist/autotune/execution_plan.py",
        "src/polisyos/scientist/autotune/calibration.py",
        "src/polisyos/scientist/cross_graph/compiler.py",
        "src/polisyos/scientist/cross_graph/gatherers/academic.py",
        "src/polisyos/scientist/search/funnel/level2_causal.py",
        "src/polisyos/scientist/nodes/builtins/decide/run_policy_translation.py",
        "src/polisyos/scientist/nodes/builtins/decide/run_translator_compliance.py",
        "src/polisyos/scientist/workflows/builder.py",
        "src/polisyos/scientist/engine/state_branching.py",
        "src/polisyos/scientist/remediation_status.py",
    ]
    for relative_path in targets:
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def marker() -> None:\n    return None\n", encoding="utf-8")


def test_scientist_phase1_gate_builds_passing_json_report(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    benchmark_json = repo_root / "benchmarks.json"
    junit_xml = repo_root / "phase1.xml"
    output_json = repo_root / "phase1-gate.json"
    repo_root.mkdir()
    _write_source_tree(repo_root)
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
        junit_xml,
        [
            "test_scientist_remediation_status_report_covers_all_workstreams",
            "test_scientist_remediation_status_report_is_machine_readable",
            "test_scientist_remediation_status_report_marks_all_workstreams_done",
            "test_extract_data_needs_json_parse_assertion_is_not_swallowed",
            "test_catalog_lookup_assertion_is_not_swallowed",
            "test_cas_norm_loader_assertion_is_not_swallowed",
            "test_create_drafter_agent_rag_assertion_is_not_swallowed",
            ("scientist.phase1.TestBuildConstitution", "test_assertion_is_not_swallowed"),
            ("scientist.phase1.TestAgentFallbackChain", "test_assertion_is_not_swallowed"),
            "test_parallel_assertion_is_not_swallowed",
            "test_load_allowed_modules_assertion_is_not_swallowed",
            "test_supervisor_provenance_export_assertion_is_not_swallowed",
            "test_rag_build_from_cas_manifest_assertion_is_not_swallowed",
            "test_cross_graph_compiler_legal_assertion_is_not_swallowed",
            "test_serialize_value_assertion_is_not_swallowed",
            "test_with_topology_mutation_does_not_swallow_registry_assertion",
            "test_coerce_context_data_does_not_swallow_assertion",
            "test_apply_to_config_uses_branch_local_nested_model_clones",
            "test_policy_translation_uses_branch_state_for_declared_outputs",
            "test_translator_compliance_uses_branch_state_for_declared_outputs",
            "test_workflow_runners_use_branch_local_snapshot_state[run_default_workflow-scientist_default]",
            "test_ledger_mutation_uses_copy_on_write_budget_state",
            "test_linear_scientist_workflow_happy_path",
            "test_linear_scientist_workflow_tool_failure_retries_and_succeeds",
            "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes",
            "test_linear_scientist_workflow_governance_rejection_stops_decision_publication",
            "test_linear_scientist_workflow_post_deploy_regression_triggers_alerts_and_reissue",
            "test_metrics_exporter_operational_signal",
            "test_trace_correlation_operational_signal",
            "test_dlq_replay_operational_signal",
            "test_bounded_retention_operational_signal",
            "test_monitoring_alerts_operational_signal",
        ],
    )

    exit_code = check_scientist_phase1_gate.main(
        [
            "--benchmark-json",
            str(benchmark_json),
            "--junit-xml",
            str(junit_xml),
            "--repo-root",
            str(repo_root),
            "--output",
            str(output_json),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["assessment_id"] == "scientist_phase1_gate"
    assert payload["passes_all"] is True
    assert payload["reliability_scorecard"]["passes_all"] is True
    assert payload["ratchet_results"]["critical_broad_exception_targets_clean"] is True
    assert payload["ratchet_results"]["no_live_model_copy_deep_true_hot_paths"] is True


def test_scientist_phase1_gate_matches_parametrized_cases_for_required_names(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    benchmark_json = repo_root / "benchmarks.json"
    junit_xml = repo_root / "phase1.xml"
    output_json = repo_root / "phase1-gate.json"
    repo_root.mkdir()
    _write_source_tree(repo_root)
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
        junit_xml,
        [
            "test_scientist_remediation_status_report_covers_all_workstreams",
            "test_scientist_remediation_status_report_is_machine_readable",
            "test_scientist_remediation_status_report_marks_all_workstreams_done",
            "test_extract_data_needs_json_parse_assertion_is_not_swallowed",
            "test_catalog_lookup_assertion_is_not_swallowed",
            "test_cas_norm_loader_assertion_is_not_swallowed",
            "test_create_drafter_agent_rag_assertion_is_not_swallowed",
            ("scientist.phase1.TestBuildConstitution", "test_assertion_is_not_swallowed"),
            ("scientist.phase1.TestAgentFallbackChain", "test_assertion_is_not_swallowed"),
            "test_parallel_assertion_is_not_swallowed",
            "test_load_allowed_modules_assertion_is_not_swallowed",
            "test_supervisor_provenance_export_assertion_is_not_swallowed",
            "test_rag_build_from_cas_manifest_assertion_is_not_swallowed",
            "test_cross_graph_compiler_legal_assertion_is_not_swallowed",
            "test_serialize_value_assertion_is_not_swallowed",
            "test_with_topology_mutation_does_not_swallow_registry_assertion",
            "test_coerce_context_data_does_not_swallow_assertion",
            "test_apply_to_config_uses_branch_local_nested_model_clones",
            "test_policy_translation_uses_branch_state_for_declared_outputs",
            "test_translator_compliance_uses_branch_state_for_declared_outputs",
            "test_workflow_runners_use_branch_local_snapshot_state[run_default_workflow-scientist_default]",
            "test_ledger_mutation_uses_copy_on_write_budget_state",
            "test_linear_scientist_workflow_happy_path",
            "test_linear_scientist_workflow_tool_failure_retries_and_succeeds",
            "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes",
            "test_linear_scientist_workflow_governance_rejection_stops_decision_publication",
            "test_linear_scientist_workflow_post_deploy_regression_triggers_alerts_and_reissue",
            "test_metrics_exporter_operational_signal",
            "test_trace_correlation_operational_signal",
            "test_dlq_replay_operational_signal",
            "test_bounded_retention_operational_signal",
            "test_monitoring_alerts_operational_signal",
        ],
    )

    exit_code = check_scientist_phase1_gate.main(
        [
            "--benchmark-json",
            str(benchmark_json),
            "--junit-xml",
            str(junit_xml),
            "--repo-root",
            str(repo_root),
            "--output",
            str(output_json),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["passes_all"] is True


def test_scientist_phase1_gate_fails_on_missing_evidence_and_broad_handlers(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    benchmark_json = repo_root / "benchmarks.json"
    junit_xml = repo_root / "phase1.xml"
    output_json = repo_root / "phase1-gate.json"
    repo_root.mkdir()
    _write_source_tree(repo_root)
    (repo_root / "src/polisyos/scientist/agent/code_verifier.py").write_text(
        "try:\n    pass\nexcept Exception:\n    pass\n",
        encoding="utf-8",
    )
    _write_benchmark_json(benchmark_json, ["test_scientist_node_chain_latency"])
    _write_junit_xml(
        junit_xml,
        [
            "test_scientist_remediation_status_report_covers_all_workstreams",
            "test_linear_scientist_workflow_happy_path",
        ],
    )

    exit_code = check_scientist_phase1_gate.main(
        [
            "--benchmark-json",
            str(benchmark_json),
            "--junit-xml",
            str(junit_xml),
            "--repo-root",
            str(repo_root),
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
    assert "broad_exception:src/polisyos/scientist/agent/code_verifier.py:3" in payload["notes"]
    assert "machine_readable_status:test_scientist_remediation_status_report_is_machine_readable" in payload["notes"]
    assert any(item.startswith("reliability:scenario_missing:tool_failure_with_retry") for item in payload["notes"])
