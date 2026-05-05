"""Calibrate predictive uncertainty envelopes for ML regression outputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
)
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

from .protocols import (
    CalibrationSupportDiagnostic,
    ConditionalCoverageDiagnostic,
    ConformalMethodSpec,
    CoverageEstimate,
    ERTDiagnostic,
    GraphCoverageDiagnostic,
    GroupCoverageEstimate,
    PredictionIntervalResult,
    PredictionResult,
    PredictionSetResult,
    ScoreTailDiagnostic,
    ShiftDiagnostic,
)


def _prediction_payload(state: Any) -> PredictionResult:
    if isinstance(state, PredictionResult):
        return state
    if isinstance(state, Mapping):
        nested = state.get("prediction_result")
        if isinstance(nested, PredictionResult):
            return nested
        nested_result = state.get("result")
        if isinstance(nested_result, PredictionResult):
            return nested_result
        if isinstance(nested, Mapping):
            return PredictionResult.model_validate(nested)
        if isinstance(nested_result, Mapping):
            return PredictionResult.model_validate(nested_result)
        return PredictionResult.model_validate(dict(state))
    raise TypeError("state must be PredictionResult or mapping")


def _weighted_quantile(values: np.ndarray, quantile: float, weights: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float).reshape(-1)
    w = np.asarray(weights, dtype=float).reshape(-1)
    if arr.shape[0] != w.shape[0]:
        raise ValueError("importance_weights must match residual length")
    if arr.shape[0] == 0:
        raise ValueError("weighted quantile requires at least one value")
    if not np.all(np.isfinite(w)) or np.any(w < 0.0):
        raise ValueError("importance_weights must be finite and non-negative")
    weight_sum = float(np.sum(w))
    if weight_sum <= 0.0:
        raise ValueError("importance_weights must sum to a positive value")
    q = min(max(float(quantile), 0.0), 1.0)
    order = np.argsort(arr)
    sorted_values = arr[order]
    sorted_weights = w[order]
    cdf = np.cumsum(sorted_weights) / weight_sum
    idx = int(np.searchsorted(cdf, q, side="left"))
    idx = min(max(idx, 0), sorted_values.shape[0] - 1)
    return float(sorted_values[idx])


def _effective_sample_size(weights: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float).reshape(-1)
    denom = float(np.sum(w**2))
    total = float(np.sum(w))
    if total <= 0.0 or denom <= 0.0:
        return 0.0
    return (total * total) / denom


class WeightedConformalQuantile(BaseModel):
    """Compute conformal score quantiles with optional density-ratio weights and ESS checks."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    min_effective_sample_size: float = Field(default=1.0, ge=1.0)
    finite_sample_correction: bool = True

    @staticmethod
    def effective_sample_size(weights: Sequence[float] | np.ndarray) -> float:
        """Return Kish effective sample size for non-negative importance weights."""

        return _effective_sample_size(np.asarray(weights, dtype=float))

    def quantile(
        self,
        scores: Sequence[float] | np.ndarray,
        weights: Sequence[float] | np.ndarray | None = None,
    ) -> tuple[float, float | None]:
        """Return the conformal quantile and optional weighted effective sample size."""

        score_arr = _as_1d_float("scores", scores)
        level = _conformal_quantile_level(score_arr.shape[0], self.alpha)
        if weights is None:
            return _higher_quantile(score_arr, level), None
        weight_arr = _as_1d_float("importance_weights", weights)
        if weight_arr.shape[0] != score_arr.shape[0]:
            raise ValueError("importance_weights must match score length")
        ess = _effective_sample_size(weight_arr)
        if ess < self.min_effective_sample_size:
            raise ValueError(
                f"weighted conformal effective sample size {ess:.3f} is below "
                f"min_effective_sample_size={self.min_effective_sample_size:.3f}"
            )
        return _weighted_quantile(score_arr, level, weight_arr), ess


def _as_1d_float(name: str, value: Any) -> np.ndarray:
    arr = np.asarray(value, dtype=float).reshape(-1)
    if arr.shape[0] == 0:
        raise ValueError(f"{name} must contain at least one value")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _alpha_from_params(params: Mapping[str, Any], default: float = 0.05) -> float:
    if params.get("target_coverage") is not None:
        target_coverage = float(params["target_coverage"])
        if not (0.0 < target_coverage < 1.0):
            raise ValueError("target_coverage must be in (0, 1)")
        alpha = 1.0 - target_coverage
    else:
        alpha = float(params.get("alpha", default))
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1)")
    return alpha


def _conformal_quantile_level(n_obs: int, alpha: float) -> float:
    if n_obs <= 0:
        raise ValueError("conformal quantile requires at least one calibration score")
    rank = np.ceil((n_obs + 1.0) * (1.0 - alpha))
    return float(min(max(rank / n_obs, 0.0), 1.0))


def _higher_quantile(values: np.ndarray, level: float) -> float:
    arr = _as_1d_float("values", values)
    return float(np.quantile(arr, min(max(level, 0.0), 1.0), method="higher"))


def _array_from_sources(
    name: str,
    params: Mapping[str, Any],
    prediction_result: PredictionResult,
    aliases: Sequence[str],
) -> np.ndarray:
    for alias in aliases:
        if alias in params and params[alias] is not None:
            return _as_1d_float(name, params[alias])
    for alias in aliases:
        value = prediction_result.metadata.get(alias)
        if value is not None:
            return _as_1d_float(name, value)
    raise ValueError(f"{name} is required; provide one of {', '.join(aliases)}")


def _as_optional_weights(
    params: Mapping[str, Any],
    prediction_result: PredictionResult,
    n_obs: int,
) -> np.ndarray | None:
    value = params.get("importance_weights")
    if value is None:
        value = prediction_result.metadata.get("importance_weights")
    if value is None:
        return None
    weights = _as_1d_float("importance_weights", value)
    if weights.shape[0] != n_obs:
        raise ValueError("importance_weights must align with calibration rows")
    if np.any(weights < 0.0):
        raise ValueError("importance_weights must be non-negative")
    if float(np.sum(weights)) <= 0.0:
        raise ValueError("importance_weights must sum to a positive value")
    return weights


def _group_payload(
    params: Mapping[str, Any],
    prediction_result: PredictionResult,
    n_obs: int,
) -> tuple[np.ndarray, str]:
    group_values = params.get("group_values")
    if group_values is None:
        group_values = prediction_result.metadata.get("group_values")
    if group_values is None:
        group_values = prediction_result.metadata.get("groups")
    if group_values is None:
        return np.full(n_obs, "__all__", dtype=object), "all"

    group_keys_param = params.get("group_keys")
    if isinstance(group_values, Mapping):
        available = dict(group_values)
        if group_keys_param is None:
            group_keys = tuple(sorted(str(key) for key in available))
        elif isinstance(group_keys_param, str):
            group_keys = (group_keys_param,)
        else:
            group_keys = tuple(str(key) for key in group_keys_param)
        columns: list[np.ndarray] = []
        for key in group_keys:
            if key not in available:
                raise ValueError(f"group_values is missing group key {key!r}")
            column = np.asarray(available[key], dtype=object).reshape(-1)
            if column.shape[0] != n_obs:
                raise ValueError("each group_values column must match prediction length")
            columns.append(column)
        labels = np.asarray(
            [
                "|".join(
                    f"{key}={columns[col_idx][row_idx]}" for col_idx, key in enumerate(group_keys)
                )
                for row_idx in range(n_obs)
            ],
            dtype=object,
        )
        return labels, "|".join(group_keys)

    labels = np.asarray(group_values, dtype=object).reshape(-1)
    if labels.shape[0] != n_obs:
        raise ValueError("group_values must match prediction length")
    group_key = str(params.get("group_key", "group"))
    return labels.astype(str), group_key


def _wilson_coverage(covered: int, n_obs: int, z: float = 1.96) -> CoverageEstimate:
    if n_obs <= 0:
        return CoverageEstimate(n=0, covered=0, coverage=0.0, ci_low=0.0, ci_high=0.0)
    coverage = covered / n_obs
    denom = 1.0 + (z * z) / n_obs
    center = (coverage + (z * z) / (2.0 * n_obs)) / denom
    half = (
        z * np.sqrt((coverage * (1.0 - coverage) / n_obs) + (z * z) / (4.0 * n_obs * n_obs)) / denom
    )
    return CoverageEstimate(
        n=int(n_obs),
        covered=int(covered),
        coverage=float(coverage),
        ci_low=float(max(0.0, center - half)),
        ci_high=float(min(1.0, center + half)),
    )


def _coverage_from_mask(covered_mask: np.ndarray) -> CoverageEstimate:
    covered_bool = np.asarray(covered_mask, dtype=bool).reshape(-1)
    return _wilson_coverage(int(np.sum(covered_bool)), int(covered_bool.shape[0]))


def _interval_widths(lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    return np.maximum(np.asarray(upper, dtype=float) - np.asarray(lower, dtype=float), 0.0)


def _score_tail_diagnostic(
    scores: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    target: np.ndarray | None,
) -> ScoreTailDiagnostic:
    score_arr = np.asarray(scores, dtype=float).reshape(-1)
    widths = _interval_widths(lower, upper)
    q50, q90, q95, q99 = (float(np.quantile(score_arr, q)) for q in (0.5, 0.9, 0.95, 0.99))
    q99_q90_ratio = float(q99 / max(abs(q90), 1.0e-12))
    median_width = float(np.median(widths))
    p90_width = float(np.quantile(widths, 0.9))
    vacuity_rate = 0.0
    status: str = "pass"
    if target is not None:
        target_arr = np.asarray(target, dtype=float).reshape(-1)
        target_iqr = float(np.quantile(target_arr, 0.75) - np.quantile(target_arr, 0.25))
        if target_iqr > 1.0e-12:
            vacuity_mask = widths > 1.5 * target_iqr
            vacuity_rate = float(np.mean(vacuity_mask))
            if median_width > 0.75 * target_iqr or p90_width > 1.5 * target_iqr:
                status = "fail"
            elif p90_width > target_iqr:
                status = "warn"
    if q99_q90_ratio > 4.0:
        status = "fail"
    elif q99_q90_ratio > 2.5 and status == "pass":
        status = "warn"
    return ScoreTailDiagnostic(
        score_q50=q50,
        score_q90=q90,
        score_q95=q95,
        score_q99=q99,
        q99_q90_ratio=q99_q90_ratio,
        hill_tail_index=None,
        vacuity_rate=vacuity_rate,
        median_interval_width=median_width,
        p90_interval_width=p90_width,
        status=status,  # type: ignore[arg-type]
    )


def _support_status(
    n_calibration: int,
    min_group_calibration_n: int,
    ess: float | None,
    min_group_weighted_ess: float | None,
) -> tuple[bool, str]:
    if n_calibration < min_group_calibration_n:
        return False, "low_n"
    if min_group_weighted_ess is not None and (ess is None or ess < min_group_weighted_ess):
        return False, "low_ess"
    return True, "ok"


def _group_estimates(
    group_labels: np.ndarray,
    group_key: str,
    lower: np.ndarray,
    upper: np.ndarray,
    target: np.ndarray | None,
    alpha: float,
    min_group_calibration_n: int,
    weights: np.ndarray | None = None,
    min_group_weighted_ess: float | None = None,
) -> tuple[list[GroupCoverageEstimate], CalibrationSupportDiagnostic, ShiftDiagnostic | None]:
    labels = np.asarray(group_labels, dtype=object).reshape(-1)
    widths = _interval_widths(lower, upper)
    groups: list[GroupCoverageEstimate] = []
    groups_below: list[str] = []
    ess_by_group: dict[str, float] = {}
    for raw_group in sorted({str(value) for value in labels}):
        mask = labels.astype(str) == raw_group
        n_group = int(np.sum(mask))
        group_ess: float | None = None
        if weights is not None:
            group_ess = _effective_sample_size(weights[mask])
            ess_by_group[raw_group] = float(group_ess)
        supported, status = _support_status(
            n_group,
            min_group_calibration_n,
            group_ess,
            min_group_weighted_ess,
        )
        if not supported:
            groups_below.append(raw_group)
        coverage = ci_low = ci_high = shortfall = None
        n_evaluation = None
        if target is not None:
            covered = (target[mask] >= lower[mask]) & (target[mask] <= upper[mask])
            estimate = _coverage_from_mask(covered)
            coverage = estimate.coverage
            ci_low = estimate.ci_low
            ci_high = estimate.ci_high
            shortfall = max((1.0 - alpha) - coverage, 0.0)
            n_evaluation = n_group
        groups.append(
            GroupCoverageEstimate(
                group_key=group_key,
                group_value=raw_group,
                n_calibration=n_group,
                n_evaluation=n_evaluation,
                coverage=coverage,
                ci_low=ci_low,
                ci_high=ci_high,
                median_width=float(np.median(widths[mask])) if n_group else None,
                p90_width=float(np.quantile(widths[mask], 0.9)) if n_group else None,
                shortfall=shortfall,
                guarantee_supported=supported,
                support_status=status,  # type: ignore[arg-type]
            )
        )

    min_group_weighted_ess_value = None
    if ess_by_group:
        min_group_weighted_ess_value = float(min(ess_by_group.values()))
    support = CalibrationSupportDiagnostic(
        n_calibration_total=int(labels.shape[0]),
        min_group_calibration_n=int(min_group_calibration_n),
        min_group_weighted_ess=min_group_weighted_ess_value,
        groups_below_min_support=groups_below,
        unsupported_groups_seen=[],
        status="warn" if groups_below else "pass",
    )
    shift: ShiftDiagnostic | None = None
    if weights is not None:
        ess = _effective_sample_size(weights)
        ratio = ess / max(float(labels.shape[0]), 1.0)
        if ratio < 0.15:
            shift_status = "fail"
        elif ratio < 0.30:
            shift_status = "warn"
        else:
            shift_status = "pass"
        shift = ShiftDiagnostic(
            evaluated=True,
            calibration_vs_deployment_auc=None,
            psi_max=None,
            mmd=None,
            density_ratio_ess=float(ess),
            density_ratio_ess_by_group=ess_by_group,
            unseen_category_rate=None,
            status=shift_status,  # type: ignore[arg-type]
        )
    return groups, support, shift


def _diagnostic_status(
    support: CalibrationSupportDiagnostic,
    tail: ScoreTailDiagnostic,
    shift: ShiftDiagnostic | None,
    groups: Sequence[GroupCoverageEstimate],
    alpha: float,
) -> tuple[str, list[str], str]:
    failure_modes: list[str] = []
    status = "pass"
    action = "accept"
    if support.groups_below_min_support:
        status = "unsupported"
        action = "pool_or_cluster_groups"
        failure_modes.append("low_group_calibration_support")
    if tail.status == "fail":
        status = "fail" if status != "unsupported" else status
        action = "retrain_base_model" if status == "fail" else action
        failure_modes.append("heavy_tail_or_vacuous_interval")
    elif tail.status == "warn" and status == "pass":
        status = "warn"
        failure_modes.append("tail_or_width_warning")
    if shift is not None and shift.status in {"warn", "fail"}:
        failure_modes.append("low_weighted_effective_sample_size")
        if shift.status == "fail":
            status = "unsupported"
            action = "collect_more_calibration_data"
        elif status == "pass":
            status = "warn"
            action = "enable_weighted_conformal"
    for group in groups:
        if group.guarantee_supported and group.coverage is not None:
            if group.coverage < (1.0 - alpha) - 0.03:
                if status == "pass":
                    status = "warn"
                failure_modes.append("group_coverage_shortfall")
                action = "collect_more_calibration_data"
                break
    return status, sorted(set(failure_modes)), action


def _method_spec(
    family: str,
    base_model_family: str,
    alpha: float,
    n_calibration: int,
    weighted: bool = False,
    grouped: bool = False,
    class_conditional: bool = False,
    calibration_timestamp: str | None = None,
    calibration_data_hash: str | None = None,
) -> ConformalMethodSpec:
    scope: list[str] = ["marginal"]
    if grouped:
        scope.append("group_conditional")
    if class_conditional:
        scope.append("class_conditional")
    if weighted:
        scope.append("finite_shift_class")
    assumptions = [
        "calibration and deployment rows are exchangeable within the declared scope",
        "the base model was fit without using the calibration labels used for conformal scores",
    ]
    if weighted:
        assumptions.append("importance weights estimate calibration-to-deployment covariate shift")
    return ConformalMethodSpec(
        family=family,  # type: ignore[arg-type]
        base_model_family=base_model_family,
        guarantee_scope=scope,  # type: ignore[arg-type]
        assumptions=assumptions,
        calibration_size=int(n_calibration),
        calibration_timestamp=calibration_timestamp,
        calibration_data_hash=calibration_data_hash,
    )


def _build_conditional_diagnostic(
    *,
    family: str,
    base_model_family: str,
    alpha: float,
    scores: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    target: np.ndarray | None,
    group_labels: np.ndarray,
    group_key: str,
    min_group_calibration_n: int,
    weights: np.ndarray | None,
    min_group_weighted_ess: float | None,
    calibration_timestamp: str | None,
    calibration_data_hash: str | None,
) -> ConditionalCoverageDiagnostic:
    covered = None
    marginal = None
    if target is not None:
        covered = (target >= lower) & (target <= upper)
        marginal = _coverage_from_mask(covered)
    tail = _score_tail_diagnostic(scores, lower, upper, target)
    groups, support, shift = _group_estimates(
        group_labels,
        group_key,
        lower,
        upper,
        target,
        alpha,
        min_group_calibration_n,
        weights=weights,
        min_group_weighted_ess=min_group_weighted_ess,
    )
    status, failure_modes, action = _diagnostic_status(support, tail, shift, groups, alpha)
    return ConditionalCoverageDiagnostic(
        status=status,  # type: ignore[arg-type]
        target_coverage=1.0 - alpha,
        alpha=alpha,
        method_spec=_method_spec(
            family,
            base_model_family,
            alpha,
            int(np.asarray(scores).shape[0]),
            weighted=weights is not None,
            grouped=not np.all(group_labels == "__all__"),
            calibration_timestamp=calibration_timestamp,
            calibration_data_hash=calibration_data_hash,
        ),
        marginal=marginal,
        groups=groups,
        ert=None,
        shift=shift,
        score_tail=tail,
        calibration_support=support,
        graph=None,
        failure_modes=failure_modes,
        recommended_action=action,  # type: ignore[arg-type]
    )


def _ert_diagnostic(
    features: Any,
    covered: np.ndarray,
    alpha: float,
    n_splits: int,
    threshold: float,
    feature_names: Sequence[str] | None = None,
) -> ERTDiagnostic:
    x = np.asarray(features, dtype=float)
    covered_bool = np.asarray(covered, dtype=bool).reshape(-1)
    if x.ndim != 2 or x.shape[0] != covered_bool.shape[0] or covered_bool.shape[0] < 20:
        return ERTDiagnostic(
            evaluated=False,
            n_splits=0,
            feature_set=list(feature_names or []),
            classifier_family="not_available",
            status="not_enough_labels",
        )
    miscovered = (~covered_bool).astype(int)
    if np.unique(miscovered).shape[0] < 2:
        observed_gap = float(np.mean(miscovered) - alpha)
        return ERTDiagnostic(
            evaluated=True,
            n_splits=0,
            feature_set=list(feature_names or [f"x{idx}" for idx in range(x.shape[1])]),
            classifier_family="constant",
            ert_l1=abs(observed_gap),
            ert_l2=abs(observed_gap),
            ert_under=max(observed_gap, 0.0),
            ert_over=max(-observed_gap, 0.0),
            p_value=None,
            status="pass" if max(observed_gap, 0.0) <= threshold else "fail",
        )
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import StratifiedKFold
    except Exception:
        return ERTDiagnostic(
            evaluated=False,
            n_splits=0,
            feature_set=list(feature_names or []),
            classifier_family="sklearn_unavailable",
            status="not_enough_labels",
        )

    split_count = min(max(int(n_splits), 2), int(np.min(np.bincount(miscovered))))
    if split_count < 2:
        split_count = 2
    predictions = np.full(miscovered.shape[0], float(np.mean(miscovered)), dtype=float)
    cv = StratifiedKFold(n_splits=split_count, shuffle=True, random_state=17)
    for train_idx, test_idx in cv.split(x, miscovered):
        clf = RandomForestClassifier(n_estimators=80, max_depth=4, random_state=17)
        clf.fit(x[train_idx], miscovered[train_idx])
        predictions[test_idx] = clf.predict_proba(x[test_idx])[:, 1]
    local_gap = predictions - alpha
    ert_l1 = float(np.mean(np.abs(local_gap)))
    ert_l2 = float(np.sqrt(np.mean(local_gap**2)))
    ert_under = float(np.mean(np.maximum(local_gap, 0.0)))
    ert_over = float(np.mean(np.maximum(-local_gap, 0.0)))
    if ert_under > threshold:
        status = "fail"
    elif ert_l1 > threshold:
        status = "warn"
    else:
        status = "pass"
    return ERTDiagnostic(
        evaluated=True,
        n_splits=split_count,
        feature_set=list(feature_names or [f"x{idx}" for idx in range(x.shape[1])]),
        classifier_family="random_forest",
        ert_l1=ert_l1,
        ert_l2=ert_l2,
        ert_under=ert_under,
        ert_over=ert_over,
        p_value=None,
        status=status,  # type: ignore[arg-type]
    )


def _metadata_value(
    prediction_result: PredictionResult,
    params: Mapping[str, Any],
    key: str,
) -> Any:
    if key in params and params[key] is not None:
        return params[key]
    return prediction_result.metadata.get(key)


def _prediction_set_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("prediction_set", "json"),
                contract_id=PredictionSetResult.contract_id,
            )
        }
    )


def _lookup_params_from_state(
    state: Mapping[str, Any] | PredictionResult,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    state_params = (
        {key: value for key, value in state.items() if key != "prediction_result"}
        if isinstance(state, Mapping)
        else {}
    )
    lookup_params = dict(state_params)
    lookup_params.update({key: value for key, value in params.items() if value is not None})
    return lookup_params


def _numpy_like(value: Any) -> np.ndarray:
    candidate = value
    detach = getattr(candidate, "detach", None)
    if callable(detach):
        candidate = detach()
    cpu = getattr(candidate, "cpu", None)
    if callable(cpu):
        candidate = cpu()
    numpy = getattr(candidate, "numpy", None)
    if callable(numpy):
        candidate = numpy()
    return np.asarray(candidate)


def _softmax_matrix(logits: Any) -> np.ndarray:
    values = np.asarray(_numpy_like(logits), dtype=float)
    if values.ndim != 2:
        raise ValueError("class logits must be a 2D matrix")
    centered = values - np.max(values, axis=1, keepdims=True)
    exp_values = np.exp(centered)
    return exp_values / np.maximum(np.sum(exp_values, axis=1, keepdims=True), 1.0e-12)


def _normalize_probability_matrix(values: Any) -> np.ndarray:
    probs = np.asarray(_numpy_like(values), dtype=float)
    if probs.ndim != 2 or probs.shape[0] == 0 or probs.shape[1] < 2:
        raise ValueError(
            "class_probabilities must be a non-empty 2D matrix with at least 2 classes"
        )
    if not np.all(np.isfinite(probs)) or np.any(probs < 0.0):
        raise ValueError("class_probabilities must be finite and non-negative")
    row_sum = np.sum(probs, axis=1, keepdims=True)
    if np.any(row_sum <= 0.0):
        raise ValueError("class_probabilities rows must sum to a positive value")
    return probs / row_sum


def _classification_prediction_payload(
    state: Mapping[str, Any] | PredictionResult,
    lookup_params: Mapping[str, Any],
) -> PredictionResult:
    if isinstance(state, PredictionResult):
        return state
    if isinstance(state, Mapping) and (
        "prediction_result" in state or isinstance(state.get("result"), PredictionResult)
    ):
        return _prediction_payload(state)
    if "class_probabilities" not in lookup_params and "logits" not in lookup_params:
        return _prediction_payload(state)
    probabilities = (
        _softmax_matrix(lookup_params["logits"])
        if lookup_params.get("class_probabilities") is None
        and lookup_params.get("logits") is not None
        else _normalize_probability_matrix(lookup_params["class_probabilities"])
    )
    metadata = dict(lookup_params.get("metadata") or {})
    for key in (
        "group_values",
        "class_labels",
        "class_clusters",
        "community",
        "temporal_bin",
        "homophily_bin",
    ):
        if key in lookup_params and lookup_params[key] is not None:
            metadata[key] = lookup_params[key]
    metadata.setdefault("class_probabilities", probabilities)
    target = lookup_params.get("target")
    return PredictionResult(
        method_name=str(
            lookup_params.get("base_method", lookup_params.get("method_name", "classifier"))
        ),
        predictions=np.argmax(probabilities, axis=1),
        target=None if target is None else np.asarray(target),
        metadata=metadata,
    )


def _probability_matrix_from_sources(
    lookup_params: Mapping[str, Any],
    prediction_result: PredictionResult,
) -> np.ndarray:
    for key in ("class_probabilities", "probabilities", "probs", "predict_proba"):
        if lookup_params.get(key) is not None:
            return _normalize_probability_matrix(lookup_params[key])
        if prediction_result.metadata.get(key) is not None:
            return _normalize_probability_matrix(prediction_result.metadata[key])
    for key in ("logits", "class_logits"):
        if lookup_params.get(key) is not None:
            return _softmax_matrix(lookup_params[key])
        if prediction_result.metadata.get(key) is not None:
            return _softmax_matrix(prediction_result.metadata[key])
    raise ValueError("class_probabilities or logits are required for conformal classification")


def _label_indices(
    labels: Any,
    n_classes: int,
    class_labels: Sequence[Any] | None = None,
) -> np.ndarray:
    raw = np.asarray(labels).reshape(-1)
    if class_labels is not None:
        mapping = {str(value): idx for idx, value in enumerate(class_labels)}
        try:
            idx = np.asarray([mapping[str(value)] for value in raw], dtype=int)
        except KeyError as exc:
            raise ValueError(
                f"target label {exc.args[0]!r} is not present in class_labels"
            ) from exc
    else:
        idx = raw.astype(int)
    if np.any(idx < 0) or np.any(idx >= n_classes):
        raise ValueError("target labels must be class indices in [0, n_classes)")
    return idx


def _class_labels_from_params(
    lookup_params: Mapping[str, Any],
    prediction_result: PredictionResult,
    n_classes: int,
) -> list[Any] | None:
    labels = lookup_params.get("class_labels")
    if labels is None:
        labels = prediction_result.metadata.get("class_labels")
    if labels is None:
        return None
    result = list(labels)
    if len(result) != n_classes:
        raise ValueError("class_labels length must match probability columns")
    return result


def _class_clusters_from_params(
    lookup_params: Mapping[str, Any],
    prediction_result: PredictionResult,
    n_classes: int,
) -> list[str] | None:
    raw = lookup_params.get("class_clusters")
    if raw is None:
        raw = prediction_result.metadata.get("class_clusters")
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        clusters = [str(raw.get(idx, raw.get(str(idx), idx))) for idx in range(n_classes)]
    else:
        clusters = [str(value) for value in list(raw)]
    if len(clusters) != n_classes:
        raise ValueError("class_clusters must map every class")
    return clusters


def _aps_raps_score_matrix(
    probabilities: np.ndarray,
    *,
    score_type: str,
    raps_lambda: float,
    raps_k_reg: int,
) -> tuple[np.ndarray, np.ndarray]:
    probs = _normalize_probability_matrix(probabilities)
    n_obs, n_classes = probs.shape
    order = np.argsort(-probs, axis=1)
    sorted_probs = np.take_along_axis(probs, order, axis=1)
    cumulative = np.cumsum(sorted_probs, axis=1)
    rank_positions = np.arange(1, n_classes + 1, dtype=float)
    penalty = np.zeros(n_classes, dtype=float)
    if score_type == "raps":
        penalty = float(raps_lambda) * np.maximum(rank_positions - float(raps_k_reg), 0.0)
    sorted_scores = cumulative + penalty[None, :]
    scores = np.empty_like(sorted_scores)
    ranks = np.empty((n_obs, n_classes), dtype=int)
    for row in range(n_obs):
        scores[row, order[row]] = sorted_scores[row]
        ranks[row, order[row]] = np.arange(1, n_classes + 1, dtype=int)
    return scores, ranks


def _threshold_key(policy_value: str, condition_value: str | None) -> str:
    if condition_value is None:
        return f"group={policy_value}"
    return f"group={policy_value}|condition={condition_value}"


def _condition_for_class(
    class_idx: int,
    *,
    class_conditioning: str,
    predicted_label: int,
    class_clusters: Sequence[str] | None,
) -> str | None:
    if class_conditioning == "none":
        return None
    if class_conditioning == "predicted_label":
        return f"predicted_label={predicted_label}"
    if class_conditioning == "class_cluster":
        if class_clusters is None:
            return f"class={class_idx}"
        return f"class_cluster={class_clusters[class_idx]}"
    return f"class={class_idx}"


def _prediction_sets_from_scores(
    score_matrix: np.ndarray,
    probabilities: np.ndarray,
    thresholds: np.ndarray,
) -> list[list[int]]:
    sets: list[list[int]] = []
    top_labels = np.argmax(probabilities, axis=1)
    for row_idx in range(score_matrix.shape[0]):
        chosen = np.flatnonzero(score_matrix[row_idx] <= thresholds[row_idx]).astype(int).tolist()
        if not chosen:
            chosen = [int(top_labels[row_idx])]
        sets.append(sorted(dict.fromkeys(chosen)))
    return sets


def _prediction_set_coverage(
    prediction_sets: Sequence[Sequence[int]], labels: np.ndarray
) -> np.ndarray:
    return np.asarray(
        [
            int(label) in {int(value) for value in prediction_sets[idx]}
            for idx, label in enumerate(labels)
        ],
        dtype=bool,
    )


def _classification_tail_diagnostic(
    calibration_scores: np.ndarray,
    set_sizes: np.ndarray,
    n_classes: int,
) -> ScoreTailDiagnostic:
    scores = np.asarray(calibration_scores, dtype=float).reshape(-1)
    sizes = np.asarray(set_sizes, dtype=float).reshape(-1)
    q50, q90, q95, q99 = (float(np.quantile(scores, q)) for q in (0.5, 0.9, 0.95, 0.99))
    q99_q90_ratio = float(q99 / max(abs(q90), 1.0e-12))
    vacuity_rate = float(np.mean(sizes > 0.5 * float(n_classes)))
    median_size = float(np.median(sizes))
    p90_size = float(np.quantile(sizes, 0.9))
    status = "pass"
    if median_size > 0.5 * n_classes or p90_size > 0.8 * n_classes:
        status = "fail"
    elif vacuity_rate > 0.10 or p90_size > 0.5 * n_classes:
        status = "warn"
    return ScoreTailDiagnostic(
        score_q50=q50,
        score_q90=q90,
        score_q95=q95,
        score_q99=q99,
        q99_q90_ratio=q99_q90_ratio,
        hill_tail_index=None,
        vacuity_rate=vacuity_rate,
        median_interval_width=median_size,
        p90_interval_width=p90_size,
        status=status,  # type: ignore[arg-type]
    )


def _classification_group_estimates(
    group_labels: np.ndarray,
    group_key: str,
    prediction_sets: Sequence[Sequence[int]],
    set_sizes: np.ndarray,
    labels: np.ndarray | None,
    alpha: float,
    min_group_calibration_n: int,
    weights: np.ndarray | None = None,
    min_group_weighted_ess: float | None = None,
) -> tuple[list[GroupCoverageEstimate], CalibrationSupportDiagnostic, ShiftDiagnostic | None]:
    groups: list[GroupCoverageEstimate] = []
    group_arr = np.asarray(group_labels, dtype=str).reshape(-1)
    sizes = np.asarray(set_sizes, dtype=float).reshape(-1)
    groups_below: list[str] = []
    ess_by_group: dict[str, float] = {}
    covered = None if labels is None else _prediction_set_coverage(prediction_sets, labels)
    for group in sorted(set(group_arr.tolist())):
        mask = group_arr == group
        n_group = int(np.sum(mask))
        group_ess = None
        if weights is not None:
            group_ess = _effective_sample_size(weights[mask])
            ess_by_group[group] = float(group_ess)
        supported, support_status = _support_status(
            n_group,
            min_group_calibration_n,
            group_ess,
            min_group_weighted_ess,
        )
        if not supported:
            groups_below.append(group)
        coverage = ci_low = ci_high = shortfall = None
        n_eval = None
        if covered is not None:
            estimate = _coverage_from_mask(covered[mask])
            coverage = estimate.coverage
            ci_low = estimate.ci_low
            ci_high = estimate.ci_high
            shortfall = max((1.0 - alpha) - coverage, 0.0)
            n_eval = n_group
        groups.append(
            GroupCoverageEstimate(
                group_key=group_key,
                group_value=group,
                n_calibration=n_group,
                n_evaluation=n_eval,
                coverage=coverage,
                ci_low=ci_low,
                ci_high=ci_high,
                median_width=float(np.median(sizes[mask])) if n_group else None,
                p90_width=float(np.quantile(sizes[mask], 0.9)) if n_group else None,
                shortfall=shortfall,
                guarantee_supported=supported,
                support_status=support_status,  # type: ignore[arg-type]
            )
        )
    support = CalibrationSupportDiagnostic(
        n_calibration_total=int(group_arr.shape[0]),
        min_group_calibration_n=int(min_group_calibration_n),
        min_group_weighted_ess=float(min(ess_by_group.values())) if ess_by_group else None,
        groups_below_min_support=groups_below,
        unsupported_groups_seen=[],
        status="warn" if groups_below else "pass",
    )
    shift = None
    if weights is not None:
        ess = _effective_sample_size(weights)
        ratio = ess / max(float(group_arr.shape[0]), 1.0)
        shift_status = "fail" if ratio < 0.15 else "warn" if ratio < 0.30 else "pass"
        shift = ShiftDiagnostic(
            evaluated=True,
            calibration_vs_deployment_auc=None,
            psi_max=None,
            mmd=None,
            density_ratio_ess=float(ess),
            density_ratio_ess_by_group=ess_by_group,
            unseen_category_rate=None,
            status=shift_status,  # type: ignore[arg-type]
        )
    return groups, support, shift


def _classification_diagnostic(
    *,
    family: str,
    base_model_family: str,
    alpha: float,
    calibration_scores: np.ndarray,
    prediction_sets: Sequence[Sequence[int]],
    set_sizes: np.ndarray,
    labels: np.ndarray | None,
    group_labels: np.ndarray,
    group_key: str,
    n_classes: int,
    min_group_calibration_n: int,
    weights: np.ndarray | None,
    min_group_weighted_ess: float | None,
    class_conditional: bool,
) -> ConditionalCoverageDiagnostic:
    covered = None if labels is None else _prediction_set_coverage(prediction_sets, labels)
    marginal = None if covered is None else _coverage_from_mask(covered)
    tail = _classification_tail_diagnostic(calibration_scores, set_sizes, n_classes)
    groups, support, shift = _classification_group_estimates(
        group_labels,
        group_key,
        prediction_sets,
        set_sizes,
        labels,
        alpha,
        min_group_calibration_n,
        weights=weights,
        min_group_weighted_ess=min_group_weighted_ess,
    )
    status, failure_modes, action = _diagnostic_status(support, tail, shift, groups, alpha)
    return ConditionalCoverageDiagnostic(
        status=status,  # type: ignore[arg-type]
        target_coverage=1.0 - alpha,
        alpha=alpha,
        method_spec=_method_spec(
            family,
            base_model_family,
            alpha,
            int(np.asarray(calibration_scores).shape[0]),
            weighted=weights is not None,
            grouped=not np.all(np.asarray(group_labels, dtype=str) == "group=__all__"),
            class_conditional=class_conditional,
        ),
        marginal=marginal,
        groups=groups,
        ert=None,
        shift=shift,
        score_tail=tail,
        calibration_support=support,
        graph=None,
        failure_modes=failure_modes,
        recommended_action=action,  # type: ignore[arg-type]
    )


def _classification_metrics(
    prediction_sets: Sequence[Sequence[int]],
    labels: np.ndarray,
    n_classes: int,
    alpha: float,
    rare_class_threshold: int,
) -> dict[str, Any]:
    covered = _prediction_set_coverage(prediction_sets, labels)
    per_class: dict[str, float] = {}
    class_counts: dict[str, int] = {}
    rare_shortfalls: list[float] = []
    for class_idx in range(n_classes):
        mask = labels == class_idx
        count = int(np.sum(mask))
        class_counts[str(class_idx)] = count
        if count == 0:
            continue
        class_cov = float(np.mean(covered[mask]))
        per_class[str(class_idx)] = class_cov
        if count < rare_class_threshold:
            rare_shortfalls.append(max((1.0 - alpha) - class_cov, 0.0))
    return {
        "macro_coverage": float(np.mean(list(per_class.values()))) if per_class else None,
        "coverage_by_class": per_class,
        "class_counts": class_counts,
        "rare_class_shortfall": float(max(rare_shortfalls)) if rare_shortfalls else 0.0,
    }


def _adjacency_matrix_from_sources(
    lookup_params: Mapping[str, Any],
    prediction_result: PredictionResult,
) -> np.ndarray:
    value = lookup_params.get("adjacency_matrix")
    if value is None:
        value = prediction_result.metadata.get("adjacency_matrix")
    if value is None:
        raise ValueError("graph-aware conformal prediction requires adjacency_matrix")
    adjacency = np.asarray(_numpy_like(value), dtype=float)
    if adjacency.ndim != 2 or adjacency.shape[0] != adjacency.shape[1]:
        raise ValueError("adjacency_matrix must be square")
    if not np.all(np.isfinite(adjacency)):
        raise ValueError("adjacency_matrix must contain finite values")
    return np.maximum(adjacency, 0.0)


def _row_normalized_adjacency(adjacency: np.ndarray) -> np.ndarray:
    graph = np.asarray(adjacency, dtype=float)
    graph = graph + np.eye(graph.shape[0], dtype=float)
    row_sum = np.sum(graph, axis=1, keepdims=True)
    return graph / np.maximum(row_sum, 1.0e-12)


def _feature_similarity_matrix(features: Any, k_neighbors: int = 8) -> np.ndarray:
    x = np.asarray(_numpy_like(features), dtype=float)
    if x.ndim != 2:
        raise ValueError("node_features must be a 2D matrix")
    centered = x - np.mean(x, axis=0, keepdims=True)
    norm = np.linalg.norm(centered, axis=1, keepdims=True)
    normalized = centered / np.maximum(norm, 1.0e-12)
    similarity = np.maximum(normalized @ normalized.T, 0.0)
    np.fill_diagonal(similarity, 1.0)
    if k_neighbors > 0 and k_neighbors < similarity.shape[0]:
        keep = np.zeros_like(similarity, dtype=bool)
        order = np.argsort(-similarity, axis=1)[:, : k_neighbors + 1]
        for row in range(similarity.shape[0]):
            keep[row, order[row]] = True
        similarity = np.where(keep, similarity, 0.0)
    row_sum = np.sum(similarity, axis=1, keepdims=True)
    return similarity / np.maximum(row_sum, 1.0e-12)


def _graph_smoothed_scores(
    score_matrix: np.ndarray,
    adjacency: np.ndarray,
    lookup_params: Mapping[str, Any],
) -> tuple[np.ndarray, str]:
    method = str(lookup_params.get("graph_method", "daps")).strip().lower() or "daps"
    smoothing = min(max(float(lookup_params.get("graph_smoothing", 0.35)), 0.0), 1.0)
    if method in {"none", "vanilla"} or smoothing <= 0.0:
        return score_matrix, "none"
    graph_kernel = _row_normalized_adjacency(adjacency)
    if method == "snaps" and lookup_params.get("node_features") is not None:
        feature_kernel = _feature_similarity_matrix(
            lookup_params["node_features"],
            k_neighbors=max(1, int(lookup_params.get("similarity_neighbors", 8))),
        )
        graph_kernel = 0.5 * graph_kernel + 0.5 * feature_kernel
        graph_kernel = graph_kernel / np.maximum(
            np.sum(graph_kernel, axis=1, keepdims=True), 1.0e-12
        )
    smoothed = (1.0 - smoothing) * score_matrix + smoothing * (graph_kernel @ score_matrix)
    return smoothed, method


def _corrected_graph_probabilities(
    probabilities: np.ndarray,
    lookup_params: Mapping[str, Any],
) -> tuple[np.ndarray, bool]:
    if lookup_params.get("corrected_class_probabilities") is not None:
        return _normalize_probability_matrix(lookup_params["corrected_class_probabilities"]), True
    if lookup_params.get("topology_correction") is None:
        return probabilities, False
    correction = np.asarray(_numpy_like(lookup_params["topology_correction"]), dtype=float)
    if correction.shape != probabilities.shape:
        raise ValueError("topology_correction must match class_probabilities shape")
    logits = np.log(np.maximum(probabilities, 1.0e-12)) + correction
    return _softmax_matrix(logits), True


def _connected_components(adjacency: np.ndarray) -> np.ndarray:
    graph = np.asarray(adjacency, dtype=float) > 0.0
    n_nodes = graph.shape[0]
    labels = np.full(n_nodes, -1, dtype=int)
    component = 0
    for start in range(n_nodes):
        if labels[start] >= 0:
            continue
        stack = [start]
        labels[start] = component
        while stack:
            node = stack.pop()
            neighbors = np.flatnonzero(graph[node] | graph[:, node])
            for neighbor in neighbors:
                if labels[neighbor] < 0:
                    labels[neighbor] = component
                    stack.append(int(neighbor))
        component += 1
    return labels


def _degree_bins(adjacency: np.ndarray) -> np.ndarray:
    degree = np.sum(np.asarray(adjacency, dtype=float) > 0.0, axis=1)
    if np.all(degree == degree[0]):
        return np.asarray([f"degree={int(value)}" for value in degree], dtype=object)
    q33, q66 = np.quantile(degree, [0.33, 0.66])
    labels = []
    for value in degree:
        if value <= 0:
            labels.append("isolated")
        elif value <= q33:
            labels.append("low_degree")
        elif value <= q66:
            labels.append("mid_degree")
        else:
            labels.append("high_degree")
    return np.asarray(labels, dtype=object)


def _homophily_bins(adjacency: np.ndarray, labels: np.ndarray | None) -> np.ndarray:
    if labels is None:
        return np.full(adjacency.shape[0], "homophily_not_available", dtype=object)
    graph = np.asarray(adjacency, dtype=float) > 0.0
    result: list[str] = []
    for row in range(graph.shape[0]):
        neighbors = np.flatnonzero(graph[row])
        if neighbors.size == 0:
            result.append("homophily_isolated")
            continue
        same_rate = float(np.mean(labels[neighbors] == labels[row]))
        if same_rate < 0.33:
            result.append("low_homophily")
        elif same_rate < 0.66:
            result.append("mid_homophily")
        else:
            result.append("high_homophily")
    return np.asarray(result, dtype=object)


def _graph_group_estimates(
    labels: np.ndarray,
    group_key: str,
    prediction_sets: Sequence[Sequence[int]],
    set_sizes: np.ndarray,
    target: np.ndarray,
    alpha: float,
    min_graph_effective_sample_size: int,
) -> list[GroupCoverageEstimate]:
    groups, _, _ = _classification_group_estimates(
        labels,
        group_key,
        prediction_sets,
        set_sizes,
        target,
        alpha,
        min_graph_effective_sample_size,
    )
    return groups


def _graph_coverage_diagnostic(
    *,
    adjacency: np.ndarray,
    prediction_sets: Sequence[Sequence[int]],
    set_sizes: np.ndarray,
    target: np.ndarray,
    alpha: float,
    lookup_params: Mapping[str, Any],
    min_graph_effective_sample_size: int,
) -> GraphCoverageDiagnostic:
    n_nodes = adjacency.shape[0]
    degree_groups = _degree_bins(adjacency)
    community = lookup_params.get("community")
    if community is None:
        community = lookup_params.get("community_labels")
    if community is None:
        community = _connected_components(adjacency)
    community_groups = np.asarray(
        [f"community={value}" for value in np.asarray(community).reshape(-1)]
    )
    if community_groups.shape[0] != n_nodes:
        raise ValueError("community labels must align with graph nodes")
    temporal = lookup_params.get("temporal_bin")
    if temporal is None:
        temporal = lookup_params.get("node_time")
    temporal_groups = (
        np.full(n_nodes, "temporal_not_available", dtype=object)
        if temporal is None
        else np.asarray([f"temporal={value}" for value in np.asarray(temporal).reshape(-1)])
    )
    if temporal_groups.shape[0] != n_nodes:
        raise ValueError("temporal bins must align with graph nodes")
    homophily_groups = _homophily_bins(adjacency, target)
    all_groups = [
        *_graph_group_estimates(
            degree_groups,
            "degree_bin",
            prediction_sets,
            set_sizes,
            target,
            alpha,
            min_graph_effective_sample_size,
        ),
        *_graph_group_estimates(
            community_groups,
            "community",
            prediction_sets,
            set_sizes,
            target,
            alpha,
            min_graph_effective_sample_size,
        ),
        *_graph_group_estimates(
            homophily_groups,
            "homophily_bin",
            prediction_sets,
            set_sizes,
            target,
            alpha,
            min_graph_effective_sample_size,
        ),
        *_graph_group_estimates(
            temporal_groups,
            "temporal_bin",
            prediction_sets,
            set_sizes,
            target,
            alpha,
            min_graph_effective_sample_size,
        ),
    ]
    unsupported = [group for group in all_groups if not group.guarantee_supported]
    exchangeability_status = "warn" if unsupported else "pass"
    if len(unsupported) > max(1, len(all_groups) // 2):
        exchangeability_status = "fail"
    return GraphCoverageDiagnostic(
        graph_id=None if lookup_params.get("graph_id") is None else str(lookup_params["graph_id"]),
        node_or_graph_level="node",
        degree_bin_coverage=_graph_group_estimates(
            degree_groups,
            "degree_bin",
            prediction_sets,
            set_sizes,
            target,
            alpha,
            min_graph_effective_sample_size,
        ),
        community_coverage=_graph_group_estimates(
            community_groups,
            "community",
            prediction_sets,
            set_sizes,
            target,
            alpha,
            min_graph_effective_sample_size,
        ),
        homophily_bin_coverage=_graph_group_estimates(
            homophily_groups,
            "homophily_bin",
            prediction_sets,
            set_sizes,
            target,
            alpha,
            min_graph_effective_sample_size,
        ),
        temporal_bin_coverage=_graph_group_estimates(
            temporal_groups,
            "temporal_bin",
            prediction_sets,
            set_sizes,
            target,
            alpha,
            min_graph_effective_sample_size,
        ),
        block_bootstrap_ci_used=False,
        effective_sample_size=int(n_nodes),
        exchangeability_proxy_status=exchangeability_status,  # type: ignore[arg-type]
    )


@foundry_method(
    namespace="ml.uncertainty",
    version="1.0.0",
    tags={"ml", "uncertainty", "conformal-prediction"},
)
class ConformalPredictionEstimator:
    """Build split-conformal prediction intervals under exchangeability; avoid nonstationary test distributions without recalibration."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="conformal_prediction",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "prediction_result",
                    SlotType.SCALAR,
                    Unit("prediction", "json"),
                    contract_id=PredictionResult.contract_id,
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("prediction_interval", "json"),
                    contract_id=PredictionIntervalResult.contract_id,
                ),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="alpha", default=0.1),
            ParameterSpec(name="shift_mode", default="standard"),
            ParameterSpec(name="importance_weights", default=None),
            ParameterSpec(name="min_effective_sample_size", default=10.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Split-conformal style residual intervals over an upstream prediction result.",
        tags=frozenset({"ml", "uncertainty", "conformal-prediction"}),
        declared_truthfulness_tier="exact",
        truthfulness_scope="marginal_coverage",
        when_to_use="Distribution-free prediction intervals with coverage guarantee; any black-box model",
        citations=(
            "Vovk, V., Gammerman, A. & Shafer, G. (2005). Algorithmic Learning in a Random World. Springer.",
            "Romano, Y., Patterson, E. & Candes, E. (2019). Conformalized quantile regression. NeurIPS, 32.",
        ),
        when_not_to_use="Need conditional coverage (use CQR); calibration set too small (<50 obs)",
        output_interpretation="Prediction set with 1-α marginal coverage guarantee. Width indicates uncertainty.",
        typical_min_obs=50,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PredictionResult:
        if "prediction_result" in bound_inputs:
            return _prediction_payload(bound_inputs["prediction_result"])
        return _prediction_payload(fallback_state)

    @staticmethod
    def pure_step(
        state: PredictionResult | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        prediction_result = (
            state if isinstance(state, PredictionResult) else PredictionResult.model_validate(state)
        )
        if prediction_result.target is None:
            raise ValueError("conformal_prediction requires target values in PredictionResult")

        alpha = float(params.get("alpha", 0.1))
        if not (0.0 < alpha < 1.0):
            raise ValueError("alpha must be in (0, 1)")
        shift_mode = str(params.get("shift_mode", "standard")).strip().lower() or "standard"
        if shift_mode not in {"standard", "weighted", "adaptive"}:
            raise ValueError("shift_mode must be one of: standard, weighted, adaptive")
        residual = np.abs(
            np.asarray(prediction_result.target, dtype=float)
            - np.asarray(prediction_result.predictions, dtype=float)
        )
        importance_weights = params.get("importance_weights")
        if importance_weights is None:
            importance_weights = prediction_result.metadata.get("importance_weights")

        ess: float | None = None
        weights_for_diag: np.ndarray | None = None
        q_hat: float
        if shift_mode == "standard":
            q_hat = _higher_quantile(residual, _conformal_quantile_level(residual.shape[0], alpha))
        else:
            if importance_weights is None:
                raise ValueError(
                    "shift-aware conformal prediction requires importance_weights in params "
                    "or PredictionResult.metadata"
                )
            weights = np.asarray(importance_weights, dtype=float).reshape(-1)
            if weights.shape[0] != residual.shape[0]:
                raise ValueError("importance_weights must align with prediction residuals")
            if not np.all(np.isfinite(weights)) or np.any(weights < 0.0):
                raise ValueError("importance_weights must be finite and non-negative")
            if shift_mode == "adaptive":
                positive = weights[weights > 0.0]
                if positive.size == 0:
                    raise ValueError(
                        "adaptive shift mode requires at least one positive importance weight"
                    )
                lower_clip = float(np.quantile(positive, 0.05))
                upper_clip = float(np.quantile(positive, 0.95))
                weights = np.clip(weights, lower_clip, upper_clip)
            if float(np.sum(weights)) <= 0.0:
                raise ValueError("importance_weights must sum to a positive value")
            ess = _effective_sample_size(weights)
            min_ess = max(float(params.get("min_effective_sample_size", 10.0)), 1.0)
            if ess < min_ess:
                raise ValueError(
                    f"shift-aware conformal effective sample size {ess:.3f} is below "
                    f"min_effective_sample_size={min_ess:.3f}"
                )
            weights_for_diag = weights
            q_hat = _weighted_quantile(
                residual,
                _conformal_quantile_level(residual.shape[0], alpha),
                weights,
            )
        predictions = np.asarray(prediction_result.predictions, dtype=float)
        lower = predictions - q_hat
        upper = predictions + q_hat
        target = np.asarray(prediction_result.target, dtype=float)
        coverage = float(np.mean((target >= lower) & (target <= upper)))
        group_labels, group_key = _group_payload(params, prediction_result, residual.shape[0])
        min_group_calibration_n = int(params.get("min_calibration_per_group", 50))
        diagnostic = _build_conditional_diagnostic(
            family="split_residual",
            base_model_family=prediction_result.method_name,
            alpha=alpha,
            scores=residual,
            lower=lower,
            upper=upper,
            target=target,
            group_labels=group_labels,
            group_key=group_key,
            min_group_calibration_n=min_group_calibration_n,
            weights=weights_for_diag,
            min_group_weighted_ess=float(params.get("min_group_weighted_ess", 10.0))
            if weights_for_diag is not None
            else None,
            calibration_timestamp=params.get("calibration_timestamp"),
            calibration_data_hash=params.get("calibration_data_hash"),
        )

        result = PredictionIntervalResult(
            method_name="conformal_prediction",
            predictions=predictions,
            lower=lower,
            upper=upper,
            coverage=coverage,
            alpha=alpha,
            conditional_coverage_diagnostic=diagnostic,
            truthfulness_receipt=TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.EXACT,
                truthfulness_scope=TruthfulnessScope.MARGINAL_COVERAGE,
                diagnostics={
                    "observed_coverage": coverage,
                    "alpha": alpha,
                    "effective_sample_size": ess,
                    "shift_mode": shift_mode,
                },
            ),
            metadata={
                "base_method": prediction_result.method_name,
                "residual_quantile": q_hat,
                "shift_mode": shift_mode,
                "effective_sample_size": ess,
                "distribution_shift_adjusted": shift_mode != "standard",
            },
        )
        return {
            "result": result,
            "uncertainty_envelope": prediction_result.to_uncertainty_envelope(),
        }


def _prediction_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("prediction_interval", "json"),
                contract_id=PredictionIntervalResult.contract_id,
            ),
            SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
        }
    )


@foundry_method(
    namespace="ml.uncertainty",
    version="1.0.0",
    tags={"ml", "uncertainty", "conformal-prediction", "cqr", "mondrian"},
)
class MondrianCQRConformalizer:
    """Conformalize tabular quantile heads with group-aware Mondrian thresholds."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="mondrian_cqr",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "prediction_result",
                    SlotType.SCALAR,
                    Unit("prediction", "json"),
                    contract_id=PredictionResult.contract_id,
                ),
                SlotSpec(
                    "lower_quantile_predictions",
                    SlotType.VECTOR,
                    Unit("target", "value"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "upper_quantile_predictions",
                    SlotType.VECTOR,
                    Unit("target", "value"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="target_coverage", default=None),
            ParameterSpec(name="group_values", default=None),
            ParameterSpec(name="group_keys", default=None),
            ParameterSpec(name="importance_weights", default=None),
            ParameterSpec(name="min_calibration_per_group", default=400),
            ParameterSpec(name="min_group_weighted_ess", default=300.0),
            ParameterSpec(name="fail_on_unsupported_group", default=False),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Mondrian conformalized quantile regression for adaptive tabular prediction intervals.",
        tags=frozenset({"ml", "uncertainty", "conformal-prediction", "cqr", "mondrian"}),
        declared_truthfulness_tier="exact",
        truthfulness_scope="conditional_coverage",
        when_to_use="FT-Transformer, TabNet, or other tabular regressors exposing lower/upper quantile heads.",
        citations=(
            "Romano, Y., Patterson, E. & Candes, E. (2019). Conformalized quantile regression. NeurIPS, 32.",
        ),
        when_not_to_use=(
            "Quantile heads are unavailable, groups have insufficient calibration support, "
            "or conditional coverage is needed outside declared finite groups."
        ),
        output_interpretation=(
            "Intervals have finite-sample marginal coverage and group-conditional coverage "
            "for supported Mondrian groups under exchangeability."
        ),
        typical_min_obs=400,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = dict(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        if "prediction_result" not in payload:
            payload["prediction_result"] = fallback_state
        return payload

    @staticmethod
    def pure_step(
        state: Mapping[str, Any] | PredictionResult, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        prediction_result = _prediction_payload(state)
        state_params = (
            {key: value for key, value in state.items() if key != "prediction_result"}
            if isinstance(state, Mapping)
            else {}
        )
        lookup_params = dict(state_params)
        lookup_params.update({key: value for key, value in params.items() if value is not None})
        if prediction_result.target is None:
            raise ValueError("mondrian_cqr requires target values in PredictionResult")
        alpha = _alpha_from_params(lookup_params, default=0.05)
        target = _as_1d_float("target", prediction_result.target)
        predictions = _as_1d_float("predictions", prediction_result.predictions)
        q_lower = _array_from_sources(
            "lower_quantile_predictions",
            lookup_params,
            prediction_result,
            (
                "lower_quantile_predictions",
                "lower_quantile",
                "quantile_lower",
                "q_lower",
            ),
        )
        q_upper = _array_from_sources(
            "upper_quantile_predictions",
            lookup_params,
            prediction_result,
            (
                "upper_quantile_predictions",
                "upper_quantile",
                "quantile_upper",
                "q_upper",
            ),
        )
        if not (q_lower.shape[0] == q_upper.shape[0] == target.shape[0] == predictions.shape[0]):
            raise ValueError("quantile predictions, point predictions, and targets must align")
        q_low = np.minimum(q_lower, q_upper)
        q_high = np.maximum(q_lower, q_upper)
        raw_scores = np.maximum(q_low - target, target - q_high)
        scores = np.maximum(raw_scores, 0.0)
        group_labels, group_key = _group_payload(lookup_params, prediction_result, target.shape[0])
        weights = _as_optional_weights(lookup_params, prediction_result, target.shape[0])
        min_group_calibration_n = int(lookup_params.get("min_calibration_per_group", 400))
        min_group_weighted_ess = float(lookup_params.get("min_group_weighted_ess", 300.0))
        quantile_engine = WeightedConformalQuantile(
            alpha=alpha,
            min_effective_sample_size=max(
                1.0, float(lookup_params.get("min_effective_sample_size", 1.0))
            ),
        )

        global_q, _ = quantile_engine.quantile(scores, weights)
        thresholds: dict[str, float] = {}
        ess_by_group: dict[str, float] = {}
        label_strings = group_labels.astype(str)
        for group in sorted({str(value) for value in label_strings}):
            mask = label_strings == group
            if weights is None:
                group_q, group_ess = quantile_engine.quantile(scores[mask], None)
            else:
                group_q, group_ess = quantile_engine.quantile(scores[mask], weights[mask])
            thresholds[group] = group_q
            if group_ess is not None:
                ess_by_group[group] = group_ess

        row_q = np.asarray([thresholds.get(str(group), global_q) for group in label_strings])
        lower = q_low - row_q
        upper = q_high + row_q
        coverage = float(np.mean((target >= lower) & (target <= upper)))
        diagnostic = _build_conditional_diagnostic(
            family="weighted_cqr" if weights is not None else "mondrian_cqr",
            base_model_family=prediction_result.method_name,
            alpha=alpha,
            scores=scores,
            lower=lower,
            upper=upper,
            target=target,
            group_labels=group_labels,
            group_key=group_key,
            min_group_calibration_n=min_group_calibration_n,
            weights=weights,
            min_group_weighted_ess=min_group_weighted_ess if weights is not None else None,
            calibration_timestamp=_metadata_value(
                prediction_result, lookup_params, "calibration_timestamp"
            ),
            calibration_data_hash=_metadata_value(
                prediction_result, lookup_params, "calibration_data_hash"
            ),
        )
        if (
            bool(lookup_params.get("fail_on_unsupported_group", False))
            and diagnostic.status == "unsupported"
        ):
            raise ValueError(
                "mondrian_cqr cannot claim group-conditional coverage for unsupported groups: "
                + ", ".join(diagnostic.calibration_support.groups_below_min_support)
            )
        degradation_reasons = tuple(diagnostic.failure_modes)
        result = PredictionIntervalResult(
            method_name="mondrian_cqr",
            predictions=predictions,
            lower=lower,
            upper=upper,
            coverage=coverage,
            alpha=alpha,
            conditional_coverage_diagnostic=diagnostic,
            truthfulness_receipt=TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.EXACT
                if diagnostic.status not in {"unsupported", "fail"}
                else TruthfulnessTier.UNVERIFIED,
                truthfulness_scope=TruthfulnessScope.CONDITIONAL_COVERAGE,
                diagnostics={
                    "observed_coverage": coverage,
                    "alpha": alpha,
                    "group_key": group_key,
                    "diagnostic_status": diagnostic.status,
                },
                degradation_reasons=degradation_reasons,
            ),
            metadata={
                "base_method": prediction_result.method_name,
                "group_key": group_key,
                "global_residual_quantile": global_q,
                "group_residual_quantiles": thresholds,
                "group_effective_sample_size": ess_by_group,
                "nonnegative_cqr_scores": True,
                "distribution_shift_adjusted": weights is not None,
            },
        )
        return {
            "result": result,
            "uncertainty_envelope": prediction_result.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="ml.uncertainty",
    version="1.0.0",
    tags={"ml", "uncertainty", "conformal-prediction", "normalized-residual", "mondrian"},
)
class NormalizedResidualMondrianConformalizer:
    """Fallback Mondrian conformalizer for models that expose a residual-scale estimate."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="normalized_residual_mondrian",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "prediction_result",
                    SlotType.SCALAR,
                    Unit("prediction", "json"),
                    contract_id=PredictionResult.contract_id,
                ),
                SlotSpec(
                    "residual_scale",
                    SlotType.VECTOR,
                    Unit("target", "scale"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=_prediction_output_slots(),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="target_coverage", default=None),
            ParameterSpec(name="group_values", default=None),
            ParameterSpec(name="group_keys", default=None),
            ParameterSpec(name="residual_scale", default=None),
            ParameterSpec(name="importance_weights", default=None),
            ParameterSpec(name="min_calibration_per_group", default=400),
            ParameterSpec(name="min_group_weighted_ess", default=300.0),
            ParameterSpec(name="scale_floor", default=1e-8),
            ParameterSpec(name="fail_on_unsupported_group", default=False),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Mondrian normalized-residual conformal intervals for tabular regressors without quantile heads.",
        tags=frozenset(
            {"ml", "uncertainty", "conformal-prediction", "normalized-residual", "mondrian"}
        ),
        declared_truthfulness_tier="exact",
        truthfulness_scope="conditional_coverage",
        when_to_use=(
            "FT-Transformer, TabNet, or other regressors without quantile heads but with "
            "a separately trained residual-scale model."
        ),
        citations=(
            "Vovk, V., Gammerman, A. & Shafer, G. (2005). Algorithmic Learning in a Random World. Springer.",
        ),
        when_not_to_use="Residual scale is unavailable or group support is too sparse; prefer Mondrian-CQR when quantile heads exist.",
        output_interpretation=(
            "Intervals scale a group-specific conformal residual quantile by each row's "
            "residual-scale estimate."
        ),
        typical_min_obs=400,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = dict(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        if "prediction_result" not in payload:
            payload["prediction_result"] = fallback_state
        return payload

    @staticmethod
    def pure_step(
        state: Mapping[str, Any] | PredictionResult, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        prediction_result = _prediction_payload(state)
        state_params = (
            {key: value for key, value in state.items() if key != "prediction_result"}
            if isinstance(state, Mapping)
            else {}
        )
        lookup_params = dict(state_params)
        lookup_params.update({key: value for key, value in params.items() if value is not None})
        if prediction_result.target is None:
            raise ValueError("normalized_residual_mondrian requires target values")
        alpha = _alpha_from_params(lookup_params, default=0.05)
        target = _as_1d_float("target", prediction_result.target)
        predictions = _as_1d_float("predictions", prediction_result.predictions)
        if target.shape[0] != predictions.shape[0]:
            raise ValueError("predictions and target must align")

        scale_source = "provided"
        try:
            scale = _array_from_sources(
                "residual_scale",
                lookup_params,
                prediction_result,
                (
                    "residual_scale",
                    "predictive_scale",
                    "sigma_hat",
                    "residual_sigma",
                ),
            )
        except ValueError:
            residual = np.abs(target - predictions)
            robust_scale = float(np.median(residual))
            if robust_scale <= 1.0e-12:
                robust_scale = float(np.mean(residual))
            if robust_scale <= 1.0e-12:
                robust_scale = 1.0
            scale = np.full(target.shape[0], robust_scale, dtype=float)
            scale_source = "global_residual_fallback"
        if scale.shape[0] == 1:
            scale = np.full(target.shape[0], float(scale[0]), dtype=float)
        if scale.shape[0] != target.shape[0]:
            raise ValueError("residual_scale must be scalar or align with prediction length")
        scale_floor = max(float(lookup_params.get("scale_floor", 1.0e-8)), 1.0e-12)
        scale = np.maximum(scale, scale_floor)
        scores = np.abs(target - predictions) / scale
        group_labels, group_key = _group_payload(lookup_params, prediction_result, target.shape[0])
        weights = _as_optional_weights(lookup_params, prediction_result, target.shape[0])
        min_group_calibration_n = int(lookup_params.get("min_calibration_per_group", 400))
        min_group_weighted_ess = float(lookup_params.get("min_group_weighted_ess", 300.0))
        quantile_engine = WeightedConformalQuantile(
            alpha=alpha,
            min_effective_sample_size=max(
                1.0, float(lookup_params.get("min_effective_sample_size", 1.0))
            ),
        )

        global_q, _ = quantile_engine.quantile(scores, weights)
        thresholds: dict[str, float] = {}
        ess_by_group: dict[str, float] = {}
        label_strings = group_labels.astype(str)
        for group in sorted({str(value) for value in label_strings}):
            mask = label_strings == group
            if weights is None:
                group_q, group_ess = quantile_engine.quantile(scores[mask], None)
            else:
                group_q, group_ess = quantile_engine.quantile(scores[mask], weights[mask])
            thresholds[group] = group_q
            if group_ess is not None:
                ess_by_group[group] = group_ess
        row_q = np.asarray([thresholds.get(str(group), global_q) for group in label_strings])
        lower = predictions - row_q * scale
        upper = predictions + row_q * scale
        coverage = float(np.mean((target >= lower) & (target <= upper)))
        diagnostic = _build_conditional_diagnostic(
            family="mondrian_normalized_residual",
            base_model_family=prediction_result.method_name,
            alpha=alpha,
            scores=scores,
            lower=lower,
            upper=upper,
            target=target,
            group_labels=group_labels,
            group_key=group_key,
            min_group_calibration_n=min_group_calibration_n,
            weights=weights,
            min_group_weighted_ess=min_group_weighted_ess if weights is not None else None,
            calibration_timestamp=_metadata_value(
                prediction_result, lookup_params, "calibration_timestamp"
            ),
            calibration_data_hash=_metadata_value(
                prediction_result, lookup_params, "calibration_data_hash"
            ),
        )
        if (
            bool(lookup_params.get("fail_on_unsupported_group", False))
            and diagnostic.status == "unsupported"
        ):
            raise ValueError(
                "normalized_residual_mondrian cannot claim group-conditional coverage "
                "for unsupported groups: "
                + ", ".join(diagnostic.calibration_support.groups_below_min_support)
            )

        result = PredictionIntervalResult(
            method_name="normalized_residual_mondrian",
            predictions=predictions,
            lower=lower,
            upper=upper,
            coverage=coverage,
            alpha=alpha,
            conditional_coverage_diagnostic=diagnostic,
            truthfulness_receipt=TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.EXACT
                if diagnostic.status not in {"unsupported", "fail"}
                else TruthfulnessTier.UNVERIFIED,
                truthfulness_scope=TruthfulnessScope.CONDITIONAL_COVERAGE,
                diagnostics={
                    "observed_coverage": coverage,
                    "alpha": alpha,
                    "group_key": group_key,
                    "diagnostic_status": diagnostic.status,
                    "scale_source": scale_source,
                },
                degradation_reasons=tuple(diagnostic.failure_modes),
            ),
            metadata={
                "base_method": prediction_result.method_name,
                "group_key": group_key,
                "global_normalized_residual_quantile": global_q,
                "group_normalized_residual_quantiles": thresholds,
                "group_effective_sample_size": ess_by_group,
                "scale_source": scale_source,
                "distribution_shift_adjusted": weights is not None,
            },
        )
        return {
            "result": result,
            "uncertainty_envelope": prediction_result.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="ml.uncertainty",
    version="1.0.0",
    tags={"ml", "uncertainty", "conformal-prediction", "aps", "raps", "mondrian"},
)
class MondrianAPSRAPSConformalizer:
    """Build APS/RAPS classification prediction sets with group and class-cluster thresholds."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="mondrian_aps_raps",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "class_probabilities",
                    SlotType.MATRIX,
                    Unit("class", "probability"),
                    shape=("n_obs", "n_classes"),
                ),
                SlotSpec("target", SlotType.VECTOR, Unit("class", "index"), shape=("n_obs",)),
            }
        ),
        output_slots=_prediction_set_output_slots(),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="target_coverage", default=None),
            ParameterSpec(name="score_type", default="raps"),
            ParameterSpec(name="raps_lambda", default=0.01),
            ParameterSpec(name="raps_k_reg", default=5),
            ParameterSpec(name="group_values", default=None),
            ParameterSpec(name="group_keys", default=None),
            ParameterSpec(name="class_conditioning", default=None),
            ParameterSpec(name="class_clusters", default=None),
            ParameterSpec(name="importance_weights", default=None),
            ParameterSpec(name="min_calibration_per_group", default=100),
            ParameterSpec(name="min_group_weighted_ess", default=100.0),
            ParameterSpec(name="rare_class_threshold", default=100),
            ParameterSpec(name="fail_on_unsupported_group", default=False),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="APS/RAPS conformal prediction sets with Mondrian group and rare-class cluster calibration.",
        tags=frozenset({"ml", "uncertainty", "conformal-prediction", "aps", "raps", "mondrian"}),
        declared_truthfulness_tier="exact",
        truthfulness_scope="conditional_coverage",
        when_to_use=(
            "Deep tabular classifiers, including FT-Transformer and TabNet, when calibrated "
            "prediction sets are required under policy groups or rare-class clusters."
        ),
        citations=(
            "Romano, Y., Sesia, M. & Candes, E. (2020). Classification with valid and adaptive coverage.",
            "Angelopoulos, A. et al. (2021). Uncertainty sets for image classifiers using conformal prediction.",
        ),
        when_not_to_use=(
            "Calibration support per policy group or class cluster is too small; raw marginal "
            "APS/RAPS alone is not sufficient for policy-sensitive deployment."
        ),
        output_interpretation=(
            "Prediction sets target marginal coverage and supported Mondrian group or "
            "class-cluster conditional coverage, with explicit unsupported statuses."
        ),
        typical_min_obs=400,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = dict(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        if "prediction_result" not in payload and isinstance(fallback_state, PredictionResult):
            payload["prediction_result"] = fallback_state
        return payload

    @staticmethod
    def pure_step(
        state: Mapping[str, Any] | PredictionResult, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        lookup_params = _lookup_params_from_state(state, params)
        prediction_result = _classification_prediction_payload(state, lookup_params)
        alpha = _alpha_from_params(lookup_params, default=0.05)
        probabilities = _probability_matrix_from_sources(lookup_params, prediction_result)
        n_obs, n_classes = probabilities.shape
        if prediction_result.target is None:
            raise ValueError("mondrian_aps_raps requires target labels for calibration")
        class_labels = _class_labels_from_params(lookup_params, prediction_result, n_classes)
        labels = _label_indices(prediction_result.target, n_classes, class_labels)
        if labels.shape[0] != n_obs:
            raise ValueError("target labels must align with probability rows")

        score_type = str(lookup_params.get("score_type", "raps")).strip().lower()
        if score_type not in {"aps", "raps"}:
            raise ValueError("score_type must be 'aps' or 'raps'")
        class_clusters = _class_clusters_from_params(lookup_params, prediction_result, n_classes)
        class_conditioning = lookup_params.get("class_conditioning")
        if class_conditioning is None:
            class_conditioning = "class_cluster" if class_clusters is not None else "none"
        class_conditioning = str(class_conditioning).strip().lower()
        if class_conditioning not in {"none", "true_label", "class_cluster", "predicted_label"}:
            raise ValueError(
                "class_conditioning must be one of: none, true_label, class_cluster, predicted_label"
            )

        score_matrix, ranks = _aps_raps_score_matrix(
            probabilities,
            score_type=score_type,
            raps_lambda=float(lookup_params.get("raps_lambda", 0.01)),
            raps_k_reg=max(1, int(lookup_params.get("raps_k_reg", 5))),
        )
        calibration_scores = score_matrix[np.arange(n_obs), labels]
        predicted_labels = np.argmax(probabilities, axis=1)
        policy_labels, policy_key = _group_payload(lookup_params, prediction_result, n_obs)
        weights = _as_optional_weights(lookup_params, prediction_result, n_obs)
        min_group_calibration_n = int(lookup_params.get("min_calibration_per_group", 100))
        min_group_weighted_ess = float(lookup_params.get("min_group_weighted_ess", 100.0))
        quantile_engine = WeightedConformalQuantile(
            alpha=alpha,
            min_effective_sample_size=max(
                1.0, float(lookup_params.get("min_effective_sample_size", 1.0))
            ),
        )
        global_threshold, _ = quantile_engine.quantile(calibration_scores, weights)

        calibration_keys = np.asarray(
            [
                _threshold_key(
                    str(policy_labels[row]),
                    _condition_for_class(
                        int(labels[row]),
                        class_conditioning=class_conditioning,
                        predicted_label=int(predicted_labels[row]),
                        class_clusters=class_clusters,
                    ),
                )
                for row in range(n_obs)
            ],
            dtype=object,
        )
        policy_only_keys = np.asarray(
            [_threshold_key(str(policy_labels[row]), None) for row in range(n_obs)],
            dtype=object,
        )
        thresholds: dict[str, float] = {}
        policy_thresholds: dict[str, float] = {}
        for key in sorted(set(calibration_keys.astype(str).tolist())):
            mask = calibration_keys.astype(str) == key
            thresholds[key] = quantile_engine.quantile(
                calibration_scores[mask],
                None if weights is None else weights[mask],
            )[0]
        for key in sorted(set(policy_only_keys.astype(str).tolist())):
            mask = policy_only_keys.astype(str) == key
            policy_thresholds[key] = quantile_engine.quantile(
                calibration_scores[mask],
                None if weights is None else weights[mask],
            )[0]

        candidate_thresholds = np.empty((n_obs, n_classes), dtype=float)
        for row in range(n_obs):
            policy_value = str(policy_labels[row])
            policy_key_value = _threshold_key(policy_value, None)
            for class_idx in range(n_classes):
                candidate_key = _threshold_key(
                    policy_value,
                    _condition_for_class(
                        class_idx,
                        class_conditioning=class_conditioning,
                        predicted_label=int(predicted_labels[row]),
                        class_clusters=class_clusters,
                    ),
                )
                candidate_thresholds[row, class_idx] = thresholds.get(
                    candidate_key,
                    policy_thresholds.get(policy_key_value, global_threshold),
                )
        prediction_sets = _prediction_sets_from_scores(
            score_matrix,
            probabilities,
            candidate_thresholds,
        )
        set_sizes = np.asarray([len(values) for values in prediction_sets], dtype=int)
        covered = _prediction_set_coverage(prediction_sets, labels)
        coverage = float(np.mean(covered))
        family = "mondrian_raps" if score_type == "raps" else "mondrian_aps"
        diagnostic = _classification_diagnostic(
            family=family,
            base_model_family=prediction_result.method_name,
            alpha=alpha,
            calibration_scores=calibration_scores,
            prediction_sets=prediction_sets,
            set_sizes=set_sizes,
            labels=labels,
            group_labels=calibration_keys,
            group_key=policy_key
            if class_conditioning == "none"
            else f"{policy_key}|{class_conditioning}",
            n_classes=n_classes,
            min_group_calibration_n=min_group_calibration_n,
            weights=weights,
            min_group_weighted_ess=min_group_weighted_ess if weights is not None else None,
            class_conditional=class_conditioning != "none",
        )
        if (
            bool(lookup_params.get("fail_on_unsupported_group", False))
            and diagnostic.status == "unsupported"
        ):
            raise ValueError(
                "mondrian_aps_raps cannot claim conditional coverage for unsupported groups: "
                + ", ".join(diagnostic.calibration_support.groups_below_min_support)
            )
        class_metrics = _classification_metrics(
            prediction_sets,
            labels,
            n_classes,
            alpha,
            int(lookup_params.get("rare_class_threshold", 100)),
        )
        result = PredictionSetResult(
            method_name="mondrian_aps_raps",
            class_probabilities=probabilities,
            prediction_sets=prediction_sets,
            set_sizes=set_sizes,
            predicted_labels=predicted_labels,
            target=labels,
            coverage=coverage,
            alpha=alpha,
            conditional_coverage_diagnostic=diagnostic,
            truthfulness_receipt=TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.EXACT
                if diagnostic.status not in {"unsupported", "fail"}
                else TruthfulnessTier.UNVERIFIED,
                truthfulness_scope=TruthfulnessScope.CONDITIONAL_COVERAGE,
                diagnostics={
                    "observed_coverage": coverage,
                    "score_type": score_type,
                    "class_conditioning": class_conditioning,
                    "diagnostic_status": diagnostic.status,
                },
                degradation_reasons=tuple(diagnostic.failure_modes),
            ),
            metadata={
                "base_method": prediction_result.method_name,
                "score_type": score_type,
                "class_conditioning": class_conditioning,
                "global_threshold": global_threshold,
                "thresholds": thresholds,
                "policy_thresholds": policy_thresholds,
                "rank_matrix_shape": [int(value) for value in ranks.shape],
                **class_metrics,
            },
        )
        return {"result": result}


@foundry_method(
    namespace="ml.uncertainty",
    version="1.0.0",
    tags={"ml", "uncertainty", "conformal-prediction", "graph", "gnn"},
)
class GraphAwareConformalizer:
    """Calibrate graph node classification sets with DAPS/SNAPS-style score smoothing."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="graph_aware_conformal",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "class_probabilities",
                    SlotType.MATRIX,
                    Unit("class", "probability"),
                    shape=("n_nodes", "n_classes"),
                ),
                SlotSpec(
                    "adjacency_matrix",
                    SlotType.MATRIX,
                    Unit("network", "adjacency"),
                    shape=("n_nodes", "n_nodes"),
                ),
                SlotSpec("target", SlotType.VECTOR, Unit("class", "index"), shape=("n_nodes",)),
            }
        ),
        output_slots=_prediction_set_output_slots(),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="target_coverage", default=None),
            ParameterSpec(name="score_type", default="aps"),
            ParameterSpec(name="graph_method", default="daps"),
            ParameterSpec(name="graph_smoothing", default=0.35),
            ParameterSpec(name="raps_lambda", default=0.01),
            ParameterSpec(name="raps_k_reg", default=5),
            ParameterSpec(name="group_values", default=None),
            ParameterSpec(name="community", default=None),
            ParameterSpec(name="temporal_bin", default=None),
            ParameterSpec(name="class_clusters", default=None),
            ParameterSpec(name="topology_correction", default=None),
            ParameterSpec(name="corrected_class_probabilities", default=None),
            ParameterSpec(name="min_calibration_per_group", default=50),
            ParameterSpec(name="min_graph_effective_sample_size", default=50),
            ParameterSpec(name="fail_on_unsupported_group", default=False),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Topology-aware conformal prediction sets for GNN node classification outputs.",
        tags=frozenset({"ml", "uncertainty", "conformal-prediction", "graph", "gnn"}),
        declared_truthfulness_tier="exact",
        truthfulness_scope="conditional_coverage",
        when_to_use=(
            "GCN, GraphSAGE, GAT, or other node classifiers where topology-aware conformal "
            "scores are required instead of raw split conformal on softmax probabilities."
        ),
        citations=(
            "H. Zargarbashi et al. (2023). Conformal Prediction Sets for Graph Neural Networks.",
            "Similarity-Navigated Conformal Prediction for Graph Neural Networks (2024).",
        ),
        when_not_to_use=(
            "Calibration and deployment graph entities are not comparable, graph strata have "
            "insufficient support, or conditional shift invalidates covariate/topology weighting."
        ),
        output_interpretation=(
            "Prediction sets are calibrated on graph-smoothed scores and report coverage by "
            "degree, community, homophily, and temporal bins."
        ),
        typical_min_obs=200,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = dict(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        if "prediction_result" not in payload and isinstance(fallback_state, PredictionResult):
            payload["prediction_result"] = fallback_state
        return payload

    @staticmethod
    def pure_step(
        state: Mapping[str, Any] | PredictionResult, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        lookup_params = _lookup_params_from_state(state, params)
        prediction_result = _classification_prediction_payload(state, lookup_params)
        alpha = _alpha_from_params(lookup_params, default=0.05)
        probabilities = _probability_matrix_from_sources(lookup_params, prediction_result)
        probabilities, correction_applied = _corrected_graph_probabilities(
            probabilities, lookup_params
        )
        adjacency = _adjacency_matrix_from_sources(lookup_params, prediction_result)
        if adjacency.shape[0] != probabilities.shape[0]:
            raise ValueError("adjacency_matrix rows must align with class_probabilities")
        n_obs, n_classes = probabilities.shape
        if prediction_result.target is None:
            raise ValueError("graph_aware_conformal requires target labels for calibration")
        class_labels = _class_labels_from_params(lookup_params, prediction_result, n_classes)
        labels = _label_indices(prediction_result.target, n_classes, class_labels)
        if labels.shape[0] != n_obs:
            raise ValueError("target labels must align with graph nodes")

        score_type = str(lookup_params.get("score_type", "aps")).strip().lower()
        if score_type not in {"aps", "raps"}:
            raise ValueError("score_type must be 'aps' or 'raps'")
        base_score_matrix, _ = _aps_raps_score_matrix(
            probabilities,
            score_type=score_type,
            raps_lambda=float(lookup_params.get("raps_lambda", 0.01)),
            raps_k_reg=max(1, int(lookup_params.get("raps_k_reg", 5))),
        )
        score_matrix, graph_method_used = _graph_smoothed_scores(
            base_score_matrix,
            adjacency,
            lookup_params,
        )
        calibration_scores = score_matrix[np.arange(n_obs), labels]
        predicted_labels = np.argmax(probabilities, axis=1)
        policy_labels, policy_key = _group_payload(lookup_params, prediction_result, n_obs)
        quantile_engine = WeightedConformalQuantile(
            alpha=alpha,
            min_effective_sample_size=max(
                1.0, float(lookup_params.get("min_effective_sample_size", 1.0))
            ),
        )
        global_threshold, _ = quantile_engine.quantile(calibration_scores, None)
        policy_thresholds: dict[str, float] = {}
        policy_keys = np.asarray(
            [_threshold_key(str(policy_labels[row]), None) for row in range(n_obs)],
            dtype=object,
        )
        for key in sorted(set(policy_keys.astype(str).tolist())):
            mask = policy_keys.astype(str) == key
            policy_thresholds[key] = quantile_engine.quantile(calibration_scores[mask], None)[0]
        row_thresholds = np.asarray(
            [
                policy_thresholds.get(
                    _threshold_key(str(policy_labels[row]), None), global_threshold
                )
                for row in range(n_obs)
            ],
            dtype=float,
        )
        threshold_matrix = np.repeat(row_thresholds[:, None], n_classes, axis=1)
        prediction_sets = _prediction_sets_from_scores(
            score_matrix, probabilities, threshold_matrix
        )
        set_sizes = np.asarray([len(values) for values in prediction_sets], dtype=int)
        covered = _prediction_set_coverage(prediction_sets, labels)
        coverage = float(np.mean(covered))
        family = (
            "graph_snaps"
            if graph_method_used == "snaps"
            else "graph_daps"
            if graph_method_used == "daps"
            else "graph_cf_gnn"
            if correction_applied
            else "graph_raps"
            if score_type == "raps"
            else "graph_aps"
        )
        min_group_calibration_n = int(lookup_params.get("min_calibration_per_group", 50))
        diagnostic = _classification_diagnostic(
            family=family,
            base_model_family=prediction_result.method_name,
            alpha=alpha,
            calibration_scores=calibration_scores,
            prediction_sets=prediction_sets,
            set_sizes=set_sizes,
            labels=labels,
            group_labels=policy_keys,
            group_key=policy_key,
            n_classes=n_classes,
            min_group_calibration_n=min_group_calibration_n,
            weights=None,
            min_group_weighted_ess=None,
            class_conditional=False,
        )
        graph_diag = _graph_coverage_diagnostic(
            adjacency=adjacency,
            prediction_sets=prediction_sets,
            set_sizes=set_sizes,
            target=labels,
            alpha=alpha,
            lookup_params=lookup_params,
            min_graph_effective_sample_size=int(
                lookup_params.get("min_graph_effective_sample_size", 50)
            ),
        )
        failure_modes = set(diagnostic.failure_modes)
        status = diagnostic.status
        action = diagnostic.recommended_action
        if graph_diag.exchangeability_proxy_status == "fail":
            status = "unsupported"
            action = "human_review_or_abstain"
            failure_modes.add("graph_exchangeability_proxy_failed")
        elif graph_diag.exchangeability_proxy_status == "warn" and status == "pass":
            status = "warn"
            failure_modes.add("graph_stratum_support_warning")
        diagnostic = diagnostic.model_copy(
            update={
                "status": status,
                "graph": graph_diag,
                "failure_modes": sorted(failure_modes),
                "recommended_action": action,
                "method_spec": diagnostic.method_spec.model_copy(
                    update={
                        "assumptions": [
                            *diagnostic.method_spec.assumptions,
                            "graph calibration and deployment nodes are comparable within topology strata",
                        ]
                    }
                ),
            }
        )
        if (
            bool(lookup_params.get("fail_on_unsupported_group", False))
            and diagnostic.status == "unsupported"
        ):
            raise ValueError("graph_aware_conformal cannot certify unsupported graph strata")
        result = PredictionSetResult(
            method_name="graph_aware_conformal",
            class_probabilities=probabilities,
            prediction_sets=prediction_sets,
            set_sizes=set_sizes,
            predicted_labels=predicted_labels,
            target=labels,
            coverage=coverage,
            alpha=alpha,
            conditional_coverage_diagnostic=diagnostic,
            truthfulness_receipt=TruthfulnessReceipt(
                runtime_truthfulness_tier=TruthfulnessTier.EXACT
                if diagnostic.status not in {"unsupported", "fail"}
                else TruthfulnessTier.UNVERIFIED,
                truthfulness_scope=TruthfulnessScope.CONDITIONAL_COVERAGE,
                diagnostics={
                    "observed_coverage": coverage,
                    "score_type": score_type,
                    "graph_method": graph_method_used,
                    "diagnostic_status": diagnostic.status,
                },
                degradation_reasons=tuple(diagnostic.failure_modes),
            ),
            metadata={
                "base_method": prediction_result.method_name,
                "score_type": score_type,
                "graph_method": graph_method_used,
                "global_threshold": global_threshold,
                "policy_thresholds": policy_thresholds,
                "topology_correction_applied": correction_applied,
                **_classification_metrics(
                    prediction_sets,
                    labels,
                    n_classes,
                    alpha,
                    int(lookup_params.get("rare_class_threshold", 50)),
                ),
            },
        )
        return {"result": result}


def update_conditional_coverage_diagnostic_with_outcomes(
    interval_result: PredictionIntervalResult | Mapping[str, Any],
    y_true: Sequence[float] | np.ndarray,
    *,
    group_values: Sequence[Any] | Mapping[str, Sequence[Any]] | None = None,
    features: Any | None = None,
    feature_names: Sequence[str] | None = None,
    ert_n_splits: int = 5,
    ert_under_threshold: float = 0.02,
    min_evaluation_per_group: int = 200,
) -> PredictionIntervalResult:
    """Return an interval result with post-outcome coverage and ERT diagnostics filled in."""

    result = (
        interval_result
        if isinstance(interval_result, PredictionIntervalResult)
        else PredictionIntervalResult.model_validate(interval_result)
    )
    target = _as_1d_float("y_true", y_true)
    lower = _as_1d_float("lower", result.lower)
    upper = _as_1d_float("upper", result.upper)
    if target.shape[0] != lower.shape[0] or target.shape[0] != upper.shape[0]:
        raise ValueError("y_true must align with prediction interval rows")
    covered = (target >= lower) & (target <= upper)
    marginal = _coverage_from_mask(covered)
    diagnostic = result.conditional_coverage_diagnostic
    if diagnostic is None:
        scores = np.maximum(lower - target, target - upper)
        group_labels = np.full(target.shape[0], "__all__", dtype=object)
        group_key = "all"
        diagnostic = _build_conditional_diagnostic(
            family="empirical_interval",
            base_model_family=result.method_name,
            alpha=result.alpha,
            scores=np.maximum(scores, 0.0),
            lower=lower,
            upper=upper,
            target=target,
            group_labels=group_labels,
            group_key=group_key,
            min_group_calibration_n=min_evaluation_per_group,
            weights=None,
            min_group_weighted_ess=None,
            calibration_timestamp=None,
            calibration_data_hash=None,
        )
    if group_values is None:
        existing_group_key = diagnostic.groups[0].group_key if diagnostic.groups else "all"
        group_labels = np.full(target.shape[0], "__all__", dtype=object)
        group_key = existing_group_key
    else:
        pseudo_prediction = PredictionResult(
            method_name=result.method_name,
            predictions=np.asarray(result.predictions, dtype=float),
            target=target,
            metadata={"group_values": group_values},
        )
        group_labels, group_key = _group_payload({}, pseudo_prediction, target.shape[0])

    groups, support, _ = _group_estimates(
        group_labels,
        group_key,
        lower,
        upper,
        target,
        result.alpha,
        min_evaluation_per_group,
    )
    ert = (
        _ert_diagnostic(
            features,
            covered,
            result.alpha,
            ert_n_splits,
            ert_under_threshold,
            feature_names=feature_names,
        )
        if features is not None
        else ERTDiagnostic(
            evaluated=False,
            n_splits=0,
            feature_set=list(feature_names or []),
            classifier_family="not_available",
            status="not_enough_labels",
        )
    )
    failure_modes = set(diagnostic.failure_modes)
    status = diagnostic.status
    action = diagnostic.recommended_action
    if marginal.ci_low < (1.0 - result.alpha) - 0.01:
        status = "fail"
        action = "retrain_base_model"
        failure_modes.add("marginal_coverage_shortfall")
    for group in groups:
        if group.guarantee_supported and group.ci_low is not None:
            if group.ci_low < (1.0 - result.alpha) - 0.03:
                status = "fail"
                action = "collect_more_calibration_data"
                failure_modes.add("group_coverage_shortfall")
                break
    if ert.status == "fail":
        status = "fail"
        action = "switch_to_mondrian"
        failure_modes.add("ert_local_undercoverage")
    elif ert.status == "warn" and status == "pass":
        status = "warn"
        failure_modes.add("ert_local_coverage_warning")

    updated_support = support.model_copy(
        update={
            "n_calibration_total": diagnostic.calibration_support.n_calibration_total,
            "min_group_calibration_n": diagnostic.calibration_support.min_group_calibration_n,
            "min_group_weighted_ess": diagnostic.calibration_support.min_group_weighted_ess,
            "groups_below_min_support": diagnostic.calibration_support.groups_below_min_support,
            "status": diagnostic.calibration_support.status,
        }
    )
    updated = diagnostic.model_copy(
        update={
            "status": status,
            "marginal": marginal,
            "groups": groups,
            "ert": ert,
            "calibration_support": updated_support,
            "failure_modes": sorted(failure_modes),
            "recommended_action": action,
        }
    )
    return result.model_copy(
        update={
            "coverage": marginal.coverage,
            "conditional_coverage_diagnostic": updated,
        }
    )


def evaluate_conformal_acceptance_gate(
    result: PredictionIntervalResult | PredictionSetResult | Mapping[str, Any],
    *,
    epsilon_m: float = 0.01,
    epsilon_g: float = 0.03,
    ert_under_threshold: float = 0.02,
    weighted_ess_ratio_warn: float = 0.30,
    weighted_ess_ratio_fail: float = 0.15,
) -> dict[str, Any]:
    """Evaluate the Phase 5 pass/warn/fail gates from a conformal result diagnostic."""

    if isinstance(result, PredictionIntervalResult | PredictionSetResult):
        conformal_result = result
    elif "prediction_sets" in result:
        conformal_result = PredictionSetResult.model_validate(result)
    else:
        conformal_result = PredictionIntervalResult.model_validate(result)
    diagnostic = conformal_result.conditional_coverage_diagnostic
    if diagnostic is None:
        return {
            "status": "fail",
            "passed": False,
            "blockers": ["missing_conditional_coverage_diagnostic"],
            "warnings": [],
            "recommended_action": "human_review_or_abstain",
        }

    target = diagnostic.target_coverage
    blockers: list[str] = []
    warnings: list[str] = []
    if diagnostic.status in {"fail", "unsupported"}:
        blockers.extend(diagnostic.failure_modes or [f"diagnostic_status_{diagnostic.status}"])
    elif diagnostic.status == "warn":
        warnings.extend(diagnostic.failure_modes or ["diagnostic_warning"])

    if diagnostic.marginal is not None:
        if diagnostic.marginal.ci_low < target - epsilon_m:
            blockers.append("marginal_coverage_lower_bound_shortfall")
    else:
        warnings.append("marginal_coverage_pending")

    worst_group_shortfall = 0.0
    for group in diagnostic.groups:
        if not group.guarantee_supported:
            warnings.append(f"unsupported_group:{group.group_value}")
            continue
        if group.shortfall is not None:
            worst_group_shortfall = max(worst_group_shortfall, float(group.shortfall))
        if group.ci_low is not None and group.ci_low < target - epsilon_g:
            blockers.append(f"group_coverage_lower_bound_shortfall:{group.group_value}")

    if diagnostic.ert is not None:
        if diagnostic.ert.status == "fail":
            blockers.append("ert_conditional_undercoverage")
        elif diagnostic.ert.status == "warn":
            warnings.append("ert_conditional_coverage_warning")
        if diagnostic.ert.ert_under is not None and diagnostic.ert.ert_under > ert_under_threshold:
            blockers.append("ert_undercoverage_exceeds_threshold")

    if diagnostic.score_tail is not None:
        if diagnostic.score_tail.status == "fail":
            blockers.append("vacuity_or_heavy_tail_failure")
        elif diagnostic.score_tail.status == "warn":
            warnings.append("vacuity_or_heavy_tail_warning")

    if diagnostic.shift is not None and diagnostic.shift.density_ratio_ess is not None:
        n_cal = max(float(diagnostic.method_spec.calibration_size), 1.0)
        ratio = diagnostic.shift.density_ratio_ess / n_cal
        if ratio < weighted_ess_ratio_fail:
            blockers.append("weighted_ess_ratio_too_low")
        elif ratio < weighted_ess_ratio_warn:
            warnings.append("weighted_ess_ratio_low")

    if diagnostic.graph is not None:
        if diagnostic.graph.exchangeability_proxy_status == "fail":
            blockers.append("graph_exchangeability_proxy_failed")
        elif diagnostic.graph.exchangeability_proxy_status == "warn":
            warnings.append("graph_exchangeability_proxy_warning")

    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    if blockers:
        status = "fail"
    elif warnings:
        status = "warn"
    else:
        status = "pass"
    return {
        "status": status,
        "passed": status == "pass",
        "blockers": blockers,
        "warnings": warnings,
        "recommended_action": diagnostic.recommended_action,
        "target_coverage": target,
        "observed_coverage": conformal_result.coverage,
        "worst_group_shortfall": worst_group_shortfall,
        "method_family": diagnostic.method_spec.family,
    }


__all__ = [
    "ConformalPredictionEstimator",
    "GraphAwareConformalizer",
    "MondrianAPSRAPSConformalizer",
    "MondrianCQRConformalizer",
    "NormalizedResidualMondrianConformalizer",
    "WeightedConformalQuantile",
    "evaluate_conformal_acceptance_gate",
    "update_conditional_coverage_diagnostic_with_outcomes",
]
