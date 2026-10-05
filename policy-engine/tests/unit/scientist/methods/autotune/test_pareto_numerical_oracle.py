"""Independent analytic oracles for the canonical Pareto runtime (B109–B111).

The finite lattice is a mathematical fixture, not production search history.
Expected dominance is computed directly from its definition, without calling
the production comparator or reproducing its skyline implementation.
"""

from __future__ import annotations

import itertools
import math

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    MetricDirection,
    PromotionPolicy,
)
from polisyos.scientist.methods.autotune.pareto import ParetoFront, ParetoPromoter


def _evaluation(index: int, values: tuple[float, ...]) -> BenchmarkEvaluation:
    return BenchmarkEvaluation(
        loop_id="numerical-oracle",
        suite_id="analytic-holdout",
        candidate_ref=ArtifactRef(
            artifact_id=f"sha256:{index + 1:064x}", kind="oracle", media_type="application/json"
        ),
        holdout_metrics={f"axis_{axis}": value for axis, value in enumerate(values)},
    )


def _policies(dim: int, direction: MetricDirection) -> list[PromotionPolicy]:
    return [
        PromotionPolicy(
            loop_id="numerical-oracle", primary_metric=f"axis_{axis}", direction=direction
        )
        for axis in range(dim)
    ]


def _expected_indices(points: list[tuple[float, ...]]) -> list[int]:
    return [
        index
        for index, point in enumerate(points)
        if not any(
            all(x >= y for x, y in zip(other, point, strict=True))
            and any(x > y for x, y in zip(other, point, strict=True))
            for other in points
        )
    ]


@pytest.mark.parametrize("dim", [1, 2, 3, 4])
def test_complete_finite_lattice_pairs_match_strict_dominance(dim: int) -> None:
    """Enumerate every ordered pair on {-1, 0, 1}^dim, including duplicates."""
    lattice = list(itertools.product((-1.0, 0.0, 1.0), repeat=dim))
    promoter = ParetoPromoter(_policies(dim, MetricDirection.MAXIMIZE))
    for left, right in itertools.product(lattice, repeat=2):
        points = [left, right]
        assert promoter._find_non_dominated(points) == _expected_indices(points), points


@pytest.mark.parametrize("direction", list(MetricDirection))
@pytest.mark.parametrize("dim", [1, 2, 3, 4])
def test_public_front_preserves_tied_candidate_ids_and_metric_direction(
    dim: int, direction: MetricDirection
) -> None:
    raw = [(2.0,) * dim, (1.0,) * dim, (2.0,) * dim, (0.0,) * dim]
    evaluations = [_evaluation(index, values) for index, values in enumerate(raw)]
    normalized = (
        raw
        if direction == MetricDirection.MAXIMIZE
        else [tuple(-value for value in point) for point in raw]
    )
    expected = {
        str(evaluations[index].candidate_ref.artifact_id) for index in _expected_indices(normalized)
    }
    promoter = ParetoPromoter(_policies(dim, direction))
    for inputs in (evaluations, list(reversed(evaluations))):
        front = ParetoFront.model_validate_json(promoter.compute_front(inputs).model_dump_json())
        assert {member.candidate_ref_id for member in front.members} == expected
        for evaluation in evaluations:
            assert promoter.is_dominated(evaluation, front) == (
                str(evaluation.candidate_ref.artifact_id) not in expected
            )


def test_split_unit_direction_coordinate_identity_survives_json_round_trip() -> None:
    """Same named metrics on different splits remain a true tradeoff."""
    policies = [
        PromotionPolicy(
            loop_id="numerical-oracle",
            primary_metric="score",
            compare_split=split,
            unit="ratio",
            direction=MetricDirection.MAXIMIZE,
        )
        for split in (BenchmarkSplit.SELECTION, BenchmarkSplit.HOLDOUT)
    ]
    a, b = [_evaluation(index, ()) for index in range(2)]
    a.selection_metrics = {"score": 10.0}
    a.holdout_metrics = {"score": 1.0}
    b.selection_metrics = {"score": 1.0}
    b.holdout_metrics = {"score": 10.0}
    promoter = ParetoPromoter(policies)
    front = ParetoFront.model_validate_json(promoter.compute_front([a, b]).model_dump_json())
    assert front.size == 2
    assert front.coordinate_schema is not None
    axes = front.coordinate_schema.coordinates
    assert len({axis.coordinate_id for axis in axes}) == 2
    assert {axis.split for axis in axes} == {BenchmarkSplit.SELECTION, BenchmarkSplit.HOLDOUT}
    assert all(axis.unit == "ratio" and axis.direction == MetricDirection.MAXIMIZE for axis in axes)
    assert len(front.coordinate_reference_point) == 2
    assert all(len(member.coordinate_values) == 2 for member in front.members)
    assert not promoter.is_dominated(a, front)
    assert not promoter.is_dominated(b, front)
    relabeled = front.model_copy(deep=True)
    for member in relabeled.members:
        member.objectives = {
            f"display_{index}": value for index, value in enumerate(member.objectives.values())
        }
    relabeled.reference_point = {
        f"display_{index}": value for index, value in enumerate(front.reference_point.values())
    }
    assert not promoter.is_dominated(a, relabeled)
    assert not promoter.is_dominated(b, relabeled)
    with pytest.raises(ValueError, match="unique"):
        ParetoPromoter([policies[0], policies[0]])


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf, None])
def test_invalid_metric_is_explicitly_unassessed_in_every_input_permutation(
    invalid: float | None,
) -> None:
    promoter = ParetoPromoter(_policies(2, MetricDirection.MAXIMIZE))
    good = _evaluation(0, (2.0, 1.0))
    bad = _evaluation(1, (1.0,))
    if invalid is not None:
        bad.holdout_metrics["axis_1"] = invalid
    dominated = _evaluation(2, (1.0, 1.0))
    for inputs in itertools.permutations([good, bad, dominated]):
        front = promoter.compute_front(list(inputs))
        assert [member.candidate_ref_id for member in front.members] == [
            str(good.candidate_ref.artifact_id)
        ]
        assert front.input_assessment.status == "partial"
        assert front.input_assessment.input_count == 3
        omissions = front.input_assessment.unassessed_evaluations
        assert len(omissions) == 1 and omissions[0].input_index == inputs.index(bad)
        assert omissions[0].candidate_ref_id == str(bad.candidate_ref.artifact_id)
        assert bool(omissions[0].missing_coordinate_ids) == (invalid is None)
        assert bool(omissions[0].non_finite_coordinate_ids) == (invalid is not None)
        assert math.isfinite(front.hypervolume)
        with pytest.raises(ValueError, match="unassessed"):
            promoter.is_dominated(bad, front)


def test_finite_extreme_values_do_not_crash_front_when_hypervolume_overflows() -> None:
    """Finite input admission is weaker than finite derived hypervolume (B111)."""
    promoter = ParetoPromoter(_policies(2, MetricDirection.MAXIMIZE))
    worst = _evaluation(0, (-1e308, -1e308))
    best = _evaluation(1, (1e308, 1e308))
    front = promoter.compute_front([worst, best])
    assert [member.candidate_ref_id for member in front.members] == [
        str(best.candidate_ref.artifact_id)
    ]
    assert front.coordinate_schema.status == "complete"
    assert front.input_assessment.status == "complete"
    assert front.input_assessment.input_count == front.input_assessment.assessed_count == 2
    assert front.input_assessment.unassessed_evaluations == ()
    assert set(front.members[0].coordinate_values.values()) == {1e308}
    assert all(math.isfinite(value) for value in front.coordinate_reference_point.values())
    # The mathematical volume exceeds binary64. Preserve the assessed front
    # while admitting a declared unavailable derived quantity, never fake zero.
    if front.hypervolume is None:
        assessment = front.model_dump(mode="json")["hypervolume_assessment"]
        assert assessment["status"] == "unavailable"
        assert assessment["predicate_basis"] == "not_established"
        assert assessment["reason"] == "non_finite_derived_hypervolume"
    else:
        assert math.isfinite(front.hypervolume) and front.hypervolume > 0.0
    restored = ParetoFront.model_validate_json(front.model_dump_json())
    assert restored == front
    assert promoter.is_dominated(worst, restored)
    assert not promoter.is_dominated(best, restored)


def test_dominance_removal_control_keeps_dto_but_breaks_mathematical_property(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A populated and valid artifact can still contain a dominated member."""
    promoter = ParetoPromoter(_policies(2, MetricDirection.MAXIMIZE))
    better, worse = _evaluation(0, (2.0, 1.0)), _evaluation(1, (1.0, 1.0))
    monkeypatch.setattr(promoter, "_find_non_dominated", lambda vectors: list(range(len(vectors))))
    front = promoter.compute_front([better, worse])
    assert front.coordinate_schema.status == "complete"
    assert front.input_assessment.status == "complete"
    with pytest.raises(AssertionError):
        assert {member.candidate_ref_id for member in front.members} == {
            str(better.candidate_ref.artifact_id)
        }
