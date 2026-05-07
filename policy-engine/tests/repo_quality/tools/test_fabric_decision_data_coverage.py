from __future__ import annotations

from pathlib import Path

from tools.quality.validation import fabric_decision_data_coverage

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_decision_data_coverage_report_is_implemented() -> None:
    report = fabric_decision_data_coverage.build_report(REPO_ROOT)

    assert report["schema_version"] == fabric_decision_data_coverage.REPORT_SCHEMA_VERSION
    assert report["summary"]["status"] == "implemented"
    assert report["summary"]["naked_decision_value_count"] == 0
    assert report["summary"]["transitional_waiver_count"] == 0
    assert report["summary"]["unknown_field_count"] == 0
    assert report["required_contracts"]["source_contract_v2_ref"] is True
    assert report["required_contracts"]["field_classification"] is True
    assert fabric_decision_data_coverage.validate_report(report) == []


def test_decision_data_coverage_has_required_typed_gap_states() -> None:
    report = fabric_decision_data_coverage.build_report(REPO_ROOT)
    states = {row["state"] for row in report["typed_gap_states"]}

    assert states == {
        "untraced",
        "unknown_quality",
        "restricted",
        "non_replayable",
        "unsupported_temporal_scope",
    }
    assert all(row["status"] == "implemented" for row in report["typed_gap_states"])


def test_checked_in_decision_data_coverage_artifact_is_current() -> None:
    report_path = (
        REPO_ROOT
        / "tools"
        / "quality"
        / "validation"
        / "fabric_decision_data_coverage.json"
    )

    assert report_path.read_text(encoding="utf-8") == fabric_decision_data_coverage.dump_json(
        fabric_decision_data_coverage.build_report(REPO_ROOT)
    )
    assert fabric_decision_data_coverage.check_artifact(report_path) == []


def test_decision_data_coverage_gate_updates_temp_artifact(tmp_path: Path) -> None:
    output = tmp_path / "fabric_decision_data_coverage.json"

    fabric_decision_data_coverage.update_artifact(output)

    assert fabric_decision_data_coverage.check_artifact(output) == []
