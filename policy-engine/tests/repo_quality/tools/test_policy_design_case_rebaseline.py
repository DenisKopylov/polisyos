# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.quality.validation import build_policy_design_case_coverage as coverage
from tools.quality.validation import compare_policy_design_case_rebaseline as compare

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_policy_design_case_rebaseline_reports_typed_no_prior_baseline(
    tmp_path: Path,
) -> None:
    current = _write_coverage_dir(tmp_path / "wave-1")

    payload = compare.compare_rebaseline(
        current_dir=current,
        previous_dir=tmp_path / "wave-0-missing",
        repo_root=REPO_ROOT,
    )

    assert payload["schema_version"] == "policyos.policy_design_case.rebaseline_diff.v1"
    assert payload["status"] == "no_prior_baseline"
    assert payload["typed_result"]["type"] == "no_prior_baseline"
    assert payload["previous"]["status"] == "missing"
    assert payload["violations"] == []
    assert payload["summary"]["improved"] == len(coverage.REQUIRED_METRIC_IDS)
    assert {
        row["reason"] for row in payload["comparisons"]["improved"]
    } == {"no_prior_baseline"}


def test_policy_design_case_rebaseline_main_writes_default_diff_under_current_dir(
    tmp_path: Path,
) -> None:
    current = _write_coverage_dir(tmp_path / "wave-1")
    previous = tmp_path / "wave-0-missing"

    exit_code = compare.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--current",
            str(current),
            "--previous",
            str(previous),
        ]
    )

    output = current / "diff_from_wave_N_minus_1.json"
    assert exit_code == 0
    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "no_prior_baseline"


def test_policy_design_case_rebaseline_requires_current_coverage(
    tmp_path: Path,
) -> None:
    with pytest.raises(compare.RebaselineInputError, match=r"coverage\.json not found"):
        compare.compare_rebaseline(
            current_dir=tmp_path / "missing-current",
            previous_dir=tmp_path / "missing-previous",
            repo_root=REPO_ROOT,
        )


def _write_coverage_dir(path: Path) -> Path:
    path.mkdir(parents=True)
    payload = coverage.build_coverage_payload(repo_root=REPO_ROOT)
    (path / "coverage.json").write_text(coverage.dump_json(payload), encoding="utf-8")
    return path
