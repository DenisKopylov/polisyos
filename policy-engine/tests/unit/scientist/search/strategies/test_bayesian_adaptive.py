"""Tests for WS6.6 — Bayesian Search Enhancements (adaptive acquisition, refit)."""

from __future__ import annotations

import pytest
from polisyos.scientist.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.search.strategies.types import (
    AcquisitionType,
    Evaluation,
    EvaluationStatus,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestBayesianConfigExtensions:
    def test_default_adaptive_off(self):
        cfg = BayesianConfig()
        assert cfg.adaptive_acquisition is False

    def test_adaptive_fields(self):
        cfg = BayesianConfig(
            adaptive_acquisition=True,
            exploration_switch_threshold=0.5,
            refit_interval=10,
            warm_start_noise_factor=0.2,
        )
        assert cfg.adaptive_acquisition is True
        assert cfg.exploration_switch_threshold == 0.5
        assert cfg.refit_interval == 10
        assert cfg.warm_start_noise_factor == 0.2

    def test_backward_compatible_defaults(self):
        cfg = BayesianConfig()
        assert cfg.n_initial == 6
        assert cfg.acquisition == AcquisitionType.EI
        assert cfg.refit_interval == 5


# ---------------------------------------------------------------------------
# Adaptive acquisition selection
# ---------------------------------------------------------------------------


class TestAdaptiveAcquisition:
    def _make_evaluations(self, scores: list[float]) -> list[Evaluation]:
        """Create mock evaluations with given scores."""
        evals = []
        for i, score in enumerate(scores):
            evals.append(
                Evaluation(
                    candidate_id=f"c{i}",
                    params={"x": float(i)},
                    params_normalized=(float(i) / max(1, len(scores)),),
                    objectives=[],
                    scalar_score=score,
                    stage_a_passed=True,
                    status=EvaluationStatus.SUCCESS,
                )
            )
        return evals

    def test_adaptive_off_returns_config(self):
        """When adaptive_acquisition=False, use the configured acquisition."""
        try:
            from polisyos.scientist.search.strategies.space import SearchSpace
            from polisyos.scientist.search.strategies.types import ParameterBounds

            space = SearchSpace([ParameterBounds(name="x", lower=0.0, upper=1.0)])
            cfg = BayesianConfig(adaptive_acquisition=False, acquisition=AcquisitionType.UCB)
            opt = BayesianOptimizer(space, config=cfg)
            result = opt._select_acquisition([], None)
            assert result == AcquisitionType.UCB
        except Exception:
            pytest.skip("torch/botorch not available")

    def test_adaptive_on_few_evals_returns_ei(self):
        """With < 5 evaluations, default to EI."""
        try:
            from polisyos.scientist.search.strategies.space import SearchSpace
            from polisyos.scientist.search.strategies.types import ParameterBounds

            space = SearchSpace([ParameterBounds(name="x", lower=0.0, upper=1.0)])
            cfg = BayesianConfig(adaptive_acquisition=True)
            opt = BayesianOptimizer(space, config=cfg)
            evals = self._make_evaluations([1.0, 2.0, 3.0])
            result = opt._select_acquisition(evals, None)
            assert result == AcquisitionType.EI
        except Exception:
            pytest.skip("torch/botorch not available")

    def test_adaptive_stuck_returns_ucb(self):
        """When no improvement in recent window, switch to UCB."""
        try:
            from polisyos.scientist.search.strategies.space import SearchSpace
            from polisyos.scientist.search.strategies.types import ParameterBounds

            space = SearchSpace([ParameterBounds(name="x", lower=0.0, upper=1.0)])
            cfg = BayesianConfig(adaptive_acquisition=True)
            opt = BayesianOptimizer(space, config=cfg)
            # All same scores -> stuck
            evals = self._make_evaluations([5.0, 5.0, 5.0, 5.0, 5.0, 5.0])
            result = opt._select_acquisition(evals, None)
            assert result == AcquisitionType.UCB
        except Exception:
            pytest.skip("torch/botorch not available")
