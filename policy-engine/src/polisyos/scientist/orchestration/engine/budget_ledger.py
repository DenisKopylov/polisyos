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
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.scientist.orchestration.engine.budget import BudgetState

_CANONICAL_LEDGER_CONTRACT = "scientist.multi_host_budget_ledger.v1"
_COORDINATION_MODE = "shared_posix_file_lock"

__all__ = [
    "BudgetLedger",
    "BudgetLedgerMutation",
    "BudgetLedgerMutationResult",
    "BudgetLedgerSnapshot",
    "BudgetLedgerWriter",
    "BudgetResourceEvent",
    "BudgetResourceReservation",
    "FileBudgetLedger",
]


class BudgetResourceEvent(BaseModel):
    """A measured provider receipt or a cache-owner reuse event.

    Identity follows the physical provider request, not a delivery attempt.
    Amounts are provider reported; admission estimates are never receipts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    provider: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    budget_keys: tuple[str, ...]
    amount_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    evaluation_id: str | None = None
    source: Literal["provider_reported", "cache_reuse"] = "provider_reported"
    reuse_event_id: str | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> BudgetResourceEvent:
        """Require a definite charge scope and honest cache-reuse amount."""
        _validate_budget_keys(self.budget_keys)
        if self.source == "cache_reuse":
            if self.amount_usd != 0 or not self.reuse_event_id:
                raise ValueError("cache reuse requires its owner event ID and zero new charge")
        elif self.reuse_event_id is not None:
            raise ValueError("provider charge cannot use a cache reuse event ID")
        return self

    @property
    def event_id(self) -> str:
        """Return stable physical-request identity across repeated deliveries."""
        identity = (self.source, self.provider, self.request_id, self.reuse_event_id)
        return hashlib.sha256(json.dumps(identity).encode("utf-8")).hexdigest()


class BudgetResourceReservation(BaseModel):
    """One owned resource attempt, retained through settlement or reconciliation."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    reservation_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    budget_keys: tuple[str, ...]
    estimated_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    evaluation_id: str | None = None
    reserved_amounts: dict[str, Decimal] = Field(default_factory=dict)
    status: Literal["reserved", "released", "settled", "reconciliation_required"] = "reserved"
    event_id: str | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> BudgetResourceReservation:
        """Reject ambiguous duplicate or empty budget keys."""
        _validate_budget_keys(self.budget_keys)
        return self


def _validate_budget_keys(keys: tuple[str, ...]) -> None:
    if not keys or any(not key.strip() for key in keys) or len(set(keys)) != len(keys):
        raise ValueError("budget_keys must contain distinct nonempty keys")


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
        "reserve_resource",
        "settle_resource",
        "release_resource",
        "require_reconciliation",
    ]
    key: str | None = None
    amount: Decimal | None = None
    applied_amount: Decimal | None = None
    provider: str | None = None
    reserved: bool | None = None
    writer: BudgetLedgerWriter
    committed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BudgetLedgerSnapshot(BaseModel):
    """Persisted budget ledger state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    canonical_contract: str = Field(default=_CANONICAL_LEDGER_CONTRACT, min_length=1)
    coordination_mode: str = Field(default=_COORDINATION_MODE, min_length=1)
    ledger_id: str | None = None
    revision: int = Field(default=0, ge=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_writer: BudgetLedgerWriter | None = None
    recent_mutations: list[BudgetLedgerMutation] = Field(default_factory=list)
    state: BudgetState = Field(default_factory=BudgetState)
    # These identities are durable accounting state, not the bounded debug journal.
    resource_reservations: dict[str, BudgetResourceReservation] = Field(default_factory=dict)
    resource_events: dict[str, BudgetResourceEvent] = Field(default_factory=dict)


@dataclass(frozen=True)
class BudgetLedgerMutationResult:
    """Result of a ledger mutation."""

    state: BudgetState
    revision: int
    applied_amount: Decimal = Decimal("0")
    reserved: bool | None = None
    duplicate: bool = False


class BudgetLedger(Protocol):
    """Protocol for distributed-safe budget ledgers."""

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
    def reserve_resource(
        self, reservation: BudgetResourceReservation
    ) -> BudgetLedgerMutationResult: ...
    def settle_resource(
        self, reservation_id: str, event: BudgetResourceEvent
    ) -> BudgetLedgerMutationResult: ...
    def release_resource(self, reservation_id: str) -> BudgetLedgerMutationResult: ...
    def require_reconciliation(self, reservation_id: str) -> BudgetLedgerMutationResult: ...


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
        return snapshot.state if snapshot is not None else BudgetState()

    def snapshot(self) -> BudgetLedgerSnapshot:
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            return self._build_snapshot(state=BudgetState())
        return self._normalize_snapshot(snapshot)

    def load_or_bootstrap(self, initial_state: BudgetState) -> BudgetState:
        with self._thread_lock:
            with self._file_lock(exclusive=True):
                existed = self._path.exists()
                fd = os.open(str(self._path), os.O_RDWR | os.O_CREAT, 0o644)
                try:
                    snapshot = self._read_snapshot_from_fd(fd) if existed else None
                    if snapshot is None:
                        snapshot = self._persist_snapshot(
                            fd,
                            self._build_snapshot(
                                state=initial_state,
                                recent_mutations=(
                                    self._build_mutation(
                                        revision=0,
                                        operation="bootstrap",
                                    ),
                                ),
                            ),
                        )
                    else:
                        needs_upgrade = self._needs_contract_upgrade(snapshot)
                        snapshot = self._normalize_snapshot(snapshot)
                        if needs_upgrade:
                            snapshot = self._persist_snapshot(fd, snapshot)
                    return snapshot.state
                finally:
                    os.close(fd)

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

    def reserve_resource(
        self, reservation: BudgetResourceReservation
    ) -> BudgetLedgerMutationResult:
        """Atomically reserve every key for one distinct physical attempt."""
        if (
            reservation.status != "reserved"
            or reservation.event_id is not None
            or reservation.reserved_amounts
        ):
            raise ValueError("resource reservation request cannot assert settled accounting state")

        def apply(snapshot: BudgetLedgerSnapshot) -> BudgetLedgerMutationResult:
            previous = snapshot.resource_reservations.get(reservation.reservation_id)
            if previous is not None:
                original = previous.model_copy(
                    update={"reserved_amounts": {}, "status": "reserved", "event_id": None}
                )
                if original != reservation:
                    raise ValueError("resource reservation identity conflict")
                if previous.status != "reserved":
                    raise ValueError(
                        "resource reservation already completed or pending reconciliation"
                    )
                return BudgetLedgerMutationResult(
                    snapshot.state, snapshot.revision, reserved=True, duplicate=True
                )
            if any(
                snapshot.state.would_exceed(key, reservation.estimated_usd)
                for key in reservation.budget_keys
            ):
                return BudgetLedgerMutationResult(
                    snapshot.state, snapshot.revision, reserved=False, duplicate=True
                )
            amounts = {}
            for key in reservation.budget_keys:
                snapshot.state.reserve(key, reservation.estimated_usd)
                amounts[key] = (
                    reservation.estimated_usd if key in snapshot.state.limits else Decimal(0)
                )
            snapshot.resource_reservations[reservation.reservation_id] = reservation.model_copy(
                update={"reserved_amounts": amounts}
            )
            return BudgetLedgerMutationResult(snapshot.state, snapshot.revision, reserved=True)

        return self._mutate_resource("reserve_resource", apply)

    def settle_resource(
        self, reservation_id: str, event: BudgetResourceEvent
    ) -> BudgetLedgerMutationResult:
        """Release this attempt's reservation and debit its full measured receipt once."""

        def apply(snapshot: BudgetLedgerSnapshot) -> BudgetLedgerMutationResult:
            reservation = snapshot.resource_reservations[reservation_id]
            if (reservation.run_id, reservation.budget_keys, reservation.evaluation_id) != (
                event.run_id,
                event.budget_keys,
                event.evaluation_id,
            ):
                raise ValueError("resource receipt scope conflict")
            previous = snapshot.resource_events.get(event.event_id)
            if previous is not None and previous != event:
                raise ValueError("resource receipt identity conflict")
            if reservation.status == "settled":
                if reservation.event_id != event.event_id or previous != event:
                    raise ValueError("resource reservation settlement conflict")
                return BudgetLedgerMutationResult(snapshot.state, snapshot.revision, duplicate=True)
            if reservation.status == "released":
                raise ValueError("released resource reservation cannot be settled")
            for key, amount in reservation.reserved_amounts.items():
                snapshot.state.release(key, amount)
            applied = Decimal(0)
            if previous is None:
                for key in event.budget_keys:
                    snapshot.state.record_spend(key, event.amount_usd)
                snapshot.state.provider_spent[event.provider] = (
                    snapshot.state.provider_spent.get(event.provider, Decimal(0)) + event.amount_usd
                )
                snapshot.resource_events[event.event_id] = event
                applied = event.amount_usd
            snapshot.resource_reservations[reservation_id] = reservation.model_copy(
                update={"status": "settled", "event_id": event.event_id}
            )
            return BudgetLedgerMutationResult(
                snapshot.state, snapshot.revision, applied_amount=applied
            )

        return self._mutate_resource("settle_resource", apply)

    def release_resource(self, reservation_id: str) -> BudgetLedgerMutationResult:
        """Release an attempt only when its caller knows no billing reconciliation is due."""

        def apply(snapshot: BudgetLedgerSnapshot) -> BudgetLedgerMutationResult:
            reservation = snapshot.resource_reservations[reservation_id]
            if reservation.status != "reserved":
                if reservation.status == "released":
                    return BudgetLedgerMutationResult(
                        snapshot.state, snapshot.revision, duplicate=True
                    )
                raise ValueError("cannot release a settled or unresolved resource attempt")
            for key, amount in reservation.reserved_amounts.items():
                snapshot.state.release(key, amount)
            snapshot.resource_reservations[reservation_id] = reservation.model_copy(
                update={"status": "released"}
            )
            return BudgetLedgerMutationResult(snapshot.state, snapshot.revision)

        return self._mutate_resource("release_resource", apply)

    def require_reconciliation(self, reservation_id: str) -> BudgetLedgerMutationResult:
        """Retain admission reservation when actual provider billing is unknown."""

        def apply(snapshot: BudgetLedgerSnapshot) -> BudgetLedgerMutationResult:
            reservation = snapshot.resource_reservations[reservation_id]
            if reservation.status != "reserved":
                return BudgetLedgerMutationResult(snapshot.state, snapshot.revision, duplicate=True)
            snapshot.resource_reservations[reservation_id] = reservation.model_copy(
                update={"status": "reconciliation_required"}
            )
            return BudgetLedgerMutationResult(snapshot.state, snapshot.revision)

        return self._mutate_resource("require_reconciliation", apply)

    def _mutate_resource(
        self,
        operation: Literal[
            "reserve_resource", "settle_resource", "release_resource", "require_reconciliation"
        ],
        apply: Callable[[BudgetLedgerSnapshot], BudgetLedgerMutationResult],
    ) -> BudgetLedgerMutationResult:
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._normalize_snapshot(
                self._load_snapshot() or self._build_snapshot(state=BudgetState())
            ).model_copy(deep=True)
            result = apply(snapshot)
            if result.duplicate:
                return result
            snapshot.revision += 1
            snapshot.updated_at = datetime.now(UTC)
            snapshot.last_writer = self._writer
            mutation = self._build_mutation(
                revision=snapshot.revision,
                operation=operation,
                applied_amount=result.applied_amount,
                reserved=result.reserved,
            )
            snapshot.recent_mutations = [*snapshot.recent_mutations, mutation][
                -self._mutation_history_limit :
            ]
            self._persist_snapshot(-1, snapshot)
            return BudgetLedgerMutationResult(
                snapshot.state, snapshot.revision, result.applied_amount, result.reserved
            )

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
                existed = self._path.exists()
                fd = os.open(str(self._path), os.O_RDWR | os.O_CREAT, 0o644)
                try:
                    snapshot = self._normalize_snapshot(
                        self._read_snapshot_from_fd(fd) if existed else BudgetLedgerSnapshot()
                    )
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
                        fd,
                        self._build_snapshot(
                            revision=revision,
                            state=state,
                            recent_mutations=tuple(mutations[-self._mutation_history_limit :]),
                            resource_reservations=snapshot.resource_reservations,
                            resource_events=snapshot.resource_events,
                        ),
                    )
                    return BudgetLedgerMutationResult(
                        state=written.state,
                        revision=written.revision,
                        applied_amount=result.applied_amount,
                        reserved=result.reserved,
                    )
                finally:
                    os.close(fd)

    def _read_snapshot_from_fd(self, fd: int) -> BudgetLedgerSnapshot | None:
        os.lseek(fd, 0, os.SEEK_SET)
        with os.fdopen(os.dup(fd), "r", encoding="utf-8") as stream:
            raw = stream.read().strip()
        if not raw:
            raise ValueError("existing budget ledger is empty")
        return BudgetLedgerSnapshot.model_validate(json.loads(raw))

    def _load_snapshot(self) -> BudgetLedgerSnapshot | None:
        if not self._path.exists():
            return None
        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            raise ValueError("existing budget ledger is empty")
        return BudgetLedgerSnapshot.model_validate(json.loads(raw))

    def _persist_snapshot(self, fd: int, snapshot: BudgetLedgerSnapshot) -> BudgetLedgerSnapshot:
        normalized = self._normalize_snapshot(snapshot)
        payload = normalized.model_dump_json(by_alias=True, exclude_none=True, indent=2).encode(
            "utf-8"
        )
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
        resource_reservations: dict[str, BudgetResourceReservation] | None = None,
        resource_events: dict[str, BudgetResourceEvent] | None = None,
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
            resource_reservations=resource_reservations or {},
            resource_events=resource_events or {},
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
            "reserve_resource",
            "settle_resource",
            "release_resource",
            "require_reconciliation",
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
            }
        )

    def _needs_contract_upgrade(self, snapshot: BudgetLedgerSnapshot) -> bool:
        return bool(
            snapshot.ledger_id is None
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
