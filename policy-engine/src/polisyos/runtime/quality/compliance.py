"""Runtime gates for privacy, licensing, and public-export compliance evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.data_forge.read_api import normalize_privacy_compliance_report

PRIVACY_COMPLIANCE_REPORT_KEY = "privacy_compliance_report"
PRIVACY_COMPLIANCE_REPORT_FILENAME = "privacy_compliance_report.json"
PRIVACY_COMPLIANCE_REPORT_REF_KEY = "privacy_compliance_report_ref"
PRIVACY_COMPLIANCE_REPORT_EVIDENCE_REF = (
    f"quality_evidence/{PRIVACY_COMPLIANCE_REPORT_FILENAME}"
)


def normalize_runtime_privacy_compliance_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a runtime compliance report before scorecard evaluation."""

    return normalize_privacy_compliance_report(report)


def privacy_compliance_gate_details(report: Any) -> dict[str, Any] | None:
    """Return scorecard gate details for a compliance report, if one is present."""

    if not isinstance(report, Mapping):
        return None
    normalized = normalize_runtime_privacy_compliance_report(report)
    status = str(normalized.get("status") or "missing").casefold()
    issues = [
        dict(issue)
        for issue in normalized.get("issues", [])
        if isinstance(issue, Mapping)
    ]
    first_blocking = next(
        (
            issue
            for issue in issues
            if str(issue.get("severity") or "").casefold() == "blocking"
        ),
        None,
    )
    first_issue = first_blocking or (issues[0] if issues else None)
    code = "privacy_compliance_report_present"
    message = "Privacy, licensing, and compliance evidence is present."
    next_action = None
    if status == "fail":
        code = str(first_issue.get("code") or "privacy_compliance_blocking_failure")
        message = (
            "Privacy, licensing, or public-export compliance evidence has blocking issues."
        )
        next_action = str(
            first_issue.get("next_action")
            or "Resolve compliance failures before production artifact publication."
        )
    elif status == "warn":
        code = str(first_issue.get("code") or "privacy_compliance_warning")
        message = "Privacy, licensing, and compliance evidence has warnings."
        next_action = str(
            first_issue.get("next_action")
            or "Review compliance warnings before production approval."
        )

    return {
        "code": code,
        "status": "fail" if status == "fail" else ("warn" if status == "warn" else "pass"),
        "message": message,
        "phase": "privacy_compliance",
        "evidence_ref": PRIVACY_COMPLIANCE_REPORT_EVIDENCE_REF,
        "next_action": next_action,
        "blocking": status == "fail",
    }


__all__ = [
    "PRIVACY_COMPLIANCE_REPORT_EVIDENCE_REF",
    "PRIVACY_COMPLIANCE_REPORT_FILENAME",
    "PRIVACY_COMPLIANCE_REPORT_KEY",
    "PRIVACY_COMPLIANCE_REPORT_REF_KEY",
    "normalize_runtime_privacy_compliance_report",
    "privacy_compliance_gate_details",
]
