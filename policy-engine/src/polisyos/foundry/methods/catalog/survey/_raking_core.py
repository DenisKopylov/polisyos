"""Core helpers for survey IPF / raking diagnostics."""
from __future__ import annotations

import math
from collections import OrderedDict
from typing import Any, Mapping, Sequence

import numpy as np

try:
    from scipy.optimize import minimize

    _SCIPY_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency path
    minimize = None
    _SCIPY_AVAILABLE = False

from polisyos.ir.analytics.survey_raking import (
    SurveyRakingCategoryDiagnostic,
    SurveyRakingDiagnosticReport,
    SurveyRakingIteration,
)

_LOG_EPS = 1e-300
_DECISION_RANK = {"pass": 0, "warn": 1, "block": 2}


def _vector(values: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D vector")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _matrix(values: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D matrix")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _normalize_category_key(value: Any) -> str:
    if value is None:
        return "__missing__"
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        if not math.isfinite(numeric):
            return "__missing__"
        if numeric.is_integer():
            return str(int(numeric))
        return format(numeric, ".12g")
    if isinstance(value, (np.integer, int)):
        return str(int(value))
    return str(value)


def build_raking_design_from_feature_targets(
    *,
    base_weights: Sequence[float] | np.ndarray,
    features: Any,
    feature_names: Sequence[str] | None,
    raking_targets: Mapping[str, Any],
    target_mode: str = "auto",
    population_total: float | None = None,
) -> dict[str, Any]:
    """Build an IPF design matrix from categorical feature columns and target margins."""

    weights = _vector(base_weights, name="base_weights")
    feature_matrix = np.asarray(features)
    if feature_matrix.ndim == 1:
        feature_matrix = feature_matrix[:, None]
    if feature_matrix.ndim != 2:
        raise ValueError("features must be a 2D matrix")
    if feature_matrix.shape[0] != weights.shape[0]:
        raise ValueError("features row count must match base_weights length")
    if not isinstance(raking_targets, Mapping) or not raking_targets:
        raise ValueError("raking_targets must be a non-empty mapping")

    names = list(feature_names or [f"feature_{idx}" for idx in range(feature_matrix.shape[1])])
    if len(names) != feature_matrix.shape[1]:
        raise ValueError("feature_names length must match features columns")
    name_to_index = {str(name): idx for idx, name in enumerate(names)}
    total = float(np.sum(weights)) if population_total is None else float(population_total)
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("population_total must be positive")

    columns: list[np.ndarray] = []
    margin_ids: list[int] = []
    margin_labels: list[str] = []
    category_labels: list[str] = []
    scaled_target_totals: list[float] = []

    for margin_idx, (margin_name_raw, target_spec_raw) in enumerate(raking_targets.items()):
        margin_name = str(margin_name_raw)
        if margin_name not in name_to_index:
            raise ValueError(f"Unknown raking margin '{margin_name}'")
        target_spec = target_spec_raw if isinstance(target_spec_raw, Mapping) else {}
        targets_map = target_spec.get("targets") if isinstance(target_spec.get("targets"), Mapping) else target_spec_raw
        if not isinstance(targets_map, Mapping) or not targets_map:
            raise ValueError(f"Margin '{margin_name}' must define category targets")

        margin_mode = str(
            target_spec.get("mode", target_mode)
            if isinstance(target_spec, Mapping)
            else target_mode
        ).lower()
        target_keys = [_normalize_category_key(key) for key in targets_map]
        raw_values = _vector(list(targets_map.values()), name=f"{margin_name}_targets")
        values = raw_values.astype(float, copy=True)
        if margin_mode == "shares" or (
            margin_mode == "auto"
            and np.all(values >= 0.0)
            and abs(float(np.sum(values)) - 1.0) <= 1e-6
        ):
            values *= total
        elif margin_mode not in {"auto", "totals"}:
            raise ValueError(
                f"Unsupported target mode '{margin_mode}' for margin '{margin_name}'"
            )

        feature_column = feature_matrix[:, name_to_index[margin_name]]
        normalized_column = np.array(
            [_normalize_category_key(value) for value in feature_column],
            dtype=object,
        )
        coverage = np.zeros(weights.shape[0], dtype=int)
        for category_key, target_value in zip(target_keys, values.tolist(), strict=False):
            mask = (normalized_column == category_key).astype(float)
            coverage += mask.astype(int)
            columns.append(mask)
            margin_ids.append(margin_idx)
            margin_labels.append(margin_name)
            category_labels.append(category_key)
            scaled_target_totals.append(float(target_value))
        if np.any(coverage != 1):
            uncovered = int(np.sum(coverage == 0))
            duplicated = int(np.sum(coverage > 1))
            raise ValueError(
                f"Margin '{margin_name}' must map every observation to exactly one target "
                f"category; uncovered={uncovered}, duplicated={duplicated}"
            )

    category_matrix = np.column_stack(columns) if columns else np.zeros((weights.shape[0], 0))
    return {
        "base_weights": weights,
        "category_matrix": category_matrix,
        "target_totals": np.asarray(scaled_target_totals, dtype=float),
        "margin_ids": np.asarray(margin_ids, dtype=int),
        "margin_names_by_category": tuple(margin_labels),
        "category_labels": tuple(category_labels),
        "population_total": total,
    }


def run_raking_ipf(
    *,
    base_weights: Sequence[float] | np.ndarray,
    category_matrix: Any,
    target_totals: Sequence[float] | np.ndarray,
    margin_ids: Sequence[int] | np.ndarray | None = None,
    margin_names_by_category: Sequence[str] | None = None,
    category_labels: Sequence[str] | None = None,
    max_iterations: int = 100,
    exact_tolerance: float = 1e-6,
    warn_tolerance: float = 1e-4,
    logweight_tolerance: float = 1e-8,
    stagnation_window: int = 5,
    stagnation_min_improvement: float = 1.02,
    sparse_count_warn: int = 30,
    sparse_count_block: int = 10,
    sparse_share_warn: float = 0.01,
    sparse_share_block: float = 0.005,
) -> tuple[np.ndarray, SurveyRakingDiagnosticReport]:
    """Run grouped IPF and emit a typed convergence / positivity report."""

    weights = _vector(base_weights, name="base_weights")
    if np.any(weights <= 0.0):
        raise ValueError("base_weights must be strictly positive")
    design = _matrix(category_matrix, name="category_matrix")
    targets = _vector(target_totals, name="target_totals")
    if design.shape[0] != weights.shape[0]:
        raise ValueError("category_matrix rows must match base_weights length")
    if design.shape[1] != targets.shape[0]:
        raise ValueError("target_totals length must match category_matrix columns")
    if np.any(design < 0.0):
        raise ValueError("category_matrix must be non-negative")
    if np.any(targets < 0.0):
        raise ValueError("target_totals must be non-negative")

    n_obs = int(weights.shape[0])
    n_categories = int(design.shape[1])
    max_iterations = max(1, int(max_iterations))
    exact_tolerance = max(0.0, float(exact_tolerance))
    warn_tolerance = max(exact_tolerance, float(warn_tolerance))
    logweight_tolerance = max(0.0, float(logweight_tolerance))
    stagnation_window = max(2, int(stagnation_window))
    stagnation_min_improvement = max(1.0, float(stagnation_min_improvement))

    resolved_margin_ids = (
        np.arange(n_categories, dtype=int)
        if margin_ids is None
        else np.asarray(margin_ids, dtype=int).reshape(-1)
    )
    if resolved_margin_ids.shape[0] != n_categories:
        raise ValueError("margin_ids length must match category_matrix columns")

    margin_names = _resolve_margin_names(
        margin_ids=resolved_margin_ids,
        margin_names_by_category=margin_names_by_category,
        n_categories=n_categories,
    )
    category_names = _resolve_category_names(category_labels=category_labels, n_categories=n_categories)
    category_keys = tuple(
        f"{margin_names[idx]}={category_names[idx]}" for idx in range(n_categories)
    )
    reference_total, inconsistent_reason = _reference_population_total(
        targets=targets,
        margin_ids=resolved_margin_ids,
    )

    if inconsistent_reason is not None:
        inconsistent_categories = _category_diagnostics(
            base_weights=weights,
            final_weights=weights,
            design=design,
            targets=targets,
            reference_total=max(reference_total, 0.0),
            margin_names=margin_names,
            category_names=category_names,
            sparse_count_warn=sparse_count_warn,
            sparse_count_block=sparse_count_block,
            sparse_share_warn=sparse_share_warn,
            sparse_share_block=sparse_share_block,
        )
        report = _build_terminal_report(
            final_weights=weights,
            base_weights=weights,
            targets=targets,
            achieved=np.asarray(design.T @ weights, dtype=float),
            category_keys=category_keys,
            categories=inconsistent_categories,
            margin_names=margin_names,
            category_names=category_names,
            trace=(),
            stop_reason="inconsistent_targets",
            reference_total=max(reference_total, 0.0),
            blocking_reasons=(inconsistent_reason,),
            extra_warnings=(),
            explicit_recommendations=(
                "Target totals across margins are inconsistent; align all margins to the same population total before rerunning IPF.",
            ),
        )
        return weights.copy(), report

    categories_pre = _category_diagnostics(
        base_weights=weights,
        final_weights=weights,
        design=design,
        targets=targets,
        reference_total=reference_total,
        margin_names=margin_names,
        category_names=category_names,
        sparse_count_warn=sparse_count_warn,
        sparse_count_block=sparse_count_block,
        sparse_share_warn=sparse_share_warn,
        sparse_share_block=sparse_share_block,
    )
    structural_zero_count = sum(item.structural_zero for item in categories_pre)
    if structural_zero_count:
        report = _build_terminal_report(
            final_weights=weights,
            base_weights=weights,
            targets=targets,
            achieved=np.asarray(design.T @ weights, dtype=float),
            category_keys=category_keys,
            categories=categories_pre,
            margin_names=margin_names,
            category_names=category_names,
            trace=(),
            stop_reason="structural_zero",
            reference_total=reference_total,
            blocking_reasons=("structural_zero",),
            extra_warnings=(),
            explicit_recommendations=tuple(
                OrderedDict.fromkeys(
                    f"Category '{item.margin_name}={item.category_name}' has a positive target total but zero sample support."
                    for item in categories_pre
                    if item.structural_zero
                )
            ),
        )
        return weights.copy(), report

    current = weights.copy()
    trace: list[SurveyRakingIteration] = []
    max_error_history: list[float] = []
    stop_reason = "max_iter_exceeded"

    unique_margins = list(dict.fromkeys(int(value) for value in resolved_margin_ids.tolist()))
    for sweep in range(1, max_iterations + 1):
        previous = current.copy()
        for margin_id in unique_margins:
            indices = np.flatnonzero(resolved_margin_ids == margin_id)
            for idx in indices.tolist():
                membership = design[:, idx] > 0.0
                current_total = float(np.sum(current[membership]))
                target_total = float(targets[idx])
                if not membership.any():
                    continue
                if current_total <= 0.0:
                    continue
                factor = 0.0 if target_total == 0.0 else float(target_total / current_total)
                current[membership] *= factor

        achieved = np.asarray(design.T @ current, dtype=float)
        rel_errors = np.abs(achieved - targets) / (1.0 + np.abs(targets))
        max_rel_error = float(np.max(rel_errors)) if rel_errors.size else 0.0
        rms_rel_error = float(np.sqrt(np.mean(rel_errors ** 2))) if rel_errors.size else 0.0
        log_change = np.abs(np.log(np.maximum(current, _LOG_EPS)) - np.log(np.maximum(previous, _LOG_EPS)))
        max_log_change = float(np.max(log_change)) if log_change.size else 0.0
        worst_idx = int(np.argmax(rel_errors)) if rel_errors.size else 0
        max_error_history.append(max_rel_error)
        improvement_ratio = None
        if len(max_error_history) > stagnation_window:
            baseline = max_error_history[-stagnation_window - 1]
            if max_rel_error <= 0.0:
                improvement_ratio = float("inf")
            else:
                improvement_ratio = float(baseline / max(max_rel_error, 1e-16))

        trace.append(
            SurveyRakingIteration(
                sweep=sweep,
                max_rel_margin_error=max_rel_error,
                rms_rel_margin_error=rms_rel_error,
                max_logweight_change=max_log_change,
                improvement_ratio=improvement_ratio,
                worst_margin=margin_names[worst_idx] if rel_errors.size else None,
                worst_category=category_names[worst_idx] if rel_errors.size else None,
            )
        )

        if max_rel_error <= exact_tolerance and max_log_change <= logweight_tolerance:
            stop_reason = "converged_exact"
            break
        if (
            max_rel_error <= warn_tolerance
            and max_log_change <= max(logweight_tolerance * 100.0, 1e-6)
            and sweep >= 3
        ):
            stop_reason = "converged_warn_tolerance"
            break
        if (
            improvement_ratio is not None
            and max_rel_error > warn_tolerance
            and improvement_ratio < stagnation_min_improvement
            and max_log_change <= 1e-6
        ):
            stop_reason = "stagnation"
            break

    final_achieved = np.asarray(design.T @ current, dtype=float)
    final_categories = _category_diagnostics(
        base_weights=weights,
        final_weights=current,
        design=design,
        targets=targets,
        reference_total=reference_total,
        margin_names=margin_names,
        category_names=category_names,
        sparse_count_warn=sparse_count_warn,
        sparse_count_block=sparse_count_block,
        sparse_share_warn=sparse_share_warn,
        sparse_share_block=sparse_share_block,
    )
    report = _build_terminal_report(
        final_weights=current,
        base_weights=weights,
        targets=targets,
        achieved=final_achieved,
        category_keys=category_keys,
        categories=final_categories,
        margin_names=margin_names,
        category_names=category_names,
        trace=tuple(trace),
        stop_reason=stop_reason,
        reference_total=reference_total,
        blocking_reasons=(),
        extra_warnings=(),
        explicit_recommendations=(),
    )
    return current, report


def _resolve_margin_names(
    *,
    margin_ids: np.ndarray,
    margin_names_by_category: Sequence[str] | None,
    n_categories: int,
) -> tuple[str, ...]:
    if margin_names_by_category is None:
        return tuple(str(int(value)) for value in margin_ids.tolist())
    names = [str(value) for value in margin_names_by_category]
    if len(names) == n_categories:
        return tuple(names)
    unique_ids = list(dict.fromkeys(int(value) for value in margin_ids.tolist()))
    if len(names) == len(unique_ids):
        lookup = {margin_id: names[idx] for idx, margin_id in enumerate(unique_ids)}
        return tuple(lookup[int(value)] for value in margin_ids.tolist())
    raise ValueError("margin_names_by_category must match either n_categories or unique margin_ids")


def _resolve_category_names(
    *,
    category_labels: Sequence[str] | None,
    n_categories: int,
) -> tuple[str, ...]:
    if category_labels is None:
        return tuple(f"category_{idx}" for idx in range(n_categories))
    labels = tuple(str(value) for value in category_labels)
    if len(labels) != n_categories:
        raise ValueError("category_labels length must match category_matrix columns")
    return labels


def _reference_population_total(
    *,
    targets: np.ndarray,
    margin_ids: np.ndarray,
) -> tuple[float, str | None]:
    totals_by_margin: "OrderedDict[int, float]" = OrderedDict()
    for margin_id in dict.fromkeys(int(value) for value in margin_ids.tolist()):
        totals_by_margin[margin_id] = float(np.sum(targets[margin_ids == margin_id]))
    totals = list(totals_by_margin.values())
    if not totals:
        return 0.0, "no_target_margins"
    reference_total = totals[0]
    for total in totals[1:]:
        if abs(total - reference_total) > max(1e-8, 1e-8 * abs(reference_total)):
            return reference_total, "inconsistent_population_totals"
    if reference_total < 0.0:
        return reference_total, "negative_population_total"
    return reference_total, None


def _category_diagnostics(
    *,
    base_weights: np.ndarray,
    final_weights: np.ndarray,
    design: np.ndarray,
    targets: np.ndarray,
    reference_total: float,
    margin_names: Sequence[str],
    category_names: Sequence[str],
    sparse_count_warn: int,
    sparse_count_block: int,
    sparse_share_warn: float,
    sparse_share_block: float,
) -> tuple[SurveyRakingCategoryDiagnostic, ...]:
    n_obs = max(int(base_weights.shape[0]), 1)
    categories: list[SurveyRakingCategoryDiagnostic] = []
    achieved = np.asarray(design.T @ final_weights, dtype=float)
    for idx in range(design.shape[1]):
        membership = design[:, idx] > 0.0
        sample_count = int(np.sum(membership))
        sample_share = float(sample_count / n_obs)
        target_total = float(targets[idx])
        target_share = float(target_total / reference_total) if reference_total > 0.0 else 0.0
        sample_weight_total = float(np.sum(base_weights[membership]))
        structural_zero = bool(target_total > 0.0 and sample_count == 0)
        sparse_level = "ok"
        if structural_zero:
            sparse_level = "structural_zero"
        elif target_total > 0.0 and (
            sample_count < sparse_count_block or sample_share < sparse_share_block
        ):
            sparse_level = "block"
        elif target_total > 0.0 and (
            sample_count < sparse_count_warn or sample_share < sparse_share_warn
        ):
            sparse_level = "warn"
        vif_lb = _vif_lower_bound(target_share=target_share, sample_share=sample_share)
        categories.append(
            SurveyRakingCategoryDiagnostic(
                margin_name=str(margin_names[idx]),
                category_name=str(category_names[idx]),
                sample_count=sample_count,
                sample_share=sample_share,
                sample_weight_total=sample_weight_total,
                target_total=target_total,
                target_share=target_share,
                achieved_total=float(achieved[idx]),
                vif_lower_bound=vif_lb,
                structural_zero=structural_zero,
                sparse_level=sparse_level,
            )
        )
    return tuple(categories)


def _vif_lower_bound(*, target_share: float, sample_share: float) -> float | None:
    q = float(sample_share)
    p = float(target_share)
    if not math.isfinite(q) or not math.isfinite(p):
        return None
    if q <= 0.0:
        return float("inf") if p > 0.0 else 1.0
    if q >= 1.0:
        return 1.0 if abs(p - 1.0) <= 1e-12 else float("inf")
    return float(1.0 + ((p - q) ** 2) / max(q * (1.0 - q), 1e-12))


def _build_terminal_report(
    *,
    final_weights: np.ndarray,
    base_weights: np.ndarray,
    targets: np.ndarray,
    achieved: np.ndarray,
    category_keys: Sequence[str],
    categories: tuple[SurveyRakingCategoryDiagnostic, ...],
    margin_names: Sequence[str],
    category_names: Sequence[str],
    trace: tuple[SurveyRakingIteration, ...],
    stop_reason: str,
    reference_total: float,
    blocking_reasons: Sequence[str],
    extra_warnings: Sequence[str],
    explicit_recommendations: Sequence[str],
    fallback_used: str | None = None,
    converged_override: bool | None = None,
) -> SurveyRakingDiagnosticReport:
    rel_errors = np.abs(achieved - targets) / (1.0 + np.abs(targets))
    max_rel_error = float(np.max(rel_errors)) if rel_errors.size else 0.0
    rms_rel_error = float(np.sqrt(np.mean(rel_errors ** 2))) if rel_errors.size else 0.0
    worst_idx = int(np.argmax(rel_errors)) if rel_errors.size else 0
    max_log_change = float(trace[-1].max_logweight_change) if trace else 0.0
    improvement_ratio_5 = float(trace[-1].improvement_ratio) if trace and trace[-1].improvement_ratio is not None else None
    decreases = [
        trace[idx].max_rel_margin_error <= trace[idx - 1].max_rel_margin_error + 1e-15
        for idx in range(1, len(trace))
    ]
    monotonicity_share = float(np.mean(decreases)) if decreases else 1.0
    n_obs = max(int(final_weights.shape[0]), 1)
    weight_sum = float(np.sum(final_weights))
    weight_sq_sum = float(np.sum(final_weights ** 2))
    ess = float(weight_sum ** 2 / max(weight_sq_sum, 1e-12))
    ess_fraction = float(np.clip(ess / n_obs, 0.0, 1.0))
    kish_deff = float(n_obs / max(ess, 1e-12))
    mean_weight = float(np.mean(final_weights))
    cv_weights = float(np.std(final_weights) / max(abs(mean_weight), 1e-12))
    sorted_weights = np.sort(final_weights)[::-1]
    total_weight = max(float(np.sum(sorted_weights)), 1e-12)
    top1 = max(1, int(math.ceil(sorted_weights.size * 0.01)))
    top5 = max(1, int(math.ceil(sorted_weights.size * 0.05)))
    top1_share = float(np.sum(sorted_weights[:top1]) / total_weight)
    top5_share = float(np.sum(sorted_weights[:top5]) / total_weight)
    g_weights = final_weights / np.maximum(base_weights, 1e-12)
    max_g = float(np.max(g_weights))
    min_g = float(np.min(g_weights))

    vif_lb_max = 0.0
    sparse_category_count = 0
    structural_zero_count = 0
    for item in categories:
        vif_lb_max = max(vif_lb_max, float(item.vif_lower_bound or 0.0))
        if item.sparse_level in {"warn", "block", "structural_zero"}:
            sparse_category_count += 1
        if item.structural_zero:
            structural_zero_count += 1

    reasons_block = list(dict.fromkeys(str(reason) for reason in blocking_reasons))
    reasons_warn = list(dict.fromkeys(str(reason) for reason in extra_warnings))
    recommendations = list(dict.fromkeys(str(message) for message in explicit_recommendations))

    converged = (
        stop_reason in {"converged_exact", "converged_warn_tolerance"}
        if converged_override is None
        else bool(converged_override)
    )
    if max_rel_error > 1e-4:
        reasons_block.append("max_rel_margin_error")
        recommendations.append(
            f"Maximum relative margin error remains {max_rel_error:.3e}; targets are still not matched closely enough for production use."
        )
    elif max_rel_error > 1e-6:
        reasons_warn.append("warn_tolerance_only")
        recommendations.append(
            f"Raking stopped with max relative margin error {max_rel_error:.3e}; results are usable with caution but not at exact tolerance."
        )
    if stop_reason == "stagnation":
        reasons_block.append("stagnation")
        recommendations.append(
            "IPF stagnated before reaching warning tolerance; collapse sparse categories or relax the calibration design."
        )
    if stop_reason == "max_iter_exceeded" and max_rel_error > 1e-4:
        reasons_block.append("max_iter_exceeded")
        recommendations.append(
            "Maximum sweeps were exhausted before calibration error fell below the warning tolerance."
        )
    if monotonicity_share < 0.7:
        reasons_block.append("oscillation")
        recommendations.append(
            "Worst margin error oscillated across sweeps; targets are likely near-infeasible or the category design is too granular."
        )
    elif monotonicity_share < 0.9:
        reasons_warn.append("weak_monotonicity")
    if ess_fraction < 0.3:
        reasons_block.append("low_ess_fraction")
        recommendations.append(
            f"ESS/n = {ess_fraction:.2f}; unequal weighting implies high variance inflation and unstable microsimulation estimates."
        )
    elif ess_fraction < 0.5:
        reasons_warn.append("ess_fraction_warn")
    if sorted_weights.size >= 20:
        if top1_share > 0.25:
            reasons_block.append("top1_weight_share")
            recommendations.append(
                f"Top 1% of observations carry {top1_share:.1%} of total weight; the final weights are overly concentrated."
            )
        elif top1_share > 0.15:
            reasons_warn.append("top1_weight_share_warn")
    if vif_lb_max > 2.0:
        reasons_block.append("vif_lower_bound")
        recommendations.append(
            f"Preflight variance-inflation lower bound reaches {vif_lb_max:.2f}; near-positivity is severe even before considering other margins."
        )
    elif vif_lb_max > 1.5:
        reasons_warn.append("vif_lower_bound_warn")
    if max_g > 5.0 or min_g < 0.2:
        reasons_block.append("g_weight_bounds")
        recommendations.append(
            f"Final g-weights fall outside the engineering guardrail [0.2, 5.0] with min={min_g:.3f}, max={max_g:.3f}."
        )
    elif max_g > 3.0 or min_g < 0.3:
        reasons_warn.append("g_weight_bounds_warn")
    block_sparse = [item for item in categories if item.sparse_level in {"block", "structural_zero"}]
    warn_sparse = [item for item in categories if item.sparse_level == "warn"]
    if block_sparse:
        reasons_block.append("sparse_categories")
        recommendations.extend(
            f"Category '{item.margin_name}={item.category_name}' has only {item.sample_count} supporting records; collapse or remove the category before weighting."
            for item in block_sparse[:5]
        )
    elif warn_sparse:
        reasons_warn.append("sparse_categories_warn")

    decision = "block" if reasons_block else ("warn" if reasons_warn else "pass")
    return SurveyRakingDiagnosticReport(
        decision=decision,
        converged=converged,
        stop_reason=stop_reason,
        n_obs=int(final_weights.shape[0]),
        population_total=float(max(reference_total, 0.0)),
        n_sweeps=len(trace),
        max_rel_margin_error=max_rel_error,
        rms_rel_margin_error=rms_rel_error,
        max_logweight_change=max_log_change,
        improvement_ratio_5=improvement_ratio_5,
        monotonicity_share=monotonicity_share,
        worst_margin=margin_names[worst_idx] if rel_errors.size else None,
        worst_category=category_names[worst_idx] if rel_errors.size else None,
        ess=ess,
        ess_fraction=ess_fraction,
        kish_deff=kish_deff,
        cv_weights=cv_weights,
        top1_weight_share=top1_share,
        top5_weight_share=top5_share,
        max_g_weight_ratio=max_g,
        min_g_weight_ratio=min_g,
        structural_zero_count=structural_zero_count,
        sparse_category_count=sparse_category_count,
        vif_lb_max=vif_lb_max,
        target_totals={category_keys[idx]: float(targets[idx]) for idx in range(len(category_keys))},
        achieved_totals={category_keys[idx]: float(achieved[idx]) for idx in range(len(category_keys))},
        blocking_reasons=tuple(dict.fromkeys(reasons_block)),
        warnings=tuple(dict.fromkeys(reasons_warn)),
        recommendations=tuple(dict.fromkeys(recommendations)),
        categories=categories,
        trace=trace,
        fallback_used=fallback_used,
    )


def run_raking_with_fallbacks(
    *,
    base_weights: Sequence[float] | np.ndarray,
    category_matrix: Any,
    target_totals: Sequence[float] | np.ndarray,
    margin_ids: Sequence[int] | np.ndarray | None = None,
    margin_names_by_category: Sequence[str] | None = None,
    category_labels: Sequence[str] | None = None,
    max_iterations: int = 100,
    exact_tolerance: float = 1e-6,
    warn_tolerance: float = 1e-4,
    logweight_tolerance: float = 1e-8,
    stagnation_window: int = 5,
    stagnation_min_improvement: float = 1.02,
    sparse_count_warn: int = 30,
    sparse_count_block: int = 10,
    sparse_share_warn: float = 0.01,
    sparse_share_block: float = 0.005,
    collapse_sparse_categories: bool = True,
    collapse_map: Mapping[str, Mapping[str, str]] | None = None,
    allow_bounded_fallback: bool = True,
    allow_penalized_fallback: bool = True,
    bounded_lower_ratio: float = 0.3,
    bounded_upper_ratio: float = 3.0,
    hard_lower_ratio: float = 0.2,
    hard_upper_ratio: float = 5.0,
    fallback_ridge: float = 1e-2,
    fallback_max_iterations: int = 200,
) -> dict[str, Any]:
    """Run exact IPF plus recovery fallbacks and return machine-readable artifacts."""

    design = _matrix(category_matrix, name="category_matrix")
    targets = _vector(target_totals, name="target_totals")
    resolved_margin_ids = (
        np.arange(design.shape[1], dtype=int)
        if margin_ids is None
        else np.asarray(margin_ids, dtype=int).reshape(-1)
    )
    margin_names = _resolve_margin_names(
        margin_ids=resolved_margin_ids,
        margin_names_by_category=margin_names_by_category,
        n_categories=design.shape[1],
    )
    category_names = _resolve_category_names(
        category_labels=category_labels,
        n_categories=design.shape[1],
    )

    def _run_exact_candidate(
        matrix: np.ndarray,
        totals: np.ndarray,
        margin_ids_local: np.ndarray,
        margin_names_local: Sequence[str],
        category_names_local: Sequence[str],
    ) -> tuple[np.ndarray, SurveyRakingDiagnosticReport]:
        return run_raking_ipf(
            base_weights=base_weights,
            category_matrix=matrix,
            target_totals=totals,
            margin_ids=margin_ids_local,
            margin_names_by_category=margin_names_local,
            category_labels=category_names_local,
            max_iterations=max_iterations,
            exact_tolerance=exact_tolerance,
            warn_tolerance=warn_tolerance,
            logweight_tolerance=logweight_tolerance,
            stagnation_window=stagnation_window,
            stagnation_min_improvement=stagnation_min_improvement,
            sparse_count_warn=sparse_count_warn,
            sparse_count_block=sparse_count_block,
            sparse_share_warn=sparse_share_warn,
            sparse_share_block=sparse_share_block,
        )

    exact_weights, exact_report = _run_exact_candidate(
        design,
        targets,
        resolved_margin_ids,
        margin_names,
        category_names,
    )
    candidates: list[dict[str, Any]] = [
        {
            "name": "exact",
            "weights": exact_weights,
            "report": exact_report,
            "category_matrix": design,
            "target_totals": targets,
            "margin_ids": resolved_margin_ids,
            "margin_names": tuple(margin_names),
            "category_names": tuple(category_names),
            "metadata": {"mode": "exact_ipf"},
        }
    ]
    collapse_events: list[dict[str, Any]] = []
    notes: list[str] = []

    collapse_result = None
    if collapse_sparse_categories and _eligible_for_collapse(exact_report, collapse_map):
        collapse_result = _collapse_sparse_design(
            design=design,
            targets=targets,
            margin_ids=resolved_margin_ids,
            margin_names=margin_names,
            category_names=category_names,
            categories=exact_report.categories,
            collapse_map=collapse_map,
        )
    if collapse_result is not None:
        collapse_events = list(collapse_result["events"])
        collapsed_weights, collapsed_report = _run_exact_candidate(
            collapse_result["category_matrix"],
            collapse_result["target_totals"],
            collapse_result["margin_ids"],
            collapse_result["margin_names"],
            collapse_result["category_names"],
        )
        recommendations = tuple(
            dict.fromkeys(
                (
                    "Sparse categories were collapsed automatically before the final raking pass.",
                    *collapsed_report.recommendations,
                )
            )
        )
        collapsed_report = collapsed_report.model_copy(
            update={
                "stop_reason": "fallback_collapsed_categories",
                "fallback_used": "collapsed_categories",
                "converged": bool(collapsed_report.max_rel_margin_error <= warn_tolerance),
                "recommendations": recommendations,
            }
        )
        candidates.append(
            {
                "name": "collapsed_categories",
                "weights": collapsed_weights,
                "report": collapsed_report,
                "category_matrix": collapse_result["category_matrix"],
                "target_totals": collapse_result["target_totals"],
                "margin_ids": collapse_result["margin_ids"],
                "margin_names": collapse_result["margin_names"],
                "category_names": collapse_result["category_names"],
                "metadata": {"collapsed_categories": collapse_events},
            }
        )

    current_best = _pick_best_candidate(candidates)
    if current_best["report"].fallback_used is not None:
        notes.append(f"raking_fallback_used:{current_best['report'].fallback_used}")

    if allow_bounded_fallback and _eligible_for_stability_fallback(current_best["report"]):
        bounded_fit = _optimize_bounded_scores(
            design=np.asarray(current_best["category_matrix"], dtype=float),
            base_weights=_vector(base_weights, name="base_weights"),
            targets=np.asarray(current_best["target_totals"], dtype=float),
            lower_ratio=bounded_lower_ratio,
            upper_ratio=bounded_upper_ratio,
            ridge=max(float(fallback_ridge), 1e-8),
            max_iterations=fallback_max_iterations,
            init_weights=np.asarray(current_best["weights"], dtype=float),
        )
        if bounded_fit is None:
            notes.append("raking_scipy_fallbacks_unavailable")
        else:
            bounded_report = _build_fallback_report(
                final_weights=bounded_fit["weights"],
                base_weights=_vector(base_weights, name="base_weights"),
                design=np.asarray(current_best["category_matrix"], dtype=float),
                targets=np.asarray(current_best["target_totals"], dtype=float),
                margin_ids=np.asarray(current_best["margin_ids"], dtype=int),
                margin_names=current_best["margin_names"],
                category_names=current_best["category_names"],
                fallback_used="bounded_logit",
                stop_reason=(
                    "fallback_bounded_logit"
                    if bounded_fit["success"] and bounded_fit["max_rel_margin_error"] <= warn_tolerance
                    else "bounded_infeasible"
                ),
                success=bool(bounded_fit["success"]),
                optimizer_message=str(bounded_fit["message"]),
                sparse_count_warn=sparse_count_warn,
                sparse_count_block=sparse_count_block,
                sparse_share_warn=sparse_share_warn,
                sparse_share_block=sparse_share_block,
                warn_tolerance=warn_tolerance,
                note=(
                    f"Applied bounded logit fallback with g-weight ratios constrained to "
                    f"[{bounded_lower_ratio:.2f}, {bounded_upper_ratio:.2f}]."
                ),
            )
            candidates.append(
                {
                    "name": "bounded_logit",
                    "weights": bounded_fit["weights"],
                    "report": bounded_report,
                    "category_matrix": current_best["category_matrix"],
                    "target_totals": current_best["target_totals"],
                    "margin_ids": current_best["margin_ids"],
                    "margin_names": current_best["margin_names"],
                    "category_names": current_best["category_names"],
                    "metadata": {
                        "optimizer_success": bounded_fit["success"],
                        "optimizer_message": bounded_fit["message"],
                        "optimizer_iterations": bounded_fit["iterations"],
                    },
                }
            )

    current_best = _pick_best_candidate(candidates)
    if allow_penalized_fallback and _eligible_for_stability_fallback(current_best["report"]):
        penalized_fit = _optimize_bounded_scores(
            design=np.asarray(current_best["category_matrix"], dtype=float),
            base_weights=_vector(base_weights, name="base_weights"),
            targets=np.asarray(current_best["target_totals"], dtype=float),
            lower_ratio=hard_lower_ratio,
            upper_ratio=hard_upper_ratio,
            ridge=max(float(fallback_ridge) * 0.1, 1e-10),
            max_iterations=fallback_max_iterations,
            init_weights=np.asarray(current_best["weights"], dtype=float),
        )
        if penalized_fit is None:
            notes.append("raking_scipy_fallbacks_unavailable")
        else:
            penalized_report = _build_fallback_report(
                final_weights=penalized_fit["weights"],
                base_weights=_vector(base_weights, name="base_weights"),
                design=np.asarray(current_best["category_matrix"], dtype=float),
                targets=np.asarray(current_best["target_totals"], dtype=float),
                margin_ids=np.asarray(current_best["margin_ids"], dtype=int),
                margin_names=current_best["margin_names"],
                category_names=current_best["category_names"],
                fallback_used="penalized",
                stop_reason="fallback_penalized",
                success=bool(penalized_fit["success"]),
                optimizer_message=str(penalized_fit["message"]),
                sparse_count_warn=sparse_count_warn,
                sparse_count_block=sparse_count_block,
                sparse_share_warn=sparse_share_warn,
                sparse_share_block=sparse_share_block,
                warn_tolerance=warn_tolerance,
                note=(
                    f"Applied penalized fallback with relaxed engineering bounds "
                    f"[{hard_lower_ratio:.2f}, {hard_upper_ratio:.2f}] on g-weights."
                ),
            )
            candidates.append(
                {
                    "name": "penalized",
                    "weights": penalized_fit["weights"],
                    "report": penalized_report,
                    "category_matrix": current_best["category_matrix"],
                    "target_totals": current_best["target_totals"],
                    "margin_ids": current_best["margin_ids"],
                    "margin_names": current_best["margin_names"],
                    "category_names": current_best["category_names"],
                    "metadata": {
                        "optimizer_success": penalized_fit["success"],
                        "optimizer_message": penalized_fit["message"],
                        "optimizer_iterations": penalized_fit["iterations"],
                    },
                }
            )

    best = _pick_best_candidate(candidates)
    warnings = list(str(item) for item in best["report"].warnings)
    if best["report"].fallback_used is not None:
        warnings.append(f"raking_fallback_used:{best['report'].fallback_used}")
    warnings.extend(notes)
    return {
        "weights": np.asarray(best["weights"], dtype=float),
        "diagnostics": best["report"],
        "category_matrix": np.asarray(best["category_matrix"], dtype=float),
        "target_totals": np.asarray(best["target_totals"], dtype=float),
        "margin_ids": np.asarray(best["margin_ids"], dtype=int),
        "margin_names_by_category": tuple(str(item) for item in best["margin_names"]),
        "category_labels": tuple(str(item) for item in best["category_names"]),
        "artifacts": _build_raking_artifacts(best=best, candidates=candidates, collapse_events=collapse_events),
        "warnings": tuple(dict.fromkeys(str(item) for item in warnings if str(item))),
    }


def _eligible_for_collapse(
    report: SurveyRakingDiagnosticReport,
    collapse_map: Mapping[str, Mapping[str, str]] | None,
) -> bool:
    if collapse_map:
        return True
    if report.stop_reason in {"stagnation", "max_iter_exceeded"}:
        return True
    return any(item.sparse_level in {"warn", "block"} for item in report.categories)


def _eligible_for_stability_fallback(report: SurveyRakingDiagnosticReport) -> bool:
    if report.stop_reason in {"structural_zero", "inconsistent_targets"}:
        return False
    if report.structural_zero_count > 0:
        return False
    if "sparse_categories" in report.blocking_reasons:
        return False
    reasons = set(report.blocking_reasons) | set(report.warnings)
    trigger_reasons = {
        "ess_fraction_warn",
        "g_weight_bounds",
        "g_weight_bounds_warn",
        "low_ess_fraction",
        "max_iter_exceeded",
        "max_rel_margin_error",
        "stagnation",
        "top1_weight_share",
        "top1_weight_share_warn",
        "warn_tolerance_only",
        "weak_monotonicity",
    }
    return report.decision != "pass" and bool(reasons & trigger_reasons)


def _collapse_sparse_design(
    *,
    design: np.ndarray,
    targets: np.ndarray,
    margin_ids: np.ndarray,
    margin_names: Sequence[str],
    category_names: Sequence[str],
    categories: Sequence[SurveyRakingCategoryDiagnostic],
    collapse_map: Mapping[str, Mapping[str, str]] | None,
) -> dict[str, Any] | None:
    categories_by_key = {
        f"{item.margin_name}={item.category_name}": item
        for item in categories
    }
    explicit_map = collapse_map if isinstance(collapse_map, Mapping) else {}
    new_columns: list[np.ndarray] = []
    new_targets: list[float] = []
    new_margin_ids: list[int] = []
    new_margin_names: list[str] = []
    new_category_names: list[str] = []
    events: list[dict[str, Any]] = []
    changed = False

    for margin_id in dict.fromkeys(int(value) for value in margin_ids.tolist()):
        indices = np.flatnonzero(margin_ids == margin_id).tolist()
        margin_name = str(margin_names[indices[0]])
        margin_map = (
            explicit_map.get(margin_name)
            if isinstance(explicit_map.get(margin_name), Mapping)
            else None
        )
        assignments: "OrderedDict[str, list[int]]"
        if margin_map:
            assignments = OrderedDict()
            for idx in indices:
                group_name = str(margin_map.get(str(category_names[idx]), str(category_names[idx])))
                assignments.setdefault(group_name, []).append(idx)
        else:
            sparse_indices = [
                idx
                for idx in indices
                if categories_by_key.get(f"{margin_names[idx]}={category_names[idx]}", None) is not None
                and categories_by_key[f"{margin_names[idx]}={category_names[idx]}"].sparse_level in {"warn", "block"}
            ]
            assignments = OrderedDict(
                (str(category_names[idx]), [idx])
                for idx in indices
                if idx not in sparse_indices
            )
            if len(sparse_indices) >= 2:
                assignments["__collapsed__"] = sparse_indices
            else:
                for idx in sparse_indices:
                    assignments[str(category_names[idx])] = [idx]

        for collapsed_name, members in assignments.items():
            column = np.clip(np.sum(design[:, members], axis=1), 0.0, 1.0)
            new_columns.append(column)
            new_targets.append(float(np.sum(targets[members])))
            new_margin_ids.append(margin_id)
            new_margin_names.append(margin_name)
            new_category_names.append(str(collapsed_name))
            if len(members) > 1 or any(str(category_names[item]) != str(collapsed_name) for item in members):
                changed = True
                events.append(
                    {
                        "margin_name": margin_name,
                        "collapsed_category": str(collapsed_name),
                        "source_categories": [str(category_names[item]) for item in members],
                        "sample_count": int(np.sum(column > 0.0)),
                        "target_total": float(np.sum(targets[members])),
                    }
                )

    if not changed:
        return None
    category_matrix = np.column_stack(new_columns) if new_columns else np.zeros((design.shape[0], 0))
    return {
        "category_matrix": category_matrix,
        "target_totals": np.asarray(new_targets, dtype=float),
        "margin_ids": np.asarray(new_margin_ids, dtype=int),
        "margin_names": tuple(new_margin_names),
        "category_names": tuple(new_category_names),
        "events": tuple(events),
    }


def _optimize_bounded_scores(
    *,
    design: np.ndarray,
    base_weights: np.ndarray,
    targets: np.ndarray,
    lower_ratio: float,
    upper_ratio: float,
    ridge: float,
    max_iterations: int,
    init_weights: np.ndarray | None,
) -> dict[str, Any] | None:
    if not _SCIPY_AVAILABLE or minimize is None:
        return None
    if not lower_ratio < 1.0 < upper_ratio:
        return None

    lower = float(lower_ratio)
    upper = float(upper_ratio)
    span = upper - lower
    offset = math.log((1.0 - lower) / max(upper - 1.0, 1e-12))
    scale = 1.0 + np.abs(targets)

    def _weights_and_grad_factor(coeffs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        scores = np.asarray(design @ coeffs, dtype=float)
        shifted = np.clip(scores + offset, -60.0, 60.0)
        sigmoid = 1.0 / (1.0 + np.exp(-shifted))
        g_weights = lower + span * sigmoid
        grad_factor = span * sigmoid * (1.0 - sigmoid)
        return base_weights * g_weights, grad_factor

    def _objective(coeffs: np.ndarray) -> tuple[float, np.ndarray]:
        weights, grad_factor = _weights_and_grad_factor(coeffs)
        achieved = np.asarray(design.T @ weights, dtype=float)
        residual = (achieved - targets) / scale
        loss = 0.5 * float(np.dot(residual, residual)) + 0.5 * float(ridge) * float(np.dot(coeffs, coeffs))
        influence = np.asarray(design @ (residual / scale), dtype=float)
        gradient = (
            np.asarray(design.T @ (base_weights * grad_factor * influence), dtype=float)
            + float(ridge) * coeffs
        )
        return loss, gradient

    x0 = np.zeros(design.shape[1], dtype=float)
    if init_weights is not None and init_weights.shape == base_weights.shape:
        init_ratio = np.clip(init_weights / np.maximum(base_weights, 1e-12), lower + 1e-6, upper - 1e-6)
        probs = np.clip((init_ratio - lower) / span, 1e-6, 1.0 - 1e-6)
        raw_scores = np.log(probs / (1.0 - probs)) - offset
        try:
            x0 = np.linalg.lstsq(design, raw_scores, rcond=None)[0]
        except np.linalg.LinAlgError:
            x0 = np.zeros(design.shape[1], dtype=float)

    result = minimize(
        fun=lambda coeffs: _objective(coeffs)[0],
        x0=x0,
        jac=lambda coeffs: _objective(coeffs)[1],
        method="L-BFGS-B",
        options={"maxiter": int(max_iterations), "ftol": 1e-12},
    )
    weights, _ = _weights_and_grad_factor(np.asarray(result.x, dtype=float))
    achieved = np.asarray(design.T @ weights, dtype=float)
    rel_errors = np.abs(achieved - targets) / (1.0 + np.abs(targets))
    return {
        "weights": np.asarray(weights, dtype=float),
        "success": bool(result.success),
        "message": str(result.message),
        "iterations": int(getattr(result, "nit", 0) or 0),
        "max_rel_margin_error": float(np.max(rel_errors)) if rel_errors.size else 0.0,
    }


def _build_fallback_report(
    *,
    final_weights: np.ndarray,
    base_weights: np.ndarray,
    design: np.ndarray,
    targets: np.ndarray,
    margin_ids: np.ndarray,
    margin_names: Sequence[str],
    category_names: Sequence[str],
    fallback_used: str,
    stop_reason: str,
    success: bool,
    optimizer_message: str,
    sparse_count_warn: int,
    sparse_count_block: int,
    sparse_share_warn: float,
    sparse_share_block: float,
    warn_tolerance: float,
    note: str,
) -> SurveyRakingDiagnosticReport:
    reference_total, _ = _reference_population_total(targets=targets, margin_ids=margin_ids)
    category_keys = tuple(f"{margin_names[idx]}={category_names[idx]}" for idx in range(design.shape[1]))
    achieved = np.asarray(design.T @ final_weights, dtype=float)
    categories = _category_diagnostics(
        base_weights=base_weights,
        final_weights=final_weights,
        design=design,
        targets=targets,
        reference_total=reference_total,
        margin_names=margin_names,
        category_names=category_names,
        sparse_count_warn=sparse_count_warn,
        sparse_count_block=sparse_count_block,
        sparse_share_warn=sparse_share_warn,
        sparse_share_block=sparse_share_block,
    )
    report = _build_terminal_report(
        final_weights=final_weights,
        base_weights=base_weights,
        targets=targets,
        achieved=achieved,
        category_keys=category_keys,
        categories=categories,
        margin_names=margin_names,
        category_names=category_names,
        trace=(),
        stop_reason=stop_reason,
        reference_total=reference_total,
        blocking_reasons=(),
        extra_warnings=(() if success else ("fallback_solver_failed",)),
        explicit_recommendations=(note,),
        fallback_used=fallback_used,
        converged_override=bool(np.max(np.abs(achieved - targets) / (1.0 + np.abs(targets))) <= warn_tolerance),
    )
    recommendations = tuple(
        dict.fromkeys(
            (
                *report.recommendations,
                f"Fallback solver message: {optimizer_message}.",
            )
        )
    )
    return report.model_copy(update={"recommendations": recommendations})


def _candidate_score(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    report: SurveyRakingDiagnosticReport = candidate["report"]
    return (
        _DECISION_RANK.get(report.decision, 3),
        0 if report.converged else 1,
        len(report.blocking_reasons),
        1 if report.max_rel_margin_error > 1e-4 else 0,
        float(report.max_rel_margin_error),
        1 if report.ess_fraction < 0.3 else 0,
        -float(report.ess_fraction),
        float(report.top1_weight_share),
        abs(float(report.max_g_weight_ratio) - 1.0) + abs(float(report.min_g_weight_ratio) - 1.0),
        0 if candidate.get("name") == "exact" else 1,
    )


def _pick_best_candidate(candidates: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return min(candidates, key=_candidate_score)


def _build_raking_artifacts(
    *,
    best: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    collapse_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    report: SurveyRakingDiagnosticReport = best["report"]
    sparse_categories = [
        item.model_dump(mode="json")
        for item in report.categories
        if item.sparse_level != "ok" or item.structural_zero
    ]
    return {
        "raking_diagnostics": report.model_dump(mode="json"),
        "raking_trace": [item.model_dump(mode="json") for item in report.trace],
        "sparse_categories": sparse_categories,
        "fallback_summary": {
            "selected": str(best.get("name")),
            "fallback_used": report.fallback_used,
            "stop_reason": report.stop_reason,
            "attempts": [
                {
                    "name": str(candidate.get("name")),
                    "decision": candidate["report"].decision,
                    "stop_reason": candidate["report"].stop_reason,
                    "fallback_used": candidate["report"].fallback_used,
                    "max_rel_margin_error": float(candidate["report"].max_rel_margin_error),
                    "ess_fraction": float(candidate["report"].ess_fraction),
                    "blocking_reasons": list(candidate["report"].blocking_reasons),
                    "warnings": list(candidate["report"].warnings),
                    "metadata": dict(candidate.get("metadata") or {}),
                }
                for candidate in candidates
            ],
            "collapse_events": [dict(item) for item in collapse_events],
        },
    }
