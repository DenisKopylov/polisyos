"""Legacy iterative search controller for ask/evaluate search loops."""

from __future__ import annotations

import os
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from functools import wraps
from threading import Lock
from typing import TYPE_CHECKING, Any, Protocol, cast
from uuid import uuid4

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.scientist.methods.search.contracts import EvaluationBundle, ParetoViewProjection
from polisyos.scientist.methods.search.frontier import (
    FrontierPoint,
    dominates,
    policy_candidate_hash,
    update_legacy_pareto_front,
)
from polisyos.scientist.methods.search.objective import CompositeObjective, ObjectiveValue
from polisyos.scientist.methods.search.run_state import (
    SearchRunState,
    _EvaluationDisposition,
    _EvaluationTransition,
)
from polisyos.scientist.methods.search.sentinels import extract_sentinel_metadata
from polisyos.scientist.methods.search.stopping import StoppingCriterion, _nonnegative_cost
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry
    from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
    from polisyos.scientist.methods.search.strategies.transfer import (
        RunFingerprint,
        TransferLearningManager,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.policy_design.objectives import (
        ObjectiveStack,
        PolicyEvaluationVector,
    )

logger = get_logger(__name__)

_IMPORT_ERRORS = (ImportError, ModuleNotFoundError)
_SEARCH_DEGRADED_ERRORS = (AttributeError, TypeError, ValidationError, ValueError)

CandidatePayload = dict[str, Any]
SearchContext = dict[str, Any]
StageAEvaluator = Callable[[CandidatePayload, SearchContext], tuple[float, bool]]
StageBEvaluator = Callable[[CandidatePayload, SearchContext], dict[str, Any]]


def _default_metrics() -> MetricsRegistry:
    from polisyos.core.observability import get_metrics

    return get_metrics()


def _search_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return emit_degraded_path(
        component="search.controller",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=logger,
    )


def _as_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class SearchStatus(str, Enum):
    """Track the lifecycle state of a legacy search loop run."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    CONVERGED = "converged"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class SearchIteration:
    """Record one ask/evaluate step and the evaluator feedback used for future proposals."""

    iteration: int
    candidate: dict[str, Any]
    objective_value: float
    objective_details: list[ObjectiveValue]
    is_promising: bool
    stage_a_passed: bool
    stage_b_result: dict[str, Any] | None
    duration_seconds: float
    policy_evaluation: Any | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    policy_evaluation_status: str = "missing"
    policy_evaluation_error: str | None = None


@dataclass(frozen=True)
class _PolicyEvaluationResolution:
    """Keep absent, valid, and invalid typed results distinct at the consumer."""

    value: Any | None
    status: str
    reason: str | None = None


@dataclass
class SearchResult:
    """Return the final champion candidate, full history, and evaluation counters."""

    search_id: str
    status: SearchStatus
    best_candidate: dict[str, Any] | None
    best_objective: float
    iterations_completed: int
    history: list[SearchIteration]
    stopping_reason: str | None
    total_duration_seconds: float
    stage_a_evaluations: int
    stage_b_evaluations: int
    pareto_front: list[dict[str, Any]] = field(default_factory=list)
    telemetry: dict[str, Any] = field(default_factory=dict)
    pareto_projection: ParetoViewProjection | None = None


def _non_reentrant_run(
    method: Callable[..., SearchResult],
) -> Callable[..., SearchResult]:
    """Guard one controller lifecycle against overlapping invocations."""

    @wraps(method)
    def guarded(self: Any, *args: Any, **kwargs: Any) -> SearchResult:
        run_lock = self._run_lock
        if not run_lock.acquire(blocking=False):
            raise RuntimeError("SearchController.run is not reentrant")
        try:
            return method(self, *args, **kwargs)
        finally:
            run_lock.release()

    return guarded


class CandidateGenerator(Protocol):
    """Generate the next candidate proposal from search history and context."""

    def generate(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Propose one candidate payload for the next evaluator round.

        Args:
            history: Prior iterations with objective values and Stage B feedback.
            current_best: Current best candidate payload, if any.
            context: Planner/runtime context assembled by the caller.

        Returns:
            JSON-compatible candidate payload accepted by the Stage A/B evaluators.
        """


class BatchCandidateGenerator(CandidateGenerator, Protocol):
    """Generate a batch of candidate proposals for parallel Stage B evaluation."""

    def generate_batch(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        """Generate multiple candidates for parallel Stage B evaluation."""


@dataclass(frozen=True)
class SearchEvaluatorPorts:
    """Bundle evaluator callables so controller construction does not sprawl."""

    stage_a: StageAEvaluator
    stage_b: StageBEvaluator


@dataclass
class SearchConfig:
    """Configure candidate generation, objective evaluation, stopping, and warm start."""

    stopping: StoppingCriterion
    objective: CompositeObjective
    max_iterations_hard_limit: int = 100
    enable_stage_a: bool = True
    log_level: str = "INFO"
    batch_size: int = 1
    resource_arbiter: Any | None = None
    transfer_manager: TransferLearningManager | None = None
    transfer_fingerprint: RunFingerprint | None = None
    initial_evaluations: list[dict[str, Any]] = field(default_factory=list)
    policy_objective_stack: ObjectiveStack | None = None
    pareto_registry: ParetoRegistry | None = None
    max_empty_generation_attempts: int = 3
    budget_middleware: BudgetMiddleware | None = None
    budget_key: str = "run"
    budget_cost_key: str = "cumulative_cost_usd"

    def __post_init__(self) -> None:
        """Validate the controller-owned hard bounds."""
        if self.max_iterations_hard_limit < 1:
            raise ValueError("max_iterations_hard_limit must be >= 1")
        if self.max_empty_generation_attempts < 1:
            raise ValueError("max_empty_generation_attempts must be >= 1")
        if (self.transfer_manager is None) != (self.transfer_fingerprint is None):
            raise ValueError("transfer_manager and transfer_fingerprint must be supplied together")


class SearchController:
    """Coordinate a legacy ask/evaluate loop over one Stage A and one Stage B evaluator.

    Candidate generation is delegated to `CandidateGenerator`, evaluator feedback
    is captured in `SearchIteration`, optional transfer/Pareto/diversity state is
    injected into generation context, and stopping criteria terminate the loop.
    `run()` is intentionally non-reentrant; overlapping calls on one controller
    raise a deterministic `RuntimeError` before replacing run state.
    """

    def __init__(
        self,
        config: SearchConfig,
        candidate_generator: CandidateGenerator,
        stage_a_evaluator: StageAEvaluator | None = None,
        stage_b_evaluator: StageBEvaluator | None = None,
        *,
        evaluators: SearchEvaluatorPorts | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._config = config
        self._generator = candidate_generator
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
        if config.transfer_manager is not None:
            from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge

            configure_transfer = getattr(candidate_generator, "configure_transfer", None)
            if not callable(configure_transfer):
                raise ValueError("configured generator does not support numeric transfer")
            configure_transfer(
                WarmStartBridge(config.transfer_manager), config.transfer_fingerprint
            )

        self._run_lock = Lock()
        self._run_state = SearchRunState(status=SearchStatus.NOT_STARTED)
        self._metrics = metrics if metrics is not None else _default_metrics()
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
        objective_value: float,
        objective_details: list[Any],
        is_promising: bool,
        stage_a_passed: bool,
        stage_b_result: dict[str, Any],
        duration_seconds: float,
        _apply_transition: bool = True,
    ) -> SearchIteration:
        """Accept one ask/tell result through the controller-owned transition.

        This is an internal bridge for ``LegacySearchServiceAdapter``.  It
        reuses the typed-evaluation resolver and frontier owner from the full
        controller loop, preserving the distinction between absent and
        malformed typed results (B123) without exposing private fields to the
        adapter.
        """
        self._prepare_service_run()
        policy_resolution = self._resolve_policy_evaluation_with_status(
            candidate,
            stage_b_result,
        )
        policy_evaluation = policy_resolution.value
        effective_objective = float(objective_value)
        effective_details: list[ObjectiveValue] = [
            detail for detail in objective_details if isinstance(detail, ObjectiveValue)
        ]
        if policy_resolution.status == "invalid":
            self._run_state.policy_evaluation_errors += 1
            effective_objective = float("inf")
            effective_details = []
        elif policy_evaluation is not None:
            effective_objective = policy_evaluation.legacy_scalar_proxy
            effective_details = policy_evaluation.as_legacy_objectives()
            stage_b_result = {**stage_b_result, "policy_evaluation": policy_evaluation}

        is_sentinel = extract_sentinel_metadata(candidate) is not None
        feedback = stage_b_result.get("feedback")
        verdict = feedback.get("verdict") if isinstance(feedback, dict) else None
        accepted = (
            bool(is_promising)
            and bool(stage_a_passed)
            and policy_resolution.status != "invalid"
            and (policy_evaluation is None or policy_evaluation.feasible)
            and verdict == "APPROVE"
        )
        if stage_a_passed and not is_sentinel and policy_resolution.status != "invalid":
            if effective_objective < self._best_objective:
                self._best_objective = effective_objective
                self._best_candidate = deepcopy(candidate)
            if effective_details or policy_evaluation is not None:
                self._update_policy_or_legacy_frontier(
                    candidate=candidate,
                    objective_details=effective_details,
                    policy_evaluation=policy_evaluation,
                    stage_b_result=stage_b_result,
                )

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
            policy_evaluation_status=policy_resolution.status,
            policy_evaluation_error=policy_resolution.reason,
        )
        transition = _EvaluationTransition(
            disposition=(
                _EvaluationDisposition.SENTINEL if is_sentinel else _EvaluationDisposition.ORDINARY
            ),
            record=record,
        )
        if not is_sentinel and self._diversity_tracker is not None:
            self._diversity_tracker.record_iteration(candidate)
        if _apply_transition:
            self._run_state.apply_tell_transition(
                transition,
                stage_a_evaluated=self._config.enable_stage_a,
                stage_b_evaluated=stage_a_passed,
            )
        else:
            if self._config.enable_stage_a:
                self._run_state.stage_a_evaluations += 1
            if stage_a_passed:
                self._run_state.stage_b_evaluations += 1
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
        start_time = datetime.now(UTC)
        search_id = str(uuid4())[:8]
        self._reset_diversity_tracker(operation="reset_diversity_tracker")
        self._run_state = SearchRunState(
            search_id=search_id,
            status=SearchStatus.RUNNING,
        )
        self._config.stopping.reset()
        self._refresh_budget_snapshot(initial_context)
        self._run_state.training_evaluations = len(self._config.initial_evaluations)

        for eval_dict in self._config.initial_evaluations:
            obj_value = eval_dict.get("objective_value", float("inf"))
            record = SearchIteration(
                iteration=-1,
                candidate=deepcopy(eval_dict.get("candidate", {})),
                objective_value=obj_value,
                objective_details=[],
                is_promising=eval_dict.get("is_promising", False),
                stage_a_passed=True,
                stage_b_result=deepcopy(eval_dict.get("stage_b_result")),
                duration_seconds=0.0,
            )
            self._history.append(record)
            if obj_value < self._best_objective:
                self._best_objective = obj_value
                self._best_candidate = deepcopy(record.candidate)

        logger.info(f"Starting search {search_id}")
        return start_time

    def _finish_native_run(
        self,
        *,
        start_time: datetime,
        stopping_reason: str | None,
    ) -> SearchResult:
        """Build a detached result from the controller-owned run state."""
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
            "budget_snapshot_source": snapshot.budget_snapshot_source,
            "budget_evidence": deepcopy(snapshot.budget_evidence),
            "budget_ledger_id": snapshot.budget_ledger_id,
            "budget_ledger_revision": snapshot.budget_ledger_revision,
            "budget_spent": (snapshot.budget_spent if snapshot.budget_available else None),
        }
        if self._diversity_tracker is not None:
            telemetry["diversity_unique_mechanisms_total"] = (
                self._diversity_tracker.unique_mechanisms_total
            )
            telemetry["diversity_ratio"] = self._diversity_tracker.diversity_ratio
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

    def run(
        self,
        initial_context: dict[str, Any],
        initial_candidate: dict[str, Any] | None = None,
    ) -> SearchResult:
        """Execute the native ask/tell driver through the compatibility entrypoint."""
        from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver

        return _NativeSearchServiceDriver(self).run_search(
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
            "budget_evidence": deepcopy(self._run_state.budget_evidence),
        }
        state.update(self._run_state.budget_snapshot)
        return state

    def _refresh_budget_snapshot(self, context: dict[str, Any]) -> None:
        """Capture one detached snapshot from the declared budget owner.

        The controller never forwards the mutable evaluator context directly to
        stopping criteria.  Only keys explicitly requested by the criterion are
        copied into the run-owned snapshot, so both stopping checkpoints and the
        final report observe the same owner contract without creating a ledger.
        """
        required_keys = self._config.stopping.state_keys()
        snapshot: dict[str, float] = {}
        owner = self._config.budget_middleware
        source = "legacy_context" if required_keys else "unavailable"
        self._run_state.budget_ledger_id = None
        self._run_state.budget_ledger_revision = None
        evidence: dict[str, Any] = {
            "source": source,
            "receipt_revision_available": False,
            "provider_cost_origin_available": False,
            "recorded_by_provider": None,
            "unavailable_reason": "budget_not_requested" if not required_keys else None,
        }
        if owner is not None:
            source = "configured_owner_recorded_state"
            evidence["source"] = source
            identity = self._budget_owner_identity()
            if identity is not None:
                self._run_state.budget_ledger_id = identity[0]
                evidence.update(canonical_contract=identity[1], coordination_mode=identity[2])
            try:
                accounting = owner.budget_state.model_copy(deep=True)
            except (OSError, ValueError, RuntimeError) as exc:
                evidence["unavailable_reason"] = f"owner_state_unavailable:{type(exc).__name__}"
            else:
                evidence["recorded_spend_key_present"] = self._config.budget_key in accounting.spent
                providers = {
                    key: _nonnegative_cost(value)
                    for key, value in accounting.provider_spent.items()
                }
                if all(value is not None for value in providers.values()):
                    evidence["recorded_by_provider"] = providers
                if self._config.budget_cost_key in required_keys:
                    value = _nonnegative_cost(
                        accounting.spent.get(self._config.budget_key, Decimal(0))
                    )
                    if value is not None:
                        snapshot[self._config.budget_cost_key] = value
                    else:
                        evidence["unavailable_reason"] = "recorded_cost_invalid"
        for key in required_keys:
            if owner is not None:
                continue
            value = _nonnegative_cost(context.get(key))
            if value is not None:
                snapshot[key] = value
            else:
                evidence["unavailable_reason"] = "context_cost_missing_or_invalid"
        self._run_state.budget_snapshot_source = source
        self._run_state.budget_evidence = evidence
        self._run_state.budget_snapshot = snapshot
        self._run_state.budget_available = bool(required_keys) and all(
            key in snapshot for key in required_keys
        )
        if "cumulative_cost_usd" in snapshot:
            self._run_state.budget_spent = snapshot["cumulative_cost_usd"]
        elif snapshot:
            self._run_state.budget_spent = next(iter(snapshot.values()))
        else:
            self._run_state.budget_spent = 0.0

    def _budget_owner_identity(self) -> tuple[str, str, str] | None:
        """Use the public owner identity; in-memory accounting has no durable identity."""
        owner = self._config.budget_middleware
        if owner is None:
            return None
        try:
            identity = getattr(owner, "settlement_owner_identity", None)
        except (OSError, ValueError, RuntimeError):
            return None
        if (
            isinstance(identity, tuple)
            and len(identity) == 3
            and all(isinstance(part, str) and part for part in identity)
        ):
            return identity
        return None

    def _generate_candidates(
        self,
        iteration: int,
        initial_candidate: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
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

    def _evaluate_candidate(
        self,
        candidate: CandidatePayload,
        iteration: int,
        context: SearchContext,
    ) -> _EvaluationTransition:
        """Compatibility driver: evaluate, then use the same acceptance owner as tell."""
        evaluation = self._evaluate_for_tell(candidate, iteration=iteration, context=context)
        record = self._accept_tell(
            candidate=candidate,
            objective_value=evaluation.objective_value,
            objective_details=evaluation.objective_details,
            is_promising=evaluation.is_promising,
            stage_a_passed=evaluation.stage_a_passed,
            stage_b_result=evaluation.stage_b_result or {},
            duration_seconds=evaluation.duration_seconds,
            _apply_transition=False,
        )
        return _EvaluationTransition(
            disposition=(
                _EvaluationDisposition.SENTINEL
                if extract_sentinel_metadata(candidate) is not None
                else _EvaluationDisposition.ORDINARY
            ),
            record=record,
        )

    def _evaluate_for_tell(
        self,
        candidate: dict[str, Any],
        *,
        iteration: int,
        context: dict[str, Any],
    ) -> EvaluationBundle:
        """Evaluate with detached outputs and no search-state acceptance writes."""
        candidate = deepcopy(candidate)
        iter_start = datetime.now(UTC)

        stage_a_passed = True
        stage_a_score = 0.0

        if self._config.enable_stage_a:
            stage_a_score, stage_a_passed = self._stage_a(candidate, context)
            if not stage_a_passed:
                logger.debug(f"Iteration {iteration}: Stage A rejected (score={stage_a_score:.4f})")

        stage_b_result: dict[str, Any] | None = None
        objective_value = float("inf")
        objective_details: list[ObjectiveValue] = []
        policy_evaluation = None
        policy_resolution = _PolicyEvaluationResolution(value=None, status="missing")
        iter_duration = 0.0

        if stage_a_passed:
            arbiter = self._config.resource_arbiter
            if arbiter is not None:
                with arbiter.acquire("jax"):
                    stage_b_result = self._stage_b(candidate, context)
            else:
                stage_b_result = self._stage_b(candidate, context)

            sim_results = stage_b_result.get("simulation_results", {})
            policy_resolution = self._resolve_policy_evaluation_with_status(
                candidate,
                stage_b_result,
            )
            policy_evaluation = policy_resolution.value
            if policy_evaluation is not None:
                objective_value = policy_evaluation.legacy_scalar_proxy
                objective_details = policy_evaluation.as_legacy_objectives()
                stage_b_result = {**stage_b_result, "policy_evaluation": policy_evaluation}
            elif policy_resolution.status == "missing":
                obj_eval = self._config.objective.evaluate(sim_results)
                objective_value = obj_eval.raw_value
                objective_details = self._config.objective.evaluate_detailed(sim_results)

        iter_duration = (datetime.now(UTC) - iter_start).total_seconds()
        return EvaluationBundle(
            objective_value=objective_value,
            objective_details=deepcopy(objective_details),
            is_promising=stage_a_passed
            and policy_resolution.status != "invalid"
            and (policy_evaluation is None or policy_evaluation.feasible)
            and (stage_b_result or {}).get("feedback", {}).get("verdict") == "APPROVE",
            stage_a_passed=stage_a_passed,
            stage_b_result=deepcopy(stage_b_result),
            duration_seconds=iter_duration,
            policy_evaluation=deepcopy(policy_evaluation),
            metadata={
                "policy_evaluation_status": policy_resolution.status,
                "policy_evaluation_error": policy_resolution.reason,
                "iteration": iteration,
            },
        )

    def _build_generation_context(
        self,
        context: dict[str, Any],
        *,
        iteration: int,
    ) -> dict[str, Any]:
        enriched = dict(context)
        enriched["search_state"] = {
            "iteration": int(iteration),
            "history_length": len(self._history),
            "current_best_candidate": self._best_candidate,
            "current_best_objective": self._best_objective,
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

    def _update_policy_or_legacy_frontier(
        self,
        *,
        candidate: dict[str, Any],
        objective_details: list[ObjectiveValue],
        policy_evaluation: PolicyEvaluationVector | None,
        stage_b_result: dict[str, Any] | None,
    ) -> None:
        registry = self._config.pareto_registry
        if policy_evaluation is not None and registry is not None:
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
                transfer_context = resolve_transfer_context(candidate=candidate)
            candidate_hash = self._policy_candidate_hash(
                candidate=candidate,
                policy_evaluation=policy_evaluation,
                stage_b_result=stage_b_result or {},
            )
            registry.update(
                self._search_id,
                candidate_hash=candidate_hash,
                evaluation=policy_evaluation,
                candidate_id=policy_evaluation.candidate_id,
                candidate_ref=(stage_b_result or {}).get("candidate_ref"),
                policy_family=(str(policy_evaluation.metadata.get("policy_family") or "") or None),
                promotion_metadata={
                    "iteration": len(self._history),
                    "feedback": dict((stage_b_result or {}).get("feedback", {})),
                },
                seed_payload=dict(candidate),
                task_family=(
                    transfer_context.task_family if transfer_context is not None else None
                ),
                domain=(transfer_context.domain if transfer_context is not None else None),
                transfer_context=transfer_context,
            )
            from polisyos.scientist.methods.search.pareto_registry import ParetoView

            self._run_state.pareto_projection = registry.get_snapshot(self._search_id).project_view(
                ParetoView.GLOBAL_FEASIBLE
            )
            self._pareto_front = registry.as_legacy_frontier_payload(self._search_id)
            return

        if objective_details:
            self._update_pareto_front(candidate, objective_details)

    @staticmethod
    def _policy_candidate_hash(
        *,
        candidate: dict[str, Any],
        policy_evaluation: PolicyEvaluationVector,
        stage_b_result: dict[str, Any],
    ) -> str:
        metadata_hash = str(policy_evaluation.metadata.get("candidate_hash", "")).strip()
        explicit = stage_b_result.get("candidate_hash")
        return policy_candidate_hash(
            candidate,
            metadata_hash=metadata_hash,
            explicit_hash=explicit if isinstance(explicit, str) else None,
        )

    def _update_pareto_front(
        self,
        candidate: dict[str, Any],
        objectives: list[ObjectiveValue],
    ) -> None:
        """Update the Pareto front with a new candidate if non-dominated."""
        self._pareto_points = update_legacy_pareto_front(
            self._pareto_points,
            candidate=candidate,
            objectives=objectives,
            cap=100,
        )
        self._pareto_front = [point.as_payload() for point in self._pareto_points]

    @staticmethod
    def _dominates(a: list[float], b: list[float]) -> bool:
        """Return True if *a* dominates *b* (all <= and at least one <)."""
        return dominates(a, b)

    def _to_history_dict(self, iteration: SearchIteration) -> dict[str, Any]:
        """Convert iteration to dict for stopping criteria."""
        return {
            "iteration": iteration.iteration,
            "objective_value": iteration.objective_value,
            "is_promising": iteration.is_promising,
            "stage_a_passed": iteration.stage_a_passed,
        }

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
                logger.warning(
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
                value = float(raw.get("objective_value", 0.0))
                result = PortfolioEvaluationResult(
                    combination=combination,
                    objective_value=value,
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
