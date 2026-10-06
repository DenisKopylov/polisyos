"""Bayesian candidate generator wrapping the methods.search strategies module."""

from __future__ import annotations

import hashlib
import json
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
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    ParameterType,
    StrategyState,
)

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
    if isinstance(value, bool):
        return _INVALID
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
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


class SearchSpace(NativeSearchSpace):
    """Autotune adapter backed by the canonical strategy ``SearchSpace``."""

    def __init__(self, bounds: list[dict[str, Any] | ParameterBounds]) -> None:
        super().__init__(bounds=[self._to_parameter_bound(bound) for bound in bounds])

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
    def param_bounds(self) -> list[ParameterBounds]:
        return self.bounds


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
        warm_start_bridge: Any = None,
        warm_start_fingerprint: Any = None,
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
        self._activity_started = False
        self._history_digests: list[str] = []
        self._resume_history_required = False
        if (warm_start_bridge is None) != (warm_start_fingerprint is None):
            raise ValueError("Warm-start bridge and configured target fingerprint must be paired")
        numerical_basis = None
        admission = None
        if warm_start_bridge is not None:
            numerical_basis = warm_start_bridge.target_basis(warm_start_fingerprint)
            admission = warm_start_bridge.admit_warm_start
            if (
                numerical_basis.metric != primary_metric
                or numerical_basis.direction.value != direction.value
                or numerical_basis.split != compare_split.value
            ):
                raise ValueError(
                    "Configured generator metric/direction/split differs from numerical target"
                )

        deps = _try_import_bayesian()
        if deps is not None and search_space is not None:
            BayesianConfig, BayesianOptimizer, _, _, _, _, _ = deps
            try:
                cfg = BayesianConfig(n_initial=n_initial, seed=seed)
                self._optimizer = BayesianOptimizer(
                    search_space,
                    config=cfg,
                    numerical_basis=numerical_basis,
                    warm_start_admission=admission,
                )
                self._botorch_available = self._optimizer.backend_available
            except Exception as exc:
                if numerical_basis is not None:
                    raise ValueError(
                        "Configured numerical warm-start receiver refused its basis"
                    ) from exc
                logger.warning("BayesianCandidateGenerator: optimizer init failed: %s", exc)
        if warm_start_bridge is not None:
            if self._optimizer is None:
                raise ValueError("Configured warm-start requires a native optimizer receiver")
            self.warm_start(warm_start_bridge.load_warm_start(warm_start_fingerprint))

    @property
    def botorch_available(self) -> bool:
        return self._botorch_available

    def warm_start(self, evaluations: list[Any]) -> None:
        """Pre-seed with historical methods.search strategy evaluations."""
        self._warm_evals.extend(evaluations)
        if self._optimizer is not None:
            self._optimizer.warm_start(evaluations)

    def configure_transfer(self, bridge: Any, fingerprint: Any) -> None:
        """Bind the owner-paired transfer reader before any generator activity.

        Construct and admit a fresh receiver first. A failed basis or CAS
        admission leaves this generator's previous optimizer and RNG untouched.
        """
        if bridge is None or fingerprint is None:
            raise ValueError("Configured transfer requires a paired bridge and target fingerprint")
        if self._activity_started or self._warm_evals or self._history_digests:
            raise ValueError("Transfer must be configured before warm/history/generation")
        replacement = BayesianCandidateGenerator(
            self._search_space,
            primary_metric=self._primary_metric,
            direction=self._direction,
            compare_split=self._compare_split,
            n_initial=self._n_initial,
            seed=self._seed,
            warm_start_bridge=bridge,
            warm_start_fingerprint=fingerprint,
        )
        self._optimizer = replacement._optimizer
        self._botorch_available = replacement._botorch_available
        self._warm_evals = replacement._warm_evals

    def _checkpoint_config(self) -> dict[str, Any]:
        return {
            "primary_metric": self._primary_metric,
            "direction": self._direction.value,
            "compare_split": self._compare_split.value,
            "space": self._search_space.sobol_space_fingerprint() if self._search_space else None,
            "n_initial": self._n_initial,
            "seed": self._seed,
            "numerical_basis": getattr(self._optimizer, "_basis_payload", None),
        }

    @staticmethod
    def _json_bytes(value: Any) -> bytes:
        try:
            return json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Generator checkpoint requires finite JSON data") from exc

    @classmethod
    def _history_row_digest(cls, evaluation: Any) -> str:
        """Bind converted numerical inputs; service custody owns the raw history.

        Conversion-generated timestamps and wall durations do not define a GP
        observation. Missing/nonfinite scores remain unavailable, never zero.
        """
        scalar = evaluation.scalar_score
        record = {
            "candidate_id": evaluation.candidate_id,
            "params": evaluation.params,
            "params_normalized": evaluation.params_normalized,
            "scalar_score": scalar if math.isfinite(scalar) else None,
            "stage_a_passed": evaluation.stage_a_passed,
            "status": evaluation.status.value,
            "provenance_ref": evaluation.provenance_ref,
            "identity": {
                key: evaluation.metadata[key]
                for key in _IDENTITY_KEYS
                | {
                    "numeric_transfer_basis",
                    "candidate_ref",
                    "evaluation_ref",
                    "transfer_history_ref",
                    "source_row_index",
                }
                if key in evaluation.metadata
            },
        }
        return hashlib.sha256(cls._json_bytes(record)).hexdigest()

    def get_state(self) -> dict[str, Any]:
        """Return a versioned wrapper plus the actual native strategy artifact."""
        if self._optimizer is None:
            raise ValueError("Generator checkpoint requires a native strategy receiver")
        return {
            "schema_version": "bayesian_candidate_generator.v1",
            "config": self._checkpoint_config(),
            "native_backend_available": self._botorch_available,
            "activity_started": self._activity_started,
            "history_digests": list(self._history_digests),
            "strategy_state": json.loads(self._optimizer.get_state().to_artifact()),
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Validate wrapper identity before the native atomic model/RNG restore."""
        fields = {
            "schema_version",
            "config",
            "native_backend_available",
            "activity_started",
            "history_digests",
            "strategy_state",
        }
        if type(state) is not dict or set(state) != fields:
            raise ValueError("Generator checkpoint fields are incomplete or unknown")
        if state["schema_version"] != "bayesian_candidate_generator.v1":
            raise ValueError("Unsupported generator checkpoint schema")
        if self._json_bytes(state["config"]) != self._json_bytes(self._checkpoint_config()):
            raise ValueError("Generator checkpoint metric/split/space/configuration changed")
        if type(state["native_backend_available"]) is not bool or (
            state["native_backend_available"] != self._botorch_available
        ):
            raise ValueError("Generator checkpoint native backend availability changed")
        if type(state["activity_started"]) is not bool:
            raise ValueError("Generator activity flag must be boolean")
        digests = state["history_digests"]
        if not isinstance(digests, list) or any(
            not isinstance(item, str)
            or len(item) != 64
            or any(c not in "0123456789abcdef" for c in item)
            for item in digests
        ):
            raise ValueError("Generator converted-history binding is invalid")
        if digests and not state["activity_started"]:
            raise ValueError("Generator history cannot precede activity")
        if self._optimizer is None:
            raise ValueError("Generator checkpoint requires a native strategy receiver")
        native = StrategyState.from_artifact(self._json_bytes(state["strategy_state"]))
        self._optimizer.set_state(native)
        self._activity_started = state["activity_started"]
        self._history_digests = list(digests)
        self._resume_history_required = True
        self._warm_evals = list(self._optimizer._warm_evals)

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._activity_started = True
        if not self._botorch_available or self._optimizer is None:
            return self._fallback_generate(history, current_best, context)

        evals = self._history_to_evaluations(history)
        digests = [self._history_row_digest(evaluation) for evaluation in evals]
        if (
            self._resume_history_required
            and digests[: len(self._history_digests)] != self._history_digests
        ):
            raise ValueError("Generator resume history differs from checkpoint numerical inputs")
        self._history_digests = digests
        self._resume_history_required = False
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
    def _history_parts(
        entry: Any,
    ) -> tuple[
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
                logger.warning(
                    "Skipping history entry %s: candidate params cannot be normalized", idx
                )
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
            raw_stage_a = getattr(
                entry, "stage_a_passed", entry_mapping.get("stage_a_passed", _MISSING)
            )
            valid_stage_type = raw_stage_a is _MISSING or type(raw_stage_a) is bool
            stage_a_passed = raw_stage_a is _MISSING or raw_stage_a is True
            if valid_stage_type:
                score, score_is_scalar = self._history_score(
                    entry=entry,
                    candidate=candidate,
                    stage_b_result=stage_b_result,
                    entry_mapping=entry_mapping,
                )
            else:
                score, score_is_scalar = _INVALID, True
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
            if not valid_stage_type:
                metadata["invalid_reason"] = "malformed_stage_a_passed"
            elif not has_score:
                metadata["invalid_reason"] = "missing_or_invalid_score"

            timestamp = getattr(entry, "timestamp", None)
            if not isinstance(timestamp, datetime):
                timestamp = datetime.now(UTC)
            duration = getattr(
                entry, "duration_seconds", entry_mapping.get("duration_seconds", 0.0)
            )
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

    scalar = -float(finite_value) if direction == MetricDirection.MAXIMIZE else float(finite_value)
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
