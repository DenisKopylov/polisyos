from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tools.quality.validation import fabric_wave2_strict_closure

REPO_ROOT = Path(__file__).resolve().parents[3]


def _surfaces(report: dict[str, object]) -> dict[str, dict[str, object]]:
    manifest = report["manifest"]
    assert isinstance(manifest, dict)
    rows = manifest["surfaces"]
    assert isinstance(rows, list)
    return {str(row["id"]): row for row in rows}


def test_wave2_strict_closure_report_passes_current_artifacts() -> None:
    report = fabric_wave2_strict_closure.build_report(REPO_ROOT)

    assert report["schema_version"] == fabric_wave2_strict_closure.REPORT_SCHEMA_VERSION
    assert fabric_wave2_strict_closure.validate_report(report) == []
    surfaces = _surfaces(report)
    assert surfaces["world.kuzu_temporal_scope_capability"]["status"] == "partial"
    assert surfaces["world.temporal_graph_reasoning"]["status"] == "blocked_by_research"
    assert surfaces["world.future_table_snapshot_adapters"]["status"] == "not_applicable"


def test_wave2_strict_closure_main_check_passes() -> None:
    assert fabric_wave2_strict_closure.main(["--check"]) == 0


def test_wave2_strict_closure_rejects_non_r_partial_surface() -> None:
    report = deepcopy(fabric_wave2_strict_closure.build_report(REPO_ROOT))
    surfaces = _surfaces(report)
    surfaces["trust.access_classification"]["status"] = "partial"

    errors = fabric_wave2_strict_closure.validate_report(report)

    assert any("trust.access_classification" in error for error in errors)


def test_wave2_strict_closure_rejects_non_replayable_sources() -> None:
    report = deepcopy(fabric_wave2_strict_closure.build_report(REPO_ROOT))
    manifest = report["manifest"]
    assert isinstance(manifest, dict)
    coverage = manifest["coverage"]
    assert isinstance(coverage, dict)
    source_platform = coverage["source_platform"]
    assert isinstance(source_platform, dict)
    source_platform["non_replayable_reason_count"] = 1

    errors = fabric_wave2_strict_closure.validate_report(report)

    assert any("non_replayable_reason_count == 0" in error for error in errors)
