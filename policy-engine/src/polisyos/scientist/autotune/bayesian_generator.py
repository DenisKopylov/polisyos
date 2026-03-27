"""Bayesian candidate generator wrapping the search.strategies.bayesian module."""

from __future__ import annotations

import logging
from typing import Any

from .models import BenchmarkEvaluation, BenchmarkSplit, MetricDirection

logger = logging.getLogger(__name__)


def _try_import_bayesian():
    """Lazy import of BayesianOptimizer and dependencies."""
    try:
        from polisyos.scientist.search.strategies.bayesian import (
            BayesianConfig,
            BayesianOptimizer,
        )
        from polisyos.scientist.search.strategies.types import (
            Evaluation,
            EvaluationStatus,
            ParameterBounds,
        )
        from polisyos.scientist.search.objective import ObjectiveValue

        from polisyos.scientist.search.objective import OptimizationDirection

        return BayesianConfig, BayesianOptimizer, Evaluation, EvaluationStatus, ParameterBounds, ObjectiveValue, OptimizationDirection
    except ImportError:
        return None


class SearchSpace:
    """Minimal search space wrapper for BayesianOptimizer."""

    def __init__(self, bounds: list[dict[str, Any]]) -> None:
        self._bounds = bounds
        deps = _try_import_bayesian()
        if deps is None:
            self._param_bounds: list[Any] = []
            return
        _, _, _, _, ParameterBounds, _, _ = deps
        self._param_bounds = [
            ParameterBounds(
                name=b["name"],
                lower=b.get("lower", 0.0),
                upper=b.get("upper", 1.0),
            )
            for b in bounds
        ]

    @property
    def dim(self) -> int:
        return len(self._bounds)

    @property
    def param_bounds(self) -> list[Any]:
        return self._param_bounds


class BayesianCandidateGenerator:
    """CandidateGenerator backed by GP-based Bayesian optimization.

    Falls back to returning the last known best when botorch is unavailable.
    """

    def __init__(
        self,
        search_space: SearchSpace | None = None,
        *,
        primary_metric: str = "score",
        direction: MetricDirection = MetricDirection.MAXIMIZE,
        compare_split: BenchmarkSplit = BenchmarkSplit.HOLDOUT,
        n_initial: int = 6,
        seed: int = 42,
    ) -> None:
        self._primary_metric = primary_metric
        self._direction = direction
        self._compare_split = compare_split
        self._search_space = search_space
        self._n_initial = n_initial
        self._seed = seed
        self._optimizer: Any = None
        self._botorch_available = False
        self._warm_evals: list[Any] = []

        deps = _try_import_bayesian()
        if deps is not None and search_space is not None:
            BayesianConfig, BayesianOptimizer, _, _, _, _, _ = deps
            try:
                cfg = BayesianConfig(n_initial=n_initial, seed=seed)
                self._optimizer = BayesianOptimizer(search_space, config=cfg)
                self._botorch_available = True
                if self._warm_evals:
                    self._optimizer.warm_start(self._warm_evals)
            except Exception as exc:  # noqa: BLE001
                logger.warning("BayesianCandidateGenerator: optimizer init failed: %s", exc)

    @property
    def botorch_available(self) -> bool:
        return self._botorch_available

    def warm_start(self, evaluations: list[Any]) -> None:
        """Pre-seed with historical evaluations (search.strategies.types.Evaluation)."""
        self._warm_evals.extend(evaluations)
        if self._optimizer is not None:
            self._optimizer.warm_start(evaluations)

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._botorch_available or self._optimizer is None:
            return self._fallback_generate(history, current_best, context)

        evals = self._history_to_evaluations(history)
        try:
            candidate = self._optimizer.suggest(evals)
            return candidate.to_dict()
        except Exception as exc:  # noqa: BLE001
            logger.warning("BayesianCandidateGenerator: suggest failed: %s", exc)
            return self._fallback_generate(history, current_best, context)

    def _fallback_generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if current_best is not None:
            return dict(current_best)
        if history:
            last = history[-1]
            if isinstance(last, dict):
                return dict(last)
        return dict(context) if context else {}

    def _history_to_evaluations(self, history: list[Any]) -> list[Any]:
        deps = _try_import_bayesian()
        if deps is None:
            return []
        _, _, Evaluation, EvaluationStatus, _, ObjectiveValue, OptimizationDirection = deps

        evaluations: list[Any] = []
        for idx, entry in enumerate(history):
            if not isinstance(entry, dict):
                continue
            score = entry.get(self._primary_metric, 0.0)
            if self._direction == MetricDirection.MAXIMIZE:
                scalar = -float(score)
            else:
                scalar = float(score)

            params = {k: v for k, v in entry.items() if k != self._primary_metric}
            dim = self._search_space.dim if self._search_space else 0
            normalized = tuple(0.5 for _ in range(dim))

            evaluations.append(
                Evaluation(
                    candidate_id=f"hist_{idx}",
                    params=params,
                    params_normalized=normalized,
                    objectives=[ObjectiveValue(name=self._primary_metric, raw_value=scalar, direction=OptimizationDirection.MINIMIZE)],
                    scalar_score=scalar,
                    stage_a_passed=True,
                    status=EvaluationStatus.SUCCESS,
                )
            )
        return evaluations


def benchmark_to_evaluation(
    bench: BenchmarkEvaluation,
    *,
    primary_metric: str,
    direction: MetricDirection = MetricDirection.MAXIMIZE,
    split: BenchmarkSplit = BenchmarkSplit.HOLDOUT,
    dim: int = 0,
) -> Any | None:
    """Convert a BenchmarkEvaluation to a search.strategies Evaluation."""
    deps = _try_import_bayesian()
    if deps is None:
        return None
    _, _, Evaluation, EvaluationStatus, _, ObjectiveValue, OptimizationDirection = deps

    value = bench.primary_value(split=split, metric=primary_metric)
    if value is None:
        return None
    scalar = -float(value) if direction == MetricDirection.MAXIMIZE else float(value)

    return Evaluation(
        candidate_id=str(bench.candidate_ref.artifact_id)[:8],
        params=bench.metrics_for_split(split),
        params_normalized=tuple(0.5 for _ in range(dim)),
        objectives=[ObjectiveValue(name=primary_metric, raw_value=scalar, direction=OptimizationDirection.MINIMIZE)],
        scalar_score=scalar,
        stage_a_passed=True,
        status=EvaluationStatus.SUCCESS,
        metadata={"source": "benchmark_evaluation", "loop_id": bench.loop_id},
    )
