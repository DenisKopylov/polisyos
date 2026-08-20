"""Runtime quality records for balanced-memory influence boundaries."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Iterable

MEMORY_INFLUENCE_SCHEMA_VERSION = "policyos.runtime.quality.memory_influence_record.v1"
MEMORY_INFLUENCE_ADR_REF = "ADR-0172"
MEMORY_INFLUENCE_RECORD_KIND = "runtime.quality.memory_influence"
MEMORY_FORBIDDEN_CURRENT_USES: tuple[str, ...] = (
    "current_claim_evidence",
    "current_claim_closure",
    "claim_support",
    "claim_refutation",
    "legal_authority",
    "data_authority",
    "method_authority",
    "closeout_verdict",
    "producer_evidence_replacement",
    "claim_registry_ref_replacement",
)
MEMORY_FUTURE_AUTHORITY_USES: tuple[str, ...] = (
    "future_search",
    "future_review",
    "future_routing",
    "future_acquisition_suggestion",
    "memory_lifecycle",
)
CORE_FORBIDDEN_CURRENT_USES: tuple[str, ...] = (
    "current_claim_evidence",
    "current_claim_closure",
    "claim_support",
    "claim_refutation",
)
CLAIM_EVIDENCE_SLOT_KEYS: tuple[str, ...] = (
    "scenario_requirement_refs",
    "data_refs",
    "selected_norm_refs",
    "rejected_norm_refs",
    "method_output_refs",
    "portfolio_refs",
    "argument_refs",
    "warrant_refs",
    "rebuttal_refs",
    "counter_evidence_refs",
    "limitation_refs",
    "accepted_deficit_refs",
    "blocker_refs",
)
# Compatibility projection of the legacy claim grammar. Provenance admission must
# traverse values and never decide from membership in this key vocabulary.
MEMORY_INFLUENCE_REF_PREFIXES: tuple[str, ...] = (
    "memory-influence:",
    "runtime.memory_influence:",
    "runtime.quality.memory_influence:",
    "balanced-memory:",
    "balanced_memory:",
    "memory://balanced/",
)
FORBIDDEN_MEMORY_KEY_TOKENS: tuple[str, ...] = (
    "hidden_benchmark",
    "hidden_eval",
    "hidden_holdout",
    "private_eval",
    "hidden_suite",
    "sentinel_answer",
    "canary",
)
_LLM_SOURCE_KINDS = frozenset({"llm_candidate", "llm_critic", "llm_drafter"})
_MEMORY_INFLUENCE_POSITION_FLAG = "memory_influence_bearing_position"


class ProvenancePayloadError(ValueError):
    """Raised when provenance traversal reaches a non-canonical payload value."""

    def __init__(self, *, path: tuple[str, ...], value: object) -> None:
        self.path = path
        self.value_type = type(value).__name__
        location = _payload_path(path) if path else "$"
        super().__init__(
            "unsupported provenance payload value at "
            f"{location}: {self.value_type}"
        )


class MemoryInfluenceRecord(BaseModel):
    """Runtime handoff that makes memory influence visible but non-evidentiary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.runtime.quality.memory_influence_record.v1"] = Field(
        default=MEMORY_INFLUENCE_SCHEMA_VERSION,
        json_schema_extra={_MEMORY_INFLUENCE_POSITION_FLAG: True},
    )
    record_kind: Literal["runtime.quality.memory_influence"] = Field(
        default=MEMORY_INFLUENCE_RECORD_KIND,
        json_schema_extra={_MEMORY_INFLUENCE_POSITION_FLAG: True},
    )
    adr_ref: Literal["ADR-0172"] = MEMORY_INFLUENCE_ADR_REF
    record_id: str = Field(
        default_factory=lambda: f"memory-influence-{uuid4().hex}",
        json_schema_extra={_MEMORY_INFLUENCE_POSITION_FLAG: True},
    )
    run_id: str = Field(min_length=1)
    memory_id: str = Field(
        min_length=1,
        json_schema_extra={_MEMORY_INFLUENCE_POSITION_FLAG: True},
    )
    memory_kind: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    source_status: str = Field(min_length=1)
    influence_modes: tuple[str, ...]
    authoritative_for: tuple[str, ...] = MEMORY_FUTURE_AUTHORITY_USES
    may_not_use_for: tuple[str, ...] = MEMORY_FORBIDDEN_CURRENT_USES
    scope: dict[str, Any] = Field(default_factory=dict)
    applicability_reasons: tuple[str, ...] = Field(default=())
    contamination_status: Literal["pass"] = "pass"
    contamination_check_ref: str = Field(min_length=1)
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    related_claim_ids: tuple[str, ...] = Field(default=())
    evidence_slot_refs: tuple[str, ...] = Field(default=())
    closes_claim_ids: tuple[str, ...] = Field(default=())
    refutes_claim_ids: tuple[str, ...] = Field(default=())
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_no_current_evidence(self) -> MemoryInfluenceRecord:
        missing = set(CORE_FORBIDDEN_CURRENT_USES) - set(self.may_not_use_for)
        if missing:
            raise ValueError(
                "memory influence boundary missing forbidden current uses: "
                + ",".join(sorted(missing))
            )
        if self.evidence_slot_refs or self.closes_claim_ids or self.refutes_claim_ids:
            raise ValueError("memory influence cannot carry current evidence or claim closure refs")
        if self.source_kind in _LLM_SOURCE_KINDS and self.influence_modes:
            raise ValueError("unverified LLM memory cannot influence current run")
        _assert_markers_in_owner_declared_positions(self)
        return self

    def to_authority_boundary(self) -> dict[str, Any]:
        """Return the compact authority boundary payload for audit surfaces."""

        return {
            "authoritative_for": list(self.authoritative_for),
            "may_not_use_for": list(self.may_not_use_for),
            "source_kind": self.source_kind,
            "source_status": self.source_status,
            "adr_ref": self.adr_ref,
        }


def build_memory_influence_record(
    memory: object,
    *,
    run_id: str,
    context: object,
    contamination_check_ref: str,
    hidden_ref_ids: set[str] | None = None,
    hidden_suite_ids: set[str] | None = None,
    canary_tokens: set[str] | None = None,
    related_claim_ids: Iterable[str] = (),
    metadata: dict[str, Any] | None = None,
) -> MemoryInfluenceRecord:
    """Build a runtime influence record after contamination and applicability checks."""

    payload = _payload_from(memory)
    context_payload = _payload_from(context)
    _assert_memory_payload_clean(
        payload,
        hidden_ref_ids=hidden_ref_ids or set(),
        hidden_suite_ids=hidden_suite_ids or set(),
        canary_tokens=canary_tokens or set(),
    )
    applicability = _evaluate_payload_applicability(payload, context_payload)
    if not applicability["applies"]:
        raise ValueError(
            "balanced memory cannot influence run: "
            + ",".join(applicability["reasons"])
        )
    boundary = _mapping(payload.get("authority_boundary"))
    return MemoryInfluenceRecord(
        run_id=run_id,
        memory_id=_text(payload.get("memory_id") or payload.get("lesson_id")),
        memory_kind=_enum_value(payload.get("kind") or payload.get("memory_kind")),
        source_run_id=_text(payload.get("source_run_id")),
        source_kind=_enum_value(boundary.get("source_kind")),
        source_status=_enum_value(boundary.get("source_status")),
        influence_modes=tuple(str(mode) for mode in applicability["influence_modes"]),
        authoritative_for=tuple(
            str(value) for value in boundary.get("authoritative_for", MEMORY_FUTURE_AUTHORITY_USES)
        ),
        may_not_use_for=tuple(
            str(value) for value in boundary.get("may_not_use_for", MEMORY_FORBIDDEN_CURRENT_USES)
        ),
        scope=dict(applicability["scope"]),
        applicability_reasons=tuple(applicability["reasons"]),
        contamination_check_ref=contamination_check_ref,
        related_claim_ids=tuple(related_claim_ids),
        metadata=metadata or {},
    )


def assert_memory_influence_not_claim_evidence(
    record: MemoryInfluenceRecord,
) -> MemoryInfluenceRecord:
    """Fail closed if a memory influence record is shaped as current evidence."""

    if record.evidence_slot_refs or record.closes_claim_ids or record.refutes_claim_ids:
        raise ValueError("memory influence cannot carry current evidence or claim closure refs")
    missing = set(CORE_FORBIDDEN_CURRENT_USES) - set(record.may_not_use_for)
    if missing:
        raise ValueError(
            "memory influence boundary missing forbidden current uses: "
            + ",".join(sorted(missing))
        )
    _assert_markers_in_owner_declared_positions(record)
    return record


def _payload_from(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))  # type: ignore[call-arg]
    payload: dict[str, Any] = {}
    for key in (
        "memory_id",
        "lesson_id",
        "kind",
        "memory_kind",
        "source_run_id",
        "authority_boundary",
        "scope",
        "influence_modes",
        "revoked_at",
        "revocation_reason",
        "run_id",
        "domain",
        "tenant_hash",
        "workflow_id",
        "method_family",
        "task_family",
        "now",
    ):
        if hasattr(value, key):
            payload[key] = getattr(value, key)
    return payload


def _evaluate_payload_applicability(
    payload: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    scope = _mapping(payload.get("scope"))
    boundary = _mapping(payload.get("authority_boundary"))
    reasons = [f"{_enum_value(payload.get('kind') or payload.get('memory_kind'))}_memory"]
    blocked: list[str] = []
    now = _parse_datetime(context.get("now")) or datetime.now(UTC)
    expires_at = _parse_datetime(scope.get("expires_at"))

    if payload.get("revoked_at") or payload.get("revocation_reason"):
        blocked.append("revoked")
    if expires_at is not None and now > expires_at:
        blocked.append("expired")
    else:
        reasons.append("not_expired")
    if _text(scope.get("task_family") or "policy") != _text(context.get("task_family") or "policy"):
        blocked.append("task_family_mismatch")
    else:
        reasons.append("task_family_match")

    _check_scope(scope=scope, payload=payload, context=context, reasons=reasons, blocked=blocked)
    source_kind = _enum_value(boundary.get("source_kind"))
    source_status = _enum_value(boundary.get("source_status"))
    if source_kind in _LLM_SOURCE_KINDS:
        blocked.append(
            "llm_rejected_speculation"
            if source_status == "rejected_speculation"
            else "llm_candidate_unverified"
        )
    applies = not blocked
    return {
        "applies": applies,
        "reasons": _dedupe([*reasons, *blocked]),
        "scope": {str(key): str(value) for key, value in scope.items() if value is not None},
        "influence_modes": list(payload.get("influence_modes") or ()) if applies else [],
    }


def _check_scope(
    *,
    scope: Mapping[str, Any],
    payload: Mapping[str, Any],
    context: Mapping[str, Any],
    reasons: list[str],
    blocked: list[str],
) -> None:
    visibility = _text(scope.get("visibility") or "domain")
    if visibility == "local_run":
        if _text(payload.get("source_run_id")) != _text(context.get("run_id")):
            blocked.append("run_scope_mismatch")
        else:
            reasons.append("run_scope_match")
        return
    if visibility == "tenant":
        if not _text(scope.get("tenant_hash")) or _text(scope.get("tenant_hash")) != _text(
            context.get("tenant_hash")
        ):
            blocked.append("tenant_scope_mismatch")
        else:
            reasons.append("tenant_scope_match")
        return
    if visibility == "domain":
        if _text(scope.get("domain") or "general") != _text(context.get("domain") or "general"):
            blocked.append("domain_scope_mismatch")
        else:
            reasons.append("domain_scope_match")
    else:
        reasons.append("global_public_scope")
    for key in ("workflow_id", "method_family"):
        expected = _text(scope.get(key))
        if not expected:
            continue
        if expected != _text(context.get(key)):
            blocked.append(f"{key}_mismatch")
        else:
            reasons.append(f"{key}_match")


def _assert_memory_payload_clean(
    payload: Mapping[str, Any],
    *,
    hidden_ref_ids: set[str],
    hidden_suite_ids: set[str],
    canary_tokens: set[str],
) -> None:
    findings: list[str] = []
    rendered = json.dumps(payload, sort_keys=True, default=str)
    for hidden_ref in sorted(hidden_ref_ids):
        if hidden_ref and hidden_ref in rendered:
            findings.append(f"artifact_id:{hidden_ref}")
    for hidden_suite in sorted(hidden_suite_ids):
        if hidden_suite and hidden_suite in rendered:
            findings.append(f"suite_id:{hidden_suite}")
    for canary in sorted(canary_tokens):
        if canary and canary in rendered:
            findings.append(f"canary:{canary}")
    findings.extend(_forbidden_key_findings(payload))
    if findings:
        raise ValueError("reusable memory contamination detected: " + ", ".join(findings))


def _forbidden_key_findings(value: object, *, path: str = "payload") -> list[str]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.casefold()
            for token in FORBIDDEN_MEMORY_KEY_TOKENS:
                if token in lowered:
                    findings.append(f"metadata_key:{path}.{key_text}")
            findings.extend(_forbidden_key_findings(item, path=f"{path}.{key_text}"))
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            findings.extend(_forbidden_key_findings(item, path=f"{path}[{index}]"))
    return findings


def _mapping(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))  # type: ignore[call-arg]
    return {}


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return _text(raw)


def _text(value: object) -> str:
    return str(value or "").strip()


def _parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def is_memory_influence_ref(ref: object) -> bool:
    """Return whether a ref names balanced-memory influence rather than evidence."""

    text = str(ref or "").strip().casefold()
    if not text:
        return False
    return any(text.startswith(prefix) for prefix in MEMORY_INFLUENCE_REF_PREFIXES) or (
        "memory_influence" in text or "memory-influence" in text
    )


def memory_influence_claim_evidence_issues(
    row: Mapping[str, Any],
    *,
    claim_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return claim-registry issues for memory provenance anywhere in a claim."""

    try:
        provenance_values = payload_provenance_values(row)
    except ProvenancePayloadError as exc:
        return [
            {
                "code": "memory_influence_payload_provenance_unknown",
                "severity": "fail",
                "layer": "runtime_quality",
                "phase": "balanced_memory_firewall",
                "claim_id": claim_id,
                "evidence_slot": exc.path[0] if exc.path else "$",
                "payload_path": _payload_path(exc.path) if exc.path else "$",
                "unsupported_value_type": exc.value_type,
                "message": (
                    "Memory influence admission cannot classify a non-canonical "
                    "payload value and therefore fails closed."
                ),
                "next_action": (
                    "Resolve the value through the destination contract's canonical "
                    "payload grammar before claim-evidence admission."
                ),
                "authority_boundary": {
                    "adr_ref": MEMORY_INFLUENCE_ADR_REF,
                    "authoritative_for": list(MEMORY_FUTURE_AUTHORITY_USES),
                    "may_not_use_for": list(MEMORY_FORBIDDEN_CURRENT_USES),
                },
            }
        ]

    issues: list[dict[str, Any]] = []
    for path, ref in provenance_values:
        if not is_memory_influence_ref(ref):
            continue
        issues.append(
            {
                "code": "memory_influence_ref_not_admissible_as_claim_evidence",
                "severity": "fail",
                "layer": "runtime_quality",
                "phase": "balanced_memory_firewall",
                "claim_id": claim_id,
                "evidence_slot": path[0],
                "payload_path": _payload_path(path),
                "memory_influence_ref": ref,
                "message": (
                    "Balanced memory influence records may guide future search, "
                    "review, routing, or acquisition, but they cannot satisfy, "
                    "close, support, or refute current-run claim evidence."
                ),
                "next_action": (
                    "Move the memory ref to a memory influence surface and bind "
                    "the claim to current-run producer evidence, typed blockers, "
                    "limitations, or accepted deficits."
                ),
                "authority_boundary": {
                    "adr_ref": MEMORY_INFLUENCE_ADR_REF,
                    "authoritative_for": list(MEMORY_FUTURE_AUTHORITY_USES),
                    "may_not_use_for": list(MEMORY_FORBIDDEN_CURRENT_USES),
                },
            }
        )
    return issues


def payload_provenance_values(
    value: object,
) -> list[tuple[tuple[str, ...], str]]:
    """Return every non-empty string value with its structural payload path.

    Destination contract owners apply their own provenance classifier to this
    complete value set. Callers cannot supply an allowlist or select paths.
    """

    return _payload_provenance_values(value, path=())


def _payload_provenance_values(
    value: object,
    *,
    path: tuple[str, ...],
) -> list[tuple[tuple[str, ...], str]]:
    if isinstance(value, str):
        text = value.strip()
        return [(path, text)] if text and path else []
    if value is None or isinstance(value, bool | int | float | datetime):
        return []
    if isinstance(value, Mapping):
        values: list[tuple[tuple[str, ...], str]] = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProvenancePayloadError(path=(*path, "<mapping-key>"), value=key)
            values.extend(
                _payload_provenance_values(item, path=(*path, key))
            )
        return values
    if isinstance(value, list | tuple):
        values = []
        for index, item in enumerate(value):
            values.extend(
                _payload_provenance_values(item, path=(*path, f"[{index}]"))
            )
        return values
    raise ProvenancePayloadError(path=path, value=value)


def _payload_path(path: tuple[str, ...]) -> str:
    output = path[0]
    for part in path[1:]:
        output += part if part.startswith("[") else f".{part}"
    return output


def _assert_markers_in_owner_declared_positions(record: MemoryInfluenceRecord) -> None:
    declared_paths = {
        (field_name,)
        for field_name, field_info in MemoryInfluenceRecord.model_fields.items()
        if isinstance(field_info.json_schema_extra, Mapping)
        and field_info.json_schema_extra.get(_MEMORY_INFLUENCE_POSITION_FLAG) is True
    }
    undeclared_paths = [
        path
        for path, ref in payload_provenance_values(record.model_dump(mode="python"))
        if is_memory_influence_ref(ref) and path not in declared_paths
    ]
    if undeclared_paths:
        raise ValueError(
            "memory influence marker outside owner-declared position: "
            + ",".join(_payload_path(path) for path in undeclared_paths)
        )


__all__ = [
    "CLAIM_EVIDENCE_SLOT_KEYS",
    "CORE_FORBIDDEN_CURRENT_USES",
    "FORBIDDEN_MEMORY_KEY_TOKENS",
    "MEMORY_FORBIDDEN_CURRENT_USES",
    "MEMORY_FUTURE_AUTHORITY_USES",
    "MEMORY_INFLUENCE_ADR_REF",
    "MEMORY_INFLUENCE_RECORD_KIND",
    "MEMORY_INFLUENCE_REF_PREFIXES",
    "MEMORY_INFLUENCE_SCHEMA_VERSION",
    "MemoryInfluenceRecord",
    "ProvenancePayloadError",
    "assert_memory_influence_not_claim_evidence",
    "build_memory_influence_record",
    "is_memory_influence_ref",
    "memory_influence_claim_evidence_issues",
    "payload_provenance_values",
]
