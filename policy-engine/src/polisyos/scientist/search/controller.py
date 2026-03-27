from __future__ import annotations

import os
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Protocol
from uuid import uuid4

from polisyos.common.logger import get_logger
from polisyos.scientist.search.objective import CompositeObjective, ObjectiveValue
from polisyos.scientist.search.sentinels import extract_sentinel_metadata
from polisyos.scientist.search.stopping import StoppingCriterion

if TYPE_CHECKING:
    from polisyos.scientist.search.strategies.transfer import TransferLearningManager
    from polisyos.scientist.policy_design.objectives import (
        ObjectiveStack,
        PolicyEvaluationBundle,
        PolicyEvaluationVector,
    )
    from polisyos.scientist.search.pareto_registry import ParetoRegistry

logger = get_logger(__name__)


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
    policy_evaluation: Any | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


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
    transfer_manager: "TransferLearningManager | None" = None
    initial_evaluations: List[Dict[str, Any]] = field(default_factory=list)
    policy_objective_stack: "ObjectiveStack | None" = None
    pareto_registry: "ParetoRegistry | None" = None


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
        self._search_id = ""

        self._stage_a_count = 0
        self._stage_b_count = 0
        self._sentinel_evaluations = 0
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
        start_time = datetime.now(UTC)
        self._status = SearchStatus.RUNNING
        self._config.stopping.reset()
        self._pareto_front: List[Dict[str, Any]] = []
        self._search_id = search_id

        logger.info(f"Starting search {search_id}")

        # Warm-start: seed history from prior evaluations
        for eval_dict in self._config.initial_evaluations:
            obj_value = eval_dict.get("objective_value", float("inf"))
            record = SearchIteration(
                iteration=-1,
                candidate=eval_dict.get("candidate", {}),
                objective_value=obj_value,
                objective_details=[],
                is_promising=eval_dict.get("is_promising", False),
                stage_a_passed=True,
                stage_b_result=eval_dict.get("stage_b_result"),
                duration_seconds=0.0,
            )
            self._history.append(record)
            if obj_value < self._best_objective:
                self._best_objective = obj_value
                self._best_candidate = record.candidate

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

        total_duration = (datetime.now(UTC) - start_time).total_seconds()
        telemetry: Dict[str, Any] = {}
        if self._diversity_tracker is not None:
            telemetry["diversity_unique_mechanisms_total"] = (
                self._diversity_tracker.unique_mechanisms_total
            )
            telemetry["diversity_ratio"] = self._diversity_tracker.diversity_ratio
        if self._sentinel_evaluations:
            telemetry["sentinel_evaluations"] = self._sentinel_evaluations

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
            pareto_front=self._pareto_front,
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
        iter_start = datetime.now(UTC)
        is_sentinel = extract_sentinel_metadata(candidate) is not None

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
        policy_evaluation = None
        iter_duration = 0.0

        if stage_a_passed:
            self._stage_b_count += 1
            arbiter = self._config.resource_arbiter
            if arbiter is not None:
                with arbiter.acquire("jax"):
                    stage_b_result = self._stage_b(candidate, context)
            else:
                stage_b_result = self._stage_b(candidate, context)

            sim_results = stage_b_result.get("simulation_results", {})
            policy_evaluation = self._resolve_policy_evaluation(candidate, stage_b_result)
            if policy_evaluation is not None:
                objective_value = policy_evaluation.legacy_scalar_proxy
                objective_details = policy_evaluation.as_legacy_objectives()
            else:
                obj_eval = self._config.objective.evaluate(sim_results)
                objective_value = obj_eval.raw_value
                objective_details = self._config.objective.evaluate_detailed(sim_results)

            if not is_sentinel and objective_value < self._best_objective:
                self._best_objective = objective_value
                self._best_candidate = candidate
                logger.info(f"Iteration {iteration}: New best objective = {objective_value:.6f}")

            if not is_sentinel:
                self._update_policy_or_legacy_frontier(
                    candidate=candidate,
                    objective_details=objective_details,
                    policy_evaluation=policy_evaluation,
                    stage_b_result=stage_b_result,
                )

        iter_duration = (datetime.now(UTC) - iter_start).total_seconds()
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
            policy_evaluation=policy_evaluation,
        )
        if is_sentinel:
            self._sentinel_evaluations += 1
            return

        self._history.append(record)
        if self._diversity_tracker is not None:
            self._diversity_tracker.record_iteration(candidate)

    def _build_generation_context(
        self,
        context: Dict[str, Any],
        *,
        iteration: int,
    ) -> Dict[str, Any]:
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
            from polisyos.scientist.autotune.execution_plan import (
                build_execution_plan_generation_context,
            )
        except Exception:
            return enriched

        try:
            execution_plan_context = build_execution_plan_generation_context(
                history=self._history,
                current_best=self._best_candidate,
                context=enriched,
            )
        except Exception:
            return enriched

        if execution_plan_context.get("execution_plan_topology_mutation_payload"):
            enriched.update(execution_plan_context)
        return enriched

    def _build_lesson_hints(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        lesson_registry = context.get("lesson_registry")
        if lesson_registry is None:
            return []
        try:
            from polisyos.scientist.search.lessons import LessonQuery
            from polisyos.scientist.search.transfer_context import (
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
        except Exception:
            logger.debug("Lesson hint generation failed.", exc_info=True)
        return []

    def _resolve_policy_evaluation(
        self,
        candidate: Dict[str, Any],
        stage_b_result: Dict[str, Any] | None,
    ) -> "PolicyEvaluationVector | None":
        if not stage_b_result:
            return None

        try:
            from polisyos.scientist.policy_design.objectives import (
                PolicyEvaluationBundle,
                PolicyEvaluationVector,
            )
            from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
        except Exception:
            return None

        raw_vector = stage_b_result.get("policy_evaluation")
        if isinstance(raw_vector, PolicyEvaluationVector):
            return raw_vector
        if isinstance(raw_vector, dict):
            try:
                return PolicyEvaluationVector.model_validate(raw_vector)
            except Exception:
                logger.debug("Failed to parse policy_evaluation payload.", exc_info=True)

        objective_stack = self._config.policy_objective_stack
        if objective_stack is None:
            return None

        raw_bundle = (
            stage_b_result.get("policy_evaluation_bundle")
            or stage_b_result.get("_policy_evaluation_bundle")
        )
        if raw_bundle is None:
            return None
        try:
            if isinstance(raw_bundle, PolicyEvaluationBundle):
                bundle = raw_bundle
            else:
                bundle = PolicyEvaluationBundle.model_validate(raw_bundle)
        except Exception:
            logger.debug("Failed to parse policy_evaluation_bundle payload.", exc_info=True)
            return None

        if bundle.candidate is None:
            candidate_schema = (
                stage_b_result.get("_policy_candidate_schema")
                or stage_b_result.get("policy_candidate")
            )
            if isinstance(candidate_schema, PolicyCandidateSchema):
                bundle = bundle.model_copy(update={"candidate": candidate_schema})
            elif isinstance(candidate_schema, dict):
                try:
                    bundle = bundle.model_copy(
                        update={"candidate": PolicyCandidateSchema.model_validate(candidate_schema)}
                    )
                except Exception:
                    logger.debug("Failed to parse policy candidate payload.", exc_info=True)
            elif isinstance(candidate, dict) and "trinity_bundle" in candidate:
                try:
                    bundle = bundle.model_copy(
                        update={"candidate": PolicyCandidateSchema.model_validate(candidate)}
                    )
                except Exception:
                    logger.debug(
                        "Candidate did not validate as PolicyCandidateSchema.",
                        exc_info=True,
                    )

        try:
            return objective_stack.evaluate(bundle)
        except Exception:
            logger.debug("ObjectiveStack evaluation failed.", exc_info=True)
            return None

    def _update_policy_or_legacy_frontier(
        self,
        *,
        candidate: Dict[str, Any],
        objective_details: List[ObjectiveValue],
        policy_evaluation: "PolicyEvaluationVector | None",
        stage_b_result: Dict[str, Any] | None,
    ) -> None:
        registry = self._config.pareto_registry
        if policy_evaluation is not None and registry is not None:
            try:
                from polisyos.scientist.search.transfer_context import resolve_transfer_context
            except Exception:
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
                policy_family=(
                    str(policy_evaluation.metadata.get("policy_family") or "") or None
                ),
                promotion_metadata={
                    "iteration": len(self._history),
                    "feedback": dict((stage_b_result or {}).get("feedback", {})),
                },
                seed_payload=dict(candidate),
                task_family=(transfer_context.task_family if transfer_context is not None else None),
                domain=(transfer_context.domain if transfer_context is not None else None),
                transfer_context=transfer_context,
            )
            self._pareto_front = registry.as_legacy_frontier_payload(self._search_id)
            return

        if objective_details:
            self._update_pareto_front(candidate, objective_details)

    @staticmethod
    def _policy_candidate_hash(
        *,
        candidate: Dict[str, Any],
        policy_evaluation: "PolicyEvaluationVector",
        stage_b_result: Dict[str, Any],
    ) -> str:
        metadata_hash = str(policy_evaluation.metadata.get("candidate_hash", "")).strip()
        if metadata_hash:
            return metadata_hash
        explicit = stage_b_result.get("candidate_hash")
        if isinstance(explicit, str) and explicit:
            return explicit
        try:
            payload = json.dumps(candidate, sort_keys=True, separators=(",", ":"), default=str)
        except TypeError:
            payload = repr(candidate)
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _update_pareto_front(
        self,
        candidate: Dict[str, Any],
        objectives: List[ObjectiveValue],
    ) -> None:
        """Update the Pareto front with a new candidate if non-dominated."""
        new_point = {
            "candidate": candidate,
            "objectives": [
                {"name": o.name, "raw_value": o.raw_value, "direction": o.direction.value}
                for o in objectives
            ],
        }
        new_values = [o.normalized_value for o in objectives]

        # Remove points dominated by new_point
        surviving: List[Dict[str, Any]] = []
        for existing in self._pareto_front:
            existing_values = [o["raw_value"] * (-1 if o["direction"] == "maximize" else 1)
                               for o in existing["objectives"]]
            if not self._dominates(new_values, existing_values):
                surviving.append(existing)

        # Check if new_point is dominated by any survivor
        is_dominated = any(
            self._dominates(
                [o["raw_value"] * (-1 if o["direction"] == "maximize" else 1)
                 for o in p["objectives"]],
                new_values,
            )
            for p in surviving
        )
        if not is_dominated:
            surviving.append(new_point)

        # Cap at 100 points
        self._pareto_front = surviving[:100]

    @staticmethod
    def _dominates(a: List[float], b: List[float]) -> bool:
        """Return True if *a* dominates *b* (all <= and at least one <)."""
        if len(a) != len(b):
            return False
        at_least_one_better = False
        for ai, bi in zip(a, b):
            if ai > bi:
                return False
            if ai < bi:
                at_least_one_better = True
        return at_least_one_better

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
