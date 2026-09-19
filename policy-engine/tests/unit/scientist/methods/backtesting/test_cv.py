"""Tests for forward-chaining cross-validation."""

from __future__ import annotations

import builtins

import numpy as np
import pytest
from polisyos.scientist.methods.backtesting.cv import (
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

    @pytest.mark.parametrize(
        ("min_train_size", "step_size", "max_folds"),
        [
            (2, 0, 3),
            (2, -1, 3),
            (0, 1, 3),
            (-1, 1, 3),
            (1001, 1, 3),
            (2, 1, 0),
            (2, 1, -1),
        ],
    )
    def test_invalid_cv_parameters_are_rejected_before_loop(
        self,
        monkeypatch,
        min_train_size,
        step_size,
        max_folds,
    ):
        def forbidden_range(*args):
            raise AssertionError("invalid parameter entered fold materialization")

        monkeypatch.setattr(builtins, "range", forbidden_range)

        with pytest.raises(ValueError):
            forward_chaining_splits(
                1000,
                min_train_size=min_train_size,
                step_size=step_size,
                max_folds=max_folds,
            )


class TestRunForwardChainingCV:
    def test_max_folds_limits_preparation_before_cv_evaluator(self, monkeypatch):
        real_range = builtins.range
        materialized_items = 0

        def bounded_range(*args):
            nonlocal materialized_items
            requested = real_range(*args)
            materialized_items += len(requested)
            if materialized_items > 1504:
                raise AssertionError("discarded folds were materialized")
            return requested

        monkeypatch.setattr(builtins, "range", bounded_range)
        data = np.arange(1000, dtype=float)
        observed_shapes = []

        def evaluator(train, test):
            observed_shapes.append((len(train), len(test)))
            return {"test_size": float(len(test))}

        result = run_forward_chaining_cv(
            data,
            evaluator,
            min_train_size=2,
            step_size=1,
            max_folds=3,
        )

        assert [(len(fold.train_indices), fold.test_indices) for fold in result.folds] == [
            (2, [2]),
            (500, [500]),
            (999, [999]),
        ]
        assert sum(
            len(fold.train_indices) + len(fold.test_indices) for fold in result.folds
        ) == 1504
        assert observed_shapes == [(2, 1), (500, 1), (999, 1)]

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
