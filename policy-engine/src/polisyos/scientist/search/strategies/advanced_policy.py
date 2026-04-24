"""Offline-gated advanced search policies for Scientist optimization.

This module provides deterministic, dependency-light implementations of the
WS-3C search policy surface: ASHA/BOHB-style scheduling, CMA-ES exploration,
learned VOI/routing, GP-like cheap-stage surrogates, constraint propagation,
and population-based training. All default-on decisions are guarded by an
explicit offline-validation gate.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.search.strategies.types import Evaluation, PolicyCandidate

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from polisyos.scientist.search.strategies.space import SearchSpace

__all__ = [
    "ASHADecision",
    "ASHAScheduler",
    "AdvancedSearchPolicyConfig",
    "AdvancedSearchPolicyReport",
    "AdvancedSearchPolicyRolloutStatus",
    "BOHBSampler",
    "CMAESExplorer",
    "ConstraintPropagationResult",
    "ConstraintSpec",
    "ExplicitConstraintPropagator",
    "GaussianProcessCheapStageSurrogate",
    "LearnedRoutingPolicy",
    "LearnedVOIPolicy",
    "PopulationBasedTrainingScheduler",
    "PopulationMember",
    "RoutingTrainingExample",
    "VOITrainingExample",
    "build_advanced_search_policy_report",
]


class AdvancedSearchPolicyConfig(BaseModel):
    """Feature-gated advanced search policy configuration."""

    model_config = ConfigDict(extra="forbid")

    enable_bohb: bool = False
    enable_asha: bool = False
    enable_cma_es: bool = False
    enable_learned_voi: bool = False
    enable_learned_routing: bool = False
    enable_gp_surrogate: bool = False
    enable_constraint_propagation: bool = True
    enable_population_based_training: bool = False
    offline_validation_ref: str | None = None
    default_enable_requested: bool = False
    rationale: str = (
        "Advanced search policies stay offline-gated until comparative "
        "trajectory evaluation beats the Reflexion-only baseline."
    )

    @property
    def requested_policies(self) -> list[str]:
        policies: list[str] = []
        for field_name, policy_name in (
            ("enable_bohb", "bohb"),
            ("enable_asha", "asha"),
            ("enable_cma_es", "cma_es"),
            ("enable_learned_voi", "learned_voi"),
            ("enable_learned_routing", "learned_routing"),
            ("enable_gp_surrogate", "gp_surrogate"),
            ("enable_constraint_propagation", "constraint_propagation"),
            ("enable_population_based_training", "population_based_training"),
        ):
            if bool(getattr(self, field_name)):
                policies.append(policy_name)
        return policies

    @property
    def offline_gate_passed(self) -> bool:
        experimental = [
            name for name in self.requested_policies if name != "constraint_propagation"
        ]
        return not experimental or bool(self.offline_validation_ref)


class AdvancedSearchPolicyReport(BaseModel):
    """Machine-readable search-policy readiness report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    requested_policies: list[str] = Field(default_factory=list)
    offline_validation_ref: str | None = None
    offline_gate_passed: bool = False
    rollout_status: AdvancedSearchPolicyRolloutStatus
    default_enable_eligible: bool = False
    default_enable_blockers: list[str] = Field(default_factory=list)
    capabilities: dict[str, str] = Field(default_factory=dict)
    rationale: str = Field(min_length=1)


class AdvancedSearchPolicyRolloutStatus(StrEnum):
    """Explicit rollout posture for WS-3C search policy bundles."""

    BASELINE_ONLY = "baseline_only"
    OFFLINE_GATED = "offline_gated"
    DEFAULT_ENABLE_ELIGIBLE = "default_enable_eligible"


class ConstraintSpec(BaseModel):
    """One explicit constraint propagated through search candidates."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    metric_key: str = Field(min_length=1)
    comparator: Literal["<=", ">=", "<", ">", "=="] = "<="
    threshold: float
    severity: Literal["warning", "blocker"] = "blocker"
    rationale: str = Field(min_length=1)

    def passed(self, metrics: Mapping[str, float]) -> bool | None:
        value = metrics.get(self.metric_key)
        if value is None or not math.isfinite(float(value)):
            return None
        observed = float(value)
        if self.comparator == "<=":
            return observed <= self.threshold
        if self.comparator == ">=":
            return observed >= self.threshold
        if self.comparator == "<":
            return observed < self.threshold
        if self.comparator == ">":
            return observed > self.threshold
        return math.isclose(observed, self.threshold, rel_tol=1e-9, abs_tol=1e-12)


class ConstraintPropagationResult(BaseModel):
    """Constraint evaluation result for one candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    feasible: bool
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)
    penalty: float = Field(default=0.0, ge=0.0)


class ExplicitConstraintPropagator:
    """Apply typed constraints before expensive stages are scheduled."""

    def __init__(self, constraints: Sequence[ConstraintSpec]) -> None:
        self._constraints = list(constraints)

    def evaluate(
        self,
        candidate: PolicyCandidate | str,
        metrics: Mapping[str, float],
    ) -> ConstraintPropagationResult:
        candidate_id = (
            candidate.candidate_id if isinstance(candidate, PolicyCandidate) else str(candidate)
        )
        warnings: list[str] = []
        blockers: list[str] = []
        missing: list[str] = []
        penalty = 0.0
        for constraint in self._constraints:
            passed = constraint.passed(metrics)
            if passed is None:
                missing.append(constraint.metric_key)
                penalty += 0.25
                continue
            if passed:
                continue
            value = float(metrics.get(constraint.metric_key, 0.0))
            gap = abs(value - constraint.threshold)
            penalty += max(gap, 1e-9)
            if constraint.severity == "blocker":
                blockers.append(constraint.name)
            else:
                warnings.append(constraint.name)
        return ConstraintPropagationResult(
            candidate_id=candidate_id,
            feasible=not blockers,
            warnings=warnings,
            blockers=blockers,
            missing_metrics=sorted(set(missing)),
            penalty=penalty,
        )


class ASHADecision(BaseModel):
    """ASHA scheduling decision for one evaluated candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    action: Literal["promote", "hold", "stop"]
    current_fidelity: int = Field(ge=1)
    next_fidelity: int | None = Field(default=None, ge=1)
    rank: int | None = Field(default=None, ge=1)
    cutoff_rank: int | None = Field(default=None, ge=1)
    reason: str = Field(min_length=1)


class ASHAScheduler:
    """Deterministic asynchronous successive-halving scheduler."""

    def __init__(self, *, eta: int = 3, max_fidelity: int = 81, min_peer_count: int = 2) -> None:
        if eta < 2:
            raise ValueError("eta must be >= 2")
        self._eta = eta
        self._max_fidelity = max_fidelity
        self._min_peer_count = min_peer_count

    def decide(self, evaluations: Sequence[Evaluation], current: Evaluation) -> ASHADecision:
        fidelity = _evaluation_fidelity(current)
        peers = [
            item for item in evaluations if item.is_valid and _evaluation_fidelity(item) == fidelity
        ]
        if current not in peers and current.is_valid:
            peers.append(current)
        if len(peers) < self._min_peer_count:
            return ASHADecision(
                candidate_id=current.candidate_id,
                action="hold",
                current_fidelity=fidelity,
                reason="insufficient_peer_count",
            )
        ranked = sorted(peers, key=lambda item: (-item.scalar_score, item.candidate_id))
        rank = next(
            index + 1
            for index, item in enumerate(ranked)
            if item.candidate_id == current.candidate_id
        )
        cutoff = max(1, math.ceil(len(ranked) / self._eta))
        if rank > cutoff:
            return ASHADecision(
                candidate_id=current.candidate_id,
                action="stop",
                current_fidelity=fidelity,
                rank=rank,
                cutoff_rank=cutoff,
                reason="below_asha_cutoff",
            )
        next_fidelity = fidelity * self._eta
        if next_fidelity > self._max_fidelity:
            return ASHADecision(
                candidate_id=current.candidate_id,
                action="hold",
                current_fidelity=fidelity,
                rank=rank,
                cutoff_rank=cutoff,
                reason="max_fidelity_reached",
            )
        return ASHADecision(
            candidate_id=current.candidate_id,
            action="promote",
            current_fidelity=fidelity,
            next_fidelity=next_fidelity,
            rank=rank,
            cutoff_rank=cutoff,
            reason="within_asha_cutoff",
        )


class BOHBSampler:
    """Small BOHB-style sampler using elite KDE-like coordinate resampling."""

    def __init__(self, space: SearchSpace, *, seed: int = 42, top_fraction: float = 0.35) -> None:
        self._space = space
        self._rng = _deterministic_rng(seed)
        self._top_fraction = min(0.9, max(0.05, top_fraction))

    def suggest_batch(
        self,
        evaluations: Sequence[Evaluation],
        batch_size: int,
        *,
        min_fidelity: int = 1,
    ) -> list[PolicyCandidate]:
        valid = [item for item in evaluations if item.is_valid]
        if len(valid) < 3:
            return [self._random_candidate("bohb_sobol", min_fidelity) for _ in range(batch_size)]
        elite_count = max(1, math.ceil(len(valid) * self._top_fraction))
        elites = sorted(
            valid,
            key=lambda item: (-item.scalar_score, item.candidate_id),
        )[:elite_count]
        candidates: list[PolicyCandidate] = []
        for _ in range(batch_size):
            base = self._rng.choice(elites)
            vector = []
            for value in base.params_normalized:
                jitter = self._rng.gauss(0.0, 0.12)
                vector.append(min(1.0, max(0.0, value + jitter)))
            candidates.append(
                PolicyCandidate(
                    params=self._space.denormalize(tuple(vector)),
                    params_normalized=tuple(vector),
                    source_strategy="bohb",
                    metadata={"fidelity": min_fidelity, "elite_parent": base.candidate_id},
                )
            )
        return candidates

    def _random_candidate(self, source: str, fidelity: int) -> PolicyCandidate:
        vector = tuple(self._rng.random() for _ in range(self._space.dim))
        return PolicyCandidate(
            params=self._space.denormalize(vector),
            params_normalized=vector,
            source_strategy=source,
            metadata={"fidelity": fidelity},
        )


class CMAESExplorer:
    """Diagonal-CMA-ES style explorer over normalized search vectors."""

    def __init__(self, space: SearchSpace, *, seed: int = 42, sigma: float = 0.25) -> None:
        self._space = space
        self._rng = _deterministic_rng(seed)
        self._mean = [0.5 for _ in range(space.dim)]
        self._sigma = [max(1e-3, sigma) for _ in range(space.dim)]

    def suggest_batch(self, batch_size: int) -> list[PolicyCandidate]:
        candidates: list[PolicyCandidate] = []
        for _ in range(batch_size):
            vector = tuple(
                min(1.0, max(0.0, self._rng.gauss(mean, sigma)))
                for mean, sigma in zip(self._mean, self._sigma, strict=False)
            )
            candidates.append(
                PolicyCandidate(
                    params=self._space.denormalize(vector),
                    params_normalized=vector,
                    source_strategy="cma_es",
                )
            )
        return candidates

    def update(self, evaluations: Sequence[Evaluation], *, elite_fraction: float = 0.5) -> None:
        valid = [item for item in evaluations if item.is_valid]
        if not valid:
            return
        elite_count = max(1, math.ceil(len(valid) * min(0.9, max(0.05, elite_fraction))))
        elites = sorted(
            valid,
            key=lambda item: (-item.scalar_score, item.candidate_id),
        )[:elite_count]
        for dim in range(self._space.dim):
            values = [item.params_normalized[dim] for item in elites]
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            self._mean[dim] = min(1.0, max(0.0, mean))
            self._sigma[dim] = min(0.5, max(0.02, math.sqrt(variance) + 0.03))


class GaussianProcessCheapStageSurrogate:
    """RBF-kernel ridge surrogate used when heavy GP dependencies are unavailable."""

    def __init__(self, *, length_scale: float = 0.35, ridge: float = 1e-6) -> None:
        self._length_scale = max(length_scale, 1e-6)
        self._ridge = max(ridge, 1e-12)
        self._x: list[tuple[float, ...]] = []
        self._y: list[float] = []
        self._alpha: list[float] = []

    @property
    def fitted(self) -> bool:
        return bool(self._x and self._alpha)

    def fit(self, evaluations: Sequence[Evaluation]) -> None:
        valid = [item for item in evaluations if item.is_valid]
        self._x = [tuple(float(value) for value in item.params_normalized) for item in valid]
        self._y = [float(item.scalar_score) for item in valid]
        if not self._x:
            self._alpha = []
            return
        try:
            import numpy as np

            kernel = np.asarray(
                [[self._rbf(a, b) for b in self._x] for a in self._x],
                dtype=float,
            )
            kernel += self._ridge * np.eye(len(self._x))
            alpha = np.linalg.solve(kernel, np.asarray(self._y, dtype=float))
            self._alpha = [float(value) for value in alpha.tolist()]
        except Exception:
            mean = sum(self._y) / len(self._y)
            self._alpha = [mean for _ in self._y]

    def predict(self, vectors: Sequence[Sequence[float]]) -> tuple[list[float], list[float]]:
        if not self.fitted:
            return [0.0 for _ in vectors], [1.0 for _ in vectors]
        means: list[float] = []
        stds: list[float] = []
        y_mean = sum(self._y) / len(self._y)
        y_var = sum((value - y_mean) ** 2 for value in self._y) / max(len(self._y), 1)
        for vector in vectors:
            x = tuple(float(value) for value in vector)
            weights = [self._rbf(x, train) for train in self._x]
            mean = sum(weight * alpha for weight, alpha in zip(weights, self._alpha, strict=False))
            confidence = min(1.0, max(weights, default=0.0))
            means.append(float(mean))
            stds.append(math.sqrt(max(y_var, 1e-9)) * (1.0 - confidence))
        return means, stds

    def _rbf(self, left: Sequence[float], right: Sequence[float]) -> float:
        dist2 = sum((a - b) ** 2 for a, b in zip(left, right, strict=False))
        return math.exp(-0.5 * dist2 / (self._length_scale**2))


class VOITrainingExample(BaseModel):
    """Training row for learned value-of-information scoring."""

    model_config = ConfigDict(extra="forbid")

    features: dict[str, float] = Field(default_factory=dict)
    realized_value: float


class LearnedVOIPolicy:
    """Ridge-linear learned VOI model with deterministic fallback."""

    def __init__(self, *, ridge: float = 0.1) -> None:
        self._ridge = max(ridge, 1e-9)
        self._feature_names: list[str] = []
        self._weights: list[float] = []
        self._bias = 0.0

    def fit(self, examples: Sequence[VOITrainingExample]) -> None:
        self._feature_names = sorted({key for item in examples for key in item.features})
        if not examples or not self._feature_names:
            self._weights = []
            self._bias = 0.0
            return
        try:
            import numpy as np

            x = np.asarray(
                [
                    [1.0, *[item.features.get(name, 0.0) for name in self._feature_names]]
                    for item in examples
                ],
                dtype=float,
            )
            y = np.asarray([item.realized_value for item in examples], dtype=float)
            reg = self._ridge * np.eye(x.shape[1])
            reg[0, 0] = 0.0
            weights = np.linalg.solve(x.T @ x + reg, x.T @ y)
            self._bias = float(weights[0])
            self._weights = [float(value) for value in weights[1:].tolist()]
        except Exception:
            self._bias = sum(item.realized_value for item in examples) / len(examples)
            self._weights = [0.0 for _ in self._feature_names]

    def score(self, features: Mapping[str, float]) -> float:
        return self._bias + sum(
            weight * float(features.get(name, 0.0))
            for name, weight in zip(self._feature_names, self._weights, strict=False)
        )


class RoutingTrainingExample(BaseModel):
    """Training row for learned routing policy."""

    model_config = ConfigDict(extra="forbid")

    features: dict[str, float] = Field(default_factory=dict)
    route: str = Field(min_length=1)
    reward: float = 0.0


class LearnedRoutingPolicy:
    """Simple reward-weighted centroid router for offline learned routing."""

    def __init__(self) -> None:
        self._route_centroids: dict[str, dict[str, float]] = {}

    def fit(self, examples: Sequence[RoutingTrainingExample]) -> None:
        totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        weights: dict[str, float] = defaultdict(float)
        for item in examples:
            weight = max(float(item.reward), 1e-6)
            weights[item.route] += weight
            for key, value in item.features.items():
                totals[item.route][key] += weight * float(value)
        self._route_centroids = {
            route: {key: value / max(weights[route], 1e-9) for key, value in values.items()}
            for route, values in totals.items()
        }

    def route(self, features: Mapping[str, float]) -> str | None:
        if not self._route_centroids:
            return None
        return max(
            self._route_centroids,
            key=lambda route: -_squared_distance(features, self._route_centroids[route]),
        )


class PopulationMember(BaseModel):
    """One member in a population-based training step."""

    model_config = ConfigDict(extra="forbid")

    member_id: str = Field(min_length=1)
    params: dict[str, float] = Field(default_factory=dict)
    score: float = 0.0
    generation: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PopulationBasedTrainingScheduler:
    """Exploit/explore scheduler for population-based search policies."""

    def __init__(self, *, seed: int = 42, perturbation: float = 0.2) -> None:
        self._rng = _deterministic_rng(seed)
        self._perturbation = max(0.0, perturbation)

    def step(self, population: Sequence[PopulationMember]) -> list[PopulationMember]:
        if not population:
            return []
        ranked = sorted(population, key=lambda item: (-item.score, item.member_id))
        elite_count = max(1, len(ranked) // 2)
        elites = ranked[:elite_count]
        next_population: list[PopulationMember] = []
        for index, member in enumerate(ranked):
            if index < elite_count:
                next_population.append(
                    member.model_copy(update={"generation": member.generation + 1})
                )
                continue
            parent = elites[index % len(elites)]
            mutated = {
                key: max(
                    0.0,
                    min(
                        1.0,
                        value
                        * (
                            1.0
                            + self._rng.uniform(
                                -self._perturbation,
                                self._perturbation,
                            )
                        ),
                    ),
                )
                for key, value in parent.params.items()
            }
            next_population.append(
                PopulationMember(
                    member_id=member.member_id,
                    params=mutated,
                    score=parent.score,
                    generation=member.generation + 1,
                    metadata={"exploited_parent": parent.member_id},
                )
            )
        return next_population


def build_advanced_search_policy_report(
    config: AdvancedSearchPolicyConfig,
) -> AdvancedSearchPolicyReport:
    """Build an offline-gating report for advanced search policies."""

    requested = config.requested_policies
    experimental_requested = [name for name in requested if name != "constraint_propagation"]
    blockers: list[str] = []
    if not config.offline_gate_passed:
        blockers.append("missing_offline_validation_ref")
    if config.default_enable_requested and not config.offline_gate_passed:
        blockers.append("default_enable_requested_without_offline_gate")
    capabilities = {
        "bohb": "enabled" if config.enable_bohb else "available_offline_gated",
        "asha": "enabled" if config.enable_asha else "available_offline_gated",
        "cma_es": "enabled" if config.enable_cma_es else "available_offline_gated",
        "learned_voi": "enabled" if config.enable_learned_voi else "available_offline_gated",
        "learned_routing": (
            "enabled" if config.enable_learned_routing else "available_offline_gated"
        ),
        "gp_surrogate": "enabled" if config.enable_gp_surrogate else "available_offline_gated",
        "constraint_propagation": (
            "enabled" if config.enable_constraint_propagation else "disabled"
        ),
        "population_based_training": (
            "enabled" if config.enable_population_based_training else "available_offline_gated"
        ),
    }
    default_enable_eligible = (
        bool(experimental_requested) and config.offline_gate_passed and not blockers
    )
    if not experimental_requested:
        rollout_status = AdvancedSearchPolicyRolloutStatus.BASELINE_ONLY
    elif default_enable_eligible:
        rollout_status = AdvancedSearchPolicyRolloutStatus.DEFAULT_ENABLE_ELIGIBLE
    else:
        rollout_status = AdvancedSearchPolicyRolloutStatus.OFFLINE_GATED
    return AdvancedSearchPolicyReport(
        requested_policies=requested,
        offline_validation_ref=config.offline_validation_ref,
        offline_gate_passed=config.offline_gate_passed,
        rollout_status=rollout_status,
        default_enable_eligible=default_enable_eligible,
        default_enable_blockers=blockers,
        capabilities=capabilities,
        rationale=config.rationale,
    )


def _evaluation_fidelity(evaluation: Evaluation) -> int:
    raw = evaluation.metadata.get("fidelity", 1)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def _deterministic_rng(seed: int) -> random.Random:
    return random.Random(seed)


def _squared_distance(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    keys = set(left).union(right)
    return sum((float(left.get(key, 0.0)) - float(right.get(key, 0.0))) ** 2 for key in keys)
