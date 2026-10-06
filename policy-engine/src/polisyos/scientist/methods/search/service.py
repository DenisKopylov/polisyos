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
from polisyos.scientist.methods.search.stopping import _stopping_limitations
from polisyos.scientist.methods.search.strategies.errors import StrategyError

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
            if "candidate_id" not in payload:
                candidate_id = f"candidate_{self._ask_iteration}_{index}"
            else:
                raw_candidate_id = payload["candidate_id"]
                if not isinstance(raw_candidate_id, str) or not raw_candidate_id:
                    raise ValueError("search candidate_id must be an explicit non-empty string")
                candidate_id = raw_candidate_id
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
        candidate_to_seed = initial_candidate

        while (
            self.controller._run_state.evaluation_iterations
            < self.controller._config.max_iterations_hard_limit
        ):
            stopping_reason = self._stopping_reason(initial_context)
            if stopping_reason is not None:
                self._stop(stopping_reason)
                break

            try:
                batch, generated, stopping_reason = self._prepare_batch(
                    initial_context=initial_context,
                    initial_candidate=candidate_to_seed,
                )
            except StrategyError as exc:
                stopping_reason = f"candidate_generation_unavailable: {exc}"
                self._stop(stopping_reason)
                break
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

        return self.controller._finish_native_run(
            start_time=start_time,
            stopping_reason=stopping_reason,
        )

    def _stopping_reason(self, context: dict[str, Any]) -> str | None:
        self.controller._refresh_budget_snapshot(context)
        stop_check = self.controller._config.stopping.check(
            [self.controller._to_history_dict(item) for item in self.controller._history],
            self.controller._stopping_state(),
        )
        for limitation in _stopping_limitations(self.controller._config.stopping.name, stop_check):
            if limitation not in self.controller._run_state.stopping_limitations:
                self.controller._run_state.stopping_limitations.append(deepcopy(limitation))
        return stop_check.reason if stop_check.should_stop else None

    def _prepare_batch(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any]], bool, str | None]:
        generated = initial_candidate is None
        batch = self.controller._generate_candidates(
            iteration=self.controller._run_state.evaluation_iterations,
            initial_candidate=initial_candidate,
            context=initial_context,
        )
        if not generated:
            return batch, False, None

        self.controller._run_state.generation_attempts += 1
        stopping_reason = self._stopping_reason(initial_context)
        return batch, True, stopping_reason

    def _handle_empty_generation(self) -> str | None:
        self.controller._run_state.empty_generation_attempts += 1
        if (
            self.controller._run_state.empty_generation_attempts
            < self.controller._config.max_empty_generation_attempts
        ):
            return None
        self.controller._run_state.generation_transition = GenerationTransition.EXHAUSTED
        self._stop("generation_exhausted")
        return "generation_exhausted"

    def _mark_nonempty_generation(self) -> None:
        if self.controller._run_state.empty_generation_attempts:
            self.controller._run_state.generation_transition = GenerationTransition.TRANSIENT_EMPTY
            self.controller._run_state.empty_generation_attempts = 0

    def _evaluate_batch(
        self,
        *,
        batch: list[dict[str, Any]],
        generated: bool,
        initial_context: dict[str, Any],
    ) -> str | None:
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

            if transition.disposition is _EvaluationDisposition.SENTINEL and not generated:
                self._stop("Initial sentinel evaluated")
                return "Initial sentinel evaluated"

            stopping_reason = self._stopping_reason(initial_context)
            if stopping_reason is not None:
                self._stop(stopping_reason)
                return stopping_reason
        return None

    def _stop(self, reason: str) -> None:
        self.controller._status = SearchStatus.STOPPED
        logger.info("Stopping: %s", reason)


__all__ = ["_NativeSearchServiceDriver"]
