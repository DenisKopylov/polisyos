"""Concrete native service driver for the legacy search lifecycle.

The search contracts are intentionally small.  This module is the internal
bridge that drives the existing owner-owned generation, evaluation, and
run-state transitions through that contract.  It is not a second search
framework: the lifecycle owner owns evaluation semantics and
``SearchRunState`` remains the sole mutable run ledger.
"""

from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from datetime import UTC, datetime
from time import monotonic, sleep
from typing import Any

from polisyos.common import logger as common_logger
from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    EvaluationBundle,
    GenerationNotice,
    GenerationTransition,
    SearchAskRequest,
    SearchResult,
    SearchStatus,
    TellResult,
    _EvaluationDisposition,
    _NativeSearchControllerPort,
)
from polisyos.scientist.methods.search.frontier import (
    _validate_search_ask_argument,
    candidate_payloads_equal,
    materialize_candidate_proposal,
)

logger = common_logger.get_logger(__name__)

_EMPTY_RESPONSE_BACKOFF_SECONDS = 0.01
_EMPTY_RESPONSE_RETRY_WINDOW_SECONDS = 1.0
_TERMINAL_NOTICE_REASONS = {
    GenerationTransition.EXHAUSTED: "generation_source_exhausted",
    GenerationTransition.ATTEMPT_LIMIT: "generation_source_attempt_limit",
    GenerationTransition.REPAIR_REQUIRED: "generation_repair_required",
}


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
        with self.owner._run_operation():
            context, request = self._prepare_search_request(goal, search_space, context)
            return self._ask(context, request=request)

    def _prepare_search_request(
        self,
        goal: dict[str, Any] | None,
        search_space: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], SearchAskRequest | None]:
        if goal is None and search_space is None:
            return context, None
        if not self.owner._supports_explicit_search_request():
            raise ValueError("search_ask_explicit_request_unsupported")
        arguments: dict[str, Any] = {}
        for key, value in (("goal", goal), ("search_space", search_space)):
            if value is None:
                continue
            _validate_search_ask_argument(key, value)
            if key in context:
                try:
                    compatible = candidate_payloads_equal({key: context[key]}, {key: value})
                except (TypeError, ValueError) as error:
                    raise ValueError(f"search_ask_{key}_conflict") from error
                if not compatible:
                    raise ValueError(f"search_ask_{key}_conflict")
            arguments[key] = deepcopy(value)
        request = SearchAskRequest.model_validate(arguments)
        return {**context, **arguments}, request

    def _ask(
        self, context: dict[str, Any], *, request: SearchAskRequest | None
    ) -> list[CandidateProposal]:
        generation, iteration = self.owner._prepare_service_run()
        payloads, notice = self.owner._generate_candidates(
            iteration=iteration,
            initial_candidate=None,
            context=context,
        )
        if notice is not None:
            raise notice

        proposals: list[CandidateProposal] = []
        pending: dict[str, CandidateProposal] = {}
        for index, payload in enumerate(payloads):
            if isinstance(payload, CandidateProposal):
                proposal = deepcopy(payload)
                materialize_candidate_proposal(proposal)
                if (
                    proposal.metadata
                    or proposal.service_iteration is not None
                    or proposal.service_request is not None
                ):
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
            proposal.service_request = deepcopy(request)
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
            previous_generation = self.owner._run_generation
            start_time = datetime.now(UTC)
            try:
                self.owner._begin_native_run(initial_context)
                return self._run_admitted(
                    start_time=start_time,
                    initial_context=initial_context,
                    initial_candidate=initial_candidate,
                )
            except BaseException as error:
                if self.owner._run_generation != previous_generation:
                    self.owner._record_native_interruption(
                        error, start_time=start_time, context=initial_context
                    )
                raise

    def _run_admitted(
        self,
        *,
        start_time: datetime,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None,
    ) -> SearchResult:
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

            deadline = self.owner._run_state.empty_generation_retry_deadline
            if deadline is not None and monotonic() >= deadline:
                stopping_reason = self._reached_empty_limit("generation_retry_deadline")
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
                continue

            self.owner._run_state.empty_generation_attempts = 0
            self.owner._run_state.empty_generation_retry_deadline = None
            stopping_reason = self._evaluate_batch(
                batch=batch,
                generated=generated,
                initial_context=initial_context,
            )
            if stopping_reason is not None:
                break
            transition = self.owner._run_state.generation_transition
            if transition in _TERMINAL_NOTICE_REASONS:
                stopping_reason = _TERMINAL_NOTICE_REASONS[transition]
                self._stop(stopping_reason)
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
        return (
            (stop_check.reason or "search_stopping_criterion_reached")
            if stop_check.should_stop
            else None
        )

    def _prepare_batch(
        self,
        *,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any] | CandidateProposal], bool, str | None]:
        generated = initial_candidate is None
        attempt = self.owner._run_state.track_attempt("generation") if generated else nullcontext()
        with attempt:
            batch, notice = self.owner._generate_candidates(
                iteration=self.owner._run_state.evaluation_iterations,
                initial_candidate=initial_candidate,
                context=initial_context,
            )
        if not generated:
            return batch, False, None

        if notice is not None or not batch:
            state = self.owner._run_state
            state.generation_transition = (
                notice.transition if notice is not None else GenerationTransition.TRANSIENT_EMPTY
            )
            state.generation_source_reason = notice.reason if notice is not None else None
            state.generation_reuse = notice.reuse if notice is not None else None
        stopping_reason = self._stopping_reason(initial_context)
        if stopping_reason is None and not batch:
            stopping_reason = self._empty_generation_stop(notice)
        return batch, True, stopping_reason

    def _empty_generation_stop(self, notice: GenerationNotice | None) -> str | None:
        if notice is not None and notice.transition in _TERMINAL_NOTICE_REASONS:
            return _TERMINAL_NOTICE_REASONS[notice.transition]

        state = self.owner._run_state
        state.empty_generation_attempts += 1
        if state.empty_generation_attempts >= self.owner._config.max_empty_generation_attempts:
            return self._reached_empty_limit("generation_empty_attempt_limit")
        now = monotonic()
        if state.empty_generation_retry_deadline is None:
            state.empty_generation_retry_deadline = now + _EMPTY_RESPONSE_RETRY_WINDOW_SECONDS
        delay = (
            notice.retry_after_seconds if notice is not None else _EMPTY_RESPONSE_BACKOFF_SECONDS
        )
        assert delay is not None
        if now + delay >= state.empty_generation_retry_deadline:
            return self._reached_empty_limit("generation_retry_deadline")
        sleep(delay)
        return None

    def _reached_empty_limit(self, reason: str) -> str:
        self.owner._run_state.generation_transition = GenerationTransition.ATTEMPT_LIMIT
        return reason

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
            with self.owner._run_state.track_attempt("evaluation"):
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
