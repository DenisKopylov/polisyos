from __future__ import annotations

import json

from polisyos.data_forge import build_privacy_compliance_report
from polisyos.runtime.quality.scorecard import build_quality_scorecard


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _complete_job_payload() -> dict[str, object]:
    return {
        "job_id": "job-compliance",
        "run_id": "R_compliance",
        "state": "completed",
        "progress": {
            "details": {
                "data_snapshot_ref": _sha("1"),
                "input_bindings_ref": _sha("2"),
                "registry_bundle_ref": _sha("3"),
                "quality_report_ref": _sha("4"),
                "normative_applicability_report_ref": _sha("5"),
                "fabric_retrieval_trace_ref": _sha("6"),
                "foundry_method_report_ref": _sha("7"),
                "policy_grounding_matrix_ref": _sha("8"),
                "conflict_check_ref": _sha("9"),
                "llm_model_variants": [
                    {
                        "model_variant_id": "qwen_1",
                        "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                        "provider": "gateway",
                        "status": "completed",
                        "prompt_tokens": 120,
                        "completion_tokens": 32,
                        "total_tokens": 152,
                        "cost_usd": 0.0001,
                    }
                ],
                "run_performance_summary": {"status": "pass"},
            }
        },
    }


def _passing_quality_evidence(
    privacy_compliance_report: dict[str, object],
) -> dict[str, object]:
    return {
        "normative_evidence": {"status": "pass"},
        "fabric_retrieval_trace": {"status": "pass"},
        "foundry_method_report": {"status": "pass"},
        "policy_grounding_matrix": {"status": "pass"},
        "conflict_check": {"status": "pass"},
        "privacy_compliance_report": privacy_compliance_report,
    }


def test_privacy_compliance_report_summarizes_inputs_without_raw_sensitive_records() -> None:
    report = build_privacy_compliance_report(
        production_data_sources=[
            {
                "source_id": "production-msme-panel",
                "source_family": "production_msme_panel",
                "fields": [
                    {"name": "firm_id", "retained": True},
                    {
                        "name": "owner_email",
                        "retained": True,
                        "basis": "public_authority",
                        "basis_ref": "law://ua.statistics",
                        "redaction_status": "redacted",
                    },
                ],
                "raw_records": [{"owner_email": "owner@example.test"}],
                "minimization": {
                    "purpose": "Estimate wartime credit policy outcomes.",
                    "retained_fields": ["firm_id", "owner_email"],
                    "excluded_fields": ["owner_phone"],
                },
                "retention_class": "warm",
                "jurisdiction": "UA",
                "license": "CC-BY-4.0",
                "public_export_allowed": True,
                "source_attribution": "State Statistics Service of Ukraine",
                "authority_basis": "statutory mandate",
                "authority_basis_ref": "law://ua.statistics",
            }
        ],
        public_artifact_families=[
            {
                "artifact_family": "public_policy_brief",
                "jurisdiction": "UA",
                "license": "CC-BY-4.0",
                "public_export_allowed": True,
                "source_attribution": ["production-msme-panel"],
                "redaction_status": "redacted",
                "authority_basis": "public interest publication",
            }
        ],
    )

    rendered = json.dumps(report, sort_keys=True)

    assert report["schema_version"] == "policyos.privacy_compliance_report.v1"
    assert report["status"] == "pass"
    assert report["summary"]["production_data_source_count"] == 1
    assert report["summary"]["public_artifact_family_count"] == 1
    assert report["production_data_sources"][0]["source_id"] == "production-msme-panel"
    assert report["production_data_sources"][0]["pii_like_fields"] == [
        {
            "field": "owner_email",
            "basis": "public_authority",
            "basis_ref": "law://ua.statistics",
            "redaction_status": "redacted",
        }
    ]
    assert "owner@example.test" not in rendered
    assert "raw_records" not in rendered


def test_pii_like_field_without_basis_or_redaction_blocks_compliance() -> None:
    report = build_privacy_compliance_report(
        production_data_sources=[
            {
                "source_id": "production-msme-panel",
                "source_family": "production_msme_panel",
                "fields": [{"name": "owner_email", "retained": True}],
                "minimization": {"purpose": "Estimate policy outcomes."},
                "retention_class": "warm",
                "jurisdiction": "UA",
                "license": "CC-BY-4.0",
                "public_export_allowed": True,
                "source_attribution": "State Statistics Service of Ukraine",
            }
        ],
        public_artifact_families=[],
    )

    assert report["status"] == "fail"
    assert report["summary"]["blocking_issue_count"] == 1
    assert report["issues"][0]["code"] == "pii_basis_or_redaction_missing"
    assert report["issues"][0]["field"] == "owner_email"


def test_license_or_public_export_conflict_blocks_scorecard_approval() -> None:
    report = build_privacy_compliance_report(
        production_data_sources=[
            {
                "source_id": "restricted-msme-panel",
                "source_family": "production_msme_panel",
                "fields": [{"name": "firm_id", "retained": True}],
                "minimization": {"purpose": "Estimate policy outcomes."},
                "retention_class": "warm",
                "jurisdiction": "UA",
                "license": "Internal-only no redistribution",
                "public_export_allowed": False,
                "source_attribution": "Restricted registry",
            }
        ],
        public_artifact_families=[
            {
                "artifact_family": "public_policy_brief",
                "jurisdiction": "UA",
                "license": "CC-BY-4.0",
                "public_export_allowed": True,
                "source_attribution": ["restricted-msme-panel"],
                "redaction_status": "redacted",
                "authority_basis": "public interest publication",
            }
        ],
    )

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-compliance",
        run_id="R_compliance",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=_passing_quality_evidence(report),
    )
    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}

    assert scorecard["quality_status"] == "fail"
    assert scorecard["approval_state"] == "quality_failed"
    assert gates["privacy_compliance_report_present"]["status"] == "fail"
    assert gates["privacy_compliance_report_present"]["code"] == "license_conflict"
    assert any(
        failure["gate"] == "privacy_compliance_report_present"
        and failure["code"] == "license_conflict"
        for failure in scorecard["blocking_quality_failures"]
    )


def test_missing_privacy_compliance_report_blocks_serious_scorecard() -> None:
    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-compliance",
        run_id="R_compliance",
        execution_status="completed",
        job_payload=_complete_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence={
            key: value
            for key, value in _passing_quality_evidence(
                {"schema_version": "policyos.privacy_compliance_report.v1", "status": "pass"}
            ).items()
            if key != "privacy_compliance_report"
        },
    )
    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}

    assert scorecard["quality_status"] == "fail"
    assert gates["privacy_compliance_report_present"]["status"] == "fail"
    assert gates["privacy_compliance_report_present"]["code"] == (
        "privacy_compliance_report_missing"
    )
    assert any(
        failure["gate"] == "privacy_compliance_report_present"
        and failure["code"] == "privacy_compliance_report_missing"
        for failure in scorecard["blocking_quality_failures"]
    )


def test_compliance_override_requires_reviewer_reason_scope_expiry_and_evidence_refs() -> None:
    report = build_privacy_compliance_report(
        production_data_sources=[
            {
                "source_id": "restricted-msme-panel",
                "source_family": "production_msme_panel",
                "fields": [{"name": "owner_email", "retained": True}],
                "retention_class": "warm",
                "jurisdiction": "UA",
                "license": "Internal-only no redistribution",
                "public_export_allowed": False,
                "source_attribution": "Restricted registry",
            }
        ],
        public_artifact_families=[],
        override={
            "reviewer_identity": "governance@example.test",
            "reason": "Temporary legal hold while attribution is corrected.",
            "scope": "source:restricted-msme-panel",
            "evidence_refs": ["case://privacy-review/42"],
        },
    )

    assert report["override"]["valid"] is False
    assert report["override"]["missing_fields"] == ["expires_at"]
    assert any(issue["code"] == "compliance_override_incomplete" for issue in report["issues"])
