from __future__ import annotations

import pytest

from polisyos.core.evaluation import ThresholdBand, ThresholdMapper, WeightedScorer


def test_weighted_scorer_normalizes_and_handles_missing_components() -> None:
    scorer = WeightedScorer({"a": 2.0, "b": 1.0, "c": 1.0})

    result = scorer.score({"a": 1.0, "b": None, "c": 0.5})

    # effective weights re-normalize over present components a/c = 2/3 and 1/3
    assert round(result.score, 6) == round((2.0 / 3.0) * 1.0 + (1.0 / 3.0) * 0.5, 6)
    assert result.components == {"a": 1.0, "c": 0.5}


def test_threshold_mapper() -> None:
    mapper = ThresholdMapper[str](
        [
            ThresholdBand(0.8, "high"),
            ThresholdBand(0.5, "medium"),
            ThresholdBand(0.0, "low"),
        ],
        default="low",
    )

    assert mapper.map(0.9) == "high"
    assert mapper.map(0.7) == "medium"
    assert mapper.map(0.1) == "low"
    assert mapper.map(None) == "low"


def test_weighted_scorer_all_zero_component_scores() -> None:
    scorer = WeightedScorer({"a": 0.2, "b": 0.8})
    result = scorer.score({"a": 0.0, "b": 0.0})
    assert result.score == 0.0
    assert result.contributions == {"a": 0.0, "b": 0.0}


def test_weighted_scorer_extreme_weights_are_normalized() -> None:
    scorer = WeightedScorer({"tiny": 1e-12, "huge": 1e12})
    result = scorer.score({"tiny": 1.0, "huge": 0.5})

    assert result.score == pytest.approx(0.5, rel=1e-12)
    assert result.effective_weights["huge"] == pytest.approx(1.0, rel=1e-12)
    assert result.effective_weights["tiny"] == pytest.approx(1e-24, rel=1e-8)


def test_weighted_scorer_all_zero_weights_rejected() -> None:
    with pytest.raises(ValueError, match="weights cannot be empty"):
        WeightedScorer({"a": 0.0, "b": 0.0})
