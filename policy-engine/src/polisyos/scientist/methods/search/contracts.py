"""Canonical ask/tell and funnel contracts for search runtimes.

This module intentionally contains only DTOs and protocols.  The concrete
bridges for the legacy controller and funnel live in :mod:`adapters` and are
resolved lazily for the historical imports that remain part of the supported
surface.  Keeping the bridge out of this module makes contract-only imports
safe for planners and import-boundary checks.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from polisyos.scientist.methods.search.funnel.orchestrator import (
        FunnelOutcome,
        FunnelTicket,
    )


class CandidateProposal(BaseModel):
    """Carry one candidate proposal and metadata across service boundaries."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationBundle(BaseModel):
    """Capture evaluator feedback returned by Stage A/B and promotion scoring."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    objective_value: float
    is_promising: bool
    stage_a_passed: bool = True
    stage_b_result: dict[str, Any] | None = None
    duration_seconds: float = 0.0
    objective_details: list[Any] = Field(default_factory=list)
    policy_evaluation: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TellResult(BaseModel):
    """Return registry/frontier deltas and current-best feedback after `tell()`."""

    model_config = ConfigDict(extra="forbid")

    best_candidate: dict[str, Any] | None = None
    best_objective: float | None = None
    history_length: int = 0
    registry_update: dict[str, Any] = Field(default_factory=dict)
    lesson_cards: list[dict[str, Any]] = Field(default_factory=list)
    frontier_delta: list[dict[str, Any]] = Field(default_factory=list)


class SearchService(Protocol):
    """Expose candidate generation (`ask`) and evaluator feedback ingestion (`tell`)."""

    def ask(
        self,
        goal: dict[str, Any] | None,
        search_space: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[CandidateProposal]: ...

    def tell(
        self,
        candidate_id: str,
        evaluation: EvaluationBundle,
    ) -> TellResult: ...


class FunnelService(Protocol):
    """Submit candidates to a multi-fidelity funnel and fetch routed outcomes."""

    def submit(
        self,
        candidate: CandidateProposal,
        *,
        context: dict[str, Any] | None = None,
    ) -> FunnelTicket: ...

    def get_result(self, ticket: FunnelTicket | str) -> FunnelOutcome: ...


_LAZY_ADAPTER_EXPORTS = frozenset(
    {
        "LegacySearchServiceAdapter",
        "OrchestratorFunnelService",
    }
)


def __getattr__(name: str) -> Any:
    """Resolve legacy bridge names without importing runtime implementations eagerly."""
    if name in _LAZY_ADAPTER_EXPORTS:
        module = importlib.import_module("polisyos.scientist.methods.search.adapters")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CandidateProposal",
    "EvaluationBundle",
    "FunnelService",
    "LegacySearchServiceAdapter",
    "OrchestratorFunnelService",
    "SearchService",
    "TellResult",
]
