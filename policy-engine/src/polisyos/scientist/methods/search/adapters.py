"""Concrete bridges from search contracts to legacy runtime owners.

The DTOs and protocols stay in :mod:`contracts`; this module is the only
place where those contracts are connected to the legacy controller and funnel
implementations.  The adapter deliberately delegates evaluation acceptance to
the controller's state-owner seam instead of editing controller compatibility
views itself.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    EvaluationBundle,
    TellResult,
)
from polisyos.scientist.methods.search.controller import SearchController, SearchResult
from polisyos.scientist.methods.search.funnel.orchestrator import (
    FunnelOrchestrator,
    FunnelOutcome,
    FunnelTicket,
)


@dataclass(slots=True)
class LegacySearchServiceAdapter:
    """Expose the legacy controller through the ask/tell service contract.

    ``SearchController`` remains the owner of run state and compatibility
    behavior.  Candidate IDs are leases: an ID must have been returned by
    ``ask`` exactly once before it can be submitted to ``tell``.  This keeps
    unknown and duplicate feedback from creating synthetic history entries.
    """

    controller: SearchController
    _pending_candidates: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _completed_candidate_ids: set[str] = field(default_factory=set, init=False)
    _ask_iteration: int = field(default=0, init=False)

    def ask(
        self,
        goal: dict[str, Any] | None,
        search_space: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[CandidateProposal]:
        """Generate proposals and retain their candidate-ID ownership."""
        del goal, search_space
        self.controller._prepare_service_run()
        payloads = self.controller._generate_candidates(
            iteration=self._ask_iteration,
            initial_candidate=None,
            context=context,
        )

        proposals: list[CandidateProposal] = []
        pending: dict[str, dict[str, Any]] = {}
        for index, payload in enumerate(payloads):
            if not isinstance(payload, dict):
                raise TypeError("search candidate generators must return mappings")
            candidate_id = (
                str(payload.get("candidate_id"))
                if payload.get("candidate_id")
                else f"candidate_{self._ask_iteration}_{index}"
            )
            if (
                candidate_id in pending
                or candidate_id in self._pending_candidates
                or candidate_id in self._completed_candidate_ids
            ):
                raise ValueError(f"duplicate search candidate id: {candidate_id}")
            candidate = deepcopy(payload)
            pending[candidate_id] = candidate
            proposals.append(
                CandidateProposal(
                    candidate_id=candidate_id,
                    payload=deepcopy(candidate),
                    metadata={"iteration": self._ask_iteration},
                )
            )

        self._pending_candidates.update(pending)
        self._ask_iteration += 1
        return proposals

    def tell(
        self,
        candidate_id: str,
        evaluation: EvaluationBundle,
    ) -> TellResult:
        """Accept one previously asked evaluation through the state owner.

        The adapter does not infer a candidate for an unknown ID and does not
        permit a second transition for an already completed ID.  Typed
        evaluation presence is forwarded to the controller unchanged so the
        B123 absent-versus-invalid distinction remains authoritative there.
        """
        if not isinstance(candidate_id, str) or not candidate_id:
            raise KeyError(candidate_id)
        if candidate_id in self._completed_candidate_ids:
            raise ValueError(f"duplicate search evaluation: {candidate_id}")
        if candidate_id not in self._pending_candidates:
            raise KeyError(candidate_id)

        candidate = deepcopy(self._pending_candidates[candidate_id])
        stage_b_result = self._stage_b_result(evaluation)
        self.controller._accept_tell(
            candidate=candidate,
            objective_value=float(evaluation.objective_value),
            objective_details=list(evaluation.objective_details),
            is_promising=bool(evaluation.is_promising),
            stage_a_passed=bool(evaluation.stage_a_passed),
            stage_b_result=stage_b_result,
            duration_seconds=float(evaluation.duration_seconds),
        )

        del self._pending_candidates[candidate_id]
        self._completed_candidate_ids.add(candidate_id)
        return TellResult(**self.controller._service_tell_snapshot())

    @staticmethod
    def _stage_b_result(evaluation: EvaluationBundle) -> dict[str, Any]:
        """Build a controller-shaped result without changing typed payloads."""
        stage_b_result = deepcopy(evaluation.stage_b_result or {})
        simulation_results = stage_b_result.get("simulation_results")
        if simulation_results is None:
            stage_b_result["simulation_results"] = {
                "objective_value": float(evaluation.objective_value),
            }
        elif not isinstance(simulation_results, dict):
            raise TypeError("EvaluationBundle.stage_b_result.simulation_results must be a mapping")

        feedback = stage_b_result.get("feedback")
        if feedback is None:
            stage_b_result["feedback"] = {
                "verdict": "APPROVE" if evaluation.is_promising else "REJECT",
            }
        elif not isinstance(feedback, dict):
            raise TypeError("EvaluationBundle.stage_b_result.feedback must be a mapping")
        else:
            feedback.setdefault(
                "verdict",
                "APPROVE" if evaluation.is_promising else "REJECT",
            )

        if evaluation.policy_evaluation is not None:
            stage_b_result.setdefault("policy_evaluation", evaluation.policy_evaluation)
        return stage_b_result

    def run_search(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None = None,
    ) -> SearchResult:
        """Run the compatibility loop with the controller's established semantics."""
        self._pending_candidates.clear()
        self._completed_candidate_ids.clear()
        self._ask_iteration = 0
        return self.controller.run(
            initial_context=initial_context,
            initial_candidate=initial_candidate,
        )


@dataclass(slots=True)
class OrchestratorFunnelService:
    """Wrap ``FunnelOrchestrator`` behind the canonical funnel contract."""

    orchestrator: FunnelOrchestrator

    def submit(
        self,
        candidate: CandidateProposal,
        *,
        context: dict[str, Any] | None = None,
    ) -> FunnelTicket:
        """Submit one proposal to the existing multi-fidelity orchestrator."""
        return self.orchestrator.submit(candidate.payload, context or {})

    def get_result(self, ticket: FunnelTicket | str) -> FunnelOutcome:
        """Return a completed outcome, advancing the existing ticket if needed."""
        outcome = self.orchestrator.get_outcome(ticket)
        if not outcome.completed and outcome.final_result is None:
            return self.orchestrator.advance(ticket, policy="full")
        return outcome


__all__ = [
    "LegacySearchServiceAdapter",
    "OrchestratorFunnelService",
]
