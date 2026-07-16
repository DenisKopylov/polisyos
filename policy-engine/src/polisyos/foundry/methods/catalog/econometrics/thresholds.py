"""Estimate threshold, kink, FRD, and FRKD models with state-dependent policy surfaces."""

from __future__ import annotations

from collections.abc import Mapping
from statistics import NormalDist
from typing import Any, ClassVar

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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsReport,
    PartialIdentificationResult,
)
from polisyos.ir.observation.bundles import SpecificationCurveBundle, SpecificationCurveSource
from polisyos.ir.observation.contracts import ObservationFamily

from .protocols import (
    EconometricResult,
    ThresholdEffectModel,
    ThresholdIdentificationMode,
    ThresholdRegressionData,
    ThresholdScoreSummary,
    ThresholdStateField,
    ThresholdSurfaceMode,
)

_FLOAT_EPS = 1e-12
_DEFAULT_BOOTSTRAP_SEED = 1729


def _threshold_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=ThresholdRegressionData,
        nested_keys=("threshold_data",),
    )


def _materialize_threshold_data(
    bound_inputs: Mapping[str, Any],
    fallback_state: Any,
) -> ThresholdRegressionData:
    payload = _threshold_payload(fallback_state)
    payload.update(bound_inputs)
    return ThresholdRegressionData.model_validate(payload)


def _threshold_input_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="threshold_data",
                slot_type=SlotType.SCALAR,
                unit=Unit("threshold", "dataset"),
                contract_id=ThresholdRegressionData.contract_id,
            )
        }
    )


def _threshold_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec.for_output_contract(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("result", "json"),
                output_contract=EconometricResult,
            ),
            SlotSpec(
                name="uncertainty_envelope",
                slot_type=SlotType.SCALAR,
                unit=Unit("uncertainty", "json"),
            ),
            SlotSpec(
                name="specification_curve_bundle",
                slot_type=SlotType.SCALAR,
                unit=Unit("robustness", "json"),
            ),
            SlotSpec(
                name="bounds_report",
                slot_type=SlotType.SCALAR,
                unit=Unit("bounds", "json"),
            ),
        }
    )


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except Exception:
        return None
    if not np.isfinite(result):
        return None
    return result


def _python_scalar(value: Any) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        coerced = float(value)
    except Exception:
        return str(value)
    return coerced if np.isfinite(coerced) else None


def _resolve_observation_family(data: ThresholdRegressionData) -> ObservationFamily:
    raw = data.metadata.get("observation_family") if isinstance(data.metadata, dict) else None
    if isinstance(raw, ObservationFamily):
        return raw
    if isinstance(raw, str):
        text = raw.strip().lower()
        for family in ObservationFamily:
            if family.value == text or family.name.lower() == text:
                return family
    return ObservationFamily.MACRO_STATE


def _coerce_optional_vector(value: Any, *, length: int, field_name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float).reshape(-1)
    if arr.size != length:
        raise ValueError(f"{field_name} length must match state_variables column count")
    if not np.isfinite(arr).all():
        raise ValueError(f"{field_name} contains non-finite values")
    return arr


def _resolve_feature_names(data: ThresholdRegressionData) -> list[str]:
    return list(data.feature_names or [f"x{i}" for i in range(data.n_features)])


def _resolve_state_names(data: ThresholdRegressionData) -> list[str]:
    if data.n_states == 0:
        return []
    return list(data.state_names or [f"s{i}" for i in range(data.n_states)])


def _stack_columns(columns: list[np.ndarray]) -> np.ndarray:
    blocks: list[np.ndarray] = []
    for column in columns:
        arr = np.asarray(column)
        if arr.ndim == 1:
            arr = arr[:, None]
        elif arr.ndim != 2:
            raise ValueError("design blocks must be 1D or 2D arrays")
        blocks.append(arr.astype(float, copy=False))
    return np.hstack(blocks)


def _resolve_backend(params: Mapping[str, Any]) -> str:
    backend = str(params.get("estimation_backend", "ols")).strip().lower()
    if backend not in {"ols", "2sls", "gmm"}:
        return "ols"
    return backend


def _kernel_weights(score: np.ndarray, bandwidth: float, kernel: str) -> np.ndarray:
    scaled = np.abs(score) / max(float(bandwidth), _FLOAT_EPS)
    name = kernel.strip().lower()
    if name == "uniform":
        return (scaled <= 1.0).astype(float)
    if name == "epanechnikov":
        weights = 0.75 * (1.0 - scaled**2)
        return np.where(scaled <= 1.0, weights, 0.0)
    weights = 1.0 - scaled
    return np.where(scaled <= 1.0, weights, 0.0)


def _regression_summary(
    *,
    beta: np.ndarray,
    cov: np.ndarray,
    resid: np.ndarray,
    y: np.ndarray,
    X: np.ndarray,
    confidence_level: float,
) -> dict[str, Any]:
    n_obs, n_params = X.shape
    std = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    normal = NormalDist()
    alpha = max(1.0 - confidence_level, _FLOAT_EPS)
    z = normal.inv_cdf(1.0 - alpha / 2.0)

    t_stats = np.divide(beta, std, out=np.zeros_like(beta), where=std > _FLOAT_EPS)
    p_values = 2.0 * (1.0 - np.vectorize(normal.cdf)(np.abs(t_stats)))
    intervals = np.column_stack([beta - z * std, beta + z * std])

    centered = y - float(np.mean(y))
    tss = float(centered @ centered)
    rss = float(resid @ resid)
    r_squared = None
    adj_r_squared = None
    if tss > _FLOAT_EPS:
        r_squared = max(0.0, 1.0 - rss / tss)
        if n_obs > n_params:
            adj_r_squared = 1.0 - (1.0 - r_squared) * ((n_obs - 1.0) / max(n_obs - n_params, 1))

    return {
        "beta": beta,
        "std": std,
        "t_stats": t_stats,
        "p_values": p_values,
        "intervals": intervals,
        "rss": rss,
        "r_squared": r_squared,
        "adj_r_squared": adj_r_squared,
    }


def _ols_fit(
    y: np.ndarray,
    X: np.ndarray,
    *,
    confidence_level: float,
    cov_type: str,
) -> dict[str, Any]:
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n_obs, n_params = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)

    if cov_type == "classic":
        sigma2 = float(np.sum(resid**2) / max(n_obs - n_params, 1))
        cov = sigma2 * xtx_inv
    else:
        weighted = X * resid[:, None]
        meat = weighted.T @ weighted
        hc1_scale = n_obs / max(n_obs - n_params, 1)
        cov = hc1_scale * xtx_inv @ meat @ xtx_inv

    summary = _regression_summary(
        beta=beta,
        cov=cov,
        resid=resid,
        y=y,
        X=X,
        confidence_level=confidence_level,
    )
    summary["objective"] = summary["rss"]
    summary["j_statistic"] = None
    return summary


def _two_stage_least_squares_fit(
    y: np.ndarray,
    X: np.ndarray,
    Z: np.ndarray,
    *,
    confidence_level: float,
    cov_type: str,
) -> dict[str, Any]:
    ztz_inv = np.linalg.pinv(Z.T @ Z)
    x_hat = Z @ ztz_inv @ (Z.T @ X)
    bread = np.linalg.pinv(X.T @ x_hat)
    beta = bread @ (X.T @ Z @ ztz_inv @ (Z.T @ y))
    resid = y - X @ beta
    n_obs, n_params = X.shape

    if cov_type == "classic":
        sigma2 = float(np.sum(resid**2) / max(n_obs - n_params, 1))
        cov = sigma2 * bread
    else:
        meat = (x_hat * resid[:, None]).T @ (x_hat * resid[:, None])
        hc1_scale = n_obs / max(n_obs - n_params, 1)
        cov = hc1_scale * bread @ meat @ bread

    summary = _regression_summary(
        beta=beta,
        cov=cov,
        resid=resid,
        y=y,
        X=X,
        confidence_level=confidence_level,
    )
    summary["objective"] = summary["rss"]
    summary["j_statistic"] = None
    return summary


def _gmm_fit(
    y: np.ndarray,
    X: np.ndarray,
    Z: np.ndarray,
    *,
    confidence_level: float,
    weight_type: str,
) -> dict[str, Any]:
    n_obs = y.shape[0]
    if weight_type == "identity":
        W = np.eye(Z.shape[1])
    else:
        W = np.linalg.pinv((Z.T @ Z) / max(n_obs, 1))

    def solve(weight: np.ndarray) -> np.ndarray:
        bread = X.T @ Z @ weight @ Z.T @ X
        moments = X.T @ Z @ weight @ Z.T @ y
        return np.linalg.pinv(bread) @ moments

    beta_1 = solve(W)
    resid_1 = y - X @ beta_1
    S = ((Z * resid_1[:, None]).T @ (Z * resid_1[:, None])) / max(n_obs, 1)
    W_opt = (
        np.eye(Z.shape[1])
        if weight_type == "identity"
        else np.linalg.pinv(S + 1e-8 * np.eye(S.shape[0]))
    )

    beta = solve(W_opt)
    resid = y - X @ beta
    S_final = ((Z * resid[:, None]).T @ (Z * resid[:, None])) / max(n_obs, 1)
    G = (Z.T @ X) / max(n_obs, 1)
    bread = np.linalg.pinv(G.T @ W_opt @ G)
    cov = bread @ (G.T @ W_opt @ S_final @ W_opt @ G) @ bread / max(n_obs, 1)

    g_bar = (Z.T @ resid) / max(n_obs, 1)
    j_statistic = float(n_obs * (g_bar.T @ W_opt @ g_bar))

    summary = _regression_summary(
        beta=beta,
        cov=cov,
        resid=resid,
        y=y,
        X=X,
        confidence_level=confidence_level,
    )
    summary["objective"] = j_statistic
    summary["j_statistic"] = j_statistic
    return summary


def _weighted_least_squares_fit(
    y: np.ndarray,
    X: np.ndarray,
    weights: np.ndarray,
    *,
    confidence_level: float,
    cov_type: str,
) -> dict[str, Any]:
    sqrt_w = np.sqrt(np.clip(weights, 0.0, None))
    Xw = X * sqrt_w[:, None]
    yw = y * sqrt_w
    beta, _, _, _ = np.linalg.lstsq(Xw, yw, rcond=None)
    resid = y - X @ beta
    xtwx_inv = np.linalg.pinv(Xw.T @ Xw)
    n_obs, n_params = X.shape

    if cov_type == "classic":
        sigma2 = float(np.sum(weights * resid**2) / max(n_obs - n_params, 1))
        cov = sigma2 * xtwx_inv
    else:
        weighted = X * (weights * resid)[:, None]
        meat = weighted.T @ weighted
        hc1_scale = n_obs / max(n_obs - n_params, 1)
        cov = hc1_scale * xtwx_inv @ meat @ xtwx_inv

    summary = _regression_summary(
        beta=beta,
        cov=cov,
        resid=resid,
        y=y,
        X=X,
        confidence_level=confidence_level,
    )
    summary["objective"] = float(np.sum(weights * resid**2))
    return summary


def _resolve_state_surface(
    data: ThresholdRegressionData,
    params: Mapping[str, Any],
) -> tuple[np.ndarray, ThresholdSurfaceMode]:
    if data.n_states == 0:
        return np.zeros(0, dtype=float), ThresholdSurfaceMode.CONSTANT

    state_weight_values = params.get("state_policy_weights")
    if state_weight_values is not None:
        weights = _coerce_optional_vector(
            state_weight_values,
            length=data.n_states,
            field_name="state_policy_weights",
        )
        return weights, ThresholdSurfaceMode.AFFINE_STATE_FIXED

    if bool(params.get("estimate_state_weights", False)):
        design = _stack_columns([np.ones(data.n_obs), data.state_variables])
        coeffs, _, _, _ = np.linalg.lstsq(
            design,
            np.asarray(data.running_variable, dtype=float),
            rcond=None,
        )
        return np.asarray(coeffs[1:], dtype=float), ThresholdSurfaceMode.AFFINE_STATE_ESTIMATED

    return np.zeros(data.n_states, dtype=float), ThresholdSurfaceMode.CONSTANT


def _candidate_thresholds(
    base_score: np.ndarray,
    params: Mapping[str, Any],
) -> tuple[np.ndarray, float]:
    explicit_shift = _safe_float(params.get("threshold_shift"))
    trim_fraction = float(params.get("trim_fraction", 0.1))
    trim_fraction = min(max(trim_fraction, 0.0), 0.49)

    if explicit_shift is not None:
        return np.asarray([explicit_shift], dtype=float), trim_fraction

    grid_size = max(5, int(params.get("grid_size", 40)))
    if base_score.size == 0:
        return np.asarray([0.0], dtype=float), trim_fraction

    quantiles = np.linspace(trim_fraction, 1.0 - trim_fraction, num=grid_size)
    if np.allclose(quantiles, quantiles[0]):
        quantiles = np.asarray([0.5], dtype=float)
    candidates = np.quantile(base_score, quantiles)
    candidates = np.unique(np.asarray(candidates, dtype=float))
    if candidates.size == 0:
        candidates = np.asarray([float(np.median(base_score))], dtype=float)
    return candidates, trim_fraction


def _control_function_terms(
    data: ThresholdRegressionData,
    params: Mapping[str, Any],
) -> tuple[np.ndarray | None, dict[str, float | int | str | bool]]:
    use_cf = bool(params.get("use_control_function", False))
    diagnostics: dict[str, float | int | str | bool] = {
        "used_control_function": use_cf,
    }
    if not use_cf:
        return None, diagnostics
    if data.instruments is None:
        raise ValueError("control-function mode requires instruments")

    baseline_columns: list[np.ndarray] = [np.ones(data.n_obs)]
    if data.state_variables is not None:
        baseline_columns.append(data.state_variables)

    baseline_design = _stack_columns(baseline_columns)
    full_design = _stack_columns([baseline_design, data.instruments])
    q = np.asarray(data.running_variable, dtype=float)

    beta_base, _, _, _ = np.linalg.lstsq(baseline_design, q, rcond=None)
    beta_full, _, _, _ = np.linalg.lstsq(full_design, q, rcond=None)
    qhat_full = full_design @ beta_full
    residuals = q - qhat_full

    order = max(1, int(params.get("control_function_order", 2)))
    basis = np.column_stack([residuals**degree for degree in range(1, order + 1)])

    rss_base = float(np.sum((q - baseline_design @ beta_base) ** 2))
    rss_full = float(np.sum((q - qhat_full) ** 2))
    centered = q - float(np.mean(q))
    tss = float(centered @ centered)
    first_stage_r2 = 0.0 if tss <= _FLOAT_EPS else max(0.0, 1.0 - rss_full / tss)

    f_stat: float | None = None
    df_num = data.n_instruments
    df_den = data.n_obs - full_design.shape[1]
    if df_num > 0 and df_den > 0 and rss_full > _FLOAT_EPS and rss_base >= rss_full:
        f_stat = max(0.0, ((rss_base - rss_full) / df_num) / (rss_full / df_den))

    diagnostics.update(
        {
            "control_function_order": order,
            "first_stage_r_squared": first_stage_r2,
            "first_stage_f_statistic": f_stat,
        }
    )
    return basis, diagnostics


def _endogenous_feature_diagnostics(
    data: ThresholdRegressionData,
    *,
    n_endogenous: int,
) -> dict[str, float | int]:
    if n_endogenous <= 0 or data.instruments is None:
        return {}
    if n_endogenous > data.n_features:
        raise ValueError("n_endogenous cannot exceed the number of regressors")

    exogenous_controls = [np.ones(data.n_obs)]
    if data.n_features > n_endogenous:
        exogenous_controls.append(np.asarray(data.exog[:, n_endogenous:], dtype=float))
    if data.state_variables is not None:
        exogenous_controls.append(np.asarray(data.state_variables, dtype=float))

    base_design = _stack_columns(exogenous_controls)
    full_design = _stack_columns([base_design, np.asarray(data.instruments, dtype=float)])
    f_stats: list[float] = []
    r_squares: list[float] = []

    for idx in range(n_endogenous):
        target = np.asarray(data.exog[:, idx], dtype=float)
        beta_base, _, _, _ = np.linalg.lstsq(base_design, target, rcond=None)
        beta_full, _, _, _ = np.linalg.lstsq(full_design, target, rcond=None)

        rss_base = float(np.sum((target - base_design @ beta_base) ** 2))
        rss_full = float(np.sum((target - full_design @ beta_full) ** 2))
        centered = target - float(np.mean(target))
        tss = float(centered @ centered)
        r_sq = 0.0 if tss <= _FLOAT_EPS else max(0.0, 1.0 - rss_full / tss)
        r_squares.append(r_sq)

        df_num = data.n_instruments
        df_den = data.n_obs - full_design.shape[1]
        if df_num > 0 and df_den > 0 and rss_full > _FLOAT_EPS and rss_base >= rss_full:
            f_stats.append(max(0.0, ((rss_base - rss_full) / df_num) / (rss_full / df_den)))

    diagnostics: dict[str, float | int] = {
        "n_endogenous": int(n_endogenous),
        "endogenous_first_stage_mean_r_squared": float(np.mean(r_squares)) if r_squares else 0.0,
    }
    if f_stats:
        diagnostics["endogenous_first_stage_min_f_statistic"] = float(np.min(f_stats))
        diagnostics["endogenous_first_stage_mean_f_statistic"] = float(np.mean(f_stats))
    return diagnostics


def _build_global_design_matrix(
    data: ThresholdRegressionData,
    *,
    score: np.ndarray,
    feature_names: list[str],
    regime_model: ThresholdEffectModel,
    control_function_terms: np.ndarray | None,
    params: Mapping[str, Any],
) -> tuple[np.ndarray, list[str], np.ndarray]:
    columns: list[np.ndarray] = [np.ones(data.n_obs), np.asarray(data.exog, dtype=float)]
    names = ["const", *feature_names]
    regime = (score >= 0.0).astype(float)

    if regime_model is ThresholdEffectModel.THRESHOLD:
        columns.append(regime)
        names.append("regime_intercept")
        if bool(params.get("regime_interactions", True)):
            for idx, feature_name in enumerate(feature_names):
                columns.append(np.asarray(data.exog[:, idx], dtype=float) * regime)
                names.append(f"regime:{feature_name}")
    else:
        hinge = np.maximum(score, 0.0)
        columns.append(hinge)
        names.append("kink_plus")

    if control_function_terms is not None:
        for idx in range(control_function_terms.shape[1]):
            cf_column = np.asarray(control_function_terms[:, idx], dtype=float)
            columns.append(cf_column)
            names.append(f"cf_{idx + 1}")

        if bool(params.get("regime_specific_cf", True)):
            if regime_model is ThresholdEffectModel.THRESHOLD:
                multiplier = regime
                prefix = "regime"
            else:
                multiplier = np.maximum(score, 0.0)
                prefix = "kink"
            for idx in range(control_function_terms.shape[1]):
                cf_column = np.asarray(control_function_terms[:, idx], dtype=float) * multiplier
                columns.append(cf_column)
                names.append(f"{prefix}:cf_{idx + 1}")

    design = _stack_columns(columns)
    return design, names, regime


def _build_global_instruments(
    data: ThresholdRegressionData,
    *,
    score: np.ndarray,
    n_endogenous: int,
    regime_model: ThresholdEffectModel,
    control_function_terms: np.ndarray | None,
    params: Mapping[str, Any],
) -> np.ndarray | None:
    backend = _resolve_backend(params)
    if n_endogenous <= 0 and (data.instruments is None or backend not in {"2sls", "gmm"}):
        return None
    if data.instruments is None:
        raise ValueError("IV/GMM threshold estimation requires instruments when n_endogenous > 0")

    regime = (score >= 0.0).astype(float)
    exog = np.asarray(data.exog, dtype=float)
    columns: list[np.ndarray] = [np.ones(data.n_obs)]
    if data.n_features > n_endogenous:
        columns.append(exog[:, n_endogenous:])

    if regime_model is ThresholdEffectModel.THRESHOLD:
        columns.append(regime)
        if bool(params.get("regime_interactions", True)) and data.n_features > n_endogenous:
            columns.append(exog[:, n_endogenous:] * regime[:, None])
        columns.append(np.asarray(data.instruments, dtype=float))
        if bool(params.get("regime_interactions", True)):
            columns.append(np.asarray(data.instruments, dtype=float) * regime[:, None])
    else:
        columns.append(np.maximum(score, 0.0))
        columns.append(np.asarray(data.instruments, dtype=float))

    if control_function_terms is not None:
        columns.append(control_function_terms)
        if bool(params.get("regime_specific_cf", True)):
            if regime_model is ThresholdEffectModel.THRESHOLD:
                columns.append(control_function_terms * regime[:, None])
            else:
                columns.append(control_function_terms * np.maximum(score, 0.0)[:, None])

    return _stack_columns(columns)


def _linear_fit(
    y: np.ndarray,
    X: np.ndarray,
    *,
    backend: str,
    Z: np.ndarray | None,
    confidence_level: float,
    cov_type: str,
    gmm_weight_type: str,
) -> dict[str, Any]:
    if backend == "ols" or Z is None:
        return _ols_fit(y, X, confidence_level=confidence_level, cov_type=cov_type)
    if backend == "2sls":
        return _two_stage_least_squares_fit(
            y,
            X,
            Z,
            confidence_level=confidence_level,
            cov_type=cov_type,
        )
    return _gmm_fit(
        y,
        X,
        Z,
        confidence_level=confidence_level,
        weight_type=gmm_weight_type,
    )


def _resolve_target_parameter_name(
    names: list[str],
    *,
    preferred: str | None,
    fallback: str,
) -> str:
    if preferred and preferred in names:
        return preferred
    if fallback in names:
        return fallback
    for name in names:
        if name.lower() != "const":
            return name
    return names[0]


def _build_score_summary(
    score: np.ndarray,
    regime_indicator: np.ndarray,
    *,
    near_window: float,
) -> ThresholdScoreSummary:
    return ThresholdScoreSummary(
        min_score=float(np.min(score)),
        max_score=float(np.max(score)),
        mean_score=float(np.mean(score)),
        std_score=float(np.std(score)),
        positive_share=float(np.mean(regime_indicator >= 0.5)),
        support_within_window=int(np.sum(np.abs(score) <= near_window)),
        window_half_width=float(near_window),
    )


def _build_bounds_report(
    y: np.ndarray,
    *,
    confidence_level: float,
    reason: str,
    method: BoundMethod,
    metadata: dict[str, Any],
) -> BoundsReport:
    y_min = float(np.min(y))
    y_max = float(np.max(y))
    effect_radius = max(y_max - y_min, 1e-8)
    pid = PartialIdentificationResult(
        method=method,
        lower_bound=-effect_radius,
        upper_bound=effect_radius,
        confidence=confidence_level,
        assumptions_used=[
            "Observed outcome support bounds the unidentified treatment contrast.",
            reason,
        ],
        bounds_type="manski",
        display_label="Weak-identification fallback bounds",
        chart_type="interval",
        solver_metadata=metadata,
    )
    return BoundsReport(
        estimand_type="threshold_effect",
        results=[pid],
        assumptions_used=list(pid.assumptions_used),
        warnings=[reason],
        metadata=metadata,
    )


def _bandwidth_candidates(
    score: np.ndarray,
    *,
    derivative_order: int,
    params: Mapping[str, Any],
) -> tuple[float, np.ndarray]:
    explicit_bandwidth = _safe_float(params.get("bandwidth"))
    positive_score = np.asarray(score, dtype=float)
    scale = float(np.std(positive_score))
    if scale <= _FLOAT_EPS:
        iqr = np.quantile(positive_score, 0.75) - np.quantile(positive_score, 0.25)
        scale = max(float(iqr) / 1.349 if iqr > 0 else 1.0, 1e-3)

    rate_power = 1.0 / 5.0 if derivative_order == 0 else 1.0 / 7.0
    default_bandwidth = max(scale * (positive_score.shape[0] ** (-rate_power)), 1e-3)
    selected = explicit_bandwidth if explicit_bandwidth is not None else default_bandwidth

    raw_grid = params.get("bandwidth_grid")
    if raw_grid is not None:
        candidates = np.unique(np.asarray(raw_grid, dtype=float).reshape(-1))
        candidates = candidates[candidates > 0]
    else:
        multipliers = np.asarray(
            params.get("bandwidth_multipliers", [0.75, 1.0, 1.25, 1.5]), dtype=float
        )
        candidates = np.unique(np.clip(selected * multipliers, 1e-4, None))

    if selected not in candidates:
        candidates = np.unique(np.append(candidates, selected))
    return float(selected), np.asarray(np.sort(candidates), dtype=float)


def _local_side_fit(
    y: np.ndarray,
    score: np.ndarray,
    exog: np.ndarray,
    *,
    bandwidth: float,
    order: int,
    side: str,
    kernel: str,
    cov_type: str,
    confidence_level: float,
    use_covariates: bool,
) -> dict[str, Any]:
    if side == "left":
        mask = (score < 0.0) & (np.abs(score) <= bandwidth)
    else:
        mask = (score >= 0.0) & (np.abs(score) <= bandwidth)
    if int(np.sum(mask)) < max(order + 2, 6):
        raise ValueError("insufficient support for local polynomial fit")

    local_score = np.asarray(score[mask], dtype=float)
    columns = [local_score**degree for degree in range(order + 1)]
    if use_covariates:
        columns.append(np.asarray(exog[mask], dtype=float))
    X = _stack_columns(columns)
    weights = _kernel_weights(local_score, bandwidth, kernel)
    fit = _weighted_least_squares_fit(
        np.asarray(y[mask], dtype=float),
        X,
        weights,
        confidence_level=confidence_level,
        cov_type=cov_type,
    )
    fit["n_support"] = int(np.sum(mask))
    fit["weights_sum"] = float(np.sum(weights))
    return fit


def _local_ratio_estimate(
    numerator_left: dict[str, Any],
    numerator_right: dict[str, Any],
    denominator_left: dict[str, Any],
    denominator_right: dict[str, Any],
    *,
    coefficient_index: int,
    confidence_level: float,
) -> dict[str, float]:
    rf = float(
        numerator_right["beta"][coefficient_index] - numerator_left["beta"][coefficient_index]
    )
    fs = float(
        denominator_right["beta"][coefficient_index] - denominator_left["beta"][coefficient_index]
    )

    rf_var = float(
        numerator_right["std"][coefficient_index] ** 2
        + numerator_left["std"][coefficient_index] ** 2
    )
    fs_var = float(
        denominator_right["std"][coefficient_index] ** 2
        + denominator_left["std"][coefficient_index] ** 2
    )
    fs_safe = np.sign(fs) * max(abs(fs), _FLOAT_EPS) if abs(fs) > _FLOAT_EPS else _FLOAT_EPS
    effect = float(rf / fs_safe)
    effect_var = (rf_var / max(fs_safe**2, _FLOAT_EPS)) + (
        (rf**2) * fs_var / max(fs_safe**4, _FLOAT_EPS)
    )
    effect_se = float(np.sqrt(max(effect_var, 0.0)))

    normal = NormalDist()
    z = normal.inv_cdf(1.0 - max(1.0 - confidence_level, _FLOAT_EPS) / 2.0)
    t_effect = effect / max(effect_se, _FLOAT_EPS)

    fs_se = float(np.sqrt(max(fs_var, 0.0)))
    fs_t = float(fs / max(fs_se, _FLOAT_EPS))

    return {
        "local_effect": effect,
        "local_effect_se": effect_se,
        "local_effect_ci_lo": float(effect - z * effect_se),
        "local_effect_ci_hi": float(effect + z * effect_se),
        "local_effect_p_value": float(2.0 * (1.0 - normal.cdf(abs(t_effect)))),
        "reduced_form_effect": rf,
        "reduced_form_se": float(np.sqrt(max(rf_var, 0.0))),
        "first_stage_effect": fs,
        "first_stage_se": fs_se,
        "first_stage_statistic": float(fs_t**2),
    }


def _specification_curve_bundle(
    specification_records: list[dict[str, Any]],
    *,
    contract_payload: dict[str, Any],
    family: ObservationFamily,
) -> SpecificationCurveBundle:
    if not specification_records:
        raise ValueError("specification_records must be non-empty")

    sources = [
        SpecificationCurveSource(
            source_combination_id=str(record["specification_id"]),
            included_families=[family],
            sensitivity_axes=list(record.get("sensitivity_axes", [])),
            notes=list(record.get("notes", [])),
        )
        for record in specification_records
    ]
    return SpecificationCurveBundle(
        source_specifications=sources,
        specification_ids=[str(record["specification_id"]) for record in specification_records],
        estimates=[float(record["estimate"]) for record in specification_records],
        standard_errors=[float(record["standard_error"]) for record in specification_records],
        contract_payload=contract_payload,
    )


def _resample_threshold_data(
    data: ThresholdRegressionData,
    indices: np.ndarray,
) -> ThresholdRegressionData:
    def maybe_take(value: Any) -> Any:
        if value is None:
            return None
        return np.asarray(value)[indices]

    return ThresholdRegressionData(
        dependent=maybe_take(data.dependent),
        exog=maybe_take(data.exog),
        running_variable=maybe_take(data.running_variable),
        state_variables=maybe_take(data.state_variables),
        instruments=maybe_take(data.instruments),
        treatment=maybe_take(data.treatment),
        policy_variable=maybe_take(data.policy_variable),
        cluster_ids=maybe_take(data.cluster_ids),
        feature_names=list(data.feature_names) if data.feature_names is not None else None,
        state_names=list(data.state_names) if data.state_names is not None else None,
        instrument_names=list(data.instrument_names) if data.instrument_names is not None else None,
        metadata=dict(data.metadata),
    )


def _bootstrap_indices(
    data: ThresholdRegressionData,
    rng: np.random.Generator,
    *,
    use_cluster_bootstrap: bool,
) -> np.ndarray:
    if use_cluster_bootstrap and data.cluster_ids is not None:
        cluster_ids = np.asarray(data.cluster_ids)
        unique_clusters = np.unique(cluster_ids)
        sampled_clusters = rng.choice(unique_clusters, size=unique_clusters.shape[0], replace=True)
        return np.concatenate(
            [np.flatnonzero(cluster_ids == cluster_id) for cluster_id in sampled_clusters]
        )
    return rng.integers(0, data.n_obs, size=data.n_obs)


def _apply_bootstrap_to_result(
    result: EconometricResult,
    *,
    bootstrap_params: dict[str, list[float]],
    bootstrap_thresholds: list[float],
    confidence_level: float,
    label: str,
) -> EconometricResult:
    alpha = max(1.0 - confidence_level, _FLOAT_EPS)
    std_errors = dict(result.std_errors)
    t_stats = dict(result.t_stats)
    confidence_intervals = dict(result.confidence_intervals)
    p_values = dict(result.p_values)
    summaries: dict[str, Any] = {}

    for name, values in bootstrap_params.items():
        arr = np.asarray(values, dtype=float)
        if arr.size < 2:
            continue
        std = float(np.std(arr, ddof=1))
        lo, hi = np.quantile(arr, [alpha / 2.0, 1.0 - alpha / 2.0])
        std_errors[name] = std
        confidence_intervals[name] = (float(lo), float(hi))
        t_value = result.params.get(name, 0.0) / max(std, _FLOAT_EPS)
        t_stats[name] = float(t_value)
        p_values[name] = float(2.0 * (1.0 - NormalDist().cdf(abs(t_value))))
        summaries[name] = {
            "bootstrap_mean": float(np.mean(arr)),
            "bootstrap_std": std,
            "bootstrap_interval": (float(lo), float(hi)),
            "bootstrap_replications": int(arr.size),
        }

    diagnostics = dict(result.diagnostics)
    diagnostics["bootstrap"] = {
        "label": label,
        "replications": int(max((len(values) for values in bootstrap_params.values()), default=0)),
        "parameters": summaries,
    }

    threshold_state = result.threshold_state_field
    if threshold_state is not None:
        metadata = dict(threshold_state.metadata)
        metadata["bootstrap"] = {
            "label": label,
            "successful_replications": int(
                max((len(values) for values in bootstrap_params.values()), default=0)
            ),
        }
        if bootstrap_thresholds:
            lo, hi = np.quantile(
                np.asarray(bootstrap_thresholds, dtype=float), [alpha / 2.0, 1.0 - alpha / 2.0]
            )
            metadata["bootstrap"]["threshold_shift_interval"] = (float(lo), float(hi))
        threshold_state = threshold_state.model_copy(update={"metadata": metadata})

    return result.model_copy(
        update={
            "std_errors": std_errors,
            "t_stats": t_stats,
            "confidence_intervals": confidence_intervals,
            "p_values": p_values,
            "diagnostics": diagnostics,
            "threshold_state_field": threshold_state,
        }
    )


def _global_core_fit(
    data: ThresholdRegressionData,
    *,
    regime_model: ThresholdEffectModel,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    feature_names = _resolve_feature_names(data)
    state_names = _resolve_state_names(data)
    state_weights, surface_mode = _resolve_state_surface(data, params)
    state_component = (
        np.asarray(data.state_variables, dtype=float) @ state_weights
        if data.state_variables is not None and state_weights.size > 0
        else np.zeros(data.n_obs, dtype=float)
    )
    base_score = np.asarray(data.running_variable, dtype=float) - state_component
    candidate_shifts, trim_fraction = _candidate_thresholds(base_score, params)
    min_regime_count = max(3, int(np.floor(trim_fraction * data.n_obs)))

    cf_terms, cf_diagnostics = _control_function_terms(data, params)
    backend = _resolve_backend(params)
    n_endogenous = max(0, int(params.get("n_endogenous", 0)))
    iv_diagnostics = _endogenous_feature_diagnostics(data, n_endogenous=n_endogenous)

    confidence_level = float(params.get("confidence_level", 0.95))
    covariance = str(params.get("covariance", "robust")).lower()
    if covariance not in {"robust", "classic"}:
        covariance = "robust"
    gmm_weight_type = str(params.get("gmm_weight_type", "robust")).strip().lower()

    best: dict[str, Any] | None = None
    best_shift = 0.0
    best_score = None
    best_regime = None
    specification_records: list[dict[str, Any]] = []

    default_effect_param = (
        "kink_plus" if regime_model is ThresholdEffectModel.KINK else "regime_intercept"
    )
    requested_effect_param = str(params.get("specification_param", default_effect_param))

    for candidate_index, threshold_shift in enumerate(candidate_shifts):
        score = base_score - float(threshold_shift)
        regime = score >= 0.0
        n_right = int(np.sum(regime))
        n_left = int(data.n_obs - n_right)
        if n_left < min_regime_count or n_right < min_regime_count:
            continue

        design, names, regime_indicator = _build_global_design_matrix(
            data,
            score=score,
            feature_names=feature_names,
            regime_model=regime_model,
            control_function_terms=cf_terms,
            params=params,
        )
        instruments = _build_global_instruments(
            data,
            score=score,
            n_endogenous=n_endogenous,
            regime_model=regime_model,
            control_function_terms=cf_terms,
            params=params,
        )
        fit = _linear_fit(
            np.asarray(data.dependent, dtype=float),
            design,
            backend=backend,
            Z=instruments,
            confidence_level=confidence_level,
            cov_type=covariance,
            gmm_weight_type=gmm_weight_type,
        )
        fit["names"] = names
        fit["score"] = score
        fit["regime_indicator"] = regime_indicator
        fit["threshold_shift"] = float(threshold_shift)
        fit["n_left"] = n_left
        fit["n_right"] = n_right

        target_name = _resolve_target_parameter_name(
            names,
            preferred=requested_effect_param,
            fallback=default_effect_param,
        )
        target_index = names.index(target_name)
        specification_records.append(
            {
                "specification_id": f"threshold_candidate_{candidate_index}",
                "estimate": float(fit["beta"][target_index]),
                "standard_error": float(fit["std"][target_index]),
                "sensitivity_axes": ["threshold_shift", "trim_fraction"],
                "notes": [
                    f"threshold_shift={float(threshold_shift):.6f}",
                    f"n_left={n_left}",
                    f"n_right={n_right}",
                ],
                "threshold_shift": float(threshold_shift),
                "target_param": target_name,
            }
        )

        if best is None or float(fit["objective"]) < float(best["objective"]):
            best = fit
            best_shift = float(threshold_shift)
            best_score = score
            best_regime = regime_indicator

    if best is None or best_score is None or best_regime is None:
        raise ValueError("no admissible threshold candidate survived trimming")

    near_window = _safe_float(params.get("near_threshold_window"))
    if near_window is None:
        near_window = max(float(np.std(best_score)) * 0.1, 1e-6)

    score_summary = _build_score_summary(best_score, best_regime, near_window=near_window)
    if bool(cf_diagnostics.get("used_control_function", False)):
        identification_mode = ThresholdIdentificationMode.GLOBAL_CONTROL_FUNCTION
    elif backend in {"2sls", "gmm"} and n_endogenous > 0:
        identification_mode = ThresholdIdentificationMode.GLOBAL_IV_GMM
    else:
        identification_mode = ThresholdIdentificationMode.GLOBAL_PROFILE

    first_stage_r2 = _safe_float(cf_diagnostics.get("first_stage_r_squared"))
    first_stage_f = _safe_float(cf_diagnostics.get("first_stage_f_statistic"))
    if first_stage_r2 is None:
        first_stage_r2 = _safe_float(iv_diagnostics.get("endogenous_first_stage_mean_r_squared"))
    if first_stage_f is None:
        first_stage_f = _safe_float(iv_diagnostics.get("endogenous_first_stage_min_f_statistic"))

    threshold_state_field = ThresholdStateField(
        regime_model=regime_model,
        identification_mode=identification_mode,
        threshold_surface_mode=surface_mode,
        continuity_imposed=regime_model is ThresholdEffectModel.KINK,
        threshold_shift=best_shift,
        state_weights=tuple(float(value) for value in state_weights),
        state_variable_names=tuple(state_names),
        trim_fraction=trim_fraction,
        candidate_count=int(candidate_shifts.size),
        objective_value=max(float(best["objective"]), 0.0),
        regime_counts={
            "below_threshold": int(np.sum(best_regime < 0.5)),
            "at_or_above_threshold": int(np.sum(best_regime >= 0.5)),
        },
        normalized_score=score_summary,
        threshold_variable_endogeneity_adjusted=bool(
            cf_diagnostics.get("used_control_function", False)
        ),
        control_function_order=(
            int(cf_diagnostics["control_function_order"])
            if cf_diagnostics.get("control_function_order") is not None
            else None
        ),
        first_stage_r_squared=first_stage_r2,
        first_stage_f_statistic=first_stage_f,
        metadata={
            "surface_mode": surface_mode.value,
            "covariance": covariance,
            "estimation_backend": backend,
            "gmm_weight_type": gmm_weight_type,
            "n_endogenous": n_endogenous,
        },
    )

    names = list(best["names"])
    beta = np.asarray(best["beta"], dtype=float)
    std = np.asarray(best["std"], dtype=float)
    t_stats = np.asarray(best["t_stats"], dtype=float)
    p_values = np.asarray(best["p_values"], dtype=float)
    intervals = np.asarray(best["intervals"], dtype=float)

    diagnostics: dict[str, Any] = {
        "objective": "profile_gmm" if backend == "gmm" else "profile_least_squares",
        "covariance": covariance,
        "estimation_backend": backend,
        "candidate_count": int(candidate_shifts.size),
        "selected_threshold_shift": best_shift,
        "trim_fraction": trim_fraction,
        "support_within_window": score_summary.support_within_window,
        **cf_diagnostics,
        **iv_diagnostics,
    }
    if best.get("j_statistic") is not None:
        diagnostics["j_statistic"] = float(best["j_statistic"])
    diagnostics["regime_counts"] = dict(threshold_state_field.regime_counts)

    result = EconometricResult(
        method_name=(
            "state_dependent_kink"
            if regime_model is ThresholdEffectModel.KINK
            else "state_dependent_threshold"
        ),
        params={name: float(beta[idx]) for idx, name in enumerate(names)},
        std_errors={name: float(std[idx]) for idx, name in enumerate(names)},
        t_stats={name: float(t_stats[idx]) for idx, name in enumerate(names)},
        p_values={name: float(p_values[idx]) for idx, name in enumerate(names)},
        confidence_intervals={
            name: (float(intervals[idx, 0]), float(intervals[idx, 1]))
            for idx, name in enumerate(names)
        },
        confidence_level=confidence_level,
        r_squared=_safe_float(best["r_squared"]),
        adj_r_squared=_safe_float(best["adj_r_squared"]),
        n_obs=data.n_obs,
        diagnostics=diagnostics,
        model_info={
            "library": "numpy",
            "estimator": "profile_threshold_regression",
            "regime_model": regime_model.value,
        },
        metadata={
            "feature_names": feature_names,
            "state_names": state_names,
            "instrument_names": list(data.instrument_names or []),
        },
        threshold_state_field=threshold_state_field,
    )

    family = _resolve_observation_family(data)
    spec_bundle = _specification_curve_bundle(
        specification_records,
        contract_payload={
            "method_name": result.method_name,
            "selected_threshold_shift": best_shift,
            "target_parameter": _resolve_target_parameter_name(
                names,
                preferred=requested_effect_param,
                fallback=default_effect_param,
            ),
            "estimation_backend": backend,
        },
        family=family,
    )
    return {
        "result": result,
        "specification_curve_bundle": spec_bundle,
        "base_score": base_score,
    }


def _global_outputs(
    data: ThresholdRegressionData,
    *,
    regime_model: ThresholdEffectModel,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _global_core_fit(data, regime_model=regime_model, params=params)
    result: EconometricResult = payload["result"]
    spec_bundle: SpecificationCurveBundle = payload["specification_curve_bundle"]

    n_bootstrap = max(0, int(params.get("n_bootstrap", 0)))
    if n_bootstrap > 0:
        bootstrap_seed = int(params.get("bootstrap_seed", _DEFAULT_BOOTSTRAP_SEED))
        bootstrap_cluster = bool(params.get("bootstrap_by_cluster", data.cluster_ids is not None))
        rng = np.random.default_rng(bootstrap_seed)
        bootstrap_params = {name: [] for name in result.params}
        bootstrap_thresholds: list[float] = []

        bootstrap_params_config = dict(params)
        bootstrap_params_config["n_bootstrap"] = 0

        for _ in range(n_bootstrap):
            sample_idx = _bootstrap_indices(data, rng, use_cluster_bootstrap=bootstrap_cluster)
            boot_data = _resample_threshold_data(data, sample_idx)
            try:
                boot_payload = _global_core_fit(
                    boot_data, regime_model=regime_model, params=bootstrap_params_config
                )
            except Exception:
                continue
            boot_result: EconometricResult = boot_payload["result"]
            for name in bootstrap_params:
                value = boot_result.params.get(name)
                if value is not None and np.isfinite(value):
                    bootstrap_params[name].append(float(value))
            if boot_result.threshold_state_field is not None:
                bootstrap_thresholds.append(
                    float(boot_result.threshold_state_field.threshold_shift)
                )

        result = _apply_bootstrap_to_result(
            result,
            bootstrap_params=bootstrap_params,
            bootstrap_thresholds=bootstrap_thresholds,
            confidence_level=float(params.get("confidence_level", 0.95)),
            label="global_threshold_bootstrap",
        )

    weak_id_threshold = float(params.get("weak_first_stage_threshold", 5.0))
    min_support = int(params.get("min_support_within_window", max(12, int(0.05 * data.n_obs))))
    first_stage_f = None
    if result.threshold_state_field is not None:
        first_stage_f = result.threshold_state_field.first_stage_f_statistic
    weak_reasons: list[str] = []
    if result.threshold_state_field is not None:
        if result.threshold_state_field.normalized_score.support_within_window < min_support:
            weak_reasons.append(
                "Support near the normalized threshold is too thin for stable point identification."
            )
    if first_stage_f is not None and first_stage_f < weak_id_threshold:
        weak_reasons.append(
            f"First-stage strength fell below the configured threshold ({first_stage_f:.3f} < {weak_id_threshold:.3f})."
        )

    bounds_report = None
    if bool(params.get("bounds_on_weak_id", True)) and weak_reasons:
        bounds_report = _build_bounds_report(
            np.asarray(data.dependent, dtype=float),
            confidence_level=float(params.get("confidence_level", 0.95)),
            reason=" ".join(weak_reasons),
            method=BoundMethod.IV_BOUNDS if first_stage_f is not None else BoundMethod.MANSKI,
            metadata={
                "method_name": result.method_name,
                "weak_reasons": weak_reasons,
            },
        )
        diagnostics = dict(result.diagnostics)
        diagnostics["identify_or_bound"] = {
            "triggered": True,
            "reasons": weak_reasons,
        }
        threshold_state = result.threshold_state_field
        if threshold_state is not None:
            metadata = dict(threshold_state.metadata)
            metadata["identify_or_bound"] = {"triggered": True, "reasons": weak_reasons}
            threshold_state = threshold_state.model_copy(update={"metadata": metadata})
        result = result.model_copy(
            update={"diagnostics": diagnostics, "threshold_state_field": threshold_state}
        )

    return {
        "result": result,
        "uncertainty_envelope": result.to_uncertainty_envelope(
            param_name=params.get("envelope_param")
        ),
        "specification_curve_bundle": spec_bundle,
        "bounds_report": bounds_report,
    }


def _local_core_fit(
    data: ThresholdRegressionData,
    *,
    regime_model: ThresholdEffectModel,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    confidence_level = float(params.get("confidence_level", 0.95))
    covariance = str(params.get("covariance", "robust")).lower()
    if covariance not in {"robust", "classic"}:
        covariance = "robust"
    kernel = str(params.get("kernel", "triangular"))
    use_covariates = bool(params.get("covariate_adjustment", True))

    state_weights, surface_mode = _resolve_state_surface(data, params)
    state_names = _resolve_state_names(data)
    state_component = (
        np.asarray(data.state_variables, dtype=float) @ state_weights
        if data.state_variables is not None and state_weights.size > 0
        else np.zeros(data.n_obs, dtype=float)
    )
    threshold_shift = float(_safe_float(params.get("threshold_shift")) or 0.0)
    score = np.asarray(data.running_variable, dtype=float) - state_component - threshold_shift

    if regime_model is ThresholdEffectModel.THRESHOLD:
        denominator = data.treatment
        if denominator is None:
            raise ValueError("state_dependent_frd requires treatment in ThresholdRegressionData")
        derivative_order = 0
        order = max(1, int(params.get("poly_order", 1)))
        coefficient_index = 0
        method_name = "state_dependent_frd"
        identification_mode = ThresholdIdentificationMode.LOCAL_FUZZY_RD
        denominator_label = "first_stage_jump"
        target_param = "local_effect"
    else:
        denominator = data.policy_variable if data.policy_variable is not None else data.treatment
        if denominator is None:
            raise ValueError(
                "state_dependent_frkd requires policy_variable or treatment in ThresholdRegressionData"
            )
        derivative_order = 1
        order = max(2, int(params.get("poly_order", 2)))
        coefficient_index = 1
        method_name = "state_dependent_frkd"
        identification_mode = ThresholdIdentificationMode.LOCAL_FUZZY_RKD
        denominator_label = "first_stage_slope_jump"
        target_param = "local_effect"

    selected_bandwidth, bandwidth_candidates = _bandwidth_candidates(
        score,
        derivative_order=derivative_order,
        params=params,
    )

    exog = np.asarray(data.exog, dtype=float)
    y = np.asarray(data.dependent, dtype=float)
    d = np.asarray(denominator, dtype=float)
    specification_records: list[dict[str, Any]] = []
    selected_fit: dict[str, Any] | None = None
    selected_distance = float("inf")

    for idx, bandwidth in enumerate(bandwidth_candidates):
        try:
            y_left = _local_side_fit(
                y,
                score,
                exog,
                bandwidth=float(bandwidth),
                order=order,
                side="left",
                kernel=kernel,
                cov_type=covariance,
                confidence_level=confidence_level,
                use_covariates=use_covariates,
            )
            y_right = _local_side_fit(
                y,
                score,
                exog,
                bandwidth=float(bandwidth),
                order=order,
                side="right",
                kernel=kernel,
                cov_type=covariance,
                confidence_level=confidence_level,
                use_covariates=use_covariates,
            )
            d_left = _local_side_fit(
                d,
                score,
                exog,
                bandwidth=float(bandwidth),
                order=order,
                side="left",
                kernel=kernel,
                cov_type=covariance,
                confidence_level=confidence_level,
                use_covariates=use_covariates,
            )
            d_right = _local_side_fit(
                d,
                score,
                exog,
                bandwidth=float(bandwidth),
                order=order,
                side="right",
                kernel=kernel,
                cov_type=covariance,
                confidence_level=confidence_level,
                use_covariates=use_covariates,
            )
        except ValueError:
            continue
        ratio = _local_ratio_estimate(
            y_left,
            y_right,
            d_left,
            d_right,
            coefficient_index=coefficient_index,
            confidence_level=confidence_level,
        )
        specification_records.append(
            {
                "specification_id": f"bandwidth_{idx}",
                "estimate": ratio["local_effect"],
                "standard_error": ratio["local_effect_se"],
                "sensitivity_axes": ["bandwidth", "poly_order"],
                "notes": [f"bandwidth={float(bandwidth):.6f}", f"poly_order={order}"],
                "bandwidth": float(bandwidth),
            }
        )
        distance = abs(float(bandwidth) - selected_bandwidth)
        if distance < selected_distance:
            selected_distance = distance
            selected_fit = {
                "y_left": y_left,
                "y_right": y_right,
                "d_left": d_left,
                "d_right": d_right,
                "ratio": ratio,
                "bandwidth": float(bandwidth),
            }

    if selected_fit is None:
        raise ValueError("selected bandwidth did not yield an admissible local fit")

    ratio = selected_fit["ratio"]
    bandwidth = float(selected_fit["bandwidth"])
    threshold_state_field = ThresholdStateField(
        regime_model=regime_model,
        identification_mode=identification_mode,
        threshold_surface_mode=surface_mode,
        continuity_imposed=regime_model is ThresholdEffectModel.KINK,
        threshold_shift=threshold_shift,
        state_weights=tuple(float(value) for value in state_weights),
        state_variable_names=tuple(state_names),
        trim_fraction=0.0,
        candidate_count=int(bandwidth_candidates.size),
        objective_value=max(
            float(selected_fit["y_left"]["objective"])
            + float(selected_fit["y_right"]["objective"])
            + float(selected_fit["d_left"]["objective"])
            + float(selected_fit["d_right"]["objective"]),
            0.0,
        ),
        regime_counts={
            "below_threshold": int(selected_fit["y_left"]["n_support"]),
            "at_or_above_threshold": int(selected_fit["y_right"]["n_support"]),
        },
        normalized_score=_build_score_summary(
            score, (score >= 0.0).astype(float), near_window=bandwidth
        ),
        threshold_variable_endogeneity_adjusted=False,
        control_function_order=None,
        first_stage_r_squared=None,
        first_stage_f_statistic=float(ratio["first_stage_statistic"]),
        metadata={
            "bandwidth": bandwidth,
            "kernel": kernel,
            "poly_order": order,
            "denominator_label": denominator_label,
            "reduced_form_effect": ratio["reduced_form_effect"],
            "first_stage_effect": ratio["first_stage_effect"],
            "use_covariates": use_covariates,
        },
    )

    diagnostics = {
        "objective": "local_polynomial_wald",
        "bandwidth": bandwidth,
        "kernel": kernel,
        "poly_order": order,
        "reduced_form_effect": ratio["reduced_form_effect"],
        "reduced_form_se": ratio["reduced_form_se"],
        denominator_label: ratio["first_stage_effect"],
        "first_stage_se": ratio["first_stage_se"],
        "first_stage_statistic": ratio["first_stage_statistic"],
        "support_within_bandwidth": threshold_state_field.regime_counts,
    }

    result = EconometricResult(
        method_name=method_name,
        params={
            target_param: float(ratio["local_effect"]),
            "reduced_form_effect": float(ratio["reduced_form_effect"]),
            "first_stage_effect": float(ratio["first_stage_effect"]),
        },
        std_errors={
            target_param: float(ratio["local_effect_se"]),
            "reduced_form_effect": float(ratio["reduced_form_se"]),
            "first_stage_effect": float(ratio["first_stage_se"]),
        },
        p_values={target_param: float(ratio["local_effect_p_value"])},
        confidence_intervals={
            target_param: (float(ratio["local_effect_ci_lo"]), float(ratio["local_effect_ci_hi"]))
        },
        confidence_level=confidence_level,
        n_obs=data.n_obs,
        diagnostics=diagnostics,
        model_info={
            "library": "numpy",
            "estimator": "local_polynomial_wald",
            "regime_model": regime_model.value,
        },
        metadata={
            "feature_names": _resolve_feature_names(data),
            "state_names": state_names,
            "bandwidth_candidates": [float(value) for value in bandwidth_candidates.tolist()],
        },
        threshold_state_field=threshold_state_field,
    )

    family = _resolve_observation_family(data)
    spec_bundle = _specification_curve_bundle(
        specification_records,
        contract_payload={
            "method_name": method_name,
            "selected_bandwidth": bandwidth,
            "target_parameter": target_param,
        },
        family=family,
    )
    return {"result": result, "specification_curve_bundle": spec_bundle}


def _local_outputs(
    data: ThresholdRegressionData,
    *,
    regime_model: ThresholdEffectModel,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _local_core_fit(data, regime_model=regime_model, params=params)
    result: EconometricResult = payload["result"]
    spec_bundle: SpecificationCurveBundle = payload["specification_curve_bundle"]

    n_bootstrap = max(0, int(params.get("n_bootstrap", 0)))
    if n_bootstrap > 0:
        bootstrap_seed = int(params.get("bootstrap_seed", _DEFAULT_BOOTSTRAP_SEED))
        bootstrap_cluster = bool(params.get("bootstrap_by_cluster", data.cluster_ids is not None))
        rng = np.random.default_rng(bootstrap_seed)
        bootstrap_params = {name: [] for name in result.params}
        bootstrap_thresholds: list[float] = []
        bootstrap_params_config = dict(params)
        bootstrap_params_config["n_bootstrap"] = 0

        for _ in range(n_bootstrap):
            sample_idx = _bootstrap_indices(data, rng, use_cluster_bootstrap=bootstrap_cluster)
            boot_data = _resample_threshold_data(data, sample_idx)
            try:
                boot_payload = _local_core_fit(
                    boot_data, regime_model=regime_model, params=bootstrap_params_config
                )
            except Exception:
                continue
            boot_result: EconometricResult = boot_payload["result"]
            for name in bootstrap_params:
                value = boot_result.params.get(name)
                if value is not None and np.isfinite(value):
                    bootstrap_params[name].append(float(value))
            if boot_result.threshold_state_field is not None:
                bootstrap_thresholds.append(
                    float(boot_result.threshold_state_field.threshold_shift)
                )

        result = _apply_bootstrap_to_result(
            result,
            bootstrap_params=bootstrap_params,
            bootstrap_thresholds=bootstrap_thresholds,
            confidence_level=float(params.get("confidence_level", 0.95)),
            label="local_threshold_bootstrap",
        )

    first_stage_threshold = float(params.get("weak_first_stage_threshold", 4.0))
    min_support = int(params.get("min_support_within_window", 10))
    weak_reasons: list[str] = []
    threshold_state = result.threshold_state_field
    if threshold_state is not None:
        counts = threshold_state.regime_counts
        if (
            counts.get("below_threshold", 0) < min_support
            or counts.get("at_or_above_threshold", 0) < min_support
        ):
            weak_reasons.append(
                "One side of the local window has too little support for reliable local identification."
            )
        if (
            threshold_state.first_stage_f_statistic is not None
            and threshold_state.first_stage_f_statistic < first_stage_threshold
        ):
            weak_reasons.append(
                f"Local first-stage strength is weak ({threshold_state.first_stage_f_statistic:.3f} < {first_stage_threshold:.3f})."
            )

    bounds_report = None
    if bool(params.get("bounds_on_weak_id", True)) and weak_reasons:
        bounds_report = _build_bounds_report(
            np.asarray(data.dependent, dtype=float),
            confidence_level=float(params.get("confidence_level", 0.95)),
            reason=" ".join(weak_reasons),
            method=BoundMethod.IV_BOUNDS,
            metadata={"method_name": result.method_name, "weak_reasons": weak_reasons},
        )
        diagnostics = dict(result.diagnostics)
        diagnostics["identify_or_bound"] = {"triggered": True, "reasons": weak_reasons}
        if threshold_state is not None:
            metadata = dict(threshold_state.metadata)
            metadata["identify_or_bound"] = {"triggered": True, "reasons": weak_reasons}
            threshold_state = threshold_state.model_copy(update={"metadata": metadata})
        result = result.model_copy(
            update={"diagnostics": diagnostics, "threshold_state_field": threshold_state}
        )

    return {
        "result": result,
        "uncertainty_envelope": result.to_uncertainty_envelope(
            param_name=params.get("envelope_param")
        ),
        "specification_curve_bundle": spec_bundle,
        "bounds_report": bounds_report,
    }


@foundry_method(
    namespace="econometrics.thresholds",
    version="1.0.0",
    tags={"econometrics", "threshold", "state-dependent", "profile-gmm", "tabular"},
)
class StateDependentThresholdEstimator:
    """Estimate a state-dependent threshold regression with profile OLS/2SLS/GMM search."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="state_dependent_threshold",
        namespace="",
        version="0.0.0",
        input_slots=_threshold_input_slots(),
        output_slots=_threshold_output_slots(),
        parameters=(
            ParameterSpec(name="threshold_shift", default=None),
            ParameterSpec(name="trim_fraction", default=0.1),
            ParameterSpec(name="grid_size", default=40),
            ParameterSpec(name="state_policy_weights", default=None),
            ParameterSpec(name="estimate_state_weights", default=False),
            ParameterSpec(name="use_control_function", default=False),
            ParameterSpec(name="control_function_order", default=2),
            ParameterSpec(name="estimation_backend", default="ols"),
            ParameterSpec(name="n_endogenous", default=0),
            ParameterSpec(name="gmm_weight_type", default="robust"),
            ParameterSpec(name="regime_interactions", default=True),
            ParameterSpec(name="regime_specific_cf", default=True),
            ParameterSpec(name="covariance", default="robust"),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="n_bootstrap", default=0),
            ParameterSpec(name="bootstrap_seed", default=_DEFAULT_BOOTSTRAP_SEED),
            ParameterSpec(name="bootstrap_by_cluster", default=False),
            ParameterSpec(name="weak_first_stage_threshold", default=5.0),
            ParameterSpec(name="bounds_on_weak_id", default=True),
            ParameterSpec(name="envelope_param", default="regime_intercept"),
            ParameterSpec(name="specification_param", default="regime_intercept"),
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
            "Profile threshold regression on a normalized score R = Q - gamma(S), "
            "with optional control-function correction, IV/GMM backends, "
            "bootstrap inference, specification curves, and weak-ID bounds fallback."
        ),
        tags=frozenset(
            {"econometrics", "threshold", "state-dependent", "control-function", "gmm", "tabular"}
        ),
        citations=(
            "Hansen, B. (2000). Sample Splitting and Threshold Estimation.",
            "Caner, M. & Hansen, B. (2004). Instrumental Variable Estimation of a Threshold Model.",
            "Kourtellos, A. et al. (2016). Structural Threshold Regression.",
        ),
        equations={
            "normalized_score": "R_i = Q_i - gamma(S_i)",
            "threshold_model": "Y_i = X_i beta + delta * 1{R_i >= 0} + u_i",
        },
        assumptions={
            "support": "Both sides of the threshold need positive support after trimming.",
            "policy_rule": "State-dependent threshold surface gamma(S) must be known or credibly approximated.",
            "instruments": "2SLS/GMM backends require valid excluded shifters for endogenous regressors.",
            "control_function": "If enabled, instruments must shift Q without directly entering the structural error.",
        },
        when_to_use="Global threshold search with an institutional or state-dependent policy rule.",
        when_not_to_use="Purely local RD/RKD estimands at a known cutoff; use state_dependent_frd or state_dependent_frkd.",
        typical_min_obs=150,
        output_interpretation="Regime-intercept and regime-slope terms summarize the global threshold contrast after score normalization.",
    )

    @staticmethod
    def pure_step(state: ThresholdRegressionData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, ThresholdRegressionData)
            else ThresholdRegressionData.model_validate(state)
        )
        return _global_outputs(data, regime_model=ThresholdEffectModel.THRESHOLD, params=params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> ThresholdRegressionData:
        return _materialize_threshold_data(bound_inputs, fallback_state)


@foundry_method(
    namespace="econometrics.thresholds",
    version="1.0.0",
    tags={"econometrics", "kink", "state-dependent", "profile-gmm", "tabular"},
)
class StateDependentKinkEstimator:
    """Estimate a continuous-threshold kink model with profile OLS/2SLS/GMM search."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="state_dependent_kink",
        namespace="",
        version="0.0.0",
        input_slots=_threshold_input_slots(),
        output_slots=_threshold_output_slots(),
        parameters=(
            ParameterSpec(name="threshold_shift", default=None),
            ParameterSpec(name="trim_fraction", default=0.1),
            ParameterSpec(name="grid_size", default=40),
            ParameterSpec(name="state_policy_weights", default=None),
            ParameterSpec(name="estimate_state_weights", default=False),
            ParameterSpec(name="use_control_function", default=False),
            ParameterSpec(name="control_function_order", default=2),
            ParameterSpec(name="estimation_backend", default="ols"),
            ParameterSpec(name="n_endogenous", default=0),
            ParameterSpec(name="gmm_weight_type", default="robust"),
            ParameterSpec(name="regime_specific_cf", default=True),
            ParameterSpec(name="covariance", default="robust"),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="n_bootstrap", default=0),
            ParameterSpec(name="bootstrap_seed", default=_DEFAULT_BOOTSTRAP_SEED),
            ParameterSpec(name="bootstrap_by_cluster", default=False),
            ParameterSpec(name="weak_first_stage_threshold", default=5.0),
            ParameterSpec(name="bounds_on_weak_id", default=True),
            ParameterSpec(name="envelope_param", default="kink_plus"),
            ParameterSpec(name="specification_param", default="kink_plus"),
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
            "Continuous-threshold kink model with state-dependent score normalization, "
            "optional control-function correction, IV/GMM backends, bootstrap inference, "
            "specification curves, and weak-ID bounds fallback."
        ),
        tags=frozenset(
            {"econometrics", "kink", "state-dependent", "control-function", "gmm", "tabular"}
        ),
        citations=(
            "Hansen, B. (2017). Regression Kink With an Unknown Threshold.",
            "Zhang, H. et al. (2017). Endogenous Kink Threshold Regression.",
        ),
        equations={
            "normalized_score": "R_i = Q_i - gamma(S_i)",
            "kink_model": "Y_i = X_i beta + kappa * max(R_i, 0) + u_i",
        },
        assumptions={
            "continuity": "Outcome level is continuous at the threshold; only the slope may change.",
            "support": "Both sides of the kink need positive support after trimming.",
            "control_function": "If enabled, instruments must support the running-variable first stage.",
        },
        when_to_use="Global continuous-threshold or endogenous-kink regressions after score normalization.",
        when_not_to_use="Local fuzzy RKD designs that need a margin-specific effect; use state_dependent_frkd.",
        typical_min_obs=150,
        output_interpretation="The kink_plus coefficient captures the global slope change above the normalized policy threshold.",
    )

    @staticmethod
    def pure_step(state: ThresholdRegressionData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, ThresholdRegressionData)
            else ThresholdRegressionData.model_validate(state)
        )
        return _global_outputs(data, regime_model=ThresholdEffectModel.KINK, params=params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> ThresholdRegressionData:
        return _materialize_threshold_data(bound_inputs, fallback_state)


@foundry_method(
    namespace="econometrics.thresholds",
    version="1.0.0",
    tags={"econometrics", "frd", "state-dependent", "local-design", "tabular"},
)
class StateDependentFRDEstimator:
    """Estimate a local fuzzy RD effect on the normalized score R = Q - gamma(S)."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="state_dependent_frd",
        namespace="",
        version="0.0.0",
        input_slots=_threshold_input_slots(),
        output_slots=_threshold_output_slots(),
        parameters=(
            ParameterSpec(name="threshold_shift", default=0.0),
            ParameterSpec(name="state_policy_weights", default=None),
            ParameterSpec(name="estimate_state_weights", default=False),
            ParameterSpec(name="bandwidth", default=None),
            ParameterSpec(name="bandwidth_grid", default=None),
            ParameterSpec(name="bandwidth_multipliers", default=[0.75, 1.0, 1.25, 1.5]),
            ParameterSpec(name="poly_order", default=1),
            ParameterSpec(name="kernel", default="triangular"),
            ParameterSpec(name="covariate_adjustment", default=True),
            ParameterSpec(name="covariance", default="robust"),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="n_bootstrap", default=0),
            ParameterSpec(name="bootstrap_seed", default=_DEFAULT_BOOTSTRAP_SEED),
            ParameterSpec(name="bootstrap_by_cluster", default=False),
            ParameterSpec(name="weak_first_stage_threshold", default=4.0),
            ParameterSpec(name="bounds_on_weak_id", default=True),
            ParameterSpec(name="envelope_param", default="local_effect"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Local fuzzy RD estimator on the normalized score R = Q - gamma(S).",
        tags=frozenset(
            {"econometrics", "fuzzy-rd", "state-dependent", "local-polynomial", "tabular"}
        ),
        citations=(
            "Hahn, J., Todd, P. & van der Klaauw, W. (2001). Identification and Estimation of Treatment Effects with a Regression-Discontinuity Design.",
            "Calonico, C. et al. (2014). Robust Nonparametric Confidence Intervals for Regression-Discontinuity Designs.",
        ),
        equations={
            "score": "R_i = Q_i - gamma(S_i)",
            "wald_ratio": "tau_FRD = Delta E[Y|R] / Delta E[D|R]",
        },
        assumptions={
            "institutional_rule": "The policy cutoff is known after score normalization.",
            "local_smoothness": "Potential outcomes evolve smoothly in the normalized score near zero.",
            "first_stage": "Treatment probability must jump at the local cutoff.",
        },
        when_to_use="Local causal evaluation at a policy eligibility cutoff after state normalization.",
        when_not_to_use="Global regime models or applications with no credible local support near the normalized cutoff.",
        typical_min_obs=120,
        output_interpretation="local_effect is the local Wald ratio for marginal compliers at the normalized threshold.",
    )

    @staticmethod
    def pure_step(state: ThresholdRegressionData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, ThresholdRegressionData)
            else ThresholdRegressionData.model_validate(state)
        )
        return _local_outputs(data, regime_model=ThresholdEffectModel.THRESHOLD, params=params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> ThresholdRegressionData:
        return _materialize_threshold_data(bound_inputs, fallback_state)


@foundry_method(
    namespace="econometrics.thresholds",
    version="1.0.0",
    tags={"econometrics", "frkd", "state-dependent", "local-design", "tabular"},
)
class StateDependentFRKDEstimator:
    """Estimate a local fuzzy RKD effect on the normalized score R = Q - gamma(S)."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="state_dependent_frkd",
        namespace="",
        version="0.0.0",
        input_slots=_threshold_input_slots(),
        output_slots=_threshold_output_slots(),
        parameters=(
            ParameterSpec(name="threshold_shift", default=0.0),
            ParameterSpec(name="state_policy_weights", default=None),
            ParameterSpec(name="estimate_state_weights", default=False),
            ParameterSpec(name="bandwidth", default=None),
            ParameterSpec(name="bandwidth_grid", default=None),
            ParameterSpec(name="bandwidth_multipliers", default=[0.75, 1.0, 1.25, 1.5]),
            ParameterSpec(name="poly_order", default=2),
            ParameterSpec(name="kernel", default="triangular"),
            ParameterSpec(name="covariate_adjustment", default=True),
            ParameterSpec(name="covariance", default="robust"),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="n_bootstrap", default=0),
            ParameterSpec(name="bootstrap_seed", default=_DEFAULT_BOOTSTRAP_SEED),
            ParameterSpec(name="bootstrap_by_cluster", default=False),
            ParameterSpec(name="weak_first_stage_threshold", default=4.0),
            ParameterSpec(name="bounds_on_weak_id", default=True),
            ParameterSpec(name="envelope_param", default="local_effect"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Local fuzzy RKD estimator on the normalized score R = Q - gamma(S).",
        tags=frozenset(
            {"econometrics", "fuzzy-rkd", "state-dependent", "local-polynomial", "tabular"}
        ),
        citations=(
            "Card, D. et al. (2015). Inference on Causal Effects in a Generalized Regression Kink Design.",
            "Calonico, C. et al. (2014). Robust Nonparametric Confidence Intervals for Regression-Discontinuity Designs.",
        ),
        equations={
            "score": "R_i = Q_i - gamma(S_i)",
            "wald_ratio": "tau_FRKD = Delta' E[Y|R] / Delta' E[T|R]",
        },
        assumptions={
            "institutional_rule": "The policy schedule is known and introduces a kink at the normalized threshold.",
            "local_smoothness": "Potential outcomes have smooth derivatives in the normalized score near zero.",
            "first_stage": "The policy variable slope must kink at the local cutoff.",
        },
        when_to_use="Local marginal policy effects at a kinked institutional schedule after state normalization.",
        when_not_to_use="Global kink models or applications with sparse support around the normalized threshold.",
        typical_min_obs=150,
        output_interpretation="local_effect is the derivative Wald ratio at the normalized policy kink.",
    )

    @staticmethod
    def pure_step(state: ThresholdRegressionData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, ThresholdRegressionData)
            else ThresholdRegressionData.model_validate(state)
        )
        return _local_outputs(data, regime_model=ThresholdEffectModel.KINK, params=params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> ThresholdRegressionData:
        return _materialize_threshold_data(bound_inputs, fallback_state)


__all__ = [
    "StateDependentFRDEstimator",
    "StateDependentFRKDEstimator",
    "StateDependentKinkEstimator",
    "StateDependentThresholdEstimator",
]
