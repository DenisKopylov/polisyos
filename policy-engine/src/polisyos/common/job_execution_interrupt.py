"""A scoped, in-process interruption signal for one leased job attempt."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from threading import Event


class JobExecutionInterrupted(BaseException):
    """The owning worker observed that this execution's lease was lost."""


class JobExecutionOwnerNotEstablishedError(RuntimeError):
    """A strict continuation has no matching live owner-check capability."""


@dataclass(frozen=True, slots=True)
class JobExecutionInterrupt:
    """Carry one worker-owned signal without implying that all work stopped."""

    job_id: str
    worker_id: str
    attempt: int
    lost: Event
    current_owner_check: Callable[[], None] | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not self.job_id or not self.worker_id or self.attempt < 1:
            raise ValueError("job_execution_interrupt_identity_invalid")
        if self.current_owner_check is not None and not callable(self.current_owner_check):
            raise ValueError("job_execution_current_owner_check_invalid")


_CURRENT: ContextVar[JobExecutionInterrupt | None] = ContextVar(
    "job_execution_interrupt", default=None
)


@contextmanager
def job_execution_interrupt_scope(signal: JobExecutionInterrupt) -> Iterator[None]:
    """Bind an exact attempt to work that preserves its execution context."""
    token = _CURRENT.set(signal)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def raise_if_job_execution_interrupted(*, check_current_owner: bool = False) -> None:
    """Check the signal, optionally refreshing its worker-owned admission.

    Ordinary cooperative polling reads only the event. The final producer
    dispatch can request a fresh check without making every wait loop query SQL.
    A legacy event-only signal cannot establish strict continuation authority.
    """
    current = _CURRENT.get()
    if current is None:
        return
    if current.lost.is_set():
        raise JobExecutionInterrupted(
            f"lease lost for job {current.job_id} owner {current.worker_id} "
            f"attempt {current.attempt}"
        )
    if check_current_owner and current.current_owner_check is not None:
        try:
            current.current_owner_check()
        except JobExecutionInterrupted:
            current.lost.set()
            raise
        except Exception as error:
            # An unavailable owner check is never an ordinary retryable node
            # failure. Preserve the real cause while stopping this attempt.
            current.lost.set()
            raise JobExecutionInterrupted("job_execution_current_owner_check_failed") from error
        if current.lost.is_set():
            raise JobExecutionInterrupted(
                f"lease lost for job {current.job_id} owner {current.worker_id} "
                f"attempt {current.attempt}"
            )


def require_current_job_execution_owner(expected_job_id: str) -> None:
    """Require and refresh the actual worker capability for one strict resume.

    The worker installs the check from its real store and execution fence; the
    consumer supplies only a restriction, never an affirmative permission.
    This does not make a later external effect atomic with its lease check.
    """
    current = _CURRENT.get()
    if (
        not expected_job_id
        or current is None
        or current.job_id != expected_job_id
        or current.current_owner_check is None
    ):
        raise JobExecutionOwnerNotEstablishedError("job_execution_current_owner_not_established")
    raise_if_job_execution_interrupted(check_current_owner=True)


def has_job_execution_owner_check() -> bool:
    """Report a bound live-check capability's presence, without checking its owner.

    This is only a transport restriction: a caller may refuse a route that cannot
    carry the check. True establishes neither currentness nor permission.
    """
    current = _CURRENT.get()
    return current is not None and current.current_owner_check is not None


def has_job_execution_scope() -> bool:
    """Report a bound attempt's presence without establishing live authority.

    An event-only legacy scope is still worker-bound and cannot be transported
    through a child route that cannot preserve its interruption capability.
    A lost bound attempt still reports present. The predicate performs no owner
    lookup and grants no execution permission.
    """
    return _CURRENT.get() is not None
