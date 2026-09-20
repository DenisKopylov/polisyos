"""Forward-chaining cross-validation for time-series backtesting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from operator import index

import numpy as np


@dataclass(frozen=True)
class CVFold:
    """One fold of forward-chaining CV."""

    fold_id: int
    train_indices: list[int]
    test_indices: list[int]
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CVResult:
    """Aggregated cross-validation result."""

    folds: list[CVFold]
    mean_metrics: dict[str, float]
    std_metrics: dict[str, float]
    n_folds: int


def forward_chaining_splits(
    n_samples: int,
    *,
    min_train_size: int = 2,
    step_size: int = 1,
    max_folds: int | None = None,
) -> list[tuple[list[int], list[int]]]:
    """Generate forward-chaining (expanding window) train/test splits.

    Each fold uses all data up to time t for training and predicts t+1...t+step.
    """
    n_samples = _coerce_index(n_samples, "n_samples")
    min_train_size = _coerce_index(min_train_size, "min_train_size")
    step_size = _coerce_index(step_size, "step_size")
    if max_folds is not None:
        max_folds = _coerce_index(max_folds, "max_folds")

    if n_samples < 0:
        raise ValueError("n_samples must be non-negative")
    if min_train_size <= 0 or min_train_size > n_samples:
        raise ValueError("min_train_size must be greater than zero and at most n_samples")
    if step_size <= 0:
        raise ValueError("step_size must be greater than zero")
    if max_folds is not None and max_folds <= 0:
        raise ValueError("max_folds must be greater than zero")

    available_folds = max(0, (n_samples - min_train_size + step_size - 1) // step_size)
    if max_folds is None or max_folds >= available_folds:
        selected_positions = range(available_folds)
    else:
        # Keep the old evenly spaced fold positions without materializing folds that
        # will be discarded.  The integer conversion matches the previous
        # np.linspace(..., dtype=int) selection exactly.
        selected_positions = (
            int(position)
            for position in np.linspace(
                0,
                available_folds - 1,
                max_folds,
                dtype=int,
            )
        )

    splits: list[tuple[list[int], list[int]]] = []
    for position in selected_positions:
        train_start = min_train_size + position * step_size
        test_end = min(train_start + step_size, n_samples)
        train = list(range(train_start))
        test = list(range(train_start, test_end))
        if test:
            splits.append((train, test))

    return splits


def _coerce_index(value: int, name: str) -> int:
    """Return an integer parameter or raise a domain validation error."""
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be an integer")
    try:
        return int(index(value))
    except TypeError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def run_forward_chaining_cv(
    data: np.ndarray,
    evaluator: Callable[[np.ndarray, np.ndarray], dict[str, float]],
    *,
    min_train_size: int = 2,
    step_size: int = 1,
    max_folds: int | None = None,
) -> CVResult:
    """Run forward-chaining CV with a user-provided evaluator.

    Parameters
    ----------
    data:
        1D array of observations (time-ordered).
    evaluator:
        Callable(train_data, test_data) -> dict of metric_name -> value.
    min_train_size:
        Minimum training set size.
    step_size:
        Number of time steps per fold.
    max_folds:
        Maximum number of folds.
    """
    arr = np.asarray(data, dtype=float)
    splits = forward_chaining_splits(
        len(arr),
        min_train_size=min_train_size,
        step_size=step_size,
        max_folds=max_folds,
    )

    folds: list[CVFold] = []
    for fold_id, (train_idx, test_idx) in enumerate(splits):
        train_data = arr[train_idx]
        test_data = arr[test_idx]
        metrics = evaluator(train_data, test_data)
        folds.append(
            CVFold(
                fold_id=fold_id,
                train_indices=train_idx,
                test_indices=test_idx,
                metrics=metrics,
            )
        )

    # Aggregate
    all_metric_names: set[str] = set()
    for f in folds:
        all_metric_names.update(f.metrics.keys())

    mean_metrics: dict[str, float] = {}
    std_metrics: dict[str, float] = {}
    for name in sorted(all_metric_names):
        values = [f.metrics[name] for f in folds if name in f.metrics]
        if values:
            mean_metrics[name] = float(np.mean(values))
            std_metrics[name] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0

    return CVResult(
        folds=folds,
        mean_metrics=mean_metrics,
        std_metrics=std_metrics,
        n_folds=len(folds),
    )
