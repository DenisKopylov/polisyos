from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from defusedxml.ElementTree import fromstring

from tools.ci import check_scientist_phase1_gate


def _load_gate_candidate(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("phase1_cleanup_candidate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        f'<testsuite name="scientist-phase1">\n{testcases}\n</testsuite>\n',
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
        "src/polisyos/scientist/methods/autotune/execution_plan.py",
        "src/polisyos/scientist/methods/autotune/calibration.py",
        "src/polisyos/scientist/cross_graph/compiler.py",
        "src/polisyos/scientist/cross_graph/gatherers/academic.py",
        "src/polisyos/scientist/methods/search/funnel/level2_causal.py",
        "src/polisyos/scientist/nodes/builtins/decide/run_policy_translation.py",
        "src/polisyos/scientist/nodes/builtins/decide/run_translator_compliance.py",
        "src/polisyos/scientist/orchestration/workflows/builder.py",
        "src/polisyos/scientist/orchestration/engine/state_branching.py",
        "src/polisyos/scientist/remediation_status.py",
    ]
    for relative_path in targets:
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def marker() -> None:\n    return None\n", encoding="utf-8")


def _write_complete_evidence(repo_root: Path) -> tuple[Path, Path]:
    from polisyos.scientist.validation import reliability_scorecard

    benchmark = repo_root / "bench.json"
    junit = repo_root / "cases.xml"
    _write_benchmark_json(
        benchmark,
        [
            case
            for cases in reliability_scorecard.BENCHMARK_EVIDENCE_CASES.values()
            for case in cases
        ],
    )
    _write_junit_xml(
        junit,
        [
            case
            for group in (
                check_scientist_phase1_gate.PHASE1_TEST_CASES,
                reliability_scorecard.SCENARIO_EVIDENCE_CASES,
                reliability_scorecard.OPERATIONAL_EVIDENCE_CASES,
            )
            for cases in group.values()
            for case in cases
        ],
    )
    return benchmark, junit


def _output_measurement(output: Path, output_format: str) -> dict[str, object]:
    content = output.read_text()
    if output_format == "json":
        return json.loads(content)["measurement"]
    if output_format == "junit":
        return json.loads(fromstring(content).findtext("system-out") or "{}")
    return json.loads(content.split("\nmeasurement: ", 1)[1])


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
            "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes[incomplete]",
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
    assert payload["ratchet_results"]["no_explicit_model_copy_deep_true"] is True


def test_scientist_phase1_gate_matches_parametrized_cases_for_required_names(
    tmp_path: Path,
) -> None:
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
            "test_linear_scientist_workflow_checkpoint_resume_skips_completed_nodes[incomplete]",
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
    assert (
        "machine_readable_status:test_scientist_remediation_status_report_is_machine_readable"
        in payload["notes"]
    )
    assert any(
        item.startswith("reliability:scenario_missing:tool_failure_with_retry")
        for item in payload["notes"]
    )


def test_scientist_phase1_copy_scan_uses_ast_and_reports_unresolved_calls(tmp_path: Path) -> None:
    source = tmp_path / "src/polisyos/scientist/candidate.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "# model_copy(deep=True) is only a comment\n"
        "label = 'model_copy(deep=True)'\n"
        "a = candidate.model_copy(deep = True)\n"
        "b = candidate.model_copy(\n    deep=True, update={}\n)\n"
        "copy = candidate.model_copy\n"
        "c = copy(deep=True)\n"
        "d = candidate.model_copy(deep=flag)\n"
        "e = candidate.model_copy(**options)\n"
        "f = candidate.model_copy(deep=False)\n",
        encoding="utf-8",
    )
    scan = check_scientist_phase1_gate._scan_for_explicit_deep_copy_calls(tmp_path, set())
    assert scan["findings"] == [
        "src/polisyos/scientist/candidate.py:3",
        "src/polisyos/scientist/candidate.py:4",
    ]
    assert {item["line"] for item in scan["unresolved_by_construction"]} == {8, 9, 10}
    assert scan["unmeasured"]
    assert scan["source_files"] == ["src/polisyos/scientist/candidate.py"]


def test_scientist_phase1_absent_or_malformed_source_is_unrun(tmp_path: Path) -> None:
    benchmark = tmp_path / "bench.json"
    junit = tmp_path / "cases.xml"
    output = tmp_path / "out.json"
    _write_benchmark_json(benchmark, [])
    _write_junit_xml(junit, [])
    args = [
        "--repo-root",
        str(tmp_path),
        "--benchmark-json",
        str(benchmark),
        "--junit-xml",
        str(junit),
        "--output",
        str(output),
    ]
    assert check_scientist_phase1_gate.main(args) == 2
    payload = json.loads(output.read_text())
    assert payload["status"] == "UNRUN"
    assert payload["complete_verdict"] is False
    _write_source_tree(tmp_path)
    (tmp_path / "src/polisyos/scientist/candidate.py").write_text("def broken(:\n")
    assert check_scientist_phase1_gate.main(args) == 2
    assert json.loads(output.read_text())["status"] == "UNRUN"


def test_scientist_phase1_broad_handler_scan_ignores_comments_and_includes_tuples(
    tmp_path: Path,
) -> None:
    source = tmp_path / "candidate.py"
    source.write_text(
        "# except Exception: is not a handler\n"
        "try:\n    run()\nexcept (ValueError, Exception):\n    pass\n"
    )
    assert check_scientist_phase1_gate._scan_for_broad_handlers(tmp_path, ["candidate.py"]) == [
        "candidate.py:4"
    ]


@pytest.mark.parametrize(
    "body",
    [
        "raise",
        "raise primary",
        (
            "try:\n    cleanup()\nexcept BaseException as secondary:\n"
            "    primary.add_note(f'cleanup failed: {type(secondary).__name__}')\nraise"
        ),
    ],
)
def test_phase1_recognizes_only_same_primary_reraise_paths(tmp_path: Path, body: str) -> None:
    source = tmp_path / "candidate.py"
    source.write_text(
        "def operation():\n    try:\n        work()\n    except BaseException as primary:\n"
        + "\n".join("        " + line for line in body.splitlines())
        + "\n"
    )
    findings, recognized = check_scientist_phase1_gate._classify_broad_handlers(
        tmp_path, ["candidate.py"]
    )
    assert findings == []
    assert "candidate.py:4" in recognized


@pytest.mark.parametrize(
    "body",
    [
        "pass",
        "return",
        "if skip:\n    return\nraise",
        "if retry:\n    raise primary\nelse:\n    raise",
        "if decide():\n    raise primary\nelse:\n    raise",
        "primary = RuntimeError('replacement')\nraise primary",
        "primary.args = ('changed',)\nraise primary",
        "raise RuntimeError('replacement')",
        "raise primary from None",
        "raise primary from make_cause()",
        "yield primary\nraise",
        "for item in items:\n    break\nraise",
        ("try:\n    cleanup()\nexcept BaseException as secondary:\n    raise\nraise"),
        ("try:\n    cleanup()\nexcept BaseException as secondary:\n    raise primary\nraise"),
        (
            "try:\n    cleanup()\nexcept BaseException as secondary:\n"
            "    raise primary from secondary\nraise"
        ),
        (
            "try:\n    cleanup()\nexcept BaseException as secondary:\n"
            "    primary.add_note('')\nraise"
        ),
        (
            "try:\n    cleanup()\nexcept BaseException as secondary:\n"
            "    primary.add_note('ok')\nraise"
        ),
        ("try:\n    cleanup()\nexcept BaseException as primary:\n    raise primary\nraise"),
        (
            "try:\n    cleanup()\nexcept BaseException as secondary:\n"
            "    primary.add_note(f'cleanup failed: {secondary!r}')\nraise"
        ),
        (
            "try:\n    cleanup()\nexcept Exception as secondary:\n"
            "    primary.add_note('cleanup failed')\nraise"
        ),
        (
            "try:\n    cleanup()\nexcept select_handler(BaseException) as secondary:\n"
            "    primary.add_note('cleanup failed')\nraise"
        ),
        (
            "try:\n    while True:\n        pass\nexcept BaseException as secondary:\n"
            "    primary.add_note('cleanup failed')\nraise"
        ),
        (
            "try:\n    [item for item in forever()]\nexcept BaseException as secondary:\n"
            "    primary.add_note(f'cleanup failed: {type(secondary).__name__}')\nraise"
        ),
        (
            "try:\n    cleanup([item for item in forever()])\n"
            "except BaseException as secondary:\n"
            "    primary.add_note(f'cleanup failed: {type(secondary).__name__}')\nraise"
        ),
    ],
)
def test_phase1_rejects_swallowing_or_replaced_primary(tmp_path: Path, body: str) -> None:
    source = tmp_path / "candidate.py"
    source.write_text(
        "def operation():\n    try:\n        work()\n    except BaseException as primary:\n"
        + "\n".join("        " + line for line in body.splitlines())
        + "\n"
    )
    assert "candidate.py:4" in check_scientist_phase1_gate._scan_for_broad_handlers(
        tmp_path, ["candidate.py"]
    )


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_phase1_cleanup_recognition_matches_actual_primary_propagation(
    tmp_path: Path, cleanup_fails: bool
) -> None:
    source = tmp_path / "candidate.py"
    program = (
        "def operation(cleanup, original):\n"
        "    try:\n        raise original\n"
        "    except BaseException as primary:\n"
        "        try:\n            cleanup()\n"
        "        except BaseException as secondary:\n"
        "            primary.add_note(f'cleanup failed: {type(secondary).__name__}')\n"
        "        raise\n"
    )
    source.write_text(program)
    assert check_scientist_phase1_gate._scan_for_broad_handlers(tmp_path, ["candidate.py"]) == []
    candidate = _load_gate_candidate(source)
    original = KeyboardInterrupt("original")
    root_cause = OSError("original cause")
    original.__cause__ = root_cause

    def cleanup() -> None:
        if cleanup_fails:
            raise OSError("cleanup")

    with pytest.raises(KeyboardInterrupt) as caught:
        candidate.operation(cleanup, original)
    assert caught.value is original
    assert caught.value.__cause__ is root_cause
    if cleanup_fails:
        assert original.__notes__ == ["cleanup failed: OSError"]

    # Hold the broad syntax and names fixed but remove the guarded property.
    swallowed = program.rsplit("        raise\n", 1)[0]
    source.write_text(swallowed)
    assert "candidate.py:4" in check_scientist_phase1_gate._scan_for_broad_handlers(
        tmp_path, ["candidate.py"]
    )
    candidate = _load_gate_candidate(source)
    assert candidate.operation(cleanup, KeyboardInterrupt("swallowed")) is None


def test_scientist_phase1_qualified_handler_is_explicitly_unmeasured(tmp_path: Path) -> None:
    _write_source_tree(tmp_path)
    benchmark, junit = _write_complete_evidence(tmp_path)
    output = tmp_path / "out.json"
    source = tmp_path / check_scientist_phase1_gate.DEFAULT_BROAD_EXCEPTION_TARGETS[0]
    source.write_text("import builtins\ntry:\n    run()\nexcept builtins.Exception:\n    pass\n")
    assert (
        check_scientist_phase1_gate.main(
            [
                "--repo-root",
                str(tmp_path),
                "--benchmark-json",
                str(benchmark),
                "--junit-xml",
                str(junit),
                "--output",
                str(output),
                "--require-passing",
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text())
    assert payload["broad_exception_findings"] == []
    assert "qualified/aliased exception types" in payload["measurement_scope"]
    assert (
        "bare or unqualified Exception/BaseException handler syntax" in payload["measurement_scope"]
    )


@pytest.mark.parametrize("output_format", ["text", "json", "junit"])
def test_phase1_caller_discloses_actual_reads_and_preserves_failure_predicates(
    tmp_path: Path, output_format: str
) -> None:
    _write_source_tree(tmp_path)
    benchmark, junit = _write_complete_evidence(tmp_path)
    output = tmp_path / f"output.{output_format}"
    source_name = check_scientist_phase1_gate.DEFAULT_BROAD_EXCEPTION_TARGETS[0]
    source = tmp_path / source_name
    original_source = source.read_bytes()
    outside = tmp_path / "outside_selector.py"
    outside.write_text("try:\n    work()\nexcept Exception:\n    pass\n")
    excluded_name = check_scientist_phase1_gate.DEFAULT_DEEP_COPY_ALLOWLIST[0]
    (tmp_path / excluded_name).write_text("value = candidate.model_copy(deep=True)\n")
    args = [
        "--repo-root",
        str(tmp_path),
        "--benchmark-json",
        str(benchmark),
        "--junit-xml",
        str(junit),
        "--output",
        str(output),
        "--output-format",
        output_format,
        "--require-passing",
    ]
    assert check_scientist_phase1_gate.main(args) == 0
    measurement = _output_measurement(output, output_format)
    actual_inputs = {item["path"] for item in measurement["inputs"]}
    assert source_name in actual_inputs
    assert {"bench.json", "cases.xml"} <= actual_inputs
    assert outside.name not in actual_inputs
    assert excluded_name not in actual_inputs
    assert measurement["complete_verdict"] is True
    assert measurement["selector"]["excluded_paths"] == sorted(
        check_scientist_phase1_gate.DEFAULT_DEEP_COPY_ALLOWLIST
    )
    assert set(measurement["denominator"]["deep_copy_source_files"]) == set(
        check_scientist_phase1_gate.DEFAULT_BROAD_EXCEPTION_TARGETS
    )
    assert any(
        item.startswith("unselected_or_qualified_handlers:")
        for item in measurement["unresolved_by_construction"]
    )
    before = {
        item["text_sha256"]
        for item in measurement["inputs"]
        if item["path"] == source_name and item["status"] == "read"
    }
    assert before == {hashlib.sha256(original_source).hexdigest()}

    # Selected swallowing fails despite retaining the same receipt structure.
    source.write_text("try:\n    work()\nexcept Exception:\n    pass\n")
    assert check_scientist_phase1_gate.main(args) == 1
    assert f"broad_exception:{source_name}:3" in output.read_text()
    changed = _output_measurement(output, output_format)
    after = {
        item["text_sha256"]
        for item in changed["inputs"]
        if item["path"] == source_name and item["status"] == "read"
    }
    assert before.isdisjoint(after)

    # The original deep-copy guard still fails through the real caller too.
    source.write_text("value = candidate.model_copy(deep=True)\n")
    assert check_scientist_phase1_gate.main(args) == 1
    assert f"deep_copy:{source_name}:1" in output.read_text()

    source.unlink()
    source.mkdir()
    assert check_scientist_phase1_gate.main(args) == 2
    incomplete = _output_measurement(output, output_format)
    assert incomplete["complete_verdict"] is False
    assert incomplete["denominator"]["deep_copy_enumeration_completed"] is False
    assert any(
        item["path"] == source_name and item["status"] == "unreadable"
        for item in incomplete["inputs"]
    )
    if output_format == "junit":
        suite = fromstring(output.read_text())
        assert suite.get("errors") == "1"
        assert suite.get("failures") == "0"
