from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import os
from typing import Any, Callable, Dict, List, Protocol
from uuid import uuid4

from loguru import logger

from polisyos.scientist.search.objective import CompositeObjective, ObjectiveValue
from polisyos.scientist.search.stopping import StoppingCriterion


def _as_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class SearchStatus(str, Enum):
    """Status of the search process."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    CONVERGED = "converged"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class SearchIteration:
    """Record of a single search iteration."""

    iteration: int
    candidate: Dict[str, Any]
    objective_value: float
    objective_details: List[ObjectiveValue]
    is_promising: bool
    stage_a_passed: bool
    stage_b_result: Dict[str, Any] | None
    duration_seconds: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SearchResult:
    """Final result of a search run."""

    search_id: str
    status: SearchStatus
    best_candidate: Dict[str, Any] | None
    best_objective: float
    iterations_completed: int
    history: List[SearchIteration]
    stopping_reason: str | None
    total_duration_seconds: float
    stage_a_evaluations: int
    stage_b_evaluations: int
    pareto_front: List[Dict[str, Any]] = field(default_factory=list)
    telemetry: Dict[str, Any] = field(default_factory=dict)


class CandidateGenerator(Protocol):
    """Protocol for generating next policy candidate."""

    def generate(
        self,
        history: List[SearchIteration],
        current_best: Dict[str, Any] | None,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate next policy candidate based on search history.

        This is where the Reflexion/Agent-as-optimizer logic lives.
        The agent reviews past attempts and produces a refined policy.
        """


class BatchCandidateGenerator(CandidateGenerator, Protocol):
    """Optional protocol for batch candidate generation."""

    def generate_batch(
        self,
        history: List[SearchIteration],
        current_best: Dict[str, Any] | None,
        context: Dict[str, Any],
        batch_size: int,
    ) -> List[Dict[str, Any]]:
        """Generate multiple candidates for parallel Stage B evaluation."""


@dataclass
class SearchConfig:
    """Configuration for the search controller."""

    stopping: StoppingCriterion
    objective: CompositeObjective
    max_iterations_hard_limit: int = 100
    enable_stage_a: bool = True
    log_level: str = "INFO"
    batch_size: int = 1
    resource_arbiter: Any | None = None


class SearchController:
    """
    Main search loop controller.

    Orchestrates the iterative refinement of policies by:
    1. Generating candidate policies (via CandidateGenerator/Agent)
    2. Evaluating through Two-Stage filter
    3. Tracking history and best results
    4. Checking stopping criteria
    """

    def __init__(
        self,
        config: SearchConfig,
        candidate_generator: CandidateGenerator,
        stage_a_evaluator: Callable[[Dict[str, Any], Dict[str, Any]], tuple[float, bool]],
        stage_b_evaluator: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    ):
        self._config = config
        self._generator = candidate_generator
        self._stage_a = stage_a_evaluator
        self._stage_b = stage_b_evaluator

        self._history: List[SearchIteration] = []
        self._best_candidate: Dict[str, Any] | None = None
        self._best_objective: float = float("inf")
        self._status = SearchStatus.NOT_STARTED

        self._stage_a_count = 0
        self._stage_b_count = 0
        self._diversity_enabled = _as_bool(
            os.getenv("POLISYOS_SEARCH_DIVERSITY_ENABLED"),
            default=False,
        )
        self._diversity_tracker = None
        if self._diversity_enabled:
            try:
                from polisyos.scientist.search.diversity import DiversityTracker
            except Exception:
                self._diversity_enabled = False
            else:
                self._diversity_tracker = DiversityTracker()

    def run(
        self,
        initial_context: Dict[str, Any],
        initial_candidate: Dict[str, Any] | None = None,
    ) -> SearchResult:
        """
        Execute the search loop.

        Args:
            initial_context: Context passed to candidate generator
            initial_candidate: Optional starting policy

        Returns:
            SearchResult with best policy and history
        """
        search_id = str(uuid4())[:8]
        start_time = datetime.utcnow()
        self._status = SearchStatus.RUNNING
        self._config.stopping.reset()

        logger.info(f"Starting search {search_id}")

        stopping_reason: str | None = None
        iteration = 0

        while iteration < self._config.max_iterations_hard_limit:
            stop_check = self._config.stopping.check(
                [self._to_history_dict(h) for h in self._history],
                {"iteration": iteration, "best_objective": self._best_objective},
            )
            if stop_check.should_stop:
                stopping_reason = stop_check.reason
                self._status = SearchStatus.STOPPED
                logger.info(f"Stopping: {stopping_reason}")
                break

            batch = self._generate_candidates(
                iteration=iteration,
                initial_candidate=initial_candidate,
                context=initial_context,
            )
            for candidate in batch:
                if iteration >= self._config.max_iterations_hard_limit:
                    break
                self._evaluate_candidate(candidate, iteration=iteration, context=initial_context)
                iteration += 1

                stop_check = self._config.stopping.check(
                    [self._to_history_dict(h) for h in self._history],
                    {"iteration": iteration, "best_objective": self._best_objective},
                )
                if stop_check.should_stop:
                    stopping_reason = stop_check.reason
                    self._status = SearchStatus.STOPPED
                    logger.info(f"Stopping: {stopping_reason}")
                    break

            if self._status == SearchStatus.STOPPED:
                break

        if self._status == SearchStatus.RUNNING:
            self._status = SearchStatus.STOPPED
            stopping_reason = (
                f"Hard iteration limit ({self._config.max_iterations_hard_limit}) reached"
            )

        total_duration = (datetime.utcnow() - start_time).total_seconds()
        telemetry: Dict[str, Any] = {}
        if self._diversity_tracker is not None:
            telemetry["diversity_unique_mechanisms_total"] = (
                self._diversity_tracker.unique_mechanisms_total
            )
            telemetry["diversity_ratio"] = self._diversity_tracker.diversity_ratio

        return SearchResult(
            search_id=search_id,
            status=self._status,
            best_candidate=self._best_candidate,
            best_objective=self._best_objective,
            iterations_completed=iteration,
            history=self._history,
            stopping_reason=stopping_reason,
            total_duration_seconds=total_duration,
            stage_a_evaluations=self._stage_a_count,
            stage_b_evaluations=self._stage_b_count,
            telemetry=telemetry,
        )

    def _generate_candidates(
        self,
        iteration: int,
        initial_candidate: Dict[str, Any] | None,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if iteration == 0 and initial_candidate is not None:
            return [initial_candidate]

        effective_context = context
        if self._diversity_enabled:
            try:
                from polisyos.scientist.search.diversity import enrich_context_with_diversity
            except Exception:
                effective_context = context
            else:
                effective_context = enrich_context_with_diversity(context, self._history)

        batch_size = max(1, int(self._config.batch_size))
        can_batch = (
            batch_size > 1
            and hasattr(self._generator, "generate_batch")
            and callable(getattr(self._generator, "generate_batch"))
        )
        if can_batch:
            return getattr(self._generator, "generate_batch")(
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
        candidate: Dict[str, Any],
        iteration: int,
        context: Dict[str, Any],
    ) -> None:
        iter_start = datetime.utcnow()

        stage_a_passed = True
        stage_a_score = 0.0

        if self._config.enable_stage_a:
            self._stage_a_count += 1
            stage_a_score, stage_a_passed = self._stage_a(candidate, context)
            if not stage_a_passed:
                logger.debug(
                    f"Iteration {iteration}: Stage A rejected (score={stage_a_score:.4f})"
                )

        stage_b_result: Dict[str, Any] | None = None
        objective_value = float("inf")
        objective_details: List[ObjectiveValue] = []

        if stage_a_passed:
            self._stage_b_count += 1
            arbiter = self._config.resource_arbiter
            if arbiter is not None:
                with arbiter.acquire("jax"):
                    stage_b_result = self._stage_b(candidate, context)
            else:
                stage_b_result = self._stage_b(candidate, context)

            sim_results = stage_b_result.get("simulation_results", {})
            obj_eval = self._config.objective.evaluate(sim_results)
            objective_value = obj_eval.raw_value
            objective_details = self._config.objective.evaluate_detailed(sim_results)

            if objective_value < self._best_objective:
                self._best_objective = objective_value
                self._best_candidate = candidate
                logger.info(f"Iteration {iteration}: New best objective = {objective_value:.6f}")

        iter_duration = (datetime.utcnow() - iter_start).total_seconds()
        record = SearchIteration(
            iteration=iteration,
            candidate=candidate,
            objective_value=objective_value,
            objective_details=objective_details,
            is_promising=stage_a_passed
            and (stage_b_result or {}).get("feedback", {}).get("verdict") == "APPROVE",
            stage_a_passed=stage_a_passed,
            stage_b_result=stage_b_result,
            duration_seconds=iter_duration,
        )
        self._history.append(record)
        if self._diversity_tracker is not None:
            self._diversity_tracker.record_iteration(candidate)

    def _to_history_dict(self, iteration: SearchIteration) -> Dict[str, Any]:
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
        evaluator: Callable[[Any, Dict[str, Any]], Any],
        mode: str = "enumerate",
        max_evaluations: int = 100,
        base_benefits: Dict[str, float] | None = None,
        initial_context: Dict[str, Any] | None = None,
    ) -> List[Any]:
        """Run discrete portfolio optimization over policy combinations.

        Returns a list of `PortfolioEvaluationResult`, sorted by objective descending.
        """

        from polisyos.core.observability import get_metrics
        from polisyos.scientist.search.portfolio import (
            PortfolioCombination,
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

        results: List[PortfolioEvaluationResult] = []
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

        metrics = get_metrics()
        portfolio_id = str(getattr(portfolio, "portfolio_id", "portfolio"))
        helper = getattr(metrics, "record_portfolio_search", None)
        if callable(helper):
            helper(
                portfolio_id=portfolio_id,
                combinations_evaluated=len(results),
                best_objective=(float(results[0].objective_value) if results else None),
            )
        else:
            counter = getattr(metrics, "portfolio_combinations_evaluated", None)
            if counter is not None and hasattr(counter, "add"):
                counter.add(len(results), {"portfolio_id": portfolio_id})
            gauge = getattr(metrics, "portfolio_best_objective", None)
            if results and gauge is not None and hasattr(gauge, "set"):
                gauge.set(float(results[0].objective_value), {"portfolio_id": portfolio_id})

        return results
