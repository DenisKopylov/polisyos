# ruff: noqa: S101
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from polisyos.runtime.quality.legacy_payload_migration_audit import (
    LEGACY_MIGRATION_SEMANTIC_LOSS,
    build_legacy_migration_sandbox,
    comparison_failure_codes,
    persist_legacy_migration_sandbox_report,
)
from tests._helpers.hds_quality import (
    authority_envelope_for,
    blocking_codes,
    complete_job_payload,
    complete_quality_evidence,
    scorecard_for,
    sha,
)


def test_semantic_loss_in_legacy_migration_comparison_is_blocking() -> None:
    authority_payload = {
        "schema_version": "policyos.scientist.policy_grounding_matrix.v1",
        "status": "pass",
        "policy_grounding_matrix_ref": sha("9"),
        "authority_envelope": authority_envelope_for(
            report_key="policy_grounding_matrix",
            ref_key="policy_grounding_matrix_ref",
            ref_value=sha("9"),
        ),
        "claims": [
            {
                "claim_id": "rec_1",
                "claim_type": "recommendation",
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
            }
        ],
    }
    legacy_payload = deepcopy(authority_payload)
    legacy_payload["claims"] = [
        {
            "claim_id": "rec_1",
            "claim_type": "recommendation",
            "major": True,
            "text": "Target wartime credit support to eligible MSMEs.",
        }
    ]

    report = build_legacy_migration_sandbox(
        canary_kind="production",
        run_id="R_hds_migration",
        job_id="job-hds-migration",
        comparisons=[
            {
                "report_key": "policy_grounding_matrix",
                "ref_key": "policy_grounding_matrix_ref",
                "legacy_payload": legacy_payload,
                "authority_payload": authority_payload,
                "authority_ref": sha("9"),
                "semantic_fields": ["claims"],
            }
        ],
    )

    assert report["status"] == "fail"
    assert report["production_closeout_allowed"] is False
    assert LEGACY_MIGRATION_SEMANTIC_LOSS in comparison_failure_codes(report)
    comparison = report["comparisons"][0]
    assert comparison["semantic_fields"]["lost_fields"] == ["claims"]
    assert comparison["legacy"]["evidence_class"] == "legacy_quarantined"
    assert comparison["authority"]["evidence_class"] == "authority_bearing"


def test_semantic_loss_in_migration_sandbox_blocks_serious_scorecard() -> None:
    quality_evidence = complete_quality_evidence()
    authority_payload = deepcopy(quality_evidence["policy_grounding_matrix"])
    authority_payload["authority_envelope"] = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=sha("9"),
    )
    legacy_payload = deepcopy(authority_payload)
    legacy_payload["claims"] = []
    quality_evidence["legacy_migration_sandbox"] = build_legacy_migration_sandbox(
        canary_kind="production",
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        comparisons=[
            {
                "report_key": "policy_grounding_matrix",
                "ref_key": "policy_grounding_matrix_ref",
                "legacy_payload": legacy_payload,
                "authority_payload": authority_payload,
                "authority_ref": sha("9"),
                "semantic_fields": ["claims"],
            }
        ],
    )

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=quality_evidence,
        normalize=True,
    )

    assert scorecard["quality_status"] == "fail"
    assert LEGACY_MIGRATION_SEMANTIC_LOSS in blocking_codes(scorecard)


def test_dual_write_cutoff_requires_two_consecutive_weekly_baselines() -> None:
    one_baseline = build_legacy_migration_sandbox(
        canary_kind="production",
        run_id="R_hds_migration",
        job_id="job-hds-migration",
        comparisons=[],
        baseline_history=[
            {"cadence": "weekly-closeout", "status": "pass"},
        ],
    )
    two_baselines = build_legacy_migration_sandbox(
        canary_kind="production",
        run_id="R_hds_migration",
        job_id="job-hds-migration",
        comparisons=[],
        baseline_history=[
            {"cadence": "weekly-closeout", "status": "pass"},
            {"cadence": "weekly-closeout", "status": "pass"},
        ],
    )

    assert one_baseline["dual_write_policy"][
        "observed_consecutive_weekly_closeout_baselines"
    ] == 1
    assert one_baseline["dual_write_policy"]["cutoff_allowed"] is False
    assert two_baselines["dual_write_policy"][
        "observed_consecutive_weekly_closeout_baselines"
    ] == 2
    assert two_baselines["dual_write_policy"]["cutoff_allowed"] is True


def test_dual_write_legacy_evidence_cannot_satisfy_serious_authority_gate() -> None:
    quality_evidence = complete_quality_evidence()
    envelope = quality_evidence["policy_grounding_matrix"]["authority_envelope"]
    envelope["evidence_class"] = "legacy_quarantined"
    envelope["authority_role"] = "diagnostic_only"
    envelope["provenance_kind"] = "legacy_supported"

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=quality_evidence,
        normalize=True,
    )

    assert scorecard["quality_status"] == "fail"
    assert "legacy_migration_legacy_used_as_authority" in blocking_codes(scorecard)


def test_authority_ref_without_envelope_cannot_satisfy_migration_sandbox() -> None:
    payload = {
        "schema_version": "policyos.scientist.policy_grounding_matrix.v1",
        "status": "pass",
        "policy_grounding_matrix_ref": sha("9"),
        "claims": [{"claim_id": "rec_1"}],
    }

    report = build_legacy_migration_sandbox(
        canary_kind="production",
        run_id="R_hds_migration",
        job_id="job-hds-migration",
        comparisons=[
            {
                "report_key": "policy_grounding_matrix",
                "ref_key": "policy_grounding_matrix_ref",
                "legacy_payload": payload,
                "authority_payload": payload,
                "authority_ref": sha("9"),
                "semantic_fields": ["claims"],
            }
        ],
    )

    assert report["status"] == "fail"
    assert report["production_closeout_allowed"] is False
    assert "legacy_migration_authority_envelope_missing" in comparison_failure_codes(report)


def test_local_validation_persists_migration_sandbox_report_under_build_dir(
    tmp_path: Path,
) -> None:
    report = build_legacy_migration_sandbox(
        canary_kind="production",
        run_id="R_hds_migration",
        job_id="job-hds-migration",
        comparisons=[],
    )

    written = persist_legacy_migration_sandbox_report(
        report,
        repo_root=tmp_path,
        validation_id="weekly-baseline-1",
    )

    assert written == (
        tmp_path
        / "_build"
        / "honest-diagnostics"
        / "migration-sandbox"
        / "weekly-baseline-1.json"
    )
    assert written.is_file()
