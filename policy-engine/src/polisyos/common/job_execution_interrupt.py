"""A scoped, in-process interruption signal for one leased job attempt."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from threading import Event


class JobExecutionInterrupted(BaseException):
    """The owning worker observed that this execution's lease was lost."""


@dataclass(frozen=True, slots=True)
class JobExecutionInterrupt:
    """Carry one worker-owned signal without implying that all work stopped."""

    job_id: str
    worker_id: str
    attempt: int
    lost: Event

    def __post_init__(self) -> None:
        if not self.job_id or not self.worker_id or self.attempt < 1:
            raise ValueError("job_execution_interrupt_identity_invalid")


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


def raise_if_job_execution_interrupted() -> None:
    """Interrupt the current computation after its worker observed lease loss."""
    current = _CURRENT.get()
    if current is not None and current.lost.is_set():
        raise JobExecutionInterrupted(
            f"lease lost for job {current.job_id} owner {current.worker_id} "
            f"attempt {current.attempt}"
        )
