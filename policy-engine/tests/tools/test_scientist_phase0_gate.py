from __future__ import annotations

import json
from pathlib import Path

from tools.ci import check_scientist_phase0_gate


def _write_junit_xml(path: Path, names: list[str]) -> None:
    testcases = "\n".join(
        f'    <testcase classname="scientist.phase0" name="{name}" />' for name in names
    )
    path.write_text(
        f'<testsuite name="scientist-phase0">\n{testcases}\n</testsuite>\n',
        encoding="utf-8",
    )


def test_scientist_phase0_gate_builds_passing_json_report(tmp_path: Path) -> None:
    junit_xml = tmp_path / "phase0.xml"
    output_json = tmp_path / "phase0-gate.json"
    _write_junit_xml(
        junit_xml,
        [
            "test_timeout_worker_does_not_swallow_system_exit",
            "test_worker_runtime_error_surfaces_on_future",
            "test_measure_acquire_does_not_swallow_assertion_errors",
            "test_detect_stale_runtime_probe_error_returns_false",
            "test_detect_stale_returns_false_on_runtime_probe_error",
            "test_retry_after_header_and_idempotency_key_are_reused",
            "test_idempotency_key_is_added_even_without_retry_budget",
            "test_compute_idempotency_key_stable_for_same_inputs",
            "test_compute_idempotency_key_changes_on_artifact_change",
            "test_post_record_falls_back_to_reserved_cost_when_accounting_breaks",
            "test_parallel_calls_do_not_overspend_reserved_budget",
            "test_releases_reservation_when_generate_raises",
            "test_releases_reservation_when_task_is_cancelled",
            "test_actual_cost_commit_reconciles_estimate_delta",
            "test_masking_raises_when_target_metric_is_missing",
            "test_masking_raises_when_intervention_step_exceeds_metric_horizon",
            "test_rejects_control_characters_in_env_values",
            "test_sets_and_restores_sanitized_env_values",
            "test_rmse_ci_bootstraps_rmse_directly",
            "test_equal_propensity",
            "test_iid_data",
            "test_spearman_uses_average_ranks_for_ties",
        ],
    )

    exit_code = check_scientist_phase0_gate.main(
        [
            "--junit-xml",
            str(junit_xml),
            "--output",
            str(output_json),
            "--output-format",
            "json",
            "--require-passing",
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["assessment_id"] == "scientist_phase0_gate"
    assert payload["passes_all"] is True
    assert payload["category_results"]["async_lifecycle"] is True
    assert payload["category_results"]["statistical_hotfixes"] is True


def test_scientist_phase0_gate_fails_when_required_evidence_is_missing(tmp_path: Path) -> None:
    junit_xml = tmp_path / "phase0.xml"
    output_json = tmp_path / "phase0-gate.json"
    _write_junit_xml(
        junit_xml,
        [
            "test_timeout_worker_does_not_swallow_system_exit",
            "test_retry_after_header_and_idempotency_key_are_reused",
        ],
    )

    exit_code = check_scientist_phase0_gate.main(
        [
            "--junit-xml",
            str(junit_xml),
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
    assert "async_lifecycle:test_worker_runtime_error_surfaces_on_future" in payload["notes"]
    assert "statistical_hotfixes:test_spearman_uses_average_ranks_for_ties" in payload["notes"]
