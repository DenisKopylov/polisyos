"""File-backed budget ledger for distributed-safe Scientist budget accounting."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.orchestration.engine.budget import BudgetState

_CANONICAL_LEDGER_CONTRACT = "scientist.multi_host_budget_ledger.v1"
_COORDINATION_MODE = "shared_posix_file_lock"
_SNAPSHOT_VERSION = "1.1"

__all__ = [
    "BudgetLedger",
    "BudgetLedgerMutation",
    "BudgetLedgerMutationResult",
    "BudgetLedgerSnapshot",
    "BudgetLedgerWriter",
    "BudgetLedgerSpendReceipt",
    "BudgetLedgerSettlementOutcomeUnknownError",
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
    if not isinstance(version, str) or version not in {"1.0", _SNAPSHOT_VERSION}:
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
    return snapshot


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
