"""Privacy, licensing, and public-export compliance evidence builders."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

PRIVACY_COMPLIANCE_REPORT_SCHEMA_VERSION = "policyos.privacy_compliance_report.v1"

COMPLIANCE_OVERRIDE_REQUIRED_FIELDS = (
    "reviewer_identity",
    "reason",
    "scope",
    "expires_at",
    "evidence_refs",
)

_PII_FIELD_MARKERS = (
    "address",
    "birth",
    "dob",
    "email",
    "ip_address",
    "name",
    "national_id",
    "passport",
    "phone",
    "ssn",
    "tax_id",
    "taxpayer",
)
_PHI_FIELD_MARKERS = (
    "diagnosis",
    "health",
    "medical",
    "patient",
    "phi",
)
_REDACTED_STATUSES = {
    "aggregated",
    "anonymized",
    "de-identified",
    "deidentified",
    "masked",
    "pseudonymized",
    "redacted",
    "tokenized",
}
_RESTRICTED_LICENSE_MARKERS = (
    "all rights reserved",
    "confidential",
    "internal only",
    "internal-only",
    "no public export",
    "no redistribution",
    "non-commercial",
    "noncommercial",
    "not for redistribution",
    "personal use",
    "proprietary",
    "restricted",
)
_SAFE_SOURCE_KEYS = (
    "source_id",
    "source_family",
    "source_kind",
    "dataset_id",
    "version_id",
    "retention_class",
    "jurisdiction",
    "license",
    "public_export_allowed",
    "source_attribution",
)
_SAFE_ARTIFACT_KEYS = (
    "artifact_family",
    "family",
    "artifact_kind",
    "jurisdiction",
    "license",
    "public_export_allowed",
    "source_attribution",
    "redaction_status",
)


def build_privacy_compliance_report(
    *,
    production_data_sources: Iterable[Mapping[str, Any]] | None = None,
    public_artifact_families: Iterable[Mapping[str, Any]] | None = None,
    override: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build an auditable compliance report without embedding raw records."""

    issues: list[dict[str, Any]] = []
    source_summaries = [
        _source_summary(dict(source), index=index, issues=issues)
        for index, source in enumerate(production_data_sources or [])
        if isinstance(source, Mapping)
    ]
    artifact_summaries = [
        _artifact_summary(dict(artifact), index=index, issues=issues)
        for index, artifact in enumerate(public_artifact_families or [])
        if isinstance(artifact, Mapping)
    ]
    override_summary = _override_summary(override)
    if override is not None and not override_summary["valid"]:
        issues.append(
            _issue(
                code="compliance_override_incomplete",
                severity="blocking",
                subject_type="override",
                subject_id="privacy_compliance_override",
                message=(
                    "Compliance override is missing required reviewer attribution, "
                    "scope, expiry, or evidence refs."
                ),
                next_action=(
                    "Attach reviewer_identity, reason, scope, expires_at, and evidence_refs "
                    "before accepting a compliance override."
                ),
            )
        )

    blocking_count = sum(1 for issue in issues if issue["severity"] == "blocking")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "schema_version": PRIVACY_COMPLIANCE_REPORT_SCHEMA_VERSION,
        "generated_at": _utc(generated_at).isoformat(),
        "status": "fail" if blocking_count else ("warn" if warning_count else "pass"),
        "summary": {
            "production_data_source_count": len(source_summaries),
            "public_artifact_family_count": len(artifact_summaries),
            "pii_like_field_count": sum(
                len(source["pii_like_fields"]) for source in source_summaries
            ),
            "blocking_issue_count": blocking_count,
            "warning_count": warning_count,
        },
        "production_data_sources": source_summaries,
        "public_artifact_families": artifact_summaries,
        "issues": issues,
        "override_requirements": {
            "required_fields": list(COMPLIANCE_OVERRIDE_REQUIRED_FIELDS),
        },
        "override": override_summary,
    }


def normalize_privacy_compliance_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable report shape for scorecards and evidence bundles."""

    normalized = dict(report)
    normalized.setdefault("schema_version", PRIVACY_COMPLIANCE_REPORT_SCHEMA_VERSION)
    normalized.setdefault("generated_at", datetime.now(UTC).replace(microsecond=0).isoformat())
    issues = [
        dict(issue)
        for issue in normalized.get("issues", [])
        if isinstance(issue, Mapping)
    ]
    blocking_count = sum(
        1 for issue in issues if str(issue.get("severity") or "").casefold() == "blocking"
    )
    warning_count = sum(
        1 for issue in issues if str(issue.get("severity") or "").casefold() == "warning"
    )
    status = _status(normalized.get("status"))
    if blocking_count:
        status = "fail"
    elif status not in {"pass", "warn", "fail"}:
        status = "warn" if warning_count else "pass"
    normalized["status"] = status
    normalized["issues"] = issues
    summary = dict(normalized.get("summary") or {})
    summary.setdefault("blocking_issue_count", blocking_count)
    summary.setdefault("warning_count", warning_count)
    summary.setdefault(
        "production_data_source_count",
        len(normalized.get("production_data_sources") or []),
    )
    summary.setdefault(
        "public_artifact_family_count",
        len(normalized.get("public_artifact_families") or []),
    )
    normalized["summary"] = summary
    normalized.setdefault(
        "override_requirements",
        {"required_fields": list(COMPLIANCE_OVERRIDE_REQUIRED_FIELDS)},
    )
    normalized.setdefault("override", _override_summary(None))
    return normalized


def _source_summary(
    source: dict[str, Any],
    *,
    index: int,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    source_id = _clean_text(
        source.get("source_id")
        or source.get("id")
        or source.get("dataset_id")
        or source.get("name")
    ) or f"production_source_{index + 1}"
    fields = _field_specs(source)
    pii_fields = [
        _pii_field_summary(field, source)
        for field in fields
        if _field_is_pii_like(field, source)
    ]
    for field in pii_fields:
        if not field["basis"] and not _redaction_approved(field["redaction_status"]):
            issues.append(
                _issue(
                    code="pii_basis_or_redaction_missing",
                    severity="blocking",
                    subject_type="production_data_source",
                    subject_id=source_id,
                    field=str(field["field"]),
                    message=(
                        "PII/PHI-like field has no approved basis and no approved redaction."
                    ),
                    next_action=(
                        "Provide consent/authority basis, remove the field, or mark an "
                        "approved redaction status before production approval."
                    ),
                )
            )

    license_text = _clean_text(source.get("license"))
    public_export_allowed = _bool_or_none(source.get("public_export_allowed"))
    if _license_conflicts(license_text):
        issues.append(
            _issue(
                code="license_conflict",
                severity="blocking",
                subject_type="production_data_source",
                subject_id=source_id,
                message="Production data source license conflicts with public artifact export.",
                next_action=(
                    "Replace the source, obtain explicit publication rights, or route through "
                    "a reviewer-attributed compliance override."
                ),
            )
        )
    if public_export_allowed is False:
        issues.append(
            _issue(
                code="public_export_not_allowed",
                severity="blocking",
                subject_type="production_data_source",
                subject_id=source_id,
                message="Production data source is marked as not allowed for public export.",
                next_action=(
                    "Remove this source from public artifacts or attach explicit export authority."
                ),
            )
        )

    return {
        "source_id": source_id,
        "source_family": _clean_text(source.get("source_family")),
        "source_kind": _clean_text(source.get("source_kind")) or "production_data",
        "jurisdiction": _clean_text(source.get("jurisdiction")),
        "retention_class": _clean_text(
            source.get("retention_class") or source.get("retention")
        ),
        "license": license_text,
        "public_export_allowed": public_export_allowed,
        "source_attribution": _attribution_present(source),
        "authority_basis": _clean_text(source.get("authority_basis")),
        "consent_basis": _clean_text(source.get("consent_basis")),
        "minimization": _minimization_summary(source),
        "field_count": len(fields),
        "pii_like_fields": pii_fields,
        "metadata": _safe_metadata(source, _SAFE_SOURCE_KEYS),
        "status": _subject_status(issues, "production_data_source", source_id),
    }


def _artifact_summary(
    artifact: dict[str, Any],
    *,
    index: int,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    artifact_family = _clean_text(
        artifact.get("artifact_family")
        or artifact.get("family")
        or artifact.get("artifact_kind")
        or artifact.get("name")
    ) or f"public_artifact_family_{index + 1}"
    license_text = _clean_text(artifact.get("license"))
    public_export_allowed = _bool_or_none(artifact.get("public_export_allowed"))
    if _license_conflicts(license_text):
        issues.append(
            _issue(
                code="license_conflict",
                severity="blocking",
                subject_type="public_artifact_family",
                subject_id=artifact_family,
                message="Public artifact family license conflicts with publication.",
                next_action=(
                    "Change the publication license or obtain explicit publication authority."
                ),
            )
        )
    if public_export_allowed is False:
        issues.append(
            _issue(
                code="public_export_not_allowed",
                severity="blocking",
                subject_type="public_artifact_family",
                subject_id=artifact_family,
                message="Public artifact family is marked as not allowed for export.",
                next_action="Do not publish this artifact family until export constraints clear.",
            )
        )

    return {
        "artifact_family": artifact_family,
        "jurisdiction": _clean_text(artifact.get("jurisdiction")),
        "license": license_text,
        "public_export_allowed": public_export_allowed,
        "source_attribution": _attribution_present(artifact),
        "authority_basis": _clean_text(artifact.get("authority_basis")),
        "redaction_status": _clean_text(artifact.get("redaction_status")),
        "metadata": _safe_metadata(artifact, _SAFE_ARTIFACT_KEYS),
        "status": _subject_status(issues, "public_artifact_family", artifact_family),
    }


def _field_specs(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for raw in _list(source.get("fields")):
        if isinstance(raw, Mapping):
            fields.append(dict(raw))
        elif str(raw or "").strip():
            fields.append({"name": str(raw).strip()})
    schema = source.get("schema")
    if isinstance(schema, Mapping):
        for raw in _list(schema.get("fields") or schema.get("columns")):
            if isinstance(raw, Mapping):
                fields.append(dict(raw))
            elif str(raw or "").strip():
                fields.append({"name": str(raw).strip()})
    for raw in _list(source.get("columns")):
        if isinstance(raw, Mapping):
            fields.append(dict(raw))
        elif str(raw or "").strip():
            fields.append({"name": str(raw).strip()})
    for pii_name in _list(source.get("pii_fields") or source.get("phi_fields")):
        text = _clean_text(pii_name)
        if text:
            fields.append({"name": text, "pii": True})
    deduped: dict[str, dict[str, Any]] = {}
    for field in fields:
        name = _field_name(field)
        if name is not None:
            deduped.setdefault(name, field)
    return list(deduped.values())


def _pii_field_summary(field: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    basis = _clean_text(
        field.get("basis")
        or field.get("legal_basis")
        or field.get("authority_basis")
        or field.get("consent_basis")
        or source.get("basis")
        or source.get("legal_basis")
        or source.get("authority_basis")
        or source.get("consent_basis")
    )
    basis_ref = _clean_text(
        field.get("basis_ref")
        or field.get("authority_basis_ref")
        or field.get("consent_ref")
        or source.get("basis_ref")
        or source.get("authority_basis_ref")
        or source.get("consent_ref")
    )
    return {
        "field": _field_name(field) or "unknown",
        "basis": basis,
        "basis_ref": basis_ref,
        "redaction_status": _clean_text(
            field.get("redaction_status") or source.get("redaction_status")
        ),
    }


def _field_name(field: Mapping[str, Any]) -> str | None:
    return _clean_text(field.get("name") or field.get("field") or field.get("column"))


def _field_is_pii_like(field: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    explicit = field.get("pii") or field.get("phi") or field.get("sensitive")
    if isinstance(explicit, bool):
        return explicit
    pii_level = str(field.get("pii_level") or source.get("pii_level") or "").casefold()
    if pii_level and pii_level not in {"none", "no", "false"}:
        return True
    field_class = str(field.get("classification") or field.get("data_class") or "").casefold()
    if any(marker in field_class for marker in ("pii", "phi", "personal", "health")):
        return True
    name = (_field_name(field) or "").replace("-", "_").casefold()
    return any(marker in name for marker in (*_PII_FIELD_MARKERS, *_PHI_FIELD_MARKERS))


def _minimization_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    minimization = source.get("minimization")
    if isinstance(minimization, Mapping):
        retained = _list(minimization.get("retained_fields"))
        excluded = _list(minimization.get("excluded_fields"))
        purpose = _clean_text(minimization.get("purpose") or minimization.get("basis"))
    else:
        retained = _list(source.get("retained_fields"))
        excluded = _list(source.get("excluded_fields"))
        purpose = _clean_text(
            source.get("minimization_basis")
            or source.get("purpose")
            or source.get("data_use_purpose")
        )
    return {
        "present": bool(purpose or retained or excluded),
        "purpose": purpose,
        "retained_field_count": len(retained),
        "excluded_field_count": len(excluded),
    }


def _override_summary(override: Mapping[str, Any] | None) -> dict[str, Any]:
    required = list(COMPLIANCE_OVERRIDE_REQUIRED_FIELDS)
    if override is None:
        return {
            "status": "not_requested",
            "valid": False,
            "required_fields": required,
            "missing_fields": required,
        }
    missing = [
        field
        for field in required
        if not _override_field_present(field, override.get(field))
    ]
    return {
        "status": "valid" if not missing else "invalid",
        "valid": not missing,
        "required_fields": required,
        "missing_fields": missing,
        "reviewer_identity": _clean_text(override.get("reviewer_identity")),
        "scope": _clean_text(override.get("scope")),
        "evidence_refs": [
            ref for ref in (_clean_text(value) for value in _list(override.get("evidence_refs"))) if ref
        ],
    }


def _override_field_present(field: str, value: Any) -> bool:
    if field == "evidence_refs":
        return bool([item for item in _list(value) if _clean_text(item)])
    return _clean_text(value) is not None


def _issue(
    *,
    code: str,
    severity: str,
    subject_type: str,
    subject_id: str,
    message: str,
    next_action: str,
    field: str | None = None,
) -> dict[str, Any]:
    issue = {
        "code": code,
        "severity": severity,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "message": message,
        "next_action": next_action,
    }
    if field is not None:
        issue["field"] = field
    return issue


def _subject_status(
    issues: list[dict[str, Any]],
    subject_type: str,
    subject_id: str,
) -> str:
    subject_issues = [
        issue
        for issue in issues
        if issue["subject_type"] == subject_type and issue["subject_id"] == subject_id
    ]
    if any(issue["severity"] == "blocking" for issue in subject_issues):
        return "fail"
    if subject_issues:
        return "warn"
    return "pass"


def _safe_metadata(source: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {
        key: source[key]
        for key in keys
        if key in source and _safe_scalar_or_list(source[key]) is not None
    }


def _safe_scalar_or_list(value: Any) -> Any | None:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        cleaned = [_safe_scalar_or_list(item) for item in value]
        return [item for item in cleaned if item is not None]
    return None


def _attribution_present(source: Mapping[str, Any]) -> bool:
    value = source.get("source_attribution") or source.get("attribution")
    if isinstance(value, list):
        return any(_clean_text(item) for item in value)
    return _clean_text(value) is not None


def _license_conflicts(license_text: str | None) -> bool:
    if license_text is None:
        return False
    lowered = license_text.casefold()
    return any(marker in lowered for marker in _RESTRICTED_LICENSE_MARKERS)


def _redaction_approved(status: str | None) -> bool:
    return status is not None and status.casefold() in _REDACTED_STATUSES


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _status(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return {
        "ok": "pass",
        "passed": "pass",
        "success": "pass",
        "failed": "fail",
        "warning": "warn",
    }.get(text, text)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 512 or any(char in text for char in "\r\n\t"):
        return None
    return text


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "COMPLIANCE_OVERRIDE_REQUIRED_FIELDS",
    "PRIVACY_COMPLIANCE_REPORT_SCHEMA_VERSION",
    "build_privacy_compliance_report",
    "normalize_privacy_compliance_report",
]
