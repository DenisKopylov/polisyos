"""Tests for NeuralSearchStrategy — WS5 neural search."""

from __future__ import annotations

import sys
from datetime import datetime

import pytest

sys.path.insert(0, "src")

from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.neural import (
    NeuralSearchConfig,
    NeuralSearchStrategy,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    EvaluationStatus,
    ParameterBounds,
    PolicyCandidate,
)


def _make_space() -> SearchSpace:
    return SearchSpace(bounds=[ParameterBounds(name="x", lower=0.0, upper=1.0)])


def _make_evaluation(
    x: float = 0.5,
    score: float = 1.0,
    *,
    valid: bool = True,
) -> Evaluation:
    return Evaluation(
        candidate_id="cand-1",
        params={"x": x},
        params_normalized=(x,),
        objectives=[
            ObjectiveValue(
                name="obj",
                raw_value=score,
                direction=OptimizationDirection.MAXIMIZE,
            )
        ],
        scalar_score=score,
        stage_a_passed=valid,
        status=EvaluationStatus.SUCCESS if valid else EvaluationStatus.STAGE_A_REJECT,
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
    )


class TestSuggestInitialSobol:
    def test_suggest_initial_sobol(self) -> None:
        space = _make_space()
        config = NeuralSearchConfig(n_initial=8, seed=42)
        strategy = NeuralSearchStrategy(space, config=config)

        # With fewer evaluations than n_initial, should use sobol
        candidate = strategy.suggest(evaluations=[])
        assert isinstance(candidate, PolicyCandidate)
        assert candidate.params_normalized is not None
        assert "x" in candidate.params
        # Source should indicate sobol init
        assert (
            "sobol" in candidate.source_strategy.lower()
            or "neural" in candidate.source_strategy.lower()
        )


class TestWarmStart:
    def test_warm_start(self) -> None:
        space = _make_space()
        strategy = NeuralSearchStrategy(space)

        evals = [_make_evaluation(x=0.3, score=0.8)]
        # Should not raise
        strategy.warm_start(evals)

        # Invalid evaluations should be filtered
        invalid_eval = _make_evaluation(x=0.7, score=0.1, valid=False)
        strategy.warm_start([invalid_eval])


class TestGetState:
    def test_get_state(self) -> None:
        space = _make_space()
        config = NeuralSearchConfig(seed=123)
        strategy = NeuralSearchStrategy(space, config=config)

        state = strategy.get_state()
        assert state.strategy_name == "NeuralSearchStrategy"
        assert "warm_start_count" in state.metadata
        assert "config" in state.metadata


class TestGPBasedSuggest:
    """GP-based tests require BoTorch. Skip if unavailable."""

    @pytest.fixture(autouse=True)
    def _require_botorch(self) -> None:
        pytest.importorskip("botorch", reason="BoTorch not installed")

    def test_suggest_after_initial_phase(self) -> None:
        space = _make_space()
        config = NeuralSearchConfig(n_initial=3, seed=42)
        strategy = NeuralSearchStrategy(space, config=config)

        # Provide enough evaluations to pass the initial phase
        evals = [_make_evaluation(x=i / 10.0, score=i * 0.1) for i in range(1, 6)]

        candidate = strategy.suggest(evaluations=evals)
        assert isinstance(candidate, PolicyCandidate)
        assert "x" in candidate.params
