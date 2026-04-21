"""Design-aware doubly robust estimation for survey missingness workflows.

Phase 1 intentionally keeps the estimator operational rather than pretending to
solve arbitrary MNAR identification:

* `population_mar` implements the design-adjusted AIPW mean estimator.
* `mnar_shadow` activates only when a shadow-variable control-function branch
  clears explicit identification diagnostics.
* Optional `reference_X` / `reference_design_weights` inputs switch the method
  into a probability-reference data-integration regime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
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
from polisyos.foundry.methods.catalog._phase1_artifacts import (
    resolve_artifact_store,
    resolve_dataset_context,
)
from polisyos.foundry.methods.catalog.survey.semiparametric import (
    SamplingModelSpec,
    SurveyDesignSpec,
    build_psu_stratified_cross_fit_schedule,
    diagnose_weight_regime,
)
from polisyos.ir.analytics.administrative_missingness import (
    MissingnessAssessmentReport,
    MissingnessAssessmentStatus,
)
from polisyos.ir.analytics.survey_quality import (
    SurveyAssumptionComponent,
    SurveyAssumptionLayer,
    SurveyAssumptionStatus,
    SurveyRequestedRegime,
    SurveyValidatedRegime,
    SurveyVarianceMode,
    build_survey_quality_certificate,
    persist_survey_quality_certificate,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec(
                "survey_quality_certificate_ref",
                SlotType.SCALAR,
                Unit("artifact_ref", "json"),
            ),
        }
    )


def _vector(state: Mapping[str, Any], key: str) -> np.ndarray:
    arr = np.asarray(state[key], dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _optional_vector(state: Mapping[str, Any], key: str) -> np.ndarray | None:
    if key not in state:
        return None
    return _vector(state, key)


def _matrix(state: Mapping[str, Any], key: str) -> np.ndarray:
    arr = np.asarray(state[key], dtype=float)
    if arr.ndim == 1:
        arr = arr[:, None]
    if arr.ndim != 2:
        raise ValueError(f"{key} must be a 2D matrix")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _optional_matrix(state: Mapping[str, Any], key: str) -> np.ndarray | None:
    if key not in state:
        return None
    return _matrix(state, key)


def _label_vector(state: Mapping[str, Any], key: str, n: int, default: np.ndarray) -> np.ndarray:
    if key not in state:
        return default
    arr = np.asarray(state[key], dtype=object).reshape(-1)
    if arr.size != n:
        raise ValueError(f"{key} must have length {n}")
    return arr


def _shadow_matrix(state: Mapping[str, Any], key: str, n: int) -> np.ndarray | None:
    if key not in state:
        return None
    shadow = np.asarray(state[key], dtype=float)
    if shadow.ndim == 1:
        shadow = shadow[:, None]
    if shadow.ndim != 2 or shadow.shape[0] != n:
        raise ValueError(f"{key} must be a matrix with {n} rows")
    if np.any(~np.isfinite(shadow)):
        raise ValueError(f"{key} must contain only finite values")
    return shadow


def _replicate_matrix(state: Mapping[str, Any], key: str, n: int) -> np.ndarray | None:
    if key not in state:
        return None
    repl = np.asarray(state[key], dtype=float)
    if repl.ndim != 2:
        raise ValueError(f"{key} must be a 2D matrix")
    if repl.shape[0] == n and repl.shape[1] != n:
        repl = repl.T
    if repl.shape[1] != n:
        raise ValueError(f"{key} must have n_obs={n} columns")
    if np.any(~np.isfinite(repl)) or np.any(repl < 0.0):
        raise ValueError(f"{key} must be finite and non-negative")
    return repl


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if total <= 0.0:
        return 0.0
    return float(np.sum(weights * values) / total)


def _weighted_var(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if total <= 0.0:
        return 0.0
    mean = _weighted_mean(values, weights)
    return float(np.sum(weights * (values - mean) ** 2) / total)


def _weighted_std(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sqrt(max(_weighted_var(values, weights), 0.0)))


def _weighted_r2(y: np.ndarray, y_hat: np.ndarray, weights: np.ndarray) -> float:
    denom = float(np.sum(weights * (y - _weighted_mean(y, weights)) ** 2))
    if denom <= 1e-12:
        return 0.0
    numer = float(np.sum(weights * (y - y_hat) ** 2))
    return float(max(0.0, 1.0 - numer / denom))


def _encode_ids(values: np.ndarray) -> np.ndarray:
    _, codes = np.unique(values.astype(str), return_inverse=True)
    if np.unique(codes).size <= 1:
        return np.zeros_like(codes, dtype=float)
    centered = codes.astype(float) - float(np.mean(codes))
    scale = float(np.std(centered))
    return centered / max(scale, 1.0)


def _augment_response_features(
    X: np.ndarray,
    *,
    base_weights: np.ndarray,
    strata: np.ndarray,
    clusters: np.ndarray,
    extra_columns: tuple[np.ndarray, ...] = (),
) -> np.ndarray:
    parts: list[np.ndarray] = [X, np.log(np.clip(base_weights, 1e-12, None))[:, None]]
    if np.unique(strata.astype(str)).size > 1:
        parts.append(_encode_ids(strata)[:, None])
    if np.unique(clusters.astype(str)).size > 1:
        parts.append(_encode_ids(clusters)[:, None])
    for column in extra_columns:
        arr = np.asarray(column, dtype=float)
        if arr.ndim == 1:
            arr = arr[:, None]
        parts.append(arr)
    return np.column_stack(parts)


def _augment_outcome_features(X: np.ndarray, shadow: np.ndarray | None = None) -> np.ndarray:
    if shadow is None:
        return X
    return np.column_stack([X, shadow])


def _standardize_matrix(X: np.ndarray) -> np.ndarray:
    means = np.mean(X, axis=0)
    sds = np.std(X, axis=0)
    sds = np.where(sds <= 1e-8, 1.0, sds)
    return (X - means) / sds


def _standardize_vector(values: np.ndarray) -> np.ndarray:
    mean = float(np.mean(values))
    sd = float(np.std(values))
    if sd <= 1e-8:
        return np.zeros_like(values, dtype=float)
    return (values - mean) / sd


def _diagnostic_basis(features: np.ndarray, spec: str) -> np.ndarray:
    max_features = 5
    if ":" in spec:
        _, raw = spec.split(":", 1)
        try:
            max_features = max(1, min(int(raw), features.shape[1]))
        except ValueError:
            max_features = min(5, features.shape[1])
    subset = features[:, : max(1, min(max_features, features.shape[1]))]
    standardized = _standardize_matrix(subset)
    intercept = np.ones((features.shape[0], 1), dtype=float)
    return np.column_stack([intercept, standardized])


def _fit_weighted_linear(
    X: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    *,
    ridge: float = 1e-6,
) -> np.ndarray:
    X_aug = np.column_stack([np.ones(X.shape[0]), X])
    W = np.maximum(weights, 1e-8)
    XtW = X_aug.T * W
    gram = XtW @ X_aug
    penalty = np.eye(gram.shape[0]) * ridge
    penalty[0, 0] = 0.0
    rhs = XtW @ y
    try:
        return np.linalg.solve(gram + penalty, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(X_aug * np.sqrt(W)[:, None], y * np.sqrt(W), rcond=None)[0]


def _predict_linear(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    X_aug = np.column_stack([np.ones(X.shape[0]), X])
    return X_aug @ beta


def _fit_weighted_logistic(
    X: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    *,
    ridge: float = 1e-4,
    max_iter: int = 100,
) -> np.ndarray:
    X_aug = np.column_stack([np.ones(X.shape[0]), X])
    beta = np.zeros(X_aug.shape[1], dtype=float)
    penalty = np.eye(X_aug.shape[1]) * ridge
    penalty[0, 0] = 0.0
    for _ in range(max_iter):
        eta = np.clip(X_aug @ beta, -20.0, 20.0)
        p = 1.0 / (1.0 + np.exp(-eta))
        W = np.maximum(weights * p * (1.0 - p), 1e-8)
        grad = X_aug.T @ (weights * (y - p)) - penalty @ beta
        hess = X_aug.T @ (W[:, None] * X_aug) + penalty
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            break
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta


def _predict_logistic(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    X_aug = np.column_stack([np.ones(X.shape[0]), X])
    eta = np.clip(X_aug @ beta, -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-eta))


def _make_stratified_folds(response: np.ndarray, n_folds: int, seed: int) -> tuple[np.ndarray, ...]:
    n = response.shape[0]
    if n < 2:
        return (np.arange(n, dtype=int),)
    k = max(2, min(int(n_folds), n))
    rng = np.random.default_rng(seed)
    fold_buckets: list[list[int]] = [[] for _ in range(k)]
    for group_value in (0.0, 1.0):
        idx = np.flatnonzero(np.isclose(response, group_value))
        if idx.size == 0:
            continue
        shuffled = idx.copy()
        rng.shuffle(shuffled)
        for fold_id, chunk in enumerate(np.array_split(shuffled, k)):
            fold_buckets[fold_id].extend(chunk.tolist())
    folds = tuple(np.asarray(sorted(bucket), dtype=int) for bucket in fold_buckets if bucket)
    return folds or (np.arange(n, dtype=int),)


@dataclass(frozen=True)
class _FoldPlan:
    folds: tuple[np.ndarray, ...]
    info: dict[str, Any]


def _build_fold_plan(
    response: np.ndarray,
    *,
    strata: np.ndarray,
    clusters: np.ndarray,
    n_folds: int,
    seed: int,
) -> _FoldPlan:
    use_design_folds = (
        np.unique(strata.astype(str)).size > 1
        or np.unique(clusters.astype(str)).size > 1
    )
    if use_design_folds:
        schedule = build_psu_stratified_cross_fit_schedule(
            strata,
            clusters,
            n_folds=n_folds,
            seed=seed,
        )
        folds = tuple(
            np.flatnonzero(schedule.fold_ids == fold_id)
            for fold_id in range(schedule.n_folds)
            if np.any(schedule.fold_ids == fold_id)
        )
        if folds:
            return _FoldPlan(
                folds=folds,
                info={
                    "fold_assignment": "psu_within_strata",
                    "n_folds": len(folds),
                    "fold_sizes": [int(fold.size) for fold in folds],
                    "fallback_used": schedule.fallback_used,
                    "schedule_warnings": list(schedule.warnings),
                    "psu_counts_by_stratum": dict(schedule.psu_counts_by_stratum),
                },
            )
    folds = _make_stratified_folds(response, n_folds, seed)
    return _FoldPlan(
        folds=folds,
        info={
            "fold_assignment": "row_stratified_by_response",
            "n_folds": len(folds),
            "fold_sizes": [int(fold.size) for fold in folds],
            "fallback_used": "none",
            "schedule_warnings": [],
            "psu_counts_by_stratum": {},
        },
    )


def _parse_weight_truncation_rule(rule: Any) -> tuple[float, float | None]:
    if rule is None:
        return 0.0, None
    if isinstance(rule, (int, float)):
        return max(float(rule), 0.0), None
    if isinstance(rule, Mapping):
        min_obs = max(float(rule.get("min_observability", 0.0)), 0.0)
        max_weight = rule.get("max_weight")
        return min_obs, None if max_weight is None else max(float(max_weight), 0.0)
    text = str(rule).strip().lower()
    if not text or text == "none":
        return 0.0, None
    if text.startswith("clip="):
        values = [item.strip() for item in text.split("=", 1)[1].split(",") if item.strip()]
        if not values:
            return 0.0, None
        min_obs = max(float(values[0]), 0.0)
        max_weight = max(float(values[1]), 0.0) if len(values) > 1 else None
        return min_obs, max_weight
    return 0.0, None


def _apply_observability_guard(
    rho: np.ndarray,
    *,
    base_weights: np.ndarray,
    min_observability: float,
    max_weight: float | None,
) -> tuple[np.ndarray, int]:
    lower = np.full_like(rho, max(min_observability, 1e-4))
    if max_weight is not None and max_weight > 0.0:
        lower = np.maximum(lower, np.clip(base_weights / max_weight, 0.0, 0.99))
    clipped = np.clip(rho, lower, 1.0 - 1e-4)
    n_truncated = int(np.sum(np.abs(clipped - rho) > 1e-10))
    return clipped, n_truncated


def _cross_fit_response(
    features: np.ndarray,
    response: np.ndarray,
    weights: np.ndarray,
    *,
    folds: tuple[np.ndarray, ...],
    min_observability: float,
    max_weight: float | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    n = features.shape[0]
    rho_hat = np.zeros(n, dtype=float)
    for fold in folds:
        train_mask = np.ones(n, dtype=bool)
        train_mask[fold] = False
        beta = _fit_weighted_logistic(features[train_mask], response[train_mask], weights[train_mask])
        rho_hat[fold] = _predict_logistic(features[fold], beta)

    guarded, truncated = _apply_observability_guard(
        rho_hat,
        base_weights=weights,
        min_observability=min_observability,
        max_weight=max_weight,
    )
    return guarded, {"n_truncated_observabilities": truncated}


def _cross_fit_outcome(
    features_train_eval: np.ndarray,
    features_predict: np.ndarray,
    y: np.ndarray,
    response: np.ndarray,
    weights: np.ndarray,
    *,
    folds: tuple[np.ndarray, ...],
) -> tuple[np.ndarray, dict[str, Any]]:
    n = features_train_eval.shape[0]
    preds = np.zeros(features_predict.shape[0], dtype=float)
    prediction_counts = np.zeros(features_predict.shape[0], dtype=float)
    min_train_respondents = n
    for fold in folds:
        train_mask = np.ones(n, dtype=bool)
        train_mask[fold] = False
        respondent_mask = train_mask & (response > 0.5)
        n_resp = int(np.sum(respondent_mask))
        min_train_respondents = min(min_train_respondents, n_resp)
        if n_resp >= max(features_train_eval.shape[1] + 2, 8):
            beta = _fit_weighted_linear(
                features_train_eval[respondent_mask],
                y[respondent_mask],
                weights[respondent_mask],
            )
            if features_predict.shape[0] == n:
                preds[fold] = _predict_linear(features_predict[fold], beta)
                prediction_counts[fold] = 1.0
            else:
                preds += _predict_linear(features_predict, beta)
                prediction_counts += 1.0
        elif np.any(respondent_mask):
            fallback = _weighted_mean(y[respondent_mask], weights[respondent_mask])
            if features_predict.shape[0] == n:
                preds[fold] = fallback
                prediction_counts[fold] = 1.0
            else:
                preds += fallback
                prediction_counts += 1.0
        else:
            if features_predict.shape[0] == n:
                preds[fold] = 0.0
                prediction_counts[fold] = 1.0
            else:
                prediction_counts += 1.0
    prediction_counts = np.where(prediction_counts <= 0.0, 1.0, prediction_counts)
    preds = preds / prediction_counts
    return preds, {"min_train_respondents": int(min_train_respondents if np.isfinite(min_train_respondents) else 0)}


def _cross_fit_reference_membership(
    analytic_features: np.ndarray,
    reference_features: np.ndarray,
    analytic_weights: np.ndarray,
    reference_weights: np.ndarray,
    *,
    folds: tuple[np.ndarray, ...],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    n_analytic = analytic_features.shape[0]
    membership_prob = np.zeros(n_analytic, dtype=float)
    ref_scale = max(float(np.mean(reference_weights)), 1e-12)
    analytic_scale = max(float(np.mean(analytic_weights)), 1e-12)
    normalized_reference_weights = reference_weights * (analytic_scale / ref_scale)

    for fold in folds:
        train_mask = np.ones(n_analytic, dtype=bool)
        train_mask[fold] = False
        X_train = np.vstack([analytic_features[train_mask], reference_features])
        y_train = np.concatenate(
            [
                np.ones(int(np.sum(train_mask)), dtype=float),
                np.zeros(reference_features.shape[0], dtype=float),
            ]
        )
        w_train = np.concatenate(
            [
                analytic_weights[train_mask],
                normalized_reference_weights,
            ]
        )
        beta = _fit_weighted_logistic(X_train, y_train, w_train)
        membership_prob[fold] = _predict_logistic(analytic_features[fold], beta)

    membership_prob = np.clip(membership_prob, 0.02, 0.98)
    odds = membership_prob / np.clip(1.0 - membership_prob, 0.02, None)
    return odds, membership_prob, {"membership_probability_range": [float(np.min(membership_prob)), float(np.max(membership_prob))]}


def _weighted_brier_gain(y: np.ndarray, p_hat: np.ndarray, weights: np.ndarray) -> float:
    brier = _weighted_mean((y - p_hat) ** 2, weights)
    null_prob = np.full(y.shape[0], _weighted_mean(y, weights))
    null_brier = _weighted_mean((y - null_prob) ** 2, weights)
    if null_brier <= 1e-12:
        return 0.0
    return float(max(0.0, 1.0 - brier / null_brier))


def _status_from_score(
    score: float,
    *,
    pass_threshold: float,
    warn_threshold: float,
) -> SurveyAssumptionStatus:
    if score <= pass_threshold:
        return SurveyAssumptionStatus.PASS
    if score <= warn_threshold:
        return SurveyAssumptionStatus.WARN
    return SurveyAssumptionStatus.FAIL


def _component(
    *,
    component_id: str,
    layer: SurveyAssumptionLayer,
    statement: str,
    status: SurveyAssumptionStatus,
    metric_name: str | None = None,
    metric_value: float | None = None,
    threshold_value: float | None = None,
    notes: list[str] | None = None,
    evidence_refs: list[str] | None = None,
) -> SurveyAssumptionComponent:
    return SurveyAssumptionComponent(
        component_id=component_id,
        layer=layer,
        statement=statement,
        status=status,
        metric_name=metric_name,
        metric_value=metric_value,
        threshold_value=threshold_value,
        notes=list(notes or ()),
        evidence_refs=list(evidence_refs or ()),
    )


def _normalize_missingness_assessment(
    state: Mapping[str, Any],
) -> MissingnessAssessmentReport | None:
    raw = state.get("missingness_assessment")
    if raw is None:
        return None
    if isinstance(raw, MissingnessAssessmentReport):
        return raw
    return MissingnessAssessmentReport.model_validate(raw)


def _stable_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _prefixed_labels(values: np.ndarray, prefix: str) -> np.ndarray:
    return np.asarray([f"{prefix}:{item}" for item in values.astype(str)], dtype=object)


def _design_linearized_variance(
    linearized: np.ndarray,
    *,
    strata: np.ndarray,
    clusters: np.ndarray,
) -> float:
    if linearized.size <= 1:
        return 0.0
    unique_clusters = np.unique(clusters.astype(str))
    if unique_clusters.size <= 1:
        return float(np.var(linearized, ddof=1))

    strata_values = np.unique(strata.astype(str))
    total = 0.0
    used = False
    for stratum in strata_values:
        in_h = strata.astype(str) == stratum
        clusters_h = np.unique(clusters[in_h].astype(str))
        if clusters_h.size < 2:
            continue
        z_hi = np.array(
            [np.sum(linearized[in_h & (clusters.astype(str) == clu)]) for clu in clusters_h],
            dtype=float,
        )
        z_bar = float(np.mean(z_hi))
        total += float(
            clusters_h.size / (clusters_h.size - 1.0) * np.sum((z_hi - z_bar) ** 2)
        )
        used = True
    if used:
        return max(total, 0.0)
    return float(np.var(linearized, ddof=1))


def _replicate_variance(
    estimate_fn: callable,
    *,
    analytic_replicates: np.ndarray | None,
    reference_replicates: np.ndarray | None,
) -> tuple[float, np.ndarray | None]:
    if analytic_replicates is None and reference_replicates is None:
        return 0.0, None
    if analytic_replicates is not None and reference_replicates is not None:
        n_reps = min(analytic_replicates.shape[0], reference_replicates.shape[0])
        if n_reps <= 1:
            return 0.0, None
        estimates = np.array(
            [estimate_fn(analytic_replicates[idx], reference_replicates[idx]) for idx in range(n_reps)],
            dtype=float,
        )
    elif analytic_replicates is not None:
        if analytic_replicates.shape[0] <= 1:
            return 0.0, None
        estimates = np.array(
            [estimate_fn(analytic_replicates[idx], None) for idx in range(analytic_replicates.shape[0])],
            dtype=float,
        )
    else:
        if reference_replicates is None or reference_replicates.shape[0] <= 1:
            return 0.0, None
        estimates = np.array(
            [estimate_fn(None, reference_replicates[idx]) for idx in range(reference_replicates.shape[0])],
            dtype=float,
        )
    return float(np.var(estimates, ddof=1)), estimates


@dataclass(frozen=True)
class _CoreEstimate:
    estimate: float
    variance_estimate: float
    standard_error: float
    variance_mode: SurveyVarianceMode
    replicate_estimates: np.ndarray | None
    linearized: np.ndarray
    pseudo_outcome: np.ndarray
    response_propensity: np.ndarray
    outcome_regression: np.ndarray
    reference_outcome_regression: np.ndarray | None
    selection_membership_probability: np.ndarray | None
    selection_odds: np.ndarray | None
    design_moments: np.ndarray
    imputation_moments: np.ndarray
    design_score: float
    imputation_score: float
    response_fit_gain: float
    outcome_r2: float
    overlap_score: float
    effective_sample_size: float
    max_weight: float
    weight_cv: float
    positivity_min: float
    sensitivity_low: float
    sensitivity_high: float
    crossfit_info: dict[str, Any]
    estimation_mode: str
    shadow_metrics: dict[str, float]
    weight_regime_report: dict[str, Any]


def _estimate_one_sample(
    *,
    X: np.ndarray,
    Y: np.ndarray,
    response: np.ndarray,
    base_weights: np.ndarray,
    strata: np.ndarray,
    clusters: np.ndarray,
    shadow: np.ndarray | None,
    replicate_weights: np.ndarray | None,
    regime: SurveyRequestedRegime,
    variance_mode_requested: SurveyVarianceMode,
    n_folds: int,
    seed: int,
    diagnostic_threshold: float,
    sensitivity_radius: float,
    diagnostic_basis_spec: str,
    min_observability: float,
    max_weight_rule: float | None,
) -> _CoreEstimate:
    fold_plan = _build_fold_plan(
        response,
        strata=strata,
        clusters=clusters,
        n_folds=n_folds,
        seed=seed,
    )
    outcome_features_base = _augment_outcome_features(X)
    response_features_base = _augment_response_features(
        X,
        base_weights=base_weights,
        strata=strata,
        clusters=clusters,
    )
    m_base, outcome_info_base = _cross_fit_outcome(
        outcome_features_base,
        outcome_features_base,
        Y,
        response,
        base_weights,
        folds=fold_plan.folds,
    )
    rho_base, response_info_base = _cross_fit_response(
        response_features_base,
        response,
        base_weights,
        folds=fold_plan.folds,
        min_observability=min_observability,
        max_weight=max_weight_rule,
    )

    shadow_metrics: dict[str, float] = {
        "shadow_incremental_r2": 0.0,
        "shadow_tilting_gain": 0.0,
        "n_shadow_variables": float(0 if shadow is None else shadow.shape[1]),
    }
    observed_mask = response > 0.5
    m_hat = m_base
    rho_hat = rho_base

    if regime is SurveyRequestedRegime.MNAR_SHADOW and shadow is not None:
        outcome_features_shadow = _augment_outcome_features(X, shadow)
        m_shadow, outcome_info_shadow = _cross_fit_outcome(
            outcome_features_shadow,
            outcome_features_shadow,
            Y,
            response,
            base_weights,
            folds=fold_plan.folds,
        )
        proxy_signal = _standardize_vector(m_shadow - m_base)
        response_features_shadow = _augment_response_features(
            X,
            base_weights=base_weights,
            strata=strata,
            clusters=clusters,
            extra_columns=(proxy_signal,),
        )
        rho_shadow, response_info_shadow = _cross_fit_response(
            response_features_shadow,
            response,
            base_weights,
            folds=fold_plan.folds,
            min_observability=min_observability,
            max_weight=max_weight_rule,
        )
        m_hat = m_shadow
        rho_hat = rho_shadow
        shadow_metrics["shadow_incremental_r2"] = max(
            0.0,
            _weighted_r2(Y[observed_mask], m_shadow[observed_mask], base_weights[observed_mask])
            - _weighted_r2(Y[observed_mask], m_base[observed_mask], base_weights[observed_mask]),
        )
        shadow_metrics["shadow_tilting_gain"] = max(
            0.0,
            _weighted_brier_gain(response, rho_shadow, base_weights)
            - _weighted_brier_gain(response, rho_base, base_weights),
        )
        outcome_info_base["min_train_respondents"] = min(
            outcome_info_base["min_train_respondents"],
            outcome_info_shadow["min_train_respondents"],
        )
        response_info_base["n_truncated_observabilities"] = max(
            response_info_base["n_truncated_observabilities"],
            response_info_shadow["n_truncated_observabilities"],
        )

    pseudo_outcome = m_hat.copy()
    pseudo_outcome[observed_mask] += (Y[observed_mask] - m_hat[observed_mask]) / rho_hat[observed_mask]
    estimate = _weighted_mean(pseudo_outcome, base_weights)

    centered_signal = pseudo_outcome - estimate
    linearized = base_weights * centered_signal / max(float(np.sum(base_weights)), 1e-12)

    variance_mode = variance_mode_requested
    replicate_estimates: np.ndarray | None = None
    if variance_mode_requested is SurveyVarianceMode.REPLICATE and replicate_weights is not None:
        def _rep_fn(analytic_rep: np.ndarray | None, _: np.ndarray | None) -> float:
            if analytic_rep is None:
                return estimate
            return _weighted_mean(pseudo_outcome, analytic_rep)

        variance_estimate, replicate_estimates = _replicate_variance(
            _rep_fn,
            analytic_replicates=replicate_weights,
            reference_replicates=None,
        )
    else:
        if variance_mode_requested is SurveyVarianceMode.REPLICATE and replicate_weights is None:
            variance_mode = SurveyVarianceMode.SANDWICH
        variance_estimate = _design_linearized_variance(
            linearized,
            strata=strata,
            clusters=clusters,
        )
    standard_error = float(np.sqrt(max(variance_estimate, 0.0)))

    final_weights = np.zeros_like(base_weights, dtype=float)
    final_weights[observed_mask] = base_weights[observed_mask] / rho_hat[observed_mask]
    respondent_weights = final_weights[observed_mask]
    effective_sample_size = (
        float(np.sum(respondent_weights) ** 2 / np.sum(respondent_weights**2))
        if respondent_weights.size and np.sum(respondent_weights**2) > 0.0
        else 0.0
    )
    weight_cv = (
        float(np.std(respondent_weights) / max(np.mean(respondent_weights), 1e-12))
        if respondent_weights.size
        else 0.0
    )
    max_weight = float(np.max(respondent_weights)) if respondent_weights.size else 0.0
    positivity_min = float(np.min(rho_hat))
    overlap_score = float(np.mean(rho_hat >= max(0.05, min_observability)))

    basis = _diagnostic_basis(response_features_base, diagnostic_basis_spec)
    design_moments = (
        (
            base_weights[:, None]
            * ((response / rho_hat) - 1.0)[:, None]
            * basis
        ).sum(axis=0)
        / max(float(np.sum(base_weights)), 1e-12)
    )
    residual_term = np.zeros_like(Y, dtype=float)
    residual_term[observed_mask] = (Y[observed_mask] - m_hat[observed_mask]) / rho_hat[observed_mask]
    outcome_scale = max(_weighted_std(Y[observed_mask], base_weights[observed_mask]), 1e-6)
    imputation_moments = (
        (base_weights[:, None] * residual_term[:, None] * basis).sum(axis=0)
        / max(float(np.sum(base_weights)), 1e-12)
    )
    design_score = float(np.max(np.abs(design_moments)))
    imputation_score = float(np.max(np.abs(imputation_moments)) / outcome_scale)

    response_fit_gain = _weighted_brier_gain(response, rho_hat, base_weights)
    outcome_r2 = _weighted_r2(Y[observed_mask], m_hat[observed_mask], base_weights[observed_mask])

    weighted_missing_share = 1.0 - _weighted_mean(response, base_weights)
    sensitivity_shift = sensitivity_radius * outcome_scale * weighted_missing_share
    sensitivity_low = float(estimate - sensitivity_shift)
    sensitivity_high = float(estimate + sensitivity_shift)

    design_spec = SurveyDesignSpec(
        weights=base_weights,
        strata=strata,
        psu=clusters,
        replicate_weights=replicate_weights,
        provenance="base+nonresponse",
    )
    weight_regime = diagnose_weight_regime(
        design_spec,
        sampling_spec=SamplingModelSpec(sampled=response),
        influence_values=linearized,
    )

    crossfit_info = dict(fold_plan.info)
    crossfit_info.update(outcome_info_base)
    crossfit_info.update(response_info_base)

    return _CoreEstimate(
        estimate=float(estimate),
        variance_estimate=float(variance_estimate),
        standard_error=standard_error,
        variance_mode=variance_mode,
        replicate_estimates=replicate_estimates,
        linearized=linearized,
        pseudo_outcome=pseudo_outcome,
        response_propensity=rho_hat,
        outcome_regression=m_hat,
        reference_outcome_regression=None,
        selection_membership_probability=None,
        selection_odds=None,
        design_moments=design_moments,
        imputation_moments=imputation_moments,
        design_score=design_score,
        imputation_score=imputation_score,
        response_fit_gain=response_fit_gain,
        outcome_r2=outcome_r2,
        overlap_score=overlap_score,
        effective_sample_size=effective_sample_size,
        max_weight=max_weight,
        weight_cv=weight_cv,
        positivity_min=positivity_min,
        sensitivity_low=sensitivity_low,
        sensitivity_high=sensitivity_high,
        crossfit_info=crossfit_info,
        estimation_mode="one_sample",
        shadow_metrics=shadow_metrics,
        weight_regime_report={
            "weight_regime": weight_regime.weight_regime,
            "claim_level": weight_regime.claim_level,
            "warnings": list(weight_regime.warnings),
            "positivity_flags": list(weight_regime.positivity_flags),
            "psu_leverage_flags": list(weight_regime.psu_leverage_flags),
            "report": dict(weight_regime.report),
        },
    )


def _estimate_reference_integration(
    *,
    X: np.ndarray,
    Y: np.ndarray,
    response: np.ndarray,
    base_weights: np.ndarray,
    strata: np.ndarray,
    clusters: np.ndarray,
    shadow: np.ndarray | None,
    replicate_weights: np.ndarray | None,
    reference_X: np.ndarray,
    reference_weights: np.ndarray,
    reference_strata: np.ndarray,
    reference_clusters: np.ndarray,
    reference_shadow: np.ndarray | None,
    reference_replicates: np.ndarray | None,
    regime: SurveyRequestedRegime,
    variance_mode_requested: SurveyVarianceMode,
    n_folds: int,
    seed: int,
    diagnostic_threshold: float,
    sensitivity_radius: float,
    diagnostic_basis_spec: str,
    min_observability: float,
    max_weight_rule: float | None,
) -> _CoreEstimate:
    observed_mask = response > 0.5
    fold_plan = _build_fold_plan(
        response,
        strata=strata,
        clusters=clusters,
        n_folds=n_folds,
        seed=seed,
    )

    outcome_features_base = _augment_outcome_features(X)
    response_features_base = _augment_response_features(
        X,
        base_weights=base_weights,
        strata=strata,
        clusters=clusters,
    )
    reference_outcome_features_base = _augment_outcome_features(reference_X)

    m_base, outcome_info_base = _cross_fit_outcome(
        outcome_features_base,
        outcome_features_base,
        Y,
        response,
        base_weights,
        folds=fold_plan.folds,
    )
    m_ref_base, _ = _cross_fit_outcome(
        outcome_features_base,
        reference_outcome_features_base,
        Y,
        response,
        base_weights,
        folds=fold_plan.folds,
    )
    rho_base, response_info_base = _cross_fit_response(
        response_features_base,
        response,
        base_weights,
        folds=fold_plan.folds,
        min_observability=min_observability,
        max_weight=max_weight_rule,
    )

    shadow_metrics: dict[str, float] = {
        "shadow_incremental_r2": 0.0,
        "shadow_tilting_gain": 0.0,
        "n_shadow_variables": float(0 if shadow is None else shadow.shape[1]),
    }
    m_hat = m_base
    rho_hat = rho_base
    m_ref = m_ref_base

    if regime is SurveyRequestedRegime.MNAR_SHADOW and shadow is not None and reference_shadow is not None:
        outcome_features_shadow = _augment_outcome_features(X, shadow)
        reference_outcome_features_shadow = _augment_outcome_features(reference_X, reference_shadow)
        m_shadow, outcome_info_shadow = _cross_fit_outcome(
            outcome_features_shadow,
            outcome_features_shadow,
            Y,
            response,
            base_weights,
            folds=fold_plan.folds,
        )
        m_ref_shadow, _ = _cross_fit_outcome(
            outcome_features_shadow,
            reference_outcome_features_shadow,
            Y,
            response,
            base_weights,
            folds=fold_plan.folds,
        )
        proxy_signal = _standardize_vector(m_shadow - m_base)
        response_features_shadow = _augment_response_features(
            X,
            base_weights=base_weights,
            strata=strata,
            clusters=clusters,
            extra_columns=(proxy_signal,),
        )
        rho_shadow, response_info_shadow = _cross_fit_response(
            response_features_shadow,
            response,
            base_weights,
            folds=fold_plan.folds,
            min_observability=min_observability,
            max_weight=max_weight_rule,
        )
        m_hat = m_shadow
        m_ref = m_ref_shadow
        rho_hat = rho_shadow
        shadow_metrics["shadow_incremental_r2"] = max(
            0.0,
            _weighted_r2(Y[observed_mask], m_shadow[observed_mask], base_weights[observed_mask])
            - _weighted_r2(Y[observed_mask], m_base[observed_mask], base_weights[observed_mask]),
        )
        shadow_metrics["shadow_tilting_gain"] = max(
            0.0,
            _weighted_brier_gain(response, rho_shadow, base_weights)
            - _weighted_brier_gain(response, rho_base, base_weights),
        )
        outcome_info_base["min_train_respondents"] = min(
            outcome_info_base["min_train_respondents"],
            outcome_info_shadow["min_train_respondents"],
        )
        response_info_base["n_truncated_observabilities"] = max(
            response_info_base["n_truncated_observabilities"],
            response_info_shadow["n_truncated_observabilities"],
        )

    selection_odds, membership_prob, membership_info = _cross_fit_reference_membership(
        analytic_features=X,
        reference_features=reference_X,
        analytic_weights=base_weights,
        reference_weights=reference_weights,
        folds=fold_plan.folds,
    )

    correction_weights = np.zeros_like(base_weights, dtype=float)
    correction_weights[observed_mask] = (
        base_weights[observed_mask]
        / (rho_hat[observed_mask] * selection_odds[observed_mask])
    )
    reference_total = max(float(np.sum(reference_weights)), 1e-12)
    baseline = _weighted_mean(m_ref, reference_weights)
    correction = float(
        np.sum(correction_weights[observed_mask] * (Y[observed_mask] - m_hat[observed_mask])) / reference_total
    )
    estimate = float(baseline + correction)

    analytic_linearized = np.zeros_like(base_weights, dtype=float)
    analytic_linearized[observed_mask] = (
        correction_weights[observed_mask] * (Y[observed_mask] - m_hat[observed_mask]) / reference_total
    )
    reference_linearized = reference_weights * (m_ref - baseline) / reference_total
    linearized = np.concatenate([reference_linearized, analytic_linearized])
    combined_strata = np.concatenate(
        [
            _prefixed_labels(reference_strata, "reference"),
            _prefixed_labels(strata, "analytic"),
        ]
    )
    combined_clusters = np.concatenate(
        [
            _prefixed_labels(reference_clusters, "reference"),
            _prefixed_labels(clusters, "analytic"),
        ]
    )

    variance_mode = variance_mode_requested
    replicate_estimates: np.ndarray | None = None
    if variance_mode_requested is SurveyVarianceMode.REPLICATE and (
        replicate_weights is not None or reference_replicates is not None
    ):
        def _rep_fn(analytic_rep: np.ndarray | None, reference_rep: np.ndarray | None) -> float:
            rep_analytic = base_weights if analytic_rep is None else analytic_rep
            rep_reference = reference_weights if reference_rep is None else reference_rep
            rep_baseline = _weighted_mean(m_ref, rep_reference)
            rep_total = max(float(np.sum(rep_reference)), 1e-12)
            rep_correction = float(
                np.sum(
                    np.where(
                        observed_mask,
                        rep_analytic / (rho_hat * selection_odds) * (Y - m_hat),
                        0.0,
                    )
                )
                / rep_total
            )
            return float(rep_baseline + rep_correction)

        variance_estimate, replicate_estimates = _replicate_variance(
            _rep_fn,
            analytic_replicates=replicate_weights,
            reference_replicates=reference_replicates,
        )
    else:
        if variance_mode_requested is SurveyVarianceMode.REPLICATE:
            variance_mode = SurveyVarianceMode.SANDWICH
        variance_estimate = _design_linearized_variance(
            linearized,
            strata=combined_strata,
            clusters=combined_clusters,
        )
    standard_error = float(np.sqrt(max(variance_estimate, 0.0)))

    combined_weights = np.concatenate([reference_weights, correction_weights[observed_mask]])
    effective_sample_size = (
        float(np.sum(combined_weights) ** 2 / np.sum(combined_weights**2))
        if combined_weights.size and np.sum(combined_weights**2) > 0.0
        else 0.0
    )
    weight_cv = (
        float(np.std(combined_weights) / max(np.mean(combined_weights), 1e-12))
        if combined_weights.size
        else 0.0
    )
    max_weight = float(np.max(combined_weights)) if combined_weights.size else 0.0
    positivity_min = float(min(np.min(rho_hat), np.min(1.0 / (1.0 + selection_odds))))
    overlap_score = float(
        np.mean(
            (rho_hat >= max(0.05, min_observability))
            & (membership_prob >= 0.05)
            & (membership_prob <= 0.95)
        )
    )

    pooled_basis = _diagnostic_basis(np.vstack([X, reference_X]), diagnostic_basis_spec)
    analytic_basis = pooled_basis[: X.shape[0]]
    reference_basis = pooled_basis[X.shape[0] :]
    design_moments = (
        np.sum(correction_weights[:, None] * analytic_basis, axis=0) / reference_total
        - np.sum(reference_weights[:, None] * reference_basis, axis=0) / reference_total
    )
    outcome_scale = max(_weighted_std(Y[observed_mask], base_weights[observed_mask]), 1e-6)
    imputation_moments = (
        np.sum(
            correction_weights[:, None]
            * np.where(observed_mask[:, None], (Y - m_hat)[:, None], 0.0)
            * analytic_basis,
            axis=0,
        )
        / max(reference_total * outcome_scale, 1e-12)
    )
    design_score = float(np.max(np.abs(design_moments)))
    imputation_score = float(np.max(np.abs(imputation_moments)))

    response_fit_gain = _weighted_brier_gain(response, rho_hat, base_weights)
    outcome_r2 = _weighted_r2(Y[observed_mask], m_hat[observed_mask], base_weights[observed_mask])
    weighted_missing_share = 1.0 - _weighted_mean(response, base_weights)
    sensitivity_shift = sensitivity_radius * outcome_scale * weighted_missing_share
    sensitivity_low = float(estimate - sensitivity_shift)
    sensitivity_high = float(estimate + sensitivity_shift)

    combined_design = SurveyDesignSpec(
        weights=np.concatenate([reference_weights, base_weights]),
        strata=combined_strata,
        psu=combined_clusters,
        provenance="base+nonresponse",
    )
    weight_regime = diagnose_weight_regime(
        combined_design,
        influence_values=linearized,
    )

    crossfit_info = dict(fold_plan.info)
    crossfit_info.update(outcome_info_base)
    crossfit_info.update(response_info_base)
    crossfit_info.update(membership_info)

    pseudo_outcome = np.zeros_like(base_weights, dtype=float)
    pseudo_outcome[observed_mask] = correction_weights[observed_mask] * (Y[observed_mask] - m_hat[observed_mask])

    return _CoreEstimate(
        estimate=estimate,
        variance_estimate=float(variance_estimate),
        standard_error=standard_error,
        variance_mode=variance_mode,
        replicate_estimates=replicate_estimates,
        linearized=linearized,
        pseudo_outcome=pseudo_outcome,
        response_propensity=rho_hat,
        outcome_regression=m_hat,
        reference_outcome_regression=m_ref,
        selection_membership_probability=membership_prob,
        selection_odds=selection_odds,
        design_moments=design_moments,
        imputation_moments=imputation_moments,
        design_score=design_score,
        imputation_score=imputation_score,
        response_fit_gain=response_fit_gain,
        outcome_r2=outcome_r2,
        overlap_score=overlap_score,
        effective_sample_size=effective_sample_size,
        max_weight=max_weight,
        weight_cv=weight_cv,
        positivity_min=positivity_min,
        sensitivity_low=sensitivity_low,
        sensitivity_high=sensitivity_high,
        crossfit_info=crossfit_info,
        estimation_mode="reference_integration",
        shadow_metrics=shadow_metrics,
        weight_regime_report={
            "weight_regime": weight_regime.weight_regime,
            "claim_level": weight_regime.claim_level,
            "warnings": list(weight_regime.warnings),
            "positivity_flags": list(weight_regime.positivity_flags),
            "psu_leverage_flags": list(weight_regime.psu_leverage_flags),
            "report": dict(weight_regime.report),
        },
    )


def _missingness_requires_guardrail(
    assessment: MissingnessAssessmentReport | None,
) -> bool:
    if assessment is None:
        return False
    return assessment.status in {
        MissingnessAssessmentStatus.NOT_RECOVERABLE,
        MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE,
    }


@foundry_method(
    namespace="survey.dr",
    version="1.0.0",
    tags={"survey", "doubly-robust", "missingness", "aipw"},
)
class DesignMissingnessDREstimator:
    """Design-aware DR estimator with regime diagnostics and survey certificate."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="design_missingness",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("Y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("response_indicator", SlotType.VECTOR, Unit("indicator", "binary"), shape=("n_obs",)),
                SlotSpec("base_weights", SlotType.VECTOR, Unit("weight", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="regime", default="population_mar"),
            ParameterSpec(name="design_model", default="known_weights"),
            ParameterSpec(name="response_model", default="logit"),
            ParameterSpec(name="outcome_model", default="linear"),
            ParameterSpec(name="crossfit_folds", default=5),
            ParameterSpec(name="weight_truncation_rule", default="none"),
            ParameterSpec(name="variance_mode", default="sandwich"),
            ParameterSpec(name="diagnostic_basis_spec", default="intercept+linear:5"),
            ParameterSpec(name="diagnostic_threshold", default=0.05),
            ParameterSpec(name="sensitivity_radius", default=0.25),
            ParameterSpec(name="seed", default=42),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Design-adjusted doubly robust mean estimation under survey item nonresponse "
            "with explicit regime diagnostics for population-MAR, shadow-variable MNAR, "
            "and probability-reference integration."
        ),
        tags=frozenset(
            {
                "survey",
                "doubly-robust",
                "missingness",
                "aipw",
                "quality-certificate",
                "mnar-shadow",
                "reference-integration",
            }
        ),
        citations=(
            "Bang, H. & Robins, J.M. (2005). Doubly robust estimation in missing data and causal inference models.",
            "Särndal, C.-E., Swensson, B. & Wretman, J. (1992). Model Assisted Survey Sampling.",
        ),
        equations={
            "design_aipw": "psi_hat = sum_i d_i [R_i (Y_i - m_i)/rho_i + m_i] / sum_i d_i",
            "reference_dr": "psi_hat = sum_{i in A} d_A m_i / sum_A d_A + sum_{i in B_R} w_i (Y_i - m_i)/(rho_i * o_i) / sum_A d_A",
            "design_moment": "G_omega = sum_i d_i (R_i/rho_i - 1) b(X_i) / sum_i d_i",
            "imputation_moment": "G_m = sum_i d_i R_i (Y_i - m_i) q(X_i) / (rho_i sum_i d_i)",
        },
        assumptions={
            "population_mar": "E[Y | X, design, R=1] = E[Y | X, design]",
            "mnar_shadow": "Shadow-variable control function identifies an operational MNAR branch under explicit diagnostics",
            "cross_fitting": "Nuisance functions are estimated out-of-fold, preferably by PSU within strata",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Survey or administrative microdata with base weights, item nonresponse, "
            "optional probability-reference samples, and a need for auditable robustness diagnostics."
        ),
        when_not_to_use=(
            "Arbitrary MNAR mechanisms without shadow variables, validation structure, or a recoverable "
            "administrative-missingness assessment."
        ),
        output_interpretation=(
            "estimate is the target mean under the requested regime; survey_quality_certificate records "
            "which robustness claim appears operationally admissible and why."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = _matrix(state, "X")
        Y = _vector(state, "Y")
        response = _vector(state, "response_indicator")
        base_weights = _vector(state, "base_weights")
        n = X.shape[0]
        if Y.shape[0] != n or response.shape[0] != n or base_weights.shape[0] != n:
            raise ValueError("X, Y, response_indicator, and base_weights must align on n_obs")
        if np.any((response < 0.0) | (response > 1.0)):
            raise ValueError("response_indicator must lie in [0, 1]")
        if np.any(base_weights <= 0.0):
            raise ValueError("base_weights must be strictly positive")

        observed_mask = response > 0.5
        if not np.any(observed_mask):
            raise ValueError("At least one observed outcome is required")
        if np.any(~np.isfinite(Y[observed_mask])):
            raise ValueError("Observed outcomes must be finite")

        regime = SurveyRequestedRegime(str(params.get("regime", "population_mar")))
        variance_mode_requested = SurveyVarianceMode(str(params.get("variance_mode", "sandwich")))
        design_model = str(params.get("design_model", "known_weights")).strip().lower()
        response_model = str(params.get("response_model", "logit")).strip().lower()
        outcome_model = str(params.get("outcome_model", "linear")).strip().lower()
        if response_model not in {"logit"}:
            raise NotImplementedError(f"Unsupported response_model {response_model!r}")
        if outcome_model not in {"linear", "ols"}:
            raise NotImplementedError(f"Unsupported outcome_model {outcome_model!r}")
        if design_model not in {"known_weights", "logit"}:
            raise NotImplementedError(f"Unsupported design_model {design_model!r}")

        crossfit_folds = max(2, int(params.get("crossfit_folds", 5)))
        seed = int(params.get("seed", 42))
        diagnostic_threshold = max(float(params.get("diagnostic_threshold", 0.05)), 1e-6)
        sensitivity_radius = max(float(params.get("sensitivity_radius", 0.25)), 0.0)
        diagnostic_basis_spec = str(params.get("diagnostic_basis_spec", "intercept+linear:5"))
        min_observability, max_weight_rule = _parse_weight_truncation_rule(
            params.get("weight_truncation_rule", "none")
        )

        strata = _label_vector(state, "strata", n, np.zeros(n, dtype=object))
        clusters = _label_vector(state, "clusters", n, np.asarray(np.arange(n), dtype=object))
        shadow = _shadow_matrix(state, "shadow_variables", n)
        replicate_weights = _replicate_matrix(state, "replicate_weights", n)
        missingness_assessment = _normalize_missingness_assessment(state)

        reference_X = _optional_matrix(state, "reference_X")
        reference_weights = _optional_vector(state, "reference_design_weights")
        reference_shadow: np.ndarray | None = None
        reference_replicates: np.ndarray | None = None
        if reference_X is not None or reference_weights is not None:
            if reference_X is None or reference_weights is None:
                raise ValueError("reference_X and reference_design_weights must be provided together")
            if reference_X.shape[1] != X.shape[1]:
                raise ValueError("reference_X must have the same number of columns as X")
            n_ref = reference_X.shape[0]
            if reference_weights.shape[0] != n_ref:
                raise ValueError("reference_design_weights must align with reference_X")
            if np.any(reference_weights <= 0.0):
                raise ValueError("reference_design_weights must be strictly positive")
            reference_shadow = _shadow_matrix(state, "reference_shadow_variables", n_ref)
            reference_replicates = _replicate_matrix(state, "reference_replicate_weights", n_ref)
            reference_strata = _label_vector(
                state,
                "reference_strata",
                n_ref,
                np.zeros(n_ref, dtype=object),
            )
            reference_clusters = _label_vector(
                state,
                "reference_clusters",
                n_ref,
                np.asarray(np.arange(n_ref), dtype=object),
            )
        else:
            n_ref = 0
            reference_strata = np.zeros(0, dtype=object)
            reference_clusters = np.zeros(0, dtype=object)

        if regime is SurveyRequestedRegime.MNAR_SHADOW and shadow is None:
            # We still build the certificate below, but the identification branch cannot pass.
            pass

        if reference_X is not None and design_model not in {"logit", "known_weights"}:
            raise NotImplementedError("Reference integration currently supports logit / known_weights design models only")

        if reference_X is None:
            estimate_result = _estimate_one_sample(
                X=X,
                Y=Y,
                response=response,
                base_weights=base_weights,
                strata=strata,
                clusters=clusters,
                shadow=shadow,
                replicate_weights=replicate_weights,
                regime=regime,
                variance_mode_requested=variance_mode_requested,
                n_folds=crossfit_folds,
                seed=seed,
                diagnostic_threshold=diagnostic_threshold,
                sensitivity_radius=sensitivity_radius,
                diagnostic_basis_spec=diagnostic_basis_spec,
                min_observability=min_observability,
                max_weight_rule=max_weight_rule,
            )
        else:
            estimate_result = _estimate_reference_integration(
                X=X,
                Y=Y,
                response=response,
                base_weights=base_weights,
                strata=strata,
                clusters=clusters,
                shadow=shadow,
                replicate_weights=replicate_weights,
                reference_X=reference_X,
                reference_weights=reference_weights,
                reference_strata=reference_strata,
                reference_clusters=reference_clusters,
                reference_shadow=reference_shadow,
                reference_replicates=reference_replicates,
                regime=regime,
                variance_mode_requested=variance_mode_requested,
                n_folds=crossfit_folds,
                seed=seed,
                diagnostic_threshold=diagnostic_threshold,
                sensitivity_radius=sensitivity_radius,
                diagnostic_basis_spec=diagnostic_basis_spec,
                min_observability=min_observability,
                max_weight_rule=max_weight_rule,
            )

        positivity_status = (
            SurveyAssumptionStatus.PASS
            if estimate_result.positivity_min >= 0.05
            else SurveyAssumptionStatus.WARN
            if estimate_result.positivity_min >= 0.01
            else SurveyAssumptionStatus.FAIL
        )
        weight_stability_status = (
            SurveyAssumptionStatus.PASS
            if estimate_result.weight_cv <= 1.0
            else SurveyAssumptionStatus.WARN
            if estimate_result.weight_cv <= 2.5
            else SurveyAssumptionStatus.FAIL
        )
        design_status = _status_from_score(
            estimate_result.design_score,
            pass_threshold=diagnostic_threshold,
            warn_threshold=2.0 * diagnostic_threshold,
        )
        imputation_status = _status_from_score(
            estimate_result.imputation_score,
            pass_threshold=diagnostic_threshold,
            warn_threshold=2.0 * diagnostic_threshold,
        )
        response_fit_status = (
            SurveyAssumptionStatus.PASS
            if estimate_result.response_fit_gain >= 0.05
            else SurveyAssumptionStatus.WARN
            if estimate_result.response_fit_gain >= 0.01
            else SurveyAssumptionStatus.FAIL
        )
        outcome_fit_status = (
            SurveyAssumptionStatus.PASS
            if estimate_result.outcome_r2 >= 0.10
            else SurveyAssumptionStatus.WARN
            if estimate_result.outcome_r2 >= 0.02
            else SurveyAssumptionStatus.FAIL
        )
        crossfit_status = (
            SurveyAssumptionStatus.PASS
            if estimate_result.crossfit_info.get("n_folds", 0) >= 2
            and estimate_result.crossfit_info.get("min_train_respondents", 0)
            >= max(X.shape[1] + 2, 8)
            else SurveyAssumptionStatus.WARN
        )
        replicate_status = (
            SurveyAssumptionStatus.PASS
            if (
                variance_mode_requested is not SurveyVarianceMode.REPLICATE
                or replicate_weights is not None
                or reference_replicates is not None
            )
            else SurveyAssumptionStatus.WARN
        )
        variance_status = (
            SurveyAssumptionStatus.PASS
            if np.isfinite(estimate_result.standard_error) and estimate_result.standard_error >= 0.0
            else SurveyAssumptionStatus.FAIL
        )

        design_assumptions = [
            _component(
                component_id="frame_coverage",
                layer=SurveyAssumptionLayer.DESIGN,
                statement="Frame coverage is still an upstream governance concern, not something the estimator can prove from outcomes alone.",
                status=SurveyAssumptionStatus.UNTESTED,
                notes=["Use external evidence or DataReadinessReport to upgrade this component."],
            ),
            _component(
                component_id="inclusion_identifiable",
                layer=SurveyAssumptionLayer.DESIGN,
                statement="Base design weights are present, finite, and strictly positive.",
                status=SurveyAssumptionStatus.PASS,
                metric_name="min_base_weight",
                metric_value=float(np.min(base_weights)),
                threshold_value=0.0,
            ),
            _component(
                component_id="calibration_margins_match",
                layer=SurveyAssumptionLayer.DESIGN,
                statement="Design-side orthogonality moments are close to zero on the chosen diagnostic basis.",
                status=design_status,
                metric_name="orthogonality_score_design",
                metric_value=estimate_result.design_score,
                threshold_value=diagnostic_threshold,
            ),
            _component(
                component_id="positivity",
                layer=SurveyAssumptionLayer.POSITIVITY,
                statement="Estimated observability weights remain bounded away from pathological tails.",
                status=positivity_status,
                metric_name="min_observability",
                metric_value=estimate_result.positivity_min,
                threshold_value=max(min_observability, 0.05),
                notes=["The method reports any truncation through crossfit diagnostics; clipping is never silent."],
            ),
            _component(
                component_id="weight_stability",
                layer=SurveyAssumptionLayer.DESIGN,
                statement="Final analysis weights are not dominated by a thin tail.",
                status=weight_stability_status,
                metric_name="weight_cv",
                metric_value=estimate_result.weight_cv,
                threshold_value=1.0,
                notes=[f"max_weight={estimate_result.max_weight:.6f}"],
            ),
            _component(
                component_id="replicate_design_available",
                layer=SurveyAssumptionLayer.VARIANCE,
                statement="Replicate weights are available when replicate variance is requested.",
                status=replicate_status,
                metric_name="n_replicates",
                metric_value=float(
                    0
                    if estimate_result.replicate_estimates is None
                    else estimate_result.replicate_estimates.shape[0]
                ),
                threshold_value=1.0,
            ),
        ]

        imputation_assumptions = [
            _component(
                component_id="outcome_support_overlap",
                layer=SurveyAssumptionLayer.IMPUTATION,
                statement="Observed outcome support overlaps sufficiently with the weighted analytic target.",
                status=positivity_status,
                metric_name="overlap_score",
                metric_value=estimate_result.overlap_score,
                threshold_value=0.5,
            ),
            _component(
                component_id="outcome_model_fit",
                layer=SurveyAssumptionLayer.IMPUTATION,
                statement="Out-of-fold weighted outcome regression explains respondent outcome variation.",
                status=outcome_fit_status,
                metric_name="weighted_r2",
                metric_value=estimate_result.outcome_r2,
                threshold_value=0.10,
            ),
            _component(
                component_id="residual_orthogonality",
                layer=SurveyAssumptionLayer.IMPUTATION,
                statement="Outcome-side orthogonality moments are close to zero on the chosen diagnostic basis.",
                status=imputation_status,
                metric_name="orthogonality_score_imputation",
                metric_value=estimate_result.imputation_score,
                threshold_value=diagnostic_threshold,
            ),
            _component(
                component_id="missingness_model_fit",
                layer=SurveyAssumptionLayer.IMPUTATION,
                statement="The response model improves on a weighted intercept-only benchmark.",
                status=response_fit_status,
                metric_name="response_fit_gain",
                metric_value=estimate_result.response_fit_gain,
                threshold_value=0.05,
            ),
            _component(
                component_id="crossfit_honesty",
                layer=SurveyAssumptionLayer.IMPUTATION,
                statement="Nuisance models are fit out-of-fold with fold assignments that respect dependence when design metadata exists.",
                status=crossfit_status,
                metric_name="min_train_respondents",
                metric_value=float(estimate_result.crossfit_info.get("min_train_respondents", 0)),
                threshold_value=float(max(X.shape[1] + 2, 8)),
                notes=[str(estimate_result.crossfit_info.get("fold_assignment", "unknown"))],
            ),
        ]

        blocking_reasons: list[str] = []
        identification_assumptions: list[SurveyAssumptionComponent] = []
        design_valid = (
            design_status is SurveyAssumptionStatus.PASS
            and positivity_status is not SurveyAssumptionStatus.FAIL
            and weight_stability_status is not SurveyAssumptionStatus.FAIL
            and variance_status is not SurveyAssumptionStatus.FAIL
        )
        imputation_valid = (
            imputation_status is SurveyAssumptionStatus.PASS
            and crossfit_status is not SurveyAssumptionStatus.FAIL
            and outcome_fit_status is not SurveyAssumptionStatus.FAIL
            and response_fit_status is not SurveyAssumptionStatus.FAIL
            and positivity_status is not SurveyAssumptionStatus.FAIL
        )
        design_plausible = (
            design_status is not SurveyAssumptionStatus.FAIL
            and positivity_status is not SurveyAssumptionStatus.FAIL
            and weight_stability_status is not SurveyAssumptionStatus.FAIL
            and variance_status is not SurveyAssumptionStatus.FAIL
        )
        imputation_plausible = (
            imputation_status is not SurveyAssumptionStatus.FAIL
            and crossfit_status is not SurveyAssumptionStatus.FAIL
            and outcome_fit_status is not SurveyAssumptionStatus.FAIL
            and response_fit_status is not SurveyAssumptionStatus.FAIL
            and positivity_status is not SurveyAssumptionStatus.FAIL
        )

        if positivity_status is SurveyAssumptionStatus.FAIL:
            blocking_reasons.append("positivity_violation")
        if variance_status is SurveyAssumptionStatus.FAIL:
            blocking_reasons.append("variance_not_estimable")

        if missingness_assessment is not None and missingness_assessment.status is MissingnessAssessmentStatus.NOT_RECOVERABLE:
            blocking_reasons.append("missingness_not_recoverable")

        if regime is SurveyRequestedRegime.MNAR_SHADOW:
            shadow_incremental_r2 = estimate_result.shadow_metrics.get("shadow_incremental_r2", 0.0)
            shadow_tilting_gain = estimate_result.shadow_metrics.get("shadow_tilting_gain", 0.0)
            shadow_status = (
                SurveyAssumptionStatus.PASS
                if shadow is not None and shadow_incremental_r2 >= 0.01
                else SurveyAssumptionStatus.WARN
                if shadow is not None and shadow_incremental_r2 >= 0.002
                else SurveyAssumptionStatus.FAIL
            )
            tilting_status = (
                SurveyAssumptionStatus.PASS
                if shadow_tilting_gain >= 0.002
                else SurveyAssumptionStatus.WARN
                if shadow is not None
                else SurveyAssumptionStatus.FAIL
            )
            if missingness_assessment is None:
                validation_status = SurveyAssumptionStatus.WARN
                validation_notes = ["No external missingness assessment was supplied; identification rests entirely on the shadow branch."]
            elif missingness_assessment.status is MissingnessAssessmentStatus.RECOVERABLE:
                validation_status = SurveyAssumptionStatus.PASS
                validation_notes = ["Administrative missingness assessment is recoverable and compatible with identified estimation."]
            elif missingness_assessment.status is MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE:
                validation_status = SurveyAssumptionStatus.WARN
                validation_notes = ["Administrative missingness assessment is only partially recoverable; shadow identification remains a maintained working restriction."]
            else:
                validation_status = SurveyAssumptionStatus.FAIL
                validation_notes = ["Administrative missingness assessment marked the regime as not recoverable without stronger structure."]

            identification_assumptions.extend(
                [
                    _component(
                        component_id="shadow_variable_valid",
                        layer=SurveyAssumptionLayer.IDENTIFICATION,
                        statement="Shadow variables add incremental predictive information for the latent outcome.",
                        status=shadow_status,
                        metric_name="shadow_incremental_r2",
                        metric_value=shadow_incremental_r2,
                        threshold_value=0.01,
                        notes=[] if shadow is not None else ["No shadow_variables were supplied."],
                    ),
                    _component(
                        component_id="tilting_model_fit",
                        layer=SurveyAssumptionLayer.IDENTIFICATION,
                        statement="The shadow-induced control function improves the response model enough to support an MNAR tilting branch.",
                        status=tilting_status,
                        metric_name="shadow_tilting_gain",
                        metric_value=shadow_tilting_gain,
                        threshold_value=0.002,
                    ),
                    _component(
                        component_id="validation_link_available",
                        layer=SurveyAssumptionLayer.IDENTIFICATION,
                        statement="Administrative evidence or validation structure does not contradict the requested identified shadow branch.",
                        status=validation_status,
                        notes=validation_notes,
                    ),
                ]
            )

            if (
                shadow_status is not SurveyAssumptionStatus.FAIL
                and tilting_status is not SurveyAssumptionStatus.FAIL
                and validation_status is not SurveyAssumptionStatus.FAIL
                and design_plausible
                and imputation_plausible
                and not blocking_reasons
            ):
                regime_validated = SurveyValidatedRegime.MNAR_SHADOW_IDENTIFIED
            else:
                regime_validated = SurveyValidatedRegime.MNAR_UNIDENTIFIED
                if shadow is None:
                    blocking_reasons.append("mnar_shadow_requires_shadow_variables")
                else:
                    blocking_reasons.append("mnar_shadow_identification_failed")
        else:
            identification_assumptions.append(
                _component(
                    component_id="population_mar_given_design_covariates",
                    layer=SurveyAssumptionLayer.IDENTIFICATION,
                    statement="Population-MAR given observed covariates and design features remains a maintained working assumption, not a theorem proven by diagnostics.",
                    status=SurveyAssumptionStatus.WARN,
                    notes=["The design and imputation channels provide operational support, not proof of ignorability."],
                )
            )
            if _missingness_requires_guardrail(missingness_assessment):
                regime_validated = SurveyValidatedRegime.MNAR_UNIDENTIFIED
                blocking_reasons.append("missingness_assessment_requires_non_mar_identification")
            elif design_valid and imputation_valid:
                regime_validated = SurveyValidatedRegime.BOTH_VALID
            elif design_valid:
                regime_validated = SurveyValidatedRegime.DESIGN_VALID_ONLY
            elif imputation_valid:
                regime_validated = SurveyValidatedRegime.IMPUTATION_VALID_ONLY
            else:
                regime_validated = SurveyValidatedRegime.NEITHER_VALID

        blocking_reasons = _stable_strings(blocking_reasons)
        regime_warning: str | None = None
        if regime_validated is SurveyValidatedRegime.DESIGN_VALID_ONLY:
            regime_warning = "consistency relies on observability/design specification"
        elif regime_validated is SurveyValidatedRegime.IMPUTATION_VALID_ONLY:
            regime_warning = "consistency relies on outcome/imputation specification"
        elif regime_validated is SurveyValidatedRegime.MNAR_SHADOW_IDENTIFIED:
            regime_warning = "identified MNAR branch relies on shadow-variable control-function restrictions"

        overall_pass = (
            regime_validated
            in {
                SurveyValidatedRegime.BOTH_VALID,
                SurveyValidatedRegime.DESIGN_VALID_ONLY,
                SurveyValidatedRegime.IMPUTATION_VALID_ONLY,
                SurveyValidatedRegime.MNAR_SHADOW_IDENTIFIED,
            }
            and not blocking_reasons
        )
        dataset_context = resolve_dataset_context(state, params)

        certificate = build_survey_quality_certificate(
            target_estimand="E[Y]",
            estimator_id="survey.dr.design_missingness@1.0.0",
            dataset_id=dataset_context.get("dataset_id"),
            data_origin=dataset_context.get("data_origin"),
            regime_requested=regime,
            regime_validated=regime_validated,
            estimate=float(estimate_result.estimate),
            standard_error=estimate_result.standard_error,
            variance_mode=estimate_result.variance_mode,
            estimated_efficiency_bound=(
                estimate_result.variance_estimate
                if regime_validated is SurveyValidatedRegime.BOTH_VALID
                else None
            ),
            design_assumptions=design_assumptions,
            imputation_assumptions=imputation_assumptions,
            identification_assumptions=identification_assumptions,
            missingness_assessment=missingness_assessment,
            overlap_score=estimate_result.overlap_score,
            effective_sample_size=estimate_result.effective_sample_size,
            max_weight=estimate_result.max_weight,
            weight_cv=estimate_result.weight_cv,
            orthogonality_score_design=estimate_result.design_score,
            orthogonality_score_imputation=estimate_result.imputation_score,
            sensitivity_radius=sensitivity_radius,
            overall_pass=overall_pass,
            blocking_reasons=blocking_reasons,
            evidence_payload={
                "estimation_mode": estimate_result.estimation_mode,
                "respondent_fraction": float(np.mean(observed_mask)),
                "n_obs": int(n),
                "n_respondents": int(np.sum(observed_mask)),
                "n_reference": int(n_ref),
                "design_moments": estimate_result.design_moments.tolist(),
                "imputation_moments": estimate_result.imputation_moments.tolist(),
                "crossfit": estimate_result.crossfit_info,
                "response_fit_gain": estimate_result.response_fit_gain,
                "outcome_weighted_r2": estimate_result.outcome_r2,
                "sensitivity_envelope": [
                    estimate_result.sensitivity_low,
                    estimate_result.sensitivity_high,
                ],
                "shadow_metrics": estimate_result.shadow_metrics,
                "weight_truncation_rule": {
                    "min_observability": min_observability,
                    "max_weight": max_weight_rule,
                },
                "weight_regime": estimate_result.weight_regime_report,
                "selection_membership_probability": (
                    None
                    if estimate_result.selection_membership_probability is None
                    else estimate_result.selection_membership_probability.tolist()
                ),
                "selection_odds": (
                    None
                    if estimate_result.selection_odds is None
                    else estimate_result.selection_odds.tolist()
                ),
                "design_model": design_model,
                "response_model": response_model,
                "outcome_model": outcome_model,
                "regime_warning": regime_warning,
            },
        )
        artifact_store = resolve_artifact_store(state, params)
        certificate_ref = (
            persist_survey_quality_certificate(artifact_store, certificate)
            if artifact_store is not None
            else None
        )

        return {
            "result": {
                "estimate": float(estimate_result.estimate),
                "standard_error": estimate_result.standard_error,
                "variance_estimate": float(estimate_result.variance_estimate),
                "variance_mode": estimate_result.variance_mode.value,
                "estimation_mode": estimate_result.estimation_mode,
                "effective_influence_function": estimate_result.linearized.tolist(),
                "pseudo_outcome": estimate_result.pseudo_outcome.tolist(),
                "response_propensity": estimate_result.response_propensity.tolist(),
                "outcome_regression": estimate_result.outcome_regression.tolist(),
                "reference_outcome_regression": (
                    None
                    if estimate_result.reference_outcome_regression is None
                    else estimate_result.reference_outcome_regression.tolist()
                ),
                "selection_membership_probability": (
                    None
                    if estimate_result.selection_membership_probability is None
                    else estimate_result.selection_membership_probability.tolist()
                ),
                "selection_odds": (
                    None
                    if estimate_result.selection_odds is None
                    else estimate_result.selection_odds.tolist()
                ),
                "effective_sample_size": estimate_result.effective_sample_size,
                "max_weight": estimate_result.max_weight,
                "weight_cv": estimate_result.weight_cv,
                "overlap_score": estimate_result.overlap_score,
                "orthogonality_score_design": estimate_result.design_score,
                "orthogonality_score_imputation": estimate_result.imputation_score,
                "sensitivity_envelope": {
                    "lower": estimate_result.sensitivity_low,
                    "upper": estimate_result.sensitivity_high,
                    "radius": sensitivity_radius,
                },
                "replicate_estimates": (
                    None
                    if estimate_result.replicate_estimates is None
                    else estimate_result.replicate_estimates.tolist()
                ),
                "survey_quality_certificate": certificate.model_dump(mode="json"),
                "survey_quality_certificate_ref": (
                    None if certificate_ref is None else certificate_ref.model_dump(mode="json")
                ),
            }
        }


__all__ = ["DesignMissingnessDREstimator"]
