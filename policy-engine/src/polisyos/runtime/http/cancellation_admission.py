"""Short-lived request scope for a job cancellation action."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING

from polisyos.runtime.http.authorization import BoundActionPermissionVerification
from polisyos.runtime.http.errors import forbidden

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import Request


@dataclass(frozen=True, slots=True)
class _LiveCancellationAuthority:
    proof: BoundActionPermissionVerification
    active: Event


_CURRENT: ContextVar[_LiveCancellationAuthority | None] = ContextVar(
    "live_control_job_cancellation_authority", default=None
)


@contextmanager
def cancellation_request_scope(
    request: Request, proof: BoundActionPermissionVerification
) -> Iterator[None]:
    """Bind an exact still-open action/resource verification to this request only."""
    state = request.state
    if (
        type(proof) is not BoundActionPermissionVerification
        or getattr(state, "action_permission_verification", None) is not proof
        or getattr(state, "authz_bound_resource", None) is not proof.bound_resource
        or getattr(state, "authz_action_bound_resource", None) is not proof.bound_resource
        or getattr(state, "authz_resource_frozen", False) is not True
        or getattr(state, "control_job_cancellation_consumed", False) is not False
    ):
        raise forbidden(
            "Cancellation requires a current, unconsumed request authority",
            code="control_job_cancellation_authorization_not_current",
        )
    state.control_job_cancellation_consumed = True
    active = Event()
    active.set()
    token = _CURRENT.set(_LiveCancellationAuthority(proof=proof, active=active))
    try:
        yield
    finally:
        active.clear()
        _CURRENT.reset(token)


def is_current_cancellation_authority(proof: object) -> bool:
    """Return whether this exact proof belongs to the active cancellation request."""
    current = _CURRENT.get()
    return current is not None and current.proof is proof and current.active.is_set()
