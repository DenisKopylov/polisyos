"""Tests for forward-chaining cross-validation."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.scientist.backtesting.cv import (
    CVResult,
    forward_chaining_splits,
    run_forward_chaining_cv,
)


class TestForwardChainingSplits:
    def test_basic_splits(self):
        splits = forward_chaining_splits(10, min_train_size=3, step_size=1)
        assert len(splits) > 0
        for train, test in splits:
            assert max(train) < min(test)

    def test_expanding_window(self):
        splits = forward_chaining_splits(10, min_train_size=2, step_size=1)
        for i in range(1, len(splits)):
            assert len(splits[i][0]) >= len(splits[i - 1][0])

    def test_max_folds(self):
        splits = forward_chaining_splits(100, min_train_size=2, max_folds=5)
        assert len(splits) <= 5

    def test_small_data(self):
        splits = forward_chaining_splits(3, min_train_size=2, step_size=1)
        assert len(splits) == 1


class TestRunForwardChainingCV:
    def test_basic_cv(self):
        data = np.arange(20, dtype=float)

        def evaluator(train, test):
            pred = np.full_like(test, np.mean(train))
            mae = float(np.mean(np.abs(test - pred)))
            return {"mae": mae}

        result = run_forward_chaining_cv(data, evaluator, min_train_size=5)
        assert result.n_folds > 0
        assert "mae" in result.mean_metrics
        assert result.std_metrics["mae"] >= 0

    def test_step_size(self):
        data = np.arange(20, dtype=float)
        result = run_forward_chaining_cv(
            data,
            lambda tr, te: {"n": float(len(te))},
            min_train_size=5,
            step_size=3,
        )
        assert result.n_folds > 0
