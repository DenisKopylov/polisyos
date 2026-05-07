"""Tests for WS6.2 — Semantic Convergence Detection."""

from __future__ import annotations

import math

import pytest
from polisyos.scientist.orchestration.engine.convergence import (
    ConvergenceConfig,
    ConvergenceDetector,
    ConvergenceStrategy,
    _cosine_similarity,
    _linear_regression_slope,
)

# ---------------------------------------------------------------------------
# Helper: mock embedder
# ---------------------------------------------------------------------------


class MockEmbedder:
    """Returns a fixed embedding or an echo of the input text."""

    def __init__(self, dim: int = 32):
        self._dim = dim
        self._call_count = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            self._call_count += 1
            # Use per-character hashing to spread signal across dimensions
            vec = [0.0] * self._dim
            for ci, ch in enumerate(text):
                idx = (ord(ch) + ci * 7) % self._dim
                vec[idx] += (ord(ch) - 96) / 26.0
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            results.append(vec)
        return results

    @property
    def dim(self) -> int:
        return self._dim


class ConstantEmbedder:
    """Always returns the same vector."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.5, 0.5, 0.5, 0.5]] * len(texts)

    @property
    def dim(self) -> int:
        return 4


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert _cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert _cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0], [1, 0]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Linear regression slope
# ---------------------------------------------------------------------------


class TestLinearRegressionSlope:
    def test_increasing_sequence(self):
        slope = _linear_regression_slope([0.0, 1.0, 2.0, 3.0])
        assert slope == pytest.approx(1.0, abs=0.01)

    def test_flat_sequence(self):
        slope = _linear_regression_slope([5.0, 5.0, 5.0])
        assert abs(slope) < 0.01

    def test_single_value(self):
        assert _linear_regression_slope([42.0]) == 0.0


# ---------------------------------------------------------------------------
# Backward compat: classic strategies unchanged
# ---------------------------------------------------------------------------


class TestClassicStrategies:
    def test_absolute_delta_unchanged(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.ABSOLUTE_DELTA,
            threshold=0.05,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(1.0)
        d.check(1.0)
        state = d.check(1.0)
        assert state.converged

    def test_relative_delta_unchanged(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.RELATIVE_DELTA,
            threshold=0.05,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(10.0)
        d.check(10.0)
        state = d.check(10.0)
        assert state.converged


# ---------------------------------------------------------------------------
# Embedding cosine strategy
# ---------------------------------------------------------------------------


class TestEmbeddingCosine:
    def test_identical_texts_converge(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.EMBEDDING_COSINE,
            threshold=0.99,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg, embedder=ConstantEmbedder())
        d.check_with_text(1.0, "same text")
        state = d.check_with_text(1.0, "same text")
        assert state.converged

    def test_different_texts_no_convergence(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.EMBEDDING_COSINE,
            threshold=0.99,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg, embedder=MockEmbedder())
        d.check_with_text(1.0, "text alpha")
        state = d.check_with_text(1.0, "completely different text beta gamma delta")
        assert not state.converged

    def test_no_embedder_does_not_converge(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.EMBEDDING_COSINE,
            threshold=0.5,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg, embedder=None)
        d.check_with_text(1.0, "a")
        state = d.check_with_text(1.0, "a")
        assert not state.converged

    def test_check_without_text_falls_back(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.EMBEDDING_COSINE,
            threshold=0.5,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg, embedder=MockEmbedder())
        d.check(1.0)
        state = d.check(1.0)
        # No text -> no embeddings -> not converged
        assert not state.converged


# ---------------------------------------------------------------------------
# Statistical plateau
# ---------------------------------------------------------------------------


class TestStatisticalPlateau:
    def test_flat_series_converges(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.STATISTICAL_PLATEAU,
            threshold=0.05,
            min_iterations=3,
            window_size=3,
        )
        d = ConvergenceDetector(cfg)
        d.check(5.0)
        d.check(5.01)
        state = d.check(4.99)
        assert state.converged

    def test_improving_series_does_not_converge(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.STATISTICAL_PLATEAU,
            threshold=0.01,
            min_iterations=3,
            window_size=3,
        )
        d = ConvergenceDetector(cfg)
        d.check(10.0)
        d.check(7.0)
        state = d.check(4.0)
        assert not state.converged


# ---------------------------------------------------------------------------
# Budget projection
# ---------------------------------------------------------------------------


class TestBudgetProjection:
    def test_flat_trend_converges(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.BUDGET_PROJECTION,
            threshold=0.1,
            min_iterations=3,
            max_iterations=20,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(5.0)
        d.check(5.0)
        state = d.check(5.0)
        assert state.converged

    def test_improving_trend_does_not_converge(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.BUDGET_PROJECTION,
            threshold=0.01,
            min_iterations=3,
            max_iterations=50,
            window_size=2,
        )
        d = ConvergenceDetector(cfg)
        d.check(10.0)
        d.check(8.0)
        state = d.check(6.0)
        assert not state.converged


# ---------------------------------------------------------------------------
# Multi-signal composite
# ---------------------------------------------------------------------------


class TestMultiSignal:
    def test_all_signals_converged(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.MULTI_SIGNAL,
            threshold=0.4,
            min_iterations=2,
            window_size=2,
            signal_weights={"numeric": 0.5, "budget": 0.3, "semantic": 0.2},
        )
        d = ConvergenceDetector(cfg, embedder=ConstantEmbedder())
        # Feed flat metrics -> numeric signal = 1.0
        d.check_with_text(5.0, "same")
        state = d.check_with_text(5.0, "same")
        # numeric=1.0*0.5=0.5, budget=0.0*0.3=0.0, semantic=1.0*0.2=0.2
        # total = 0.7 >= 0.4
        assert state.converged

    def test_only_numeric_not_enough(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.MULTI_SIGNAL,
            threshold=0.8,
            min_iterations=2,
            window_size=2,
            signal_weights={"numeric": 0.5, "budget": 0.3, "semantic": 0.2},
        )
        d = ConvergenceDetector(cfg)
        d.check(5.0)
        state = d.check(5.0)
        # numeric=1.0*0.5=0.5, budget=0.0, semantic=0.0 -> 0.5 < 0.8
        assert not state.converged


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestDetectorReset:
    def test_reset_clears_all_state(self):
        cfg = ConvergenceConfig(
            strategy=ConvergenceStrategy.EMBEDDING_COSINE,
            threshold=0.5,
            min_iterations=2,
            window_size=2,
        )
        d = ConvergenceDetector(cfg, embedder=MockEmbedder())
        d.check_with_text(1.0, "hello")
        d.check_with_text(1.0, "world")
        d.reset()
        assert d._iteration == 0
        assert len(d._history) == 0
        assert len(d._text_embeddings) == 0
