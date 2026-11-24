"""Concrete native service driver for the legacy search lifecycle.

The search contracts are intentionally small.  This module is the internal
bridge that drives the existing owner-owned generation, evaluation, and
run-state transitions through that contract.  It is not a second search
framework: the lifecycle owner owns evaluation semantics and
``SearchRunState`` remains the sole mutable run ledger.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from polisyos.common import logger as common_logger
from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    EvaluationBundle,
    GenerationTransition,
    SearchResult,
    SearchStatus,
    TellResult,
    _EvaluationDisposition,
    _NativeSearchControllerPort,
)
from polisyos.scientist.methods.search.frontier import materialize_candidate_proposal

logger = common_logger.get_logger(__name__)


class _NativeSearchServiceDriver:
    """Drive one search lifecycle through the native service boundary.

    The ask/tell methods are the concrete implementation of the existing
    ``SearchService`` protocol.  ``run_search`` uses the same methods' owner
    seams and the owner's established evaluator path, so the autotune
    consumer no longer calls the legacy full-loop implementation directly.
    The owner refuses overlapping calls, including reentry from an evaluator.
    """

    def __init__(self, lifecycle_owner: _NativeSearchControllerPort) -> None:
        self.owner = lifecycle_owner
        self._issued_generations: dict[str, int] = {}

    def ask(
        self,
        goal: dict[str, Any] | None,
        search_space: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[CandidateProposal]:
        """Generate proposals for the current owner generation."""
        del goal, search_space
        with self.owner._run_operation():
            return self._ask(context)

    def _ask(self, context: dict[str, Any]) -> list[CandidateProposal]:
        generation, iteration = self.owner._prepare_service_run()
        payloads = self.owner._generate_candidates(
            iteration=iteration,
            initial_candidate=None,
            context=context,
        )

        proposals: list[CandidateProposal] = []
        pending: dict[str, CandidateProposal] = {}
        for index, payload in enumerate(payloads):
            if isinstance(payload, CandidateProposal):
                proposal = deepcopy(payload)
                materialize_candidate_proposal(proposal)
                if proposal.metadata or proposal.service_iteration is not None:
                    raise ValueError("candidate_service_context_already_present")
                proposal.metadata = {"iteration": iteration}
                proposal.service_iteration = iteration
            else:
                if not isinstance(payload, dict):
                    raise TypeError("search candidate generators must return mappings")
                if "candidate_id" in payload:
                    candidate_id = payload["candidate_id"]
                    if not isinstance(candidate_id, str) or not candidate_id:
                        raise ValueError("search candidate_id must be an explicit non-empty string")
                else:
                    candidate_id = f"candidate_{iteration}_{index}"
                    if self._issued_generations.get(candidate_id, generation) != generation:
                        base_id = f"{candidate_id}_run_{generation}"
                        candidate_id = base_id
                        suffix = 1
                        while candidate_id in self._issued_generations or candidate_id in pending:
                            candidate_id = f"{base_id}_{suffix}"
                            suffix += 1
                proposal = CandidateProposal(
                    candidate_id=candidate_id,
                    payload=deepcopy(payload),
                    metadata={"iteration": iteration},
                    service_iteration=iteration,
                )
            materialize_candidate_proposal(proposal)
            candidate_id = proposal.candidate_id
            if candidate_id in pending:
                raise ValueError(f"duplicate search candidate id: {candidate_id}")
            previous_generation = self._issued_generations.get(candidate_id)
            if previous_generation is not None and previous_generation != generation:
                # A bare tell ID cannot distinguish two generations issued by this adapter.
                raise ValueError(
                    f"candidate ID was issued in an earlier search generation: {candidate_id}"
                )
            pending[candidate_id] = proposal
            proposals.append(deepcopy(proposal))

        self.owner._publish_service_proposals(generation, pending)
        self._issued_generations.update(dict.fromkeys(pending, generation))
        return proposals

    def tell(
        self,
        candidate_id: str,
        evaluation: EvaluationBundle,
    ) -> TellResult:
        """Accept an evaluation using its issued generation and the owner's claim."""
        if not isinstance(candidate_id, str) or not candidate_id:
            raise KeyError(candidate_id)
        with self.owner._run_operation():
            generation = self._issued_generations[candidate_id]
            with self.owner._claim_service_tell(candidate_id, generation) as proposal:
                self.owner._accept_tell(
                    generation=generation,
                    candidate_proposal=proposal,
                    is_promising=bool(evaluation.is_promising),
                    stage_a_passed=bool(evaluation.stage_a_passed),
                    stage_b_result=self._stage_b_result(evaluation),
                    duration_seconds=float(evaluation.duration_seconds),
                )
            return TellResult(**self.owner._service_tell_snapshot())

    @staticmethod
    def _stage_b_result(evaluation: EvaluationBundle) -> dict[str, Any]:
        """Build a service-shaped result without changing typed payloads."""
        stage_b_result = deepcopy(evaluation.stage_b_result or {})
        simulation_results = stage_b_result.get("simulation_results")
        if simulation_results is None:
            stage_b_result["simulation_results"] = (
                {"objective_value": evaluation.objective_value}
                if evaluation.objective_value is not None
                else {}
            )
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

        stage_b_result["feedback"].setdefault(
            "objective_score_status", evaluation.score_status.value
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
        """Run the existing generation/evaluation lifecycle through this driver."""
        with self.owner._run_operation(full_run=True):
            return self._run_admitted(
                initial_context=initial_context,
                initial_candidate=initial_candidate,
            )

    def _run_admitted(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None,
    ) -> SearchResult:
        start_time = self.owner._begin_native_run(initial_context)
        stopping_reason: str | None = None
        candidate_to_seed = initial_candidate

        while (
            self.owner._run_state.evaluation_iterations
            < self.owner._config.max_iterations_hard_limit
        ):
            stopping_reason = self._stopping_reason(initial_context)
            if stopping_reason is not None:
                self._stop(stopping_reason)
                break

            batch, generated, stopping_reason = self._prepare_batch(
                initial_context=initial_context,
                initial_candidate=candidate_to_seed,
            )
            candidate_to_seed = None
            if stopping_reason is not None:
                self._stop(stopping_reason)
                break

            if not batch:
                stopping_reason = self._handle_empty_generation()
                if stopping_reason is not None:
                    break
                continue

            self._mark_nonempty_generation()
            stopping_reason = self._evaluate_batch(
                batch=batch,
                generated=generated,
                initial_context=initial_context,
            )
            if stopping_reason is not None:
                break

        return self.owner._finish_native_run(
            start_time=start_time,
            stopping_reason=stopping_reason,
        )

    def _stopping_reason(self, context: dict[str, Any]) -> str | None:
        self.owner._refresh_budget_snapshot(context)
        stop_check = self.owner._config.stopping.check(
            [self.owner._to_history_dict(item) for item in self.owner._history],
            self.owner._stopping_state(),
        )
        return stop_check.reason if stop_check.should_stop else None

    def _prepare_batch(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any] | CandidateProposal], bool, str | None]:
        generated = initial_candidate is None
        batch = self.owner._generate_candidates(
            iteration=self.owner._run_state.evaluation_iterations,
            initial_candidate=initial_candidate,
            context=initial_context,
        )
        if not generated:
            return batch, False, None

        self.owner._run_state.generation_attempts += 1
        stopping_reason = self._stopping_reason(initial_context)
        return batch, True, stopping_reason

    def _handle_empty_generation(self) -> str | None:
        self.owner._run_state.empty_generation_attempts += 1
        if (
            self.owner._run_state.empty_generation_attempts
            < self.owner._config.max_empty_generation_attempts
        ):
            return None
        self.owner._run_state.generation_transition = GenerationTransition.EXHAUSTED
        self._stop("generation_exhausted")
        return "generation_exhausted"

    def _mark_nonempty_generation(self) -> None:
        if self.owner._run_state.empty_generation_attempts:
            self.owner._run_state.generation_transition = GenerationTransition.TRANSIENT_EMPTY
            self.owner._run_state.empty_generation_attempts = 0

    def _evaluate_batch(
        self,
        *,
        batch: list[dict[str, Any] | CandidateProposal],
        generated: bool,
        initial_context: dict[str, Any],
    ) -> str | None:
        for candidate in batch:
            if (
                self.owner._run_state.evaluation_iterations
                >= self.owner._config.max_iterations_hard_limit
            ):
                break
            transition = self.owner._evaluate_candidate(
                candidate,
                iteration=self.owner._run_state.evaluation_iterations,
                context=initial_context,
            )
            self.owner._run_state.apply_evaluation_transition(transition)
            self.owner._refresh_budget_snapshot(initial_context)

            if transition.disposition is _EvaluationDisposition.SENTINEL and not generated:
                self._stop("Initial sentinel evaluated")
                return "Initial sentinel evaluated"

            stopping_reason = self._stopping_reason(initial_context)
            if stopping_reason is not None:
                self._stop(stopping_reason)
                return stopping_reason
        return None

    def _stop(self, reason: str) -> None:
        self.owner._status = SearchStatus.STOPPED
        logger.info("Stopping: %s", reason)


__all__ = ["_NativeSearchServiceDriver"]
