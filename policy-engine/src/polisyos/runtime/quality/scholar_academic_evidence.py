"""Runtime-quality facade for Scholar academic evidence records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from polisyos.scholar import (
    SCHOLAR_ACADEMIC_EVIDENCE_FILENAME,
    SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY,
    SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION,
    build_scholar_academic_evidence_report,
    build_scholar_academic_evidence_report_from_web_bundle,
    normalize_scholar_academic_evidence_report as _normalize_scholar_report,
    scholar_academic_evidence_required,
)

SCHOLAR_ACADEMIC_EVIDENCE_BOUNDARY_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.scholar_academic_evidence_boundary.v1"
)
SCHOLAR_ACADEMIC_EVIDENCE_RECORD_FAMILY = "scholar_academic_evidence.v1"
SCHOLAR_ACADEMIC_EVIDENCE_PRODUCER_OWNER = "team-scholar"
SCHOLAR_ACADEMIC_EVIDENCE_READER_OWNER = "team-runtime-quality"


def normalize_scholar_academic_evidence_report(
    report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize Scholar evidence and make missing records reader-compatible."""

    if not isinstance(report, Mapping):
        return {
            "schema_version": SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION,
            "status": "fail",
            "issues": [
                {
                    "code": "policy_design_scholar_academic_evidence_missing",
                    "severity": "fail",
                    "phase": "scholar_academic_evidence",
                    "message": (
                        "Serious claims require Scholar academic/grey-literature "
                        "evidence or a typed literature-deficit blocker."
                    ),
                    "next_action": (
                        "Emit research intent, query graph, provider trace, source "
                        "scoring, snippets, citations, freshness, corpus lineage, "
                        "support/conflict links, or a typed Scholar blocker."
                    ),
                }
            ],
            "literature_deficit_blockers": [],
        }
    return _normalize_scholar_report(report)


def build_scholar_academic_evidence_boundary_record(
    report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the runtime residual-boundary record read by PDC closeout."""

    normalized = normalize_scholar_academic_evidence_report(report)
    issues = _mapping_list(normalized.get("issues"))
    blockers = _mapping_list(normalized.get("literature_deficit_blockers")) or _mapping_list(
        normalized.get("blockers")
    )
    status = str(normalized.get("status") or "").strip().casefold()
    if issues:
        boundary_status = "failed"
    elif status == "blocked" or blockers:
        boundary_status = "blocked"
    else:
        boundary_status = "pass"
    evidence_ref = _first_ref(normalized) or _derived_ref(normalized)
    runtime_event_ref = (
        _text(normalized.get("runtime_event_ref"))
        or f"event://policy-design-case/scholar-academic-evidence/{evidence_ref}"
    )
    return {
        "schema_version": SCHOLAR_ACADEMIC_EVIDENCE_BOUNDARY_SCHEMA_VERSION,
        "source_schema_version": SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION,
        "record_id": "policy-design-scholar-academic-evidence-boundary",
        "record_family": SCHOLAR_ACADEMIC_EVIDENCE_RECORD_FAMILY,
        "status": boundary_status,
        "producer_owner": SCHOLAR_ACADEMIC_EVIDENCE_PRODUCER_OWNER,
        "reader_owner": SCHOLAR_ACADEMIC_EVIDENCE_READER_OWNER,
        "scorecard_gate": "scholar_academic_evidence_valid",
        "readiness_gate": "policy_design_case.residual_spine_boundaries",
        "evidence_ref": evidence_ref,
        "cas_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
        "scholar_evidence_ref": _text(normalized.get(SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY)),
        "blockers": blockers,
        "issues": issues,
        "runtime_authority_envelope": {
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_blocker"
            if boundary_status in {"blocked", "failed"}
            else "runtime_derived",
            "cas_ref": evidence_ref,
            "runtime_event_ref": runtime_event_ref,
        },
    }


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _first_ref(report: Mapping[str, Any]) -> str | None:
    for key in (SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY, "cas_ref", "evidence_ref"):
        text = _text(report.get(key))
        if text:
            return text
    return None


def _derived_ref(report: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(report, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "SCHOLAR_ACADEMIC_EVIDENCE_BOUNDARY_SCHEMA_VERSION",
    "SCHOLAR_ACADEMIC_EVIDENCE_FILENAME",
    "SCHOLAR_ACADEMIC_EVIDENCE_PRODUCER_OWNER",
    "SCHOLAR_ACADEMIC_EVIDENCE_READER_OWNER",
    "SCHOLAR_ACADEMIC_EVIDENCE_RECORD_FAMILY",
    "SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY",
    "SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION",
    "build_scholar_academic_evidence_boundary_record",
    "build_scholar_academic_evidence_report",
    "build_scholar_academic_evidence_report_from_web_bundle",
    "normalize_scholar_academic_evidence_report",
    "scholar_academic_evidence_required",
]
