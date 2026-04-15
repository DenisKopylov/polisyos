"""File-backed budget ledger for distributed-safe Scientist budget accounting."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.engine.budget import BudgetState

__all__ = [
    "BudgetLedger",
    "BudgetLedgerMutationResult",
    "BudgetLedgerSnapshot",
    "FileBudgetLedger",
]


class BudgetLedgerSnapshot(BaseModel):
    """Persisted budget ledger state."""

    model_config = ConfigDict(extra="forbid")

    revision: int = Field(default=0, ge=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    state: BudgetState = Field(default_factory=BudgetState)


@dataclass(frozen=True)
class BudgetLedgerMutationResult:
    """Result of a ledger mutation."""

    state: BudgetState
    revision: int
    applied_amount: Decimal = Decimal("0")
    reserved: bool | None = None


class BudgetLedger(Protocol):
    """Protocol for distributed-safe budget ledgers."""

    def load(self) -> BudgetState: ...
    def load_or_bootstrap(self, initial_state: BudgetState) -> BudgetState: ...
    def record_spend(
        self, key: str, amount: Decimal, *, provider: str | None = None,
    ) -> BudgetLedgerMutationResult: ...
    def reserve(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult: ...
    def release(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult: ...
    def commit_reservation(
        self, key: str, amount: Decimal, *, provider: str | None = None,
    ) -> BudgetLedgerMutationResult: ...


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class FileBudgetLedger:
    """Atomic JSON budget ledger shared across threads/processes."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._thread_lock = threading.Lock()

    def load(self) -> BudgetState:
        snapshot = self._load_snapshot()
        return snapshot.state if snapshot is not None else BudgetState()

    def load_or_bootstrap(self, initial_state: BudgetState) -> BudgetState:
        with self._thread_lock:
            try:
                import fcntl
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("fcntl is required for file budget ledger locking") from exc

            fd = os.open(str(self._path), os.O_RDWR | os.O_CREAT, 0o644)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                snapshot = self._read_snapshot_from_fd(fd)
                if snapshot is None:
                    snapshot = self._persist_snapshot(fd, BudgetLedgerSnapshot(state=initial_state))
                return snapshot.state
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def record_spend(
        self, key: str, amount: Decimal, *, provider: str | None = None,
    ) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            state.record_spend(key, amount, provider=provider)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=amount,
            )

        return self._mutate(apply)

    def reserve(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            reserved = state.reserve(key, amount)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=amount if reserved else Decimal("0"),
                reserved=reserved,
            )

        return self._mutate(apply)

    def release(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            released = state.release(key, amount)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=released,
            )

        return self._mutate(apply)

    def commit_reservation(
        self, key: str, amount: Decimal, *, provider: str | None = None,
    ) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            committed = state.commit_reservation(key, amount, provider=provider)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=committed,
            )

        return self._mutate(apply)

    def _mutate(
        self,
        operation: Callable[[BudgetState], BudgetLedgerMutationResult],
    ) -> BudgetLedgerMutationResult:
        with self._thread_lock:
            try:
                import fcntl
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("fcntl is required for file budget ledger locking") from exc

            fd = os.open(str(self._path), os.O_RDWR | os.O_CREAT, 0o644)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                snapshot = self._read_snapshot_from_fd(fd) or BudgetLedgerSnapshot()
                state = _branch_budget_state(snapshot.state)
                result = operation(state)
                written = self._persist_snapshot(
                    fd,
                    BudgetLedgerSnapshot(
                        revision=snapshot.revision + 1,
                        updated_at=datetime.now(UTC),
                        state=state,
                    )
                )
                return BudgetLedgerMutationResult(
                    state=written.state,
                    revision=written.revision,
                    applied_amount=result.applied_amount,
                    reserved=result.reserved,
                )
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def _read_snapshot_from_fd(self, fd: int) -> BudgetLedgerSnapshot | None:
        os.lseek(fd, 0, os.SEEK_SET)
        raw = os.read(fd, 1_000_000).decode("utf-8").strip()
        if not raw:
            return None
        return BudgetLedgerSnapshot.model_validate(json.loads(raw))

    def _load_snapshot(self) -> BudgetLedgerSnapshot | None:
        if not self._path.exists():
            return None
        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        return BudgetLedgerSnapshot.model_validate(json.loads(raw))

    def _persist_snapshot(self, fd: int, snapshot: BudgetLedgerSnapshot) -> BudgetLedgerSnapshot:
        payload = snapshot.model_dump_json(by_alias=True, exclude_none=True, indent=2).encode(
            "utf-8"
        )
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, payload)
        os.fsync(fd)
        _fsync_dir(self._path.parent)
        return snapshot


def _branch_budget_state(state: BudgetState) -> BudgetState:
    """Copy only the mutable budget maps before one ledger mutation."""

    branched = state.model_copy(deep=False)
    branched.limits = dict(state.limits)
    branched.spent = dict(state.spent)
    branched.provider_spent = dict(state.provider_spent)
    branched.reserved = dict(state.reserved)
    return branched
