"""Rollback compensation hooks for Scientist workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from polisyos.scientist.engine.state import ExperimentState

__all__ = [
    "RollbackCompensationEvent",
    "RollbackCompensationHook",
]


@dataclass(frozen=True)
class RollbackCompensationEvent:
    """Structured rollback event emitted when a tier savepoint is restored."""

    run_id: str
    workflow_id: str
    tier_index: int
    failed_aliases: tuple[str, ...]
    completed_before_tier: tuple[str, ...]
    reason: str


class RollbackCompensationHook(Protocol):
    """Optional hook for saga-style rollback compensation."""

    def on_tier_rollback(
        self,
        *,
        event: RollbackCompensationEvent,
        restored_state: ExperimentState,
    ) -> None: ...
