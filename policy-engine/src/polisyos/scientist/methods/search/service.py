"""Concrete native service driver for the legacy search lifecycle.

The search contracts are intentionally small.  This module is the internal
bridge that drives the existing controller-owned generation, evaluation, and
run-state transitions through that contract.  It is not a second search
framework: the controller remains the owner of evaluation semantics and
``SearchRunState`` remains the sole mutable run ledger.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    EvaluationBundle,
    TellResult,
)
from polisyos.scientist.methods.search.controller import (
    SearchController,
    SearchResult,
    SearchStatus,
)
from polisyos.scientist.methods.search.run_state import (
    GenerationTransition,
    _EvaluationDisposition,
)

logger = get_logger(__name__)


class _NativeSearchServiceDriver:
    """Drive one controller lifecycle through the native service boundary.

    The ask/tell methods are the concrete implementation of the existing
    ``SearchService`` protocol.  ``run_search`` uses the same methods' owner
    seams and the controller's established evaluator path, so the autotune
    consumer no longer calls the legacy full-loop implementation directly.
    """

    def __init__(self, controller: SearchController) -> None:
        self.controller = controller
        self._pending_candidates: dict[str, dict[str, Any]] = {}
        self._completed_candidate_ids: set[str] = set()
        self._ask_iteration = 0

    def ask(
        self,
        goal: dict[str, Any] | None,
        search_space: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[CandidateProposal]:
        """Generate proposals and retain candidate-ID ownership for ``tell``."""
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
        """Accept one previously asked evaluation through controller state."""
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
            raise TypeError(
                "EvaluationBundle.stage_b_result.simulation_results must be a mapping"
            )

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
        """Run the existing generation/evaluation lifecycle through this driver."""
        self._pending_candidates.clear()
        self._completed_candidate_ids.clear()
        self._ask_iteration = 0

        run_lock = self.controller._run_lock
        if not run_lock.acquire(blocking=False):
            raise RuntimeError("SearchController.run is not reentrant")
        try:
            return self._run_locked(
                initial_context=initial_context,
                initial_candidate=initial_candidate,
            )
        finally:
            run_lock.release()

    def _run_locked(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None,
    ) -> SearchResult:
        start_time = self.controller._begin_native_run(initial_context)
        stopping_reason: str | None = None
        initial_candidate_pending = initial_candidate is not None

        while (
            self.controller._run_state.evaluation_iterations
            < self.controller._config.max_iterations_hard_limit
        ):
            self.controller._refresh_budget_snapshot(initial_context)
            stop_check = self.controller._config.stopping.check(
                [self.controller._to_history_dict(item) for item in self.controller._history],
                self.controller._stopping_state(),
            )
            if stop_check.should_stop:
                stopping_reason = stop_check.reason
                self.controller._status = SearchStatus.STOPPED
                logger.info("Stopping: %s", stopping_reason)
                break

            batch = self.controller._generate_candidates(
                iteration=self.controller._run_state.evaluation_iterations,
                initial_candidate=(
                    initial_candidate if initial_candidate_pending else None
                ),
                context=initial_context,
            )
            generated = not initial_candidate_pending
            initial_candidate_pending = False
            if generated:
                self.controller._run_state.generation_attempts += 1
                self.controller._refresh_budget_snapshot(initial_context)
                generation_stop = self.controller._config.stopping.check(
                    [
                        self.controller._to_history_dict(item)
                        for item in self.controller._history
                    ],
                    self.controller._stopping_state(),
                )
                if generation_stop.should_stop:
                    stopping_reason = generation_stop.reason
                    self.controller._status = SearchStatus.STOPPED
                    logger.info("Stopping: %s", stopping_reason)
                    break

            if not batch:
                self.controller._run_state.empty_generation_attempts += 1
                if (
                    self.controller._run_state.empty_generation_attempts
                    >= self.controller._config.max_empty_generation_attempts
                ):
                    self.controller._run_state.generation_transition = (
                        GenerationTransition.EXHAUSTED
                    )
                    stopping_reason = "generation_exhausted"
                    self.controller._status = SearchStatus.STOPPED
                    logger.info("Stopping: generation exhausted")
                    break
                continue

            if self.controller._run_state.empty_generation_attempts:
                self.controller._run_state.generation_transition = (
                    GenerationTransition.TRANSIENT_EMPTY
                )
                self.controller._run_state.empty_generation_attempts = 0

            for candidate in batch:
                if (
                    self.controller._run_state.evaluation_iterations
                    >= self.controller._config.max_iterations_hard_limit
                ):
                    break
                transition = self.controller._evaluate_candidate(
                    candidate,
                    iteration=self.controller._run_state.evaluation_iterations,
                    context=initial_context,
                )
                self.controller._run_state.apply_evaluation_transition(transition)
                self.controller._refresh_budget_snapshot(initial_context)

                if (
                    transition.disposition is _EvaluationDisposition.SENTINEL
                    and not generated
                ):
                    self.controller._status = SearchStatus.STOPPED
                    stopping_reason = "Initial sentinel evaluated"
                    break

                stop_check = self.controller._config.stopping.check(
                    [
                        self.controller._to_history_dict(item)
                        for item in self.controller._history
                    ],
                    self.controller._stopping_state(),
                )
                if stop_check.should_stop:
                    stopping_reason = stop_check.reason
                    self.controller._status = SearchStatus.STOPPED
                    logger.info("Stopping: %s", stopping_reason)
                    break

            if self.controller._status == SearchStatus.STOPPED:
                break

        return self.controller._finish_native_run(
            start_time=start_time,
            stopping_reason=stopping_reason,
        )


__all__ = ["_NativeSearchServiceDriver"]
