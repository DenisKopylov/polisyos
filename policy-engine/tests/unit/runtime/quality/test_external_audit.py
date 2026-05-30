# ruff: noqa: S101

from __future__ import annotations

from copy import deepcopy

import pytest

from polisyos.core.audit import StepResult, StepStatus, VerificationReport
from polisyos.runtime.quality.external_audit import (
    EXTERNAL_AUDIT_RECORD_SCHEMA_VERSION,
    ExternalAuditRecordError,
    build_public_audit_archive_record,
    validate_public_audit_archive_record,
)
from polisyos.runtime.quality.projection_semantics import (
    build_policy_design_case_projection_semantics,
)
from tests._helpers.policy_design_case_projection import policy_design_case


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _passing_report() -> VerificationReport:
    report = VerificationReport(
        package_path="public-audit/R_phase27_3.polisyos-audit.tar.gz",
        run_id="R_phase27_3",
    )
    report.overall_status = "PASS"
    report.prov_entities = 3
    report.prov_activities = 2
    report.prov_agents = 1
    report.package_integrity = StepResult(
        step_name="Package Integrity",
        status=StepStatus.PASS,
        checks_passed=4,
    )
    report.provenance_validation = StepResult(
        step_name="Provenance Validation",
        status=StepStatus.PASS,
        checks_passed=3,
    )
    report.slsa_verification = StepResult(
        step_name="SLSA Verification",
        status=StepStatus.PASS,
        checks_passed=3,
    )
    return report


def _record_kwargs() -> dict[str, object]:
    return {
        "run_id": "R_phase27_3",
        "archive_path": "public-audit/R_phase27_3.polisyos-audit.tar.gz",
        "archive_sha256": _sha("a"),
        "archive_size_bytes": 4096,
        "verification_report": _passing_report(),
        "exported_refs": {
            "audit_archive": {
                "ref": "public://policyos/audit/R_phase27_3/archive.tar.gz",
                "sha256": _sha("a"),
            },
            "public_export_bundle": {
                "ref": "public://policyos/audit/R_phase27_3/public-export.json",
                "sha256": _sha("b"),
            },
        },
        "evidence_rights": {
            "classification": "public_redacted",
            "redacted_private_fields": ["tenant_id", "reviewer_private_notes"],
        },
    }


def test_public_audit_archive_record_wires_core_audit_surfaces_without_private_context() -> None:
    record = build_public_audit_archive_record(**_record_kwargs())

    assert record["schema_version"] == EXTERNAL_AUDIT_RECORD_SCHEMA_VERSION
    assert record["record_family"] == "publication_trust_and_external_governance.v1"
    assert record["status"] == "pass"
    assert record["public_archive"] == {
        "path": "public-audit/R_phase27_3.polisyos-audit.tar.gz",
        "sha256": _sha("a"),
        "size_bytes": 4096,
        "verifiable_without_private_operator_context": True,
    }
    assert record["core_audit"]["prov_json"] == {
        "path": "provenance/prov.json",
        "status": "pass",
        "entity_count": 3,
        "activity_count": 2,
        "agent_count": 1,
    }
    assert record["core_audit"]["slsa"]["attestation_path"] == "slsa/attestation.json"
    assert record["core_audit"]["slsa"]["status"] == "pass"
    assert record["core_audit"]["standalone_verifier"]["path"] == "verification/verify.py"
    assert "python verification/verify.py" in record["core_audit"]["standalone_verifier"]["command"]
    assert record["core_audit"]["safe_archive_tool"] == (
        "polisyos.core.audit.safe_tar.safe_extract_tar"
    )
    assert record["public_private_boundary"]["private_operator_context_required"] is False
    assert set(record["exported_refs"]) == {"audit_archive", "public_export_bundle"}

    validation = validate_public_audit_archive_record(record)
    assert validation["status"] == "pass"
    assert validation["issues"] == []


def test_public_audit_archive_record_surfaces_policy_design_case_projection_truth() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="public_export",
        source_payload={
            "authority_role": "final_decision_artifact",
            "audit_refs": ["audit://pdc/w5a/external-audit"],
            "closeout_verdict": {
                "status": "blocked",
                "verdict": "cannot_closeout",
                "can_closeout": False,
                "issues": [
                    {
                        "code": "omitted_blocked_claim",
                        "severity": "omission",
                        "message": "Claim rec_1 is omitted from the public summary.",
                        "claim_ids": ["rec_1"],
                    }
                ],
            },
        },
    )
    projection["contract_verification_status"] = "pass"

    record = build_public_audit_archive_record(
        **_record_kwargs(),
        policy_design_case_projection=projection,
    )

    surface = record["policy_design_case_surface"]
    assert surface["authority_role"] == "projection_only"
    assert surface["closeout_truth"]["can_closeout"] is False
    assert surface["omission_manifest"][0]["claim_ids"] == ["rec_1"]
    assert "audit://pdc/w5a/external-audit" in surface["audit_refs"]
    assert surface["contract_verification_status"] == "pass"

    validation = validate_public_audit_archive_record(record)
    assert validation["status"] == "pass"


def test_public_audit_archive_record_rejects_missing_prov() -> None:
    kwargs = _record_kwargs()
    report = deepcopy(kwargs["verification_report"])
    assert isinstance(report, VerificationReport)
    report.provenance_validation.status = StepStatus.FAIL
    report.prov_entities = 0
    kwargs["verification_report"] = report

    with pytest.raises(ExternalAuditRecordError, match="external_audit_prov_missing"):
        build_public_audit_archive_record(**kwargs)


def test_public_audit_archive_record_rejects_missing_slsa() -> None:
    kwargs = _record_kwargs()
    report = deepcopy(kwargs["verification_report"])
    assert isinstance(report, VerificationReport)
    report.slsa_verification.status = StepStatus.SKIP
    kwargs["verification_report"] = report

    with pytest.raises(ExternalAuditRecordError, match="external_audit_slsa_missing"):
        build_public_audit_archive_record(**kwargs)


def test_public_audit_archive_record_rejects_unsafe_archive_path() -> None:
    kwargs = _record_kwargs()
    kwargs["archive_path"] = "../private/R_phase27_3.polisyos-audit.tar.gz"

    with pytest.raises(ExternalAuditRecordError, match="external_audit_archive_path_unsafe"):
        build_public_audit_archive_record(**kwargs)


def test_public_audit_archive_record_rejects_unverifiable_exported_refs() -> None:
    kwargs = _record_kwargs()
    kwargs["exported_refs"] = {
        "public_export_bundle": {
            "ref": "public://policyos/audit/R_phase27_3/public-export.json",
        }
    }

    with pytest.raises(ExternalAuditRecordError, match="external_audit_exported_ref_unverifiable"):
        build_public_audit_archive_record(**kwargs)
