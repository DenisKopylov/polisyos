"""Runtime-owned boundary records for Policy Design jurisdiction competence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from polisyos.runtime.quality.assurance_case import (
    POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION,
    PolicyDesignCaseAuthorityError,
    build_policy_design_jurisdiction_spine,
    policy_design_jurisdiction_spine_json_schema,
    validate_policy_design_jurisdiction_spine,
)

JURISDICTION_SPINE_BOUNDARY_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.jurisdiction_spine_boundary.v1"
)
JURISDICTION_SPINE_RECORD_FAMILY = "concept_and_jurisdiction_spine.v1"
JURISDICTION_SPINE_PRODUCER_OWNER = "team-lex"
JURISDICTION_SPINE_READER_OWNER = "team-runtime-quality"


def build_policy_design_jurisdiction_spine_boundary_record(
    spine: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a first-failing producer record for jurisdiction competence."""

    if not isinstance(spine, Mapping):
        return _boundary_record(
            source={},
            status="failed",
            issues=[
                _issue(
                    "policy_design_jurisdiction_spine_missing",
                    (
                        "Policy Design Case jurisdiction spine is missing before "
                        "PDC compilation."
                    ),
                )
            ],
        )

    raw_status = _status(spine.get("status"))
    try:
        normalized = validate_policy_design_jurisdiction_spine(spine)
    except PolicyDesignCaseAuthorityError as exc:
        return _boundary_record(
            source=spine,
            status="failed",
            issues=[_issue(exc.code, str(exc))],
        )

    blockers = _mapping_list(normalized.get("blockers"))
    normalized_status = _status(normalized.get("status"))
    if raw_status == "pass" and normalized_status == "blocked":
        return _boundary_record(
            source=normalized,
            status="failed",
            blockers=blockers,
            issues=[
                _issue(
                    "policy_design_jurisdiction_spine_blocker_missing",
                    (
                        "Jurisdiction competence blockers cannot be hidden behind "
                        "producer status=pass."
                    ),
                )
            ],
        )
    return _boundary_record(
        source=normalized,
        status="blocked" if normalized_status == "blocked" or blockers else "pass",
        blockers=blockers,
    )


def _boundary_record(
    *,
    source: Mapping[str, Any],
    status: str,
    blockers: list[dict[str, Any]] | None = None,
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    blockers = blockers or []
    issues = issues or []
    evidence_ref = _first_ref(source, ("jurisdiction_spine_ref", "cas_ref")) or _derived_ref(
        source
    )
    runtime_event_ref = (
        _text(source.get("runtime_event_ref"))
        or f"event://policy-design-case/jurisdiction-spine-boundary/{evidence_ref}"
    )
    authority_status = "runtime_blocker" if status in {"blocked", "failed"} else "runtime_derived"
    return {
        "schema_version": JURISDICTION_SPINE_BOUNDARY_SCHEMA_VERSION,
        "source_schema_version": source.get("schema_version")
        or POLICY_DESIGN_JURISDICTION_SPINE_SCHEMA_VERSION,
        "record_id": "policy-design-jurisdiction-spine-boundary",
        "record_family": JURISDICTION_SPINE_RECORD_FAMILY,
        "status": status,
        "producer_owner": JURISDICTION_SPINE_PRODUCER_OWNER,
        "reader_owner": JURISDICTION_SPINE_READER_OWNER,
        "scorecard_gate": "policy_design_jurisdiction_spine_boundary",
        "readiness_gate": "policy_design_case.residual_spine_boundaries",
        "evidence_ref": evidence_ref,
        "cas_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
        "jurisdiction_spine_ref": _text(source.get("jurisdiction_spine_ref")),
        "source_status": _text(source.get("status")),
        "blockers": blockers,
        "issues": issues,
        "runtime_authority_envelope": {
            "authority_role": "producer_authority",
            "provenance_kind": authority_status,
            "cas_ref": evidence_ref,
            "runtime_event_ref": runtime_event_ref,
        },
    }


def _issue(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "phase": "policy_design_jurisdiction_spine",
        "message": message,
        "next_action": (
            "Emit jurisdiction competence evidence or a typed blocker before "
            "Policy Design Case compilation."
        ),
    }


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _first_ref(source: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        text = _text(source.get(key))
        if text:
            return text
    authority = source.get("runtime_authority_envelope")
    if isinstance(authority, Mapping):
        return _text(authority.get("cas_ref") or authority.get("evidence_ref"))
    return None


def _derived_ref(source: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(source, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _status(value: object) -> str:
    return str(value or "").strip().casefold()


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "JURISDICTION_SPINE_BOUNDARY_SCHEMA_VERSION",
    "JURISDICTION_SPINE_PRODUCER_OWNER",
    "JURISDICTION_SPINE_READER_OWNER",
    "JURISDICTION_SPINE_RECORD_FAMILY",
    "build_policy_design_jurisdiction_spine",
    "build_policy_design_jurisdiction_spine_boundary_record",
    "policy_design_jurisdiction_spine_json_schema",
    "validate_policy_design_jurisdiction_spine",
]
