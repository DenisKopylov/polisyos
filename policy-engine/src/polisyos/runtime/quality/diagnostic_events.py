"""Diagnostic event envelope and registry contracts for runtime quality authority."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DIAGNOSTIC_EVENT_SCHEMA_NAME = "polisyos.runtime.quality.diagnostic_event"
DIAGNOSTIC_EVENT_SCHEMA_VERSION = "1.0"
DIAGNOSTIC_EVENT_ARTIFACT_KIND = "runtime_quality.diagnostic_event"
DEFAULT_MAX_EVENT_AGE = timedelta(hours=24)
DEFAULT_MAX_CLOCK_SKEW = timedelta(minutes=5)
SERIOUS_EXECUTION_PROFILES = frozenset({"governed", "production", "research"})
RECONCILIATION_FAILURE_CODES = (
    "authority_cas_missing",
    "authority_orphan_cas",
    "authority_payload_mismatch",
    "authority_ref_not_cas",
    "authority_event_collision",
    "authority_replay_drift_unexplained",
    "authority_tenant_conflict",
)

EXPECTED_DIAGNOSTIC_EVENT_TYPES = (
    "polisyos.runtime.diagnostic.producer_execution.v1",
    "polisyos.runtime.diagnostic.cas_write.v1",
    "polisyos.runtime.diagnostic.ref_publication.v1",
    "polisyos.runtime.diagnostic.phase_transition.v1",
    "polisyos.runtime.diagnostic.blocker.v1",
    "polisyos.runtime.diagnostic.effective_mode.v1",
    "polisyos.runtime.diagnostic.fallback_degradation.v1",
    "polisyos.runtime.diagnostic.schema_migration.v1",
    "polisyos.runtime.diagnostic.scorecard_gate_read.v1",
    "polisyos.runtime.diagnostic.readiness_closeout.v1",
    "polisyos.runtime.diagnostic.approval_decision.v1",
    "polisyos.runtime.diagnostic.dashboard_projection.v1",
    "polisyos.runtime.diagnostic.public_artifact_publication.v1",
    "polisyos.runtime.diagnostic.replay_result.v1",
    "polisyos.runtime.diagnostic.reconciliation_result.v1",
    "polisyos.runtime.diagnostic.governance_lifecycle_decision.v1",
    "polisyos.runtime.resilience_lane.evidence_emitted.v1",
    "polisyos.runtime.resilience_lane.slo_evidence_emitted.v1",
)

DuplicateStatus = Literal[
    "recorded",
    "idempotent_duplicate",
    "authority_event_collision",
    "retry_replay_candidate",
]


class DiagnosticEventContractError(ValueError):
    """Typed diagnostic event contract failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


class DiagnosticEvent(BaseModel):
    """ADR-0154 runtime diagnostic event envelope."""

    event_id: str
    event_source: str
    event_type: str
    event_time: datetime
    event_subject: str
    schema_name: Literal["polisyos.runtime.quality.diagnostic_event"]
    schema_version: Literal["1.0"]
    trace_id: str
    span_id: str
    parent_span_id: str | None
    run_id: str
    job_id: str
    tenant_id: str
    cell_id: str
    producer_component: str
    producer_version: str
    execution_profile: str
    phase: str
    state_before: str | None
    state_after: str | None
    payload_ref: str | None
    artifact_refs: tuple[str, ...]
    input_refs: tuple[str, ...]
    blocking_status: str | None
    redaction_policy_ref: str | None
    duplicate_of: str | None
    dedupe_key: str | None
    sampling_decision: str = "always_record"
    sampling_rate: float | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("event_time")
    @classmethod
    def _normalize_event_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class DiagnosticEventType(BaseModel):
    """One registry-scoped diagnostic event type."""

    name: str
    category: str
    description: str
    owner: str
    authority_role: str
    phase_required: bool = True
    producer_required: bool = True
    serious_no_sampling: bool = True
    allowed_event_sources: tuple[str, ...] = Field(default_factory=tuple)
    payload_ref_policy: str = "optional"

    model_config = ConfigDict(extra="forbid", frozen=True)


class DiagnosticEventTypeRegistry(BaseModel):
    """Loaded diagnostic event type registry."""

    registry_name: str
    registry_version: str
    event_types: dict[str, DiagnosticEventType]

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class DuplicateEventDecision:
    """Classification for an incoming event against already observed events."""

    status: DuplicateStatus
    event_id: str
    existing_event_id: str | None = None
    code: str | None = None
    must_reconcile: bool = False


def default_diagnostic_event_type_registry_path() -> Path:
    """Return the repository-local diagnostic event type registry path."""

    return (
        Path(__file__).resolve().parents[4]
        / "architecture/production_quality/diagnostic_event_types.toml"
    )


def load_diagnostic_event_type_registry(
    path: str | Path | None = None,
) -> DiagnosticEventTypeRegistry:
    """Load and validate the TOML event type registry."""

    registry_path = (
        Path(path) if path is not None else default_diagnostic_event_type_registry_path()
    )
    with registry_path.open("rb") as handle:
        payload = tomllib.load(handle)

    metadata = payload.get("registry")
    rows = payload.get("event_types")
    if not isinstance(metadata, Mapping) or not isinstance(rows, list):
        raise DiagnosticEventContractError(
            "diagnostic_event_registry_invalid",
            "Diagnostic event type registry must contain [registry] and [[event_types]].",
            details={"path": str(registry_path)},
        )

    event_types: dict[str, DiagnosticEventType] = {}
    for row in rows:
        event_type = DiagnosticEventType.model_validate(row)
        if event_type.name in event_types:
            raise DiagnosticEventContractError(
                "diagnostic_event_type_duplicate",
                f"Duplicate diagnostic event type {event_type.name!r}.",
                details={"event_type": event_type.name},
            )
        event_types[event_type.name] = event_type

    missing = sorted(set(EXPECTED_DIAGNOSTIC_EVENT_TYPES) - set(event_types))
    if missing:
        raise DiagnosticEventContractError(
            "diagnostic_event_type_registry_incomplete",
            "Diagnostic event type registry is missing Phase 1.2 minimum event types.",
            details={"missing_event_types": missing},
        )

    return DiagnosticEventTypeRegistry(
        registry_name=str(metadata.get("name") or ""),
        registry_version=str(metadata.get("version") or ""),
        event_types=event_types,
    )


def classify_duplicate_event(
    existing_events: Iterable[DiagnosticEvent | Mapping[str, Any]],
    incoming_event: DiagnosticEvent | Mapping[str, Any],
) -> DuplicateEventDecision:
    """Classify duplicate, collision, and retry/replay semantics for an event."""

    incoming = _as_event(incoming_event)
    normalized_existing = tuple(_as_event(event) for event in existing_events)
    incoming_identity = _payload_artifact_identity(incoming)

    for existing in normalized_existing:
        if existing.event_id != incoming.event_id:
            continue
        if _payload_artifact_identity(existing) == incoming_identity:
            return DuplicateEventDecision(
                status="idempotent_duplicate",
                event_id=incoming.event_id,
                existing_event_id=existing.event_id,
                code="idempotent_duplicate",
            )
        raise DiagnosticEventContractError(
            "authority_event_collision",
            "Same diagnostic event id points at different payload or artifact refs.",
            details={
                "event_id": incoming.event_id,
                "existing_payload_ref": existing.payload_ref,
                "incoming_payload_ref": incoming.payload_ref,
                "existing_artifact_refs": list(existing.artifact_refs),
                "incoming_artifact_refs": list(incoming.artifact_refs),
            },
        )

    for existing in normalized_existing:
        if (
            incoming.dedupe_key
            and existing.dedupe_key
            and existing.dedupe_key == incoming.dedupe_key
            and existing.event_id != incoming.event_id
        ):
            return DuplicateEventDecision(
                status="retry_replay_candidate",
                event_id=incoming.event_id,
                existing_event_id=existing.event_id,
                code="retry_replay_requires_reconciliation",
                must_reconcile=True,
            )

    return DuplicateEventDecision(status="recorded", event_id=incoming.event_id)


def validate_diagnostic_event(
    event: DiagnosticEvent | Mapping[str, Any],
    *,
    registry: DiagnosticEventTypeRegistry | None = None,
    expected_artifact_refs: Sequence[str] | None = None,
    now: datetime | None = None,
    max_event_age: timedelta | None = DEFAULT_MAX_EVENT_AGE,
    max_clock_skew: timedelta = DEFAULT_MAX_CLOCK_SKEW,
) -> DiagnosticEvent:
    """Validate ADR-0154 event invariants that depend on registry context."""

    diagnostic_event = _as_event(event)
    event_registry = registry or load_diagnostic_event_type_registry()
    event_type = event_registry.event_types.get(diagnostic_event.event_type)
    if event_type is None:
        raise DiagnosticEventContractError(
            "unknown_diagnostic_event_type",
            f"Diagnostic event type {diagnostic_event.event_type!r} is not registered.",
            details={"event_type": diagnostic_event.event_type},
        )

    if diagnostic_event.schema_name != DIAGNOSTIC_EVENT_SCHEMA_NAME:
        raise DiagnosticEventContractError(
            "diagnostic_event_schema_mismatch",
            "Diagnostic event uses an unknown schema name.",
            details={"schema_name": diagnostic_event.schema_name},
        )
    if diagnostic_event.schema_version != DIAGNOSTIC_EVENT_SCHEMA_VERSION:
        raise DiagnosticEventContractError(
            "diagnostic_event_schema_mismatch",
            "Diagnostic event uses an unknown schema version.",
            details={"schema_version": diagnostic_event.schema_version},
        )

    if event_type.phase_required and not _text(diagnostic_event.phase):
        raise DiagnosticEventContractError(
            "diagnostic_event_phase_missing",
            "Registered diagnostic events must carry the runtime phase.",
            details={"event_id": diagnostic_event.event_id},
        )
    if event_type.producer_required and (
        not _text(diagnostic_event.producer_component)
        or not _text(diagnostic_event.producer_version)
    ):
        raise DiagnosticEventContractError(
            "diagnostic_event_producer_missing",
            "Diagnostic event producer component and version are required.",
            details={"event_id": diagnostic_event.event_id},
        )

    if _bundle_source(diagnostic_event.event_source) and event_type.authority_role.startswith(
        "runtime"
    ):
        raise DiagnosticEventContractError(
            "bundle_event_cannot_mint_runtime_authority",
            "Bundle-created events cannot claim runtime authority event types.",
            details={
                "event_id": diagnostic_event.event_id,
                "event_source": diagnostic_event.event_source,
                "event_type": diagnostic_event.event_type,
            },
        )

    if event_type.allowed_event_sources and not _source_allowed(
        diagnostic_event.event_source,
        event_type.allowed_event_sources,
    ):
        raise DiagnosticEventContractError(
            "diagnostic_event_source_not_allowed",
            "Diagnostic event source is not allowed for this registered event type.",
            details={
                "event_source": diagnostic_event.event_source,
                "event_type": diagnostic_event.event_type,
                "allowed_event_sources": list(event_type.allowed_event_sources),
            },
        )

    if expected_artifact_refs is not None and _canonical_refs(
        diagnostic_event.artifact_refs
    ) != _canonical_refs(expected_artifact_refs):
        raise DiagnosticEventContractError(
            "diagnostic_event_ref_mismatch",
            "Diagnostic event artifact refs do not match expected runtime output refs.",
            details={
                "event_id": diagnostic_event.event_id,
                "expected_artifact_refs": sorted(expected_artifact_refs),
                "actual_artifact_refs": sorted(diagnostic_event.artifact_refs),
            },
        )

    reference_now = _aware_utc(now) if now is not None else None
    if reference_now is not None:
        if max_event_age is not None and diagnostic_event.event_time < (
            reference_now - max_event_age
        ):
            raise DiagnosticEventContractError(
                "stale_diagnostic_event",
                "Diagnostic event is older than the accepted runtime freshness window.",
                details={
                    "event_id": diagnostic_event.event_id,
                    "event_time": diagnostic_event.event_time.isoformat(),
                    "now": reference_now.isoformat(),
                },
            )
        if diagnostic_event.event_time > reference_now + max_clock_skew:
            raise DiagnosticEventContractError(
                "future_diagnostic_event",
                "Diagnostic event time is ahead of the accepted runtime clock skew.",
                details={
                    "event_id": diagnostic_event.event_id,
                    "event_time": diagnostic_event.event_time.isoformat(),
                    "now": reference_now.isoformat(),
                },
            )

    if (
        diagnostic_event.execution_profile.casefold() in SERIOUS_EXECUTION_PROFILES
        and event_type.serious_no_sampling
        and _sampled_away(diagnostic_event)
    ):
        raise DiagnosticEventContractError(
            "serious_diagnostic_event_sampled_away",
            "Serious-run authority diagnostic events must not be sampled away.",
            details={
                "event_id": diagnostic_event.event_id,
                "execution_profile": diagnostic_event.execution_profile,
                "sampling_decision": diagnostic_event.sampling_decision,
                "sampling_rate": diagnostic_event.sampling_rate,
            },
        )

    return diagnostic_event


def diagnostic_event_json_schema() -> dict[str, Any]:
    """Return the generated JSON schema for the v1 diagnostic event envelope."""

    schema = DiagnosticEvent.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://schemas.polisyos.dev/runtime_quality/diagnostic_event_v1.schema.json"
    schema["title"] = "PolicyOS Diagnostic Event Envelope v1"
    return schema


def _as_event(event: DiagnosticEvent | Mapping[str, Any]) -> DiagnosticEvent:
    if isinstance(event, DiagnosticEvent):
        return event
    return DiagnosticEvent.model_validate(event)


def _payload_artifact_identity(
    event: DiagnosticEvent,
) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
    return (
        event.payload_ref,
        _canonical_refs(event.artifact_refs),
        _canonical_refs(event.input_refs),
    )


def _canonical_refs(refs: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(str(ref).strip() for ref in refs))


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _sampled_away(event: DiagnosticEvent) -> bool:
    decision = event.sampling_decision.strip().casefold()
    if decision in {"drop", "dropped", "sampled", "sampled_away", "sampled-away"}:
        return True
    return event.sampling_rate is not None and event.sampling_rate < 1.0


def _source_allowed(event_source: str, allowed_sources: Sequence[str]) -> bool:
    normalized = event_source.strip().casefold()
    for allowed in allowed_sources:
        allowed_normalized = allowed.strip().casefold()
        if normalized == allowed_normalized or normalized.startswith(f"{allowed_normalized}."):
            return True
    return False


def _bundle_source(event_source: str) -> bool:
    normalized = event_source.strip().replace("_", "-").casefold()
    return (
        normalized == "polisyos.bundle"
        or ".bundle" in normalized
        or "bundle." in normalized
        or "canary-bundle" in normalized
    )


__all__ = [
    "DEFAULT_MAX_EVENT_AGE",
    "DIAGNOSTIC_EVENT_ARTIFACT_KIND",
    "DIAGNOSTIC_EVENT_SCHEMA_NAME",
    "DIAGNOSTIC_EVENT_SCHEMA_VERSION",
    "EXPECTED_DIAGNOSTIC_EVENT_TYPES",
    "RECONCILIATION_FAILURE_CODES",
    "SERIOUS_EXECUTION_PROFILES",
    "DiagnosticEvent",
    "DiagnosticEventContractError",
    "DiagnosticEventType",
    "DiagnosticEventTypeRegistry",
    "DuplicateEventDecision",
    "classify_duplicate_event",
    "default_diagnostic_event_type_registry_path",
    "diagnostic_event_json_schema",
    "load_diagnostic_event_type_registry",
    "validate_diagnostic_event",
]
