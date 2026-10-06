"""Multi-objective Pareto dominance utilities."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    MetricDirection,
    PromotionPolicy,
)


def _canonical_coordinate_id(
    *,
    metric: str,
    split: BenchmarkSplit,
    unit_state: Literal["absent", "present"],
    unit: str | None,
    direction: MetricDirection,
) -> str:
    """Return the content-bound id for one typed coordinate tuple."""
    identity = {
        "direction": direction.value,
        "metric": metric,
        "split": split.value,
        "unit": unit,
        "unit_state": unit_state,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "pareto-coordinate.v1:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ParetoCoordinate(BaseModel):
    """Typed identity for one normalized Pareto coordinate."""

    model_config = ConfigDict(extra="forbid")

    coordinate_id: str
    metric: str = Field(..., min_length=1, max_length=128)
    split: BenchmarkSplit
    unit_state: Literal["absent", "present"]
    unit: str | None = Field(default=None, min_length=1, max_length=64)
    direction: MetricDirection

    @model_validator(mode="after")
    def _validate_content_bound_identity(self) -> Self:
        """Reject ids or unit states that do not describe this typed tuple."""
        if (self.unit_state == "present") != (self.unit is not None):
            raise ValueError("coordinate unit_state does not match unit")
        expected_id = _canonical_coordinate_id(
            metric=self.metric,
            split=self.split,
            unit_state=self.unit_state,
            unit=self.unit,
            direction=self.direction,
        )
        if self.coordinate_id != expected_id:
            raise ValueError("coordinate_id is not bound to its typed coordinate")
        return self


class ParetoCoordinateSchema(BaseModel):
    """Versioned schema shared by Pareto values and reference points."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["pareto-coordinate.v1"] = "pareto-coordinate.v1"
    status: Literal["complete", "incomplete", "legacy_limited"]
    coordinates: list[ParetoCoordinate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_coordinates(self) -> Self:
        """Reject duplicate content identities in one coordinate artifact."""
        coordinate_ids = [coordinate.coordinate_id for coordinate in self.coordinates]
        if len(set(coordinate_ids)) != len(coordinate_ids):
            raise ValueError("coordinate schema contains duplicate coordinate ids")
        return self


class ParetoMember(BaseModel):
    """A member of a Pareto front."""

    model_config = ConfigDict(extra="forbid")

    candidate_ref_id: str
    objectives: dict[str, float]
    coordinate_values: dict[str, float] = Field(default_factory=dict)
    evaluation: BenchmarkEvaluation


class ParetoUnassessedEvaluation(BaseModel):
    """Identify an admitted evaluation that lacks one or more required axes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_index: int = Field(ge=0)
    candidate_ref_id: str = Field(min_length=1)
    missing_coordinate_ids: list[str] = Field(default_factory=list)
    non_finite_coordinate_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_omission_reason(self) -> Self:
        """Keep omission records tied to a concrete missing or invalid coordinate."""
        if not self.missing_coordinate_ids and not self.non_finite_coordinate_ids:
            raise ValueError("unassessed evaluation requires an omission reason")
        if set(self.missing_coordinate_ids) & set(self.non_finite_coordinate_ids):
            raise ValueError("a coordinate cannot be both missing and non-finite")
        return self


class ParetoInputAssessment(BaseModel):
    """Describe objective coverage over the exact evaluation input sequence.

    ``complete`` means that every supplied evaluation had every required
    coordinate. It does not claim that the supplied sequence exhausts the
    candidate universe.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["complete", "partial", "no_usable_inputs"]
    input_count: int = Field(ge=0)
    assessed_count: int = Field(ge=0)
    unassessed_evaluations: tuple[ParetoUnassessedEvaluation, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_coverage_counts(self) -> Self:
        """Require every supplied row to be assessed or explicitly omitted."""
        if self.assessed_count + len(self.unassessed_evaluations) != self.input_count:
            raise ValueError("input assessment counts do not cover the supplied evaluations")
        omission_indices = [item.input_index for item in self.unassessed_evaluations]
        if len(set(omission_indices)) != len(omission_indices):
            raise ValueError("omission input_index must be unique within an assessment")
        if any(index >= self.input_count for index in omission_indices):
            raise ValueError("omission input_index is outside the declared input_count")
        if self.status == "complete" and (self.input_count == 0 or self.unassessed_evaluations):
            raise ValueError("complete input assessment requires nonempty fully assessed inputs")
        if self.status == "partial" and (
            self.assessed_count == 0 or not self.unassessed_evaluations
        ):
            raise ValueError("partial input assessment requires assessed and omitted inputs")
        if self.status == "no_usable_inputs" and self.assessed_count != 0:
            raise ValueError("no_usable_inputs cannot contain assessed evaluations")
        return self


class HypervolumeAssessment(BaseModel):
    """Representability of the existing indicator, separate from front membership."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["hypervolume-assessment.v1"] = "hypervolume-assessment.v1"
    status: Literal["available", "unavailable"]
    basis: Literal["recomputed", "not_established"]
    reason: Literal["non_finite_derived_hypervolume", "catalog_union_not_recomputed"] | None = None

    @model_validator(mode="after")
    def _validate_status(self) -> Self:
        if self.status == "available" and (self.basis != "recomputed" or self.reason is not None):
            raise ValueError("Available hypervolume requires a recomputed indicator")
        if self.status == "unavailable" and (
            self.basis != "not_established" or self.reason is None
        ):
            raise ValueError("Unavailable hypervolume requires its declared limitation")
        return self


def validate_hypervolume(value: float | None, assessment: HypervolumeAssessment | None) -> None:
    if assessment is not None and assessment.status == "unavailable":
        if value is not None:
            raise ValueError("Unavailable hypervolume must be null")
    elif value is None or not math.isfinite(value):
        raise ValueError("Hypervolume must be finite or explicitly unavailable")


class ParetoFront(BaseModel):
    """Result of Pareto front computation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "2.0"] = "1.0"
    members: list[ParetoMember] = Field(default_factory=list)
    hypervolume: float | None = 0.0
    hypervolume_assessment: HypervolumeAssessment | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    reference_point: dict[str, float] = Field(default_factory=dict)
    coordinate_schema: ParetoCoordinateSchema | None = Field(
        default_factory=lambda: ParetoCoordinateSchema(status="legacy_limited")
    )
    coordinate_reference_point: dict[str, float] = Field(default_factory=dict)
    input_assessment: ParetoInputAssessment | None = None

    @model_validator(mode="after")
    def _validate_coordinate_artifact(self) -> Self:
        """Admit only complete, content-bound v1 coordinate artifacts."""
        if self.schema_version == "2.0" and self.input_assessment is None:
            raise ValueError("v2 Pareto front requires input assessment")
        if self.schema_version == "1.0" and self.input_assessment is not None:
            raise ValueError("v1 Pareto front cannot carry v2 input assessment")
        if self.schema_version == "1.0" and self.hypervolume_assessment is not None:
            raise ValueError("v1 Pareto front cannot carry the typed indicator assessment")
        validate_hypervolume(self.hypervolume, self.hypervolume_assessment)
        _validate_coordinate_artifact(self)
        return self

    def historical_v1_payload(self) -> dict[str, object]:
        """Serialize the historical front projection without v2 assessment fields."""
        if self.schema_version != "1.0":
            raise ValueError("historical v1 serialization requires a v1 Pareto front")
        payload = self.model_dump(
            mode="json",
            include={
                "members",
                "hypervolume",
                "reference_point",
                "coordinate_schema",
                "coordinate_reference_point",
            },
        )
        return payload

    @property
    def size(self) -> int:
        return len(self.members)


def _validate_coordinate_artifact(front: ParetoFront) -> None:
    """Validate the shared schema, values, and reference-point key sets."""
    schema = front.coordinate_schema
    if schema is None or schema.status == "legacy_limited":
        return
    if schema.status == "incomplete":
        if (
            front.members
            or front.reference_point
            or front.coordinate_reference_point
            or front.hypervolume != 0.0
        ):
            raise ValueError("incomplete coordinate schema cannot carry v1 values")
        return

    coordinate_ids = {coordinate.coordinate_id for coordinate in schema.coordinates}
    if not coordinate_ids or not front.members:
        raise ValueError("complete coordinate schema requires members and coordinates")
    if set(front.coordinate_reference_point) != coordinate_ids:
        raise ValueError("coordinate reference keys do not match the coordinate schema")
    if any(not math.isfinite(value) for value in front.coordinate_reference_point.values()):
        raise ValueError("coordinate reference point contains a non-finite value")

    display_keys: set[str] | None = None
    for member in front.members:
        if set(member.coordinate_values) != coordinate_ids:
            raise ValueError("member coordinate keys do not match the coordinate schema")
        if any(not math.isfinite(value) for value in member.coordinate_values.values()):
            raise ValueError("member coordinate values contain a non-finite value")
        current_display_keys = set(member.objectives)
        if not current_display_keys:
            raise ValueError("complete coordinate artifact requires display objectives")
        if display_keys is None:
            display_keys = current_display_keys
        elif current_display_keys != display_keys:
            raise ValueError("member display keys are not consistent")
        if any(not math.isfinite(value) for value in member.objectives.values()):
            raise ValueError("member display objectives contain a non-finite value")

    if display_keys is None or set(front.reference_point) != display_keys:
        raise ValueError("display reference keys do not match member objectives")
    if any(not math.isfinite(value) for value in front.reference_point.values()):
        raise ValueError("display reference point contains a non-finite value")


def _coordinate_for_policy(policy: PromotionPolicy) -> ParetoCoordinate:
    """Build a collision-safe coordinate identity from all policy dimensions."""
    unit_state = "present" if policy.unit is not None else "absent"
    coordinate_id = _canonical_coordinate_id(
        metric=policy.primary_metric,
        split=policy.compare_split,
        unit_state=unit_state,
        unit=policy.unit,
        direction=policy.direction,
    )
    return ParetoCoordinate(
        coordinate_id=coordinate_id,
        metric=policy.primary_metric,
        split=policy.compare_split,
        unit_state=unit_state,
        unit=policy.unit,
        direction=policy.direction,
    )


class ParetoPromoter:
    """Promotes candidates using Pareto dominance across multiple objectives."""

    def __init__(self, policies: list[PromotionPolicy]) -> None:
        if not policies:
            raise ValueError("At least one PromotionPolicy is required")
        self._policies = list(policies)
        metric_counts: dict[str, int] = {}
        for policy in self._policies:
            metric_counts[policy.primary_metric] = metric_counts.get(policy.primary_metric, 0) + 1

        coordinates = [_coordinate_for_policy(policy) for policy in self._policies]
        coordinate_ids = [coordinate.coordinate_id for coordinate in coordinates]
        if len(set(coordinate_ids)) != len(coordinate_ids):
            raise ValueError("PromotionPolicy coordinates must be unique")

        display_names: list[str] = []
        for policy in self._policies:
            if metric_counts[policy.primary_metric] == 1 and policy.unit is None:
                display_names.append(policy.primary_metric)
                continue
            coordinate = [policy.primary_metric, policy.compare_split.value]
            if policy.unit is not None:
                coordinate.append(f"unit={policy.unit}")
            coordinate.append(f"direction={policy.direction.value}")
            display_names.append("::".join(coordinate))

        self._coordinates = tuple(coordinates)
        self._coordinate_schema = ParetoCoordinateSchema(
            status="complete",
            coordinates=coordinates,
        )
        self._objective_names = tuple(coordinate_ids)
        self._display_objective_names = tuple(display_names)

    def _incomplete_front(self, assessment: ParetoInputAssessment) -> ParetoFront:
        """Return an empty result that retains the known coordinate contract."""
        return ParetoFront(
            schema_version="2.0",
            coordinate_schema=ParetoCoordinateSchema(
                status="incomplete",
                coordinates=list(self._coordinates),
            ),
            input_assessment=assessment,
        )

    def compute_front(self, evaluations: list[BenchmarkEvaluation]) -> ParetoFront:
        """Compute the Pareto front from a set of evaluations."""
        if not evaluations:
            return self._incomplete_front(
                ParetoInputAssessment(
                    status="no_usable_inputs",
                    input_count=0,
                    assessed_count=0,
                )
            )

        valid_evaluations: list[BenchmarkEvaluation] = []
        objective_vectors: list[tuple[float, ...]] = []
        unassessed: list[ParetoUnassessedEvaluation] = []
        for input_index, evaluation in enumerate(evaluations):
            vector, missing, non_finite = self._assess_objective_vector(evaluation)
            if vector is None:
                unassessed.append(
                    ParetoUnassessedEvaluation(
                        input_index=input_index,
                        candidate_ref_id=str(evaluation.candidate_ref.artifact_id),
                        missing_coordinate_ids=missing,
                        non_finite_coordinate_ids=non_finite,
                    )
                )
                continue
            valid_evaluations.append(evaluation)
            objective_vectors.append(vector)
        assessment = ParetoInputAssessment(
            status=(
                "no_usable_inputs"
                if not objective_vectors
                else "partial"
                if unassessed
                else "complete"
            ),
            input_count=len(evaluations),
            assessed_count=len(objective_vectors),
            unassessed_evaluations=unassessed,
        )
        if not objective_vectors:
            return self._incomplete_front(assessment)
        non_dominated_indices = self._find_non_dominated(objective_vectors)

        members = [
            ParetoMember(
                candidate_ref_id=str(valid_evaluations[i].candidate_ref.artifact_id),
                objectives=self._vector_to_display_objectives(objective_vectors[i]),
                coordinate_values=self._vector_to_objectives(objective_vectors[i]),
                evaluation=valid_evaluations[i],
            )
            for i in non_dominated_indices
        ]

        coordinate_ref_point = self._reference_point(objective_vectors)
        ref_point = self._display_reference_point(objective_vectors)
        hv = self._compute_hypervolume(
            [objective_vectors[i] for i in non_dominated_indices],
            coordinate_ref_point,
        )
        hv_assessment = None
        if not math.isfinite(hv):
            hv = None
            hv_assessment = HypervolumeAssessment(
                status="unavailable",
                basis="not_established",
                reason="non_finite_derived_hypervolume",
            )

        return ParetoFront(
            members=members,
            hypervolume=hv,
            hypervolume_assessment=hv_assessment,
            reference_point=ref_point,
            coordinate_schema=self._coordinate_schema,
            coordinate_reference_point=coordinate_ref_point,
            schema_version="2.0",
            input_assessment=assessment,
        )

    def is_dominated(
        self,
        candidate: BenchmarkEvaluation,
        front: ParetoFront,
    ) -> bool:
        """Check if candidate is dominated by any member of the front."""
        vector, missing, non_finite = self._assess_objective_vector(candidate)
        if vector is None:
            reason = "missing" if missing else "non-finite"
            raise ValueError(f"candidate is unassessed: {reason} required Pareto coordinate")
        if not front.members:
            return False
        schema = front.coordinate_schema
        if schema is None or schema.status != "complete":
            raise ValueError("v1 dominance requires a complete coordinate schema")
        _validate_coordinate_artifact(front)

        cand_obj = self._vector_to_objectives(vector)
        for member in front.members:
            if self._dominates(member.coordinate_values, cand_obj):
                return True
        return False

    def _extract_objectives(
        self,
        evaluations: list[BenchmarkEvaluation],
    ) -> list[dict[str, float]]:
        return [
            objectives
            for evaluation in evaluations
            if (objectives := self._eval_objectives(evaluation)) is not None
        ]

    def _eval_objectives(self, ev: BenchmarkEvaluation) -> dict[str, float] | None:
        vector = self._eval_objective_vector(ev)
        if vector is None:
            return None
        return self._vector_to_objectives(vector)

    def _extract_objective_vectors(
        self,
        evaluations: list[BenchmarkEvaluation],
    ) -> list[tuple[float, ...]]:
        return [
            vector
            for evaluation in evaluations
            if (vector := self._eval_objective_vector(evaluation)) is not None
        ]

    def _eval_objective_vector(self, ev: BenchmarkEvaluation) -> tuple[float, ...] | None:
        vector, _, _ = self._assess_objective_vector(ev)
        return vector

    def _assess_objective_vector(
        self,
        ev: BenchmarkEvaluation,
    ) -> tuple[tuple[float, ...] | None, list[str], list[str]]:
        """Return finite coordinates plus exact missing/non-finite omissions."""
        values: list[float] = []
        missing: list[str] = []
        non_finite: list[str] = []
        for policy, coordinate in zip(self._policies, self._coordinates, strict=True):
            value = ev.primary_value(split=policy.compare_split, metric=policy.primary_metric)
            if value is None:
                missing.append(coordinate.coordinate_id)
                continue
            if not math.isfinite(value):
                non_finite.append(coordinate.coordinate_id)
                continue
            # Normalize: higher is always better
            if policy.direction == MetricDirection.MINIMIZE:
                value = -value
            if not math.isfinite(value):
                non_finite.append(coordinate.coordinate_id)
                continue
            values.append(value)
        if missing or non_finite:
            return None, missing, non_finite
        return tuple(values), missing, non_finite

    def _vector_to_objectives(self, vector: tuple[float, ...]) -> dict[str, float]:
        return dict(zip(self._objective_names, vector, strict=True))

    def _vector_to_display_objectives(self, vector: tuple[float, ...]) -> dict[str, float]:
        """Return the legacy display projection for backwards-compatible readers."""
        return dict(zip(self._display_objective_names, vector, strict=True))

    def _dominates(self, a: dict[str, float], b: dict[str, float]) -> bool:
        """Return True if a dominates b (all >= and at least one >)."""
        if a.keys() != b.keys() or any(
            not math.isfinite(value) for value in (*a.values(), *b.values())
        ):
            return False
        at_least_one_better = False
        for key in a:
            va = a[key]
            vb = b[key]
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
        max_second_from_previous_groups: float | None = None
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
                if (
                    max_second_from_previous_groups is not None
                    and second_value <= max_second_from_previous_groups
                ):
                    continue
                if second_value == group_max_second:
                    front.append(index)
            if (
                max_second_from_previous_groups is None
                or group_max_second > max_second_from_previous_groups
            ):
                max_second_from_previous_groups = group_max_second
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
        if any(not math.isfinite(value) for vector in objectives for value in vector):
            return {}
        return {
            metric_name: min(vector[index] for vector in objectives)
            for index, metric_name in enumerate(self._objective_names)
        }

    def _display_reference_point(
        self,
        objectives: list[tuple[float, ...]],
    ) -> dict[str, float]:
        """Return the legacy display projection of the reference point."""
        if not objectives:
            return {}
        return {
            display_name: min(vector[index] for vector in objectives)
            for index, display_name in enumerate(self._display_objective_names)
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
        if set(ref_point) != set(keys):
            return 0.0
        if any(not math.isfinite(value) for value in ref_point.values()):
            return 0.0
        if any(
            len(objective) != len(keys) or any(not math.isfinite(value) for value in objective)
            for objective in front_objectives
        ):
            return 0.0
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
