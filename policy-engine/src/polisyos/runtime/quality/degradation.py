"""Fallback and degradation ledger contracts for honest diagnostics closeout."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

DEGRADATION_LEDGER_REQUIRED_FIELDS = (
    "component",
    "phase",
    "trigger",
    "allowed_profiles",
    "produced_artifacts",
    "affected_claims",
    "affected_gates",
    "severity",
    "override_policy",
    "downstream_impact",
    "provenance_refs",
    "typed_blocker",
)
SERIOUS_PROFILES = frozenset({"research", "governed", "production", "serious_runtime"})
SIGNED_NON_PRODUCTION_LOWERING_POLICIES = frozenset(
    {
        "signed_non_production_lowering_exception",
        "signed_non_production_lowering",
    }
)
NON_OVERRIDABLE_POLICIES = frozenset({"not_overridable", "non_overridable"})
NON_BLOCKING_STATUSES = frozenset({"allowed", "non_blocking", "recorded"})
BLOCKING_STATUSES = frozenset({"blocked", "blocking", "fail", "non_overridable"})
DEGRADATION_KIND_FAILURE_CODES = {
    "fallback_default": "degradation_fallback_default_not_allowed",
    "optional_report_generation": "degradation_optional_report_generation_not_allowed",
    "generated_substitute": "degradation_generated_substitute_not_allowed",
    "parser_healing": "degradation_parser_healing_not_allowed",
    "provider_quarantine": "degradation_provider_quarantine_not_allowed",
    "jax_missing_materialization_refs": (
        "degradation_jax_missing_materialization_refs_not_allowed"
    ),
    "local_canary_fixture_payload": "degradation_local_canary_fixture_payload_not_allowed",
    "deterministic_overlay": "degradation_deterministic_overlay_not_allowed",
    "dashboard_projection": "degradation_dashboard_projection_not_allowed",
    "legacy_unknown": "degradation_legacy_record_quarantined",
}
DEFAULT_MODE_AND_FALLBACK_POLICY_REGISTRY = (
    Path(__file__).resolve().parents[4]
    / "architecture/production_quality/mode_and_fallback_policy.toml"
)


class DegradationLedgerContractError(ValueError):
    """Raised when degradation evidence cannot satisfy closeout policy."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        field: str | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.field = field


class ModeAndFallbackPolicyRegistryError(ValueError):
    """Raised when mode/fallback policy registry rows are incomplete."""

    def __init__(self, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.field = field


@dataclass(frozen=True)
class ModeAndFallbackPolicyRegistry:
    """Loaded mode and fallback policy rows."""

    mode_policies: tuple[Mapping[str, Any], ...]
    fallback_policies: tuple[Mapping[str, Any], ...]
    path: Path


def load_mode_and_fallback_policy_registry(
    path: str | Path = DEFAULT_MODE_AND_FALLBACK_POLICY_REGISTRY,
    *,
    repo_root: str | Path | None = None,
) -> ModeAndFallbackPolicyRegistry:
    registry_path = Path(path)
    with registry_path.open("rb") as handle:
        payload = tomllib.load(handle)
    mode_rows = _policy_rows(payload, "mode_policies")
    fallback_rows = _policy_rows(payload, "fallback_policies")
    root = Path(repo_root) if repo_root is not None else registry_path.parents[2]
    for table_name, rows in (
        ("mode_policies", mode_rows),
        ("fallback_policies", fallback_rows),
    ):
        for row in rows:
            _validate_policy_row(table_name, row, repo_root=root)
    return ModeAndFallbackPolicyRegistry(
        mode_policies=mode_rows,
        fallback_policies=fallback_rows,
        path=registry_path,
    )


def _policy_rows(payload: Mapping[str, Any], table_name: str) -> tuple[Mapping[str, Any], ...]:
    rows = payload.get(table_name)
    if not isinstance(rows, list) or not rows:
        raise ModeAndFallbackPolicyRegistryError(
            "mode_fallback_policy_rows_missing",
            f"Policy registry must define [[{table_name}]].",
            field=table_name,
        )
    return tuple(dict(row) for row in rows if isinstance(row, Mapping))


def _validate_policy_row(
    table_name: str,
    row: Mapping[str, Any],
    *,
    repo_root: Path,
) -> None:
    for field in ("policy_id", "profiles", "failure_code", "next_diagnostic_command"):
        value = row.get(field)
        if field == "profiles":
            valid = isinstance(value, list) and bool(value)
        else:
            valid = isinstance(value, str) and bool(value.strip())
        if not valid:
            raise ModeAndFallbackPolicyRegistryError(
                "mode_fallback_policy_row_incomplete",
                f"{table_name} row is missing {field}.",
                field=field,
            )
    command = str(row["next_diagnostic_command"])
    path = _pytest_command_path(command)
    if path is not None and not (repo_root / path).exists():
        raise ModeAndFallbackPolicyRegistryError(
            "mode_fallback_policy_command_missing",
            f"Policy diagnostic command path does not exist: {path}.",
            field="next_diagnostic_command",
        )


def _pytest_command_path(command: str) -> Path | None:
    parts = command.split()
    if "pytest" not in parts:
        return None
    for part in parts[parts.index("pytest") + 1 :]:
        if part.startswith("-"):
            continue
        return Path(part.split("::", 1)[0])
    return None


class TypedBlocker(BaseModel):
    """Machine-actionable blocker attached to a degradation record."""

    model_config = ConfigDict(frozen=True, extra="allow")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    next_action: str = Field(min_length=1)
    blocking: bool = True
    may_satisfy_serious_gate: bool = False


class DegradationLedgerRecord(BaseModel):
    """Runtime-owned fallback/degradation ledger record."""

    model_config = ConfigDict(frozen=True, extra="allow")

    degradation_id: str | None = None
    runtime_event_ref: str | None = None
    cas_ref: str | None = None
    component: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    primary_path: str | None = None
    fallback_path: str | None = None
    allowed_profiles: tuple[str, ...]
    actual_profile: str | None = None
    produced_artifacts: tuple[str, ...]
    affected_claims: tuple[str, ...]
    affected_gates: tuple[str, ...]
    severity: str = Field(min_length=1)
    degradation_kind: str = Field(default="fallback_default", min_length=1)
    override_policy: str = Field(min_length=1)
    downstream_impact: str = Field(min_length=1)
    provenance_refs: tuple[str, ...]
    typed_blocker: TypedBlocker | None
    blocking_status: str = "blocking"
    owner: str | None = None
    generated_at: datetime | None = None
    validation_status: str | None = None
    signed_exception_ref: str | None = None
    next_diagnostic_command: str | None = None


@dataclass(frozen=True)
class DegradationPolicyDecision:
    """Result of applying the fallback/degradation closeout policy."""

    allowed: bool
    blocking: bool
    code: str | None
    reason: str
    record: DegradationLedgerRecord | None = None
    typed_blocker: dict[str, Any] | None = None


def deserialize_degradation_record(payload: Mapping[str, Any]) -> DegradationLedgerRecord:
    """Validate a raw degradation ledger payload."""

    for field in DEGRADATION_LEDGER_REQUIRED_FIELDS:
        if field not in payload:
            raise DegradationLedgerContractError(
                "degradation_ledger_required_field_missing",
                f"Degradation ledger record is missing required field: {field}.",
                field=field,
            )
    return DegradationLedgerRecord.model_validate(dict(payload))


def serialize_degradation_record(record: DegradationLedgerRecord) -> dict[str, Any]:
    """Return a JSON-safe degradation ledger payload."""

    return record.model_dump(mode="json")


def build_degradation_record(
    *,
    component: str,
    phase: str,
    trigger: str,
    primary_path: str | None,
    fallback_path: str | None,
    allowed_profiles: Iterable[str],
    actual_profile: str,
    produced_artifacts: Iterable[str],
    affected_claims: Iterable[str],
    affected_gates: Iterable[str],
    severity: str,
    degradation_kind: str,
    override_policy: str,
    downstream_impact: str,
    provenance_refs: Iterable[str],
    owner: str,
    degradation_id: str | None = None,
    runtime_event_ref: str | None = None,
    cas_ref: str | None = None,
    typed_blocker: Mapping[str, Any] | None = None,
    signed_exception_ref: str | None = None,
    next_diagnostic_command: str | None = None,
) -> DegradationLedgerRecord:
    """Build a normalized degradation record from runtime fallback context."""

    allowed = tuple(str(profile).strip() for profile in allowed_profiles if str(profile).strip())
    artifacts = tuple(str(ref).strip() for ref in produced_artifacts if str(ref).strip())
    claims = tuple(str(ref).strip() for ref in affected_claims if str(ref).strip())
    gates = tuple(str(gate).strip() for gate in affected_gates if str(gate).strip())
    provenance = tuple(str(ref).strip() for ref in provenance_refs if str(ref).strip())
    event_ref = runtime_event_ref or _first_prefixed(provenance, "event://")
    artifact_ref = cas_ref or _first_prefixed((*artifacts, *provenance), "cas://")
    record_id = degradation_id or f"degradation_{_slug(component)}_{_slug(phase)}_{_slug(trigger)}"
    profile_allowed = actual_profile in allowed
    signed_allowed = _has_signed_non_production_lowering_exception(
        override_policy=override_policy,
        signed_exception_ref=signed_exception_ref,
    )
    blocking_status = (
        "non_blocking" if profile_allowed or signed_allowed else "blocking"
    )
    blocker_model = TypedBlocker.model_validate(typed_blocker) if typed_blocker else None
    return DegradationLedgerRecord(
        degradation_id=record_id,
        runtime_event_ref=event_ref,
        cas_ref=artifact_ref,
        component=component,
        phase=phase,
        trigger=trigger,
        primary_path=primary_path,
        fallback_path=fallback_path,
        allowed_profiles=allowed,
        actual_profile=actual_profile,
        produced_artifacts=artifacts,
        affected_claims=claims,
        affected_gates=gates,
        severity=severity,
        degradation_kind=degradation_kind,
        override_policy=override_policy,
        downstream_impact=downstream_impact,
        provenance_refs=provenance,
        typed_blocker=blocker_model,
        blocking_status=blocking_status,
        owner=owner,
        generated_at=datetime.now(UTC).replace(microsecond=0),
        validation_status="pass" if blocking_status == "non_blocking" else "blocked",
        signed_exception_ref=signed_exception_ref,
        next_diagnostic_command=next_diagnostic_command,
    )


def evaluate_degradation_policy(
    record: DegradationLedgerRecord,
    *,
    active_profile: str | None = None,
    authority_bearing: bool = True,
) -> DegradationPolicyDecision:
    """Fail closed for serious fallback-produced authority-bearing evidence."""

    profile = _normalize_profile(active_profile or record.actual_profile)
    if not authority_bearing:
        return DegradationPolicyDecision(
            allowed=True,
            blocking=False,
            code=None,
            reason="Degradation record is diagnostic-only and not authority-bearing.",
            record=record,
        )

    if _is_legacy_or_quarantined(record):
        return _blocking_decision(record, profile, "degradation_legacy_record_quarantined")

    if profile not in SERIOUS_PROFILES:
        return DegradationPolicyDecision(
            allowed=True,
            blocking=False,
            code=None,
            reason=f"Profile {profile or 'unknown'} is not a serious closeout profile.",
            record=record,
        )

    if _has_signed_non_production_lowering_exception(
        override_policy=record.override_policy,
        signed_exception_ref=record.signed_exception_ref,
    ):
        return DegradationPolicyDecision(
            allowed=True,
            blocking=False,
            code=None,
            reason="Signed non-production-lowering exception permits this degradation.",
            record=record,
        )

    allowed_profiles = {
        _normalize_profile(profile_name) for profile_name in record.allowed_profiles
    }
    if profile in allowed_profiles and _blocking_status(record) in NON_BLOCKING_STATUSES:
        return DegradationPolicyDecision(
            allowed=True,
            blocking=False,
            code=None,
            reason=f"Profile {profile} is explicitly allowed by degradation policy.",
            record=record,
        )

    return _blocking_decision(record, profile, None)


def assert_serious_fallback_allowed(
    record: DegradationLedgerRecord,
    *,
    active_profile: str | None = None,
    authority_bearing: bool = True,
) -> None:
    """Raise when a fallback/degradation record cannot satisfy serious closeout."""

    decision = evaluate_degradation_policy(
        record,
        active_profile=active_profile,
        authority_bearing=authority_bearing,
    )
    if decision.blocking:
        raise DegradationLedgerContractError(
            decision.code or "degradation_policy_blocked",
            decision.reason,
        )


def degradation_gate_from_payloads(
    *,
    canary_kind: str,
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
    quality_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build a scorecard gate for fallback/degradation closeout policy."""

    profile = _normalize_profile(canary_kind)
    payloads = [job_payload or {}, run_payload or {}, quality_evidence or {}]
    records = list(_iter_degradation_records(payloads))
    for record in records:
        decision = evaluate_degradation_policy(record, active_profile=profile)
        if decision.blocking:
            return _degradation_gate(
                code=decision.code or "degradation_policy_blocked",
                phase=record.phase,
                message=decision.reason,
                evidence_ref=record.cas_ref or record.runtime_event_ref,
                next_action=record.next_diagnostic_command
                or _typed_next_action(decision.typed_blocker)
                or "Inspect fallback/degradation ledger before serious closeout.",
            )

    if (
        profile in SERIOUS_PROFILES
        and _fallback_affects_authority(payloads)
        and not records
        and not _fallback_has_degradation_ref(payloads)
    ):
        return _degradation_gate(
            code="silent_fallback_degradation_ledger_missing",
            phase="fallback_degradation",
            message=(
                "Fallback-produced authority-bearing evidence was observed without "
                "a runtime degradation ledger record."
            ),
            evidence_ref=None,
            next_action=(
                "Emit src/polisyos/runtime/quality/degradation.py ledger evidence "
                "before scorecard or readiness closeout consumes the fallback output."
            ),
        )
    return None


def _blocking_decision(
    record: DegradationLedgerRecord,
    profile: str | None,
    code_override: str | None,
) -> DegradationPolicyDecision:
    typed_blocker = _typed_blocker(record, code_override=code_override)
    code = str(typed_blocker["code"])
    reason = str(
        typed_blocker.get("message")
        or f"Degradation {record.degradation_kind} is not allowed for {profile}."
    )
    return DegradationPolicyDecision(
        allowed=False,
        blocking=True,
        code=code,
        reason=reason,
        record=record,
        typed_blocker=typed_blocker,
    )


def _typed_blocker(
    record: DegradationLedgerRecord,
    *,
    code_override: str | None,
) -> dict[str, Any]:
    if record.typed_blocker is not None and not code_override:
        return record.typed_blocker.model_dump(mode="json")
    code = code_override or _fixture_failure_code(record) or _kind_failure_code(record)
    return {
        "code": code,
        "message": (
            f"Degradation kind {record.degradation_kind} is not allowed for "
            f"serious closeout profile {record.actual_profile or 'unknown'}."
        ),
        "severity": record.severity,
        "next_action": record.next_diagnostic_command
        or "Declare an allowed-profile policy or signed non-production-lowering exception.",
        "blocking": True,
        "may_satisfy_serious_gate": False,
    }


def _fixture_failure_code(record: DegradationLedgerRecord) -> str | None:
    for extra_key in ("rejection", "quarantine"):
        value = getattr(record, extra_key, None)
        if isinstance(value, Mapping):
            failure_code = value.get("failure_code")
            if isinstance(failure_code, str) and failure_code.strip():
                return failure_code.strip()
    return None


def _kind_failure_code(record: DegradationLedgerRecord) -> str:
    normalized = _normalize_token(record.degradation_kind)
    return DEGRADATION_KIND_FAILURE_CODES.get(
        normalized,
        f"degradation_{normalized or 'unknown'}_not_allowed",
    )


def _is_legacy_or_quarantined(record: DegradationLedgerRecord) -> bool:
    status = str(record.validation_status or "").casefold()
    return (
        _normalize_token(record.degradation_kind) == "legacy_unknown"
        or status == "quarantined"
        or isinstance(getattr(record, "quarantine", None), Mapping)
    )


def _iter_degradation_records(
    payloads: Iterable[Mapping[str, Any]],
) -> Iterable[DegradationLedgerRecord]:
    for payload in payloads:
        for candidate in _nested_find_degradation_candidates(payload):
            if isinstance(candidate, Mapping):
                yield deserialize_degradation_record(candidate)


def _looks_like_degradation_record(candidate: object) -> bool:
    if not isinstance(candidate, Mapping) or not candidate:
        return False
    return any(field in candidate for field in DEGRADATION_LEDGER_REQUIRED_FIELDS)


def _nested_find_degradation_candidates(payload: object) -> Iterable[object]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key)
            if key_text in {
                "degradation_record",
                "degradation_ledger_record",
            }:
                yield value
                continue
            if key_text == "degradation_ledger":
                if _looks_like_degradation_record(value):
                    yield value
                else:
                    yield from _nested_find_degradation_candidates(value)
                continue
            if key_text in {"degradation_ledgers", "degradation_records"}:
                if isinstance(value, list):
                    yield from value
                elif isinstance(value, Mapping):
                    yield from value.values()
                continue
            yield from _nested_find_degradation_candidates(value)
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            yield from _nested_find_degradation_candidates(value)


def _fallback_affects_authority(payloads: Iterable[Mapping[str, Any]]) -> bool:
    for payload in payloads:
        if _truthy_nested(payload, "fallback_used"):
            return True
        if _truthy_nested(payload, "mock_fallback_used"):
            return True
        if _truthy_nested(payload, "generated_substitute_used"):
            return True
        if _truthy_nested(payload, "provider_quarantine"):
            return True
        if _truthy_nested(payload, "dashboard_projection_used"):
            return True
        if _truthy_nested(payload, "deterministic_overlay_used"):
            return True
        if _truthy_nested(payload, "local_canary_fixture_payload"):
            return True
        optional_refs = _nested_get(payload, "optional_runtime_quality_refs")
        if isinstance(optional_refs, Mapping) and optional_refs:
            return True
        overlay_mode = _nested_get(payload, "evidence_overlay_mode")
        if overlay_mode and str(overlay_mode).casefold() not in {"disabled", "none"}:
            return True
        quarantine_status = _nested_get(payload, "quarantine_status")
        if quarantine_status and str(quarantine_status).casefold() not in {"none", "pass"}:
            return True
        healing_count = _nested_get(payload, "schema_healing_count")
        if _positive_int(healing_count):
            return True
        if _contains_text(payload, "fallback_state_snapshot_without_jax"):
            return True
        if _contains_jax_missing(payload):
            return True
    return False


def _fallback_has_degradation_ref(payloads: Iterable[Mapping[str, Any]]) -> bool:
    return any(
        _fallback_affects_authority([payload]) and _has_degradation_ref([payload])
        for payload in payloads
    )


def _has_degradation_ref(payloads: Iterable[Mapping[str, Any]]) -> bool:
    for payload in payloads:
        ref = _nested_get(payload, "degradation_ledger_ref")
        if isinstance(ref, str) and ref.strip():
            return True
        refs = _nested_get(payload, "degradation_ledger_refs")
        if isinstance(refs, list) and any(isinstance(item, str) and item.strip() for item in refs):
            return True
    return False


def _degradation_gate(
    *,
    code: str,
    phase: str,
    message: str,
    evidence_ref: str | None,
    next_action: str | None,
) -> dict[str, Any]:
    return {
        "name": "fallback_degradation_ledger_allowed",
        "stage": "ops",
        "code": code,
        "status": "fail",
        "layer": "runtime_degradation",
        "phase": phase,
        "message": message,
        "evidence_ref": evidence_ref,
        "next_action": next_action,
        "blocking": True,
    }


def _typed_next_action(blocker: Mapping[str, Any] | None) -> str | None:
    if not isinstance(blocker, Mapping):
        return None
    value = blocker.get("next_action")
    return str(value).strip() if value else None


def _has_signed_non_production_lowering_exception(
    *,
    override_policy: str,
    signed_exception_ref: str | None,
) -> bool:
    if _normalize_token(override_policy) not in SIGNED_NON_PRODUCTION_LOWERING_POLICIES:
        return False
    if not signed_exception_ref:
        return False
    return signed_exception_ref.startswith(("exception://signed/", "cas://", "sha256:"))


def _blocking_status(record: DegradationLedgerRecord) -> str:
    return _normalize_token(record.blocking_status)


def _normalize_profile(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _normalize_token(value)
    if normalized in {"serious", "serious_closeout", "production_live"}:
        return "production"
    return normalized


def _normalize_token(value: object) -> str:
    return str(value or "").strip().replace("-", "_").casefold()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").casefold()
    return slug or "unknown"


def _first_prefixed(values: Iterable[str], prefix: str) -> str | None:
    for value in values:
        if value.startswith(prefix):
            return value
    return None


def _nested_get(payload: object, key: str) -> object | None:
    if isinstance(payload, Mapping):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _nested_get(value, key)
            if found is not None:
                return found
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            found = _nested_get(value, key)
            if found is not None:
                return found
    return None


def _truthy_nested(payload: object, key: str) -> bool:
    value = _nested_get(payload, key)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "used"}
    return bool(value)


def _positive_int(value: object) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _contains_text(payload: object, needle: str) -> bool:
    if isinstance(payload, str):
        return needle in payload
    if isinstance(payload, Mapping):
        return any(_contains_text(value, needle) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return any(_contains_text(value, needle) for value in payload)
    return False


def _contains_jax_missing(payload: object) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).casefold() == "jax" and str(value).casefold() == "missing":
                return True
            if _contains_jax_missing(value):
                return True
    if isinstance(payload, (list, tuple)):
        return any(_contains_jax_missing(value) for value in payload)
    return False


__all__ = [
    "DEFAULT_MODE_AND_FALLBACK_POLICY_REGISTRY",
    "DEGRADATION_LEDGER_REQUIRED_FIELDS",
    "DegradationLedgerContractError",
    "DegradationLedgerRecord",
    "DegradationPolicyDecision",
    "ModeAndFallbackPolicyRegistry",
    "ModeAndFallbackPolicyRegistryError",
    "TypedBlocker",
    "assert_serious_fallback_allowed",
    "build_degradation_record",
    "degradation_gate_from_payloads",
    "deserialize_degradation_record",
    "evaluate_degradation_policy",
    "load_mode_and_fallback_policy_registry",
    "serialize_degradation_record",
]
