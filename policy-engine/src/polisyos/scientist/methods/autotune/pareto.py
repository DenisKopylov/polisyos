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


type HypervolumeAlgorithm = Literal[
    "interval_union_1d.v1",
    "rectangle_union_2d.v1",
    "bounding_box_upper_bound.v1",
]


def _hypervolume_algorithm(dimensions: int) -> HypervolumeAlgorithm:
    if dimensions == 1:
        return "interval_union_1d.v1"
    if dimensions == 2:
        return "rectangle_union_2d.v1"
    return "bounding_box_upper_bound.v1"


class ParetoHypervolumeIndicator(BaseModel):
    """Describe the geometry of a measured volume over the supplied candidates.

    The coordinate IDs bind the metric, split, unit and direction. The
    bounding-box result is an upper bound on the exact union volume. Coverage
    of a candidate sequence says nothing about the completeness of the search
    space or the authority of any member.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    algorithm: HypervolumeAlgorithm
    value: float = Field(ge=0.0, allow_inf_nan=False)
    reference_source: Literal["declared", "observed_minimum"]
    coordinate_reference_point: dict[str, float] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_geometry(self) -> Self:
        if self.algorithm != _hypervolume_algorithm(len(self.coordinate_reference_point)):
            raise ValueError("hypervolume algorithm does not match its coordinate dimensions")
        if any(
            not key or not math.isfinite(value)
            for key, value in self.coordinate_reference_point.items()
        ):
            raise ValueError("hypervolume requires finite reference coordinates")
        return self

    def change_from(self, prior: ParetoHypervolumeIndicator) -> float:
        """Compare like indicators with the same declared reference and coordinate IDs."""
        self._validate_geometry()
        prior._validate_geometry()
        if self.reference_source != "declared" or prior.reference_source != "declared":
            raise ValueError("hypervolume comparison requires a declared reference")
        if (
            self.algorithm != prior.algorithm
            or self.coordinate_reference_point != prior.coordinate_reference_point
        ):
            raise ValueError("hypervolume reference or coordinate basis differs")
        return self.value - prior.value


class ParetoFront(BaseModel):
    """Result of Pareto front computation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "2.0"] = "1.0"
    members: list[ParetoMember] = Field(default_factory=list)
    hypervolume: float = 0.0
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
            or not math.isfinite(front.hypervolume)
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
    if not math.isfinite(front.hypervolume):
        raise ValueError("complete coordinate artifact has a non-finite hypervolume")

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
        coordinates = [_coordinate_for_policy(policy) for policy in policies]
        metric_counts: dict[str, int] = {}
        for coordinate in coordinates:
            metric_counts[coordinate.metric] = metric_counts.get(coordinate.metric, 0) + 1

        coordinate_ids = [coordinate.coordinate_id for coordinate in coordinates]
        if len(set(coordinate_ids)) != len(coordinate_ids):
            raise ValueError("PromotionPolicy coordinates must be unique")

        display_names: list[str] = []
        for coordinate in coordinates:
            if metric_counts[coordinate.metric] == 1 and coordinate.unit is None:
                display_names.append(coordinate.metric)
                continue
            label = [coordinate.metric, coordinate.split.value]
            if coordinate.unit is not None:
                label.append(f"unit={coordinate.unit}")
            label.append(f"direction={coordinate.direction.value}")
            display_names.append("::".join(label))

        self._coordinates = tuple(coordinates)
        self._coordinate_schema = ParetoCoordinateSchema(
            status="complete",
            coordinates=coordinates,
        )
        self._objective_names = tuple(coordinate_ids)
        # Fall back as a set: a metric can also be named like another axis's
        # canonical ID, so mixing display labels with replacement IDs can collide.
        self._display_objective_names = (
            tuple(display_names)
            if len(set(display_names)) == len(display_names)
            else self._objective_names
        )

    def _incomplete_front(self, assessment: ParetoInputAssessment) -> ParetoFront:
        """Return an empty result that retains the known coordinate contract."""
        return ParetoFront(
            schema_version="2.0",
            coordinate_schema=self._coordinate_schema.model_copy(
                update={"status": "incomplete"}, deep=True
            ),
            input_assessment=assessment,
        )

    def compute_front(
        self,
        evaluations: list[BenchmarkEvaluation],
        *,
        declared_reference_point: dict[str, float] | None = None,
    ) -> ParetoFront:
        """Evaluate the configured coordinates from their benchmark split maps."""
        return self._compute_front(evaluations, declared_reference_point=declared_reference_point)

    def _compute_front(
        self,
        evaluations: list[BenchmarkEvaluation],
        *,
        declared_reference_point: dict[str, float] | None = None,
        coordinate_values: list[dict[str, float]] | None = None,
    ) -> ParetoFront:
        """Compute Pareto geometry from benchmark maps or source-selected coordinates.

        An explicit reference is expressed in normalized coordinates. Values
        selected by a source owner are still raw measurements, so the same
        direction and omission logic applies to both input forms.
        """
        if coordinate_values is not None and len(coordinate_values) != len(evaluations):
            raise ValueError("Pareto coordinate rows must cover the exact evaluation sequence")
        if declared_reference_point is not None:
            self._validate_reference_point(declared_reference_point)
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
            vector, missing, non_finite = self._assess_objective_vector(
                evaluation,
                coordinate_values=(
                    coordinate_values[input_index] if coordinate_values is not None else None
                ),
            )
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
                evaluation=valid_evaluations[i].model_copy(deep=True),
            )
            for i in non_dominated_indices
        ]

        coordinate_ref_point = (
            self._reference_point(objective_vectors)
            if declared_reference_point is None
            else dict(declared_reference_point)
        )
        ref_point = {
            display_name: coordinate_ref_point[coordinate_id]
            for display_name, coordinate_id in zip(
                self._display_objective_names, self._objective_names, strict=True
            )
        }
        hv = self._compute_hypervolume(
            [objective_vectors[i] for i in non_dominated_indices],
            coordinate_ref_point,
        )

        return ParetoFront(
            members=members,
            hypervolume=hv,
            reference_point=ref_point,
            coordinate_schema=self._coordinate_schema.model_copy(deep=True),
            coordinate_reference_point=coordinate_ref_point,
            schema_version="2.0",
            input_assessment=assessment,
        )

    def compute_front_with_indicator(
        self,
        evaluations: list[BenchmarkEvaluation],
        *,
        declared_reference_point: dict[str, float] | None = None,
    ) -> tuple[ParetoFront, ParetoHypervolumeIndicator | None]:
        """Measure benchmark geometry only when every supplied candidate was assessed."""
        return self._compute_front_with_indicator(
            evaluations, declared_reference_point=declared_reference_point
        )

    def _compute_front_with_indicator(
        self,
        evaluations: list[BenchmarkEvaluation],
        *,
        declared_reference_point: dict[str, float] | None = None,
        coordinate_values: list[dict[str, float]] | None = None,
    ) -> tuple[ParetoFront, ParetoHypervolumeIndicator | None]:
        """Share the comparator with the companion owner of verified source rows."""
        front = self._compute_front(
            evaluations,
            declared_reference_point=declared_reference_point,
            coordinate_values=coordinate_values,
        )
        if front.input_assessment is None or front.input_assessment.status != "complete":
            return front, None
        return front, ParetoHypervolumeIndicator(
            algorithm=_hypervolume_algorithm(len(self._objective_names)),
            value=front.hypervolume,
            reference_source=(
                "observed_minimum" if declared_reference_point is None else "declared"
            ),
            coordinate_reference_point=dict(front.coordinate_reference_point),
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
        schema = front.coordinate_schema
        if schema is None or schema.status != "complete":
            raise ValueError("front coordinate schema does not establish comparison axes")
        _validate_coordinate_artifact(front)
        active_axes = {coordinate.coordinate_id: coordinate for coordinate in self._coordinates}
        supplied_axes = {coordinate.coordinate_id: coordinate for coordinate in schema.coordinates}
        if (
            schema.version != self._coordinate_schema.version
            or len(schema.coordinates) != len(active_axes)
            or supplied_axes != active_axes
        ):
            raise ValueError("front coordinate schema does not match the active comparison basis")

        cand_obj = self._vector_to_objectives(vector)
        for member in front.members:
            if self._dominates(member.coordinate_values, cand_obj):
                return True
        assessment = front.input_assessment
        if assessment is None or assessment.status != "complete":
            raise ValueError("front assessment does not establish non-dominance")
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
        *,
        coordinate_values: dict[str, float] | None = None,
    ) -> tuple[tuple[float, ...] | None, list[str], list[str]]:
        """Return finite coordinates plus exact missing/non-finite omissions."""
        if coordinate_values is not None and not coordinate_values.keys() <= set(
            self._objective_names
        ):
            raise ValueError("Pareto values name an undeclared coordinate")
        values: list[float] = []
        missing: list[str] = []
        non_finite: list[str] = []
        ordinary_splits = {BenchmarkSplit.SELECTION, BenchmarkSplit.HOLDOUT}
        method_job = any((ev.method_result_ref, ev.method_evidence_ref, ev.method_job_key))
        for coordinate in self._coordinates:
            if coordinate_values is not None:
                value = coordinate_values.get(coordinate.coordinate_id)
            else:
                split = coordinate.split
                # The shared holdout map does not establish what specialized split
                # produced it. Historical selection/holdout aggregates remain usable.
                needs_exact_split = (
                    method_job
                    or split not in ordinary_splits
                    or (
                        split is BenchmarkSplit.HOLDOUT
                        and ev.runtime_split_type is not None
                        and ev.runtime_split_type not in ordinary_splits
                    )
                )
                if (needs_exact_split and ev.runtime_split_type is not split) or (
                    method_job
                    and coordinate.unit is not None
                    and ev.metadata.get("metric_unit") != coordinate.unit
                ):
                    missing.append(coordinate.coordinate_id)
                    continue
                value = ev.primary_value(split=split, metric=coordinate.metric)
            if value is None:
                missing.append(coordinate.coordinate_id)
                continue
            if not math.isfinite(value):
                non_finite.append(coordinate.coordinate_id)
                continue
            # Normalize: higher is always better
            if coordinate.direction == MetricDirection.MINIMIZE:
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

    def _validate_reference_point(self, ref_point: dict[str, float]) -> None:
        if not ref_point:
            raise ValueError("hypervolume reference point is unavailable")
        if set(ref_point) != set(self._objective_names):
            raise ValueError("hypervolume reference keys do not match the objective schema")
        if any(not math.isfinite(value) for value in ref_point.values()):
            raise ValueError("hypervolume reference point contains a non-finite value")

    def _compute_hypervolume(
        self,
        front_objectives: list[tuple[float, ...]],
        ref_point: dict[str, float],
    ) -> float:
        """Compute hypervolume indicator (exact for 2D, approximate for higher)."""
        if not front_objectives:
            return 0.0
        self._validate_reference_point(ref_point)
        keys = self._objective_names
        if any(
            len(objective) != len(keys) or any(not math.isfinite(value) for value in objective)
            for objective in front_objectives
        ):
            raise ValueError("hypervolume objective contains malformed or non-finite values")
        if len(keys) == 1:
            hv = max(
                0.0,
                max(obj[0] for obj in front_objectives) - ref_point[keys[0]],
            )
        elif len(keys) == 2:
            hv = self._hypervolume_2d(front_objectives, ref_point)
        else:
            # Rough approximation for >2 objectives: product of ranges.
            hv = 1.0
            for index, key in enumerate(keys):
                best = max(obj[index] for obj in front_objectives)
                hv *= max(0.0, best - ref_point[key])
        if not math.isfinite(hv):
            raise ValueError("hypervolume result is non-finite")
        return max(0.0, hv)

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
