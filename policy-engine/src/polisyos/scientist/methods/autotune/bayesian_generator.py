"""Bayesian candidate generator wrapping the methods.search strategies module."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.scientist.methods.search.strategies.space import (
    SearchSpace as NativeSearchSpace,
)
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, ParameterType

from .models import BenchmarkEvaluation, BenchmarkSplit, MetricDirection

logger = logging.getLogger(__name__)

_MISSING = object()
_INVALID = object()
_IDENTITY_KEYS = frozenset(
    {
        "subject",
        "subject_id",
        "subject_version",
        "search_space_version",
        "data_snapshot",
        "dataset_version",
        "split",
        "origin",
        "candidate_id",
        "evaluation_id",
        "provenance_ref",
        "replicate_id",
        "replica_id",
        "seed",
    }
)


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _identity_value(value: Any) -> Any:
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, ArtifactID):
        return str(value)
    return value


def _merge_identity_sources(
    sources: tuple[Mapping[str, Any], ...],
) -> dict[str, Any] | None:
    """Merge identity claims only when every explicit claim agrees."""
    identity: dict[str, Any] = {}
    for source in sources:
        for key in _IDENTITY_KEYS:
            if key not in source or source[key] is None:
                continue
            value = _identity_value(source[key])
            if key in identity and identity[key] != value:
                return None
            identity[key] = value
    return identity


def _finite_float(value: Any) -> float | object:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return _INVALID
    return result if math.isfinite(result) else _INVALID


def _try_import_bayesian():
    """Lazy import of BayesianOptimizer and dependencies."""
    try:
        from polisyos.scientist.methods.search.objective import (
            ObjectiveValue,
            OptimizationDirection,
        )
        from polisyos.scientist.methods.search.strategies.bayesian import (
            BayesianConfig,
            BayesianOptimizer,
        )
        from polisyos.scientist.methods.search.strategies.types import (
            Evaluation,
            EvaluationStatus,
            ParameterBounds,
        )

        return (
            BayesianConfig,
            BayesianOptimizer,
            Evaluation,
            EvaluationStatus,
            ParameterBounds,
            ObjectiveValue,
            OptimizationDirection,
        )
    except ImportError:
        return None


class SearchSpace:
    """Autotune adapter backed by the canonical strategy ``SearchSpace``."""

    def __init__(self, bounds: list[dict[str, Any] | ParameterBounds]) -> None:
        self._native = NativeSearchSpace(
            bounds=[self._to_parameter_bound(bound) for bound in bounds]
        )

    @staticmethod
    def _to_parameter_bound(bound: dict[str, Any] | ParameterBounds) -> ParameterBounds:
        if isinstance(bound, ParameterBounds):
            return bound

        raw_dtype = bound.get("dtype", ParameterType.CONTINUOUS)
        dtype = raw_dtype if isinstance(raw_dtype, ParameterType) else ParameterType(raw_dtype)
        categories = bound.get("categories")
        if categories is not None:
            categories = tuple(categories)
        lower = bound.get("lower", 0.0)
        upper = bound.get("upper", 1.0)
        if lower is None:
            lower = 0.0
        if upper is None:
            upper = 1.0
        return ParameterBounds(
            name=str(bound["name"]),
            lower=lower,
            upper=upper,
            dtype=dtype,
            log_scale=bool(bound.get("log_scale", False)),
            categories=categories,
        )

    @property
    def bounds(self) -> list[ParameterBounds]:
        """Return the canonical parameter bounds used by the strategy."""
        return self._native.bounds

    @property
    def dim(self) -> int:
        return self._native.dim

    @property
    def param_bounds(self) -> list[Any]:
        """Compatibility alias for consumers that inspect parameter bounds."""
        return self._native.bounds

    @property
    def names(self) -> list[str]:
        """Return canonical expanded parameter names."""
        return self._native.names

    def normalize(self, params: dict[str, Any]) -> tuple[float, ...]:
        """Normalize parameters through the canonical strategy implementation."""
        return self._native.normalize(params)

    def denormalize(self, vector: tuple[float, ...]) -> dict[str, Any]:
        """Resolve a relaxed vector to the effective typed execution."""
        return self._native.denormalize(vector)

    def sample_sobol(self, n_samples: int, seed: int = 42) -> list[tuple[float, ...]]:
        """Sample relaxed vectors through the canonical strategy implementation."""
        return self._native.sample_sobol(n_samples=n_samples, seed=seed)

    def to_botorch_bounds(self) -> Any:
        """Delegate optional BoTorch bounds construction to the native space."""
        return self._native.to_botorch_bounds()


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
            except Exception as exc:
                logger.warning("BayesianCandidateGenerator: optimizer init failed: %s", exc)

    @property
    def botorch_available(self) -> bool:
        return self._botorch_available

    def warm_start(self, evaluations: list[Any]) -> None:
        """Pre-seed with historical methods.search strategy evaluations."""
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
        except Exception as exc:
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

    @staticmethod
    def _history_parts(entry: Any) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
    ]:
        """Extract candidate, stage-B, entry, and entry-metadata mappings."""
        if isinstance(entry, Mapping):
            entry_mapping = dict(entry)
            candidate = _as_mapping(entry_mapping.get("candidate", entry_mapping))
            stage_b_result = _as_mapping(entry_mapping.get("stage_b_result"))
            entry_metadata = _as_mapping(entry_mapping.get("metadata"))
            return candidate, stage_b_result, entry_mapping, entry_metadata

        candidate = _as_mapping(getattr(entry, "candidate", None))
        stage_b_result = _as_mapping(getattr(entry, "stage_b_result", None))
        entry_metadata = _as_mapping(getattr(entry, "metadata", None))
        return candidate, stage_b_result, {}, entry_metadata

    def _history_params(
        self,
        *,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any],
        entry_mapping: dict[str, Any],
    ) -> dict[str, Any]:
        for source in (stage_b_result, candidate, entry_mapping):
            explicit = source.get("params")
            if isinstance(explicit, Mapping):
                return dict(explicit)

        reserved = {
            self._primary_metric,
            "candidate",
            "stage_b_result",
            "objective_value",
            "objective_details",
            "is_promising",
            "stage_a_passed",
            "duration_seconds",
            "timestamp",
            "policy_evaluation",
            "semantic",
            "_strategy_metadata",
            "metadata",
        }
        return {key: value for key, value in candidate.items() if key not in reserved}

    def _history_score(
        self,
        *,
        entry: Any,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any],
        entry_mapping: dict[str, Any],
    ) -> tuple[float | object, bool]:
        """Return one finite metric and whether it is already scalarized."""
        metric_sources = (
            stage_b_result,
            _as_mapping(stage_b_result.get("simulation_results")),
            _as_mapping(stage_b_result.get("metrics")),
            entry_mapping,
            candidate,
        )
        for source in metric_sources:
            if self._primary_metric not in source:
                continue
            value = _finite_float(source[self._primary_metric])
            return value, False

        objective_details = getattr(entry, "objective_details", None)
        if objective_details is None:
            objective_details = entry_mapping.get("objective_details")
        if isinstance(objective_details, list):
            for objective in objective_details:
                if isinstance(objective, Mapping):
                    name = objective.get("name")
                    raw_value = objective.get("raw_value")
                else:
                    name = getattr(objective, "name", None)
                    raw_value = getattr(objective, "raw_value", None)
                if name == self._primary_metric:
                    value = _finite_float(raw_value)
                    return value, False

        objective_value = getattr(entry, "objective_value", _MISSING)
        if objective_value is _MISSING:
            objective_value = entry_mapping.get("objective_value", _MISSING)
        if objective_value is not _MISSING:
            value = _finite_float(objective_value)
            return value, True
        return _MISSING, True

    @staticmethod
    def _history_identity(
        *,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any],
        entry_mapping: dict[str, Any],
        entry_metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        candidate_metadata = _as_mapping(candidate.get("_strategy_metadata"))
        stage_b_metadata = _as_mapping(stage_b_result.get("metadata"))
        return _merge_identity_sources(
            (
                entry_mapping,
                entry_metadata,
                candidate,
                candidate_metadata,
                stage_b_result,
                stage_b_metadata,
            )
        )

    def _history_to_evaluations(self, history: list[Any]) -> list[Any]:
        deps = _try_import_bayesian()
        if deps is None or self._search_space is None:
            return []
        _, _, Evaluation, EvaluationStatus, _, ObjectiveValue, OptimizationDirection = deps

        evaluations: list[Any] = []
        required_names = {bound.name for bound in self._search_space.bounds}
        for idx, entry in enumerate(history):
            candidate, stage_b_result, entry_mapping, entry_metadata = self._history_parts(entry)
            params = self._history_params(
                candidate=candidate,
                stage_b_result=stage_b_result,
                entry_mapping=entry_mapping,
            )
            if not required_names.issubset(params):
                logger.warning(
                    "Skipping history entry %s: candidate params are incomplete for the search space",
                    idx,
                )
                continue
            try:
                normalized = tuple(self._search_space.normalize(params))
            except (TypeError, ValueError):
                logger.warning("Skipping history entry %s: candidate params cannot be normalized", idx)
                continue

            identity = self._history_identity(
                candidate=candidate,
                stage_b_result=stage_b_result,
                entry_mapping=entry_mapping,
                entry_metadata=entry_metadata,
            )
            if identity is None:
                logger.warning("Skipping history entry %s: conflicting identity fields", idx)
                continue
            candidate_id = str(identity.get("candidate_id") or f"hist_{idx}")
            score, score_is_scalar = self._history_score(
                entry=entry,
                candidate=candidate,
                stage_b_result=stage_b_result,
                entry_mapping=entry_mapping,
            )
            has_score = score not in {_MISSING, _INVALID}
            if has_score:
                score_value = float(score)
                scalar = (
                    score_value
                    if score_is_scalar or self._direction == MetricDirection.MINIMIZE
                    else -score_value
                )
            else:
                scalar = math.inf

            stage_a_passed = bool(
                getattr(entry, "stage_a_passed", entry_mapping.get("stage_a_passed", True))
            )
            feedback = _as_mapping(stage_b_result.get("feedback"))
            reported_status = str(
                feedback.get("status") or stage_b_result.get("status") or ""
            ).lower()
            if not stage_a_passed:
                status = EvaluationStatus.STAGE_A_REJECT
            elif not has_score or reported_status in {
                "error",
                "failed",
                "invalid",
                EvaluationStatus.STAGE_B_ERROR.value,
            }:
                status = EvaluationStatus.STAGE_B_ERROR
            else:
                status = EvaluationStatus.SUCCESS

            metadata = dict(entry_metadata)
            metadata.update(_as_mapping(candidate.get("_strategy_metadata")))
            metadata.update(_as_mapping(stage_b_result.get("metadata")))
            metadata.update(
                {
                    "source": "search_iteration",
                    "params": dict(params),
                    "params_normalized": list(normalized),
                }
            )
            for key, value in identity.items():
                metadata[key] = value
            if not has_score:
                metadata["invalid_reason"] = "missing_or_invalid_score"

            timestamp = getattr(entry, "timestamp", None)
            if not isinstance(timestamp, datetime):
                timestamp = datetime.now(UTC)
            duration = getattr(entry, "duration_seconds", entry_mapping.get("duration_seconds", 0.0))
            try:
                duration_seconds = float(duration)
            except (TypeError, ValueError):
                duration_seconds = 0.0
            provenance_ref = identity.get("provenance_ref")
            evaluations.append(
                Evaluation(
                    candidate_id=candidate_id,
                    params=dict(params),
                    params_normalized=normalized,
                    objectives=[
                        ObjectiveValue(
                            name=self._primary_metric,
                            raw_value=scalar,
                            direction=OptimizationDirection.MINIMIZE,
                        )
                    ],
                    scalar_score=scalar,
                    stage_a_passed=stage_a_passed,
                    stage_b_result=dict(stage_b_result) or None,
                    status=status,
                    timestamp=timestamp,
                    wall_time_seconds=duration_seconds,
                    provenance_ref=str(provenance_ref) if provenance_ref is not None else None,
                    metadata=metadata,
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
    search_space: Any | None = None,
) -> Any | None:
    """Convert a BenchmarkEvaluation to a methods.search strategy Evaluation."""
    deps = _try_import_bayesian()
    if deps is None:
        return None
    _, _, Evaluation, EvaluationStatus, _, ObjectiveValue, OptimizationDirection = deps

    runtime_split = bench.resolved_runtime_split_type()
    if runtime_split != split:
        return None
    benchmark_metadata = dict(bench.metadata)
    benchmark_identity = _merge_identity_sources(
        (
            {"candidate_id": bench.candidate_ref.artifact_id, "split": runtime_split},
            benchmark_metadata,
            _as_mapping(benchmark_metadata.get("metadata")),
        )
    )
    if benchmark_identity is None:
        return None
    value = bench.primary_value(split=split, metric=primary_metric)
    if value is None:
        return None
    finite_value = _finite_float(value)
    if finite_value is _INVALID:
        return None

    raw_params = benchmark_metadata.get("params", benchmark_metadata.get("candidate_params"))
    if not isinstance(raw_params, Mapping):
        return None
    params = dict(raw_params)

    if search_space is not None:
        try:
            params_normalized = tuple(search_space.normalize(params))
        except (TypeError, ValueError):
            return None
    else:
        raw_normalized = benchmark_metadata.get("params_normalized")
        if not isinstance(raw_normalized, (list, tuple)):
            return None
        try:
            params_normalized = tuple(float(item) for item in raw_normalized)
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(item) for item in params_normalized):
            return None
    if dim and len(params_normalized) != dim:
        return None

    scalar = (
        -float(finite_value)
        if direction == MetricDirection.MAXIMIZE
        else float(finite_value)
    )
    split_value = split.value
    metadata = {
        **benchmark_metadata,
        "source": "benchmark_evaluation",
        "loop_id": bench.loop_id,
        "suite_id": bench.suite_id,
        "suite_version": bench.suite_version,
        "split": split_value,
        "params": dict(params),
        "params_normalized": list(params_normalized),
    }
    candidate_id = str(bench.candidate_ref.artifact_id)

    return Evaluation(
        candidate_id=candidate_id,
        params=params,
        params_normalized=params_normalized,
        objectives=[
            ObjectiveValue(
                name=primary_metric, raw_value=scalar, direction=OptimizationDirection.MINIMIZE
            )
        ],
        scalar_score=scalar,
        stage_a_passed=True,
        status=EvaluationStatus.SUCCESS,
        provenance_ref=str(benchmark_metadata["provenance_ref"])
        if benchmark_metadata.get("provenance_ref") is not None
        else None,
        metadata=metadata,
    )
