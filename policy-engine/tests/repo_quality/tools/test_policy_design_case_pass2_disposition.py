from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import (
    build_policy_design_case_pass2_disposition as build,
)
from tools.quality.validation import (
    check_policy_design_case_pass2_disposition as check,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_wave35_findings_ledger_represents_every_wave34_artifact() -> None:
    ledger = build.build_findings_ledger_payload(repo_root=REPO_ROOT)

    assert ledger["schema_version"] == build.SCHEMA_VERSION
    assert ledger["wave"] == "35"
    assert ledger["source_wave"] == "34"
    assert ledger["summary"]["phase_index_count"] == 6
    assert ledger["summary"]["pdd_detail_artifact_count"] == 27
    assert ledger["summary"]["finding_count"] == 113
    assert ledger["summary"]["zero_finding_pdd_ids"] == ["PDD-088"]

    pdd100 = next(
        row for row in ledger["findings"] if row["pdd_id"] == "PDD-100"
    )
    assert pdd100["recommended_remediation_id"] == "PDD-100-A1"
    assert pdd100["recommended_gate"]
    assert pdd100["source_evidence"]["detail_artifact"].endswith(
        "pdd-100/document_extraction_authority_audit.json"
    )


def test_wave35_root_cause_clusters_cover_every_finding_once() -> None:
    ledger, clusters, _disposition = build.build_wave35_payloads(repo_root=REPO_ROOT)

    finding_ids = {row["finding_id"] for row in ledger["findings"]}
    covered_ids = [
        finding_id
        for cluster in clusters["clusters"]
        for finding_id in cluster["finding_ids"]
    ]

    assert set(covered_ids) == finding_ids
    assert len(covered_ids) == len(finding_ids)
    assert {cluster["cluster_id"] for cluster in clusters["clusters"]} == set(
        build.CLUSTER_SPECS
    )
    assert all(
        cluster["target_plan_wave"].startswith("Wave 35")
        for cluster in clusters["clusters"]
    )


def test_wave35_disposition_classifies_every_finding_and_not_triggered_artifact() -> None:
    _ledger, _clusters, disposition = build.build_wave35_payloads(repo_root=REPO_ROOT)

    assert disposition["status"] == "pass"
    assert disposition["summary"]["finding_count"] == 113
    assert disposition["summary"]["disposition_count"] == 113
    assert disposition["summary"]["must_fix_unresolved_count"] == 0
    assert disposition["summary"]["classification_counts"]["next_plan_remediation"] > 0
    assert disposition["summary"]["classification_counts"]["accepted_blocker"] > 0
    assert (
        disposition["summary"]["classification_counts"][
            "false_alarm_with_evidence"
        ]
        > 0
    )
    assert {row["pdd_id"] for row in disposition["artifact_dispositions"]} == {
        "PDD-088"
    }

    for row in disposition["dispositions"]:
        assert row["rationale"]
        assert row["owner"]
        assert row["affected_subsystem"]
        assert row["closeout_impact"]
        assert row["verification_command"]
        assert row["source_evidence"]


def test_wave35_validator_accepts_generated_payloads(tmp_path: Path) -> None:
    build.main(["--repo-root", str(REPO_ROOT), "--output-dir", str(tmp_path)])

    errors = check.validate_pass2_disposition(
        repo_root=REPO_ROOT,
        output_dir=tmp_path,
        require_passing=True,
    )

    assert errors == []


def test_wave35_validator_fails_when_a_finding_lacks_disposition(
    tmp_path: Path,
) -> None:
    _write_payloads(tmp_path)
    disposition_path = tmp_path / "pass2_disposition.json"
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    disposition["dispositions"] = disposition["dispositions"][1:]
    disposition_path.write_text(json.dumps(disposition, indent=2) + "\n", encoding="utf-8")

    errors = check.validate_pass2_disposition(
        repo_root=REPO_ROOT,
        output_dir=tmp_path,
    )

    assert any("exactly one disposition" in error for error in errors)


def test_wave35_validator_fails_when_deferral_target_is_not_before_wave36(
    tmp_path: Path,
) -> None:
    _write_payloads(tmp_path)
    disposition_path = tmp_path / "pass2_disposition.json"
    disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    for row in disposition["dispositions"]:
        if row["classification"] == "next_plan_remediation":
            row["target_plan_wave"] = "Wave 36"
            break
    disposition_path.write_text(json.dumps(disposition, indent=2) + "\n", encoding="utf-8")

    errors = check.validate_pass2_disposition(
        repo_root=REPO_ROOT,
        output_dir=tmp_path,
    )

    assert any("target_plan_wave must occur before Wave 36" in error for error in errors)


def test_wave35_validator_closeout_ready_fails_while_deferrals_remain(
    tmp_path: Path,
) -> None:
    _write_payloads(tmp_path)

    errors = check.validate_pass2_disposition(
        repo_root=REPO_ROOT,
        output_dir=tmp_path,
        require_passing=True,
        require_closeout_ready=True,
    )

    assert any("--require-closeout-ready forbids unresolved" in error for error in errors)


def test_wave35_validator_fails_when_remediation_wave_spec_is_too_vague(
    tmp_path: Path,
) -> None:
    _write_payloads(tmp_path)
    plan_path = tmp_path / "plan.md"
    source = (
        REPO_ROOT
        / "docs"
        / "plans"
        / "archive"
        / "2026-05-19-policyos-policy-design-case-implementation-plan.md"
    ).read_text(encoding="utf-8")
    plan_path.write_text(
        source.replace("scenario_variant_inventory.json", "scenario_inventory.json"),
        encoding="utf-8",
    )

    errors = check.validate_pass2_disposition(
        repo_root=REPO_ROOT,
        output_dir=tmp_path,
        plan_path=plan_path,
    )

    assert any(
        "Wave 35A: remediation wave spec missing marker: scenario_variant_inventory.json"
        in error
        for error in errors
    )


def test_wave35_validator_requires_wave35f_integrity_gate_before_wave36(
    tmp_path: Path,
) -> None:
    _write_payloads(tmp_path)
    plan_path = tmp_path / "plan.md"
    source = (
        REPO_ROOT
        / "docs"
        / "plans"
        / "archive"
        / "2026-05-19-policyos-policy-design-case-implementation-plan.md"
    ).read_text(encoding="utf-8")
    plan_path.write_text(
        source.replace(
            "check_policy_design_case_wave35f_integrity.py",
            "check_policy_design_case_wave35_integrity.py",
        ),
        encoding="utf-8",
    )

    errors = check.validate_pass2_disposition(
        repo_root=REPO_ROOT,
        output_dir=tmp_path,
        plan_path=plan_path,
    )

    assert any(
        "Wave 35F: remediation wave spec missing marker: "
        "check_policy_design_case_wave35f_integrity.py" in error
        for error in errors
    )


def test_wave35_validator_requires_wave35g_backfill_gate_before_wave36(
    tmp_path: Path,
) -> None:
    _write_payloads(tmp_path)
    plan_path = tmp_path / "plan.md"
    source = (
        REPO_ROOT
        / "docs"
        / "plans"
        / "archive"
        / "2026-05-19-policyos-policy-design-case-implementation-plan.md"
    ).read_text(encoding="utf-8")
    plan_path.write_text(
        source.replace(
            "check_policy_design_case_wave35g_backfill.py",
            "check_policy_design_case_wave35_backfill.py",
        ),
        encoding="utf-8",
    )

    errors = check.validate_pass2_disposition(
        repo_root=REPO_ROOT,
        output_dir=tmp_path,
        plan_path=plan_path,
    )

    assert any(
        "Wave 36 entry criteria missing marker: "
        "check_policy_design_case_wave35g_backfill.py --repo-root ." in error
        for error in errors
    )


def _write_payloads(output_dir: Path) -> None:
    ledger, clusters, disposition = build.build_wave35_payloads(
        repo_root=REPO_ROOT,
        output_dir=output_dir,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pass2_findings_ledger.json").write_text(
        json.dumps(ledger, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "pass2_root_cause_clusters.json").write_text(
        json.dumps(clusters, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "pass2_disposition.json").write_text(
        json.dumps(disposition, indent=2) + "\n",
        encoding="utf-8",
    )
