"""Run-lock protocol — backend-agnostic lock interface."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RunLockHandle(Protocol):
    """Handle returned by a successful lock acquisition."""

    @property
    def run_id(self) -> str:  # pragma: no cover - protocol
        ...

    @property
    def metadata(self) -> dict[str, Any]:  # pragma: no cover - protocol
        ...

    def release(self) -> None:  # pragma: no cover - protocol
        ...

    def is_alive(self) -> bool:  # pragma: no cover - protocol
        """Return True if the lock is still actively held."""
        ...


@runtime_checkable
class RunLockBackend(Protocol):
    """Backend that can acquire an exclusive run lock."""

    def acquire(
        self,
        *,
        run_id: str,
        mode: str,
        force: bool = False,
        owner_token: str | None = None,
    ) -> RunLockHandle:  # pragma: no cover - protocol
        ...

    def detect_stale(self, run_id: str) -> bool:  # pragma: no cover - protocol
        """Return True if the lock for *run_id* appears stale."""
        ...
