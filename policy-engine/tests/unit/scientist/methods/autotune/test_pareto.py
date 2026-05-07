"""Tests for Pareto front computation and promotion."""

from __future__ import annotations

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
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
