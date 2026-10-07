"""File-backed budget ledger for distributed-safe Scientist budget accounting."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from polisyos.scientist.orchestration.engine.budget import BudgetState

_CANONICAL_LEDGER_CONTRACT = "scientist.multi_host_budget_ledger.v1"
_COORDINATION_MODE = "shared_posix_file_lock"
_SNAPSHOT_VERSION = "1.2"

__all__ = [
    "BudgetLedger",
    "BudgetLedgerMutation",
    "BudgetLedgerMutationResult",
    "BudgetLedgerSnapshot",
    "BudgetLedgerWriter",
    "BudgetLedgerSpendReceipt",
    "BudgetLedgerSettlementOutcomeUnknownError",
    "BudgetLedgerCompletionObligation",
    "BudgetLedgerCompletionResolution",
    "BudgetLedgerCompletionResolver",
    "BudgetLedgerCompletionRequiredError",
    "BudgetLedgerCompletionOutcomeUnknownError",
    "FileBudgetLedger",
]


class BudgetLedgerWriter(BaseModel):
    """Identity of the process or host that last mutated the ledger."""

    model_config = ConfigDict(extra="forbid")

    host_id: str = Field(min_length=1)
    writer_id: str = Field(min_length=1)
    pid: int = Field(ge=0)


class BudgetLedgerMutation(BaseModel):
    """Bounded mutation journal entry for the canonical ledger contract."""

    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    operation: Literal[
        "bootstrap",
        "record_spend",
        "reserve",
        "release",
        "commit_reservation",
        "settle_spend",
        "retain_completion",
        "transition_completion",
        "complete_completion",
        "admit_provider_intent",
        "abort_provider_intent",
    ]
    key: str | None = None
    amount: Decimal | None = None
    applied_amount: Decimal | None = None
    provider: str | None = None
    reserved: bool | None = None
    writer: BudgetLedgerWriter
    committed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BudgetLedgerSpendReceipt(BaseModel):
    """Durable local accounting acknowledgment for one producer settlement event.

    This binds an observed producer payload to one local charge. It does not
    certify external billing authority or supply permission to run new work.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    key: str = Field(min_length=1)
    amount: Decimal = Field(ge=0, allow_inf_nan=False)
    provider: str | None = None
    revision: int = Field(ge=1)
    committed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BudgetLedgerSettlementOutcomeUnknownError(RuntimeError):
    """A filesystem publication failed without establishing charge acknowledgment."""

    def __init__(self, event_id: str, payload_digest: str) -> None:
        self.event_id = event_id
        self.payload_digest = payload_digest
        super().__init__(
            f"budget settlement outcome unknown for event {event_id!r}; "
            "resolve or retry the same event before assuming any charge outcome"
        )


class BudgetLedgerCompletionObligation(BaseModel):
    """Retained completion work, distinct from a known monetary acknowledgment.

    Event and required-action payloads belong to the configured producer/audit
    owner. The ledger preserves their exact JSON content; it does not certify
    provider billing or invent a protected-audit authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str = Field(min_length=1)
    event_payload: dict[str, JsonValue]
    event_digest: str = Field(pattern=r"^(sha256:)?[a-f0-9]{64}$")
    run_id: str = Field(min_length=1)
    owner_epoch: str = Field(min_length=1)
    budget_keys: tuple[str, ...]
    reserved_amounts: dict[str, Decimal]
    phase: Literal[
        "provider_in_flight", "cost_unknown", "ledger_ack_unknown", "protected_audit_pending"
    ]
    known_receipt_ids: tuple[str, ...] = ()
    required_action: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def _validate_completion(self) -> BudgetLedgerCompletionObligation:
        if (
            not self.budget_keys
            or any(not key for key in self.budget_keys)
            or len(set(self.budget_keys)) != len(self.budget_keys)
            or set(self.reserved_amounts) != set(self.budget_keys)
        ):
            raise ValueError("completion requires unique keys and exact reservation coordinates")
        if any(not amount.is_finite() or amount < 0 for amount in self.reserved_amounts.values()):
            raise ValueError("completion reservations must be finite and nonnegative")
        if (
            not isinstance(self.event_payload.get("event_id"), str)
            or not self.event_payload["event_id"]
        ):
            raise ValueError("completion requires its original event identity")
        if len(set(self.known_receipt_ids)) != len(self.known_receipt_ids):
            raise ValueError("completion receipt IDs must be unique")
        kind = self.event_payload.get("kind")
        amount = self.event_payload.get("amount")
        if "amount" not in self.event_payload:
            raise ValueError("completion requires an explicit known or unknown amount")
        if kind not in ("provider_intent", "provider", "budget_audit", "reuse"):
            raise ValueError("completion requires a provider or protected budget-audit event")
        if kind == "provider_intent":
            if self.phase != "provider_in_flight" or amount is not None or self.known_receipt_ids:
                raise ValueError("provider intent cannot assert completion or a charge")
            if (
                not isinstance(self.event_payload.get("request_digest"), str)
                or not self.event_payload["request_digest"]
            ):
                raise ValueError("provider intent requires its exact owned request binding")
        elif self.phase == "provider_in_flight":
            raise ValueError("in-flight phase requires an actual request intent")
        elif kind == "budget_audit":
            if (
                self.phase != "protected_audit_pending"
                or amount is not None
                or self.known_receipt_ids
                or self.required_action is None
            ):
                raise ValueError("budget-audit completion cannot fabricate a provider charge")
        elif kind == "reuse":
            try:
                known_zero = (
                    isinstance(amount, str) and Decimal(amount).is_finite() and Decimal(amount) == 0
                )
            except InvalidOperation as exc:
                raise ValueError("reuse completion requires a known decimal zero") from exc
            if (
                self.phase not in {"ledger_ack_unknown", "protected_audit_pending"}
                or not known_zero
                or self.known_receipt_ids
            ):
                raise ValueError("reuse audit cannot issue a new provider charge acknowledgment")
        elif self.phase == "cost_unknown":
            if amount is not None or self.known_receipt_ids:
                raise ValueError("unknown cost cannot carry a known amount or spend receipt")
        else:
            if not isinstance(amount, str):
                raise ValueError("known provider completion requires an explicit decimal amount")
            try:
                parsed = Decimal(amount)
            except InvalidOperation as exc:
                raise ValueError("known completion requires a decimal amount") from exc
            if not parsed.is_finite() or parsed < 0:
                raise ValueError("known completion amount must be finite and nonnegative")
        if self.phase == "protected_audit_pending" and self.required_action is None:
            raise ValueError("protected audit completion requires its exact action payload")
        # Reject JSON nonfinite values instead of allowing a noncanonical digest.
        json.dumps(self.event_payload, allow_nan=False)
        json.dumps(self.required_action, allow_nan=False)
        body_digest = hashlib.sha256(
            json.dumps(
                self.event_payload, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        if self.event_digest.removeprefix("sha256:") != body_digest:
            raise ValueError("completion event digest does not bind its actual retained body")
        return self

    @property
    def payload_digest(self) -> str:
        """Bind the whole retained record, including phase and required action."""
        payload = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class BudgetLedgerCompletionResolution(BaseModel):
    """Exact proof returned by the constructor-bound completion resolver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    record_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    phase: Literal["provider_in_flight", "ledger_ack_unknown", "protected_audit_pending"]
    known_receipt_ids: tuple[str, ...]
    owner_resolution_ref: str | None = None
    status: Literal["resolved", "not_admitted"] = "resolved"


class BudgetLedgerCompletionResolver(Protocol):
    """Configured owner verifier; resolve must not mutate or reenter the ledger."""

    def resolve(
        self,
        obligation: BudgetLedgerCompletionObligation,
        owner_resolution_ref: str | None,
    ) -> BudgetLedgerCompletionResolution: ...


class BudgetLedgerCompletionRequiredError(RuntimeError):
    """An intersecting completion obligation prevents admission of new work."""

    def __init__(self, obligations: tuple[BudgetLedgerCompletionObligation, ...]) -> None:
        self.obligations = obligations
        super().__init__(
            "budget completion requires reconciliation before new work: "
            + ", ".join(record.obligation_id for record in obligations)
        )


class BudgetLedgerCompletionOutcomeUnknownError(RuntimeError):
    """Completion publication/ACK failed; reopen before deciding its outcome."""

    def __init__(self, obligation_id: str, record_digest: str) -> None:
        self.obligation_id = obligation_id
        self.record_digest = record_digest
        super().__init__(f"budget completion publication outcome unknown for {obligation_id!r}")


@dataclass
class _CompletionRuntimeOwner:
    """One live owner shared across views, including failed-publication custody."""

    uncertain: dict[str, BudgetLedgerCompletionObligation] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


class BudgetLedgerSnapshot(BaseModel):
    """Persisted budget ledger state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=_SNAPSHOT_VERSION, pattern=r"^\d+\.\d+$")
    canonical_contract: str = Field(default=_CANONICAL_LEDGER_CONTRACT, min_length=1)
    coordination_mode: str = Field(default=_COORDINATION_MODE, min_length=1)
    ledger_id: str | None = None
    revision: int = Field(default=0, ge=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_writer: BudgetLedgerWriter | None = None
    recent_mutations: list[BudgetLedgerMutation] = Field(default_factory=list)
    state: BudgetState = Field(default_factory=BudgetState)
    spend_receipts: dict[str, BudgetLedgerSpendReceipt] = Field(
        default_factory=dict, json_schema_extra={"introduced_in": "1.1"}
    )
    completion_obligations: dict[str, BudgetLedgerCompletionObligation] = Field(
        default_factory=dict, json_schema_extra={"introduced_in": "1.2"}
    )


_PERSISTED_SNAPSHOT_SCHEMA = BudgetLedgerSnapshot.model_json_schema(mode="serialization")


def _require_wire_fields(
    value: object,
    schema: dict[str, Any],
    definitions: dict[str, Any],
    *,
    location: str = "snapshot",
    version: str = _SNAPSHOT_VERSION,
) -> None:
    """Require non-nullable writer fields before constructor defaults can apply."""
    if "$ref" in schema:
        schema = definitions[schema["$ref"].rsplit("/", 1)[1]]
    alternatives = schema.get("anyOf", [])
    if alternatives:
        schema = next((item for item in alternatives if item.get("type") != "null"), schema)
        if "$ref" in schema:
            schema = definitions[schema["$ref"].rsplit("/", 1)[1]]
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name, field_schema in properties.items():
            nullable = any(item.get("type") == "null" for item in field_schema.get("anyOf", []))
            introduced = field_schema.get("introduced_in", "1.0")
            required_in_version = tuple(map(int, introduced.split("."))) <= tuple(
                map(int, version.split("."))
            )
            if name in value and not required_in_version:
                raise ValueError(
                    f"unsupported budget ledger field for {version}: {location}.{name}"
                )
            if name not in value and not nullable and required_in_version:
                raise ValueError(f"incomplete budget ledger: missing {location}.{name}")
        for name, item in value.items():
            field_schema = properties.get(name, schema.get("additionalProperties", {}))
            if isinstance(field_schema, dict):
                _require_wire_fields(
                    item, field_schema, definitions, location=f"{location}.{name}", version=version
                )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _require_wire_fields(
                item,
                schema.get("items", {}),
                definitions,
                location=f"{location}[{index}]",
                version=version,
            )


def _require_nonnegative_amounts(value: object) -> None:
    """Reject nonfinite or negative accounting amounts in a persisted snapshot."""
    if isinstance(value, Decimal):
        if not value.is_finite() or value < 0:
            raise ValueError("budget ledger accounting amounts must be finite and nonnegative")
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            _require_nonnegative_amounts(getattr(value, name))
    elif isinstance(value, dict):
        for item in value.values():
            _require_nonnegative_amounts(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _require_nonnegative_amounts(item)


def _decode_snapshot(raw: str) -> BudgetLedgerSnapshot:
    """Decode complete persisted wire data without treating corruption as defaults."""
    if not raw.strip():
        raise ValueError("existing budget ledger is empty")
    value = json.loads(raw)
    version = value.get("schema_version") if isinstance(value, dict) else None
    if not isinstance(version, str) or version not in {"1.0", "1.1", _SNAPSHOT_VERSION}:
        raise ValueError("budget ledger schema_version is missing or unsupported")
    if (
        value.get("canonical_contract") != _CANONICAL_LEDGER_CONTRACT
        or value.get("coordination_mode") != _COORDINATION_MODE
    ):
        raise ValueError("budget ledger contract or coordination mode is unsupported")
    _require_wire_fields(
        value,
        _PERSISTED_SNAPSHOT_SCHEMA,
        _PERSISTED_SNAPSHOT_SCHEMA.get("$defs", {}),
        version=version,
    )
    snapshot = BudgetLedgerSnapshot.model_validate_json(raw, strict=True)
    _require_nonnegative_amounts(snapshot)
    if version != "1.2" and any(
        entry.operation
        in {
            "retain_completion",
            "transition_completion",
            "complete_completion",
            "admit_provider_intent",
            "abort_provider_intent",
        }
        for entry in snapshot.recent_mutations
    ):
        raise ValueError("legacy budget wire cannot contain completion-protocol mutations")
    amounts: dict[str, Decimal] = {}
    provider_amounts: dict[str, Decimal] = {}
    for event_id, receipt in snapshot.spend_receipts.items():
        if receipt.event_id != event_id or receipt.revision > snapshot.revision:
            raise ValueError("budget settlement receipt identity/revision disagrees with snapshot")
        amounts[receipt.key] = amounts.get(receipt.key, Decimal("0")) + receipt.amount
        if receipt.provider is not None:
            provider_amounts[receipt.provider] = (
                provider_amounts.get(receipt.provider, Decimal("0")) + receipt.amount
            )
    for key, amount in amounts.items():
        if snapshot.state.spent.get(key, Decimal("0")) < amount:
            raise ValueError("budget settlement receipts exceed the recorded spend")
    for provider, amount in provider_amounts.items():
        if snapshot.state.provider_spent.get(provider, Decimal("0")) < amount:
            raise ValueError("budget settlement receipts exceed the recorded provider spend")
    for obligation_id, record in snapshot.completion_obligations.items():
        if record.obligation_id != obligation_id:
            raise ValueError("completion index identity disagrees with retained record")
        _validate_completion_receipts(snapshot, record, complete=False)
    return snapshot


def _validate_completion_receipts(
    snapshot: BudgetLedgerSnapshot,
    record: BudgetLedgerCompletionObligation,
    *,
    complete: bool,
) -> None:
    """Resolve actual known charge coordinates, never an asserted ACK marker."""
    if record.event_payload.get("kind") in {"budget_audit", "reuse"}:
        return
    if record.phase in {"provider_in_flight", "cost_unknown"}:
        if complete:
            raise ValueError("unknown provider cost cannot be completed without its cost owner")
        return
    keys: set[str] = set()
    for receipt_id in record.known_receipt_ids:
        receipt = snapshot.spend_receipts.get(receipt_id)
        if receipt is None:
            raise ValueError("completion references a missing known spend receipt")
        if (
            receipt.key not in record.budget_keys
            or receipt.key in keys
            or receipt.event_id
            != (
                f"{record.event_payload['event_id']}:budget:"
                + hashlib.sha256(receipt.key.encode()).hexdigest()
            )
            or receipt.payload_digest
            != hashlib.sha256(f"{record.event_digest}:{receipt.key}".encode()).hexdigest()
            or receipt.amount != Decimal(str(record.event_payload["amount"]))
            or receipt.provider != record.event_payload.get("provider")
        ):
            raise ValueError("completion receipt charge coordinates disagree with the event")
        keys.add(receipt.key)
    if complete and keys != set(record.budget_keys):
        raise ValueError("provider completion requires actual receipts for every budget key")


@dataclass(frozen=True)
class BudgetLedgerMutationResult:
    """Result of a ledger mutation."""

    state: BudgetState
    revision: int
    applied_amount: Decimal = Decimal("0")
    reserved: bool | None = None


class BudgetLedger(Protocol):
    """Protocol for distributed-safe budget ledgers."""

    @property
    def settlement_owner_identity(self) -> tuple[str, str, str]: ...
    @property
    def completion_owner_epoch(self) -> str: ...

    def load(self) -> BudgetState: ...
    def snapshot(self) -> BudgetLedgerSnapshot: ...
    def load_or_bootstrap(self, initial_state: BudgetState) -> BudgetState: ...
    def record_spend(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> BudgetLedgerMutationResult: ...
    def reserve(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult: ...
    def release(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult: ...
    def commit_reservation(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> BudgetLedgerMutationResult: ...
    def settle_spend(
        self,
        event_id: str,
        key: str,
        amount: Decimal,
        *,
        payload_digest: str,
        provider: str | None = None,
    ) -> BudgetLedgerSpendReceipt: ...
    def resolve_spend(self, event_id: str) -> BudgetLedgerSpendReceipt | None: ...
    def load_for_admission(self, budget_keys: tuple[str, ...]) -> BudgetState: ...
    def with_completion_resolver(
        self, resolver: BudgetLedgerCompletionResolver
    ) -> BudgetLedger: ...
    def retain_completion_obligation(
        self, record: BudgetLedgerCompletionObligation
    ) -> BudgetLedgerCompletionObligation: ...
    def admit_provider_intent(self, record: BudgetLedgerCompletionObligation) -> bool: ...
    def abort_provider_intent(self, obligation_id: str, expected_digest: str) -> bool: ...
    def list_completion_obligations(
        self, budget_keys: tuple[str, ...]
    ) -> tuple[BudgetLedgerCompletionObligation, ...]: ...
    def transition_completion_obligation(
        self, record: BudgetLedgerCompletionObligation, expected_digest: str
    ) -> BudgetLedgerCompletionObligation: ...
    def complete_completion_obligation(
        self,
        obligation_id: str,
        expected_digest: str,
        known_receipt_ids: tuple[str, ...],
        owner_resolution_ref: str | None,
    ) -> bool: ...


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class FileBudgetLedger:
    """Atomic JSON budget ledger shared across threads/processes."""

    def __init__(
        self,
        path: Path,
        *,
        ledger_id: str | None = None,
        host_id: str | None = None,
        writer_id: str | None = None,
        mutation_history_limit: int = 32,
        completion_resolver: BudgetLedgerCompletionResolver | None = None,
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        self._thread_lock = threading.Lock()
        self._ledger_id = str(ledger_id or _default_ledger_id(self._path))
        resolved_host_id = str(
            host_id or os.getenv("POLISYOS_LEDGER_HOST_ID") or socket.gethostname()
        )
        self._host_id = resolved_host_id.strip() or "localhost"
        resolved_writer_id = str(writer_id or f"{self._host_id}:{os.getpid()}:{self._path.name}")
        self._writer = BudgetLedgerWriter(
            host_id=self._host_id,
            writer_id=resolved_writer_id.strip() or f"{self._host_id}:{os.getpid()}",
            pid=os.getpid(),
        )
        self._mutation_history_limit = max(int(mutation_history_limit), 1)
        self._completion_resolver = completion_resolver
        self._completion_owner_epoch = f"{os.getpid()}:{uuid.uuid4().hex}"
        self._completion_owner_pid = os.getpid()
        self._completion_runtime_owner = _CompletionRuntimeOwner()

    @property
    def completion_owner_epoch(self) -> str:
        """Expose the configured live owner coordinate, never accept it from callers."""
        self._require_live_completion_owner()
        return self._completion_owner_epoch

    def _require_live_completion_owner(self) -> None:
        if os.getpid() != self._completion_owner_pid:
            raise RuntimeError("live budget completion owner belongs to another process")

    def with_completion_resolver(
        self, resolver: BudgetLedgerCompletionResolver
    ) -> FileBudgetLedger:
        """Bind an owner verifier to a new view of the same persisted ledger."""
        bound = FileBudgetLedger(
            self._path,
            ledger_id=self._ledger_id,
            host_id=self._host_id,
            writer_id=self._writer.writer_id,
            mutation_history_limit=self._mutation_history_limit,
            completion_resolver=resolver,
        )
        bound._completion_owner_epoch = self._completion_owner_epoch
        bound._completion_owner_pid = self._completion_owner_pid
        bound._completion_runtime_owner = self._completion_runtime_owner
        return bound

    def _assert_runtime_admission(self, budget_keys: tuple[str, ...]) -> None:
        # A fork may inherit another thread's locked mutex. Its old live owner
        # is ineligible; the persisted intent fence supplies the child predicate.
        if os.getpid() != self._completion_owner_pid:
            return
        with self._completion_runtime_owner.lock:
            records = tuple(
                record.model_copy(deep=True)
                for record in self._completion_runtime_owner.uncertain.values()
                if set(budget_keys).intersection(record.budget_keys)
            )
        if records:
            raise BudgetLedgerCompletionRequiredError(records)

    def _acknowledge_completion_publication(self, obligation_id: str, record_digest: str) -> None:
        with self._completion_runtime_owner.lock:
            uncertain = self._completion_runtime_owner.uncertain.get(obligation_id)
            if uncertain is not None and uncertain.payload_digest == record_digest:
                self._completion_runtime_owner.uncertain.pop(obligation_id)

    @staticmethod
    def _intersecting_completions(
        snapshot: BudgetLedgerSnapshot,
        budget_keys: tuple[str, ...],
        *,
        owner_epoch: str | None = None,
    ) -> tuple[BudgetLedgerCompletionObligation, ...]:
        keys = set(budget_keys)
        return tuple(
            record.model_copy(deep=True)
            for record in snapshot.completion_obligations.values()
            if keys.intersection(record.budget_keys)
            and not (record.phase == "provider_in_flight" and record.owner_epoch == owner_epoch)
        )

    def load_for_admission(self, budget_keys: tuple[str, ...]) -> BudgetState:
        """Read current state only if its actual keys have no pending completion."""
        with self._file_lock(exclusive=False):
            self._assert_runtime_admission(budget_keys)
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            pending = self._intersecting_completions(
                snapshot,
                budget_keys,
                owner_epoch=self._completion_owner_epoch
                if os.getpid() == self._completion_owner_pid
                else None,
            )
            if pending:
                raise BudgetLedgerCompletionRequiredError(pending)
            return snapshot.state

    def list_completion_obligations(
        self, budget_keys: tuple[str, ...]
    ) -> tuple[BudgetLedgerCompletionObligation, ...]:
        """Discover retained work after reopening, including in a new owner process."""
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            return self._intersecting_completions(snapshot, budget_keys)

    def admit_provider_intent(self, record: BudgetLedgerCompletionObligation) -> bool:
        """Atomically reserve all exact keys and retain intent before external work.

        Only this configured live owner can admit another controlled intent
        alongside its in-flight work. Other unresolved phases block everyone.
        An existing intent is uncertainty, never permission to reissue work.
        """
        candidate = BudgetLedgerCompletionObligation.model_validate_json(
            record.model_dump_json(), strict=True
        )
        self._require_live_completion_owner()
        if (
            candidate.phase != "provider_in_flight"
            or candidate.owner_epoch != self._completion_owner_epoch
        ):
            raise ValueError("provider intent requires its actual constructor-bound live owner")
        with self._thread_lock, self._file_lock(exclusive=True):
            self._assert_runtime_admission(candidate.budget_keys)
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            existing = snapshot.completion_obligations.get(candidate.obligation_id)
            if existing is not None:
                raise BudgetLedgerCompletionRequiredError((existing.model_copy(deep=True),))
            pending = self._intersecting_completions(
                snapshot, candidate.budget_keys, owner_epoch=self._completion_owner_epoch
            )
            if pending:
                raise BudgetLedgerCompletionRequiredError(pending)
            state = _branch_budget_state(snapshot.state)
            for key, amount in candidate.reserved_amounts.items():
                if not state.reserve(key, amount):
                    return False
            records = dict(snapshot.completion_obligations)
            records[candidate.obligation_id] = candidate
            self._write_completions(
                snapshot.model_copy(update={"state": state}),
                records,
                "admit_provider_intent",
                candidate,
            )
            return True

    def abort_provider_intent(self, obligation_id: str, expected_digest: str) -> bool:
        """Release unentered work only when its live owner proves non-admission.

        A reopened owner cannot supply this proof for an earlier physical call.
        Entered/unobserved work therefore remains unknown instead of becoming zero.
        """
        self._require_live_completion_owner()
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            record = snapshot.completion_obligations.get(obligation_id)
            if record is None:
                # An intent whose publication failed before replace reserved no
                # durable amount. Only its exact original owner can establish
                # non-admission; do not release another attempt's reservations.
                with self._completion_runtime_owner.lock:
                    uncertain = self._completion_runtime_owner.uncertain.get(obligation_id)
                if uncertain is not None:
                    if (
                        uncertain.phase != "provider_in_flight"
                        or uncertain.owner_epoch != self._completion_owner_epoch
                        or uncertain.payload_digest != expected_digest
                    ):
                        raise ValueError("intent abort disagrees with retained uncertainty")
                    self._verify_completion_resolution(uncertain, None, status="not_admitted")
                    self._acknowledge_completion_publication(
                        obligation_id, uncertain.payload_digest
                    )
                    return True
                return False
            if (
                record.phase != "provider_in_flight"
                or record.owner_epoch != self._completion_owner_epoch
                or record.payload_digest != expected_digest
            ):
                raise ValueError("intent abort requires its exact original live owner")
            self._verify_completion_resolution(record, None, status="not_admitted")
            state = _branch_budget_state(snapshot.state)
            for key, amount in record.reserved_amounts.items():
                state.release(key, amount)
            records = dict(snapshot.completion_obligations)
            del records[obligation_id]
            self._write_completions(
                snapshot.model_copy(update={"state": state}),
                records,
                "abort_provider_intent",
                record,
            )
            return True

    def retain_completion_obligation(
        self, record: BudgetLedgerCompletionObligation
    ) -> BudgetLedgerCompletionObligation:
        """Persist exact observed completion work without issuing a spend receipt."""
        self._require_live_completion_owner()
        # Detach mutable payloads and revalidate even model_copy(update=...) input.
        candidate = BudgetLedgerCompletionObligation.model_validate_json(
            record.model_dump_json(), strict=True
        )
        if candidate.phase == "provider_in_flight":
            raise ValueError("request intent requires atomic reservation and admission")
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            existing = snapshot.completion_obligations.get(candidate.obligation_id)
            if existing is not None:
                if existing.payload_digest != candidate.payload_digest:
                    raise ValueError("completion ID conflicts with its retained exact record")
                self._acknowledge_completion_publication(
                    candidate.obligation_id, candidate.payload_digest
                )
                return existing.model_copy(deep=True)
            _validate_completion_receipts(snapshot, candidate, complete=False)
            records = dict(snapshot.completion_obligations)
            records[candidate.obligation_id] = candidate
            self._write_completions(snapshot, records, "retain_completion", candidate)
            return candidate.model_copy(deep=True)

    def transition_completion_obligation(
        self, record: BudgetLedgerCompletionObligation, expected_digest: str
    ) -> BudgetLedgerCompletionObligation:
        """Advance exact completion work after actual known charge acknowledgments."""
        self._require_live_completion_owner()
        candidate = BudgetLedgerCompletionObligation.model_validate_json(
            record.model_dump_json(), strict=True
        )
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            existing = snapshot.completion_obligations.get(candidate.obligation_id)
            if existing is not None and existing.payload_digest == candidate.payload_digest:
                self._acknowledge_completion_publication(
                    candidate.obligation_id, candidate.payload_digest
                )
                return existing.model_copy(deep=True)
            if existing is None or existing.payload_digest != expected_digest:
                raise ValueError("completion transition requires its exact retained prior record")
            identity = (
                "obligation_id",
                "run_id",
                "owner_epoch",
                "budget_keys",
                "reserved_amounts",
            )
            if any(getattr(existing, name) != getattr(candidate, name) for name in identity):
                raise ValueError("completion transition cannot rewrite event or owner coordinates")
            if existing.phase == "provider_in_flight":
                self._require_live_completion_owner()
                if (
                    existing.owner_epoch != self._completion_owner_epoch
                    or candidate.phase == "provider_in_flight"
                    or existing.event_payload.get("request_digest")
                    != candidate.event_payload.get("request_digest")
                    or candidate.event_payload.get("kind") not in ("provider", "reuse")
                    or (
                        candidate.event_payload.get("kind") == "provider"
                        and candidate.event_payload.get("event_id")
                        != existing.event_payload.get("event_id")
                    )
                ):
                    raise ValueError("observed completion must bind its exact live owned request")
            elif (
                existing.event_payload != candidate.event_payload
                or existing.event_digest != candidate.event_digest
            ):
                raise ValueError("completion transition cannot rewrite an observed event")
            if existing.required_action != candidate.required_action and (
                existing.required_action is not None
                or candidate.phase != "protected_audit_pending"
                or candidate.required_action is None
            ):
                raise ValueError("completion transition cannot rewrite an established required act")
            if (
                existing.phase == "cost_unknown"
                or (candidate.phase == "cost_unknown" and existing.phase != "provider_in_flight")
                or (
                    existing.phase == "protected_audit_pending"
                    and candidate.phase != "protected_audit_pending"
                )
                or not set(existing.known_receipt_ids).issubset(candidate.known_receipt_ids)
            ):
                raise ValueError("completion transition cannot erase established uncertainty")
            _validate_completion_receipts(
                snapshot, candidate, complete=candidate.phase == "protected_audit_pending"
            )
            records = dict(snapshot.completion_obligations)
            records[candidate.obligation_id] = candidate
            self._write_completions(snapshot, records, "transition_completion", candidate)
            return candidate.model_copy(deep=True)

    def complete_completion_obligation(
        self,
        obligation_id: str,
        expected_digest: str,
        known_receipt_ids: tuple[str, ...],
        owner_resolution_ref: str | None = None,
    ) -> bool:
        """Remove a resolved gate only on actual receipts and bound owner verification.

        The optional ref is a diagnostic coordinate, never proof on its own.
        Unknown cost cannot be cleared through this API. Absence returns False;
        it does not manufacture a successful accounting acknowledgment.
        """
        self._require_live_completion_owner()
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            record = snapshot.completion_obligations.get(obligation_id)
            if record is None:
                with self._completion_runtime_owner.lock:
                    uncertain = self._completion_runtime_owner.uncertain.get(obligation_id)
                if uncertain is not None:
                    if (
                        uncertain.payload_digest != expected_digest
                        or uncertain.known_receipt_ids != known_receipt_ids
                    ):
                        raise ValueError("completion readback disagrees with retained uncertainty")
                    _validate_completion_receipts(snapshot, uncertain, complete=True)
                    self._verify_completion_resolution(
                        uncertain, owner_resolution_ref, status="resolved"
                    )
                    self._acknowledge_completion_publication(
                        obligation_id, uncertain.payload_digest
                    )
                return False
            if (
                record.payload_digest != expected_digest
                or record.known_receipt_ids != known_receipt_ids
            ):
                raise ValueError("completion resolution disagrees with its exact retained record")
            _validate_completion_receipts(snapshot, record, complete=True)
            self._verify_completion_resolution(record, owner_resolution_ref, status="resolved")
            records = dict(snapshot.completion_obligations)
            del records[obligation_id]
            self._write_completions(snapshot, records, "complete_completion", record)
            return True

    def _verify_completion_resolution(
        self,
        record: BudgetLedgerCompletionObligation,
        owner_resolution_ref: str | None,
        *,
        status: Literal["resolved", "not_admitted"],
    ) -> None:
        self._require_live_completion_owner()
        if self._completion_resolver is None:
            raise RuntimeError("completion requires a constructor-bound owner resolver")
        proof = self._completion_resolver.resolve(
            record.model_copy(deep=True), owner_resolution_ref
        )
        if not isinstance(proof, BudgetLedgerCompletionResolution) or (
            proof.obligation_id != record.obligation_id
            or proof.record_digest != record.payload_digest
            or proof.phase != record.phase
            or proof.known_receipt_ids != record.known_receipt_ids
            or proof.owner_resolution_ref != owner_resolution_ref
            or proof.status != status
        ):
            raise ValueError("owner resolver did not verify the exact completion record")

    def _write_completions(
        self,
        snapshot: BudgetLedgerSnapshot,
        records: dict[str, BudgetLedgerCompletionObligation],
        operation: Literal[
            "retain_completion",
            "transition_completion",
            "complete_completion",
            "admit_provider_intent",
            "abort_provider_intent",
        ],
        record: BudgetLedgerCompletionObligation,
    ) -> None:
        revision = snapshot.revision + 1
        mutations = list(snapshot.recent_mutations)
        mutations.append(self._build_mutation(revision=revision, operation=operation))
        try:
            self._persist_snapshot(
                self._build_snapshot(
                    state=snapshot.state,
                    revision=revision,
                    recent_mutations=mutations,
                    spend_receipts=snapshot.spend_receipts,
                    completion_obligations=records,
                )
            )
        except OSError as exc:
            with self._completion_runtime_owner.lock:
                self._completion_runtime_owner.uncertain[record.obligation_id] = record.model_copy(
                    deep=True
                )
            raise BudgetLedgerCompletionOutcomeUnknownError(
                record.obligation_id, record.payload_digest
            ) from exc
        self._acknowledge_completion_publication(record.obligation_id, record.payload_digest)

    def load(self) -> BudgetState:
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        return snapshot.state

    @property
    def settlement_owner_identity(self) -> tuple[str, str, str]:
        """Return the persisted owner/contract identity for producer cache isolation."""
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        if snapshot.ledger_id is None:
            raise ValueError("durable settlement owner requires a persisted ledger identity")
        return snapshot.ledger_id, snapshot.canonical_contract, snapshot.coordination_mode

    def snapshot(self) -> BudgetLedgerSnapshot:
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        return self._normalize_snapshot(snapshot)

    def load_or_bootstrap(self, initial_state: BudgetState) -> BudgetState:
        with self._thread_lock:
            with self._file_lock(exclusive=True):
                snapshot = self._load_snapshot()
                if snapshot is None:
                    snapshot = self._persist_snapshot(
                        self._build_snapshot(
                            state=initial_state,
                            recent_mutations=(
                                self._build_mutation(
                                    revision=0,
                                    operation="bootstrap",
                                ),
                            ),
                        )
                    )
                else:
                    needs_upgrade = self._needs_contract_upgrade(snapshot)
                    snapshot = self._normalize_snapshot(snapshot)
                    if needs_upgrade:
                        snapshot = self._persist_snapshot(snapshot)
                return snapshot.state

    def record_spend(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            state.record_spend(key, amount, provider=provider)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=amount,
            )

        return self._mutate(
            "record_spend",
            key,
            amount,
            provider=provider,
            operation=apply,
        )

    def reserve(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            reserved = state.reserve(key, amount)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=amount if reserved else Decimal("0"),
                reserved=reserved,
            )

        return self._mutate("reserve", key, amount, operation=apply)

    def release(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            released = state.release(key, amount)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=released,
            )

        return self._mutate("release", key, amount, operation=apply)

    def commit_reservation(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            committed = state.commit_reservation(key, amount, provider=provider)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=committed,
            )

        return self._mutate(
            "commit_reservation",
            key,
            amount,
            provider=provider,
            operation=apply,
        )

    def settle_spend(
        self,
        event_id: str,
        key: str,
        amount: Decimal,
        *,
        payload_digest: str,
        provider: str | None = None,
    ) -> BudgetLedgerSpendReceipt:
        """Atomically charge one exact event once and return its durable receipt.

        Exact retries return the original receipt, including after journal
        eviction or process restart. A reused ID with different payload or
        charge refuses. Filesystem failure is an unknown acknowledgment;
        resolve or retry this same ID instead of inventing a second event.
        """
        candidate = BudgetLedgerSpendReceipt(
            event_id=event_id,
            payload_digest=payload_digest,
            key=key,
            amount=amount,
            provider=provider,
            revision=1,
        )
        with self._thread_lock:
            with self._file_lock(exclusive=True):
                snapshot = self._load_snapshot()
                if snapshot is None:
                    raise FileNotFoundError(
                        "budget ledger requires explicit load_or_bootstrap before use"
                    )
                existing = snapshot.spend_receipts.get(event_id)
                if existing is not None:
                    identity = ("event_id", "payload_digest", "key", "amount", "provider")
                    if any(
                        getattr(existing, field) != getattr(candidate, field) for field in identity
                    ):
                        raise ValueError("settlement event ID conflicts with an existing charge")
                    return existing
                state = _branch_budget_state(snapshot.state)
                state.record_spend(key, candidate.amount, provider=provider)
                revision = snapshot.revision + 1
                receipt = candidate.model_copy(update={"revision": revision})
                receipts = dict(snapshot.spend_receipts)
                receipts[event_id] = receipt
                mutations = list(snapshot.recent_mutations)
                mutations.append(
                    self._build_mutation(
                        revision=revision,
                        operation="settle_spend",
                        key=key,
                        amount=candidate.amount,
                        applied_amount=candidate.amount,
                        provider=provider,
                    )
                )
                try:
                    written = self._persist_snapshot(
                        self._build_snapshot(
                            state=state,
                            revision=revision,
                            recent_mutations=mutations,
                            spend_receipts=receipts,
                            completion_obligations=snapshot.completion_obligations,
                        )
                    )
                except OSError as exc:
                    raise BudgetLedgerSettlementOutcomeUnknownError(
                        event_id, payload_digest
                    ) from exc
                return written.spend_receipts[event_id]

    def resolve_spend(self, event_id: str) -> BudgetLedgerSpendReceipt | None:
        """Resolve a durable local receipt; absence is not an assertion of zero cost."""
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        return snapshot.spend_receipts.get(event_id)

    @contextmanager
    def _file_lock(self, *, exclusive: bool) -> Iterator[None]:
        """Hold the stable lockfile for one complete read or publication."""
        try:
            import fcntl
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("fcntl is required for file budget ledger locking") from exc

        fd = os.open(str(self._lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _mutate(
        self,
        mutation_kind: Literal[
            "record_spend",
            "reserve",
            "release",
            "commit_reservation",
        ],
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
        operation: Callable[[BudgetState], BudgetLedgerMutationResult],
    ) -> BudgetLedgerMutationResult:
        with self._thread_lock:
            with self._file_lock(exclusive=True):
                snapshot = self._load_snapshot()
                if snapshot is None:
                    raise FileNotFoundError(
                        "budget ledger requires explicit load_or_bootstrap before use"
                    )
                snapshot = self._normalize_snapshot(snapshot)
                if mutation_kind == "reserve":
                    self._assert_runtime_admission((key,))
                    pending = self._intersecting_completions(snapshot, (key,))
                    if pending:
                        raise BudgetLedgerCompletionRequiredError(pending)
                state = _branch_budget_state(snapshot.state)
                result = operation(state)
                revision = snapshot.revision + 1
                mutations = list(snapshot.recent_mutations)
                mutations.append(
                    self._build_mutation(
                        revision=revision,
                        operation=mutation_kind,
                        key=key,
                        amount=amount,
                        applied_amount=result.applied_amount,
                        provider=provider,
                        reserved=result.reserved,
                    )
                )
                written = self._persist_snapshot(
                    self._build_snapshot(
                        revision=revision,
                        state=state,
                        recent_mutations=tuple(mutations[-self._mutation_history_limit :]),
                        spend_receipts=snapshot.spend_receipts,
                        completion_obligations=snapshot.completion_obligations,
                    )
                )
                return BudgetLedgerMutationResult(
                    state=written.state,
                    revision=written.revision,
                    applied_amount=result.applied_amount,
                    reserved=result.reserved,
                )

    def _load_snapshot(self) -> BudgetLedgerSnapshot | None:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        return _decode_snapshot(raw)

    def _persist_snapshot(self, snapshot: BudgetLedgerSnapshot) -> BudgetLedgerSnapshot:
        normalized = self._normalize_snapshot(snapshot)
        payload = normalized.model_dump_json(by_alias=True, exclude_none=True, indent=2).encode(
            "utf-8"
        )
        # Constructor defaults are permitted for an explicit bootstrap only.
        # Every published byte record must also pass the strict persisted inlet.
        normalized = _decode_snapshot(payload.decode("utf-8"))
        temp_fd, temp_name = tempfile.mkstemp(
            prefix=f".{self._path.name}.tmp-",
            dir=self._path.parent,
        )
        try:
            offset = 0
            while offset < len(payload):
                written = os.write(temp_fd, payload[offset:])
                if written <= 0:
                    raise OSError("budget ledger temporary write made no progress")
                offset += written
            os.fsync(temp_fd)
            os.close(temp_fd)
            temp_fd = -1
            os.replace(temp_name, self._path)
            _fsync_dir(self._path.parent)
            return normalized
        finally:
            if temp_fd >= 0:
                os.close(temp_fd)
            Path(temp_name).unlink(missing_ok=True)

    def _build_snapshot(
        self,
        *,
        state: BudgetState,
        revision: int = 0,
        recent_mutations: tuple[BudgetLedgerMutation, ...] | list[BudgetLedgerMutation] = (),
        spend_receipts: dict[str, BudgetLedgerSpendReceipt] | None = None,
        completion_obligations: dict[str, BudgetLedgerCompletionObligation] | None = None,
    ) -> BudgetLedgerSnapshot:
        return BudgetLedgerSnapshot(
            canonical_contract=_CANONICAL_LEDGER_CONTRACT,
            coordination_mode=_COORDINATION_MODE,
            ledger_id=self._ledger_id,
            revision=revision,
            updated_at=datetime.now(UTC),
            last_writer=self._writer,
            recent_mutations=list(recent_mutations)[-self._mutation_history_limit :],
            state=state,
            spend_receipts=dict(spend_receipts or {}),
            completion_obligations=dict(completion_obligations or {}),
        )

    def _build_mutation(
        self,
        *,
        revision: int,
        operation: Literal[
            "bootstrap",
            "record_spend",
            "reserve",
            "release",
            "commit_reservation",
            "settle_spend",
            "retain_completion",
            "transition_completion",
            "complete_completion",
            "admit_provider_intent",
            "abort_provider_intent",
        ],
        key: str | None = None,
        amount: Decimal | None = None,
        applied_amount: Decimal | None = None,
        provider: str | None = None,
        reserved: bool | None = None,
    ) -> BudgetLedgerMutation:
        return BudgetLedgerMutation(
            revision=revision,
            operation=operation,
            key=key,
            amount=amount,
            applied_amount=applied_amount,
            provider=provider,
            reserved=reserved,
            writer=self._writer,
        )

    def _normalize_snapshot(self, snapshot: BudgetLedgerSnapshot) -> BudgetLedgerSnapshot:
        return snapshot.model_copy(
            update={
                "canonical_contract": snapshot.canonical_contract or _CANONICAL_LEDGER_CONTRACT,
                "coordination_mode": snapshot.coordination_mode or _COORDINATION_MODE,
                "ledger_id": snapshot.ledger_id or self._ledger_id,
                "schema_version": _SNAPSHOT_VERSION,
            }
        )

    def _needs_contract_upgrade(self, snapshot: BudgetLedgerSnapshot) -> bool:
        return bool(
            snapshot.ledger_id is None
            or snapshot.schema_version != _SNAPSHOT_VERSION
            or snapshot.canonical_contract != _CANONICAL_LEDGER_CONTRACT
            or snapshot.coordination_mode != _COORDINATION_MODE
        )


def _branch_budget_state(state: BudgetState) -> BudgetState:
    """Copy only the mutable budget maps before one ledger mutation."""

    branched = state.model_copy(deep=False)
    branched.limits = dict(state.limits)
    branched.spent = dict(state.spent)
    branched.provider_spent = dict(state.provider_spent)
    branched.reserved = dict(state.reserved)
    return branched


def _default_ledger_id(path: Path) -> str:
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()
    return f"ledger:{digest[:16]}"
