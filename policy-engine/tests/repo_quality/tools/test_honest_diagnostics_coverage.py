# ruff: noqa: S101

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools.quality.validation import build_honest_diagnostics_coverage as coverage
from tools.quality.validation import compare_honest_diagnostics_rebaseline as compare

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_METRICS = {
    "invariant_registry_complete_pct",
    "runtime_emitted_invariant_pct",
    "negative_control_coverage_pct",
    "authority_envelope_complete_pct",
    "payload_identity_verified_gate_pct",
    "fallback_ledger_coverage_pct",
    "authority_bearing_provenance_pct",
    "source_truth_conflict_gate_pct",
    "semantic_binding_gate_pct",
    "legacy_quarantine_classified_pct",
    "false_pass_rate_negative_controls",
    "operator_ttrc_p50_minutes",
    "operator_ttrc_p90_minutes",
}


def test_coverage_builder_writes_required_metric_dashboard(tmp_path: Path) -> None:
    output_dir = tmp_path / "coverage"

    exit_code = coverage.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    payload = json.loads((output_dir / "coverage.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "coverage.md").read_text(encoding="utf-8")
    metrics = payload["metrics"]

    assert set(metrics) == EXPECTED_METRICS
    assert payload["source"]["invariant_registry"].endswith(
        "architecture/production_quality/invariant_registry.toml"
    )
    assert "| Metric | Value | Numerator | Denominator |" in markdown

    for metric_id in EXPECTED_METRICS:
        metric = metrics[metric_id]
        assert "numerator" in metric, metric_id
        assert "denominator" in metric, metric_id
        assert isinstance(metric["denominator_changed"], bool), metric_id
        assert metric["definition"]["target"]["final"], metric_id

    for metric_id in ("operator_ttrc_p50_minutes", "operator_ttrc_p90_minutes"):
        metric = metrics[metric_id]
        assert metric["value"] is None
        assert metric["numerator"] == 0
        assert metric["denominator"] == 0
        assert metric["measurement_status"] == "not_measured"
    assert "| `operator_ttrc_p50_minutes` | null | 0 | 0 |" in markdown


def test_coverage_builder_rejects_missing_metric_definitions() -> None:
    definitions = dict(coverage.METRIC_DEFINITIONS)
    definitions.pop("semantic_binding_gate_pct")

    with pytest.raises(coverage.CoverageDefinitionError, match="semantic_binding_gate_pct"):
        coverage.build_coverage_payload(
            repo_root=REPO_ROOT,
            metric_definitions=definitions,
        )


def test_coverage_builder_marks_wrong_shaped_invariant_rows_invalid(tmp_path: Path) -> None:
    registry = tmp_path / "invariant_registry.toml"
    registry.write_text(
        "\n".join(
            [
                "[[invariants]]",
                'invariant_id = ""',
                'minimum_closeout_gate = "serious_canary_runtime_refs"',
                'pql_id = "PQL-001"',
                'final_owner = "runtime.quality.closeout"',
                "producer_owners = []",
                "runtime_event_names = []",
                "required_artifact_kinds = []",
                "required_ref_keys = []",
                "evidence_classes = []",
                "allowed_provenance_kinds = []",
                "required_schema_contracts = []",
                "scorecard_gate_names = []",
                'readiness_check = "production_quality.runtime_required_refs"',
                'approval_policy = "requires_verified_scorecard"',
                'override_policy = "not_overridable"',
                "non_overridable_blockers = []",
                'dashboard_projection_policy = "projection_only"',
                'public_artifact_policy = "not_public_exportable"',
                'conflict_policy = "fail_closed"',
                'failure_code = "hds_runtime_refs_missing"',
                'diagnostic_owner = "team-runtime"',
                "dependencies = []",
                "consumers = []",
                'next_diagnostic_command = "uv run pytest tests/unit/runtime/http/test_nl_pipeline_materialization.py -q"',
                "negative_tests = []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = coverage.build_coverage_payload(
        repo_root=REPO_ROOT,
        registry_path=registry,
    )

    assert payload["summary"]["status"] == "fail"
    assert payload["invalid_invariants"][0]["invariant_id"] == "invariants[1]"
    assert "producer_owners" in payload["invalid_invariants"][0]["missing_fields"]


def test_rebaseline_comparator_reports_missing_improved_regressed_and_denominator_changed(
    tmp_path: Path,
) -> None:
    previous_payload = coverage.build_coverage_payload(repo_root=REPO_ROOT)
    current_payload = copy.deepcopy(previous_payload)

    current_payload["metrics"].pop("legacy_quarantine_classified_pct")
    _set_metric_value(
        current_payload,
        "negative_control_coverage_pct",
        numerator=2,
        denominator=2,
        value=100.0,
    )
    _set_metric_value(
        previous_payload,
        "negative_control_coverage_pct",
        numerator=1,
        denominator=2,
        value=50.0,
    )
    _set_metric_value(
        current_payload,
        "authority_envelope_complete_pct",
        numerator=1,
        denominator=2,
        value=50.0,
    )
    _set_metric_value(
        previous_payload,
        "authority_envelope_complete_pct",
        numerator=2,
        denominator=2,
        value=100.0,
    )
    _set_metric_value(
        current_payload,
        "fallback_ledger_coverage_pct",
        numerator=1,
        denominator=3,
        value=33.333,
        denominator_changed=True,
    )
    _set_metric_value(
        previous_payload,
        "fallback_ledger_coverage_pct",
        numerator=1,
        denominator=2,
        value=50.0,
    )

    previous_dir = _write_payload(tmp_path / "previous", previous_payload)
    current_dir = _write_payload(tmp_path / "current", current_payload)

    payload = compare.compare_rebaseline(
        current_dir=current_dir,
        previous_dir=previous_dir,
        decision_log_path=tmp_path / "missing-decision-log.md",
    )

    assert payload["status"] == "fail"
    assert payload["anti_drift"]["status"] == "pass"
    assert payload["summary"]["anti_drift_status"] == "pass"
    assert _metric_ids(payload["comparisons"]["missing"]) == {
        "legacy_quarantine_classified_pct"
    }
    assert "negative_control_coverage_pct" in _metric_ids(
        payload["comparisons"]["improved"]
    )
    assert "authority_envelope_complete_pct" in _metric_ids(
        payload["comparisons"]["regressed"]
    )
    assert "fallback_ledger_coverage_pct" in _metric_ids(
        payload["comparisons"]["denominator_changed"]
    )
    assert any(
        violation["code"] == "coverage_drop_missing_denominator_change"
        for violation in payload["violations"]
    )


def test_rebaseline_comparator_allows_drop_only_with_denominator_change_and_log_entry(
    tmp_path: Path,
) -> None:
    previous_payload = coverage.build_coverage_payload(repo_root=REPO_ROOT)
    current_payload = copy.deepcopy(previous_payload)
    _set_metric_value(
        previous_payload,
        "authority_envelope_complete_pct",
        numerator=4,
        denominator=4,
        value=100.0,
    )
    _set_metric_value(
        current_payload,
        "authority_envelope_complete_pct",
        numerator=4,
        denominator=8,
        value=50.0,
        denominator_changed=True,
    )
    decision_log = tmp_path / "decision-log.md"
    decision_log.write_text(
        "\n".join(
            [
                "## 2026-05-15 - Coverage denominator rebaseline",
                "- metric: authority_envelope_complete_pct",
                "- denominator_changed=true",
                "- context: Wave 0 made the denominator more honest.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = compare.compare_rebaseline(
        current_dir=_write_payload(tmp_path / "current", current_payload),
        previous_dir=_write_payload(tmp_path / "previous", previous_payload),
        decision_log_path=decision_log,
    )

    assert payload["status"] == "pass"
    assert payload["anti_drift"]["status"] == "pass"
    assert "authority_envelope_complete_pct" in _metric_ids(
        payload["comparisons"]["regressed"]
    )
    assert payload["violations"] == []


def test_rebaseline_comparator_reports_typed_no_prior_baseline(tmp_path: Path) -> None:
    current_dir = _write_payload(
        tmp_path / "current",
        coverage.build_coverage_payload(repo_root=REPO_ROOT),
    )

    payload = compare.compare_rebaseline(
        current_dir=current_dir,
        previous_dir=tmp_path / "missing",
        decision_log_path=tmp_path / "missing-decision-log.md",
    )

    assert payload["status"] == "no_prior_baseline"
    assert payload["violations"] == []
    assert payload["comparisons"]["missing"] == []
    assert payload["anti_drift"]["status"] == "pass"
    assert payload["summary"]["anti_drift_status"] == "pass"


def _set_metric_value(
    payload: dict[str, object],
    metric_id: str,
    *,
    numerator: int | float,
    denominator: int | float,
    value: int | float,
    denominator_changed: bool = False,
) -> None:
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    metric = metrics[metric_id]
    assert isinstance(metric, dict)
    metric["numerator"] = numerator
    metric["denominator"] = denominator
    metric["value"] = value
    metric["denominator_changed"] = denominator_changed


def _write_payload(directory: Path, payload: dict[str, object]) -> Path:
    directory.mkdir(parents=True)
    (directory / "coverage.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return directory


def _metric_ids(rows: list[dict[str, object]]) -> set[str]:
    return {str(row["metric_id"]) for row in rows}
