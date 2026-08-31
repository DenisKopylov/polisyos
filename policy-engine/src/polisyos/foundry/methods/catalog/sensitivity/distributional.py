"""Quantile and distributional sensitivity indices.

This module implements the Phase 5 catalog entry for sensitivity questions
that are not variance-centered: median and tail quantiles, tail distribution
shape, whole-output CDF shifts, PAWN screening, and Borgonovo-style TV
dependence via a classifier surrogate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)

_EPS = 1.0e-12


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _coerce_xy(X: Any, Y: Any) -> tuple[np.ndarray, np.ndarray]:
    inputs = np.asarray(X, dtype=float)
    outputs = np.asarray(Y, dtype=float)
    if inputs.ndim == 1:
        inputs = inputs.reshape(-1, 1)
    if inputs.ndim != 2:
        raise ValueError("X/inputs_matrix must be a 2D matrix")
    if outputs.ndim != 1:
        outputs = outputs.reshape(-1)
    if inputs.shape[0] != outputs.shape[0]:
        raise ValueError("X and Y must have the same number of rows")
    if not np.all(np.isfinite(outputs)) or not np.all(np.isfinite(inputs)):
        raise ValueError("X and Y must contain only finite values")
    if inputs.shape[0] < 3:
        raise ValueError("at least three finite observations are required")
    return inputs, outputs


def _coerce_weights(sample_weight: Any, n: int) -> np.ndarray:
    if sample_weight is None:
        return np.ones(n, dtype=float)
    weights = np.asarray(sample_weight, dtype=float).reshape(-1)
    if weights.shape[0] != n:
        raise ValueError("sample_weight must align with Y")
    weights = np.where(np.isfinite(weights) & (weights > 0.0), weights, 0.0)
    if float(np.sum(weights)) <= 0.0:
        raise ValueError("sample_weight must contain positive finite mass")
    return weights


def _problem_names(problem: Mapping[str, Any] | None, n_features: int) -> list[str]:
    if isinstance(problem, Mapping):
        raw_names = problem.get("names")
        if raw_names is not None:
            names = [str(name) for name in raw_names]
            if len(names) != n_features:
                raise ValueError("problem.names must match X column count")
            return names
    return [f"x{i + 1}" for i in range(n_features)]


def _parse_groups(groups: Any, names: Sequence[str]) -> list[tuple[list[int], list[str]]]:
    name_to_index = {name: idx for idx, name in enumerate(names)}
    n_features = len(names)

    if groups is None or groups == "first_order":
        return [([idx], [names[idx]]) for idx in range(n_features)]
    if groups == "all":
        return [(list(range(n_features)), list(names))]
    if isinstance(groups, (str, int)):
        groups = [groups]

    parsed: list[tuple[list[int], list[str]]] = []
    for group in groups:
        if isinstance(group, (str, int)):
            raw_members = [group]
        else:
            raw_members = list(group)
        indices: list[int] = []
        labels: list[str] = []
        for member in raw_members:
            if isinstance(member, str):
                if member not in name_to_index:
                    raise ValueError(f"unknown group member: {member}")
                idx = name_to_index[member]
            else:
                idx = int(member)
                if idx < 0 or idx >= n_features:
                    raise ValueError(f"group index out of range: {idx}")
            if idx not in indices:
                indices.append(idx)
                labels.append(names[idx])
        if not indices:
            raise ValueError("groups cannot contain empty entries")
        parsed.append((indices, labels))
    if not parsed:
        raise ValueError("at least one group is required")
    return parsed


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    weight_sum = float(np.sum(weights))
    if weight_sum <= 0.0:
        return float("nan")
    return float(np.sum(np.asarray(values, dtype=float) * weights) / weight_sum)


def _weighted_quantile(
    values: np.ndarray, quantile: float, weights: np.ndarray | None = None
) -> float:
    q = float(quantile)
    if q < 0.0 or q > 1.0:
        raise ValueError("quantiles must be in [0, 1]")
    arr = np.asarray(values, dtype=float).reshape(-1)
    finite = np.isfinite(arr)
    if weights is None:
        if not np.any(finite):
            raise ValueError("cannot estimate quantile from empty finite values")
        return float(np.quantile(arr[finite], q))
    w = np.asarray(weights, dtype=float).reshape(-1)
    finite &= np.isfinite(w) & (w > 0.0)
    if not np.any(finite):
        raise ValueError("cannot estimate weighted quantile without positive finite weights")
    arr = arr[finite]
    w = w[finite]
    order = np.argsort(arr)
    arr = arr[order]
    w = w[order]
    cdf = np.cumsum(w) / max(float(np.sum(w)), _EPS)
    return float(np.interp(q, cdf, arr, left=arr[0], right=arr[-1]))


def _weighted_ecdf(
    values: np.ndarray, grid: np.ndarray, weights: np.ndarray | None = None
) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    finite = np.isfinite(arr)
    if weights is None:
        w = np.ones_like(arr, dtype=float)
    else:
        w = np.asarray(weights, dtype=float).reshape(-1)
        finite &= np.isfinite(w) & (w > 0.0)
    arr = arr[finite]
    w = w[finite]
    if arr.size == 0 or float(np.sum(w)) <= 0.0:
        return np.zeros_like(grid, dtype=float)
    order = np.argsort(arr)
    arr = arr[order]
    cumulative = np.cumsum(w[order])
    positions = np.searchsorted(arr, grid, side="right") - 1
    result = np.zeros_like(grid, dtype=float)
    valid = positions >= 0
    result[valid] = cumulative[positions[valid]] / max(float(cumulative[-1]), _EPS)
    return np.clip(result, 0.0, 1.0)


def _pinball_loss(y: np.ndarray, q: np.ndarray, alpha: float) -> np.ndarray:
    indicator = (y <= q).astype(float)
    return (float(alpha) - indicator) * (y - q)


def _fold_masks(n: int, cv: int, seed: int | None) -> list[np.ndarray]:
    k = int(max(1, min(cv, n)))
    if k == 1:
        return [np.arange(n, dtype=int)]
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(n)
    return [fold.astype(int) for fold in np.array_split(permutation, k) if fold.size > 0]


def _thresholds_for_bins(x: np.ndarray, n_bins: int) -> list[np.ndarray]:
    matrix = np.asarray(x, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(-1, 1)
    thresholds: list[np.ndarray] = []
    for col in range(matrix.shape[1]):
        values = matrix[:, col]
        if np.allclose(values, values[0]):
            thresholds.append(np.asarray([], dtype=float))
            continue
        q = np.linspace(0.0, 1.0, int(max(2, n_bins)) + 1)
        edges = np.unique(np.quantile(values, q))
        thresholds.append(edges[1:-1])
    return thresholds


def _cell_codes(x: np.ndarray, thresholds: Sequence[np.ndarray]) -> list[tuple[int, ...]]:
    matrix = np.asarray(x, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(-1, 1)
    columns = [
        np.searchsorted(np.asarray(edges, dtype=float), matrix[:, col], side="right")
        for col, edges in enumerate(thresholds)
    ]
    if not columns:
        return [tuple() for _ in range(matrix.shape[0])]
    stacked = np.vstack(columns).T
    return [tuple(int(v) for v in row) for row in stacked]


def _cell_index_map(codes: Sequence[tuple[int, ...]]) -> dict[tuple[int, ...], np.ndarray]:
    buckets: dict[tuple[int, ...], list[int]] = {}
    for idx, code in enumerate(codes):
        buckets.setdefault(code, []).append(idx)
    return {code: np.asarray(indices, dtype=int) for code, indices in buckets.items()}


def _predict_binned_quantile(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
    *,
    alpha: float,
    weights_train: np.ndarray,
    n_bins: int,
    min_leaf: int,
) -> np.ndarray:
    thresholds = _thresholds_for_bins(X_train, n_bins)
    train_codes = _cell_codes(X_train, thresholds)
    eval_codes = _cell_codes(X_eval, thresholds)
    by_cell = _cell_index_map(train_codes)
    fallback = _weighted_quantile(y_train, alpha, weights_train)
    predictions = np.full(len(eval_codes), fallback, dtype=float)
    for pos, code in enumerate(eval_codes):
        indices = by_cell.get(code)
        if indices is None or indices.size < min_leaf:
            continue
        predictions[pos] = _weighted_quantile(y_train[indices], alpha, weights_train[indices])
    return predictions


def _predict_binned_cdf(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
    *,
    grid: np.ndarray,
    weights_train: np.ndarray,
    n_bins: int,
    min_leaf: int,
) -> np.ndarray:
    thresholds = _thresholds_for_bins(X_train, n_bins)
    train_codes = _cell_codes(X_train, thresholds)
    eval_codes = _cell_codes(X_eval, thresholds)
    by_cell = _cell_index_map(train_codes)
    fallback = _weighted_ecdf(y_train, grid, weights_train)
    predictions = np.tile(fallback, (len(eval_codes), 1))
    cache: dict[tuple[int, ...], np.ndarray] = {}
    for pos, code in enumerate(eval_codes):
        indices = by_cell.get(code)
        if indices is None or indices.size < min_leaf:
            continue
        if code not in cache:
            cdf = _weighted_ecdf(y_train[indices], grid, weights_train[indices])
            cache[code] = np.maximum.accumulate(np.clip(cdf, 0.0, 1.0))
        predictions[pos, :] = cache[code]
    return predictions


def _predict_forest_quantile(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
    *,
    alpha: float,
    weights_train: np.ndarray,
    min_leaf: int,
    random_seed: int | None,
) -> np.ndarray:
    try:
        from sklearn.ensemble import RandomForestRegressor
    except Exception as exc:  # pragma: no cover - optional dependency fallback
        raise RuntimeError("scikit-learn is required for quantile_forest") from exc

    forest = RandomForestRegressor(
        n_estimators=64,
        min_samples_leaf=max(int(min_leaf), 1),
        random_state=random_seed,
        n_jobs=1,
    )
    forest.fit(X_train, y_train, sample_weight=weights_train)
    fallback = _weighted_quantile(y_train, alpha, weights_train)
    predictions = np.full(X_eval.shape[0], fallback, dtype=float)
    train_leaves = [tree.apply(X_train) for tree in forest.estimators_]
    eval_leaves = [tree.apply(X_eval) for tree in forest.estimators_]
    for row in range(X_eval.shape[0]):
        pooled_indices = [
            np.flatnonzero(train_leaf == eval_leaf[row])
            for train_leaf, eval_leaf in zip(train_leaves, eval_leaves, strict=False)
        ]
        pooled = np.concatenate([idx for idx in pooled_indices if idx.size > 0])
        if pooled.size == 0:
            continue
        predictions[row] = _weighted_quantile(y_train[pooled], alpha, weights_train[pooled])
    return predictions


def _predict_forest_cdf(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
    *,
    grid: np.ndarray,
    weights_train: np.ndarray,
    min_leaf: int,
    random_seed: int | None,
) -> np.ndarray:
    try:
        from sklearn.ensemble import RandomForestRegressor
    except Exception as exc:  # pragma: no cover - optional dependency fallback
        raise RuntimeError("scikit-learn is required for cdf_forest") from exc

    forest = RandomForestRegressor(
        n_estimators=64,
        min_samples_leaf=max(int(min_leaf), 1),
        random_state=random_seed,
        n_jobs=1,
    )
    forest.fit(X_train, y_train, sample_weight=weights_train)
    fallback = _weighted_ecdf(y_train, grid, weights_train)
    predictions = np.tile(fallback, (X_eval.shape[0], 1))
    train_leaves = [tree.apply(X_train) for tree in forest.estimators_]
    eval_leaves = [tree.apply(X_eval) for tree in forest.estimators_]
    for row in range(X_eval.shape[0]):
        pooled_indices = [
            np.flatnonzero(train_leaf == eval_leaf[row])
            for train_leaf, eval_leaf in zip(train_leaves, eval_leaves, strict=False)
        ]
        pooled = np.concatenate([idx for idx in pooled_indices if idx.size > 0])
        if pooled.size == 0:
            continue
        predictions[row, :] = _weighted_ecdf(y_train[pooled], grid, weights_train[pooled])
    return np.maximum.accumulate(np.clip(predictions, 0.0, 1.0), axis=1)


def _predict_conditional_quantile(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
    *,
    alpha: float,
    weights_train: np.ndarray,
    n_bins: int,
    min_leaf: int,
    learner: str,
    random_seed: int | None,
) -> tuple[np.ndarray, str]:
    requested = str(learner).lower()
    if requested in {"auto", "quantile_forest", "forest", "random_forest"}:
        try:
            return (
                _predict_forest_quantile(
                    X_train,
                    y_train,
                    X_eval,
                    alpha=alpha,
                    weights_train=weights_train,
                    min_leaf=min_leaf,
                    random_seed=random_seed,
                ),
                "quantile_forest",
            )
        except RuntimeError:
            pass
    return (
        _predict_binned_quantile(
            X_train,
            y_train,
            X_eval,
            alpha=alpha,
            weights_train=weights_train,
            n_bins=n_bins,
            min_leaf=min_leaf,
        ),
        "quantile_bins",
    )


def _predict_conditional_cdf(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
    *,
    grid: np.ndarray,
    weights_train: np.ndarray,
    n_bins: int,
    min_leaf: int,
    learner: str,
    random_seed: int | None,
) -> tuple[np.ndarray, str]:
    requested = str(learner).lower()
    if requested in {"auto", "cdf_forest", "forest", "random_forest"}:
        try:
            return (
                _predict_forest_cdf(
                    X_train,
                    y_train,
                    X_eval,
                    grid=grid,
                    weights_train=weights_train,
                    min_leaf=min_leaf,
                    random_seed=random_seed,
                ),
                "cdf_forest",
            )
        except RuntimeError:
            pass
    return (
        _predict_binned_cdf(
            X_train,
            y_train,
            X_eval,
            grid=grid,
            weights_train=weights_train,
            n_bins=n_bins,
            min_leaf=min_leaf,
        ),
        "cdf_bins",
    )


def _silverman_bandwidth(values: np.ndarray, weights: np.ndarray | None = None) -> float:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if weights is None:
        w = np.ones(arr.shape[0], dtype=float)
    else:
        w = np.asarray(weights, dtype=float).reshape(-1)
    finite = np.isfinite(arr) & np.isfinite(w) & (w > 0.0)
    arr = arr[finite]
    w = w[finite]
    if arr.size < 2:
        return 1.0
    total_weight = max(float(np.sum(w)), _EPS)
    mean = float(np.sum(arr * w) / total_weight)
    variance = float(np.sum(w * (arr - mean) ** 2) / total_weight)
    std = max(variance**0.5, _EPS)
    q25, q75 = np.quantile(arr, [0.25, 0.75])
    robust_scale = min(std, max(float(q75 - q25) / 1.349, _EPS))
    effective_n = total_weight**2 / max(float(np.sum(w**2)), _EPS)
    return float(max(0.9 * robust_scale * effective_n ** (-1.0 / 5.0), _EPS))


def _kde_pdf(
    values: np.ndarray,
    grid: np.ndarray,
    *,
    weights: np.ndarray,
    bandwidth: float,
) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    w = np.asarray(weights, dtype=float).reshape(-1)
    finite = np.isfinite(arr) & np.isfinite(w) & (w > 0.0)
    arr = arr[finite]
    w = w[finite]
    if arr.size == 0:
        return np.zeros_like(grid, dtype=float)
    bw = max(float(bandwidth), _EPS)
    scaled = (grid[:, None] - arr[None, :]) / bw
    kernels = np.exp(-0.5 * scaled**2) / (bw * np.sqrt(2.0 * np.pi))
    pdf = kernels @ (w / max(float(np.sum(w)), _EPS))
    return np.maximum(pdf, 0.0)


def _predict_binned_density(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
    *,
    grid: np.ndarray,
    weights_train: np.ndarray,
    n_bins: int,
    min_leaf: int,
    bandwidth: float,
) -> np.ndarray:
    thresholds = _thresholds_for_bins(X_train, n_bins)
    train_codes = _cell_codes(X_train, thresholds)
    eval_codes = _cell_codes(X_eval, thresholds)
    by_cell = _cell_index_map(train_codes)
    fallback = _kde_pdf(y_train, grid, weights=weights_train, bandwidth=bandwidth)
    predictions = np.tile(fallback, (len(eval_codes), 1))
    cache: dict[tuple[int, ...], np.ndarray] = {}
    for pos, code in enumerate(eval_codes):
        indices = by_cell.get(code)
        if indices is None or indices.size < min_leaf:
            continue
        if code not in cache:
            cache[code] = _kde_pdf(
                y_train[indices],
                grid,
                weights=weights_train[indices],
                bandwidth=bandwidth,
            )
        predictions[pos, :] = cache[code]
    return predictions


def _qosa_group_estimate(
    X_group: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    *,
    alpha: float,
    cv: int,
    n_bins: int,
    min_leaf: int,
    learner: str,
    random_seed: int | None,
) -> tuple[float, float, float, float, np.ndarray, np.ndarray, str]:
    n = y.shape[0]
    q0_pred = np.zeros(n, dtype=float)
    qu_pred = np.zeros(n, dtype=float)
    folds = _fold_masks(n, cv, random_seed)
    all_indices = np.arange(n, dtype=int)
    learners_used: set[str] = set()
    for fold in folds:
        train = np.setdiff1d(all_indices, fold, assume_unique=False)
        if train.size == 0:
            train = all_indices
        q0 = _weighted_quantile(y[train], alpha, weights[train])
        q0_pred[fold] = q0
        fold_pred, learner_used = _predict_conditional_quantile(
            X_group[train],
            y[train],
            X_group[fold],
            alpha=alpha,
            weights_train=weights[train],
            n_bins=n_bins,
            min_leaf=min_leaf,
            learner=learner,
            random_seed=random_seed,
        )
        qu_pred[fold] = fold_pred
        learners_used.add(learner_used)

    h0_losses = _pinball_loss(y, q0_pred, alpha)
    hu_losses = _pinball_loss(y, qu_pred, alpha)
    h0 = _weighted_mean(h0_losses, weights)
    hu = _weighted_mean(hu_losses, weights)
    raw = (h0 - hu) / h0 if h0 > _EPS else float("nan")
    coverage = _weighted_mean((y <= qu_pred).astype(float), weights)
    learner_used_label = "+".join(sorted(learners_used)) if learners_used else "unknown"
    return raw, h0, hu, coverage, q0_pred, qu_pred, learner_used_label


def _tail_diagnostics(
    X_group: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    *,
    alpha: float,
    n_bins: int,
) -> dict[str, Any]:
    cutoff = _weighted_quantile(y, alpha, weights)
    exceed = y >= cutoff
    thresholds = _thresholds_for_bins(X_group, n_bins)
    codes = _cell_codes(X_group, thresholds)
    by_cell = _cell_index_map(codes)
    local_counts = [int(np.sum(exceed[indices])) for indices in by_cell.values()]
    return {
        "tail_cutoff": float(cutoff),
        "tail_exceedances": int(np.sum(exceed)),
        "min_local_tail_exceedances": int(min(local_counts) if local_counts else 0),
        "median_local_tail_exceedances": float(np.median(local_counts)) if local_counts else 0.0,
        "effective_leaves": int(len(by_cell)),
    }


def sample_size_qosa_cvm(
    epsilon: float,
    delta: float,
    p: int,
    group_dimension: int,
    *,
    beta: float = 1.0,
    constant: float = 1.0,
) -> int:
    """Planner from the Phase 5 QOSA/CVM rate bound."""
    eps = max(float(epsilon), _EPS)
    fail = min(max(float(delta), _EPS), 1.0 - _EPS)
    groups = max(int(p), 1)
    s = max(int(group_dimension), 1)
    smoothness = max(float(beta), _EPS)
    empirical = eps**-2.0 * np.log(groups / fail)
    nuisance = eps ** -((2.0 * smoothness + s) / (2.0 * smoothness))
    return int(np.ceil(float(constant) * max(empirical, nuisance)))


def sample_size_delta_tv(
    epsilon: float,
    delta: float,
    p: int,
    group_dimension: int,
    *,
    beta: float = 1.0,
    constant: float = 1.0,
) -> int:
    """Planner from the Phase 5 Delta-TV density plug-in rate bound."""
    eps = max(float(epsilon), _EPS)
    fail = min(max(float(delta), _EPS), 1.0 - _EPS)
    groups = max(int(p), 1)
    s = max(int(group_dimension), 1)
    smoothness = max(float(beta), _EPS)
    empirical = eps**-2.0 * np.log(groups / fail)
    nuisance = eps ** -((2.0 * smoothness + s + 1.0) / smoothness)
    return int(np.ceil(float(constant) * max(empirical, nuisance)))


def analyze_quantile(
    *,
    problem: Mapping[str, Any] | None,
    X: Any,
    Y: Any,
    alphas: Sequence[float] = (0.5, 0.95),
    groups: Any = "first_order",
    learner: str = "quantile_bins",
    cv: int = 5,
    n_boot: int = 0,
    sample_weight: Any = None,
    n_bins: int = 8,
    min_leaf: int = 5,
    random_seed: int | None = 0,
    denominator_tol: float = 1.0e-10,
    ci_level: float = 0.95,
    include_dummy: bool = True,
) -> dict[str, Any]:
    """Estimate cross-fitted QOSA-pinball sensitivity indices."""
    inputs, outputs = _coerce_xy(X, Y)
    weights = _coerce_weights(sample_weight, outputs.shape[0])
    names = _problem_names(problem, inputs.shape[1])
    parsed_groups = _parse_groups(groups, names)
    rng = np.random.default_rng(random_seed)
    n = outputs.shape[0]

    targets: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for alpha in [float(a) for a in alphas]:
        if alpha <= 0.0 or alpha >= 1.0:
            raise ValueError("alphas must be strictly between 0 and 1")
        estimates: list[dict[str, Any]] = []
        dummy_x = rng.normal(size=(n, 1))
        dummy_raw, dummy_h0, _, _, _, _, dummy_learner_used = _qosa_group_estimate(
            dummy_x,
            outputs,
            weights,
            alpha=alpha,
            cv=cv,
            n_bins=n_bins,
            min_leaf=min_leaf,
            learner=learner,
            random_seed=None if random_seed is None else int(random_seed) + 991,
        )
        for indices, labels in parsed_groups:
            x_group = inputs[:, indices]
            raw, h0, hu, coverage, _, q_pred, learner_used = _qosa_group_estimate(
                x_group,
                outputs,
                weights,
                alpha=alpha,
                cv=cv,
                n_bins=n_bins,
                min_leaf=min_leaf,
                learner=learner,
                random_seed=random_seed,
            )
            tail = _tail_diagnostics(x_group, outputs, weights, alpha=alpha, n_bins=n_bins)
            diagnostics = {
                "denominator": float(h0),
                "conditional_loss": float(hu),
                "quantile_coverage": float(coverage),
                "coverage_error": float(abs(coverage - alpha)),
                "denominator_status": "ok" if h0 > denominator_tol else "near_zero",
                "null_dummy_index": float(dummy_raw) if include_dummy else None,
                "dummy_denominator": float(dummy_h0) if include_dummy else None,
                "learner": learner_used,
                "learner_requested": learner,
                "dummy_learner": dummy_learner_used if include_dummy else None,
                "cross_fit_folds": int(max(1, min(cv, n))),
                "index_clipped": bool(raw < 0.0 or raw > 1.0),
                "raw_estimate": float(raw),
                "local_quantile_min": float(np.min(q_pred)),
                "local_quantile_max": float(np.max(q_pred)),
            }
            diagnostics.update(tail)
            estimates.append(
                {
                    "group": labels,
                    "estimate": float(np.clip(raw, 0.0, 1.0)),
                    "raw_estimate": float(raw),
                    "stderr": None,
                    "ci_low": None,
                    "ci_high": None,
                    "effective_n": int(n),
                    "convergence_rate": "n^-1/2 + n^(-2*beta/(2*beta+s))",
                    "sample_size_planner": {
                        "epsilon_0_05_beta_1": sample_size_qosa_cvm(
                            0.05,
                            0.05,
                            len(parsed_groups),
                            len(indices),
                        )
                    },
                    "diagnostics": diagnostics,
                }
            )
        target = {"alpha": float(alpha), "estimates": estimates}
        targets.append(target)
        results.append(
            {
                "method": "qosa_pinball",
                "target": {"alpha": float(alpha), "loss": "pinball"},
                "estimates": estimates,
            }
        )

    if n_boot > 0:
        _attach_quantile_bootstrap(
            targets,
            problem=problem,
            X=inputs,
            Y=outputs,
            weights=weights if sample_weight is not None else None,
            alphas=tuple(float(a) for a in alphas),
            groups=groups,
            learner=learner,
            cv=cv,
            n_boot=int(n_boot),
            n_bins=n_bins,
            min_leaf=min_leaf,
            random_seed=random_seed,
            denominator_tol=denominator_tol,
            ci_level=ci_level,
        )

    return {
        "method": "qosa_pinball",
        "target_family": "quantile",
        "targets": targets,
        "results": results,
        "diagnostics": {
            "n_samples": int(n),
            "n_features": int(inputs.shape[1]),
            "n_groups": int(len(parsed_groups)),
            "learner": learner,
            "cv": int(max(1, min(cv, n))),
            "n_boot": int(n_boot),
            "index_clipping": "raw_estimate retained; estimate is clipped to [0, 1]",
        },
    }


def _attach_quantile_bootstrap(
    targets: list[dict[str, Any]],
    *,
    problem: Mapping[str, Any] | None,
    X: np.ndarray,
    Y: np.ndarray,
    weights: np.ndarray | None,
    alphas: Sequence[float],
    groups: Any,
    learner: str,
    cv: int,
    n_boot: int,
    n_bins: int,
    min_leaf: int,
    random_seed: int | None,
    denominator_tol: float,
    ci_level: float,
) -> None:
    rng = np.random.default_rng(random_seed)
    boot_values: dict[tuple[float, tuple[str, ...]], list[float]] = {}
    n = Y.shape[0]
    for boot_idx in range(n_boot):
        rows = rng.integers(0, n, size=n)
        boot = analyze_quantile(
            problem=problem,
            X=X[rows],
            Y=Y[rows],
            alphas=alphas,
            groups=groups,
            learner=learner,
            cv=cv,
            n_boot=0,
            sample_weight=None if weights is None else weights[rows],
            n_bins=n_bins,
            min_leaf=min_leaf,
            random_seed=None if random_seed is None else int(random_seed) + boot_idx + 1,
            denominator_tol=denominator_tol,
            include_dummy=False,
        )
        for target in boot["targets"]:
            alpha = float(target["alpha"])
            for estimate in target["estimates"]:
                key = (alpha, tuple(str(v) for v in estimate["group"]))
                boot_values.setdefault(key, []).append(float(estimate["raw_estimate"]))

    alpha_tail = (1.0 - float(ci_level)) / 2.0
    for target in targets:
        alpha = float(target["alpha"])
        for estimate in target["estimates"]:
            key = (alpha, tuple(str(v) for v in estimate["group"]))
            values = np.asarray(boot_values.get(key, ()), dtype=float)
            values = values[np.isfinite(values)]
            if values.size == 0:
                continue
            estimate["stderr"] = float(np.std(values, ddof=1)) if values.size > 1 else 0.0
            estimate["ci_low"] = float(np.quantile(values, alpha_tail))
            estimate["ci_high"] = float(np.quantile(values, 1.0 - alpha_tail))


def _cdf_grid_and_weights(
    y: np.ndarray,
    weights: np.ndarray,
    *,
    grid_size: int,
    weight: str,
    tail_alpha: float,
) -> tuple[np.ndarray, np.ndarray, str]:
    m = int(max(8, min(grid_size, max(8, y.shape[0]))))
    if weight in {"crps", "dt", "cdf_dt"}:
        grid = np.linspace(float(np.min(y)), float(np.max(y)), m)
        if grid.size == 1:
            grid_weights = np.ones(1, dtype=float)
        else:
            widths = np.diff(grid)
            grid_weights = np.empty_like(grid)
            grid_weights[0] = widths[0] / 2.0
            grid_weights[-1] = widths[-1] / 2.0
            if grid.size > 2:
                grid_weights[1:-1] = (widths[:-1] + widths[1:]) / 2.0
        return grid, grid_weights, "dt"

    levels = np.linspace(0.0, 1.0, m)
    grid = np.asarray([_weighted_quantile(y, q, weights) for q in levels], dtype=float)
    grid = np.unique(grid)
    if grid.size == 0:
        raise ValueError("CDF grid is empty")
    grid_weights = np.ones(grid.shape[0], dtype=float) / float(grid.shape[0])
    if weight == "tail_cvm":
        cutoff = _weighted_quantile(y, tail_alpha, weights)
        mask = grid >= cutoff
        if not np.any(mask):
            mask[-1] = True
        grid = grid[mask]
        grid_weights = np.ones(grid.shape[0], dtype=float) / float(grid.shape[0])
        return grid, grid_weights, "upper_tail_dF"
    if weight == "lower_tail_cvm":
        cutoff = _weighted_quantile(y, tail_alpha, weights)
        mask = grid <= cutoff
        if not np.any(mask):
            mask[0] = True
        grid = grid[mask]
        grid_weights = np.ones(grid.shape[0], dtype=float) / float(grid.shape[0])
        return grid, grid_weights, "lower_tail_dF"
    return grid, grid_weights, "empirical_cdf"


def _cvm_group_estimate(
    X_group: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    *,
    grid: np.ndarray,
    grid_weights: np.ndarray,
    cv: int,
    n_bins: int,
    min_leaf: int,
    learner: str,
    random_seed: int | None,
) -> tuple[float, float, np.ndarray, str]:
    n = y.shape[0]
    folds = _fold_masks(n, cv, random_seed)
    all_indices = np.arange(n, dtype=int)
    unconditional = _weighted_ecdf(y, grid, weights)
    row_scores = np.zeros(n, dtype=float)
    coverage_matrix = np.zeros((n, grid.shape[0]), dtype=float)
    learners_used: set[str] = set()
    for fold in folds:
        train = np.setdiff1d(all_indices, fold, assume_unique=False)
        if train.size == 0:
            train = all_indices
        cdf_pred, learner_used = _predict_conditional_cdf(
            X_group[train],
            y[train],
            X_group[fold],
            grid=grid,
            weights_train=weights[train],
            n_bins=n_bins,
            min_leaf=min_leaf,
            learner=learner,
            random_seed=random_seed,
        )
        learners_used.add(learner_used)
        cdf_pred = np.maximum.accumulate(np.clip(cdf_pred, 0.0, 1.0), axis=1)
        indicator = (y[fold, None] <= grid[None, :]).astype(float)
        phi = 2.0 * cdf_pred * indicator - cdf_pred**2 - unconditional[None, :] ** 2
        row_scores[fold] = phi @ grid_weights
        coverage_matrix[fold, :] = cdf_pred
    numerator = _weighted_mean(row_scores, weights)
    denominator = float(np.sum(unconditional * (1.0 - unconditional) * grid_weights))
    raw = numerator / denominator if denominator > _EPS else float("nan")
    learner_used_label = "+".join(sorted(learners_used)) if learners_used else "unknown"
    return raw, denominator, coverage_matrix, learner_used_label


def _pawn_group_estimate(
    X_group: np.ndarray,
    y: np.ndarray,
    *,
    weights: np.ndarray,
    n_bins: int,
    min_leaf: int,
) -> tuple[float, dict[str, Any]]:
    thresholds = _thresholds_for_bins(X_group, n_bins)
    codes = _cell_codes(X_group, thresholds)
    by_cell = _cell_index_map(codes)
    ks_values: list[float] = []
    for indices in by_cell.values():
        if indices.size < min_leaf:
            continue
        conditional = np.sort(y[indices])
        all_values = np.unique(np.concatenate([y, conditional]))
        uncond_cdf = _weighted_ecdf(y, all_values, weights)
        cond_cdf = _weighted_ecdf(conditional, all_values, weights[indices])
        ks_values.append(float(np.max(np.abs(uncond_cdf - cond_cdf))))
    raw = float(np.median(ks_values)) if ks_values else 0.0
    diagnostics = {
        "ks_median": raw,
        "ks_max": float(np.max(ks_values)) if ks_values else 0.0,
        "effective_leaves": int(len(by_cell)),
        "usable_leaves": int(len(ks_values)),
    }
    return raw, diagnostics


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40.0, 40.0)))


def _fit_logistic_classifier(
    X: np.ndarray,
    z: np.ndarray,
    *,
    iterations: int,
    learning_rate: float,
    l2: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.mean(X, axis=0)
    scale = np.std(X, axis=0)
    scale = np.where(scale > _EPS, scale, 1.0)
    design = np.column_stack([np.ones(X.shape[0]), (X - mean) / scale])
    coef = np.zeros(design.shape[1], dtype=float)
    labels = z.astype(float)
    n = max(float(X.shape[0]), 1.0)
    for _ in range(int(max(1, iterations))):
        pred = _sigmoid(design @ coef)
        grad = (design.T @ (pred - labels)) / n
        grad[1:] += float(l2) * coef[1:]
        coef -= float(learning_rate) * grad
    return coef, mean, scale


def _predict_logistic_classifier(
    X: np.ndarray, coef: np.ndarray, mean: np.ndarray, scale: np.ndarray
) -> np.ndarray:
    design = np.column_stack([np.ones(X.shape[0]), (X - mean) / scale])
    return _sigmoid(design @ coef)


def _delta_tv_classifier_group(
    X_group: np.ndarray,
    y: np.ndarray,
    *,
    cv: int,
    random_seed: int | None,
    iterations: int,
    learning_rate: float,
    l2: float,
) -> tuple[float, dict[str, Any]]:
    rng = np.random.default_rng(random_seed)
    n = y.shape[0]
    permutation = rng.permutation(n)
    positive = np.column_stack([X_group, y])
    negative = np.column_stack([X_group, y[permutation]])
    features = np.vstack([positive, negative])
    labels = np.concatenate([np.ones(n, dtype=float), np.zeros(n, dtype=float)])
    folds = _fold_masks(features.shape[0], cv, random_seed)
    predictions = np.zeros(features.shape[0], dtype=float)
    all_indices = np.arange(features.shape[0], dtype=int)
    for fold in folds:
        train = np.setdiff1d(all_indices, fold, assume_unique=False)
        if train.size == 0:
            train = all_indices
        coef, mean, scale = _fit_logistic_classifier(
            features[train],
            labels[train],
            iterations=iterations,
            learning_rate=learning_rate,
            l2=l2,
        )
        predictions[fold] = _predict_logistic_classifier(features[fold], coef, mean, scale)
    raw = float(np.mean(np.abs(2.0 * predictions - 1.0)))
    diagnostics = {
        "tv_method": "classifier",
        "learner": "logistic_classifier",
        "mean_positive_score": float(np.mean(predictions[:n])),
        "mean_product_score": float(np.mean(predictions[n:])),
        "classifier_iterations": int(iterations),
    }
    return raw, diagnostics


def _delta_tv_density_group(
    X_group: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    *,
    grid: np.ndarray,
    cv: int,
    n_bins: int,
    min_leaf: int,
    random_seed: int | None,
    bandwidth: float | None,
) -> tuple[float, dict[str, Any]]:
    n = y.shape[0]
    folds = _fold_masks(n, cv, random_seed)
    all_indices = np.arange(n, dtype=int)
    bw = _silverman_bandwidth(y, weights) if bandwidth is None else float(bandwidth)
    row_integrals = np.zeros(n, dtype=float)
    unconditional_full = _kde_pdf(y, grid, weights=weights, bandwidth=bw)
    for fold in folds:
        train = np.setdiff1d(all_indices, fold, assume_unique=False)
        if train.size == 0:
            train = all_indices
        unconditional = _kde_pdf(y[train], grid, weights=weights[train], bandwidth=bw)
        conditional = _predict_binned_density(
            X_group[train],
            y[train],
            X_group[fold],
            grid=grid,
            weights_train=weights[train],
            n_bins=n_bins,
            min_leaf=min_leaf,
            bandwidth=bw,
        )
        row_integrals[fold] = np.trapezoid(
            np.abs(conditional - unconditional[None, :]), grid, axis=1
        )
    raw = 0.5 * _weighted_mean(row_integrals, weights)
    diagnostics = {
        "tv_method": "density",
        "learner": "binned_conditional_kde",
        "bandwidth": float(bw),
        "density_grid_size": int(grid.shape[0]),
        "unconditional_density_mass": float(np.trapezoid(unconditional_full, grid)),
    }
    return raw, diagnostics


def analyze_distribution(
    *,
    problem: Mapping[str, Any] | None,
    X: Any,
    Y: Any,
    metrics: Sequence[str] = ("cvm", "tail_cvm", "pawn", "delta_tv"),
    groups: Any = "first_order",
    cdf_learner: str = "cdf_bins",
    tv_method: str = "classifier",
    tail_alpha: float = 0.95,
    grid_size: int = 1024,
    cv: int = 5,
    n_boot: int = 0,
    sample_weight: Any = None,
    n_bins: int = 8,
    min_leaf: int = 5,
    random_seed: int | None = 0,
    denominator_tol: float = 1.0e-10,
    ci_level: float = 0.95,
    classifier_iterations: int = 200,
    classifier_learning_rate: float = 0.1,
    classifier_l2: float = 1.0e-3,
    density_grid_size: int | None = None,
    density_bandwidth: float | None = None,
    include_dummy: bool = True,
) -> dict[str, Any]:
    """Estimate weighted-CDF/CVM, PAWN, and Delta-TV indices."""
    inputs, outputs = _coerce_xy(X, Y)
    weights = _coerce_weights(sample_weight, outputs.shape[0])
    names = _problem_names(problem, inputs.shape[1])
    parsed_groups = _parse_groups(groups, names)
    normalized_metrics = [str(metric).lower() for metric in metrics]
    results: list[dict[str, Any]] = []
    n = outputs.shape[0]
    rng = np.random.default_rng(random_seed)

    for metric in normalized_metrics:
        if metric in {"cvm", "tail_cvm", "lower_tail_cvm", "crps", "dt", "cdf_dt"}:
            weight_name = "tail_cvm" if metric == "tail_cvm" else metric
            grid, grid_weights, weight_label = _cdf_grid_and_weights(
                outputs,
                weights,
                grid_size=grid_size,
                weight=weight_name,
                tail_alpha=float(tail_alpha),
            )
            estimates: list[dict[str, Any]] = []
            dummy_raw: float | None = None
            if include_dummy:
                dummy_raw, _, _, dummy_learner_used = _cvm_group_estimate(
                    rng.normal(size=(n, 1)),
                    outputs,
                    weights,
                    grid=grid,
                    grid_weights=grid_weights,
                    cv=cv,
                    n_bins=n_bins,
                    min_leaf=min_leaf,
                    learner=cdf_learner,
                    random_seed=None if random_seed is None else int(random_seed) + 997,
                )
            for indices, labels in parsed_groups:
                raw, denominator, cdf_pred, learner_used = _cvm_group_estimate(
                    inputs[:, indices],
                    outputs,
                    weights,
                    grid=grid,
                    grid_weights=grid_weights,
                    cv=cv,
                    n_bins=n_bins,
                    min_leaf=min_leaf,
                    learner=cdf_learner,
                    random_seed=random_seed,
                )
                diagnostics = {
                    "denominator": float(denominator),
                    "denominator_status": "ok" if denominator > denominator_tol else "near_zero",
                    "grid_size": int(grid.shape[0]),
                    "weight": weight_label,
                    "learner": learner_used,
                    "learner_requested": cdf_learner,
                    "dummy_learner": dummy_learner_used if include_dummy else None,
                    "monotonicity_enforced": True,
                    "null_dummy_index": dummy_raw,
                    "index_clipped": bool(raw < 0.0 or raw > 1.0),
                    "raw_estimate": float(raw),
                    "cdf_prediction_min": float(np.min(cdf_pred)),
                    "cdf_prediction_max": float(np.max(cdf_pred)),
                }
                diagnostics.update(
                    _tail_diagnostics(
                        inputs[:, indices],
                        outputs,
                        weights,
                        alpha=float(tail_alpha),
                        n_bins=n_bins,
                    )
                )
                method_name = "tail_cvm_orthogonal" if metric == "tail_cvm" else "cvm_orthogonal"
                if metric in {"crps", "dt", "cdf_dt"}:
                    method_name = "cdf_distance_orthogonal"
                estimates.append(
                    {
                        "group": labels,
                        "estimate": float(np.clip(raw, 0.0, 1.0)),
                        "raw_estimate": float(raw),
                        "stderr": None,
                        "ci_low": None,
                        "ci_high": None,
                        "effective_n": int(n),
                        "convergence_rate": "n^-1/2 + n^(-2*beta/(2*beta+s))",
                        "sample_size_planner": {
                            "epsilon_0_05_beta_1": sample_size_qosa_cvm(
                                0.05,
                                0.05,
                                len(parsed_groups),
                                len(indices),
                            )
                        },
                        "diagnostics": diagnostics,
                    }
                )
            results.append(
                {
                    "method": method_name,
                    "target": {
                        "metric": metric,
                        "tail": "upper" if metric == "tail_cvm" else None,
                        "alpha": float(tail_alpha) if "tail" in metric else None,
                        "weight": weight_label,
                    },
                    "estimates": estimates,
                }
            )
        elif metric == "pawn":
            estimates = []
            dummy_raw = None
            if include_dummy:
                dummy_raw, _ = _pawn_group_estimate(
                    rng.normal(size=(n, 1)),
                    outputs,
                    weights=weights,
                    n_bins=n_bins,
                    min_leaf=min_leaf,
                )
            for indices, labels in parsed_groups:
                raw, diagnostics = _pawn_group_estimate(
                    inputs[:, indices],
                    outputs,
                    weights=weights,
                    n_bins=n_bins,
                    min_leaf=min_leaf,
                )
                diagnostics.update(
                    _tail_diagnostics(
                        inputs[:, indices],
                        outputs,
                        weights,
                        alpha=float(tail_alpha),
                        n_bins=n_bins,
                    )
                )
                estimates.append(
                    {
                        "group": labels,
                        "estimate": float(np.clip(raw, 0.0, 1.0)),
                        "raw_estimate": float(raw),
                        "stderr": None,
                        "ci_low": None,
                        "ci_high": None,
                        "effective_n": int(n),
                        "convergence_rate": "n^(-beta/(2*beta+s))",
                        "diagnostics": diagnostics
                        | {"index_clipped": False, "null_dummy_index": dummy_raw},
                    }
                )
            results.append(
                {
                    "method": "pawn_ks",
                    "target": {"metric": "pawn", "summary": "median_ks"},
                    "estimates": estimates,
                }
            )
        elif metric == "delta_tv":
            if tv_method not in {"auto", "classifier", "density"}:
                raise ValueError("tv_method must be one of: auto, classifier, density")
            estimates = []
            result_method_name = f"delta_tv_{tv_method}"
            density_grid_count = int(density_grid_size or grid_size)
            density_bw = (
                _silverman_bandwidth(outputs, weights)
                if density_bandwidth is None
                else float(density_bandwidth)
            )
            density_grid = np.linspace(
                float(np.min(outputs) - 3.0 * density_bw),
                float(np.max(outputs) + 3.0 * density_bw),
                int(max(32, density_grid_count)),
            )
            for indices, labels in parsed_groups:
                resolved_tv_method = (
                    "density" if tv_method == "auto" and len(indices) <= 2 else tv_method
                )
                if resolved_tv_method == "density":
                    raw, diagnostics = _delta_tv_density_group(
                        inputs[:, indices],
                        outputs,
                        weights,
                        grid=density_grid,
                        cv=cv,
                        n_bins=n_bins,
                        min_leaf=min_leaf,
                        random_seed=random_seed,
                        bandwidth=density_bw,
                    )
                    convergence_rate = "n^-1/2 + n^(-beta/(2*beta+s+1))"
                else:
                    raw, diagnostics = _delta_tv_classifier_group(
                        inputs[:, indices],
                        outputs,
                        cv=cv,
                        random_seed=random_seed,
                        iterations=classifier_iterations,
                        learning_rate=classifier_learning_rate,
                        l2=classifier_l2,
                    )
                    convergence_rate = "n^-1/2 + r_eta,n"
                dummy_raw = None
                if include_dummy:
                    if resolved_tv_method == "density":
                        dummy_raw, _ = _delta_tv_density_group(
                            rng.normal(size=(n, 1)),
                            outputs,
                            weights,
                            grid=density_grid,
                            cv=cv,
                            n_bins=n_bins,
                            min_leaf=min_leaf,
                            random_seed=None
                            if random_seed is None
                            else int(random_seed) + 1009 + len(indices),
                            bandwidth=density_bw,
                        )
                    else:
                        dummy_raw, _ = _delta_tv_classifier_group(
                            rng.normal(size=(n, 1)),
                            outputs,
                            cv=cv,
                            random_seed=None
                            if random_seed is None
                            else int(random_seed) + 1009 + len(indices),
                            iterations=classifier_iterations,
                            learning_rate=classifier_learning_rate,
                            l2=classifier_l2,
                        )
                diagnostics.update(
                    _tail_diagnostics(
                        inputs[:, indices],
                        outputs,
                        weights,
                        alpha=float(tail_alpha),
                        n_bins=n_bins,
                    )
                )
                estimates.append(
                    {
                        "group": labels,
                        "estimate": float(np.clip(raw, 0.0, 1.0)),
                        "raw_estimate": float(raw),
                        "stderr": None,
                        "ci_low": None,
                        "ci_high": None,
                        "effective_n": int(n),
                        "convergence_rate": convergence_rate,
                        "sample_size_planner": {
                            "density_epsilon_0_05_beta_1": sample_size_delta_tv(
                                0.05,
                                0.05,
                                len(parsed_groups),
                                len(indices),
                            )
                        },
                        "diagnostics": diagnostics
                        | {"index_clipped": False, "null_dummy_index": dummy_raw},
                    }
                )
            results.append(
                {
                    "method": result_method_name,
                    "target": {"metric": "delta_tv", "tv_method": tv_method},
                    "estimates": estimates,
                }
            )
        else:
            raise ValueError(f"unknown distributional sensitivity metric: {metric}")

    if n_boot > 0:
        _attach_distribution_bootstrap(
            results,
            problem=problem,
            X=inputs,
            Y=outputs,
            weights=weights if sample_weight is not None else None,
            metrics=tuple(normalized_metrics),
            groups=groups,
            cdf_learner=cdf_learner,
            tv_method=tv_method,
            tail_alpha=tail_alpha,
            grid_size=grid_size,
            cv=cv,
            n_boot=int(n_boot),
            n_bins=n_bins,
            min_leaf=min_leaf,
            random_seed=random_seed,
            denominator_tol=denominator_tol,
            ci_level=ci_level,
            classifier_iterations=classifier_iterations,
            classifier_learning_rate=classifier_learning_rate,
            classifier_l2=classifier_l2,
            density_grid_size=density_grid_size,
            density_bandwidth=density_bandwidth,
        )

    return {
        "method": "quantile_distributional_sensitivity",
        "target_family": "distribution",
        "results": results,
        "diagnostics": {
            "n_samples": int(n),
            "n_features": int(inputs.shape[1]),
            "n_groups": int(len(parsed_groups)),
            "cv": int(max(1, min(cv, n))),
            "n_boot": int(n_boot),
            "tv_method": tv_method,
            "index_clipping": "raw_estimate retained; estimate is clipped to [0, 1]",
        },
    }


def _attach_distribution_bootstrap(
    results: list[dict[str, Any]],
    *,
    problem: Mapping[str, Any] | None,
    X: np.ndarray,
    Y: np.ndarray,
    weights: np.ndarray | None,
    metrics: Sequence[str],
    groups: Any,
    cdf_learner: str,
    tv_method: str,
    tail_alpha: float,
    grid_size: int,
    cv: int,
    n_boot: int,
    n_bins: int,
    min_leaf: int,
    random_seed: int | None,
    denominator_tol: float,
    ci_level: float,
    classifier_iterations: int,
    classifier_learning_rate: float,
    classifier_l2: float,
    density_grid_size: int | None,
    density_bandwidth: float | None,
) -> None:
    rng = np.random.default_rng(random_seed)
    n = Y.shape[0]
    boot_values: dict[tuple[str, tuple[str, ...]], list[float]] = {}
    for boot_idx in range(n_boot):
        rows = rng.integers(0, n, size=n)
        boot = analyze_distribution(
            problem=problem,
            X=X[rows],
            Y=Y[rows],
            metrics=metrics,
            groups=groups,
            cdf_learner=cdf_learner,
            tv_method=tv_method,
            tail_alpha=tail_alpha,
            grid_size=grid_size,
            cv=cv,
            n_boot=0,
            sample_weight=None if weights is None else weights[rows],
            n_bins=n_bins,
            min_leaf=min_leaf,
            random_seed=None if random_seed is None else int(random_seed) + boot_idx + 1,
            denominator_tol=denominator_tol,
            classifier_iterations=classifier_iterations,
            classifier_learning_rate=classifier_learning_rate,
            classifier_l2=classifier_l2,
            density_grid_size=density_grid_size,
            density_bandwidth=density_bandwidth,
            include_dummy=False,
        )
        for result in boot["results"]:
            method = str(result["method"])
            for estimate in result["estimates"]:
                key = (method, tuple(str(v) for v in estimate["group"]))
                boot_values.setdefault(key, []).append(float(estimate["raw_estimate"]))

    alpha_tail = (1.0 - float(ci_level)) / 2.0
    for result in results:
        method = str(result["method"])
        for estimate in result["estimates"]:
            key = (method, tuple(str(v) for v in estimate["group"]))
            values = np.asarray(boot_values.get(key, ()), dtype=float)
            values = values[np.isfinite(values)]
            if values.size == 0:
                continue
            estimate["stderr"] = float(np.std(values, ddof=1)) if values.size > 1 else 0.0
            estimate["ci_low"] = float(np.quantile(values, alpha_tail))
            estimate["ci_high"] = float(np.quantile(values, 1.0 - alpha_tail))


def _state_xy(state: Mapping[str, Any]) -> tuple[Any, Any]:
    if "inputs_matrix" in state:
        x_value = state["inputs_matrix"]
    else:
        x_value = state.get("X")
    if "outputs" in state:
        y_value = state["outputs"]
    else:
        y_value = state.get("Y")
    if x_value is None or y_value is None:
        raise ValueError("state must contain inputs_matrix/outputs or X/Y")
    return x_value, y_value


@foundry_method(
    namespace="sensitivity.distributional",
    version="1.0.0",
    tags={"sensitivity", "qosa", "quantile", "distributional", "tabular"},
)
class QOSAPinballSensitivityEstimator:
    """Estimate cross-fitted quantile-oriented sensitivity indices."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="qosa_pinball",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "inputs_matrix",
                    SlotType.MATRIX,
                    Unit("parameter", "value"),
                    shape=("n_samples", "n_factors"),
                ),
                SlotSpec(
                    "outputs",
                    SlotType.VECTOR,
                    Unit("response", "value"),
                    shape=("n_samples",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="alphas", default=(0.5, 0.95)),
            ParameterSpec(name="groups", default="first_order"),
            ParameterSpec(name="learner", default="quantile_bins"),
            ParameterSpec(name="cv", default=5),
            ParameterSpec(name="n_boot", default=0),
            ParameterSpec(name="n_bins", default=8),
            ParameterSpec(name="min_leaf", default=5),
            ParameterSpec(name="random_seed", default=0),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Cross-fitted QOSA-pinball indices for median and tail quantile sensitivity.",
        tags=frozenset({"sensitivity", "qosa", "quantile", "pinball", "tabular"}),
        citations=(
            "Fort, J.-C., Klein, T. & Rachdi, N. (2013). New sensitivity analysis subordinated to a contrast.",
            "Maume-Deschamps, V. & Niang, I. (2021). Quantile-oriented sensitivity analysis.",
        ),
        equations={"qosa": "S_u,alpha = (H_0,alpha - H_u,alpha) / H_0,alpha"},
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use="Median, percentile, or tail-risk sensitivity for simulation outputs where variance is not the policy target",
        when_not_to_use="Only variance decomposition is needed; use Sobol for variance-first global sensitivity",
        output_interpretation="Index near 1 means conditioning on the input group greatly reduces quantile pinball loss; raw estimates are retained before clipping.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X, Y = _state_xy(state)
        problem = state.get("problem") if isinstance(state, Mapping) else None
        result = analyze_quantile(
            problem=problem,
            X=X,
            Y=Y,
            alphas=tuple(params.get("alphas", (0.5, 0.95))),
            groups=params.get("groups", "first_order"),
            learner=str(params.get("learner", "quantile_bins")),
            cv=int(params.get("cv", 5)),
            n_boot=int(params.get("n_boot", 0)),
            sample_weight=state.get("sample_weight"),
            n_bins=int(params.get("n_bins", 8)),
            min_leaf=int(params.get("min_leaf", 5)),
            random_seed=params.get("random_seed", 0),
        )
        return {"result": result}


@foundry_method(
    namespace="sensitivity.distributional",
    version="1.0.0",
    tags={"sensitivity", "cdf", "cvm", "pawn", "delta-tv", "distributional", "tabular"},
)
class DistributionalSensitivityEstimator:
    """Estimate CDF/CVM, PAWN, and classifier Delta-TV sensitivity indices."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="distributional_indices",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "inputs_matrix",
                    SlotType.MATRIX,
                    Unit("parameter", "value"),
                    shape=("n_samples", "n_factors"),
                ),
                SlotSpec(
                    "outputs",
                    SlotType.VECTOR,
                    Unit("response", "value"),
                    shape=("n_samples",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="metrics", default=("cvm", "tail_cvm", "pawn", "delta_tv")),
            ParameterSpec(name="groups", default="first_order"),
            ParameterSpec(name="cdf_learner", default="cdf_bins"),
            ParameterSpec(name="tv_method", default="classifier"),
            ParameterSpec(name="tail_alpha", default=0.95),
            ParameterSpec(name="grid_size", default=1024),
            ParameterSpec(name="cv", default=5),
            ParameterSpec(name="n_boot", default=0),
            ParameterSpec(name="n_bins", default=8),
            ParameterSpec(name="min_leaf", default=5),
            ParameterSpec(name="random_seed", default=0),
            ParameterSpec(name="density_grid_size", default=None),
            ParameterSpec(name="density_bandwidth", default=None),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Cross-fitted distributional sensitivity indices: orthogonal CVM/tail-CVM, PAWN, and density/classifier Delta-TV.",
        tags=frozenset({"sensitivity", "distributional", "cdf", "cvm", "pawn", "delta-tv"}),
        citations=(
            "Borgonovo, E. (2007). A new uncertainty importance measure.",
            "Pianosi, F. & Wagener, T. (2015). PAWN sensitivity analysis.",
        ),
        equations={
            "cvm": "S_u,w = E[int (F_u(t|X_u)-F(t))^2 w(dt)] / int F(t)(1-F(t)) w(dt)",
            "delta_tv_classifier": "delta_u = E_m |2 eta_u(X_u,Y)-1|",
            "delta_tv_density": "delta_u = 0.5 E_X int |f(Y|X)-f(Y)| dy",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use="Whole-distribution, tail-shape, or moment-independent sensitivity when means and variances hide policy risk",
        when_not_to_use="Need only variance attribution or a small deterministic Sobol design is already available",
        output_interpretation="CVM/tail-CVM report squared CDF information gain; PAWN reports median KS shift; Delta-TV reports density or classifier total-variation dependence.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X, Y = _state_xy(state)
        problem = state.get("problem") if isinstance(state, Mapping) else None
        result = analyze_distribution(
            problem=problem,
            X=X,
            Y=Y,
            metrics=tuple(params.get("metrics", ("cvm", "tail_cvm", "pawn", "delta_tv"))),
            groups=params.get("groups", "first_order"),
            cdf_learner=str(params.get("cdf_learner", "cdf_bins")),
            tv_method=str(params.get("tv_method", "classifier")),
            tail_alpha=float(params.get("tail_alpha", 0.95)),
            grid_size=int(params.get("grid_size", 1024)),
            cv=int(params.get("cv", 5)),
            n_boot=int(params.get("n_boot", 0)),
            sample_weight=state.get("sample_weight"),
            n_bins=int(params.get("n_bins", 8)),
            min_leaf=int(params.get("min_leaf", 5)),
            random_seed=params.get("random_seed", 0),
            density_grid_size=params.get("density_grid_size"),
            density_bandwidth=params.get("density_bandwidth"),
        )
        return {"result": result}


__all__ = [
    "DistributionalSensitivityEstimator",
    "QOSAPinballSensitivityEstimator",
    "analyze_distribution",
    "analyze_quantile",
    "sample_size_delta_tv",
    "sample_size_qosa_cvm",
]
