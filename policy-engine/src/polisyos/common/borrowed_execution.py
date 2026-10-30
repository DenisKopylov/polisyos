"""Thread-affine continuation of an actual admitted worker."""

from __future__ import annotations

import json
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

from polisyos.common.async_tools import owns_shared_executor_slot

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from concurrent.futures import ThreadPoolExecutor

T = TypeVar("T")


class _OwnedEffectOutcomeUnknownError(BaseException):
    """An entered effect needs reconciliation, not an ordinary failure fallback."""


def _valid_basis_ref(value: str) -> bool:
    """Accept canonical JSON for exactly one profile-qualified ArtifactRef."""
    if type(value) is not str or len(value) > 4096:
        return False
    try:
        item = json.loads(value)
    except (ValueError, RecursionError):
        return False
    if type(item) is not dict or set(item) != {
        "artifact_id",
        "kind",
        "media_type",
        "manifest_profile_sha256",
    }:
        return False
    for key in ("kind", "media_type"):
        if type(item[key]) is not str or not item[key].strip():
            return False
    for key in ("artifact_id", "manifest_profile_sha256"):
        if type(item[key]) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", item[key]) is None:
            return False
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True) == value


@dataclass
class _BlockingAttempt:
    unavailable: bool = False
    deadline: float = float("inf")
    revoked: bool = False
    grant: _BorrowedExecutionGrant | None = None
    budget_uncertain: threading.Event | None = None
    lease_lost: threading.Event | None = None
    transition_lock: threading.RLock = field(default_factory=threading.RLock)

    def revoke(self) -> None:
        with self.transition_lock:
            self.revoked = True


_CONTROL_LIVENESS_TOKEN = object()


class _BorrowedControlLiveness:
    """Read-only liveness of an owner-verified attempt, not an execution grant.

    Core may retain this inside a separately owner-issued, one-use operation
    handle. It cannot run work, admit a child, or publish an effect by itself.
    """

    __slots__ = ("__attempt", "__binding", "__grant_identity")

    def __init__(
        self,
        attempt: _BlockingAttempt,
        binding: tuple[str, str | None, str, str],
        grant_identity: int,
        *,
        token: object,
    ) -> None:
        if token is not _CONTROL_LIVENESS_TOKEN:
            raise TypeError("borrowed_control_liveness_not_owner_issued")
        self.__attempt = attempt
        self.__binding = binding
        self.__grant_identity = grant_identity

    def _require_current(self) -> None:
        """Reconcile the original live attempt without transferring its grant."""
        attempt = self.__attempt
        with attempt.transition_lock:
            grant = attempt.grant
            if (
                attempt.revoked
                or grant is None
                or id(grant) != self.__grant_identity
                or grant._parent_binding != self.__binding
                or time.monotonic() >= attempt.deadline
                or (attempt.budget_uncertain is not None and attempt.budget_uncertain.is_set())
                or (attempt.lease_lost is not None and attempt.lease_lost.is_set())
            ):
                raise RuntimeError("borrowed_execution_admission_not_current")

    @contextmanager
    def _admission(self) -> Iterator[None]:
        """Order one short owner decision against actual attempt revocation."""
        with self.__attempt.transition_lock:
            self._require_current()
            yield


class _BorrowedExecutionGrant:
    """Thread-affine continuation of an actual running guard worker.

    This is a compute-capacity handle, not monetary or data authority. The
    enclosing guard must run the entire parent body on its worker.
    """

    def __init__(
        self, attempt: _BlockingAttempt, execution: threading.local, executor: ThreadPoolExecutor
    ) -> None:
        self._attempt = attempt
        self._executor = executor
        self._execution = execution
        self._thread_id = threading.get_ident()
        self._in_child = False
        self._parent_binding: tuple[str, str | None, str, str] | None = None

    def bind_parent(
        self, *, run_id: str, job_id: str | None, attempt_id: str, basis_ref: str
    ) -> None:
        """Bind once to a basis already verified by trusted engine bootstrap.

        The caller must independently reconcile these values with the actual
        persisted owner record; this method does not authenticate declarations.
        """
        values = (run_id, job_id, attempt_id, basis_ref)
        if (
            any(type(value) is not str or not value.strip() for value in (run_id, attempt_id))
            or (job_id is not None and (type(job_id) is not str or not job_id.strip()))
            or not _valid_basis_ref(basis_ref)
        ):
            raise ValueError("borrowed_execution_parent_binding_invalid")
        with self._attempt.transition_lock:
            self._check_locked()
            if self._parent_binding is not None:
                raise RuntimeError("borrowed_execution_parent_already_bound")
            self._parent_binding = values

    def require_parent(
        self, *, run_id: str, job_id: str | None, attempt_id: str, basis_ref: str
    ) -> None:
        """Refuse if the live grant is not bound to the exact verified basis."""
        with self._attempt.transition_lock:
            self._check_locked()
            if self._parent_binding is None or self._parent_binding != (
                run_id,
                job_id,
                attempt_id,
                basis_ref,
            ):
                raise RuntimeError("borrowed_execution_parent_binding_mismatch")

    def _control_liveness(
        self, *, run_id: str, job_id: str | None, attempt_id: str, basis_ref: str
    ) -> _BorrowedControlLiveness:
        """Capture only liveness after checking the actual owning thread and basis."""
        binding = (run_id, job_id, attempt_id, basis_ref)
        with self._attempt.transition_lock:
            self._check_locked()
            if self._parent_binding != binding:
                raise RuntimeError("borrowed_execution_parent_binding_mismatch")
            return _BorrowedControlLiveness(
                self._attempt, binding, id(self), token=_CONTROL_LIVENESS_TOKEN
            )

    @property
    def deadline_monotonic(self) -> float:
        """Return the original absolute deadline, never a renewed duration."""
        return self._attempt.deadline

    def _check_locked(self) -> None:
        if (
            self._attempt.revoked
            or self._attempt.grant is not self
            or getattr(self._execution, "attempt", None) is not self._attempt
            or threading.get_ident() != self._thread_id
            or not owns_shared_executor_slot(self._executor)
            or time.monotonic() >= self._attempt.deadline
            or (
                self._attempt.budget_uncertain is not None
                and self._attempt.budget_uncertain.is_set()
            )
            or (self._attempt.lease_lost is not None and self._attempt.lease_lost.is_set())
        ):
            raise RuntimeError("borrowed_execution_admission_not_current")

    def check_current(self) -> None:
        """Refuse a foreign, expired or revoked execution attempt."""
        with self._attempt.transition_lock:
            self._check_locked()

    def run_child(self, operation: Callable[[], T]) -> T:
        """Continue the worker serially; do not acquire a second worker."""
        self.check_current()
        if self._parent_binding is None:
            raise RuntimeError("borrowed_execution_parent_binding_mismatch")
        if self._in_child:
            raise RuntimeError("borrowed_execution_child_already_active")
        self._in_child = True
        try:
            result = operation()
            self.check_current()
            return result
        finally:
            self._in_child = False

    @contextmanager
    def admission(self) -> Iterator[None]:
        """Order one short actual child-admission decision against observed loss.

        Do not run child computation, blocking I/O or capacity waits while held.
        """
        with self.publication():
            yield

    @contextmanager
    def publication(self) -> Iterator[None]:
        """Order a short release against this guard's timeout/revocation.

        Acquire the actual job fence first; no computation, copying or external
        waits belong inside this guard. This does not fence a different owner.
        """
        with self._attempt.transition_lock:
            self._check_locked()
            if self._parent_binding is None:
                raise RuntimeError("borrowed_execution_parent_binding_mismatch")
            yield
