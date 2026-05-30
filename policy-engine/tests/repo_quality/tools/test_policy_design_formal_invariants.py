# ruff: noqa: S101

from __future__ import annotations

import copy
import tomllib
from pathlib import Path

from polisyos.runtime.quality.formal_invariants import (
    FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH,
    REQUIRED_CLOSEOUT_INVARIANT_IDS,
    REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS,
    build_formal_invariant_spec_report,
    validate_formal_invariant_specs_payload,
)
from tools.quality.validation import check_policy_design_formal_invariants

REPO_ROOT = Path(__file__).resolve().parents[3]


def _actual_payload() -> dict[str, object]:
    with (REPO_ROOT / FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH).open("rb") as handle:
        return tomllib.load(handle)


def test_policy_design_formal_invariant_specs_cover_phase_29_4() -> None:
    report = build_formal_invariant_spec_report(repo_root=REPO_ROOT)

    assert report["status"] == "pass", report["issues"]
    assert report["summary"]["spec_count"] >= 9
    assert report["summary"]["required_spec_count"] == 5
    assert report["summary"]["covered_required_spec_count"] == 5
    assert report["summary"]["required_coverage_pct"] == 100.0
    assert report["summary"]["temporal_liveness_required_spec_count"] == 4
    assert report["summary"]["temporal_liveness_covered_required_spec_count"] == 4
    assert report["summary"]["temporal_liveness_coverage_pct"] == 100.0
    assert report["summary"]["issue_count"] == 0
    spec_ids = {row["spec_id"] for row in report["specs"]}
    assert spec_ids >= REQUIRED_CLOSEOUT_INVARIANT_IDS
    assert spec_ids >= REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS


def test_policy_design_formal_invariant_specs_reject_missing_evidence_artifact() -> None:
    payload = _actual_payload()
    mutated = copy.deepcopy(payload)
    mutated["specs"][0]["minimum_evidence_artifacts"] = []

    validation = validate_formal_invariant_specs_payload(mutated, repo_root=REPO_ROOT)

    assert validation.status == "fail"
    assert "formal_invariant_list_field_empty" in {
        issue.code for issue in validation.issues
    }


def test_policy_design_formal_invariant_cli_fails_incomplete_registry(
    tmp_path: Path,
) -> None:
    payload = _actual_payload()
    mutated = copy.deepcopy(payload)
    mutated["specs"] = [
        row for row in mutated["specs"] if row["spec_id"] != "authority_ordering"
    ]
    registry = tmp_path / "formal_invariant_specs.toml"
    registry.write_text(_toml_specs(mutated["specs"]), encoding="utf-8")

    exit_code = check_policy_design_formal_invariants.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--registry",
            str(registry),
            "--output-format",
            "json",
        ]
    )

    assert exit_code == 1


def _toml_specs(specs: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for row in specs:
        lines.append("[[specs]]")
        for key, value in row.items():
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    return "\n".join(lines)


def _toml_value(value: object) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if value is None:
        return '""'
    return repr(str(value)).replace("'", '"')
