from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import build_policy_design_case_wave35f_integrity as build
from tools.quality.validation import check_policy_design_case_wave35f_integrity as check

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_wave35f_builds_integrity_gate_and_blocks_unbacked_human_overlays(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "wave-35F"

    outputs = build.build_wave35f_integrity_outputs(
        repo_root=REPO_ROOT,
        wave35f_dir=output_dir,
        wave35g_dir=tmp_path / "missing-wave-35G",
    )

    classification = outputs["classification"]
    assert classification["status"] == "pass"
    assert classification["summary"]["remediated_finding_count"] == 112
    assert set(classification["summary"]["authority_class_counts"]) <= set(
        build.ALLOWED_AUTHORITY_CLASSES
    )
    assert classification["coverage"]["missing_remediated_finding_ids"] == []
    assert classification["coverage"]["missing_disposition_artifact_paths"] == []

    trust_rows = [
        row
        for row in classification["rows"]
        if row["artifact_path"].endswith("trust_framing_ui_negative_tests.json")
    ]
    assert trust_rows
    assert {row["evidence_authority_class"] for row in trust_rows} == {
        "synthetic_remediation_overlay"
    }
    assert all(row["counts_toward_deterministic_closeout"] is False for row in trust_rows)

    gap_ledger = outputs["gap_ledger"]
    assert gap_ledger["status"] == "pass_with_wave36_blockers"
    trust_gap = next(
        row
        for row in gap_ledger["rows"]
        if row["artifact_path"].endswith("trust_framing_ui_negative_tests.json")
        and row["finding_id"] == "PDD-103-F004"
    )
    assert trust_gap["accepted_boundary"]["boundary_decision"] == "not_closeout_authority"
    assert trust_gap["accepted_boundary"]["blocks_wave36_closeout_authority"] is True
    assert trust_gap["wave36_blocking_decision"] == "block_wave36_release"
    assert trust_gap["required_test_or_trace"]

    human_audit = outputs["human_surface_audit"]
    assert human_audit["status"] == "pass_with_not_closeout_authority_caveats"
    not_closeout_surfaces = {
        row["claim_surface"]
        for row in human_audit["rows"]
        if row["closeout_authority_decision"] == "not_closeout_authority"
    }
    assert not_closeout_surfaces >= {
        "memory_authority",
    }
    assert {
        row["claim_surface"]
        for row in human_audit["rows"]
        if row["runtime_or_test_observed"] is True
    } >= {
        "dashboard_api_projection",
        "implementation_feasibility",
        "contestability",
        "trust_framing",
    }

    authority_map = outputs["authority_map"]
    assert authority_map["coverage"]["missing_wave35_artifact_paths"] == []
    assert any(
        row["remediation_overlay_only"] is True
        for row in authority_map["artifacts"]
        if row["artifact_path"].endswith("wave35_disposition_update.json")
    )

    exit_fence = outputs["exit_fence"]
    assert exit_fence["status"] == "pass"
    assert exit_fence["wave36_release_decision"] == "blocked"
    assert "PDD-103-F004" in exit_fence["blocking_finding_ids"]

    assert (
        check.validate_wave35f_integrity(
            repo_root=REPO_ROOT,
            wave35f_dir=output_dir,
            wave35g_dir=tmp_path / "missing-wave-35G",
        )
        == []
    )


def test_wave35f_validator_rejects_overlay_gap_without_accepted_boundary(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "wave-35F"
    build.build_wave35f_integrity_outputs(
        repo_root=REPO_ROOT,
        wave35f_dir=output_dir,
        wave35g_dir=tmp_path / "missing-wave-35G",
    )
    gap_path = output_dir / "runtime_enforcement_gap_ledger.json"
    gap_ledger = json.loads(gap_path.read_text(encoding="utf-8"))
    gap_ledger["rows"][0]["accepted_boundary"] = None
    gap_path.write_text(json.dumps(gap_ledger, indent=2), encoding="utf-8")

    errors = check.validate_wave35f_integrity(
        repo_root=REPO_ROOT,
        wave35f_dir=output_dir,
        wave35g_dir=tmp_path / "missing-wave-35G",
    )

    assert any("missing accepted boundary" in error for error in errors)
