"""Typed first-class conflict records for Policy Design Case evidence portfolios."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

CONFLICT_RECORD_SCHEMA_VERSION = "policyos.evidence.portfolio.conflict_record.v1"
CONFLICT_PORTFOLIO_INDEX_SCHEMA_VERSION = (
    "policyos.evidence.portfolio.conflict_index.v1"
)
CONFLICT_RECORD_CONTRACT_ID = "policy_design_case.conflict_record.v1"
CONFLICT_PORTFOLIO_INDEX_CONTRACT_ID = "policy_design_case.conflict_portfolio_index.v1"


class PortfolioConflictType(str, Enum):
    """Conflict families materialized into the evidence portfolio."""

    EMPIRICAL = "empirical"
    METHODOLOGICAL = "methodological"
    LEGAL = "legal"
    SCOPE = "scope"
    NORMATIVE = "normative"
    PARTICIPATION = "participation"
    IMPLEMENTATION = "implementation"
    AUTHORITY_PROVENANCE = "authority_provenance"


class ConflictResolutionRoute(str, Enum):
    """Resolution route a reviewer or producer must follow for a conflict."""

    NEW_EVIDENCE = "new_evidence"
    METHOD_ARBITRATION = "method_arbitration"
    LEGAL_HIERARCHY = "legal_hierarchy"
    SCOPE_NARROWING = "scope_narrowing"
    GOVERNANCE_DECISION = "governance_decision"
    PERSISTENT_CONTESTED_STATE = "persistent_contested_state"


class ConflictSeverity(str, Enum):
    """Local severity axis for first-class portfolio conflict records."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConflictAuthorityEnvelope(BaseModel):
    """Authority boundary for conflict materialization records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authoritative_for: list[str] = Field(default_factory=lambda: ["conflict_materialization"])
    may_not_use_for: list[str] = Field(
        default_factory=lambda: [
            "claim_authority",
            "support_strength",
            "legal_authority",
            "method_authority",
        ]
    )

    @model_validator(mode="after")
    def _validate_boundary(self) -> ConflictAuthorityEnvelope:
        if "conflict_materialization" not in self.authoritative_for:
            raise ValueError("conflict records are authoritative only for conflict materialization")
        missing = {"claim_authority", "support_strength"} - set(self.may_not_use_for)
        if missing:
            raise ValueError(
                "conflict records must not be usable for "
                + ", ".join(sorted(missing))
            )
        return self


class PolicyConflictRecord(BaseModel):
    """One first-class conflict fact bound to claim registry and portfolio axes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.evidence.portfolio.conflict_record.v1"] = (
        CONFLICT_RECORD_SCHEMA_VERSION
    )
    contract_id: Literal["policy_design_case.conflict_record.v1"] = (
        CONFLICT_RECORD_CONTRACT_ID
    )
    conflict_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    claim_ids: list[str] = Field(min_length=1)
    conflict_type: PortfolioConflictType
    resolution_route: ConflictResolutionRoute
    severity: ConflictSeverity
    conflicting_source_refs: list[str] = Field(min_length=1)
    description: str = Field(min_length=1)
    need_id: str | None = None
    dimension: str | None = None
    detected_by: Literal["producer_handshake", "conflict_detector", "manual_review"] = (
        "conflict_detector"
    )
    detection_phase: Literal[
        "pre_emission_handshake",
        "post_hoc_backstop",
        "manual_review",
    ] = "post_hoc_backstop"
    producer_handshake_refs: list[str] = Field(default_factory=list)
    source_conflict_signature: str | None = None
    resolution_status: Literal[
        "unresolved",
        "routed",
        "resolved",
        "contested_persistent",
    ] = "routed"
    support_count_effect: Literal["not_supporting_evidence"] = "not_supporting_evidence"
    claim_registry_effect: Literal[
        "add_conflict_ref_and_counterevidence",
        "add_conflict_ref",
        "block_claim",
    ] = "add_conflict_ref_and_counterevidence"
    closeout_effect: Literal[
        "blocks_until_resolved",
        "requires_review",
        "publish_as_contested",
        "advisory_only",
    ] = "requires_review"
    authority_envelope: ConflictAuthorityEnvelope = Field(
        default_factory=ConflictAuthorityEnvelope
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_semantics(self) -> PolicyConflictRecord:
        if not _clean_texts(self.claim_ids):
            raise ValueError("conflict records must bind at least one claim")
        if not _clean_texts(self.conflicting_source_refs):
            raise ValueError("conflict records must bind conflicting source refs")
        if (
            self.resolution_route
            is ConflictResolutionRoute.PERSISTENT_CONTESTED_STATE
            and self.closeout_effect == "advisory_only"
        ):
            raise ValueError("persistent contested conflicts cannot be advisory only")
        return self


class ConflictRecordError(ValueError):
    """Fail-closed conflict-record validation error."""

    def __init__(self, code: str, message: str, field: str | None = None) -> None:
        self.code = code
        self.message = message
        self.field = field
        super().__init__(f"{code}: {message}")


def build_conflict_record(
    *,
    conflict_id: str | None = None,
    run_id: str,
    claim_ids: Iterable[str],
    conflict_type: PortfolioConflictType | str,
    severity: ConflictSeverity | str,
    conflicting_source_refs: Iterable[str],
    description: str,
    resolution_route: ConflictResolutionRoute | str | None = None,
    need_id: str | None = None,
    dimension: str | None = None,
    detected_by: Literal["producer_handshake", "conflict_detector", "manual_review"] = (
        "conflict_detector"
    ),
    detection_phase: Literal[
        "pre_emission_handshake",
        "post_hoc_backstop",
        "manual_review",
    ] = "post_hoc_backstop",
    producer_handshake_refs: Iterable[str] = (),
    source_conflict_signature: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate a first-class conflict record."""

    conflict_kind = (
        conflict_type
        if isinstance(conflict_type, PortfolioConflictType)
        else PortfolioConflictType(str(conflict_type))
    )
    route = (
        resolution_route
        if isinstance(resolution_route, ConflictResolutionRoute)
        else ConflictResolutionRoute(str(resolution_route))
        if resolution_route is not None
        else _default_resolution_route(conflict_kind)
    )
    conflict_severity = (
        severity if isinstance(severity, ConflictSeverity) else ConflictSeverity(str(severity))
    )
    clean_claim_ids = _clean_texts(claim_ids)
    clean_source_refs = _clean_texts(conflicting_source_refs)
    payload = {
        "schema_version": CONFLICT_RECORD_SCHEMA_VERSION,
        "contract_id": CONFLICT_RECORD_CONTRACT_ID,
        "conflict_id": _text(conflict_id)
        or _stable_conflict_id(
            run_id=run_id,
            claim_ids=clean_claim_ids,
            conflict_type=conflict_kind.value,
            need_id=need_id,
            dimension=dimension,
            conflicting_source_refs=clean_source_refs,
            description=description,
        ),
        "run_id": _text(run_id),
        "claim_ids": clean_claim_ids,
        "conflict_type": conflict_kind.value,
        "resolution_route": route.value,
        "severity": conflict_severity.value,
        "conflicting_source_refs": clean_source_refs,
        "description": _text(description),
        "need_id": _optional_text(need_id),
        "dimension": _optional_text(dimension),
        "detected_by": detected_by,
        "detection_phase": detection_phase,
        "producer_handshake_refs": _clean_texts(producer_handshake_refs),
        "source_conflict_signature": _optional_text(source_conflict_signature),
        "resolution_status": (
            "contested_persistent"
            if route is ConflictResolutionRoute.PERSISTENT_CONTESTED_STATE
            else "routed"
        ),
        "support_count_effect": "not_supporting_evidence",
        "claim_registry_effect": "add_conflict_ref_and_counterevidence",
        "closeout_effect": _default_closeout_effect(route, conflict_severity),
        "authority_envelope": ConflictAuthorityEnvelope().model_dump(mode="json"),
        "metadata": dict(metadata or {}),
    }
    return validate_conflict_record(payload)


def validate_conflict_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one conflict record."""

    if not isinstance(record, Mapping):
        raise ConflictRecordError(
            "policy_design_conflict_record_invalid",
            "Conflict record must be a mapping.",
        )
    if not _clean_texts(record.get("claim_ids")):
        raise ConflictRecordError(
            "policy_design_conflict_claim_binding_missing",
            "Conflict record must bind at least one claim.",
            "claim_ids",
        )
    if not _clean_texts(record.get("conflicting_source_refs")):
        raise ConflictRecordError(
            "policy_design_conflict_source_refs_missing",
            "Conflict record must bind conflicting source refs.",
            "conflicting_source_refs",
        )
    try:
        validated = PolicyConflictRecord.model_validate(dict(record))
    except ValidationError as exc:
        raise ConflictRecordError(
            "policy_design_conflict_record_invalid",
            str(exc),
        ) from exc
    return validated.model_dump(mode="json", exclude_none=True)


def build_conflict_portfolio_index(
    conflict_records: Iterable[Mapping[str, Any]],
    *,
    index_id: str,
    run_id: str,
    portfolio_designs: Iterable[Mapping[str, Any]] = (),
    claim_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the portfolio/audit surface for first-class conflict records."""

    records = [validate_conflict_record(record) for record in conflict_records]
    refs_by_claim = conflict_refs_by_claim(records)
    portfolio_ids_by_claim = _portfolio_ids_by_claim(portfolio_designs)
    if claim_registry is not None:
        portfolio_ids_by_claim.update(_portfolio_ids_by_claim_from_registry(claim_registry))

    refs_by_portfolio: dict[str, list[str]] = {}
    for claim_id, conflict_refs in refs_by_claim.items():
        for portfolio_id in portfolio_ids_by_claim.get(claim_id, ()):
            refs_by_portfolio.setdefault(portfolio_id, [])
            refs_by_portfolio[portfolio_id] = _dedupe(
                [*refs_by_portfolio[portfolio_id], *conflict_refs]
            )

    payload = {
        "schema_version": CONFLICT_PORTFOLIO_INDEX_SCHEMA_VERSION,
        "contract_id": CONFLICT_PORTFOLIO_INDEX_CONTRACT_ID,
        "index_id": _required_text(
            index_id,
            "policy_design_conflict_index_id_missing",
            "index_id",
        ),
        "run_id": _required_text(
            run_id,
            "policy_design_conflict_index_run_id_missing",
            "run_id",
        ),
        "conflict_records": records,
        "conflict_refs_by_claim": refs_by_claim,
        "conflict_refs_by_portfolio": {
            key: refs_by_portfolio[key] for key in sorted(refs_by_portfolio)
        },
        "summary": {
            "conflict_count": len(records),
            "claim_count": len(refs_by_claim),
            "portfolio_count": len(refs_by_portfolio),
            "closeout_blocking_count": sum(
                1 for record in records if record.get("closeout_effect") == "blocks_until_resolved"
            ),
        },
        "authority_envelope": {
            "authoritative_for": ["portfolio_conflict_index"],
            "may_not_use_for": ["claim_authority", "support_strength"],
        },
    }
    return payload


def conflict_refs_by_claim(
    conflict_records: Iterable[Mapping[str, Any]],
) -> dict[str, list[str]]:
    """Project conflict ids by claim id."""

    refs: dict[str, list[str]] = {}
    for raw in conflict_records:
        record = validate_conflict_record(raw)
        conflict_id = str(record["conflict_id"])
        for claim_id in _clean_texts(record.get("claim_ids")):
            refs.setdefault(claim_id, [])
            refs[claim_id] = _dedupe([*refs[claim_id], conflict_id])
    return {key: refs[key] for key in sorted(refs)}


def _default_resolution_route(conflict_type: PortfolioConflictType) -> ConflictResolutionRoute:
    return {
        PortfolioConflictType.EMPIRICAL: ConflictResolutionRoute.NEW_EVIDENCE,
        PortfolioConflictType.METHODOLOGICAL: ConflictResolutionRoute.METHOD_ARBITRATION,
        PortfolioConflictType.LEGAL: ConflictResolutionRoute.LEGAL_HIERARCHY,
        PortfolioConflictType.SCOPE: ConflictResolutionRoute.SCOPE_NARROWING,
        PortfolioConflictType.NORMATIVE: ConflictResolutionRoute.GOVERNANCE_DECISION,
        PortfolioConflictType.PARTICIPATION: ConflictResolutionRoute.GOVERNANCE_DECISION,
        PortfolioConflictType.IMPLEMENTATION: ConflictResolutionRoute.NEW_EVIDENCE,
        PortfolioConflictType.AUTHORITY_PROVENANCE: (
            ConflictResolutionRoute.PERSISTENT_CONTESTED_STATE
        ),
    }[conflict_type]


def _default_closeout_effect(
    route: ConflictResolutionRoute,
    severity: ConflictSeverity,
) -> str:
    if severity in {ConflictSeverity.HIGH, ConflictSeverity.CRITICAL}:
        return "blocks_until_resolved"
    if route is ConflictResolutionRoute.PERSISTENT_CONTESTED_STATE:
        return "publish_as_contested"
    if severity is ConflictSeverity.LOW:
        return "advisory_only"
    return "requires_review"


def _portfolio_ids_by_claim(
    portfolio_designs: Iterable[Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {}
    for raw in portfolio_designs:
        if not isinstance(raw, Mapping):
            continue
        portfolio_id = _text(
            raw.get("portfolio_id")
            or raw.get("portfolio_design_id")
            or raw.get("design_id")
            or raw.get("record_id")
            or raw.get("id")
        )
        if not portfolio_id:
            continue
        for claim_id in _clean_texts(raw.get("claim_ids") or raw.get("claim_id")):
            result.setdefault(claim_id, [])
            result[claim_id] = _dedupe([*result[claim_id], portfolio_id])
    return {claim_id: tuple(ids) for claim_id, ids in result.items()}


def _portfolio_ids_by_claim_from_registry(
    claim_registry: Mapping[str, Any],
) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {}
    rows = claim_registry.get("claims")
    if not isinstance(rows, Sequence) or isinstance(rows, str | bytes | bytearray):
        return {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        claim_id = _text(row.get("claim_id"))
        if not claim_id:
            continue
        result.setdefault(claim_id, [])
        result[claim_id] = _dedupe(
            [*result[claim_id], *_clean_texts(row.get("portfolio_refs"))]
        )
    return {claim_id: tuple(ids) for claim_id, ids in result.items()}


def _stable_conflict_id(
    *,
    run_id: str,
    claim_ids: Sequence[str],
    conflict_type: str,
    need_id: str | None,
    dimension: str | None,
    conflicting_source_refs: Sequence[str],
    description: str,
) -> str:
    seed = json.dumps(
        {
            "run_id": run_id,
            "claim_ids": list(claim_ids),
            "conflict_type": conflict_type,
            "need_id": need_id,
            "dimension": dimension,
            "conflicting_source_refs": list(conflicting_source_refs),
            "description": description,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    scope = _slug(need_id or claim_ids[0] if claim_ids else run_id)
    return f"conflict.{conflict_type}.{scope}.{digest}"


def _required_text(value: object, code: str, field: str) -> str:
    text = _text(value)
    if not text:
        raise ConflictRecordError(code, f"{field} is required.", field)
    return text


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _clean_texts(value: object) -> list[str]:
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if isinstance(value, Mapping):
        refs: list[str] = []
        for key in ("ref", "id", "claim_id", "portfolio_id", "source_ref", "source_id"):
            refs.extend(_clean_texts(value.get(key)))
        return _dedupe(refs)
    if isinstance(value, Iterable):
        refs = []
        for item in value:
            refs.extend(_clean_texts(item))
        return _dedupe(refs)
    return []


def _dedupe(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _slug(value: object) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._:-]+", "-", _text(value)).strip("-")
    return slug or "conflict"


def _text(value: object) -> str:
    return str(value or "").strip()


__all__ = [
    "CONFLICT_PORTFOLIO_INDEX_SCHEMA_VERSION",
    "CONFLICT_RECORD_SCHEMA_VERSION",
    "ConflictRecordError",
    "ConflictResolutionRoute",
    "PolicyConflictRecord",
    "PortfolioConflictType",
    "build_conflict_portfolio_index",
    "build_conflict_record",
    "conflict_refs_by_claim",
    "validate_conflict_record",
]
