"""Multi-objective Pareto dominance utilities."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .models import BenchmarkEvaluation, MetricDirection, PromotionPolicy


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
        self._objective_names = tuple(policy.primary_metric for policy in policies)

    def compute_front(self, evaluations: list[BenchmarkEvaluation]) -> ParetoFront:
        """Compute the Pareto front from a set of evaluations."""
        if not evaluations:
            return ParetoFront()

        objective_vectors = self._extract_objective_vectors(evaluations)
        non_dominated_indices = self._find_non_dominated(objective_vectors)

        members = [
            ParetoMember(
                candidate_ref_id=str(evaluations[i].candidate_ref.artifact_id),
                objectives=self._vector_to_objectives(objective_vectors[i]),
                evaluation=evaluations[i],
            )
            for i in non_dominated_indices
        ]

        ref_point = self._reference_point(objective_vectors)
        hv = self._compute_hypervolume(
            [objective_vectors[i] for i in non_dominated_indices],
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
        self,
        evaluations: list[BenchmarkEvaluation],
    ) -> list[dict[str, float]]:
        return [self._eval_objectives(ev) for ev in evaluations]

    def _eval_objectives(self, ev: BenchmarkEvaluation) -> dict[str, float]:
        return self._vector_to_objectives(self._eval_objective_vector(ev))

    def _extract_objective_vectors(
        self,
        evaluations: list[BenchmarkEvaluation],
    ) -> list[tuple[float, ...]]:
        return [self._eval_objective_vector(ev) for ev in evaluations]

    def _eval_objective_vector(self, ev: BenchmarkEvaluation) -> tuple[float, ...]:
        values: list[float] = []
        for policy in self._policies:
            value = ev.primary_value(split=policy.compare_split, metric=policy.primary_metric)
            if value is None:
                value = (
                    float("inf") if policy.direction == MetricDirection.MINIMIZE else float("-inf")
                )
            # Normalize: higher is always better
            if policy.direction == MetricDirection.MINIMIZE:
                values.append(-value)
            else:
                values.append(value)
        return tuple(values)

    def _vector_to_objectives(self, vector: tuple[float, ...]) -> dict[str, float]:
        return dict(zip(self._objective_names, vector, strict=True))

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
        self,
        objectives: list[tuple[float, ...]],
    ) -> list[int]:
        if not objectives:
            return []
        objective_count = len(objectives[0])
        if objective_count == 1:
            best_value = max(item[0] for item in objectives)
            return [index for index, point in enumerate(objectives) if point[0] == best_value]
        if objective_count == 2:
            return self._find_non_dominated_2d(objectives)
        if objective_count == 3:
            return self._find_non_dominated_3d(objectives)

        n = len(objectives)
        dominated = [False] * n
        for i in range(n):
            if dominated[i]:
                continue
            for j in range(n):
                if i == j or dominated[j]:
                    continue
                if self._dominates_vector(objectives[j], objectives[i]):
                    dominated[i] = True
                    break
        return [i for i in range(n) if not dominated[i]]

    def _find_non_dominated_2d(
        self,
        objectives: list[tuple[float, ...]],
    ) -> list[int]:
        ranked = sorted(
            range(len(objectives)),
            key=lambda index: (
                objectives[index][0],
                objectives[index][1],
            ),
            reverse=True,
        )
        front: list[int] = []
        max_second_from_previous_groups = float("-inf")
        cursor = 0
        while cursor < len(ranked):
            first_value = objectives[ranked[cursor]][0]
            group: list[int] = []
            while cursor < len(ranked) and objectives[ranked[cursor]][0] == first_value:
                group.append(ranked[cursor])
                cursor += 1

            group_max_second = max(objectives[index][1] for index in group)
            for index in group:
                second_value = objectives[index][1]
                if second_value < max_second_from_previous_groups:
                    continue
                if second_value == group_max_second:
                    front.append(index)
            max_second_from_previous_groups = max(
                max_second_from_previous_groups,
                group_max_second,
            )
        return sorted(front)

    def _find_non_dominated_3d(
        self,
        objectives: list[tuple[float, ...]],
    ) -> list[int]:
        ranked = sorted(
            range(len(objectives)),
            key=lambda index: (
                objectives[index][0],
                objectives[index][1],
                objectives[index][2],
            ),
            reverse=True,
        )
        skyline: list[tuple[float, float]] = []
        front: list[int] = []
        cursor = 0
        while cursor < len(ranked):
            first_value = objectives[ranked[cursor]][0]
            group: list[int] = []
            while cursor < len(ranked) and objectives[ranked[cursor]][0] == first_value:
                group.append(ranked[cursor])
                cursor += 1

            local_front = self._find_non_dominated_2d(
                [(objectives[index][1], objectives[index][2]) for index in group],
            )

            selected_group_indices = [group[index] for index in local_front]
            for index in selected_group_indices:
                if not self._is_dominated_2d(
                    skyline,
                    point=(objectives[index][1], objectives[index][2]),
                ):
                    front.append(index)

            skyline = self._merge_2d_skyline(
                skyline,
                [(objectives[index][1], objectives[index][2]) for index in selected_group_indices],
            )

        return sorted(front)

    def _merge_2d_skyline(
        self,
        skyline: list[tuple[float, float]],
        candidates: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        merged = list(skyline)
        for candidate in candidates:
            if self._is_dominated_2d(merged, point=candidate):
                continue
            merged = [point for point in merged if not self._dominates_vector(candidate, point)]
            merged.append(candidate)
        merged.sort(key=lambda point: (point[0], point[1]), reverse=True)
        reduced: list[tuple[float, float]] = []
        best_second = float("-inf")
        for point in merged:
            if point[1] <= best_second:
                continue
            reduced.append(point)
            best_second = point[1]
        return reduced

    def _is_dominated_2d(
        self,
        skyline: list[tuple[float, float]],
        *,
        point: tuple[float, float],
    ) -> bool:
        for skyline_point in skyline:
            if skyline_point[0] < point[0]:
                break
            if skyline_point[1] >= point[1]:
                return True
        return False

    def _dominates_vector(
        self,
        left: tuple[float, ...],
        right: tuple[float, ...],
    ) -> bool:
        at_least_one_better = False
        for left_value, right_value in zip(left, right, strict=True):
            if left_value < right_value:
                return False
            if left_value > right_value:
                at_least_one_better = True
        return at_least_one_better

    def _reference_point(
        self,
        objectives: list[tuple[float, ...]],
    ) -> dict[str, float]:
        """Worst value per objective as reference point."""
        if not objectives:
            return {}
        return {
            metric_name: min(vector[index] for vector in objectives)
            for index, metric_name in enumerate(self._objective_names)
        }

    def _compute_hypervolume(
        self,
        front_objectives: list[tuple[float, ...]],
        ref_point: dict[str, float],
    ) -> float:
        """Compute hypervolume indicator (exact for 2D, approximate for higher)."""
        if not front_objectives or not ref_point:
            return 0.0

        keys = self._objective_names
        if len(keys) == 1:
            return max(0.0, max(obj[0] for obj in front_objectives) - ref_point[keys[0]])

        if len(keys) == 2:
            return self._hypervolume_2d(front_objectives, ref_point)

        # Rough approximation for >2 objectives: product of ranges
        hv = 1.0
        for index, key in enumerate(keys):
            best = max(obj[index] for obj in front_objectives)
            hv *= max(0.0, best - ref_point[key])
        return hv

    def _hypervolume_2d(
        self,
        points: list[tuple[float, ...]],
        ref: dict[str, float],
    ) -> float:
        """Exact 2D hypervolume via sweep line."""
        first_name, second_name = self._objective_names[:2]
        sorted_pts = sorted(points, key=lambda point: point[0], reverse=True)
        hv = 0.0
        prev_k2 = ref[second_name]
        for pt in sorted_pts:
            x = pt[0] - ref[first_name]
            y = pt[1] - prev_k2
            if x > 0 and y > 0:
                hv += x * y
            prev_k2 = max(prev_k2, pt[1])
        return max(0.0, hv)
