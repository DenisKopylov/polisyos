"""Runtime-owned boundary records for the Policy Design concept spine."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from polisyos.runtime.quality.assurance_case import (
    POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION,
    PolicyDesignCaseAuthorityError,
    build_policy_design_case_concept_spine,
    policy_design_concept_spine_json_schema,
    validate_policy_design_case_concept_spine,
)

CONCEPT_SPINE_BOUNDARY_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.concept_spine_boundary.v1"
)
CONCEPT_SPINE_RECORD_FAMILY = "concept_and_jurisdiction_spine.v1"
CONCEPT_SPINE_PRODUCER_OWNER = "team-policy-semantics"
CONCEPT_SPINE_READER_OWNER = "team-runtime-quality"


def build_policy_design_concept_spine_boundary_record(
    spine: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a producer-side residual-boundary record for concept resolution.

    The record deliberately fails when a producer tries to publish unresolved
    concepts as `status=pass`, even if the downstream validator can infer the
    failure. That keeps the first failing artifact at the concept-spine boundary
    instead of letting it surface as a late PDC scorecard surprise.
    """

    if not isinstance(spine, Mapping):
        return _boundary_record(
            source={},
            status="failed",
            issues=[
                _issue(
                    "policy_design_concept_spine_missing",
                    "Policy Design Case concept spine is missing before PDC compilation.",
                )
            ],
        )

    raw_status = _status(spine.get("status"))
    try:
        normalized = validate_policy_design_case_concept_spine(spine)
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
                    "policy_design_concept_spine_blocker_missing",
                    "Concept spine blockers cannot be hidden behind producer status=pass.",
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
    evidence_ref = _first_ref(source, ("cas_ref", "concept_spine_ref")) or _derived_ref(source)
    runtime_event_ref = (
        _text(source.get("runtime_event_ref"))
        or f"event://policy-design-case/concept-spine-boundary/{evidence_ref}"
    )
    authority_status = "runtime_blocker" if status in {"blocked", "failed"} else "runtime_derived"
    return {
        "schema_version": CONCEPT_SPINE_BOUNDARY_SCHEMA_VERSION,
        "source_schema_version": source.get("schema_version")
        or POLICY_DESIGN_CONCEPT_SPINE_SCHEMA_VERSION,
        "record_id": "policy-design-concept-spine-boundary",
        "record_family": CONCEPT_SPINE_RECORD_FAMILY,
        "status": status,
        "producer_owner": CONCEPT_SPINE_PRODUCER_OWNER,
        "reader_owner": CONCEPT_SPINE_READER_OWNER,
        "scorecard_gate": "policy_design_concept_spine_boundary",
        "readiness_gate": "policy_design_case.residual_spine_boundaries",
        "evidence_ref": evidence_ref,
        "cas_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
        "concept_spine_ref": _text(source.get("concept_spine_ref")),
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
        "phase": "policy_design_concept_spine",
        "message": message,
        "next_action": (
            "Emit concept-spine resolution evidence or a typed blocker before "
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
    "CONCEPT_SPINE_BOUNDARY_SCHEMA_VERSION",
    "CONCEPT_SPINE_PRODUCER_OWNER",
    "CONCEPT_SPINE_READER_OWNER",
    "CONCEPT_SPINE_RECORD_FAMILY",
    "build_policy_design_case_concept_spine",
    "build_policy_design_concept_spine_boundary_record",
    "policy_design_concept_spine_json_schema",
    "validate_policy_design_case_concept_spine",
]
