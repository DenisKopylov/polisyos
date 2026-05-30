"""External audit archive records for public Policy Design Case verification."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.core.audit import StepStatus, VerificationReport
from polisyos.runtime.quality.projection_semantics import (
    PolicyDesignCaseProjectionError,
    assert_policy_design_projection_not_authority,
)

EXTERNAL_AUDIT_RECORD_SCHEMA_VERSION = "policyos.policy_design_case.external_audit_record.v1"
EXTERNAL_AUDIT_RECORD_FAMILY = "publication_trust_and_external_governance.v1"
EXTERNAL_AUDIT_SAFE_ARCHIVE_TOOL = "polisyos.core.audit.safe_tar.safe_extract_tar"
EXTERNAL_AUDIT_VERIFIER = "polisyos.core.audit.verifier.AuditPackageVerifier"
EXTERNAL_AUDIT_STANDALONE_VERIFIER_TEMPLATE = (
    "polisyos.core.audit.standalone_verifier_template"
)

_SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$", re.IGNORECASE)
_ALLOWED_PUBLIC_REF_PREFIXES = ("public://", "https://", "archive://")
_PRIVATE_REF_PREFIXES = ("cas://", "file://", "sha256:")


class ExternalAuditRecordError(ValueError):
    """Raised when a public external-audit archive record is not verifiable."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


def build_public_audit_archive_record(
    *,
    run_id: str,
    archive_path: str | Path,
    archive_sha256: str,
    archive_size_bytes: int,
    verification_report: VerificationReport | Mapping[str, Any],
    exported_refs: Mapping[str, Mapping[str, Any]] | None = None,
    evidence_rights: Mapping[str, Any] | None = None,
    policy_design_case_projection: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a public audit archive record from a verified core audit package."""

    report = _report_payload(verification_report)
    archive = _public_archive(archive_path, archive_sha256, archive_size_bytes)
    refs = _exported_refs(exported_refs or {})
    pdc_surface = (
        _policy_design_case_surface(policy_design_case_projection)
        if policy_design_case_projection is not None
        else None
    )
    record = {
        "schema_version": EXTERNAL_AUDIT_RECORD_SCHEMA_VERSION,
        "record_family": EXTERNAL_AUDIT_RECORD_FAMILY,
        "record_id": f"external-audit-{run_id}",
        "run_id": str(run_id),
        "generated_at": (generated_at or datetime.now(UTC))
        .replace(microsecond=0)
        .isoformat(),
        "status": "pass" if str(report.get("overall_status")) == "PASS" else "fail",
        "public_archive": archive,
        "core_audit": {
            "package_format": "polisyos-audit-v1",
            "prov_json": {
                "path": "provenance/prov.json",
                "status": _step_status_label(report.get("provenance_validation")).lower(),
                "entity_count": _int(report.get("prov_entities")),
                "activity_count": _int(report.get("prov_activities")),
                "agent_count": _int(report.get("prov_agents")),
            },
            "slsa": {
                "attestation_path": "slsa/attestation.json",
                "signature_path": "slsa/signature.json",
                "transparency_path": "slsa/transparency_entry.json",
                "status": _step_status_label(report.get("slsa_verification")).lower(),
            },
            "verifier": {
                "module": EXTERNAL_AUDIT_VERIFIER,
                "status": str(report.get("overall_status") or "FAIL").lower(),
            },
            "standalone_verifier": {
                "path": "verification/verify.py",
                "template": EXTERNAL_AUDIT_STANDALONE_VERIFIER_TEMPLATE,
                "command": f"python verification/verify.py {archive['path']}",
            },
            "safe_archive_tool": EXTERNAL_AUDIT_SAFE_ARCHIVE_TOOL,
        },
        "verification": {
            "overall_status": str(report.get("overall_status") or "FAIL"),
            "package_path": str(report.get("package_path") or archive["path"]),
            "run_id": str(report.get("run_id") or run_id),
            "failures": list(report.get("failures") or []),
            "warnings": list(report.get("warnings") or []),
        },
        "exported_refs": refs,
        "public_private_boundary": {
            "private_operator_context_required": False,
            "public_ref_count": len(refs),
            "redacted_or_access_controlled": list(
                (evidence_rights or {}).get("redacted_private_fields", [])
                if isinstance(evidence_rights, Mapping)
                else []
            ),
        },
        "evidence_rights": dict(evidence_rights or {}),
    }
    if pdc_surface is not None:
        record["policy_design_case_surface"] = pdc_surface

    validation = validate_public_audit_archive_record(record)
    if validation["issues"]:
        first = validation["issues"][0]
        raise ExternalAuditRecordError(str(first["code"]), str(first["message"]))
    return record


def validate_public_audit_archive_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate public archive replayability without private operator context."""

    issues: list[dict[str, str]] = []
    if record.get("schema_version") != EXTERNAL_AUDIT_RECORD_SCHEMA_VERSION:
        issues.append(
            _issue(
                "external_audit_schema_version_invalid",
                "External audit record must use the current schema version.",
                "schema_version",
            )
        )
    if record.get("record_family") != EXTERNAL_AUDIT_RECORD_FAMILY:
        issues.append(
            _issue(
                "external_audit_record_family_invalid",
                "External audit record must bind to publication trust governance.",
                "record_family",
            )
        )

    archive = record.get("public_archive")
    if not isinstance(archive, Mapping):
        issues.append(
            _issue(
                "external_audit_public_archive_missing",
                "Public audit archive metadata is required.",
                "public_archive",
            )
        )
    else:
        issues.extend(_archive_issues(archive))

    core_audit = record.get("core_audit")
    if not isinstance(core_audit, Mapping):
        issues.append(
            _issue(
                "external_audit_core_audit_missing",
                "Core audit surface metadata is required.",
                "core_audit",
            )
        )
    else:
        issues.extend(_core_audit_issues(core_audit))

    verification = record.get("verification")
    if not isinstance(verification, Mapping) or verification.get("overall_status") != "PASS":
        issues.append(
            _issue(
                "external_audit_verification_failed",
                "Public audit archive must have a passing verification report.",
                "verification.overall_status",
            )
        )

    exported_refs = record.get("exported_refs")
    if isinstance(exported_refs, Mapping):
        for key, value in exported_refs.items():
            issues.extend(_exported_ref_issues(str(key), value))
    elif exported_refs is not None:
        issues.append(
            _issue(
                "external_audit_exported_ref_unverifiable",
                "exported_refs must be a mapping of public refs with SHA-256 digests.",
                "exported_refs",
            )
        )

    boundary = record.get("public_private_boundary")
    if not isinstance(boundary, Mapping) or boundary.get("private_operator_context_required"):
        issues.append(
            _issue(
                "external_audit_private_operator_context_required",
                "Public audit archives must verify without private operator context.",
                "public_private_boundary.private_operator_context_required",
            )
        )

    pdc_surface = record.get("policy_design_case_surface")
    if pdc_surface is not None:
        if not isinstance(pdc_surface, Mapping):
            issues.append(
                _issue(
                    "external_audit_policy_design_case_surface_invalid",
                    "Policy Design Case audit surface must be a mapping.",
                    "policy_design_case_surface",
                )
            )
        else:
            issues.extend(_policy_design_case_surface_issues(pdc_surface))

    return {
        "schema_version": "policyos.policy_design_case.external_audit_record.validation.v1",
        "status": "fail" if issues else "pass",
        "summary": {"issue_count": len(issues)},
        "issues": issues,
    }


def _report_payload(report: VerificationReport | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(report, VerificationReport):
        return report.to_dict()
    return dict(report)


def _public_archive(path: str | Path, sha256: str, size_bytes: int) -> dict[str, Any]:
    archive_path = _safe_relative_archive_path(path)
    return {
        "path": archive_path,
        "sha256": _normalize_sha256(sha256),
        "size_bytes": int(size_bytes),
        "verifiable_without_private_operator_context": True,
    }


def _exported_refs(refs: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    for key, value in refs.items():
        if not isinstance(value, Mapping):
            normalized[str(key)] = {"ref": str(value), "sha256": ""}
            continue
        normalized[str(key)] = {
            "ref": str(value.get("ref") or ""),
            "sha256": _normalize_sha256(str(value.get("sha256") or "")),
        }
    return normalized


def _policy_design_case_surface(projection: Mapping[str, Any]) -> dict[str, Any]:
    try:
        safe_projection = assert_policy_design_projection_not_authority(projection)
    except PolicyDesignCaseProjectionError as exc:
        raise ExternalAuditRecordError(exc.code, str(exc)) from exc
    return {
        "schema_version": safe_projection.get("schema_version"),
        "surface": safe_projection.get("surface"),
        "audience": safe_projection.get("audience"),
        "authority_role": safe_projection.get("authority_role"),
        "closeout_truth": safe_projection.get("closeout_truth"),
        "projection_gaps": safe_projection.get("projection_gaps", []),
        "omission_manifest": safe_projection.get("omission_manifest", []),
        "contested_records": safe_projection.get("contested_records", []),
        "audit_refs": safe_projection.get("audit_refs", []),
        "contract_verification_status": safe_projection.get("contract_verification_status"),
        "contract_verification_refs": safe_projection.get("contract_verification_refs", []),
        "may_not_be_used_for": safe_projection.get("may_not_be_used_for", []),
    }


def _policy_design_case_surface_issues(surface: Mapping[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if surface.get("authority_role") != "projection_only":
        issues.append(
            _issue(
                "external_audit_policy_design_case_surface_mints_authority",
                "Policy Design Case audit surface must remain projection_only.",
                "policy_design_case_surface.authority_role",
            )
        )
    if not isinstance(surface.get("closeout_truth"), Mapping):
        issues.append(
            _issue(
                "external_audit_policy_design_case_closeout_truth_missing",
                "Policy Design Case audit surface must expose closeout truth.",
                "policy_design_case_surface.closeout_truth",
            )
        )
    if surface.get("contract_verification_status") == "fail":
        issues.append(
            _issue(
                "external_audit_policy_design_case_contract_failed",
                "Policy Design Case audit surface cannot report failed contract verification.",
                "policy_design_case_surface.contract_verification_status",
            )
        )
    return issues


def _safe_relative_archive_path(path: str | Path) -> str:
    value = str(path)
    rel = Path(value)
    if (
        not value.strip()
        or rel.is_absolute()
        or any(part in ("", "..") for part in rel.parts)
        or not value.endswith(".polisyos-audit.tar.gz")
    ):
        raise ExternalAuditRecordError(
            "external_audit_archive_path_unsafe",
            "Archive path must be a safe relative .polisyos-audit.tar.gz path.",
        )
    return rel.as_posix()


def _normalize_sha256(value: str) -> str:
    text = str(value or "").strip()
    if not _SHA256_RE.fullmatch(text):
        return text
    return text if text.casefold().startswith("sha256:") else f"sha256:{text.lower()}"


def _archive_issues(archive: Mapping[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    try:
        _safe_relative_archive_path(str(archive.get("path") or ""))
    except ExternalAuditRecordError:
        issues.append(
            _issue(
                "external_audit_archive_path_unsafe",
                "Archive path must be a safe relative .polisyos-audit.tar.gz path.",
                "public_archive.path",
            )
        )
    if not _is_sha256(archive.get("sha256")):
        issues.append(
            _issue(
                "external_audit_archive_digest_missing",
                "Public archive metadata must include a SHA-256 digest.",
                "public_archive.sha256",
            )
        )
    if _int(archive.get("size_bytes")) <= 0:
        issues.append(
            _issue(
                "external_audit_archive_size_missing",
                "Public archive metadata must include a positive size.",
                "public_archive.size_bytes",
            )
        )
    if archive.get("verifiable_without_private_operator_context") is not True:
        issues.append(
            _issue(
                "external_audit_private_operator_context_required",
                "Public archive must be marked verifiable without private operator context.",
                "public_archive.verifiable_without_private_operator_context",
            )
        )
    return issues


def _core_audit_issues(core_audit: Mapping[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    prov = core_audit.get("prov_json")
    if (
        not isinstance(prov, Mapping)
        or prov.get("path") != "provenance/prov.json"
        or prov.get("status") != "pass"
        or _int(prov.get("entity_count")) <= 0
    ):
        issues.append(
            _issue(
                "external_audit_prov_missing",
                "External audit records require passing PROV JSON evidence.",
                "core_audit.prov_json",
            )
        )

    slsa = core_audit.get("slsa")
    if (
        not isinstance(slsa, Mapping)
        or slsa.get("attestation_path") != "slsa/attestation.json"
        or slsa.get("status") != "pass"
    ):
        issues.append(
            _issue(
                "external_audit_slsa_missing",
                "External audit records require passing SLSA attestation evidence.",
                "core_audit.slsa",
            )
        )

    standalone = core_audit.get("standalone_verifier")
    if not isinstance(standalone, Mapping) or standalone.get("path") != "verification/verify.py":
        issues.append(
            _issue(
                "external_audit_standalone_verifier_missing",
                "External audit records require the bundled standalone verifier.",
                "core_audit.standalone_verifier",
            )
        )

    if core_audit.get("safe_archive_tool") != EXTERNAL_AUDIT_SAFE_ARCHIVE_TOOL:
        issues.append(
            _issue(
                "external_audit_safe_archive_tool_missing",
                "External audit records must point to the safe archive extractor.",
                "core_audit.safe_archive_tool",
            )
        )
    return issues


def _exported_ref_issues(key: str, value: object) -> list[dict[str, str]]:
    if not isinstance(value, Mapping):
        return [
            _issue(
                "external_audit_exported_ref_unverifiable",
                "Exported public refs must include ref and sha256 fields.",
                f"exported_refs.{key}",
            )
        ]
    ref = str(value.get("ref") or "")
    sha256 = value.get("sha256")
    if not _public_verifiable_ref(ref) or not _is_sha256(sha256):
        return [
            _issue(
                "external_audit_exported_ref_unverifiable",
                "Exported ref must be public and carry a SHA-256 digest.",
                f"exported_refs.{key}",
            )
        ]
    return []


def _public_verifiable_ref(ref: str) -> bool:
    value = ref.strip()
    if not value or value.casefold().startswith(_PRIVATE_REF_PREFIXES):
        return False
    if value.startswith(_ALLOWED_PUBLIC_REF_PREFIXES):
        return True
    rel = Path(value)
    return not rel.is_absolute() and not any(part in ("", "..") for part in rel.parts)


def _step_status_label(step: object) -> str:
    if isinstance(step, Mapping):
        status = step.get("status", StepStatus.SKIP)
    else:
        status = getattr(step, "status", StepStatus.SKIP)
    if hasattr(status, "value"):
        return str(status.value)
    text = str(status or StepStatus.SKIP.value)
    if text.startswith("StepStatus."):
        return text.rsplit(".", 1)[1]
    return text


def _is_sha256(value: object) -> bool:
    return bool(_SHA256_RE.fullmatch(str(value or "").strip()))


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _issue(code: str, message: str, field: str) -> dict[str, str]:
    return {"code": code, "message": message, "field": field}


__all__ = [
    "EXTERNAL_AUDIT_RECORD_FAMILY",
    "EXTERNAL_AUDIT_RECORD_SCHEMA_VERSION",
    "ExternalAuditRecordError",
    "build_public_audit_archive_record",
    "validate_public_audit_archive_record",
]
