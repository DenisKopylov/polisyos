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
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from polisyos.fabric.connectors.profiles.models import SourceProfile

_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_SAFE_TERMINAL_CODE_PATTERN = r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
_SAFE_TERMINAL_CODE = re.compile(_SAFE_TERMINAL_CODE_PATTERN)
_LIVE_ATTEMPT_TERMINAL_EVENT_KEYS = frozenset(
    {
        "sequence",
        "event_kind",
        "schema_version",
        "attempt_id",
        "request_event_sha256",
        "raw_evidence_event_sha256",
        "failure_code",
        "outcome_code",
        "http_status_code",
        "quarantine",
        "response_admitted",
        "terminal_sha256",
    }
)
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
_LIVE_HEARTBEAT_PHASE_ORDER = {
    "attempt_started": 0,
    "waiting": 1,
    "response_headers": 2,
    "body_progress": 3,
}
_REQUIRED_LIVE_HEARTBEAT_PHASES = (
    "attempt_started",
    "response_headers",
    "body_progress",
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


class LiveTransportTrace(_StrictModel):
    """Content-derived proof of exactly one journaled live HTTP attempt."""

    schema_version: Literal["polisyos.fabric.live_transport_trace.v1"] = (
        "polisyos.fabric.live_transport_trace.v1"
    )
    attempt_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    params: dict[str, object]
    params_sha256: str = Field(pattern=_SHA256_PATTERN)
    request_ref: JournalEventRef
    transport_attempt_ref: JournalEventRef
    heartbeat_refs: tuple[JournalEventRef, ...] = Field(min_length=3)
    heartbeat_phases: tuple[str, ...] = Field(min_length=3)
    raw_evidence_ref: JournalEventRef
    call_count: Literal[1] = 1
    trace_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _projection_is_content_derived(self) -> Self:
        refs = (
            self.request_ref,
            self.transport_attempt_ref,
            *self.heartbeat_refs,
            self.raw_evidence_ref,
        )
        if len({ref.journal_path for ref in refs}) != 1:
            raise ValueError("transport trace refs must share one journal")
        if [ref.sequence for ref in refs] != sorted(ref.sequence for ref in refs):
            raise ValueError("transport trace refs must preserve journal order")
        if self.request_ref.event_kind != "request":
            raise ValueError("transport trace request ref is invalid")
        if self.transport_attempt_ref.event_kind != "transport_attempt":
            raise ValueError("transport trace attempt ref is invalid")
        if any(ref.event_kind != "heartbeat" for ref in self.heartbeat_refs):
            raise ValueError("transport trace heartbeat ref is invalid")
        if self.raw_evidence_ref.event_kind != "raw_response":
            raise ValueError("transport trace raw ref is invalid")
        if len(self.heartbeat_refs) != len(self.heartbeat_phases):
            raise ValueError("transport trace heartbeat projection is incomplete")
        if not _live_heartbeat_phases_are_valid(self.heartbeat_phases):
            raise ValueError("transport trace heartbeat phases are invalid")
        if self.params_sha256 != content_sha256(self.params):
            raise ValueError("transport trace params identity is invalid")
        expected_trace_sha = _live_transport_trace_sha256(
            attempt_id=self.attempt_id,
            connector_id=self.connector_id,
            url=self.url,
            params=self.params,
            params_sha256=self.params_sha256,
            request_ref=self.request_ref,
            transport_attempt_ref=self.transport_attempt_ref,
            heartbeat_refs=self.heartbeat_refs,
            heartbeat_phases=self.heartbeat_phases,
            raw_evidence_ref=self.raw_evidence_ref,
            call_count=self.call_count,
        )
        if self.trace_sha256 != expected_trace_sha:
            raise ValueError("transport trace identity must be recomputed")
        return self


class LiveAttemptTerminal(_StrictModel):
    """Resolved quarantine terminal derived from one exact live-attempt journal.

    Instances returned by :func:`resolve_live_attempt_terminal` have reopened
    and content-verified every referenced event. Constructing this DTO alone
    does not confer evidence authority.
    """

    schema_version: Literal["polisyos.fabric.live_attempt_terminal.v1"] = (
        "polisyos.fabric.live_attempt_terminal.v1"
    )
    attempt_id: str = Field(min_length=1)
    outcome_code: str = Field(
        min_length=1,
        max_length=140,
        pattern=_SAFE_TERMINAL_CODE_PATTERN,
    )
    failure_code: str = Field(
        min_length=1,
        max_length=120,
        pattern=_SAFE_TERMINAL_CODE_PATTERN,
    )
    request_ref: JournalEventRef
    raw_evidence_ref: JournalEventRef | None = None
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    quarantine: Literal[True] = True
    response_admitted: Literal[False] = False
    terminal_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _terminal_is_evidence_derived(self) -> Self:
        if self.request_ref.event_kind != "request":
            raise ValueError("live terminal request ref is invalid")
        if self.raw_evidence_ref is None:
            if self.http_status_code is not None:
                raise ValueError("live terminal status requires raw evidence")
        else:
            if self.raw_evidence_ref.event_kind != "raw_response":
                raise ValueError("live terminal raw ref is invalid")
            if self.raw_evidence_ref.journal_path != self.request_ref.journal_path:
                raise ValueError("live terminal refs must share one journal")
            if self.raw_evidence_ref.sequence <= self.request_ref.sequence:
                raise ValueError("live terminal raw evidence must follow its request")
        expected_outcome = _derive_live_attempt_outcome(
            failure_code=self.failure_code,
            http_status_code=self.http_status_code,
            raw_response_present=self.raw_evidence_ref is not None,
        )
        if self.outcome_code != expected_outcome:
            raise ValueError("live terminal outcome must be evidence-derived")
        expected_sha = _live_attempt_terminal_sha256(
            attempt_id=self.attempt_id,
            request_ref=self.request_ref,
            raw_evidence_ref=self.raw_evidence_ref,
            failure_code=self.failure_code,
            outcome_code=self.outcome_code,
            http_status_code=self.http_status_code,
        )
        if self.terminal_sha256 != expected_sha:
            raise ValueError("live terminal identity must be recomputed")
        return self


class HarnessAuthorizationEvidence(_StrictModel):
    """N13a E7 harness projection that recomputes whether one carrier is safe."""

    attempt_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
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
        if self.attempt_id != self.harness.attempt_id:
            raise ValueError("authorization attempt must match the harness carrier")
        if self.connector_id != self.harness.connector_id:
            raise ValueError("authorization connector must match the harness carrier")
        if self.profile_id != self.harness.profile_id:
            raise ValueError("authorization profile must match the harness carrier")
        if self.request_variables != (self.harness.request_dataset_id,):
            raise ValueError("authorization variable must match the harness carrier")
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


def _derive_live_attempt_outcome(
    *,
    failure_code: str,
    http_status_code: int | None,
    raw_response_present: bool,
) -> str:
    """Derive an open, syntax-safe outcome from paid journal evidence."""

    if _SAFE_TERMINAL_CODE.fullmatch(failure_code) is None:
        raise ValueError("live terminal failure code is unsafe")
    if http_status_code in {401, 403}:
        return "auth_required"
    if http_status_code == 429:
        return "rate_limited"
    if http_status_code in {408, 504}:
        return "timeout"
    if http_status_code is not None and http_status_code >= 400:
        return "http_error"

    tokens = frozenset(failure_code.split("_"))
    if tokens & {"auth", "credential", "credentials", "permission"}:
        return "auth_required"
    if "rate" in tokens and "limit" in tokens:
        return "rate_limited"
    if tokens & {"license", "licence", "terms", "tos"}:
        return "license_unclear"
    if tokens & {"timeout", "timedout"}:
        return "timeout"
    if tokens & {"network", "dns", "tls", "connect", "connection"}:
        return "network_unreachable"
    if tokens & {"budget", "quota"}:
        return "budget_exhausted"
    if tokens & {"header", "headers", "contenttype"}:
        return "response_rejected"
    if tokens & {"pii", "privacy"}:
        return "pii_restricted"
    if tokens & {"checksum", "integrity", "watermark"}:
        return "integrity_failed"
    if raw_response_present and tokens & {"schema", "profile", "field", "fields"}:
        return "alive_schema_drift"
    if raw_response_present and tokens & {
        "normalization",
        "normalize",
        "transform",
        "coercion",
        "units",
    }:
        return "normalization_failed"
    prefix = "quarantined" if raw_response_present else "failed"
    return f"{prefix}_{failure_code}"


def _live_attempt_terminal_sha256(
    *,
    attempt_id: str,
    request_ref: JournalEventRef,
    raw_evidence_ref: JournalEventRef | None,
    failure_code: str,
    outcome_code: str,
    http_status_code: int | None,
) -> str:
    return content_sha256(
        {
            "schema_version": "polisyos.fabric.live_attempt_terminal.v1",
            "attempt_id": attempt_id,
            "request_event_sha256": request_ref.event_sha256,
            "raw_evidence_event_sha256": (
                raw_evidence_ref.event_sha256 if raw_evidence_ref is not None else None
            ),
            "failure_code": failure_code,
            "outcome_code": outcome_code,
            "http_status_code": http_status_code,
            "quarantine": True,
            "response_admitted": False,
        }
    )


def _live_heartbeat_phases_are_valid(phases: Sequence[str]) -> bool:
    if any(phase not in _LIVE_HEARTBEAT_PHASE_ORDER for phase in phases):
        return False
    ranks = [_LIVE_HEARTBEAT_PHASE_ORDER[phase] for phase in phases]
    if ranks != sorted(ranks):
        return False
    return all(
        phases.count(required) == 1 for required in _REQUIRED_LIVE_HEARTBEAT_PHASES[:2]
    ) and (phases.count("body_progress") >= 1)


def _live_transport_trace_sha256(
    *,
    attempt_id: str,
    connector_id: str,
    url: str,
    params: Mapping[str, object],
    params_sha256: str,
    request_ref: JournalEventRef,
    transport_attempt_ref: JournalEventRef,
    heartbeat_refs: Sequence[JournalEventRef],
    heartbeat_phases: Sequence[str],
    raw_evidence_ref: JournalEventRef,
    call_count: int,
) -> str:
    return content_sha256(
        {
            "attempt_id": attempt_id,
            "connector_id": connector_id,
            "url": url,
            "params": dict(params),
            "params_sha256": params_sha256,
            "request_event_sha256": request_ref.event_sha256,
            "transport_event_sha256": transport_attempt_ref.event_sha256,
            "heartbeat_event_sha256s": tuple(ref.event_sha256 for ref in heartbeat_refs),
            "heartbeat_phases": tuple(heartbeat_phases),
            "raw_evidence_event_sha256": raw_evidence_ref.event_sha256,
            "call_count": call_count,
        }
    )


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


def resolve_live_attempt_terminal(ref: JournalEventRef) -> LiveAttemptTerminal:
    """Reopen one journal and resolve its unique terminal for an attempt."""

    if ref.event_kind != "live_attempt_terminal":
        raise EvidenceJournalError("live_attempt_terminal_event_required", ref.event_kind)
    records = _read_canonical_journal(Path(ref.journal_path))
    return _resolve_live_attempt_terminal(ref, records)


def resolve_live_attempt_terminals(path: Path) -> tuple[LiveAttemptTerminal, ...]:
    """Resolve the full request denominator, requiring one terminal per attempt."""

    records = _read_canonical_journal(Path(path))
    request_records = [
        (event_ref, event) for event_ref, event in records if event.get("event_kind") == "request"
    ]
    request_ids: list[str] = []
    for _request_ref, event in request_records:
        attempt_id = event.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id.strip():
            raise EvidenceJournalError("live_terminal_request_link_invalid", str(attempt_id))
        request_ids.append(attempt_id)
    if len(request_ids) != len(set(request_ids)):
        raise EvidenceJournalError("duplicate_attempt_request")

    terminal_records = [
        (event_ref, event)
        for event_ref, event in records
        if event.get("event_kind") == "live_attempt_terminal"
    ]
    terminals_by_attempt: dict[str, list[JournalEventRef]] = {}
    for terminal_ref, event in terminal_records:
        attempt_id = event.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id.strip():
            raise EvidenceJournalError("live_attempt_terminal_invalid", str(attempt_id))
        terminals_by_attempt.setdefault(attempt_id, []).append(terminal_ref)
    duplicate_ids = sorted(
        attempt_id for attempt_id, refs in terminals_by_attempt.items() if len(refs) != 1
    )
    if duplicate_ids:
        raise EvidenceJournalError(
            "duplicate_live_attempt_terminal",
            ",".join(duplicate_ids),
        )
    missing_ids = sorted(set(request_ids) - terminals_by_attempt.keys())
    if missing_ids:
        raise EvidenceJournalError(
            "live_attempt_terminal_missing",
            ",".join(missing_ids),
        )
    orphan_ids = sorted(terminals_by_attempt.keys() - set(request_ids))
    if orphan_ids:
        raise EvidenceJournalError(
            "live_terminal_request_link_invalid",
            ",".join(orphan_ids),
        )
    return tuple(
        _resolve_live_attempt_terminal(terminals_by_attempt[attempt_id][0], records)
        for attempt_id in request_ids
    )


def _resolve_live_attempt_terminal(
    ref: JournalEventRef,
    records: Sequence[tuple[JournalEventRef, dict[str, Any]]],
) -> LiveAttemptTerminal:
    terminal_matches = [(event_ref, event) for event_ref, event in records if event_ref == ref]
    if len(terminal_matches) != 1:
        raise EvidenceJournalError("journal_event_ref_unresolved", ref.event_sha256)
    terminal_ref, event = terminal_matches[0]
    attempt_id = event.get("attempt_id")
    if (
        set(event) != _LIVE_ATTEMPT_TERMINAL_EVENT_KEYS
        or not isinstance(attempt_id, str)
        or not attempt_id.strip()
    ):
        raise EvidenceJournalError("live_attempt_terminal_invalid", ref.event_sha256)

    sibling_terminals = [
        event_ref
        for event_ref, candidate in records
        if candidate.get("event_kind") == "live_attempt_terminal"
        and candidate.get("attempt_id") == attempt_id
    ]
    if len(sibling_terminals) != 1:
        raise EvidenceJournalError("duplicate_live_attempt_terminal", attempt_id)

    request_sha = event.get("request_event_sha256")
    attempt_requests = [
        (event_ref, candidate)
        for event_ref, candidate in records
        if candidate.get("event_kind") == "request" and candidate.get("attempt_id") == attempt_id
    ]
    if (
        not isinstance(request_sha, str)
        or len(attempt_requests) != 1
        or attempt_requests[0][0].event_sha256 != request_sha
    ):
        raise EvidenceJournalError("live_terminal_request_link_invalid", attempt_id)
    request_ref, request_event = attempt_requests[0]
    request_payload = request_event.get("request")
    if (
        not isinstance(request_payload, Mapping)
        or request_event.get("request_sha256") != content_sha256(request_payload)
        or request_ref.sequence >= terminal_ref.sequence
    ):
        raise EvidenceJournalError("live_terminal_request_link_invalid", attempt_id)

    raw_records = [
        (event_ref, candidate)
        for event_ref, candidate in records
        if candidate.get("event_kind") == "raw_response"
        and candidate.get("attempt_id") == attempt_id
    ]
    if len(raw_records) > 1:
        raise EvidenceJournalError("duplicate_raw_evidence", attempt_id)
    raw_sha = event.get("raw_evidence_event_sha256")
    raw_ref: JournalEventRef | None = None
    http_status_code: int | None = None
    if raw_records:
        if not isinstance(raw_sha, str):
            raise EvidenceJournalError("live_terminal_raw_link_required", attempt_id)
        candidate_ref, raw_event = raw_records[0]
        if candidate_ref.event_sha256 != raw_sha:
            raise EvidenceJournalError("live_terminal_raw_link_invalid", attempt_id)
        raw_payload = raw_event.get("raw_response")
        if (
            not isinstance(raw_payload, Mapping)
            or raw_payload.get("request_event_sha256") != request_ref.event_sha256
            or not request_ref.sequence < candidate_ref.sequence < terminal_ref.sequence
        ):
            raise EvidenceJournalError("live_terminal_raw_link_invalid", attempt_id)
        resolve_raw_response_body(candidate_ref)
        status = raw_payload.get("status_code")
        if status is not None and (
            not isinstance(status, int) or isinstance(status, bool) or not 100 <= status <= 599
        ):
            raise EvidenceJournalError("live_terminal_raw_link_invalid", attempt_id)
        raw_ref = candidate_ref
        http_status_code = status
    elif raw_sha is not None:
        raise EvidenceJournalError("live_terminal_raw_link_invalid", attempt_id)

    stored_status = event.get("http_status_code")
    if stored_status != http_status_code:
        raise EvidenceJournalError("live_terminal_http_status_drift", attempt_id)
    failure_code = event.get("failure_code")
    if (
        not isinstance(failure_code, str)
        or len(failure_code) > 120
        or _SAFE_TERMINAL_CODE.fullmatch(failure_code) is None
    ):
        raise EvidenceJournalError("live_terminal_failure_code_invalid", attempt_id)
    outcome_code = event.get("outcome_code")
    expected_outcome = _derive_live_attempt_outcome(
        failure_code=failure_code,
        http_status_code=http_status_code,
        raw_response_present=raw_ref is not None,
    )
    if outcome_code != expected_outcome:
        raise EvidenceJournalError("live_terminal_outcome_drift", attempt_id)
    if (
        event.get("schema_version") != "polisyos.fabric.live_attempt_terminal.v1"
        or event.get("quarantine") is not True
        or event.get("response_admitted") is not False
    ):
        raise EvidenceJournalError("live_attempt_terminal_invalid", attempt_id)

    later_attempt_events = [
        candidate_ref
        for candidate_ref, candidate in records
        if candidate.get("attempt_id") == attempt_id
        and candidate_ref.sequence > terminal_ref.sequence
    ]
    if later_attempt_events:
        raise EvidenceJournalError("live_attempt_event_after_terminal", attempt_id)

    terminal_sha = event.get("terminal_sha256")
    expected_sha = _live_attempt_terminal_sha256(
        attempt_id=attempt_id,
        request_ref=request_ref,
        raw_evidence_ref=raw_ref,
        failure_code=failure_code,
        outcome_code=expected_outcome,
        http_status_code=http_status_code,
    )
    if terminal_sha != expected_sha:
        raise EvidenceJournalError("live_terminal_identity_drift", attempt_id)
    return LiveAttemptTerminal(
        attempt_id=attempt_id,
        outcome_code=expected_outcome,
        failure_code=failure_code,
        request_ref=request_ref,
        raw_evidence_ref=raw_ref,
        http_status_code=http_status_code,
        quarantine=True,
        response_admitted=False,
        terminal_sha256=expected_sha,
    )


def resolve_live_transport_trace(ref: JournalEventRef) -> LiveTransportTrace:
    """Reopen a canonical journal and derive an exact one-call transport proof."""

    if ref.event_kind != "raw_response":
        raise EvidenceJournalError("raw_response_event_required", ref.event_kind)
    records = _read_canonical_journal(Path(ref.journal_path))
    raw_matches = [(event_ref, event) for event_ref, event in records if event_ref == ref]
    if len(raw_matches) != 1:
        raise EvidenceJournalError("journal_event_ref_unresolved", ref.event_sha256)
    raw_ref, raw_event = raw_matches[0]
    attempt_id = raw_event.get("attempt_id")
    raw_payload = raw_event.get("raw_response")
    if not isinstance(attempt_id, str) or not attempt_id.strip():
        raise EvidenceJournalError("live_transport_attempt_id_invalid", ref.event_sha256)
    if not isinstance(raw_payload, Mapping):
        raise EvidenceJournalError("raw_response_payload_missing", ref.event_sha256)
    transport_sha = raw_payload.get("transport_event_sha256")
    if not isinstance(transport_sha, str):
        raise EvidenceJournalError("live_transport_link_required", attempt_id)

    transport_records = [
        (event_ref, event)
        for event_ref, event in records
        if event.get("event_kind") == "transport_attempt" and event.get("attempt_id") == attempt_id
    ]
    call_count = len(transport_records)
    if call_count != 1:
        raise EvidenceJournalError(
            "live_transport_call_count_invalid",
            f"{attempt_id}:{call_count}",
        )
    transport_ref, transport_event = transport_records[0]
    if (
        transport_event.get("attempt_id") != attempt_id
        or transport_ref.event_sha256 != transport_sha
    ):
        raise EvidenceJournalError("live_transport_link_invalid", attempt_id)
    transport_payload = transport_event.get("transport_attempt")
    if not isinstance(transport_payload, Mapping):
        raise EvidenceJournalError("live_transport_attempt_invalid", attempt_id)

    request_sha = raw_payload.get("request_event_sha256")
    transport_request_sha = transport_payload.get("request_event_sha256")
    request_records = [
        (event_ref, event)
        for event_ref, event in records
        if event.get("event_kind") == "request"
        and event.get("attempt_id") == attempt_id
        and event_ref.event_sha256 == request_sha
    ]
    if (
        not isinstance(request_sha, str)
        or transport_request_sha != request_sha
        or len(request_records) != 1
    ):
        raise EvidenceJournalError("live_transport_request_link_invalid", attempt_id)
    request_ref, request_event = request_records[0]
    request_payload = request_event.get("request")
    if not isinstance(request_payload, Mapping) or request_event.get(
        "request_sha256"
    ) != content_sha256(request_payload):
        raise EvidenceJournalError("live_transport_request_link_invalid", attempt_id)
    if not request_ref.sequence < transport_ref.sequence < raw_ref.sequence:
        raise EvidenceJournalError("live_transport_order_invalid", attempt_id)

    connector_id = transport_payload.get("connector_id")
    url = transport_payload.get("url")
    params = transport_payload.get("params")
    params_sha = transport_payload.get("params_sha256")
    if (
        not isinstance(connector_id, str)
        or not connector_id.strip()
        or not isinstance(url, str)
        or not url.strip()
        or not isinstance(params, Mapping)
        or not isinstance(params_sha, str)
        or params_sha != content_sha256(params)
    ):
        raise EvidenceJournalError("live_transport_attempt_invalid", attempt_id)
    normalized_params = {str(key): value for key, value in params.items()}

    heartbeat_records = [
        (event_ref, event)
        for event_ref, event in records
        if event.get("event_kind") == "heartbeat" and event.get("attempt_id") == attempt_id
    ]
    if not heartbeat_records or any(
        not transport_ref.sequence < event_ref.sequence < raw_ref.sequence
        for event_ref, _ in heartbeat_records
    ):
        raise EvidenceJournalError("live_transport_heartbeat_invalid", attempt_id)
    heartbeat_refs: list[JournalEventRef] = []
    heartbeat_phases: list[str] = []
    previous_progress = 0
    previous_elapsed = 0.0
    for heartbeat_ref, heartbeat_event in heartbeat_records:
        heartbeat = heartbeat_event.get("heartbeat")
        if not isinstance(heartbeat, Mapping):
            raise EvidenceJournalError("live_transport_heartbeat_invalid", attempt_id)
        phase = heartbeat.get("phase")
        progress = heartbeat.get("progress_bytes")
        elapsed = heartbeat.get("elapsed_seconds")
        if (
            not isinstance(phase, str)
            or not isinstance(progress, int)
            or isinstance(progress, bool)
            or not isinstance(elapsed, (int, float))
            or isinstance(elapsed, bool)
            or progress < previous_progress
            or float(elapsed) < previous_elapsed
        ):
            raise EvidenceJournalError("live_transport_heartbeat_invalid", attempt_id)
        heartbeat_refs.append(heartbeat_ref)
        heartbeat_phases.append(phase)
        previous_progress = progress
        previous_elapsed = float(elapsed)
    if not _live_heartbeat_phases_are_valid(heartbeat_phases):
        raise EvidenceJournalError("live_transport_heartbeat_invalid", attempt_id)
    body = resolve_raw_response_body(raw_ref)
    if previous_progress != len(body):
        raise EvidenceJournalError("live_transport_heartbeat_invalid", attempt_id)

    heartbeat_ref_tuple = tuple(heartbeat_refs)
    heartbeat_phase_tuple = tuple(heartbeat_phases)
    trace_sha = _live_transport_trace_sha256(
        attempt_id=attempt_id,
        connector_id=connector_id,
        url=url,
        params=normalized_params,
        params_sha256=params_sha,
        request_ref=request_ref,
        transport_attempt_ref=transport_ref,
        heartbeat_refs=heartbeat_ref_tuple,
        heartbeat_phases=heartbeat_phase_tuple,
        raw_evidence_ref=raw_ref,
        call_count=call_count,
    )
    return LiveTransportTrace(
        attempt_id=attempt_id,
        connector_id=connector_id,
        url=url,
        params=normalized_params,
        params_sha256=params_sha,
        request_ref=request_ref,
        transport_attempt_ref=transport_ref,
        heartbeat_refs=heartbeat_ref_tuple,
        heartbeat_phases=heartbeat_phase_tuple,
        raw_evidence_ref=raw_ref,
        call_count=call_count,
        trace_sha256=trace_sha,
    )


def _read_canonical_journal(
    path: Path,
) -> list[tuple[JournalEventRef, dict[str, Any]]]:
    """Reopen and verify every canonical JSONL event in sequence order."""

    if not path.is_file():
        raise EvidenceJournalError("journal_event_ref_unresolved", path.as_posix())
    journal_bytes = path.read_bytes()
    payloads = journal_bytes.splitlines(keepends=True)
    if not payloads or b"".join(payloads) != journal_bytes:
        raise EvidenceJournalError("journal_not_canonical", path.as_posix())
    records: list[tuple[JournalEventRef, dict[str, Any]]] = []
    byte_offset = 0
    for expected_sequence, payload in enumerate(payloads, start=1):
        try:
            event = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvidenceJournalError(
                "journal_not_canonical",
                path.as_posix(),
            ) from exc
        if (
            not isinstance(event, dict)
            or canonical_json_bytes(event) != payload
            or event.get("sequence") != expected_sequence
            or not isinstance(event.get("event_kind"), str)
            or not str(event["event_kind"]).strip()
        ):
            raise EvidenceJournalError("journal_not_canonical", path.as_posix())
        event_ref = JournalEventRef(
            journal_path=path.as_posix(),
            sequence=expected_sequence,
            event_kind=str(event["event_kind"]),
            event_sha256=f"sha256:{hashlib.sha256(payload).hexdigest()}",
            byte_offset=byte_offset,
            byte_length=len(payload),
        )
        records.append((event_ref, event))
        byte_offset += len(payload)
    return records


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
    rate_limit_rps = float(profile.rate_limit_rps) if profile.rate_limit_rps is not None else None
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
    profile_id = str(carrier.get("profile_id") or "")
    if not profile_id:
        raise EvidenceJournalError("harness_profile_missing", attempt_id)
    request_dataset_id = str(carrier.get("request_dataset_id") or "")
    if not request_dataset_id:
        raise EvidenceJournalError("harness_request_dataset_missing", attempt_id)
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
        attempt_id=attempt_id,
        connector_id=connector_id,
        profile_id=profile_id,
        request_dataset_id=request_dataset_id,
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


def build_live_execution_authorization(
    *,
    attempt_id: str,
    connector_id: str,
    request_dataset_id: str,
    request: Mapping[str, Any],
    schema_contract: Mapping[str, Any],
    source_profile: SourceProfile,
    baseline_sha256: str,
    family_receipt: object,
    timeout_cap_seconds: float = 15.0,
    heartbeat_cap_seconds: float = 5.0,
    max_response_bytes: int,
    max_decompressed_bytes: int,
) -> LiveExecutionAuthorization:
    """Build a one-call authorization from the exact E7-tested carrier.

    The request is content-bound only after its connector, profile, requested
    dataset, and schema contract are proven identical to the selected carrier
    and the SourceProfile owner.  A family-level green receipt cannot authorize
    a sibling carrier.
    """

    harness = derive_harness_authorization_evidence(
        family_receipt,
        attempt_id=attempt_id,
    )
    request_connector = request.get("connector_id")
    request_profile = request.get("profile_id")
    request_dataset = request.get("request_dataset_id")
    request_schema = request.get("schema_contract")
    if (
        connector_id != harness.connector_id
        or request_connector != connector_id
        or source_profile.profile_id != harness.profile_id
        or request_profile != source_profile.profile_id
        or request_dataset_id != harness.request_dataset_id
        or request_dataset != request_dataset_id
        or request_schema != schema_contract
        or not schema_contract
    ):
        raise EvidenceJournalError(
            "live_execution_request_contract_drift",
            attempt_id,
        )
    authorization = LiveExecutionAuthorization(
        attempt_id=attempt_id,
        connector_id=connector_id,
        profile_id=source_profile.profile_id,
        request_variables=(request_dataset_id,),
        request_sha256=content_sha256(request),
        schema_contract_sha256=content_sha256(schema_contract),
        source_profile_sha256=content_sha256(source_profile),
        baseline_sha256=baseline_sha256,
        harness=harness,
        budget=derive_live_http_budget(
            source_profile,
            timeout_cap_seconds=timeout_cap_seconds,
            heartbeat_cap_seconds=heartbeat_cap_seconds,
            max_response_bytes=max_response_bytes,
            max_decompressed_bytes=max_decompressed_bytes,
        ),
        authorized=harness.safe_dry_run_passed,
    )
    require_authorized_execution(authorization, family_receipt=family_receipt)
    return authorization


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
    """Recurring owner for request, heartbeat, raw evidence, and classification.

    A non-empty journal is appendable only after every prior attempt is
    terminal-closed and the complete canonical history is content-verified.
    This preserves paid evidence across recurring runs without allowing an
    incomplete or edited history to authorize another carrier.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if self.path.exists() and not self.path.is_file():
            raise EvidenceJournalError("journal_not_canonical", self.path.as_posix())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sequence = 0
        self._requests: dict[str, JournalEventRef] = {}
        self._transport_attempts: dict[str, list[JournalEventRef]] = {}
        self._raw_evidence: dict[str, JournalEventRef] = {}
        self._terminals: dict[str, JournalEventRef] = {}
        self._heartbeat_state: dict[str, tuple[int, float]] = {}
        if self.path.exists() and self.path.stat().st_size:
            self._reopen_completed_history()
        self._expected_journal_sha256 = self._current_journal_sha256()

    def _append(self, event_kind: str, payload: Mapping[str, Any]) -> JournalEventRef:
        if self._current_journal_sha256() != self._expected_journal_sha256:
            raise EvidenceJournalError("journal_changed_since_open", self.path.as_posix())
        next_sequence = self._sequence + 1
        ref = append_fsync_jsonl(
            self.path,
            {
                "sequence": next_sequence,
                "event_kind": event_kind,
                **dict(payload),
            },
        )
        self._sequence = next_sequence
        self._expected_journal_sha256 = self._current_journal_sha256()
        return ref

    def _current_journal_sha256(self) -> str:
        payload = self.path.read_bytes() if self.path.is_file() else b""
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"

    def _reopen_completed_history(self) -> None:
        records = _read_canonical_journal(self.path)
        terminals = resolve_live_attempt_terminals(self.path)
        terminal_refs = {
            str(event["attempt_id"]): event_ref
            for event_ref, event in records
            if event.get("event_kind") == "live_attempt_terminal"
        }
        self._sequence = records[-1][0].sequence
        for terminal in terminals:
            self._requests[terminal.attempt_id] = terminal.request_ref
            if terminal.raw_evidence_ref is not None:
                self._raw_evidence[terminal.attempt_id] = terminal.raw_evidence_ref
            self._terminals[terminal.attempt_id] = terminal_refs[terminal.attempt_id]

        for event_ref, event in records:
            attempt_id = event.get("attempt_id")
            event_kind = event.get("event_kind")
            if not isinstance(attempt_id, str) or attempt_id not in self._requests:
                raise EvidenceJournalError(
                    "journal_attempt_unresolved",
                    str(attempt_id),
                )
            if event_kind == "request":
                self._validate_reopened_request(event_ref, event)
            elif event_kind == "transport_attempt":
                self._validate_reopened_transport(event_ref, event)
            elif event_kind == "heartbeat":
                self._validate_reopened_heartbeat(event_ref, event)
            elif event_kind == "raw_response":
                if self._raw_evidence.get(attempt_id) != event_ref:
                    raise EvidenceJournalError("raw_evidence_ref_invalid", attempt_id)
            elif event_kind == "classification":
                self._validate_reopened_classification(event_ref, event)
            elif event_kind == "live_attempt_terminal":
                if self._terminals.get(attempt_id) != event_ref:
                    raise EvidenceJournalError("duplicate_live_attempt_terminal", attempt_id)
            else:
                raise EvidenceJournalError(
                    "journal_event_kind_unsupported",
                    str(event_kind),
                )

        for attempt_id, attempts in self._transport_attempts.items():
            if len(attempts) != 1:
                raise EvidenceJournalError(
                    "live_transport_call_count_invalid",
                    f"{attempt_id}:{len(attempts)}",
                )
        for raw_ref in self._raw_evidence.values():
            raw_event = resolve_journal_event_ref(raw_ref)
            raw_payload = raw_event.get("raw_response")
            if (
                isinstance(raw_payload, Mapping)
                and raw_payload.get("transport_event_sha256") is not None
            ):
                resolve_live_transport_trace(raw_ref)

    def _validate_reopened_request(
        self,
        event_ref: JournalEventRef,
        event: Mapping[str, Any],
    ) -> None:
        attempt_id = str(event["attempt_id"])
        request = event.get("request")
        if (
            set(event) != {"sequence", "event_kind", "attempt_id", "request", "request_sha256"}
            or self._requests.get(attempt_id) != event_ref
            or not isinstance(request, Mapping)
            or event.get("request_sha256") != content_sha256(request)
        ):
            raise EvidenceJournalError("request_evidence_ref_invalid", attempt_id)
        variable = request.get("variable_id")
        variables = request.get("request_variables")
        one_variable = isinstance(variable, str) and bool(variable.strip())
        if isinstance(variables, Sequence) and not isinstance(
            variables,
            (str, bytes, bytearray),
        ):
            one_variable = len(variables) == 1 and bool(str(variables[0]).strip())
        schema_contract = request.get("schema_contract")
        if not one_variable or not isinstance(schema_contract, Mapping) or not schema_contract:
            raise EvidenceJournalError("journal_request_contract_invalid", attempt_id)

    def _validate_reopened_transport(
        self,
        event_ref: JournalEventRef,
        event: Mapping[str, Any],
    ) -> None:
        attempt_id = str(event["attempt_id"])
        transport = event.get("transport_attempt")
        request_ref = self._requests[attempt_id]
        terminal_ref = self._terminals[attempt_id]
        if (
            set(event) != {"sequence", "event_kind", "attempt_id", "transport_attempt"}
            or not isinstance(transport, Mapping)
            or set(transport)
            != {
                "request_event_sha256",
                "connector_id",
                "url",
                "params",
                "params_sha256",
            }
            or transport.get("request_event_sha256") != request_ref.event_sha256
            or not isinstance(transport.get("connector_id"), str)
            or not str(transport["connector_id"]).strip()
            or not isinstance(transport.get("url"), str)
            or not str(transport["url"]).strip()
            or not isinstance(transport.get("params"), Mapping)
            or transport.get("params_sha256") != content_sha256(transport["params"])
            or not request_ref.sequence < event_ref.sequence < terminal_ref.sequence
        ):
            raise EvidenceJournalError("transport_evidence_ref_invalid", attempt_id)
        self._transport_attempts.setdefault(attempt_id, []).append(event_ref)

    def _validate_reopened_heartbeat(
        self,
        event_ref: JournalEventRef,
        event: Mapping[str, Any],
    ) -> None:
        attempt_id = str(event["attempt_id"])
        heartbeat = event.get("heartbeat")
        request_ref = self._requests[attempt_id]
        terminal_ref = self._terminals[attempt_id]
        raw_ref = self._raw_evidence.get(attempt_id)
        if (
            set(event) != {"sequence", "event_kind", "attempt_id", "heartbeat"}
            or not isinstance(heartbeat, Mapping)
            or set(heartbeat) != {"phase", "progress_bytes", "elapsed_seconds"}
            or heartbeat.get("phase") not in _HEARTBEAT_PHASES
            or not isinstance(heartbeat.get("progress_bytes"), int)
            or isinstance(heartbeat.get("progress_bytes"), bool)
            or int(heartbeat["progress_bytes"]) < 0
            or not isinstance(heartbeat.get("elapsed_seconds"), (int, float))
            or isinstance(heartbeat.get("elapsed_seconds"), bool)
            or float(heartbeat["elapsed_seconds"]) < 0
            or not request_ref.sequence < event_ref.sequence < terminal_ref.sequence
            or (raw_ref is not None and event_ref.sequence >= raw_ref.sequence)
        ):
            raise EvidenceJournalError("heartbeat_evidence_invalid", attempt_id)
        progress = int(heartbeat["progress_bytes"])
        elapsed = float(heartbeat["elapsed_seconds"])
        previous_progress, previous_elapsed = self._heartbeat_state.get(
            attempt_id,
            (0, 0.0),
        )
        if progress < previous_progress or elapsed < previous_elapsed:
            raise EvidenceJournalError("heartbeat_evidence_invalid", attempt_id)
        self._heartbeat_state[attempt_id] = (progress, elapsed)

    def _validate_reopened_classification(
        self,
        event_ref: JournalEventRef,
        event: Mapping[str, Any],
    ) -> None:
        attempt_id = str(event["attempt_id"])
        raw_ref = self._raw_evidence.get(attempt_id)
        terminal_ref = self._terminals[attempt_id]
        if (
            set(event)
            != {
                "sequence",
                "event_kind",
                "attempt_id",
                "evidence_event_sha256",
                "classification",
            }
            or raw_ref is None
            or event.get("evidence_event_sha256") != raw_ref.event_sha256
            or not isinstance(event.get("classification"), Mapping)
            or not raw_ref.sequence < event_ref.sequence < terminal_ref.sequence
        ):
            raise EvidenceJournalError("classification_evidence_invalid", attempt_id)

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
        if isinstance(variables, Sequence) and not isinstance(variables, (str, bytes, bytearray)):
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

    def append_transport_attempt(
        self,
        *,
        attempt_id: str,
        request_ref: JournalEventRef,
        connector_id: str,
        url: str,
        params: Mapping[str, object],
    ) -> JournalEventRef:
        """Persist each actual HTTP attempt, including retries, before transport."""

        if attempt_id in self._terminals:
            raise EvidenceJournalError("attempt_already_terminal", attempt_id)
        expected_request = self._requests.get(attempt_id)
        if expected_request != request_ref or not verify_journal_event_ref(request_ref):
            raise EvidenceJournalError("request_evidence_ref_invalid", attempt_id)
        if not connector_id.strip():
            raise EvidenceJournalError("transport_connector_missing", attempt_id)
        if not url.strip():
            raise EvidenceJournalError("transport_url_missing", attempt_id)
        try:
            params_sha = content_sha256(params)
        except (TypeError, ValueError) as exc:
            raise EvidenceJournalError("transport_params_invalid", attempt_id) from exc
        ref = self._append(
            "transport_attempt",
            {
                "attempt_id": attempt_id,
                "transport_attempt": {
                    "request_event_sha256": request_ref.event_sha256,
                    "connector_id": connector_id,
                    "url": url,
                    "params": dict(params),
                    "params_sha256": params_sha,
                },
            },
        )
        self._transport_attempts.setdefault(attempt_id, []).append(ref)
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

        if attempt_id in self._terminals:
            raise EvidenceJournalError("attempt_already_terminal", attempt_id)
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
        transport_ref: JournalEventRef | None = None,
        payload: bytes,
        status_code: int | None,
        response_headers: Mapping[str, str],
        budget: LiveHttpBudget,
    ) -> JournalEventRef:
        """Persist bounded response bytes before any classification consumes them."""

        if attempt_id in self._terminals:
            raise EvidenceJournalError("attempt_already_terminal", attempt_id)
        expected_request = self._requests.get(attempt_id)
        if expected_request != request_ref or not verify_journal_event_ref(request_ref):
            raise EvidenceJournalError("request_evidence_ref_invalid", attempt_id)
        if attempt_id in self._raw_evidence:
            raise EvidenceJournalError("duplicate_raw_evidence", attempt_id)
        if len(payload) > budget.max_response_bytes or len(payload) > budget.max_decompressed_bytes:
            raise EvidenceJournalError("response_budget_exceeded", attempt_id)
        if status_code is not None and not 100 <= status_code <= 599:
            raise EvidenceJournalError("response_status_invalid", str(status_code))
        if transport_ref is not None:
            attempts = self._transport_attempts.get(attempt_id, [])
            if transport_ref not in attempts or not verify_journal_event_ref(transport_ref):
                raise EvidenceJournalError("transport_evidence_ref_invalid", attempt_id)
            transport_event = resolve_journal_event_ref(transport_ref)
            transport = transport_event.get("transport_attempt")
            if (
                not isinstance(transport, Mapping)
                or transport.get("request_event_sha256") != request_ref.event_sha256
            ):
                raise EvidenceJournalError("transport_evidence_ref_invalid", attempt_id)
        raw_response: dict[str, object] = {
            "request_event_sha256": request_ref.event_sha256,
            "status_code": status_code,
            "response_headers": dict(sorted(response_headers.items())),
            "bounded_body_base64": base64.b64encode(payload).decode("ascii"),
            "body_sha256": f"sha256:{hashlib.sha256(payload).hexdigest()}",
            "bytes_read": len(payload),
        }
        if transport_ref is not None:
            raw_response["transport_event_sha256"] = transport_ref.event_sha256
        ref = self._append(
            "raw_response",
            {
                "attempt_id": attempt_id,
                "raw_response": raw_response,
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

        if attempt_id in self._terminals:
            raise EvidenceJournalError("attempt_already_terminal", attempt_id)
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

    def append_failure_terminal(
        self,
        *,
        attempt_id: str,
        request_ref: JournalEventRef,
        failure_code: str,
        raw_evidence_ref: JournalEventRef | None = None,
    ) -> JournalEventRef:
        """Close one failed live attempt with an evidence-derived quarantine terminal.

        The caller supplies only the observed failure code. The owner derives the
        outcome from that syntax-safe code and, when present, the exact journaled
        HTTP status. Any response already persisted for the attempt must travel
        with the terminal; response bytes can never be classified by omission.
        """

        if attempt_id in self._terminals:
            raise EvidenceJournalError("duplicate_live_attempt_terminal", attempt_id)
        expected_request = self._requests.get(attempt_id)
        if expected_request != request_ref or not verify_journal_event_ref(request_ref):
            raise EvidenceJournalError("live_terminal_request_link_invalid", attempt_id)
        request_event = resolve_journal_event_ref(request_ref)
        request_payload = request_event.get("request")
        if (
            request_event.get("attempt_id") != attempt_id
            or not isinstance(request_payload, Mapping)
            or request_event.get("request_sha256") != content_sha256(request_payload)
        ):
            raise EvidenceJournalError("live_terminal_request_link_invalid", attempt_id)
        if (
            not isinstance(failure_code, str)
            or len(failure_code) > 120
            or _SAFE_TERMINAL_CODE.fullmatch(failure_code) is None
        ):
            raise EvidenceJournalError("live_terminal_failure_code_invalid", attempt_id)

        expected_raw = self._raw_evidence.get(attempt_id)
        http_status_code: int | None = None
        if expected_raw is not None:
            if raw_evidence_ref is None:
                raise EvidenceJournalError("live_terminal_raw_link_required", attempt_id)
            if expected_raw != raw_evidence_ref or not verify_journal_event_ref(raw_evidence_ref):
                raise EvidenceJournalError("live_terminal_raw_link_invalid", attempt_id)
            raw_event = resolve_journal_event_ref(raw_evidence_ref)
            raw_payload = raw_event.get("raw_response")
            if (
                raw_event.get("attempt_id") != attempt_id
                or not isinstance(raw_payload, Mapping)
                or raw_payload.get("request_event_sha256") != request_ref.event_sha256
            ):
                raise EvidenceJournalError("live_terminal_raw_link_invalid", attempt_id)
            resolve_raw_response_body(raw_evidence_ref)
            status = raw_payload.get("status_code")
            if status is not None and (
                not isinstance(status, int) or isinstance(status, bool) or not 100 <= status <= 599
            ):
                raise EvidenceJournalError("live_terminal_raw_link_invalid", attempt_id)
            http_status_code = status
        elif raw_evidence_ref is not None:
            raise EvidenceJournalError("live_terminal_raw_link_invalid", attempt_id)

        outcome_code = _derive_live_attempt_outcome(
            failure_code=failure_code,
            http_status_code=http_status_code,
            raw_response_present=raw_evidence_ref is not None,
        )
        terminal_sha = _live_attempt_terminal_sha256(
            attempt_id=attempt_id,
            request_ref=request_ref,
            raw_evidence_ref=raw_evidence_ref,
            failure_code=failure_code,
            outcome_code=outcome_code,
            http_status_code=http_status_code,
        )
        LiveAttemptTerminal(
            attempt_id=attempt_id,
            outcome_code=outcome_code,
            failure_code=failure_code,
            request_ref=request_ref,
            raw_evidence_ref=raw_evidence_ref,
            http_status_code=http_status_code,
            quarantine=True,
            response_admitted=False,
            terminal_sha256=terminal_sha,
        )
        ref = self._append(
            "live_attempt_terminal",
            {
                "schema_version": "polisyos.fabric.live_attempt_terminal.v1",
                "attempt_id": attempt_id,
                "request_event_sha256": request_ref.event_sha256,
                "raw_evidence_event_sha256": (
                    raw_evidence_ref.event_sha256 if raw_evidence_ref is not None else None
                ),
                "failure_code": failure_code,
                "outcome_code": outcome_code,
                "http_status_code": http_status_code,
                "quarantine": True,
                "response_admitted": False,
                "terminal_sha256": terminal_sha,
            },
        )
        self._terminals[attempt_id] = ref
        resolve_live_attempt_terminal(ref)
        return ref


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
    "LiveAttemptTerminal",
    "LiveExecutionAuthorization",
    "LiveHttpBudget",
    "LiveTransportTrace",
    "append_fsync_jsonl",
    "build_live_execution_authorization",
    "canonical_json_bytes",
    "content_sha256",
    "derive_harness_authorization_evidence",
    "derive_live_http_budget",
    "require_authorized_execution",
    "resolve_journal_event_ref",
    "resolve_linked_request_event",
    "resolve_live_attempt_terminal",
    "resolve_live_attempt_terminals",
    "resolve_live_transport_trace",
    "resolve_raw_response_body",
    "verify_journal_event_ref",
]
