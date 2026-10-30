"""Trusted process-local child-composition attempt budget owner.

A job lease is renewable and is not an execution deadline. This owner issues one
absolute monotonic cutoff before the handler starts; it never reconstructs one
from wall time after a process restart. This is not monetary authority.
"""

from __future__ import annotations

import math
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _thread import RLock
    from collections.abc import Iterator
    from threading import Event

    from polisyos.common.job_execution_interrupt import JobExecutionInterrupt
    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord


@dataclass(frozen=True)
class ChildExecutionBudgetPolicy:
    """Optional deployment-appointed versioned parent computation duration."""

    policy_id: str
    version: str
    duration_seconds: float

    def __post_init__(self) -> None:
        if (
            type(self.policy_id) is not str
            or not self.policy_id.strip()
            or len(self.policy_id) > 160
            or type(self.version) is not str
            or not self.version.strip()
            or len(self.version) > 160
            or type(self.duration_seconds) not in (int, float)
            or not math.isfinite(self.duration_seconds)
            or self.duration_seconds <= 0
        ):
            raise ValueError("child_execution_budget_policy_invalid")


@dataclass(frozen=True)
class ChildBudgetClaimLocator:
    """Identity of one committed owner budget claim; not itself a grant."""

    job_id: str
    run_id: str
    attempt: int
    worker_id: str
    event_id: int
    policy_id: str
    policy_version: str
    duration_seconds: float


@dataclass(frozen=True)
class _AttemptBudget:
    job_id: str
    run_id: str
    attempt: int
    interrupt: JobExecutionInterrupt
    revoked: Event
    uncertain: Event
    transition_lock: RLock = field(repr=False, compare=False)
    claim: ChildBudgetClaimLocator
    control_store: object = field(repr=False, compare=False)
    policy_id: str
    policy_version: str
    deadline_monotonic: float
    issued_monotonic: float


_CURRENT: ContextVar[_AttemptBudget | None] = ContextVar("child_execution_budget", default=None)


@contextmanager
def _attempt_budget_scope(
    policy: ChildExecutionBudgetPolicy | None,
    job: ControlJobRecord,
    interrupt: JobExecutionInterrupt,
    revoked: Event,
    uncertain: Event,
    *,
    claim: ChildBudgetClaimLocator | None = None,
    control_store: object | None = None,
    issued_monotonic: float | None = None,
    transition_lock: RLock | None = None,
) -> Iterator[None]:
    """Issue once from worker-owned policy, or leave composition unavailable."""
    if _CURRENT.get() is not None:
        raise RuntimeError("child_execution_budget_nested_scope")
    if policy is None or not job.run_id or job.kind != "workflow_run":
        yield
        return
    from polisyos.common.job_execution_interrupt import JobExecutionInterrupt

    if transition_lock is None:
        raise ValueError("child_execution_budget_owner_invalid")
    with transition_lock:
        if (
            type(policy) is not ChildExecutionBudgetPolicy
            or type(claim) is not ChildBudgetClaimLocator
            or control_store is None
            or (
                claim.job_id,
                claim.run_id,
                claim.attempt,
                claim.worker_id,
                claim.policy_id,
                claim.policy_version,
                claim.duration_seconds,
            )
            != (
                job.job_id,
                job.run_id,
                job.attempt,
                job.lease_owner,
                policy.policy_id,
                policy.version,
                float(policy.duration_seconds),
            )
            or type(interrupt) is not JobExecutionInterrupt
            or (interrupt.job_id, interrupt.worker_id, interrupt.attempt)
            != (job.job_id, job.lease_owner, job.attempt)
            or interrupt.lost.is_set()
            or revoked.is_set()
            or uncertain.is_set()
        ):
            raise ValueError("child_execution_budget_owner_invalid")
        now = time.monotonic()
        issued = now if issued_monotonic is None else issued_monotonic
        cutoff = issued + float(policy.duration_seconds)
        if not math.isfinite(issued) or issued > now or not math.isfinite(cutoff) or cutoff <= now:
            raise ValueError("child_execution_budget_deadline_invalid")
        token = _CURRENT.set(
            _AttemptBudget(
                job_id=job.job_id,
                run_id=job.run_id,
                attempt=job.attempt,
                interrupt=interrupt,
                revoked=revoked,
                uncertain=uncertain,
                transition_lock=transition_lock,
                claim=claim,
                control_store=control_store,
                policy_id=policy.policy_id,
                policy_version=policy.version,
                deadline_monotonic=cutoff,
                issued_monotonic=issued,
            )
        )
    try:
        yield
    finally:
        with transition_lock:
            revoked.set()
        _CURRENT.reset(token)


def _require_attempt_budget(job_id: str, run_id: str, attempt: int) -> _AttemptBudget:
    """Reconcile the active job attempt and refuse absent, stale or elapsed budgets."""
    budget = _CURRENT.get()
    if type(budget) is not _AttemptBudget:
        raise RuntimeError("child_execution_budget_unavailable")
    with budget.transition_lock:
        if (
            (budget.job_id, budget.run_id, budget.attempt) != (job_id, run_id, attempt)
            or budget.interrupt.lost.is_set()
            or budget.revoked.is_set()
            or budget.uncertain.is_set()
            or time.monotonic() >= budget.deadline_monotonic
        ):
            raise RuntimeError("child_execution_budget_unavailable")
        return budget
