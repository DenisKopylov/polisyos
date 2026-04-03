"""Canonical ask/tell and funnel contracts plus adapters for legacy search runtimes.

Use these contracts when Layer A code wants to separate candidate proposal,
evaluation feedback, and multi-fidelity routing from concrete controller or
funnel implementations. `LegacySearchServiceAdapter` preserves the old
`SearchController` loop while exposing the same ask/tell surface as newer
services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.search.controller import SearchController, SearchIteration, SearchResult
from polisyos.scientist.search.funnel.orchestrator import (
    FunnelOrchestrator,
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


@dataclass(slots=True)
class LegacySearchServiceAdapter:
    """Wrap the legacy `SearchController` behind a canonical Layer A contract.

    The adapter keeps the existing controller runtime intact while giving Layer B/C
    a contract-first entry point. `run_search()` remains available for workflows
    that still expect a full `SearchResult`.
    """

    controller: SearchController
    _pending_candidates: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _ask_iteration: int = field(default=0, init=False)

    def ask(
        self,
        goal: dict[str, Any] | None,
        search_space: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[CandidateProposal]:
        del goal, search_space
        payloads = self.controller._generate_candidates(  # noqa: SLF001 - intentional adapter bridge
            iteration=self._ask_iteration,
            initial_candidate=None,
            context=context,
        )
        proposals: list[CandidateProposal] = []
        for index, payload in enumerate(payloads):
            candidate_id = (
                str(payload.get("candidate_id"))
                if isinstance(payload, dict) and payload.get("candidate_id")
                else f"candidate_{self._ask_iteration}_{index}"
            )
            self._pending_candidates[candidate_id] = dict(payload)
            proposals.append(
                CandidateProposal(
                    candidate_id=candidate_id,
                    payload=dict(payload),
                    metadata={"iteration": self._ask_iteration},
                )
            )
        self._ask_iteration += 1
        return proposals

    def tell(
        self,
        candidate_id: str,
        evaluation: EvaluationBundle,
    ) -> TellResult:
        candidate = self._pending_candidates.pop(candidate_id, {})
        record = SearchIteration(
            iteration=len(self.controller._history),  # noqa: SLF001 - adapter-managed bridge
            candidate=candidate,
            objective_value=float(evaluation.objective_value),
            objective_details=list(evaluation.objective_details),
            is_promising=bool(evaluation.is_promising),
            stage_a_passed=bool(evaluation.stage_a_passed),
            stage_b_result=evaluation.stage_b_result,
            duration_seconds=float(evaluation.duration_seconds),
            policy_evaluation=evaluation.policy_evaluation,
        )
        self.controller._history.append(record)  # noqa: SLF001 - adapter-managed bridge
        if evaluation.objective_value < self.controller._best_objective:  # noqa: SLF001
            self.controller._best_objective = float(evaluation.objective_value)  # noqa: SLF001
            self.controller._best_candidate = dict(candidate)  # noqa: SLF001
        return TellResult(
            best_candidate=self.controller._best_candidate,  # noqa: SLF001
            best_objective=(
                None
                if self.controller._best_objective == float("inf")  # noqa: SLF001
                else float(self.controller._best_objective)  # noqa: SLF001
            ),
            history_length=len(self.controller._history),  # noqa: SLF001
            registry_update={"search_id": self.controller._search_id},  # noqa: SLF001
            frontier_delta=list(getattr(self.controller, "_pareto_front", [])),
        )

    def run_search(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None = None,
    ) -> SearchResult:
        """Compatibility helper for existing call sites migrating off SearchController."""

        return self.controller.run(
            initial_context=initial_context,
            initial_candidate=initial_candidate,
        )


@dataclass(slots=True)
class OrchestratorFunnelService:
    """Wrap `FunnelOrchestrator` behind the canonical `FunnelService` contract."""

    orchestrator: FunnelOrchestrator

    def submit(
        self,
        candidate: CandidateProposal,
        *,
        context: dict[str, Any] | None = None,
    ) -> FunnelTicket:
        return self.orchestrator.submit(candidate.payload, context or {})

    def get_result(self, ticket: FunnelTicket | str) -> FunnelOutcome:
        outcome = self.orchestrator.get_outcome(ticket)
        if not outcome.completed and outcome.final_result is None:
            return self.orchestrator.advance(ticket, policy="full")
        return outcome


__all__ = [
    "CandidateProposal",
    "EvaluationBundle",
    "FunnelService",
    "LegacySearchServiceAdapter",
    "OrchestratorFunnelService",
    "SearchService",
    "TellResult",
]
