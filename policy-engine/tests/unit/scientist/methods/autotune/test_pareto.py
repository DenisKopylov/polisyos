"""Tests for Pareto front computation and promotion."""

from __future__ import annotations

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

_COUNTER = 0


def _ref() -> ArtifactRef:
    global _COUNTER
    _COUNTER += 1
    return ArtifactRef(
        artifact_id=f"sha256:{_COUNTER:064x}",
        kind="test",
        media_type="application/json",
    )


def _eval(loop_id: str = "loop1", **metrics: float) -> BenchmarkEvaluation:
    return BenchmarkEvaluation(
        loop_id=loop_id,
        suite_id="suite1",
        candidate_ref=_ref(),
        holdout_metrics=metrics,
        promotable=True,
    )


def _policies(*metric_names: str) -> list[PromotionPolicy]:
    return [
        PromotionPolicy(loop_id="loop1", primary_metric=m, direction=MetricDirection.MAXIMIZE)
        for m in metric_names
    ]


def _slow_non_dominated_points(points: list[tuple[float, ...]]) -> list[int]:
    """Return a front with an intentionally simple quadratic oracle."""
    result: list[int] = []
    for index, point in enumerate(points):
        dominated = False
        for other_index, other in enumerate(points):
            if index == other_index:
                continue
            no_worse = all(left >= right for left, right in zip(other, point, strict=True))
            strictly_better = any(left > right for left, right in zip(other, point, strict=True))
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            result.append(index)
    return result


class TestParetoFront:
    def test_two_objective_front(self):
        promoter = ParetoPromoter(_policies("acc", "speed"))
        evals = [
            _eval(acc=0.9, speed=0.3),  # front
            _eval(acc=0.7, speed=0.8),  # front
            _eval(acc=0.5, speed=0.4),  # dominated
        ]
        front = promoter.compute_front(evals)
        assert front.size == 2
        assert front.hypervolume > 0

    def test_dominated_candidate(self):
        promoter = ParetoPromoter(_policies("acc", "speed"))
        evals = [
            _eval(acc=0.9, speed=0.8),
        ]
        front = promoter.compute_front(evals)
        dominated = _eval(acc=0.5, speed=0.4)
        assert promoter.is_dominated(dominated, front) is True

    def test_two_dimensional_fast_front_removes_equal_secondary_value_from_later_group(self):
        """A strictly better first coordinate plus equal second still dominates."""
        # Catches the production mutation from <= to < in the accelerated
        # 2D sweep, which keeps (1, 1) beside its dominator (2, 1).
        promoter = ParetoPromoter(_policies("acc", "speed"))
        better = _eval(acc=2.0, speed=1.0)
        dominated = _eval(acc=1.0, speed=1.0)

        front = promoter.compute_front([better, dominated])

        assert [member.candidate_ref_id for member in front.members] == [
            str(better.candidate_ref.artifact_id)
        ]

    def test_three_dimensional_fast_front_removes_equal_secondary_value_from_later_group(self):
        """The 3D path must inherit strict dominance from its 2D local sweep."""
        # Catches the production mutation that leaves a later 3D group alive
        # when its local secondary coordinate ties an earlier group.
        promoter = ParetoPromoter(_policies("acc", "speed", "fairness"))
        better = _eval(acc=2.0, speed=1.0, fairness=1.0)
        dominated = _eval(acc=1.0, speed=1.0, fairness=1.0)

        front = promoter.compute_front([better, dominated])

        assert [member.candidate_ref_id for member in front.members] == [
            str(better.candidate_ref.artifact_id)
        ]

    def test_empty_evaluations(self):
        promoter = ParetoPromoter(_policies("acc"))
        front = promoter.compute_front([])
        assert front.size == 0
        assert front.hypervolume == 0.0

    def test_single_objective(self):
        promoter = ParetoPromoter(_policies("score"))
        evals = [
            _eval(score=0.9),
            _eval(score=0.7),
            _eval(score=0.5),
        ]
        front = promoter.compute_front(evals)
        assert front.size == 1
        assert front.members[0].objectives["score"] == 0.9

    def test_non_dominated_on_empty_front(self):
        promoter = ParetoPromoter(_policies("acc"))
        front = ParetoFront()
        candidate = _eval(acc=0.5)
        assert promoter.is_dominated(candidate, front) is False

    def test_requires_at_least_one_policy(self):
        with pytest.raises(ValueError, match="(?i)at least one"):
            ParetoPromoter([])

    def test_two_objective_front_preserves_duplicate_ties(self):
        promoter = ParetoPromoter(_policies("acc", "speed"))
        evals = [
            _eval(acc=0.8, speed=0.7),
            _eval(acc=0.8, speed=0.7),
            _eval(acc=0.7, speed=0.6),
        ]

        front = promoter.compute_front(evals)

        assert front.size == 2
        assert [member.objectives for member in front.members] == [
            {"acc": 0.8, "speed": 0.7},
            {"acc": 0.8, "speed": 0.7},
        ]
        assert [member.candidate_ref_id for member in front.members] == [
            str(evals[0].candidate_ref.artifact_id),
            str(evals[1].candidate_ref.artifact_id),
        ]

    def test_coordinate_identity_keeps_split_unit_and_direction(self):
        """Same metric names on different axes remain separate coordinates."""
        # Catches the production mutation that serializes only primary_metric,
        # collapsing split/unit/direction coordinates into one dict key.
        policies = [
            PromotionPolicy(
                loop_id="loop1",
                primary_metric="score",
                direction=MetricDirection.MAXIMIZE,
                compare_split=BenchmarkSplit.SELECTION,
                unit="percent",
            ),
            PromotionPolicy(
                loop_id="loop1",
                primary_metric="score",
                direction=MetricDirection.MINIMIZE,
                compare_split=BenchmarkSplit.HOLDOUT,
                unit="percent",
            ),
        ]
        promoter = ParetoPromoter(policies)
        first = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=_ref(),
            selection_metrics={"score": 10.0},
            holdout_metrics={"score": 1.0},
            promotable=True,
        )
        second = BenchmarkEvaluation(
            loop_id="loop1",
            suite_id="suite1",
            candidate_ref=_ref(),
            selection_metrics={"score": 1.0},
            holdout_metrics={"score": 10.0},
            promotable=True,
        )

        front = promoter.compute_front([first, second])
        keys = set(front.members[0].objectives)

        assert front.size == 2
        assert len(keys) == 2
        assert any("selection" in key and "percent" in key for key in keys)
        assert any("holdout" in key and "percent" in key for key in keys)
        assert set(front.reference_point) == keys
        assert promoter.is_dominated(first, front) is False
        assert promoter.is_dominated(second, front) is False

    def test_non_finite_and_missing_metrics_are_excluded_from_numeric_front(self):
        """Unusable metrics cannot become infinite best/worst Pareto values."""
        # Catches the production mutation that maps missing/non-finite values
        # to +/-infinity and lets them affect dominance or hypervolume.
        promoter = ParetoPromoter(_policies("acc", "speed"))
        valid = _eval(acc=0.9, speed=0.8)
        invalid_nan = _eval(acc=math.nan, speed=0.9)
        invalid_inf = _eval(acc=math.inf, speed=0.7)
        invalid_missing = _eval(acc=0.7)

        front = promoter.compute_front([valid, invalid_nan, invalid_inf, invalid_missing])

        assert [member.candidate_ref_id for member in front.members] == [
            str(valid.candidate_ref.artifact_id)
        ]
        assert all(math.isfinite(value) for member in front.members for value in member.objectives.values())
        assert all(math.isfinite(value) for value in front.reference_point.values())
        assert math.isfinite(front.hypervolume)

    def test_invalid_reference_point_does_not_emit_non_finite_hypervolume(self):
        """Hypervolume refuses an invalid reference point instead of propagating it."""
        # Catches the production mutation that multiplies a finite front by an
        # infinite reference range and returns inf to downstream consumers.
        promoter = ParetoPromoter(_policies("acc", "speed"))

        hypervolume = promoter._compute_hypervolume(
            [(1.0, 1.0)],
            {"acc": float("-inf"), "speed": 0.0},
        )

        assert hypervolume == 0.0

    @pytest.mark.parametrize(
        ("metric_names", "points"),
        [
            (
                ("first", "second"),
                [(2.0, 1.0), (1.0, 1.0), (1.0, 2.0), (2.0, 0.0), (2.0, 1.0)],
            ),
            (
                ("first", "second", "third"),
                [
                    (2.0, 1.0, 1.0),
                    (1.0, 1.0, 1.0),
                    (1.0, 2.0, 0.0),
                    (1.0, 1.0, 2.0),
                    (2.0, 0.0, 0.0),
                    (2.0, 1.0, 1.0),
                ],
            ),
            (
                ("first", "second", "third", "fourth"),
                [
                    (2.0, 1.0, 1.0, 1.0),
                    (1.0, 1.0, 1.0, 1.0),
                    (1.0, 2.0, 0.0, 0.0),
                    (1.0, 1.0, 2.0, 0.0),
                    (1.0, 1.0, 1.0, 2.0),
                    (2.0, 1.0, 1.0, 1.0),
                ],
            ),
        ],
    )
    def test_fast_front_matches_independent_slow_oracle(
        self,
        metric_names: tuple[str, ...],
        points: list[tuple[float, ...]],
    ) -> None:
        """Fast dimension-specific paths agree with a small direct oracle."""
        # Catches an optimization that fixes only the named witness while
        # diverging from strict dominance on a nearby finite point set.
        promoter = ParetoPromoter(_policies(*metric_names))

        expected = _slow_non_dominated_points(points)

        assert promoter._find_non_dominated(points) == expected

    def test_three_objective_front_matches_slow_reference(self):
        promoter = ParetoPromoter(_policies("acc", "speed", "fairness"))
        evals = [
            _eval(acc=0.9, speed=0.2, fairness=0.2),
            _eval(acc=0.8, speed=0.8, fairness=0.2),
            _eval(acc=0.8, speed=0.3, fairness=0.8),
            _eval(acc=0.7, speed=0.7, fairness=0.7),
            _eval(acc=0.6, speed=0.2, fairness=0.2),
        ]

        objectives = [promoter._eval_objectives(evaluation) for evaluation in evals]
        expected_indices = _slow_non_dominated_indices(objectives, promoter)
        front = promoter.compute_front(evals)

        expected = {tuple(objectives[index].values()) for index in expected_indices}
        observed = {tuple(member.objectives.values()) for member in front.members}
        assert observed == expected


def _slow_non_dominated_indices(
    objectives: list[dict[str, float]],
    promoter: ParetoPromoter,
) -> list[int]:
    return [
        index
        for index, point in enumerate(objectives)
        if not any(
            other_index != index and promoter._dominates(other, point)
            for other_index, other in enumerate(objectives)
        )
    ]
