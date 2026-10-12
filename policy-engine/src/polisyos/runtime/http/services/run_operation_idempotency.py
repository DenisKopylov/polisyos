"""Purpose-scoped durable ownership for retryable Runtime operations.

This module defines the internal identity and state contract shared by
purpose-specific Runtime operation owners. It records local database intent
and recovery state; it does not claim external exactly-once execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PURPOSE_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,119}$")
_INTENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")

RuntimeOperationIntentScope = Literal["run", "route"]
RuntimeOperationIntentStatus = Literal[
    "unknown",
    "pending",
    "completed",
    "refused",
    "recovery_required",
]
RuntimeOperationIntentDisposition = Literal[
    "owner",
    "body_conflict",
    "pending",
    "completed",
    "refused",
    "recovery_required",
]


class RuntimeOperationIntentStore(Protocol):
    """Purpose-neutral store seam implemented by the control-plane SQL owner."""

    def begin_runtime_operation_intent(
        self,
        key: RuntimeOperationIntentKey,
    ) -> RuntimeOperationIntentClaim:
        """Atomically create pending ownership or observe existing state."""

    def get_runtime_operation_intent(
        self,
        key: RuntimeOperationIntentKey,
    ) -> RuntimeOperationIntentSnapshot:
        """Read exact scoped intent state."""

    def complete_runtime_operation_intent(
        self,
        *,
        key: RuntimeOperationIntentKey,
        owner_token: str,
        result_ref_json: str,
        event_id: str,
        publish: Callable[[], object],
    ) -> RuntimeOperationIntentRecord:
        """Atomically publish the durable result and complete the owner row."""

    def complete_runtime_operation_intent_with_observation(
        self,
        *,
        key: RuntimeOperationIntentKey,
        owner_token: str,
        result_ref_json: str,
        event_id: str,
    ) -> RuntimeOperationIntentRecord:
        """Complete after a purpose-specific durable event is committed atomically."""

    def refuse_runtime_operation_intent(
        self,
        *,
        key: RuntimeOperationIntentKey,
        owner_token: str,
        reason_code: str,
    ) -> RuntimeOperationIntentRecord:
        """Record a pre-side-effect owner refusal."""

    def require_runtime_operation_recovery(
        self,
        *,
        key: RuntimeOperationIntentKey,
        owner_token: str,
        reason_code: str,
    ) -> RuntimeOperationIntentRecord:
        """Record an ambiguous partial attempt for reconciliation."""


@dataclass(frozen=True, slots=True)
class RuntimeOperationIntentKey:
    """Server-bound identity and exact request digest for one purpose-scoped intent.

    The database unique key deliberately excludes body_sha256. Reusing an
    intent with a different request body is a conflict, not a second operation.
    """

    purpose: str
    tenant_id: str
    cell_id: str
    actor_subject_sha256: str
    run_id: str
    intent_id: str
    body_sha256: str
    scope_kind: RuntimeOperationIntentScope = "run"
    scope_id: str | None = None

    def __post_init__(self) -> None:
        """Validate every identity component before it reaches SQL."""
        if not isinstance(self.purpose, str) or not _PURPOSE_RE.fullmatch(self.purpose):
            raise ValueError("purpose must be a versioned purpose token")
        for field_name in ("tenant_id", "cell_id", "run_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"{field_name} must be a non-empty trimmed identifier")
        if self.scope_kind not in {"run", "route"}:
            raise ValueError("scope_kind must be run or route")
        if self.scope_id is None and self.scope_kind == "run":
            object.__setattr__(self, "scope_id", self.run_id)
        if (
            not isinstance(self.scope_id, str)
            or not self.scope_id
            or self.scope_id != self.scope_id.strip()
        ):
            raise ValueError("scope_id must be a non-empty trimmed identifier")
        if self.scope_kind == "run" and self.scope_id != self.run_id:
            raise ValueError("run scope_id must equal the actual run_id")
        if not isinstance(self.intent_id, str) or not _INTENT_RE.fullmatch(self.intent_id):
            raise ValueError("intent_id must be a bounded idempotency token")
        for field_name in ("actor_subject_sha256", "body_sha256"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")

    @property
    def identity(self) -> tuple[str, str, str, str, str, str]:
        """Return the historical run-scoped identity shape for compatibility."""
        return (
            self.purpose,
            self.tenant_id,
            self.cell_id,
            self.actor_subject_sha256,
            self.run_id,
            self.intent_id,
        )

    @property
    def scope_identity(self) -> tuple[str, str, str, str, str, str, str]:
        """Return the unique purpose and route-or-run scope, excluding body bytes."""
        return (
            self.purpose,
            self.tenant_id,
            self.cell_id,
            self.actor_subject_sha256,
            self.scope_kind,
            str(self.scope_id),
            self.intent_id,
        )


@dataclass(frozen=True, slots=True)
class RuntimeOperationIntentRecord:
    """Durable state read back from the operation-intent table."""

    purpose: str
    tenant_id: str
    cell_id: str
    actor_subject_sha256: str
    run_id: str
    intent_id: str
    body_sha256: str
    status: RuntimeOperationIntentStatus
    result_ref_json: str | None
    event_id: str | None
    reason_code: str | None
    created_at: str
    updated_at: str
    scope_kind: RuntimeOperationIntentScope = "run"
    scope_id: str | None = None

    def __post_init__(self) -> None:
        """Reject contradictory or malformed rows instead of projecting valid state."""
        key = RuntimeOperationIntentKey(
            purpose=self.purpose,
            tenant_id=self.tenant_id,
            cell_id=self.cell_id,
            actor_subject_sha256=self.actor_subject_sha256,
            run_id=self.run_id,
            intent_id=self.intent_id,
            body_sha256=self.body_sha256,
            scope_kind=self.scope_kind,
            scope_id=self.scope_id,
        )
        if self.scope_id is None:
            object.__setattr__(self, "scope_id", key.scope_id)
        if not isinstance(self.created_at, str) or not self.created_at:
            raise ValueError("created_at is required")
        if not isinstance(self.updated_at, str) or not self.updated_at:
            raise ValueError("updated_at is required")
        if self.status == "completed":
            if not self.result_ref_json or not self.event_id or self.reason_code is not None:
                raise ValueError("completed operation intent requires a result and event only")
        elif self.status in {"refused", "recovery_required"}:
            if (
                not self.reason_code
                or self.result_ref_json is not None
                or self.event_id is not None
            ):
                raise ValueError("terminal non-completed intent requires a reason code only")
        elif self.status == "pending":
            if (
                self.result_ref_json is not None
                or self.event_id is not None
                or self.reason_code is not None
            ):
                raise ValueError("pending operation intent cannot contain a result or reason")
        else:
            raise ValueError("unknown operation intent cannot be persisted as a record")


@dataclass(frozen=True, slots=True)
class RuntimeOperationIntentClaim:
    """Result of atomically claiming or observing one durable operation intent."""

    disposition: RuntimeOperationIntentDisposition
    record: RuntimeOperationIntentRecord
    owner_token: str | None = None

    def __post_init__(self) -> None:
        """Keep dispositions consistent and ownership credentials private."""
        if self.disposition == "owner":
            if not self.owner_token or self.record.status != "pending":
                raise ValueError("an owner claim requires a pending row and private token")
            return
        if self.owner_token is not None:
            raise ValueError("an observed operation intent cannot expose its owner token")
        if self.disposition == "body_conflict":
            return
        if self.disposition not in {"pending", "completed", "refused", "recovery_required"}:
            raise ValueError("operation intent claim has an unknown disposition")
        if self.record.status != self.disposition:
            raise ValueError("observed disposition must match the stored operation state")


@dataclass(frozen=True, slots=True)
class RuntimeOperationIntentSnapshot:
    """Read-only lookup result; an absent row is explicit unknown."""

    status: RuntimeOperationIntentStatus
    record: RuntimeOperationIntentRecord | None

    def __post_init__(self) -> None:
        """Keep unknown state equivalent to absence, never a fabricated row."""
        if self.status == "unknown" and self.record is not None:
            raise ValueError("unknown operation intent cannot carry a stored record")
        if self.status != "unknown" and (
            self.record is None or self.record.status != self.status
        ):
            raise ValueError("stored operation state must match its record")
