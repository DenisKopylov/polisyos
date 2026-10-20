"""Caller-owned cooperative batch authorization-loss signal."""

from __future__ import annotations

from threading import Event, Lock
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

_T = TypeVar("_T")


class BatchAuthorizationLossSignal:
    """Request stopping new batch admissions after authorization scope is lost.

    The caller owns the decision to request this signal. It must do so only
    after its configured request-scope authorizer establishes authorization
    loss. The signal does not resolve policy, grant permission, or preempt work
    that the batch has already admitted.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._requested = Event()

    def request(self) -> None:
        """Request the one-way cooperative stop; repeated requests are harmless."""
        with self._lock:
            self._requested.set()

    def is_set(self) -> bool:
        """Return whether the caller requested the authorization-loss stop."""
        return self._requested.is_set()

    def admit_if_open(self, submit: Callable[[], _T]) -> _T | None:
        """Run one short executor submission only while the signal remains open.

        The callback runs under the signal lock so a concurrent request has a
        clear admission boundary. It must submit work and return immediately;
        it must not run the artifact callback itself or request this signal.

        Args:
            submit: Zero-argument callback that submits one executor task.

        Returns:
            The submission result, or ``None`` when authorization loss was
            already requested. The callback must not return ``None``.
        """
        with self._lock:
            if self._requested.is_set():
                return None
            return submit()
