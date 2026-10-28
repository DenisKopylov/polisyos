"""Internal lifecycle owner for the existing search runtime."""

from __future__ import annotations

import os
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from math import isfinite
from threading import Lock
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from polisyos.scientist.methods.search.contracts import (
    CandidatePayload,
    CandidateProposal,
    EvaluationBundle,
    SearchIteration,
    SearchResult,
    SearchStatus,
    StageAEvaluator,
    StageBEvaluator,
    _EvaluationDisposition,
    _EvaluationTransition,
    _SearchEvaluatorPorts,
    _SearchLifecycleConfig,
)
from polisyos.scientist.methods.search.contracts import (
    _SearchCandidateGenerator as CandidateGenerator,
)
from polisyos.scientist.methods.search.frontier import (
    candidate_payloads_equal,
    dominates,
    funnel_prior_ticket_id,
    invoke_candidate_evaluator,
    materialize_candidate_proposal,
    policy_candidate_hash,
    update_legacy_pareto_front,
)
from polisyos.scientist.methods.search.lifecycle_support import (
    _IMPORT_ERRORS,
    _SEARCH_DEGRADED_ERRORS,
    _as_bool,
    _default_metrics,
    _PolicyEvaluationResolution,
    _search_degraded,
)
from polisyos.scientist.methods.search.lifecycle_support import (
    logger as controller_logger,
)
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreAdmission,
    ObjectiveScoreAssessment,
    ObjectiveScoreStatus,
    ObjectiveValue,
    reconcile_objective_score_assessment,
    score_assessment_matches_source,
    selected_score_admission_status,
)
from polisyos.scientist.methods.search.run_state import SearchRunState
from polisyos.scientist.methods.search.sentinels import extract_sentinel_metadata

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry
    from polisyos.scientist.methods.search.frontier import FrontierPoint
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector


class _SearchLifecycleOwner:
    """Own configuration, evaluation, mutable state, and run flow for search.

    Candidate generation is delegated to `CandidateGenerator`, evaluator feedback
    is captured in `SearchIteration`, optional transfer/Pareto/diversity state is
    injected into generation context, and stopping criteria terminate the loop.
    `run()` is intentionally non-reentrant; overlapping calls on one lifecycle owner
    raise a deterministic `RuntimeError` before replacing run state.
    """

    def __init__(
        self,
        config: _SearchLifecycleConfig,
        candidate_generator: CandidateGenerator,
        stage_a_evaluator: StageAEvaluator | None = None,
        stage_b_evaluator: StageBEvaluator | None = None,
        *,
        evaluators: _SearchEvaluatorPorts | None = None,
        metrics: MetricsRegistry | None = None,
        metrics_factory: Callable[[], MetricsRegistry] | None = None,
        bound_owner_validator: Callable[[CandidateGenerator, Any, Any], None] | None = None,
    ) -> None:
        self._config = config
        self._generator = candidate_generator
        if config.producer_settlement_store is not None:
            assert config.producer_run_binding is not None
            if bound_owner_validator is None:
                raise ValueError("protected search requires a bound-owner validator")
            bound_owner_validator(
                candidate_generator,
                config.producer_settlement_store,
                config.producer_run_binding,
            )
        if evaluators is not None:
            if stage_a_evaluator is not None or stage_b_evaluator is not None:
                raise ValueError(
                    "Pass either SearchEvaluatorPorts or legacy evaluator arguments, not both"
                )
            stage_a_evaluator = evaluators.stage_a
            stage_b_evaluator = evaluators.stage_b
        if stage_a_evaluator is None or stage_b_evaluator is None:
            raise ValueError("SearchController requires Stage A and Stage B evaluators")
        self._stage_a = stage_a_evaluator
        self._stage_b = stage_b_evaluator

        self._run_lock = Lock()
        self._run_state = SearchRunState(status=SearchStatus.NOT_STARTED)
        self._source_budget_snapshot: dict[str, Any] = {"status": "not_configured"}
        self._metrics = metrics if metrics is not None else (metrics_factory or _default_metrics)()
        self._diversity_enabled = _as_bool(
            os.getenv("POLISYOS_SEARCH_DIVERSITY_ENABLED"),
            default=False,
        )
        self._diversity_tracker = None
        self._reset_diversity_tracker(operation="initialize_diversity_tracker")

    def _reset_diversity_tracker(self, *, operation: str) -> None:
        """Allocate fresh optional diversity telemetry for one lifecycle."""
        if not self._diversity_enabled:
            self._diversity_tracker = None
            return
        try:
            from polisyos.scientist.methods.search.diversity import DiversityTracker
        except _IMPORT_ERRORS as exc:
            _search_degraded(
                operation=operation,
                reason="optional_dependency_unavailable",
                exc=exc,
            )
            self._diversity_enabled = False
            self._diversity_tracker = None
        else:
            self._diversity_tracker = DiversityTracker()

    @property
    def _history(self) -> list[SearchIteration]:
        """Compatibility view onto the current run-state history."""
        return self._run_state.history

    @_history.setter
    def _history(self, value: list[SearchIteration]) -> None:
        self._run_state.history = value

    @property
    def _best_candidate(self) -> dict[str, Any] | None:
        """Compatibility view onto the current run-state champion."""
        return self._run_state.best_candidate

    @_best_candidate.setter
    def _best_candidate(self, value: dict[str, Any] | None) -> None:
        self._run_state.best_candidate = value

    @property
    def _best_objective(self) -> float:
        """Compatibility view onto the current run-state objective."""
        return self._run_state.best_objective

    @_best_objective.setter
    def _best_objective(self, value: float) -> None:
        self._run_state.best_objective = value

    @property
    def _status(self) -> SearchStatus:
        """Compatibility view onto the current run-state status."""
        return cast("SearchStatus", self._run_state.status)

    @_status.setter
    def _status(self, value: SearchStatus) -> None:
        self._run_state.status = value

    @property
    def _search_id(self) -> str:
        """Compatibility view onto the current run identity."""
        return self._run_state.search_id

    @_search_id.setter
    def _search_id(self, value: str) -> None:
        self._run_state.search_id = value

    @property
    def _pareto_front(self) -> list[dict[str, Any]]:
        """Compatibility view onto the current run frontier."""
        return self._run_state.pareto_front

    @_pareto_front.setter
    def _pareto_front(self, value: list[dict[str, Any]]) -> None:
        self._run_state.pareto_front = value

    @property
    def _pareto_points(self) -> list[FrontierPoint]:
        """Compatibility view onto the current run frontier points."""
        return self._run_state.pareto_points

    @_pareto_points.setter
    def _pareto_points(self, value: list[FrontierPoint]) -> None:
        self._run_state.pareto_points = value

    @property
    def _stage_a_count(self) -> int:
        """Compatibility view onto Stage A evaluation count."""
        return self._run_state.stage_a_evaluations

    @_stage_a_count.setter
    def _stage_a_count(self, value: int) -> None:
        self._run_state.stage_a_evaluations = value

    @property
    def _stage_b_count(self) -> int:
        """Compatibility view onto Stage B evaluation count."""
        return self._run_state.stage_b_evaluations

    @_stage_b_count.setter
    def _stage_b_count(self, value: int) -> None:
        self._run_state.stage_b_evaluations = value

    @property
    def _sentinel_evaluations(self) -> int:
        """Compatibility view onto sentinel evaluation count."""
        return self._run_state.sentinel_evaluations

    @_sentinel_evaluations.setter
    def _sentinel_evaluations(self, value: int) -> None:
        self._run_state.sentinel_evaluations = value

    def _prepare_service_run(self) -> None:
        """Ensure the ask/tell bridge has one explicit run-state owner.

        The compatibility ``run()`` path always starts a fresh state.  The
        contract adapter, however, may receive several ask/tell transitions
        before a full loop is invoked.  This small owner operation gives that
        path a stable search identity and makes a later ask an explicit
        continuation of the same state rather than an accidental new ledger.
        """
        if self._run_state.status in {None, SearchStatus.NOT_STARTED}:
            self._run_state = SearchRunState(
                search_id=str(uuid4())[:8],
                status=SearchStatus.RUNNING,
            )
            self._config.stopping.reset()
            self._reset_diversity_tracker(operation="prepare_service_run")
            return
        if self._run_state.status is not SearchStatus.RUNNING:
            self._run_state.status = SearchStatus.RUNNING

    def _accept_tell(
        self,
        *,
        candidate: CandidatePayload,
        objective_value: float | None,
        score_status: ObjectiveScoreStatus,
        objective_details: list[Any],
        is_promising: bool,
        stage_a_passed: bool,
        stage_b_result: dict[str, Any],
        duration_seconds: float,
        candidate_proposal: CandidateProposal | None = None,
    ) -> SearchIteration:
        """Accept one ask/tell result through the lifecycle-owner transition.

        This is an internal bridge for ``LegacySearchServiceAdapter``.  It
        reuses the typed-evaluation resolver and frontier owner from the full
        native lifecycle, preserving the distinction between absent and
        malformed typed results (B123) without exposing private fields to the
        adapter.
        """
        if candidate_proposal is not None:
            if not candidate_payloads_equal(
                materialize_candidate_proposal(candidate_proposal), candidate
            ):
                raise ValueError("candidate_proposal_payload_mismatch")
        policy_resolution = self._resolve_policy_evaluation_with_status(
            candidate,
            stage_b_result,
            candidate_proposal=candidate_proposal,
        )
        policy_evaluation = policy_resolution.value
        self._validate_result_candidate_identity(
            candidate, candidate_proposal, policy_evaluation, stage_b_result
        )
        candidate_ref, evaluation_ref, source_verified = self._resolve_policy_source(
            candidate_proposal, policy_evaluation, stage_b_result
        )
        self._prepare_service_run()
        effective_objective = None
        effective_score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
        effective_assessment: ObjectiveScoreAssessment | None = None
        effective_details: list[ObjectiveValue] = []
        if policy_resolution.status == "invalid":
            self._run_state.policy_evaluation_errors += 1
        source_results = stage_b_result.get("simulation_results")
        if isinstance(source_results, dict):
            recomputed = self._config.objective.evaluate(source_results)
            effective_assessment = recomputed.score_assessment
            effective_score_status = recomputed.score_status
            effective_details = self._config.objective.evaluate_detailed(source_results)
            if (
                effective_score_status is ObjectiveScoreStatus.AVAILABLE
                and selected_score_admission_status(effective_assessment, source_results)
                is ObjectiveScoreStatus.AVAILABLE
            ):
                effective_objective = (
                    effective_assessment.value if effective_assessment is not None else None
                )
            elif effective_score_status is ObjectiveScoreStatus.AVAILABLE:
                effective_score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
        else:
            effective_score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
        if effective_score_status not in {
            ObjectiveScoreStatus.AVAILABLE,
            ObjectiveScoreStatus.NOT_ESTABLISHED,
        }:
            effective_objective = None

        effective_admission = reconcile_objective_score_assessment(
            effective_assessment,
            source_results,
            reported_status=effective_score_status,
            reported_value=effective_objective,
        )
        is_sentinel = extract_sentinel_metadata(candidate) is not None
        policy_subject = (
            candidate_proposal is not None
            and candidate_proposal.strategy_context is not None
            and candidate_proposal.strategy_context.policy_schema
        )
        if (policy_subject or policy_evaluation is not None) and not source_verified:
            effective_objective = None
            effective_score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
            effective_assessment = None
            effective_details = []
            effective_admission = reconcile_objective_score_assessment(
                None,
                source_results,
                reported_status=effective_score_status,
                reported_value=None,
            )
            if not is_sentinel and policy_evaluation is not None:
                self._record_candidate_only_evaluation(
                    candidate, candidate_proposal, policy_evaluation, candidate_ref, evaluation_ref
                )
        feedback = stage_b_result.get("feedback")
        verdict = feedback.get("verdict") if isinstance(feedback, dict) else None
        accepted = (
            bool(is_promising)
            and bool(stage_a_passed)
            and policy_resolution.status != "invalid"
            and (policy_evaluation is None or policy_evaluation.feasible)
            and verdict == "APPROVE"
            and effective_score_status is ObjectiveScoreStatus.AVAILABLE
            and effective_assessment is not None
            and selected_score_admission_status(effective_assessment, source_results)
            is ObjectiveScoreStatus.AVAILABLE
        )
        if (
            stage_a_passed
            and not is_sentinel
            and policy_resolution.status != "invalid"
            and effective_score_status is ObjectiveScoreStatus.AVAILABLE
            and effective_objective is not None
        ):
            if effective_details:
                self._update_policy_or_legacy_frontier(
                    candidate=candidate,
                    objective_details=effective_details,
                    policy_evaluation=policy_evaluation,
                    stage_b_result=stage_b_result,
                    candidate_proposal=candidate_proposal,
                )
            if effective_objective < self._best_objective:
                self._best_objective = effective_objective
                self._best_candidate = deepcopy(candidate)

        record = SearchIteration(
            iteration=self._run_state.evaluation_iterations,
            candidate=deepcopy(candidate),
            objective_value=effective_objective,
            objective_details=deepcopy(effective_details),
            is_promising=accepted,
            stage_a_passed=bool(stage_a_passed),
            stage_b_result=deepcopy(stage_b_result),
            duration_seconds=float(duration_seconds),
            policy_evaluation=deepcopy(policy_evaluation),
            policy_evaluation_status=(
                "source_unverified"
                if (policy_subject or policy_evaluation is not None) and not source_verified
                else policy_resolution.status
            ),
            policy_evaluation_error=(
                "policy_evaluation_source_unverified"
                if (policy_subject or policy_evaluation is not None) and not source_verified
                else policy_resolution.reason
            ),
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            score_status=effective_admission.status,
            score_assessment=effective_assessment,
            score_admission=effective_admission,
            candidate_proposal=deepcopy(candidate_proposal),
        )
        transition = _EvaluationTransition(
            disposition=(
                _EvaluationDisposition.SENTINEL if is_sentinel else _EvaluationDisposition.ORDINARY
            ),
            record=record,
        )
        self._run_state.apply_tell_transition(
            transition,
            stage_a_evaluated=self._config.enable_stage_a,
            stage_b_evaluated=stage_a_passed,
        )
        return record

    def _service_tell_snapshot(self) -> dict[str, Any]:
        """Return detached state feedback for the ask/tell compatibility bridge."""
        snapshot = self._run_state.snapshot()
        return {
            "best_candidate": deepcopy(snapshot.best_candidate),
            "best_objective": (
                None if snapshot.best_objective == float("inf") else float(snapshot.best_objective)
            ),
            "history_length": snapshot.history_size,
            "registry_update": {"search_id": snapshot.search_id},
            "lesson_cards": [],
            "frontier_delta": deepcopy(snapshot.pareto_front),
            "pareto_projection": snapshot.pareto_projection,
        }

    def _begin_native_run(self, initial_context: dict[str, Any]) -> datetime:
        """Initialize one native service run and seed its warm history."""
        self._validate_transfer_basis()
        start_time = datetime.now(UTC)
        search_id = str(uuid4())[:8]
        self._reset_diversity_tracker(operation="reset_diversity_tracker")
        self._run_state = SearchRunState(
            search_id=search_id,
            status=SearchStatus.RUNNING,
        )
        self._config.stopping.reset()
        self._refresh_budget_snapshot(initial_context)
        self._run_state.training_evaluations = 0

        for eval_dict in self._config.initial_evaluations:
            stage_b_result = deepcopy(eval_dict.get("stage_b_result"))
            source_results = (
                stage_b_result.get("simulation_results")
                if isinstance(stage_b_result, dict)
                else None
            )
            assessment: ObjectiveScoreAssessment | None = None
            score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
            obj_value = eval_dict.get("objective_value")
            if isinstance(source_results, dict):
                recomputed = self._config.objective.evaluate(source_results)
                assessment = recomputed.score_assessment
                score_status = recomputed.score_status
                if (
                    score_status is ObjectiveScoreStatus.AVAILABLE
                    and score_assessment_matches_source(assessment, source_results)
                ):
                    obj_value = assessment.value if assessment is not None else None
                else:
                    if score_status is ObjectiveScoreStatus.AVAILABLE:
                        score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
                    obj_value = eval_dict.get("objective_value")
            admission = reconcile_objective_score_assessment(
                assessment,
                source_results,
                reported_status=score_status,
                reported_value=obj_value,
            )
            warm_candidate = deepcopy(eval_dict.get("candidate", {}))
            proposal_data = eval_dict.get("candidate_proposal")
            warm_proposal = (
                CandidateProposal.model_validate(proposal_data)
                if proposal_data is not None
                else None
            )
            if warm_proposal is not None and not candidate_payloads_equal(
                materialize_candidate_proposal(warm_proposal), warm_candidate
            ):
                raise ValueError("warm_start_candidate_subject_mismatch")
            warm_resolution = self._resolve_policy_evaluation_with_status(
                warm_candidate, stage_b_result or {}, candidate_proposal=warm_proposal
            )
            warm_vector = warm_resolution.value
            warm_candidate_ref, warm_evaluation_ref, warm_verified = self._resolve_policy_source(
                warm_proposal, warm_vector, stage_b_result or {}
            )
            warm_policy_subject = (
                warm_proposal is not None
                and warm_proposal.strategy_context is not None
                and warm_proposal.strategy_context.policy_schema
            )
            if warm_resolution.status == "invalid" or (
                (warm_policy_subject or warm_vector is not None) and not warm_verified
            ):
                score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
                obj_value = None
                assessment = None
                admission = reconcile_objective_score_assessment(
                    None, source_results, reported_status=score_status, reported_value=None
                )
            record = SearchIteration(
                iteration=-1,
                candidate=warm_candidate,
                objective_value=obj_value,
                objective_details=[],
                is_promising=eval_dict.get("is_promising", False)
                and admission.status is ObjectiveScoreStatus.AVAILABLE,
                stage_a_passed=True,
                stage_b_result=stage_b_result,
                duration_seconds=0.0,
                policy_evaluation=warm_vector,
                policy_evaluation_status=(
                    "source_unverified"
                    if warm_policy_subject and not warm_verified
                    else warm_resolution.status
                ),
                candidate_ref=warm_candidate_ref,
                evaluation_ref=warm_evaluation_ref,
                score_status=admission.status,
                score_assessment=assessment,
                score_admission=admission,
                candidate_proposal=warm_proposal,
            )
            self._history.append(record)
            if (
                score_status is ObjectiveScoreStatus.AVAILABLE
                and assessment is not None
                and score_assessment_matches_source(assessment, source_results)
            ):
                self._run_state.training_evaluations += 1
            if (
                score_status is ObjectiveScoreStatus.AVAILABLE
                and obj_value is not None
                and obj_value < self._best_objective
            ):
                self._best_objective = float(obj_value)
                self._best_candidate = deepcopy(record.candidate)

        controller_logger.info(f"Starting search {search_id}")
        return start_time

    def _validate_transfer_basis(self) -> None:
        """Reconcile transferable numeric history against the actual producer."""
        fingerprint = self._config.transfer_fingerprint
        if fingerprint is None:
            return
        from polisyos.scientist.methods.search.objective import (
            configured_objective_rule_spec,
            configured_objective_unit,
        )
        from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
        from polisyos.scientist.methods.search.strategies.transfer import (
            RunFingerprint,
            TransferLearningManager,
        )

        if (
            type(self._generator) is not StrategyAdapter
            or type(self._config.transfer_manager) is not TransferLearningManager
        ):
            raise ValueError("transfer_history_owner_or_producer_missing")
        if type(fingerprint) is not RunFingerprint:
            raise TypeError("transfer_history_fingerprint_required")
        space = self._generator.search_space
        for bound in space.bounds:
            policy_candidate_hash({"categories": list(bound.categories or ())})
        actual_bounds = {bound.name: [bound.lower, bound.upper] for bound in space.bounds}
        objectives = self._config.objective.objectives
        names = [item.name for item in objectives]
        rules = {item.name: configured_objective_rule_spec(item) for item in objectives}
        units = {
            name: configured_objective_unit(rule)
            for name, rule in rules.items()
            if rule is not None
        }
        directions = {item.name: item.direction.value for item in objectives}
        if (
            fingerprint.space_hash != space.sobol_space_fingerprint()
            or fingerprint.bounds != actual_bounds
            or fingerprint.objective_names != names
            or fingerprint.objective_rule_specs != rules
            or fingerprint.units != units
            or fingerprint.objective_directions != directions
        ):
            raise ValueError("transfer_history_fingerprint_producer_mismatch")

    def _finish_native_run(
        self,
        *,
        start_time: datetime,
        stopping_reason: str | None,
    ) -> SearchResult:
        """Build a detached result from the lifecycle-owned run state."""
        if self._status == SearchStatus.RUNNING:
            self._status = SearchStatus.STOPPED
            stopping_reason = (
                f"Hard iteration limit ({self._config.max_iterations_hard_limit}) reached"
            )

        total_duration = (datetime.now(UTC) - start_time).total_seconds()
        snapshot = self._run_state.snapshot()
        telemetry: dict[str, Any] = {
            "history_size": snapshot.history_size,
            "training_evaluations": snapshot.training_evaluations,
            "new_evaluations": snapshot.new_evaluations,
            "evaluation_count": snapshot.evaluation_count,
            "scientific_evaluations": snapshot.scientific_evaluations,
            "sentinel_evaluations": snapshot.sentinel_evaluations,
            "policy_evaluation_errors": snapshot.policy_evaluation_errors,
            "budget_required": bool(self._config.stopping.state_keys()),
            "budget_available": snapshot.budget_available,
            "budget_snapshot": deepcopy(snapshot.budget_snapshot),
            "budget_spent": (snapshot.budget_spent if snapshot.budget_available else None),
        }
        source_budget = self._source_budget_telemetry()
        if source_budget is not None:
            telemetry["producer_budget_owner"] = source_budget
        if self._diversity_tracker is not None:
            telemetry["diversity_unique_mechanisms_total"] = (
                self._diversity_tracker.unique_mechanisms_total
            )
            telemetry["diversity_ratio"] = self._diversity_tracker.diversity_ratio
        if self._config.transfer_manager is not None and self._config.transfer_fingerprint is None:
            telemetry["transfer_history"] = {"status": "fingerprint_missing"}
        if self._config.transfer_fingerprint is not None:
            try:
                telemetry["transfer_history"] = self._persist_transfer_history(snapshot)
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                # The search result remains useful. A failed history write may
                # have left an orphan artifact, so its publication is unconfirmed.
                telemetry["transfer_history"] = {
                    "status": "not_confirmed",
                    "reason": type(exc).__name__,
                }
        transition_payload = snapshot.generation_transition_payload()
        if transition_payload is not None:
            telemetry["generation_transition"] = transition_payload

        return SearchResult(
            search_id=snapshot.search_id,
            status=cast("SearchStatus", snapshot.status),
            best_candidate=deepcopy(snapshot.best_candidate),
            best_objective=snapshot.best_objective,
            iterations_completed=snapshot.evaluation_iterations,
            history=deepcopy(snapshot.history),
            stopping_reason=stopping_reason,
            total_duration_seconds=total_duration,
            stage_a_evaluations=snapshot.stage_a_evaluations,
            stage_b_evaluations=snapshot.stage_b_evaluations,
            pareto_front=deepcopy(snapshot.pareto_front),
            pareto_projection=snapshot.pareto_projection,
            telemetry=deepcopy(telemetry),
        )

    def _persist_transfer_history(self, snapshot: Any) -> dict[str, Any]:
        self._validate_transfer_basis()
        from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
        from polisyos.scientist.methods.search.strategies.transfer import (
            RunFingerprint,
            TransferLearningManager,
        )

        manager = self._config.transfer_manager
        if (
            type(manager) is not TransferLearningManager
            or type(self._generator) is not StrategyAdapter
        ):
            raise ValueError("transfer_history_owner_or_producer_missing")
        if type(self._config.transfer_fingerprint) is not RunFingerprint:
            raise TypeError("transfer_history_fingerprint_required")
        evaluations = self._generator.completed_run_evaluations(snapshot.history)
        fingerprint = self._config.transfer_fingerprint.model_copy(
            update={"run_id": snapshot.search_id}
        )
        if not manager._has_complete_binding_basis(fingerprint):
            raise ValueError("transfer_history_fingerprint_incomplete")
        admitted = [
            item
            for item in evaluations
            if manager._evaluation_matches_fingerprint(item, fingerprint)
        ]
        fingerprint = fingerprint.model_copy(update={"num_evaluations": len(admitted)})
        history_ref = manager.register_run(fingerprint, admitted)
        return {
            "status": "persisted" if history_ref is not None else "no_eligible_evaluations",
            "history_ref": history_ref.model_dump(mode="json") if history_ref is not None else None,
            "fingerprint": fingerprint.model_dump(mode="json"),
        }

    def run(
        self,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None = None,
    ) -> SearchResult:
        """Execute the native ask/tell driver through the compatibility entrypoint."""
        from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver

        driver = _NativeSearchServiceDriver(self)
        if self._config.producer_settlement_store is None:
            return driver.run_search(
                initial_context=initial_context,
                initial_candidate=initial_candidate,
            )
        assert self._config.producer_run_binding is not None
        with self._config.producer_settlement_store.producer_run_binding_scope(
            self._config.producer_run_binding
        ):
            return driver.run_search(
                initial_context=initial_context,
                initial_candidate=initial_candidate,
            )

    def _stopping_state(self) -> dict[str, Any]:
        """Build stopping input from run counters and declared budget owners."""
        state = {
            "iteration": self._run_state.evaluation_iterations,
            "evaluation_iterations": self._run_state.evaluation_iterations,
            "generation_attempts": self._run_state.generation_attempts,
            "empty_generation_attempts": self._run_state.empty_generation_attempts,
            "best_objective": self._best_objective,
            "budget_spent": self._run_state.budget_spent,
        }
        state.update(self._run_state.budget_snapshot)
        if self._source_budget_snapshot.get("status") == "resolved":
            state["_source_budget_remaining_usd"] = self._source_budget_snapshot["remaining"]
        return state

    def _refresh_budget_snapshot(self, context: dict[str, Any]) -> None:
        """Capture one detached snapshot from the declared budget owner.

        The lifecycle owner never forwards the mutable evaluator context directly to
        stopping criteria.  Only keys explicitly requested by the criterion are
        copied into the run-owned snapshot, so both stopping checkpoints and the
        final report observe the same owner contract without creating a ledger.
        """
        required_keys = self._config.stopping.state_keys()
        source_budget_key = "_source_budget_remaining_usd"
        context_required_keys = tuple(key for key in required_keys if key != source_budget_key)
        snapshot: dict[str, float] = {}
        for key in context_required_keys:
            if self._config.producer_settlement_store is not None and key == "cumulative_cost_usd":
                continue
            value = context.get(key)
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                numeric_value = float(value)
                if isfinite(numeric_value):
                    snapshot[key] = numeric_value

        if self._config.producer_settlement_store is not None:
            self._source_budget_snapshot = self._read_source_budget_snapshot()
            if self._source_budget_snapshot.get("status") == "resolved":
                source_spent = self._source_budget_snapshot["spent"]
                if "cumulative_cost_usd" in required_keys:
                    snapshot["cumulative_cost_usd"] = float(source_spent)
                self._run_state.budget_spent = float(source_spent)
        else:
            self._source_budget_snapshot = {"status": "not_configured"}
        self._run_state.budget_snapshot = snapshot
        context_available = all(key in snapshot for key in context_required_keys)
        source_available = (
            self._config.producer_settlement_store is None
            or self._source_budget_snapshot.get("status") == "resolved"
        )
        self._run_state.budget_available = (
            bool(required_keys) and context_available and source_available
        )
        if self._config.producer_settlement_store is not None:
            pass
        elif "cumulative_cost_usd" in snapshot:
            self._run_state.budget_spent = snapshot["cumulative_cost_usd"]
        elif snapshot:
            self._run_state.budget_spent = next(iter(snapshot.values()))
        else:
            self._run_state.budget_spent = 0.0

    def _read_source_budget_snapshot(self) -> dict[str, Any]:
        """Read one owner, typed run scope, exact producer events, and remaining budget."""
        store = self._config.producer_settlement_store
        binding = self._config.producer_run_binding
        if store is None or binding is None:
            return {"status": "not_configured"}

        owner_identity: tuple[str, str, str] | None = None
        try:
            from polisyos.scientist.orchestration.engine.budget import BudgetState

            owner_identity = store.settlement_owner_identity
            if (
                type(owner_identity) is not tuple
                or len(owner_identity) != 3
                or any(not isinstance(value, str) or not value.strip() for value in owner_identity)
            ):
                raise ValueError("settlement_owner_identity_not_established")
            budget_state = store.budget_state
            if type(budget_state) is not BudgetState:
                raise TypeError("budget_owner_returned_untyped_state")
            budget_key = f"nl-run:{binding.run_id}"
            limit = budget_state.limits.get(budget_key)
            if limit is None or limit.max_usd <= 0:
                raise ValueError("run_budget_limit_not_established")
            records = store.list_producer_events_for_run_safe(binding)
            event_status_counts: dict[str, int] = {}
            settled = Decimal(0)
            for record in records:
                event_status_counts[record.status] = event_status_counts.get(record.status, 0) + 1
                if record.run_binding != binding or record.key != budget_key:
                    raise ValueError("producer_event_scope_mismatch")
                if record.status != "committed" or record.amount is None:
                    raise ValueError("producer_event_settlement_unresolved")
                settled += record.amount
            spent = budget_state.spent.get(budget_key, Decimal(0))
            reserved = budget_state.reserved.get(budget_key, Decimal(0))
            if spent != settled:
                raise ValueError("producer_settlement_spend_disagrees_with_budget_owner")
            if (
                self._run_state.generation_attempts > 0 or self._run_state.evaluation_iterations > 0
            ) and not records:
                raise ValueError("producer_event_missing_after_search_work")
            remaining = limit.max_usd - spent - reserved
            return {
                "status": "resolved",
                "owner_identity": owner_identity,
                "run_binding": binding.model_dump(mode="json"),
                "budget_key": budget_key,
                "limit": limit.max_usd,
                "spent": spent,
                "reserved": reserved,
                "remaining": remaining,
                "event_count": len(records),
                "event_status_counts": event_status_counts,
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "owner_identity": owner_identity,
                "run_binding": binding.model_dump(mode="json"),
                "reason_code": f"source_budget_{type(exc).__name__.lower()}",
            }

    def _source_budget_telemetry(self) -> dict[str, Any] | None:
        """Project source-bound accounting values without exposing event payloads."""
        snapshot = self._source_budget_snapshot
        if snapshot.get("status") == "not_configured":
            return None
        payload = dict(snapshot)
        for key in ("limit", "spent", "reserved", "remaining"):
            value = payload.get(key)
            if isinstance(value, Decimal):
                payload[key] = str(value)
        return payload

    def _generate_candidates(
        self,
        iteration: int,
        initial_candidate: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[dict[str, Any] | CandidateProposal]:
        if iteration == 0 and initial_candidate is not None:
            return [initial_candidate]

        effective_context = context
        if self._diversity_enabled:
            try:
                from polisyos.scientist.methods.search.diversity import (
                    enrich_context_with_diversity,
                )
            except _IMPORT_ERRORS as exc:
                _search_degraded(
                    operation="enrich_diversity_context",
                    reason="optional_dependency_unavailable",
                    exc=exc,
                    details={"iteration": iteration},
                )
                effective_context = context
            else:
                try:
                    effective_context = enrich_context_with_diversity(context, self._history)
                except _SEARCH_DEGRADED_ERRORS as exc:
                    _search_degraded(
                        operation="enrich_diversity_context",
                        reason="diversity_context_failed",
                        exc=exc,
                        details={"iteration": iteration},
                    )
                    effective_context = context
        effective_context = self._build_generation_context(effective_context, iteration=iteration)

        # Adaptive batch sizing based on evaluation cost
        batch_size = max(1, int(self._config.batch_size))
        if self._history:
            durations = [h.duration_seconds for h in self._history if h.duration_seconds > 0]
            if durations:
                avg_duration = sum(durations) / len(durations)
                if avg_duration < 1.0:
                    batch_size = min(batch_size * 2, 16)
                elif avg_duration > 30.0:
                    batch_size = max(1, batch_size // 2)
        generate_proposal = getattr(self._generator, "generate_proposal", None)
        generate_batch_proposals = getattr(self._generator, "generate_batch_proposals", None)
        if batch_size > 1 and callable(generate_batch_proposals):
            proposals = generate_batch_proposals(
                self._history, self._best_candidate, effective_context, batch_size
            )
            if not all(isinstance(item, CandidateProposal) for item in proposals):
                raise TypeError("search_candidate_proposal_required")
            self._admit_generated_proposals(proposals)
            return proposals
        if callable(generate_proposal):
            proposal = generate_proposal(self._history, self._best_candidate, effective_context)
            if not isinstance(proposal, CandidateProposal):
                raise TypeError("search_candidate_proposal_required")
            self._admit_generated_proposals([proposal])
            return [proposal]
        generate_batch = None
        if hasattr(self._generator, "generate_batch"):
            generate_batch = self._generator.generate_batch
        if batch_size > 1 and callable(generate_batch):
            return generate_batch(
                self._history,
                self._best_candidate,
                effective_context,
                batch_size,
            )
        return [
            self._generator.generate(
                self._history,
                self._best_candidate,
                effective_context,
            )
        ]

    def _admit_generated_proposals(self, proposals: list[CandidateProposal]) -> None:
        """Admit producer context only from the actual StrategyAdapter boundary."""
        from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter

        for proposal in proposals:
            if (
                proposal.strategy_context is not None
                and type(self._generator) is not StrategyAdapter
            ):
                raise ValueError("candidate_strategy_producer_unestablished")
            if proposal.metadata or proposal.service_iteration is not None:
                raise ValueError("candidate_service_context_already_present")
            materialize_candidate_proposal(proposal)

    def _evaluate_candidate(
        self,
        candidate: dict[str, Any] | CandidateProposal,
        iteration: int,
        context: dict[str, Any],
    ) -> _EvaluationTransition:
        candidate_proposal = (
            deepcopy(candidate) if isinstance(candidate, CandidateProposal) else None
        )
        candidate = (
            materialize_candidate_proposal(candidate_proposal)
            if candidate_proposal is not None
            else deepcopy(candidate)
        )
        policy_candidate_hash(candidate_proposal or candidate)
        stage_a_ticket: str | None = None
        iter_start = datetime.now(UTC)
        is_sentinel = extract_sentinel_metadata(candidate) is not None

        stage_a_passed = True
        stage_a_score: float | None = None

        if self._config.enable_stage_a:
            self._stage_a_count += 1
            stage_a_result = invoke_candidate_evaluator(
                self._stage_a, deepcopy(candidate), context, candidate_proposal
            )
            if isinstance(stage_a_result, EvaluationBundle):
                stage_a_score = stage_a_result.objective_value
                stage_a_passed = stage_a_result.stage_a_passed
                stage_a_ticket = funnel_prior_ticket_id(
                    self._stage_a, self._stage_b, stage_a_result
                )
            else:
                stage_a_score, stage_a_passed = stage_a_result
            if not stage_a_passed:
                controller_logger.debug(
                    "Iteration %s: Stage A did not continue candidate (score=%s)",
                    iteration,
                    stage_a_score,
                )

        stage_b_result: dict[str, Any] | None = None
        objective_value: float | None = None
        score_status = ObjectiveScoreStatus.UNAVAILABLE
        score_assessment: ObjectiveScoreAssessment | None = None
        objective_details: list[ObjectiveValue] = []
        policy_evaluation = None
        policy_resolution = _PolicyEvaluationResolution(value=None, status="missing")
        policy_subject = (
            candidate_proposal is not None
            and candidate_proposal.strategy_context is not None
            and candidate_proposal.strategy_context.policy_schema
        )
        candidate_ref = evaluation_ref = None
        source_verified = False
        sim_results: dict[str, Any] | None = None
        iter_duration = 0.0

        if stage_a_passed:
            self._stage_b_count += 1
            arbiter = self._config.resource_arbiter
            if arbiter is not None:
                with arbiter.acquire("jax"):
                    stage_b_result = invoke_candidate_evaluator(
                        self._stage_b,
                        deepcopy(candidate),
                        context,
                        candidate_proposal,
                        prior_ticket_id=stage_a_ticket,
                    )
            else:
                stage_b_result = invoke_candidate_evaluator(
                    self._stage_b,
                    deepcopy(candidate),
                    context,
                    candidate_proposal,
                    prior_ticket_id=stage_a_ticket,
                )

            sim_results = stage_b_result.get("simulation_results", {})
            policy_resolution = self._resolve_policy_evaluation_with_status(
                candidate,
                stage_b_result,
                candidate_proposal=candidate_proposal,
            )
            policy_evaluation = policy_resolution.value
            try:
                self._validate_result_candidate_identity(
                    candidate, candidate_proposal, policy_evaluation, stage_b_result
                )
            except (TypeError, ValueError):
                # Evaluation happened: retain its failure and the real stage
                # counts, but do not update best, ranking or registry.
                self._run_state.policy_evaluation_errors += 1
                record = SearchIteration(
                    iteration=iteration,
                    candidate=deepcopy(candidate),
                    objective_value=None,
                    objective_details=[],
                    is_promising=False,
                    stage_a_passed=stage_a_passed,
                    stage_b_result=deepcopy(stage_b_result),
                    duration_seconds=(datetime.now(UTC) - iter_start).total_seconds(),
                    policy_evaluation_status="invalid",
                    policy_evaluation_error="candidate_identity_mismatch",
                    score_status=ObjectiveScoreStatus.INVALID,
                    candidate_proposal=candidate_proposal,
                )
                return _EvaluationTransition(
                    disposition=(
                        _EvaluationDisposition.SENTINEL
                        if is_sentinel
                        else _EvaluationDisposition.ORDINARY
                    ),
                    record=record,
                )
            candidate_ref, evaluation_ref, source_verified = self._resolve_policy_source(
                candidate_proposal, policy_evaluation, stage_b_result
            )
            if policy_resolution.status == "invalid":
                self._run_state.policy_evaluation_errors += 1
                score_status = ObjectiveScoreStatus.INVALID
            elif (policy_subject or policy_evaluation is not None) and not source_verified:
                score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
                if not is_sentinel and policy_evaluation is not None:
                    self._record_candidate_only_evaluation(
                        candidate,
                        candidate_proposal,
                        policy_evaluation,
                        candidate_ref,
                        evaluation_ref,
                    )
            elif policy_evaluation is not None:
                selected = self._config.objective.evaluate(sim_results)
                score_status = selected.score_status
                score_assessment = selected.score_assessment
                objective_details = self._config.objective.evaluate_detailed(sim_results)
                if score_status is ObjectiveScoreStatus.AVAILABLE:
                    if score_assessment_matches_source(score_assessment, sim_results):
                        objective_value = (
                            score_assessment.value if score_assessment is not None else None
                        )
                    else:
                        score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
            else:
                obj_eval = self._config.objective.evaluate(sim_results)
                objective_details = self._config.objective.evaluate_detailed(sim_results)
                score_status = obj_eval.score_status
                score_assessment = obj_eval.score_assessment
                if score_status is ObjectiveScoreStatus.AVAILABLE:
                    if score_assessment_matches_source(score_assessment, sim_results):
                        objective_value = (
                            score_assessment.value if score_assessment is not None else None
                        )
                    else:
                        score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
                elif score_status is not ObjectiveScoreStatus.NOT_ESTABLISHED:
                    objective_value = None

            if (
                not is_sentinel
                and policy_resolution.status != "invalid"
                and score_status is ObjectiveScoreStatus.AVAILABLE
                and objective_value is not None
            ):
                self._update_policy_or_legacy_frontier(
                    candidate=candidate,
                    objective_details=objective_details,
                    policy_evaluation=policy_evaluation,
                    stage_b_result=stage_b_result,
                    candidate_proposal=candidate_proposal,
                )
                if objective_value < self._best_objective:
                    self._best_objective = objective_value
                    self._best_candidate = deepcopy(candidate)
                    controller_logger.info(
                        f"Iteration {iteration}: New best objective = {objective_value:.6f}"
                    )

        score_admission = reconcile_objective_score_assessment(
            score_assessment,
            sim_results,
            reported_status=score_status,
            reported_value=objective_value,
        )
        score_status = score_admission.status
        iter_duration = (datetime.now(UTC) - iter_start).total_seconds()
        record = SearchIteration(
            iteration=iteration,
            candidate=deepcopy(candidate),
            objective_value=objective_value,
            objective_details=deepcopy(objective_details),
            is_promising=stage_a_passed
            and policy_resolution.status != "invalid"
            and (policy_evaluation is None or policy_evaluation.feasible)
            and (stage_b_result or {}).get("feedback", {}).get("verdict") == "APPROVE"
            and score_status is ObjectiveScoreStatus.AVAILABLE
            and selected_score_admission_status(score_assessment, sim_results)
            is ObjectiveScoreStatus.AVAILABLE,
            stage_a_passed=stage_a_passed,
            stage_b_result=deepcopy(stage_b_result),
            duration_seconds=iter_duration,
            policy_evaluation=deepcopy(policy_evaluation),
            policy_evaluation_status=(
                "source_unverified"
                if (policy_subject or policy_evaluation is not None) and not source_verified
                else policy_resolution.status
            ),
            policy_evaluation_error=(
                "policy_evaluation_source_unverified"
                if (policy_subject or policy_evaluation is not None) and not source_verified
                else policy_resolution.reason
            ),
            score_status=score_status,
            score_assessment=score_assessment,
            score_admission=score_admission,
            candidate_proposal=candidate_proposal,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
        )
        if not is_sentinel and self._diversity_tracker is not None:
            self._diversity_tracker.record_iteration(candidate)
        return _EvaluationTransition(
            disposition=(
                _EvaluationDisposition.SENTINEL if is_sentinel else _EvaluationDisposition.ORDINARY
            ),
            record=record,
        )

    def _build_generation_context(
        self,
        context: dict[str, Any],
        *,
        iteration: int,
    ) -> dict[str, Any]:
        enriched = dict(context)
        best_candidate = self._best_candidate
        best_objective = self._best_objective
        if best_candidate is None and best_objective == float("inf"):
            best_objective = None
        enriched["search_state"] = {
            "iteration": int(iteration),
            "history_length": len(self._history),
            "current_best_candidate": best_candidate,
            "current_best_objective": best_objective,
        }
        if self._history:
            enriched["last_stage_b_result"] = self._history[-1].stage_b_result
        lesson_hints = self._build_lesson_hints(enriched)
        if lesson_hints:
            enriched["lesson_hints"] = lesson_hints
        try:
            from polisyos.scientist.methods.autotune.execution_plan import (
                build_execution_plan_generation_context,
            )
        except _IMPORT_ERRORS as exc:
            _search_degraded(
                operation="build_generation_context",
                reason="execution_plan_context_unavailable",
                exc=exc,
                details={"iteration": iteration},
            )
            return enriched

        try:
            execution_plan_context = build_execution_plan_generation_context(
                history=self._history,
                current_best=self._best_candidate,
                context=enriched,
            )
        except _SEARCH_DEGRADED_ERRORS as exc:
            _search_degraded(
                operation="build_generation_context",
                reason="execution_plan_context_failed",
                exc=exc,
                details={"iteration": iteration},
            )
            return enriched

        if execution_plan_context.get("execution_plan_topology_mutation_payload"):
            enriched.update(execution_plan_context)
        return enriched

    def _build_lesson_hints(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        lesson_registry = context.get("lesson_registry")
        if lesson_registry is None:
            return []
        try:
            from polisyos.scientist.methods.search.lessons import LessonQuery
            from polisyos.scientist.methods.search.transfer_context import (
                lesson_hint_payload,
                resolve_transfer_context,
            )

            transfer_context = resolve_transfer_context(context=context)
            if hasattr(lesson_registry, "query_with_transfer"):
                cards = lesson_registry.query_with_transfer(
                    LessonQuery(
                        task_family=transfer_context.task_family,
                        min_confidence=0.5,
                        limit=3,
                    ),
                    target_context=transfer_context,
                )
                return [lesson_hint_payload(card) for card in cards]
            if hasattr(lesson_registry, "top_patterns"):
                return [
                    {
                        "summary": pattern.summary,
                        "failure_type": pattern.failure_type,
                        "remediation_hint": pattern.remediation_hint,
                        "trust_level": (
                            pattern.trust_level.value
                            if hasattr(pattern.trust_level, "value")
                            else str(pattern.trust_level)
                        ),
                        "provenance_weight": float(
                            getattr(pattern, "provenance_weight", 1.0) or 0.0
                        ),
                        "domain": getattr(pattern, "domain", "general"),
                        "task_family": getattr(pattern, "task_family", "policy"),
                    }
                    for pattern in lesson_registry.top_patterns(limit=3)
                ]
        except (_IMPORT_ERRORS, _SEARCH_DEGRADED_ERRORS) as exc:
            _search_degraded(
                operation="build_lesson_hints",
                reason="lesson_hint_generation_failed",
                exc=exc,
            )
        return []

    def _resolve_policy_evaluation(
        self,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any] | None,
    ) -> PolicyEvaluationVector | None:
        """Resolve a typed evaluation while preserving the legacy private API."""
        resolution = self._resolve_policy_evaluation_with_status(candidate, stage_b_result)
        return cast("PolicyEvaluationVector | None", resolution.value)

    def _resolve_policy_evaluation_with_status(
        self,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any] | None,
        *,
        candidate_proposal: CandidateProposal | None = None,
    ) -> _PolicyEvaluationResolution:
        """Resolve typed evaluation input without conflating absent and invalid data."""
        if not stage_b_result:
            return _PolicyEvaluationResolution(value=None, status="missing")

        typed_vector_present = "policy_evaluation" in stage_b_result
        typed_bundle_present = (
            "policy_evaluation_bundle" in stage_b_result
            or "_policy_evaluation_bundle" in stage_b_result
        )
        if not typed_vector_present and not typed_bundle_present:
            return _PolicyEvaluationResolution(value=None, status="missing")

        try:
            from polisyos.scientist.policy_design.objectives import (
                PolicyEvaluationBundle,
                _normalize_policy_evaluation_vector,
            )
            from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
        except _IMPORT_ERRORS as exc:
            _search_degraded(
                operation="resolve_policy_evaluation",
                reason="policy_objective_stack_unavailable",
                exc=exc,
            )
            return _PolicyEvaluationResolution(
                value=None,
                status="invalid",
                reason="policy_objective_stack_unavailable",
            )

        typed_error_reason: str | None = None
        if typed_vector_present:
            raw_vector = stage_b_result.get("policy_evaluation")
            try:
                return _PolicyEvaluationResolution(
                    value=_normalize_policy_evaluation_vector(raw_vector, allow_mapping=True),
                    status="valid",
                )
            except _SEARCH_DEGRADED_ERRORS as exc:
                typed_error_reason = "policy_evaluation_parse_failed"
                _search_degraded(
                    operation="resolve_policy_evaluation",
                    reason=typed_error_reason,
                    exc=exc,
                )

        objective_stack = self._config.policy_objective_stack
        if objective_stack is None:
            return _PolicyEvaluationResolution(
                value=None,
                status="invalid",
                reason=typed_error_reason or "policy_evaluation_stack_unavailable",
            )

        raw_bundle = stage_b_result.get("policy_evaluation_bundle")
        if raw_bundle is None:
            raw_bundle = stage_b_result.get("_policy_evaluation_bundle")
        if raw_bundle is None:
            return _PolicyEvaluationResolution(
                value=None,
                status="invalid",
                reason=typed_error_reason or "policy_evaluation_bundle_missing",
            )
        try:
            if isinstance(raw_bundle, PolicyEvaluationBundle):
                bundle = raw_bundle
            else:
                if hasattr(raw_bundle, "model_dump"):
                    raw_bundle = raw_bundle.model_dump(mode="python")
                bundle = PolicyEvaluationBundle.model_validate(raw_bundle)
        except _SEARCH_DEGRADED_ERRORS as exc:
            _search_degraded(
                operation="resolve_policy_evaluation",
                reason="policy_evaluation_bundle_parse_failed",
                exc=exc,
            )
            return _PolicyEvaluationResolution(
                value=None,
                status="invalid",
                reason="policy_evaluation_bundle_parse_failed",
            )

        bound_policy_candidate = None
        if (
            candidate_proposal is not None
            and candidate_proposal.strategy_context is not None
            and candidate_proposal.strategy_context.policy_schema
        ):
            materialize_candidate_proposal(candidate_proposal)
            bound_policy_candidate = PolicyCandidateSchema.model_validate(
                candidate_proposal.strategy_context.subject
            )
            if (
                bundle.candidate is not None
                and bundle.candidate.candidate_hash() != bound_policy_candidate.candidate_hash()
            ):
                return _PolicyEvaluationResolution(
                    value=None, status="invalid", reason="policy_bundle_candidate_mismatch"
                )
            if bundle.candidate is None:
                bundle = bundle.model_copy(update={"candidate": bound_policy_candidate})

        if bundle.candidate is None:
            candidate_schema = stage_b_result.get("_policy_candidate_schema") or stage_b_result.get(
                "policy_candidate"
            )
            if isinstance(candidate_schema, PolicyCandidateSchema):
                bundle = bundle.model_copy(update={"candidate": candidate_schema})
            else:
                try:
                    if hasattr(candidate_schema, "model_dump"):
                        candidate_payload = candidate_schema.model_dump(mode="python")
                    else:
                        candidate_payload = candidate_schema
                    if isinstance(candidate_payload, dict):
                        bundle = bundle.model_copy(
                            update={
                                "candidate": PolicyCandidateSchema.model_validate(candidate_payload)
                            }
                        )
                except _SEARCH_DEGRADED_ERRORS as exc:
                    _search_degraded(
                        operation="resolve_policy_evaluation",
                        reason="policy_candidate_parse_failed",
                        exc=exc,
                    )
            if (
                bundle.candidate is None
                and isinstance(candidate, dict)
                and "trinity_bundle" in candidate
            ):
                try:
                    bundle = bundle.model_copy(
                        update={"candidate": PolicyCandidateSchema.model_validate(candidate)}
                    )
                except _SEARCH_DEGRADED_ERRORS as exc:
                    _search_degraded(
                        operation="resolve_policy_evaluation",
                        reason="policy_candidate_validation_failed",
                        exc=exc,
                    )

        if (
            bound_policy_candidate is None
            and bundle.candidate is not None
            and candidate_proposal is None
        ):
            try:
                if candidate_payloads_equal(
                    candidate, bundle.candidate.model_dump(mode="json", exclude_none=True)
                ):
                    bound_policy_candidate = bundle.candidate
            except (TypeError, ValueError):
                pass

        try:
            evaluation = objective_stack.evaluate(bundle)
            try:
                normalized = _normalize_policy_evaluation_vector(evaluation)
            except TypeError as exc:
                _search_degraded(
                    operation="resolve_policy_evaluation",
                    reason="objective_stack_returned_untyped_result",
                    exc=exc,
                )
                return _PolicyEvaluationResolution(
                    value=None,
                    status="invalid",
                    reason="objective_stack_returned_untyped_result",
                )
            except _SEARCH_DEGRADED_ERRORS as exc:
                _search_degraded(
                    operation="resolve_policy_evaluation",
                    reason="objective_stack_returned_invalid_vector",
                    exc=exc,
                )
                return _PolicyEvaluationResolution(
                    value=None,
                    status="invalid",
                    reason="objective_stack_returned_invalid_vector",
                )
            if bound_policy_candidate is None:
                return _PolicyEvaluationResolution(
                    value=None, status="invalid", reason="policy_bundle_subject_unbound"
                )
            identity = policy_candidate_hash(candidate_proposal or candidate)
            supplied = normalized.metadata.get("candidate_hash")
            if supplied not in (None, "", identity):
                return _PolicyEvaluationResolution(
                    value=None, status="invalid", reason="policy_bundle_candidate_mismatch"
                )
            normalized = normalized.model_copy(
                update={"metadata": {**normalized.metadata, "candidate_hash": identity}}
            )
            return _PolicyEvaluationResolution(value=normalized, status="valid")
        except _SEARCH_DEGRADED_ERRORS as exc:
            _search_degraded(
                operation="resolve_policy_evaluation",
                reason="objective_stack_evaluation_failed",
                exc=exc,
            )
            return _PolicyEvaluationResolution(
                value=None,
                status="invalid",
                reason="objective_stack_evaluation_failed",
            )

    def _resolve_policy_source(
        self,
        proposal: CandidateProposal | None,
        evaluation: PolicyEvaluationVector | None,
        stage_b_result: dict[str, Any],
    ) -> tuple[Any | None, Any | None, bool]:
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.methods.search.pareto_registry import (
            verify_policy_evaluation_source,
        )

        def ref(value: Any) -> ArtifactRef | None:
            if value is None:
                return None
            try:
                return ArtifactRef.model_validate(value)
            except (TypeError, ValueError):
                return None

        candidate_ref = ref(stage_b_result.get("candidate_ref"))
        evaluation_ref = ref(stage_b_result.get("policy_evaluation_ref"))
        store = self._config.policy_source_store
        if store is None and self._config.pareto_registry is not None:
            store = self._config.pareto_registry._source_store
        return (
            candidate_ref,
            evaluation_ref,
            verify_policy_evaluation_source(
                store, proposal, evaluation, candidate_ref, evaluation_ref
            ),
        )

    def _record_candidate_only_evaluation(
        self,
        candidate: dict[str, Any],
        proposal: CandidateProposal | None,
        evaluation: PolicyEvaluationVector,
        candidate_ref: Any | None,
        evaluation_ref: Any | None,
    ) -> None:
        registry = self._config.pareto_registry
        if registry is None:
            return
        from polisyos.scientist.methods.search.transfer_context import resolve_transfer_context

        transfer = resolve_transfer_context(candidate=candidate, fallback_run_id=self._search_id)
        registry.update(
            self._search_id,
            candidate_hash=policy_candidate_hash(proposal or candidate),
            evaluation=evaluation,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            seed_payload=dict(candidate),
            candidate_proposal=proposal,
            seed_only=True,
            transfer_context=transfer,
        )

    def _update_policy_or_legacy_frontier(
        self,
        *,
        candidate: dict[str, Any],
        objective_details: list[ObjectiveValue],
        policy_evaluation: PolicyEvaluationVector | None,
        stage_b_result: dict[str, Any] | None,
        candidate_proposal: CandidateProposal | None = None,
    ) -> None:
        registry = self._config.pareto_registry
        source_results = (
            stage_b_result.get("simulation_results") if isinstance(stage_b_result, dict) else None
        )
        vector_is_reconciled = (
            policy_evaluation is not None
            and policy_evaluation.score_assessment_matches_channels(
                source_results if isinstance(source_results, dict) else None
            )
        )
        if policy_evaluation is not None and vector_is_reconciled and registry is not None:
            try:
                from polisyos.scientist.methods.search.transfer_context import (
                    resolve_transfer_context,
                )
            except _IMPORT_ERRORS as exc:
                _search_degraded(
                    operation="update_frontier",
                    reason="transfer_context_unavailable",
                    exc=exc,
                )
                transfer_context = None
            else:
                transfer_context = resolve_transfer_context(
                    candidate=candidate, fallback_run_id=self._search_id
                )
            candidate_hash = self._policy_candidate_hash(
                candidate=candidate,
                policy_evaluation=policy_evaluation,
                stage_b_result=stage_b_result or {},
                candidate_proposal=candidate_proposal,
            )
            registry.update(
                self._search_id,
                candidate_hash=candidate_hash,
                evaluation=policy_evaluation,
                candidate_id=policy_evaluation.candidate_id,
                candidate_ref=(stage_b_result or {}).get("candidate_ref"),
                evaluation_ref=(stage_b_result or {}).get("policy_evaluation_ref"),
                policy_family=(str(policy_evaluation.metadata.get("policy_family") or "") or None),
                promotion_metadata={
                    "iteration": len(self._history),
                    "feedback": dict((stage_b_result or {}).get("feedback", {})),
                },
                seed_payload=dict(candidate),
                candidate_proposal=candidate_proposal,
                task_family=(
                    transfer_context.task_family if transfer_context is not None else None
                ),
                domain=(transfer_context.domain if transfer_context is not None else None),
                transfer_context=transfer_context,
                objective_basis_by_view=(self._config.pareto_objective_basis_by_view or None),
            )
            from polisyos.scientist.methods.search.pareto_registry import ParetoView

            self._run_state.pareto_projection = registry.get_snapshot(
                self._search_id, transfer_context=transfer_context
            ).project_view(ParetoView.GLOBAL_FEASIBLE)
            self._pareto_front = registry.as_legacy_frontier_payload(
                self._search_id, transfer_context=transfer_context
            )
            return

        if objective_details:
            self._update_pareto_front(candidate, objective_details, candidate_proposal)

    @staticmethod
    def _validate_result_candidate_identity(
        candidate: dict[str, Any],
        candidate_proposal: CandidateProposal | None,
        policy_evaluation: PolicyEvaluationVector | None,
        stage_b_result: dict[str, Any],
    ) -> str:
        metadata_hash = (
            policy_evaluation.metadata.get("candidate_hash") if policy_evaluation else None
        )
        explicit_hash = stage_b_result.get("candidate_hash")
        return policy_candidate_hash(
            candidate_proposal or candidate,
            metadata_hash=metadata_hash,
            explicit_hash=explicit_hash,
        )

    @staticmethod
    def _policy_candidate_hash(
        *,
        candidate: dict[str, Any],
        policy_evaluation: PolicyEvaluationVector,
        stage_b_result: dict[str, Any],
        candidate_proposal: CandidateProposal | None = None,
    ) -> str:
        metadata_hash = policy_evaluation.metadata.get("candidate_hash")
        if metadata_hash is not None and not isinstance(metadata_hash, str):
            raise ValueError("candidate_identity_supplied_hash_invalid")
        explicit = stage_b_result.get("candidate_hash")
        if explicit is not None and not isinstance(explicit, str):
            raise ValueError("candidate_identity_supplied_hash_invalid")
        return policy_candidate_hash(
            candidate_proposal or candidate,
            metadata_hash=metadata_hash,
            explicit_hash=explicit,
        )

    def _update_pareto_front(
        self,
        candidate: dict[str, Any],
        objectives: list[ObjectiveValue],
        candidate_proposal: CandidateProposal | None = None,
    ) -> None:
        """Update the Pareto front with a new candidate if non-dominated."""
        self._pareto_points = update_legacy_pareto_front(
            self._pareto_points,
            candidate=candidate,
            objectives=objectives,
            cap=100,
            proposal=candidate_proposal,
        )
        self._pareto_front = [point.as_payload() for point in self._pareto_points]

    @staticmethod
    def _dominates(a: list[float], b: list[float]) -> bool:
        """Return True if *a* dominates *b* (all <= and at least one <)."""
        return dominates(a, b)

    def _to_history_dict(self, iteration: SearchIteration) -> dict[str, Any]:
        """Expose objective values to stopping rules only after source reconciliation."""
        record = {
            "iteration": iteration.iteration,
            "score_status": iteration.score_status.value,
            "score_admission": (
                None
                if iteration.score_admission is None
                else iteration.score_admission.to_surface_payload()
            ),
            "is_promising": iteration.is_promising,
            "stage_a_passed": iteration.stage_a_passed,
        }
        if (
            iteration.score_status is ObjectiveScoreStatus.AVAILABLE
            and iteration.score_assessment is not None
            and score_assessment_matches_source(
                iteration.score_assessment,
                iteration.stage_b_result,
            )
        ):
            record["objective_value"] = iteration.score_assessment.value
        return record

    def run_portfolio_search(
        self,
        *,
        portfolio: Any,
        evaluator: Callable[[Any, dict[str, Any]], Any],
        mode: str = "enumerate",
        max_evaluations: int = 100,
        base_benefits: dict[str, float] | None = None,
        initial_context: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Run discrete portfolio optimization over policy combinations.

        Returns a list of `PortfolioEvaluationResult`, sorted by objective descending.
        """

        from polisyos.scientist.methods.search.portfolio import (
            PortfolioEvaluationResult,
            PortfolioSearchMode,
            PortfolioSearchSpace,
        )

        context = dict(initial_context or {})
        base = dict(base_benefits or {})
        max_evaluations = max(1, int(max_evaluations))

        search_space = PortfolioSearchSpace(portfolio)
        search_mode = PortfolioSearchMode(mode)
        if search_mode is PortfolioSearchMode.ENUMERATE:
            try:
                combinations = search_space.enumerate_combinations()
            except ValueError as exc:
                controller_logger.warning(
                    "Portfolio enumeration capped ({}). Falling back to sampling mode.",
                    exc,
                )
                combinations = search_space.sample_combinations(max_evaluations)
        elif search_mode is PortfolioSearchMode.SAMPLE:
            combinations = search_space.sample_combinations(max_evaluations)
        else:
            combinations = search_space.greedy_combinations(
                base_benefits=base,
                max_combinations=max_evaluations,
            )

        results: list[PortfolioEvaluationResult] = []
        for combination in combinations[:max_evaluations]:
            raw = evaluator(combination, context)
            if isinstance(raw, PortfolioEvaluationResult):
                result = raw
            elif isinstance(raw, dict):
                if "objective_value" not in raw:
                    raise ValueError("portfolio evaluator omitted objective_value")
                result = PortfolioEvaluationResult(
                    combination=combination,
                    objective_value=raw["objective_value"],
                    metrics=raw,
                )
            else:
                result = PortfolioEvaluationResult(
                    combination=combination,
                    objective_value=float(raw),
                    metrics={},
                )
            results.append(result)

        results.sort(key=lambda item: item.objective_value, reverse=True)

        portfolio_id = str(getattr(portfolio, "portfolio_id", "portfolio"))
        helper = getattr(self._metrics, "record_portfolio_search", None)
        if callable(helper):
            helper(
                portfolio_id=portfolio_id,
                combinations_evaluated=len(results),
                best_objective=(float(results[0].objective_value) if results else None),
            )
        else:
            counter = getattr(self._metrics, "portfolio_combinations_evaluated", None)
            if counter is not None and hasattr(counter, "add"):
                counter.add(len(results), {"portfolio_id": portfolio_id})
            gauge = getattr(self._metrics, "portfolio_best_objective", None)
            if results and gauge is not None and hasattr(gauge, "set"):
                gauge.set(float(results[0].objective_value), {"portfolio_id": portfolio_id})

        return results


__all__: list[str] = []
