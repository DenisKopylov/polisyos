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
            (2, 1.5, 3),
            (0, 1, 3),
            (-1, 1, 3),
            (1001, 1, 3),
            (2, 1, 0),
            (2, 1, -1),
            (True, 1, 3),
            (2, True, 3),
            (2, 1, True),
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

        with monkeypatch.context() as scoped:
            scoped.setattr(builtins, "range", forbidden_range)

            with pytest.raises(ValueError):
                forward_chaining_splits(
                    1000,
                    min_train_size=min_train_size,
                    step_size=step_size,
                    max_folds=max_folds,
                )

    def test_numpy_integer_parameters_remain_valid(self):
        splits = forward_chaining_splits(
            np.int64(10),
            min_train_size=np.int64(2),
            step_size=np.int64(2),
            max_folds=np.int64(2),
        )

        assert [(len(train), test) for train, test in splits] == [
            (2, [2, 3]),
            (8, [8, 9]),
        ]

    def test_full_training_window_has_no_test_folds(self) -> None:
        assert forward_chaining_splits(4, min_train_size=4) == []


class TestRunForwardChainingCV:
    def test_metric_summary_counts_only_usable_selected_folds(self) -> None:
        metrics: dict[str, float] = {}

        def evaluator(_train: np.ndarray, test: np.ndarray) -> dict[str, float]:
            metrics.clear()
            if len(test) == 2:
                metrics.update(mae=3.0, coverage=np.nan, both=2.0)
            else:
                metrics.update(coverage=0.8, both=8.0)
            return metrics

        result = run_forward_chaining_cv(
            np.arange(5, dtype=float), evaluator, min_train_size=2, step_size=2
        )

        mae = result.metric_summary("mae")
        assert (mae.requested_folds, mae.evaluated_folds, mae.missing_folds, mae.invalid_folds) == (
            2,
            1,
            1,
            0,
        )
        assert mae.mean == 3.0
        coverage = result.metric_summary("coverage")
        assert (
            coverage.requested_folds,
            coverage.evaluated_folds,
            coverage.missing_folds,
            coverage.invalid_folds,
        ) == (2, 1, 0, 1)
        assert coverage.mean == 0.8
        assert np.isnan(result.folds[0].metrics["coverage"])
        assert result.metric_summary("never_emitted").mean is None
        assert result.metric_summary("never_emitted").missing_folds == 2
        both = result.metric_summary("both")
        assert both.weighting == "equal_evaluated_fold"
        assert both.mean == 5.0  # The second fold has one cell and the first has two.

    def test_multivariate_observations_keep_features_and_isolate_folds(self) -> None:
        data = np.arange(12, dtype=float).reshape(6, 2)
        original = data.copy()
        selected_rows = iter((2, 5))

        def evaluator(train: np.ndarray, test: np.ndarray) -> dict[str, float]:
            row = next(selected_rows)
            np.testing.assert_array_equal(train, original[:row])
            np.testing.assert_array_equal(test, original[row : row + 1])
            metric = float(test[0, 1])
            train[:] = -1.0
            test[:] = -1.0
            return {"feature_value": metric}

        result = run_forward_chaining_cv(data, evaluator, min_train_size=2, max_folds=2)

        assert result.n_folds == 2
        assert result.mean_metrics == {"feature_value": 8.0}
        np.testing.assert_array_equal(data, original)

    def test_max_folds_limits_preparation_before_cv_evaluator(self, monkeypatch):
        real_range = builtins.range
        materialized_items = 0

        data = np.arange(1000, dtype=float)
        observed_shapes = []

        with monkeypatch.context() as scoped:

            def bounded_range(*args):
                nonlocal materialized_items
                requested = real_range(*args)
                materialized_items += len(requested)
                if materialized_items > 1504:
                    raise AssertionError("discarded folds were materialized")
                return requested

            scoped.setattr(builtins, "range", bounded_range)

            def evaluator(train, test):
                observed_shapes.append((len(train), len(test)))
                if len(observed_shapes) == 3:
                    # Stop observing after the selected folds have reached the
                    # evaluator; NumPy's later metric reduction also uses range.
                    scoped.undo()
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
        assert (
            sum(len(fold.train_indices) + len(fold.test_indices) for fold in result.folds) == 1504
        )
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
