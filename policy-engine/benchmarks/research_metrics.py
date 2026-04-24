"""Shared research-oriented benchmark metrics and diagnostics helpers."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import numpy as np


def finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except Exception:
        return None
    return numeric if math.isfinite(numeric) else None


def mean_or_nan(values: Iterable[Any]) -> float:
    samples = [value for value in (finite_float(item) for item in values) if value is not None]
    return float(np.mean(samples)) if samples else float("nan")


def rate_or_nan(values: Iterable[bool]) -> float:
    samples = [bool(item) for item in values]
    return float(np.mean(samples)) if samples else float("nan")


def overlap_ntv_proxy(propensity: Sequence[float] | np.ndarray) -> float:
    """Normalized total variation proxy from propensity concentration.

    0.0 means near-perfect overlap, 1.0 means severe propensity concentration.
    """
    arr = np.asarray(propensity, dtype=float).reshape(-1)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan")
    centered = np.abs(arr - 0.5) / 0.5
    return float(np.clip(np.mean(centered), 0.0, 1.0))


def eceth(
    cate_true: Sequence[float] | np.ndarray,
    cate_pred: Sequence[float] | np.ndarray,
    *,
    n_bins: int = 10,
) -> float:
    """Expected calibration error for treatment heterogeneity."""
    truth = np.asarray(cate_true, dtype=float).reshape(-1)
    pred = np.asarray(cate_pred, dtype=float).reshape(-1)
    if truth.size == 0 or pred.size == 0 or truth.size != pred.size:
        return float("nan")
    if not np.isfinite(truth).all() or not np.isfinite(pred).all():
        return float("nan")
    if truth.size < 4 or np.allclose(pred, pred[0]):
        return float(abs(float(np.mean(pred) - np.mean(truth))))

    quantiles = np.linspace(0.0, 1.0, n_bins + 1)
    edges = np.quantile(pred, quantiles)
    edges[0] = -np.inf
    edges[-1] = np.inf

    total = float(pred.size)
    error = 0.0
    for idx in range(n_bins):
        left = edges[idx]
        right = edges[idx + 1]
        if idx == n_bins - 1:
            mask = pred >= left
        else:
            mask = (pred >= left) & (pred < right)
        if not np.any(mask):
            continue
        error += (float(np.sum(mask)) / total) * abs(
            float(np.mean(pred[mask])) - float(np.mean(truth[mask]))
        )
    return float(error)


def rank_weighted_ate(
    cate_true: Sequence[float] | np.ndarray,
    cate_pred: Sequence[float] | np.ndarray,
) -> float:
    """RATE-style prioritization score from rank-weighted true effects."""
    truth = np.asarray(cate_true, dtype=float).reshape(-1)
    pred = np.asarray(cate_pred, dtype=float).reshape(-1)
    if truth.size == 0 or pred.size == 0 or truth.size != pred.size:
        return float("nan")
    order = np.argsort(-pred, kind="mergesort")
    ranked_truth = truth[order]
    weights = np.linspace(1.0, 0.0, ranked_truth.size, endpoint=False)
    total = float(np.sum(weights))
    if total <= 0:
        return float("nan")
    weighted = float(np.sum(weights * ranked_truth) / total)
    return weighted - float(np.mean(truth))


def policy_value_top_q(
    cate_true: Sequence[float] | np.ndarray,
    cate_pred: Sequence[float] | np.ndarray,
    *,
    q: float = 0.25,
) -> float:
    truth = np.asarray(cate_true, dtype=float).reshape(-1)
    pred = np.asarray(cate_pred, dtype=float).reshape(-1)
    if truth.size == 0 or pred.size == 0 or truth.size != pred.size:
        return float("nan")
    k = max(1, int(math.ceil(truth.size * float(q))))
    top_idx = np.argsort(-pred, kind="mergesort")[:k]
    return float(np.mean(truth[top_idx]))


def r_risk(
    y: Sequence[float] | np.ndarray,
    treatment: Sequence[float] | np.ndarray,
    outcome_main: Sequence[float] | np.ndarray,
    propensity: Sequence[float] | np.ndarray,
    cate_pred: Sequence[float] | np.ndarray,
) -> float:
    y_arr = np.asarray(y, dtype=float).reshape(-1)
    t_arr = np.asarray(treatment, dtype=float).reshape(-1)
    m_arr = np.asarray(outcome_main, dtype=float).reshape(-1)
    e_arr = np.asarray(propensity, dtype=float).reshape(-1)
    tau_arr = np.asarray(cate_pred, dtype=float).reshape(-1)
    if not (y_arr.size and y_arr.size == t_arr.size == m_arr.size == e_arr.size == tau_arr.size):
        return float("nan")
    residual = y_arr - m_arr - tau_arr * (t_arr - e_arr)
    weight = np.square(t_arr - e_arr)
    if not np.isfinite(residual).all() or not np.isfinite(weight).all():
        return float("nan")
    return float(np.mean(weight * np.square(residual)))


def feature_importance_stability(
    importance_vectors: Sequence[Sequence[float] | np.ndarray],
    *,
    top_k: int = 5,
) -> float:
    vectors = []
    for value in importance_vectors:
        arr = np.asarray(value, dtype=float).reshape(-1)
        if arr.size == 0 or not np.isfinite(arr).all() or float(np.sum(np.abs(arr))) <= 1e-12:
            continue
        vectors.append(arr / max(float(np.sum(np.abs(arr))), 1e-12))
    if len(vectors) < 2:
        return float("nan")

    k = max(1, min(top_k, min(arr.size for arr in vectors)))
    overlaps: list[float] = []
    for idx, left in enumerate(vectors):
        left_top = set(np.argsort(-left)[:k].tolist())
        for right in vectors[idx + 1 :]:
            right_top = set(np.argsort(-right)[:k].tolist())
            union = left_top | right_top
            overlaps.append(len(left_top & right_top) / max(len(union), 1))
    return float(np.mean(overlaps)) if overlaps else float("nan")


def summarize_selection_manifest(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        return {}

    selected_propensity = Counter()
    selected_outcome = Counter()
    selection_objectives = Counter()
    calibration_modes = Counter()
    candidate_propensity: set[str] = set()
    candidate_outcome: set[str] = set()
    split_policies = Counter()

    total_records = 0
    for record in records:
        if not isinstance(record, Mapping):
            continue
        total_records += _record_count(record)
        selected_prop = record.get("selected_propensity_backend")
        selected_out = record.get("selected_outcome_backend")
        if selected_prop:
            selected_propensity[str(selected_prop)] += _record_count(record)
        else:
            selected_propensity.update(
                _counter_from_mapping(record.get("selected_propensity_backends"))
            )
        if selected_out:
            selected_outcome[str(selected_out)] += _record_count(record)
        else:
            selected_outcome.update(_counter_from_mapping(record.get("selected_outcome_backends")))
        objective = record.get("selection_objective")
        if objective:
            selection_objectives[str(objective)] += _record_count(record)
        else:
            selection_objectives.update(_counter_from_mapping(record.get("selection_objectives")))
        split_policy = record.get("split_policy")
        if split_policy:
            split_policies[str(split_policy)] += _record_count(record)
        else:
            split_policies.update(_counter_from_mapping(record.get("split_policies")))
        for value in record.get("tested_propensity_backends", []) or []:
            candidate_propensity.add(str(value))
        for value in record.get("tested_outcome_backends", []) or []:
            candidate_outcome.add(str(value))
        calibration_field = record.get("calibration_modes", [])
        if isinstance(calibration_field, Mapping):
            calibration_modes.update(_counter_from_mapping(calibration_field))
        else:
            for value in calibration_field or []:
                calibration_modes[str(value)] += 1

    return {
        "n_records": int(total_records or len(records)),
        "selection_objectives": dict(selection_objectives),
        "split_policies": dict(split_policies),
        "tested_propensity_backends": sorted(candidate_propensity),
        "tested_outcome_backends": sorted(candidate_outcome),
        "selected_propensity_backends": dict(selected_propensity),
        "selected_outcome_backends": dict(selected_outcome),
        "calibration_modes": dict(calibration_modes),
    }


def summarize_overlap_diagnostics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        return {}
    weights = [_record_count(record) for record in records]
    return {
        "effective_sample_size_mean": weighted_mean_or_nan(
            (_record_metric(record, "effective_sample_size") for record in records),
            weights=weights,
        ),
        "overlap_ntv_mean": weighted_mean_or_nan(
            (_record_metric(record, "overlap_ntv") for record in records),
            weights=weights,
        ),
        "clipping_fraction_mean": weighted_mean_or_nan(
            (_record_metric(record, "clipping_fraction") for record in records),
            weights=weights,
        ),
        "support_mismatch_fraction_mean": weighted_mean_or_nan(
            (_record_metric(record, "support_mismatch_fraction") for record in records),
            weights=weights,
        ),
        "coverage_guard_trigger_rate": weighted_mean_or_nan(
            (
                _record_metric(record, "coverage_guard_triggered", coerce_bool=True)
                for record in records
            ),
            weights=weights,
        ),
        "n_records": int(sum(weights)),
    }


def summarize_calibration_metrics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        return {}
    weights = [_record_count(record) for record in records]
    modes = Counter()
    for record in records:
        calibration_mode = record.get("calibration_mode")
        if calibration_mode:
            modes[str(calibration_mode)] += _record_count(record)
        modes.update(_counter_from_mapping(record.get("calibration_mode_counts")))
    return {
        "ci_coverage_mean": weighted_mean_or_nan(
            (_record_metric(record, "ci_coverage") for record in records),
            weights=weights,
        ),
        "ci_width_mean": weighted_mean_or_nan(
            (_record_metric(record, "ci_width") for record in records),
            weights=weights,
        ),
        "eceth_mean": weighted_mean_or_nan(
            (_record_metric(record, "eceth") for record in records),
            weights=weights,
        ),
        "calibration_mode_counts": dict(modes),
        "n_records": int(sum(weights)),
    }


def summarize_prioritization_metrics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        return {}
    weights = [_record_count(record) for record in records]
    return {
        "r_risk_mean": weighted_mean_or_nan(
            (_record_metric(record, "r_risk") for record in records),
            weights=weights,
        ),
        "rate_mean": weighted_mean_or_nan(
            (_record_metric(record, "rate") for record in records),
            weights=weights,
        ),
        "policy_value_top_q_mean": weighted_mean_or_nan(
            (_record_metric(record, "policy_value_top_q") for record in records),
            weights=weights,
        ),
        "feature_importance_stability_mean": weighted_mean_or_nan(
            (_record_metric(record, "feature_importance_stability") for record in records),
            weights=weights,
        ),
        "n_records": int(sum(weights)),
    }


def summarize_method_records(
    report: Any,
    *,
    attribute: str,
    reducer: Callable[[Sequence[Mapping[str, Any]]], dict[str, Any]],
) -> dict[str, Any]:
    by_method: dict[str, list[Mapping[str, Any]]] = {}
    for case in getattr(report, "cases", []):
        payload = getattr(case, "result_payload", None)
        if not isinstance(payload, dict):
            continue
        for method_name, result in payload.items():
            record = getattr(result, attribute, None)
            if isinstance(record, Mapping) and record:
                by_method.setdefault(str(method_name), []).append(record)
    return {method_name: reducer(records) for method_name, records in by_method.items() if records}


def weighted_mean_or_nan(values: Iterable[Any], *, weights: Sequence[float] | None = None) -> float:
    samples = [finite_float(item) for item in values]
    if weights is None:
        return mean_or_nan(samples)
    weighted: list[tuple[float, float]] = []
    for value, weight in zip(samples, weights):
        if value is None:
            continue
        try:
            numeric_weight = float(weight)
        except Exception:
            continue
        if not math.isfinite(numeric_weight) or numeric_weight <= 0:
            continue
        weighted.append((value, numeric_weight))
    if not weighted:
        return float("nan")
    numerator = float(sum(value * weight for value, weight in weighted))
    denominator = float(sum(weight for _value, weight in weighted))
    return numerator / denominator if denominator > 0 else float("nan")


def basic_overlap_diagnostics(
    propensity: Sequence[float] | np.ndarray,
    treatment: Sequence[float] | np.ndarray,
    *,
    clip: float = 0.01,
    overlap_guard: float | None = None,
) -> dict[str, Any]:
    prop = np.asarray(propensity, dtype=float).reshape(-1)
    treat = np.asarray(treatment, dtype=float).reshape(-1)
    if prop.size == 0 or prop.size != treat.size:
        return {}
    prop = np.clip(prop, clip, 1.0 - clip)
    treated_weights = np.where(treat > 0.5, 1.0 / prop, 0.0)
    control_weights = np.where(treat <= 0.5, 1.0 / (1.0 - prop), 0.0)
    ess = 0.0
    for weights in (treated_weights, control_weights):
        total = float(np.sum(weights))
        denom = float(np.sum(np.square(weights)))
        if total > 0 and denom > 0:
            ess += (total * total) / denom
    ntv = overlap_ntv_proxy(prop)
    clipping_fraction = float(np.mean((prop <= clip + 1e-12) | (prop >= 1.0 - clip - 1e-12)))
    support_mismatch_fraction = float(np.mean((prop <= 0.05) | (prop >= 0.95)))
    guard_threshold = float(overlap_guard) if overlap_guard is not None else 0.10
    return {
        "effective_sample_size": ess,
        "overlap_ntv": ntv,
        "clipping_fraction": clipping_fraction,
        "support_mismatch_fraction": support_mismatch_fraction,
        "coverage_guard_triggered": bool(
            ntv > guard_threshold or support_mismatch_fraction > guard_threshold
        ),
    }


def fit_eval_propensity(X: np.ndarray, treatment: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    treatment = np.asarray(treatment, dtype=float).reshape(-1)
    if X.shape[0] != treatment.size or treatment.size == 0:
        return np.full(max(treatment.size, 1), 0.5, dtype=float)[: treatment.size]
    try:
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(max_iter=500, solver="lbfgs")
        model.fit(X, treatment)
        return np.clip(np.asarray(model.predict_proba(X)[:, 1], dtype=float), 0.02, 0.98)
    except Exception:
        from numpy.linalg import lstsq

        Xb = np.column_stack([X, np.ones(treatment.size)])
        coef, _, _, _ = lstsq(Xb, treatment, rcond=None)
        return np.clip(np.asarray(Xb @ coef, dtype=float), 0.02, 0.98)


def fit_eval_outcome_main(X: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    outcome = np.asarray(outcome, dtype=float).reshape(-1)
    if X.shape[0] != outcome.size or outcome.size == 0:
        return np.zeros(outcome.size, dtype=float)
    try:
        from sklearn.linear_model import Ridge

        model = Ridge(alpha=1.0)
        model.fit(X, outcome)
        return np.asarray(model.predict(X), dtype=float)
    except Exception:
        from numpy.linalg import lstsq

        Xb = np.column_stack([X, np.ones(outcome.size)])
        coef, _, _, _ = lstsq(Xb, outcome, rcond=None)
        return np.asarray(Xb @ coef, dtype=float)


def posthoc_cate_calibration(
    X: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    cate_raw: Sequence[float] | np.ndarray,
    *,
    seed: int,
    ate_anchor: float | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    raw = np.asarray(cate_raw, dtype=float).reshape(-1)
    X = np.asarray(X, dtype=float)
    treatment = np.asarray(treatment, dtype=float).reshape(-1)
    outcome = np.asarray(outcome, dtype=float).reshape(-1)
    if (
        raw.size == 0
        or raw.size != treatment.size
        or raw.size != outcome.size
        or X.shape[0] != raw.size
    ):
        return raw, {
            "calibration_mode": "identity",
            "split_policy": "invalid_shapes",
            "calibration_applied": False,
        }

    eval_propensity = fit_eval_propensity(X, treatment)
    eval_outcome_main = fit_eval_outcome_main(X, outcome)
    denominator = treatment - eval_propensity
    safe_denominator = np.where(
        np.abs(denominator) < 0.05, np.sign(denominator) * 0.05, denominator
    )
    safe_denominator = np.where(np.abs(safe_denominator) < 1e-8, 0.05, safe_denominator)
    pseudo_outcome = (outcome - eval_outcome_main) / safe_denominator
    weights = np.square(denominator)

    candidates: list[tuple[str, np.ndarray]] = [("identity", raw)]
    isotonic_pred = _crossfit_isotonic_against_pseudo(
        raw,
        pseudo_outcome,
        weights=weights,
        seed=seed,
    )
    if isotonic_pred is not None:
        candidates.append(("causal_isotonic", isotonic_pred))

    shrink_pred = _orthogonal_shrinkage_against_pseudo(
        raw,
        pseudo_outcome,
        weights=weights,
        ate_anchor=float(
            ate_anchor
            if ate_anchor is not None and math.isfinite(float(ate_anchor))
            else np.mean(raw)
        ),
    )
    if shrink_pred is not None:
        candidates.append(("orthogonal_shrinkage", shrink_pred))

    best_mode = "identity"
    best_pred = raw
    best_risk = float("inf")
    risks: dict[str, float] = {}
    for mode, candidate in candidates:
        risk = r_risk(outcome, treatment, eval_outcome_main, eval_propensity, candidate)
        risks[mode] = risk
        if math.isfinite(risk) and risk < best_risk - 1e-12:
            best_mode = mode
            best_pred = candidate
            best_risk = risk

    return np.asarray(best_pred, dtype=float), {
        "calibration_mode": best_mode,
        "split_policy": "crossfit_pseudo_outcome",
        "calibration_applied": best_mode != "identity",
        "candidate_r_risk": risks,
        "selected_r_risk": best_risk,
    }


def _record_metric(record: Mapping[str, Any], key: str, *, coerce_bool: bool = False) -> Any:
    value = record.get(key)
    if value is None:
        value = record.get(f"{key}_mean")
    if coerce_bool and value is not None:
        return 1.0 if bool(value) else 0.0
    return value


def _record_count(record: Mapping[str, Any]) -> int:
    value = record.get("n_records")
    try:
        numeric = int(value)
    except Exception:
        numeric = 1
    return max(1, numeric)


def _counter_from_mapping(value: Any) -> Counter[str]:
    counter: Counter[str] = Counter()
    if not isinstance(value, Mapping):
        return counter
    for key, count in value.items():
        try:
            numeric = int(count)
        except Exception:
            continue
        counter[str(key)] += numeric
    return counter


def _crossfit_isotonic_against_pseudo(
    raw: np.ndarray,
    pseudo_outcome: np.ndarray,
    *,
    weights: np.ndarray,
    seed: int,
) -> np.ndarray | None:
    if raw.size < 32 or np.unique(raw).size < 4:
        return None
    try:
        from sklearn.isotonic import IsotonicRegression
    except Exception:
        return None

    n_splits = 5 if raw.size >= 160 else 3
    rng = np.random.default_rng(seed)
    order = np.arange(raw.size)
    rng.shuffle(order)
    folds = [fold for fold in np.array_split(order, n_splits) if fold.size > 0]
    if len(folds) < 2:
        return None

    calibrated = np.array(raw, copy=True)
    any_fit = False
    for fold in folds:
        train_idx = np.setdiff1d(np.arange(raw.size), fold, assume_unique=False)
        if train_idx.size < 16 or np.unique(raw[train_idx]).size < 3:
            continue
        try:
            model = IsotonicRegression(out_of_bounds="clip")
            model.fit(raw[train_idx], pseudo_outcome[train_idx], sample_weight=weights[train_idx])
            calibrated[fold] = np.asarray(model.predict(raw[fold]), dtype=float)
            any_fit = True
        except Exception:
            continue
    return calibrated if any_fit else None


def _orthogonal_shrinkage_against_pseudo(
    raw: np.ndarray,
    pseudo_outcome: np.ndarray,
    *,
    weights: np.ndarray,
    ate_anchor: float,
) -> np.ndarray | None:
    if raw.size == 0:
        return None
    centered = raw - float(ate_anchor)
    alphas = np.linspace(0.0, 1.0, 9)
    best_pred = None
    best_loss = float("inf")
    for alpha in alphas:
        candidate = float(ate_anchor) + alpha * centered
        loss = float(np.mean(weights * np.square(pseudo_outcome - candidate)))
        if math.isfinite(loss) and loss < best_loss - 1e-12:
            best_loss = loss
            best_pred = candidate
    return np.asarray(best_pred, dtype=float) if best_pred is not None else None


__all__ = [
    "basic_overlap_diagnostics",
    "eceth",
    "feature_importance_stability",
    "finite_float",
    "fit_eval_outcome_main",
    "fit_eval_propensity",
    "mean_or_nan",
    "overlap_ntv_proxy",
    "posthoc_cate_calibration",
    "policy_value_top_q",
    "r_risk",
    "rank_weighted_ate",
    "summarize_calibration_metrics",
    "summarize_method_records",
    "summarize_overlap_diagnostics",
    "summarize_prioritization_metrics",
    "summarize_selection_manifest",
    "weighted_mean_or_nan",
]
