"""Shared source-truth conflict contract for non-runtime readers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

SOURCE_TRUTH_CONFLICT_SCHEMA = "policyos.runtime.quality.source_truth_conflict.v1"

_FAILURE_CODE_BY_FAMILY = {
    "approval_readiness_public_status": "hds_approval_readiness_authority_conflict",
    "final_claims": "hds_final_claims_authority_conflict",
    "runtime_refs": "hds_runtime_refs_authority_conflict",
}


def detect_source_truth_conflict(
    *,
    field_family: str,
    authoritative_source: str,
    authoritative_surface: str,
    authoritative_values: Mapping[str, Any],
    conflicting_source: str,
    conflicting_surface: str,
    conflicting_values: Mapping[str, Any],
    fields: Sequence[str],
    downstream_impact: str,
    runtime_event_refs: Sequence[str] = (),
    cas_refs: Sequence[str] = (),
    authoritative_ref: str | None = None,
    conflicting_ref: str | None = None,
    details: Mapping[str, Any] | None = None,
    recorded_at: datetime | None = None,
    **_: Any,
) -> dict[str, Any] | None:
    """Return a typed conflict when lower-authority values drift.

    This is the neutral read-side contract used by Scientist artifacts. Runtime
    may enrich the same shape through its lattice registry, but non-runtime
    callers only need deterministic comparison and the stable issue code shape.
    """

    normalized_fields = tuple(str(field).strip() for field in fields if str(field).strip())
    if not normalized_fields:
        raise ValueError("source_truth_conflict_fields_missing")

    lost_fields = [
        field
        for field in normalized_fields
        if _normalize_value(authoritative_values.get(field))
        != _normalize_value(conflicting_values.get(field))
    ]
    if not lost_fields:
        return None

    recorded = recorded_at or datetime.now(UTC)
    authoritative_ref = authoritative_ref or _first_ref(authoritative_values)
    conflicting_ref = conflicting_ref or _first_ref(conflicting_values)
    failure_code = _FAILURE_CODE_BY_FAMILY.get(field_family, "hds_source_truth_conflict")
    impact = str(downstream_impact or "").strip() or (
        "Authority-bearing projection rejected before approval or publication."
    )
    conflict_details = {
        "authoritative_source": authoritative_source,
        "conflicting_source": conflicting_source,
        "downstream_impact": impact,
        **dict(details or {}),
    }
    losing_record = {
        "record_schema": "policyos.runtime.quality.losing_authority_record.v1",
        "field_family": field_family,
        "authoritative_producer": authoritative_source,
        "authoritative_surface": authoritative_surface,
        "losing_surface": conflicting_surface,
        "lost_fields": list(lost_fields),
        "failure_code": failure_code,
        "authoritative_ref": authoritative_ref,
        "losing_ref": conflicting_ref,
        "owner": "team-runtime-quality",
        "next_diagnostic_command": (
            "uv run polisyos-tools architecture guardrails check"
        ),
        "recorded_at": recorded.isoformat(),
        "details": conflict_details,
    }
    return {
        "schema_version": SOURCE_TRUTH_CONFLICT_SCHEMA,
        "authoritative_source": authoritative_source,
        "authoritative_surface": authoritative_surface,
        "conflicting_source": conflicting_source,
        "conflicting_surface": conflicting_surface,
        "field_family": field_family,
        "lost_fields": list(lost_fields),
        "runtime_event_refs": list(_merge_refs(runtime_event_refs)),
        "cas_refs": list(_merge_refs(cas_refs, (authoritative_ref, conflicting_ref))),
        "authoritative_ref": authoritative_ref,
        "conflicting_ref": conflicting_ref,
        "losing_authority_record": losing_record,
        "failure_code": failure_code,
        "owner": "team-runtime-quality",
        "downstream_impact": impact,
        "next_diagnostic_command": losing_record["next_diagnostic_command"],
        "recorded_at": losing_record["recorded_at"],
        "details": conflict_details,
    }


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((str(k), _normalize_value(v)) for k, v in value.items()))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_normalize_value(item) for item in value)
    return value


def _first_ref(values: Mapping[str, Any]) -> str | None:
    for key in ("ref", "artifact_ref", "cas_ref", "runtime_event_ref", "scorecard_identity"):
        value = values.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _merge_refs(*groups: Sequence[str | None]) -> tuple[str, ...]:
    refs: list[str] = []
    for group in groups:
        for value in group:
            if isinstance(value, str) and value and value not in refs:
                refs.append(value)
    return tuple(refs)
