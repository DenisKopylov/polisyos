"""Append-only, fsync-backed evidence journal for bounded acquisition execution.

The journal is a quarantine evidence surface.  Persisting a request or response
does not admit data to L1 and does not create substrate authority.  Callers must
verify the returned content-bound event reference before any classifier or
admission owner consumes the evidence.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from polisyos.fabric.connectors.profiles.models import SourceProfile

_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_SAFE_DRY_RUN_OUTCOMES = frozenset(
    {
        "fetch_result_validated",
        "replay_fixture_missing_after_interception",
    }
)
_HEARTBEAT_PHASES = frozenset(
    {
        "attempt_started",
        "waiting",
        "response_headers",
        "body_progress",
    }
)


class EvidenceJournalError(RuntimeError):
    """Fail-closed journal or live-authorization error with a typed code."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(f"{code}: {self.detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class JournalEventRef(_StrictModel):
    """Durable address and content identity for one canonical JSONL event."""

    journal_path: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    event_kind: str = Field(min_length=1)
    event_sha256: str = Field(pattern=_SHA256_PATTERN)
    byte_offset: int = Field(ge=0)
    byte_length: int = Field(gt=0)


class LiveHttpBudget(_StrictModel):
    """One-call HTTP limits recomputed from a Fabric source profile and caps."""

    profile_timeout_seconds: float = Field(gt=0.0)
    profile_rate_limit_rps: float | None = Field(default=None, gt=0.0)
    profile_requests_per_hour: int | None = Field(default=None, gt=0)
    timeout_cap_seconds: float = Field(gt=0.0)
    heartbeat_cap_seconds: float = Field(gt=0.0)
    timeout_seconds: float = Field(gt=0.0)
    minimum_interval_seconds: float = Field(ge=0.0)
    heartbeat_interval_seconds: float = Field(gt=0.0)
    max_response_bytes: int = Field(gt=0)
    max_decompressed_bytes: int = Field(gt=0)
    call_budget: Literal[1] = 1
    variable_budget: Literal[1] = 1

    @model_validator(mode="after")
    def _limits_are_owner_derived(self) -> Self:
        expected_timeout = min(self.profile_timeout_seconds, self.timeout_cap_seconds)
        if abs(self.timeout_seconds - expected_timeout) > 1e-9:
            raise ValueError("timeout must be derived from the source profile and cap")
        intervals: list[float] = []
        if self.profile_rate_limit_rps is not None:
            intervals.append(1.0 / self.profile_rate_limit_rps)
        if self.profile_requests_per_hour is not None:
            intervals.append(3600.0 / self.profile_requests_per_hour)
        expected_interval = max(intervals, default=0.0)
        if abs(self.minimum_interval_seconds - expected_interval) > 1e-9:
            raise ValueError("minimum interval must be derived from the source profile")
        expected_heartbeat = min(
            self.heartbeat_cap_seconds,
            self.timeout_seconds / 5.0,
        )
        if abs(self.heartbeat_interval_seconds - expected_heartbeat) > 1e-9:
            raise ValueError("heartbeat interval must be derived from the timeout budget")
        if self.max_decompressed_bytes > self.max_response_bytes:
            raise ValueError("decompressed response cap cannot exceed the raw response cap")
        return self


class HarnessAuthorizationEvidence(_StrictModel):
    """N13a E7 harness projection that recomputes whether one carrier is safe."""

    connector_id: str = Field(min_length=1)
    family_receipt_sha256: str = Field(pattern=_SHA256_PATTERN)
    carrier_receipt_sha256: str = Field(pattern=_SHA256_PATTERN)
    protocol_conformant: bool
    harness_checks_passed: tuple[str, ...] = Field(min_length=1)
    harness_check_failures: tuple[str, ...]
    family_safe_dry_run_passed: bool
    simulator_intercepted: bool
    carrier_transport_intercepted: bool
    network_escape_attempt_count: int = Field(ge=0)
    carrier_outcome: str = Field(min_length=1)
    safe_dry_run_passed: bool

    @model_validator(mode="after")
    def _safe_status_is_recomputed(self) -> Self:
        if self.harness_checks_passed != tuple(sorted(set(self.harness_checks_passed))):
            raise ValueError("passed harness checks must be unique and sorted")
        if self.harness_check_failures != tuple(sorted(set(self.harness_check_failures))):
            raise ValueError("failed harness checks must be unique and sorted")
        if set(self.harness_checks_passed) & set(self.harness_check_failures):
            raise ValueError("a harness check cannot both pass and fail")
        expected = (
            self.protocol_conformant
            and not self.harness_check_failures
            and self.family_safe_dry_run_passed
            and self.simulator_intercepted
            and self.carrier_transport_intercepted
            and self.network_escape_attempt_count == 0
            and self.carrier_outcome in _SAFE_DRY_RUN_OUTCOMES
        )
        if self.safe_dry_run_passed != expected:
            raise ValueError("safe dry-run status must be recomputed from harness evidence")
        return self


class LiveExecutionAuthorization(_StrictModel):
    """Content-bound authorization for exactly one variable and one live call."""

    schema_version: Literal["polisyos.fabric.live_execution_authorization.v1"] = (
        "polisyos.fabric.live_execution_authorization.v1"
    )
    attempt_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    request_variables: tuple[str, ...] = Field(min_length=1, max_length=1)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    schema_contract_sha256: str = Field(pattern=_SHA256_PATTERN)
    source_profile_sha256: str = Field(pattern=_SHA256_PATTERN)
    baseline_sha256: str = Field(pattern=_SHA256_PATTERN)
    harness: HarnessAuthorizationEvidence
    budget: LiveHttpBudget
    authorized: bool

    @model_validator(mode="after")
    def _authorization_is_recomputed(self) -> Self:
        if self.connector_id != self.harness.connector_id:
            raise ValueError("authorization connector must match the harness carrier")
        expected = self.harness.safe_dry_run_passed
        if self.authorized != expected:
            raise ValueError("authorization must be recomputed from harness evidence")
        return self


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic UTF-8 JSON bytes with one trailing newline."""

    normalized = _json_value(value)
    return (
        json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def content_sha256(value: object) -> str:
    """Return a canonical content hash for a JSON-compatible evidence value."""

    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def append_fsync_jsonl(path: Path, event: Mapping[str, Any]) -> JournalEventRef:
    """Append one canonical JSONL event, flush it, fsync it, and return its ref."""

    sequence = event.get("sequence")
    event_kind = event.get("event_kind")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise EvidenceJournalError("journal_sequence_invalid")
    if not isinstance(event_kind, str) or not event_kind.strip():
        raise EvidenceJournalError("journal_event_kind_missing")
    payload = canonical_json_bytes(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    byte_offset = path.stat().st_size if path.exists() else 0
    with path.open("ab") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return JournalEventRef(
        journal_path=path.as_posix(),
        sequence=sequence,
        event_kind=event_kind,
        event_sha256=f"sha256:{hashlib.sha256(payload).hexdigest()}",
        byte_offset=byte_offset,
        byte_length=len(payload),
    )


def verify_journal_event_ref(ref: JournalEventRef) -> bool:
    """Resolve and content-verify one event ref against durable journal bytes."""

    try:
        _read_verified_journal_event(ref)
    except EvidenceJournalError:
        return False
    return True


def resolve_journal_event_ref(ref: JournalEventRef) -> dict[str, Any]:
    """Return one verified canonical journal event or fail closed."""

    return _read_verified_journal_event(ref)


def resolve_linked_request_event(ref: JournalEventRef) -> dict[str, Any]:
    """Resolve the exact request event content-bound by one raw-response event."""

    if ref.event_kind != "raw_response":
        raise EvidenceJournalError("raw_response_event_required", ref.event_kind)
    raw_event = _read_verified_journal_event(ref)
    return _resolve_linked_request_event(ref, raw_event)


def resolve_raw_response_body(ref: JournalEventRef) -> bytes:
    """Resolve and verify the bounded body carried by one raw-response event."""

    if ref.event_kind != "raw_response":
        raise EvidenceJournalError("raw_response_event_required", ref.event_kind)
    event = _read_verified_journal_event(ref)
    _resolve_linked_request_event(ref, event)
    raw = event.get("raw_response")
    if not isinstance(raw, Mapping):
        raise EvidenceJournalError("raw_response_payload_missing", ref.event_sha256)
    encoded = raw.get("bounded_body_base64")
    expected_hash = raw.get("body_sha256")
    expected_size = raw.get("bytes_read")
    if not isinstance(encoded, str) or not isinstance(expected_hash, str):
        raise EvidenceJournalError("raw_response_body_missing", ref.event_sha256)
    try:
        body = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise EvidenceJournalError("raw_response_body_invalid", ref.event_sha256) from exc
    actual_hash = f"sha256:{hashlib.sha256(body).hexdigest()}"
    if actual_hash != expected_hash or expected_size != len(body):
        raise EvidenceJournalError("raw_response_body_identity_drift", ref.event_sha256)
    return body


def _read_verified_journal_event(ref: JournalEventRef) -> dict[str, Any]:
    """Read once, then verify and parse that exact immutable buffer."""

    path = Path(ref.journal_path)
    if not path.is_file():
        raise EvidenceJournalError("journal_event_ref_unresolved", ref.event_sha256)
    with path.open("rb") as handle:
        handle.seek(ref.byte_offset)
        payload = handle.read(ref.byte_length)
    if len(payload) != ref.byte_length:
        raise EvidenceJournalError("journal_event_ref_unresolved", ref.event_sha256)
    if f"sha256:{hashlib.sha256(payload).hexdigest()}" != ref.event_sha256:
        raise EvidenceJournalError("journal_event_ref_unresolved", ref.event_sha256)
    try:
        event = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceJournalError("journal_event_ref_unresolved", ref.event_sha256) from exc
    if not isinstance(event, dict):
        raise EvidenceJournalError("journal_event_not_mapping", ref.event_sha256)
    if canonical_json_bytes(event) != payload:
        raise EvidenceJournalError("journal_event_not_canonical", ref.event_sha256)
    if event.get("sequence") != ref.sequence or event.get("event_kind") != ref.event_kind:
        raise EvidenceJournalError("journal_event_ref_unresolved", ref.event_sha256)
    return event


def _resolve_linked_request_event(
    ref: JournalEventRef,
    raw_event: Mapping[str, Any],
) -> dict[str, Any]:
    raw = raw_event.get("raw_response")
    if not isinstance(raw, Mapping):
        raise EvidenceJournalError("raw_response_payload_missing", ref.event_sha256)
    request_sha = raw.get("request_event_sha256")
    attempt_id = raw_event.get("attempt_id")
    if not isinstance(request_sha, str) or not isinstance(attempt_id, str):
        raise EvidenceJournalError("linked_request_event_unresolved", ref.event_sha256)
    prefix = Path(ref.journal_path).read_bytes()[: ref.byte_offset]
    matches: list[dict[str, Any]] = []
    for payload in prefix.splitlines(keepends=True):
        if f"sha256:{hashlib.sha256(payload).hexdigest()}" != request_sha:
            continue
        try:
            candidate = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(candidate, dict) or canonical_json_bytes(candidate) != payload:
            continue
        request = candidate.get("request")
        if (
            candidate.get("event_kind") != "request"
            or candidate.get("attempt_id") != attempt_id
            or not isinstance(request, Mapping)
            or candidate.get("request_sha256") != content_sha256(request)
        ):
            continue
        matches.append(candidate)
    if len(matches) != 1:
        raise EvidenceJournalError("linked_request_event_unresolved", request_sha)
    return matches[0]


def derive_live_http_budget(
    profile: SourceProfile,
    *,
    timeout_cap_seconds: float = 15.0,
    heartbeat_cap_seconds: float = 5.0,
    max_response_bytes: int,
    max_decompressed_bytes: int,
) -> LiveHttpBudget:
    """Derive one-call limits from the actual Fabric source-profile owner."""

    profile_timeout = float(profile.timeout_seconds)
    rate_limit_rps = (
        float(profile.rate_limit_rps) if profile.rate_limit_rps is not None else None
    )
    requests_per_hour = (
        int(profile.requests_per_hour) if profile.requests_per_hour is not None else None
    )
    intervals: list[float] = []
    if rate_limit_rps is not None:
        intervals.append(1.0 / rate_limit_rps)
    if requests_per_hour is not None:
        intervals.append(3600.0 / requests_per_hour)
    timeout_seconds = min(profile_timeout, float(timeout_cap_seconds))
    return LiveHttpBudget(
        profile_timeout_seconds=profile_timeout,
        profile_rate_limit_rps=rate_limit_rps,
        profile_requests_per_hour=requests_per_hour,
        timeout_cap_seconds=float(timeout_cap_seconds),
        heartbeat_cap_seconds=float(heartbeat_cap_seconds),
        timeout_seconds=timeout_seconds,
        minimum_interval_seconds=max(intervals, default=0.0),
        heartbeat_interval_seconds=min(
            float(heartbeat_cap_seconds),
            timeout_seconds / 5.0,
        ),
        max_response_bytes=max_response_bytes,
        max_decompressed_bytes=max_decompressed_bytes,
        call_budget=1,
        variable_budget=1,
    )


def derive_harness_authorization_evidence(
    family_receipt: object,
    *,
    attempt_id: str,
) -> HarnessAuthorizationEvidence:
    """Project one selected carrier from a validated N13a family receipt."""

    payload = _json_value(family_receipt)
    if not isinstance(payload, Mapping):
        raise EvidenceJournalError("harness_family_receipt_invalid", attempt_id)
    attempts = payload.get("dry_run_attempts")
    if not isinstance(attempts, Sequence) or isinstance(attempts, (str, bytes, bytearray)):
        raise EvidenceJournalError("harness_carrier_receipts_missing", attempt_id)
    matching = [
        item
        for item in attempts
        if isinstance(item, Mapping) and str(item.get("attempt_id") or "") == attempt_id
    ]
    if len(matching) != 1:
        raise EvidenceJournalError("harness_carrier_receipt_unresolved", attempt_id)
    carrier = matching[0]
    passed = _string_tuple(payload.get("harness_checks_passed"))
    failures = _string_tuple(payload.get("harness_check_failures"))
    connector_id = str(payload.get("connector_id") or "")
    if not connector_id:
        raise EvidenceJournalError("harness_connector_missing", attempt_id)
    family_safe = bool(payload.get("safe_dry_run_passed"))
    carrier_outcome = str(carrier.get("outcome") or "")
    carrier_intercepted = bool(carrier.get("transport_intercepted"))
    expected_safe = (
        bool(payload.get("protocol_conformant"))
        and not failures
        and family_safe
        and bool(payload.get("simulator_intercepted"))
        and carrier_intercepted
        and int(payload.get("network_escape_attempt_count") or 0) == 0
        and carrier_outcome in _SAFE_DRY_RUN_OUTCOMES
    )
    return HarnessAuthorizationEvidence(
        connector_id=connector_id,
        family_receipt_sha256=content_sha256(payload),
        carrier_receipt_sha256=content_sha256(carrier),
        protocol_conformant=bool(payload.get("protocol_conformant")),
        harness_checks_passed=passed,
        harness_check_failures=failures,
        family_safe_dry_run_passed=family_safe,
        simulator_intercepted=bool(payload.get("simulator_intercepted")),
        carrier_transport_intercepted=carrier_intercepted,
        network_escape_attempt_count=int(payload.get("network_escape_attempt_count") or 0),
        carrier_outcome=carrier_outcome,
        safe_dry_run_passed=expected_safe,
    )


def require_authorized_execution(
    authorization: LiveExecutionAuthorization,
    *,
    family_receipt: object,
) -> None:
    """Resolve the N13a owner receipt and fail closed unless it authorizes the call."""

    if not authorization.authorized:
        raise EvidenceJournalError(
            "live_execution_not_authorized",
            authorization.attempt_id,
        )
    recomputed = derive_harness_authorization_evidence(
        family_receipt,
        attempt_id=authorization.attempt_id,
    )
    if recomputed != authorization.harness:
        raise EvidenceJournalError(
            "live_execution_harness_evidence_drift",
            authorization.attempt_id,
        )


class AppendOnlyEvidenceJournal:
    """Single-run owner for request, heartbeat, raw evidence, and classification."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if self.path.exists() and self.path.stat().st_size:
            raise EvidenceJournalError("journal_not_empty", self.path.as_posix())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sequence = 0
        self._requests: dict[str, JournalEventRef] = {}
        self._raw_evidence: dict[str, JournalEventRef] = {}
        self._heartbeat_state: dict[str, tuple[int, float]] = {}

    def _append(self, event_kind: str, payload: Mapping[str, Any]) -> JournalEventRef:
        self._sequence += 1
        return append_fsync_jsonl(
            self.path,
            {
                "sequence": self._sequence,
                "event_kind": event_kind,
                **dict(payload),
            },
        )

    def append_request(
        self,
        *,
        attempt_id: str,
        request: Mapping[str, Any],
    ) -> JournalEventRef:
        """Persist one schema-carrying, one-variable request before execution."""

        if attempt_id in self._requests:
            raise EvidenceJournalError("duplicate_attempt_request", attempt_id)
        variable = request.get("variable_id")
        variables = request.get("request_variables")
        one_variable = isinstance(variable, str) and bool(variable.strip())
        if isinstance(variables, Sequence) and not isinstance(
            variables, (str, bytes, bytearray)
        ):
            one_variable = len(variables) == 1 and bool(str(variables[0]).strip())
        if not one_variable:
            raise EvidenceJournalError("one_variable_request_required", attempt_id)
        schema_contract = request.get("schema_contract")
        if not isinstance(schema_contract, Mapping) or not schema_contract:
            raise EvidenceJournalError("schema_contract_required", attempt_id)
        ref = self._append(
            "request",
            {
                "attempt_id": attempt_id,
                "request": dict(request),
                "request_sha256": content_sha256(request),
            },
        )
        self._requests[attempt_id] = ref
        return ref

    def append_heartbeat(
        self,
        *,
        attempt_id: str,
        phase: str,
        progress_bytes: int,
        elapsed_seconds: float,
    ) -> JournalEventRef:
        """Persist one monotone progress event for an active attempt."""

        if attempt_id not in self._requests:
            raise EvidenceJournalError("heartbeat_request_missing", attempt_id)
        if attempt_id in self._raw_evidence:
            raise EvidenceJournalError("heartbeat_after_raw_evidence", attempt_id)
        if phase not in _HEARTBEAT_PHASES:
            raise EvidenceJournalError("heartbeat_phase_invalid", phase)
        if progress_bytes < 0 or elapsed_seconds < 0:
            raise EvidenceJournalError("heartbeat_value_negative", attempt_id)
        previous_progress, previous_elapsed = self._heartbeat_state.get(attempt_id, (0, 0.0))
        if progress_bytes < previous_progress:
            raise EvidenceJournalError("heartbeat_progress_not_monotone", attempt_id)
        if elapsed_seconds < previous_elapsed:
            raise EvidenceJournalError("heartbeat_elapsed_not_monotone", attempt_id)
        ref = self._append(
            "heartbeat",
            {
                "attempt_id": attempt_id,
                "heartbeat": {
                    "phase": phase,
                    "progress_bytes": progress_bytes,
                    "elapsed_seconds": elapsed_seconds,
                },
            },
        )
        self._heartbeat_state[attempt_id] = (progress_bytes, elapsed_seconds)
        return ref

    def append_raw_evidence(
        self,
        *,
        attempt_id: str,
        request_ref: JournalEventRef,
        payload: bytes,
        status_code: int | None,
        response_headers: Mapping[str, str],
        budget: LiveHttpBudget,
    ) -> JournalEventRef:
        """Persist bounded response bytes before any classification consumes them."""

        expected_request = self._requests.get(attempt_id)
        if expected_request != request_ref or not verify_journal_event_ref(request_ref):
            raise EvidenceJournalError("request_evidence_ref_invalid", attempt_id)
        if attempt_id in self._raw_evidence:
            raise EvidenceJournalError("duplicate_raw_evidence", attempt_id)
        if len(payload) > budget.max_response_bytes or len(payload) > budget.max_decompressed_bytes:
            raise EvidenceJournalError("response_budget_exceeded", attempt_id)
        if status_code is not None and not 100 <= status_code <= 599:
            raise EvidenceJournalError("response_status_invalid", str(status_code))
        ref = self._append(
            "raw_response",
            {
                "attempt_id": attempt_id,
                "raw_response": {
                    "request_event_sha256": request_ref.event_sha256,
                    "status_code": status_code,
                    "response_headers": dict(sorted(response_headers.items())),
                    "bounded_body_base64": base64.b64encode(payload).decode("ascii"),
                    "body_sha256": f"sha256:{hashlib.sha256(payload).hexdigest()}",
                    "bytes_read": len(payload),
                },
            },
        )
        self._raw_evidence[attempt_id] = ref
        return ref

    def append_classification(
        self,
        *,
        attempt_id: str,
        evidence_ref: JournalEventRef,
        classification: Mapping[str, Any],
    ) -> JournalEventRef:
        """Persist a classification only after resolving its raw response bytes."""

        expected = self._raw_evidence.get(attempt_id)
        if expected is None or evidence_ref.event_kind != "raw_response":
            raise EvidenceJournalError("raw_evidence_required", attempt_id)
        if expected != evidence_ref or not verify_journal_event_ref(evidence_ref):
            raise EvidenceJournalError("raw_evidence_ref_invalid", attempt_id)
        return self._append(
            "classification",
            {
                "attempt_id": attempt_id,
                "evidence_event_sha256": evidence_ref.event_sha256,
                "classification": dict(classification),
            },
        )


def _json_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(sorted({str(item) for item in value if str(item).strip()}))


__all__ = [
    "AppendOnlyEvidenceJournal",
    "EvidenceJournalError",
    "HarnessAuthorizationEvidence",
    "JournalEventRef",
    "LiveExecutionAuthorization",
    "LiveHttpBudget",
    "append_fsync_jsonl",
    "canonical_json_bytes",
    "content_sha256",
    "derive_harness_authorization_evidence",
    "derive_live_http_budget",
    "require_authorized_execution",
    "resolve_journal_event_ref",
    "resolve_linked_request_event",
    "resolve_raw_response_body",
    "verify_journal_event_ref",
]
