"""Multi-objective Pareto dominance utilities."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import BenchmarkEvaluation, BenchmarkSplit, MetricDirection, PromotionPolicy


class ParetoMember(BaseModel):
    """A member of a Pareto front."""

    model_config = ConfigDict(extra="forbid")

    candidate_ref_id: str
    objectives: dict[str, float]
    evaluation: BenchmarkEvaluation


class ParetoFront(BaseModel):
    """Result of Pareto front computation."""

    model_config = ConfigDict(extra="forbid")

    members: list[ParetoMember] = Field(default_factory=list)
    hypervolume: float = 0.0
    reference_point: dict[str, float] = Field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.members)


class ParetoPromoter:
    """Promotes candidates using Pareto dominance across multiple objectives."""

    def __init__(self, policies: list[PromotionPolicy]) -> None:
        if not policies:
            raise ValueError("At least one PromotionPolicy is required")
        self._policies = policies

    def compute_front(self, evaluations: list[BenchmarkEvaluation]) -> ParetoFront:
        """Compute the Pareto front from a set of evaluations."""
        if not evaluations:
            return ParetoFront()

        objectives_per_eval = self._extract_objectives(evaluations)
        non_dominated_indices = self._find_non_dominated(objectives_per_eval)

        members = [
            ParetoMember(
                candidate_ref_id=str(evaluations[i].candidate_ref.artifact_id),
                objectives=objectives_per_eval[i],
                evaluation=evaluations[i],
            )
            for i in non_dominated_indices
        ]

        ref_point = self._reference_point(objectives_per_eval)
        hv = self._compute_hypervolume(
            [objectives_per_eval[i] for i in non_dominated_indices],
            ref_point,
        )

        return ParetoFront(
            members=members,
            hypervolume=hv,
            reference_point=ref_point,
        )

    def is_dominated(
        self,
        candidate: BenchmarkEvaluation,
        front: ParetoFront,
    ) -> bool:
        """Check if candidate is dominated by any member of the front."""
        if not front.members:
            return False

        cand_obj = self._eval_objectives(candidate)
        for member in front.members:
            if self._dominates(member.objectives, cand_obj):
                return True
        return False

    def _extract_objectives(
        self, evaluations: list[BenchmarkEvaluation],
    ) -> list[dict[str, float]]:
        result: list[dict[str, float]] = []
        for ev in evaluations:
            result.append(self._eval_objectives(ev))
        return result

    def _eval_objectives(self, ev: BenchmarkEvaluation) -> dict[str, float]:
        obj: dict[str, float] = {}
        for policy in self._policies:
            value = ev.primary_value(split=policy.compare_split, metric=policy.primary_metric)
            if value is None:
                value = float("inf") if policy.direction == MetricDirection.MINIMIZE else float("-inf")
            # Normalize: higher is always better
            if policy.direction == MetricDirection.MINIMIZE:
                obj[policy.primary_metric] = -value
            else:
                obj[policy.primary_metric] = value
        return obj

    def _dominates(self, a: dict[str, float], b: dict[str, float]) -> bool:
        """Return True if a dominates b (all >= and at least one >)."""
        at_least_one_better = False
        for key in a:
            va = a.get(key, float("-inf"))
            vb = b.get(key, float("-inf"))
            if va < vb:
                return False
            if va > vb:
                at_least_one_better = True
        return at_least_one_better

    def _find_non_dominated(
        self, objectives: list[dict[str, float]],
    ) -> list[int]:
        n = len(objectives)
        dominated = [False] * n
        for i in range(n):
            if dominated[i]:
                continue
            for j in range(n):
                if i == j or dominated[j]:
                    continue
                if self._dominates(objectives[j], objectives[i]):
                    dominated[i] = True
                    break
        return [i for i in range(n) if not dominated[i]]

    def _reference_point(
        self, objectives: list[dict[str, float]],
    ) -> dict[str, float]:
        """Worst value per objective as reference point."""
        if not objectives:
            return {}
        ref: dict[str, float] = {}
        for key in objectives[0]:
            ref[key] = min(obj.get(key, float("inf")) for obj in objectives)
        return ref

    def _compute_hypervolume(
        self,
        front_objectives: list[dict[str, float]],
        ref_point: dict[str, float],
    ) -> float:
        """Compute hypervolume indicator (exact for 2D, approximate for higher)."""
        if not front_objectives or not ref_point:
            return 0.0

        keys = sorted(ref_point.keys())
        if len(keys) == 1:
            key = keys[0]
            return max(0.0, max(obj[key] for obj in front_objectives) - ref_point[key])

        if len(keys) == 2:
            return self._hypervolume_2d(front_objectives, ref_point, keys[0], keys[1])

        # Rough approximation for >2 objectives: product of ranges
        hv = 1.0
        for key in keys:
            best = max(obj.get(key, ref_point[key]) for obj in front_objectives)
            hv *= max(0.0, best - ref_point[key])
        return hv

    def _hypervolume_2d(
        self,
        points: list[dict[str, float]],
        ref: dict[str, float],
        k1: str,
        k2: str,
    ) -> float:
        """Exact 2D hypervolume via sweep line."""
        sorted_pts = sorted(points, key=lambda p: p[k1], reverse=True)
        hv = 0.0
        prev_k2 = ref[k2]
        for pt in sorted_pts:
            x = pt[k1] - ref[k1]
            y = pt[k2] - prev_k2
            if x > 0 and y > 0:
                hv += x * y
            prev_k2 = max(prev_k2, pt[k2])
        return max(0.0, hv)
