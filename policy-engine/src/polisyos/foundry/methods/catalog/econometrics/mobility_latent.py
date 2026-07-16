"""Latent-heterogeneous long-horizon mobility estimator.

This module implements the Phase 4 baseline: a finite mixture of
linear-Gaussian AR(1) state-space panels with class-specific long-run profiles.
The estimator is intentionally NumPy-only so it can run in the Foundry catalog
without optional heavy probabilistic dependencies.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
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
from polisyos.foundry.methods.catalog._phase1_artifacts import resolve_artifact_store
from polisyos.ir.analytics.mobility import (
    MobilityAttrition,
    MobilityDiagnostics,
    MobilityModelSpec,
    MobilityPointEstimate,
    MobilityPopulation,
    MobilityReport,
    MobilityUncertainty,
    persist_mobility_report,
)

from .panel import _explicit_panel_input_slots, _materialize_panel_data
from .protocols import EconometricResult, PanelData

_EPS = 1e-12
_NORMAL = NormalDist()


@dataclass(frozen=True)
class _LatentPanel:
    y: np.ndarray
    design: np.ndarray
    entity_weights: np.ndarray
    entity_ids: np.ndarray
    time_ids: np.ndarray
    feature_names: tuple[str, ...]
    unique_entities: np.ndarray
    unique_times: np.ndarray
    flat_entity_ids: np.ndarray
    flat_time_ids: np.ndarray
    observed_values: np.ndarray
    observed_classes: np.ndarray | None
    class_edges: np.ndarray | None
    class_definition: dict[str, Any]
    n_obs_input: int

    @property
    def n_entities(self) -> int:
        return int(self.y.shape[0])

    @property
    def n_periods(self) -> int:
        return int(self.y.shape[1])

    @property
    def n_features(self) -> int:
        return int(self.design.shape[2])


@dataclass(frozen=True)
class _ClassParams:
    beta: np.ndarray
    rho: float
    sigma_eta2: float
    sigma_e2: float


@dataclass(frozen=True)
class _FitParams:
    pi: np.ndarray
    classes: tuple[_ClassParams, ...]

    @property
    def k(self) -> int:
        return int(self.pi.size)


@dataclass(frozen=True)
class _SmootherOutput:
    loglik: float
    mean: np.ndarray
    var: np.ndarray
    lag_cov: np.ndarray


@dataclass(frozen=True)
class LatentMobilityFit:
    """Internal fit bundle used by the estimator and report adapter."""

    params: _FitParams
    posterior_probs: np.ndarray
    smoothed_state: np.ndarray
    smoothed_state_var: np.ndarray
    log_likelihood: float
    bic: float
    icl: float
    iterations: int
    converged: bool
    selected_k: int
    posterior_entropy: float
    transition_tensor: np.ndarray
    within_type_transition_tensor: np.ndarray
    row_marginals: np.ndarray
    horizons: tuple[int, ...]
    class_edges: np.ndarray
    class_assignments: np.ndarray
    class_definition: dict[str, Any]
    pooled_ar1: float
    var_floor_hits: int
    measurement_error_variance: float | None
    measurement_error_grid: tuple[float, ...]
    robustness: dict[str, Any]
    warnings: tuple[str, ...]
    feature_names: tuple[str, ...]
    n_entities: int
    n_periods: int
    n_obs_input: int

    def to_params_dict(self) -> dict[str, Any]:
        classes: list[dict[str, Any]] = []
        for idx, cls in enumerate(self.params.classes):
            classes.append(
                {
                    "class_index": idx,
                    "share": float(self.params.pi[idx]),
                    "beta": cls.beta.tolist(),
                    "rho": float(cls.rho),
                    "sigma_eta": float(math.sqrt(max(cls.sigma_eta2, 0.0))),
                    "sigma_e": float(math.sqrt(max(cls.sigma_e2, 0.0))),
                }
            )
        return {
            "selected_k": int(self.selected_k),
            "classes": classes,
            "feature_names": list(self.feature_names),
        }


def _safe_logsumexp(values: np.ndarray, axis: int = 1) -> np.ndarray:
    max_values = np.max(values, axis=axis, keepdims=True)
    shifted = np.exp(values - max_values)
    summed = np.sum(shifted, axis=axis, keepdims=True)
    return np.squeeze(max_values + np.log(np.clip(summed, _EPS, None)), axis=axis)


def _normal_cdf(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    try:
        from scipy.special import ndtr

        return np.asarray(ndtr(arr), dtype=float)
    except ModuleNotFoundError:  # pragma: no cover - SciPy is available in full envs.
        vectorized = np.vectorize(_NORMAL.cdf)
        return np.asarray(vectorized(arr), dtype=float)


def _as_2d_exog(value: Any | None, n_obs: int) -> np.ndarray:
    if value is None:
        return np.empty((n_obs, 0), dtype=float)
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2 or arr.shape[0] != n_obs:
        raise ValueError("exog must be a matrix aligned with dependent")
    if np.any(~np.isfinite(arr)):
        raise ValueError("exog must contain only finite values")
    return arr


def _optional_sample_weights(payload: Mapping[str, Any], n_obs: int) -> np.ndarray:
    raw = payload.get("sample_weights", payload.get("weights"))
    if raw is None:
        return np.ones(n_obs, dtype=float)
    weights = np.asarray(raw, dtype=float)
    if weights.ndim != 1 or weights.size != n_obs:
        raise ValueError("sample_weights must be a 1D vector aligned with dependent")
    if np.any(~np.isfinite(weights)) or np.any(weights < 0.0):
        raise ValueError("sample_weights must be finite and non-negative")
    if float(weights.sum()) <= _EPS:
        raise ValueError("sample_weights must sum to a positive value")
    return weights


def _optional_observed_classes(payload: Mapping[str, Any], n_obs: int) -> np.ndarray | None:
    raw = payload.get("observed_classes", payload.get("income_classes"))
    if raw is None:
        return None
    classes = np.asarray(raw)
    if classes.ndim != 1 or classes.size != n_obs:
        raise ValueError("observed_classes must be a 1D vector aligned with dependent")
    classes_float = classes.astype(float)
    if np.any(~np.isfinite(classes_float)):
        raise ValueError("observed_classes must contain finite class ids")
    classes_int = classes_float.astype(int)
    if np.any(classes_int < 0) or np.any(classes_int.astype(float) != classes_float):
        raise ValueError("observed_classes must be non-negative integer ids")
    return classes_int


def _optional_class_edges(payload: Mapping[str, Any]) -> np.ndarray | None:
    raw = payload.get("class_edges", payload.get("income_class_edges"))
    if raw is None:
        return None
    edges = np.asarray(raw, dtype=float)
    if edges.ndim != 1 or edges.size < 3:
        raise ValueError("class_edges must contain at least three ordered boundaries")
    if np.any(np.diff(edges) <= 0.0):
        raise ValueError("class_edges must be strictly increasing")
    edges = edges.copy()
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def _resolve_feature_names(state: Mapping[str, Any], n_exog: int) -> tuple[str, ...]:
    raw = state.get("feature_names")
    if isinstance(raw, Sequence) and not isinstance(raw, str) and len(raw) == n_exog:
        return tuple(str(item) for item in raw)
    return tuple(f"x{idx}" for idx in range(n_exog))


def _profile_basis(
    unique_times: np.ndarray, profile_order: int
) -> tuple[np.ndarray, tuple[str, ...]]:
    t = np.arange(unique_times.size, dtype=float)
    if t.size > 1:
        centered = (t - float(t.mean())) / max(float(t.std()), 1.0)
    else:
        centered = np.zeros_like(t)

    columns = [np.ones(t.size, dtype=float)]
    names = ["intercept"]
    if profile_order >= 1:
        columns.append(centered)
        names.append("profile_linear")
    if profile_order >= 2:
        columns.append(centered**2)
        names.append("profile_quadratic")
    return np.column_stack(columns), tuple(names)


def _coerce_latent_panel(state: Any, params: Mapping[str, Any]) -> _LatentPanel:
    if not isinstance(state, Mapping):
        data = PanelData.model_validate(state)
        payload: Mapping[str, Any] = data.model_dump()
    else:
        payload = state

    dependent = np.asarray(payload.get("dependent"), dtype=float)
    if dependent.ndim != 1 or dependent.size < 8:
        raise ValueError("dependent must be a non-empty 1D vector with at least 8 observations")
    if np.any(~np.isfinite(dependent)):
        raise ValueError("dependent must contain only finite values")

    entity_ids = np.asarray(payload.get("entity_ids"))
    time_ids = np.asarray(payload.get("time_ids"))
    if entity_ids.ndim != 1 or entity_ids.size != dependent.size:
        raise ValueError("entity_ids must align with dependent")
    if time_ids.ndim != 1 or time_ids.size != dependent.size:
        raise ValueError("time_ids must align with dependent")

    exog = _as_2d_exog(payload.get("exog"), dependent.size)
    sample_weights = _optional_sample_weights(payload, dependent.size)
    observed_classes_raw = _optional_observed_classes(payload, dependent.size)
    class_edges = _optional_class_edges(payload)
    exog_names = _resolve_feature_names(payload, exog.shape[1])
    profile_order = int(params.get("profile_order", 1))
    if profile_order not in {0, 1, 2}:
        raise ValueError("profile_order must be one of {0, 1, 2}")

    order = np.lexsort((time_ids, entity_ids))
    y_sorted = dependent[order]
    x_sorted = exog[order]
    weights_sorted = sample_weights[order]
    classes_sorted = None if observed_classes_raw is None else observed_classes_raw[order]
    entity_sorted = entity_ids[order]
    time_sorted = time_ids[order]

    unique_entities = np.unique(entity_sorted)
    unique_times = np.unique(time_sorted)
    n_entities = int(unique_entities.size)
    n_periods = int(unique_times.size)
    if n_entities < 2:
        raise ValueError("latent mobility requires at least 2 entities")
    if n_periods < int(params.get("min_periods", 4)):
        raise ValueError("latent mobility requires at least min_periods panel waves")
    if y_sorted.size != n_entities * n_periods:
        raise ValueError("latent mobility currently requires a balanced panel")

    entity_lookup = {value: idx for idx, value in enumerate(unique_entities)}
    time_lookup = {value: idx for idx, value in enumerate(unique_times)}
    y = np.full((n_entities, n_periods), np.nan, dtype=float)
    x = np.full((n_entities, n_periods, x_sorted.shape[1]), np.nan, dtype=float)
    weights_panel = np.full((n_entities, n_periods), np.nan, dtype=float)
    classes_panel = (
        None if classes_sorted is None else np.full((n_entities, n_periods), -1, dtype=int)
    )
    counts = np.zeros((n_entities, n_periods), dtype=int)
    flat_entity_pos = np.empty(y_sorted.size, dtype=int)
    flat_time_pos = np.empty(y_sorted.size, dtype=int)

    for row, (entity, time) in enumerate(zip(entity_sorted, time_sorted)):
        entity_pos = entity_lookup[entity]
        time_pos = time_lookup[time]
        counts[entity_pos, time_pos] += 1
        if counts[entity_pos, time_pos] > 1:
            raise ValueError("latent mobility requires unique entity-time observations")
        y[entity_pos, time_pos] = y_sorted[row]
        weights_panel[entity_pos, time_pos] = weights_sorted[row]
        if classes_panel is not None and classes_sorted is not None:
            classes_panel[entity_pos, time_pos] = int(classes_sorted[row])
        if x.shape[2] > 0:
            x[entity_pos, time_pos, :] = x_sorted[row]
        flat_entity_pos[row] = entity_pos
        flat_time_pos[row] = time_pos

    if np.any(counts != 1) or np.any(~np.isfinite(y)):
        raise ValueError("latent mobility requires a complete balanced panel without gaps")
    if x.shape[2] > 0 and np.any(~np.isfinite(x)):
        raise ValueError("exog contains non-finite values after panel materialization")
    if np.any(~np.isfinite(weights_panel)):
        raise ValueError("sample_weights contain non-finite values after panel materialization")
    if classes_panel is not None and np.any(classes_panel < 0):
        raise ValueError("observed_classes contain gaps after panel materialization")

    profile, profile_names = _profile_basis(unique_times, profile_order)
    repeated_profile = np.repeat(profile[np.newaxis, :, :], n_entities, axis=0)
    design = repeated_profile if x.shape[2] == 0 else np.concatenate((repeated_profile, x), axis=2)
    feature_names = profile_names + exog_names
    entity_weights = np.mean(weights_panel, axis=1)
    entity_weights = np.clip(entity_weights, 0.0, None)
    weight_sum = float(entity_weights.sum())
    if weight_sum <= _EPS:
        raise ValueError("sample_weights must leave positive entity mass")
    entity_weights = entity_weights * (float(n_entities) / weight_sum)
    if classes_panel is not None:
        n_declared = int(classes_panel.max()) + 1
        if class_edges is not None and class_edges.size - 1 < n_declared:
            raise ValueError("class_edges must provide at least one interval per observed class")
        class_definition = {
            "type": "observed_classes",
            "n_classes": int(class_edges.size - 1 if class_edges is not None else n_declared),
        }
    elif class_edges is not None:
        class_definition = {"type": "fixed_edges", "n_classes": int(class_edges.size - 1)}
    else:
        class_definition = {
            "type": "observed_log_earnings_quantiles",
            "n_classes": int(params.get("n_income_classes", 10)),
        }

    return _LatentPanel(
        y=y,
        design=design,
        entity_weights=entity_weights,
        entity_ids=entity_sorted,
        time_ids=time_sorted,
        feature_names=feature_names,
        unique_entities=unique_entities,
        unique_times=unique_times,
        flat_entity_ids=flat_entity_pos,
        flat_time_ids=flat_time_pos,
        observed_values=y_sorted,
        observed_classes=classes_panel,
        class_edges=class_edges,
        class_definition=class_definition,
        n_obs_input=int(dependent.size),
    )


def _weighted_lstsq(design: np.ndarray, target: np.ndarray, weights: np.ndarray) -> np.ndarray:
    x = np.asarray(design, dtype=float)
    y = np.asarray(target, dtype=float)
    w = np.clip(np.asarray(weights, dtype=float), 0.0, None)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.size or w.size != y.size:
        raise ValueError("weighted least-squares inputs are misaligned")
    if float(w.sum()) <= _EPS:
        w = np.ones_like(w)
    xtwx = x.T @ (w[:, None] * x)
    ridge = 1e-8 * np.eye(x.shape[1], dtype=float)
    xtwy = x.T @ (w * y)
    return np.linalg.solve(xtwx + ridge, xtwy)


def _pooled_ar1(y: np.ndarray, entity_weights: np.ndarray | None = None) -> float:
    y0 = y[:, :-1].reshape(-1)
    y1 = y[:, 1:].reshape(-1)
    if entity_weights is None:
        weights = np.ones_like(y0)
    else:
        weights = np.repeat(np.asarray(entity_weights, dtype=float), y.shape[1] - 1)
        weights = np.clip(weights, 0.0, None)
    if float(weights.sum()) <= _EPS:
        weights = np.ones_like(y0)
    x = y0 - float(np.average(y0, weights=weights))
    z = y1 - float(np.average(y1, weights=weights))
    denom = float(np.sum(weights * x * x))
    if denom <= _EPS:
        return 0.0
    return float(np.clip(float(np.sum(weights * x * z)) / denom, -0.995, 0.995))


def _stationary_var(rho: float, sigma_eta2: float) -> float:
    return float(sigma_eta2 / max(1.0 - rho * rho, 1e-4))


def _kalman_smooth_1d(
    residual: np.ndarray,
    *,
    rho: float,
    sigma_eta2: float,
    sigma_e2: float,
) -> _SmootherOutput:
    obs = np.asarray(residual, dtype=float)
    n_periods = obs.size
    filtered_mean = np.zeros(n_periods, dtype=float)
    filtered_var = np.zeros(n_periods, dtype=float)
    pred_mean = np.zeros(n_periods, dtype=float)
    pred_var = np.zeros(n_periods, dtype=float)
    gains = np.zeros(n_periods, dtype=float)
    loglik = 0.0

    pred_mean[0] = 0.0
    pred_var[0] = max(_stationary_var(rho, sigma_eta2), sigma_eta2, _EPS)
    for time_idx in range(n_periods):
        innovation = obs[time_idx] - pred_mean[time_idx]
        innovation_var = max(pred_var[time_idx] + sigma_e2, _EPS)
        gains[time_idx] = pred_var[time_idx] / innovation_var
        filtered_mean[time_idx] = pred_mean[time_idx] + gains[time_idx] * innovation
        filtered_var[time_idx] = max((1.0 - gains[time_idx]) * pred_var[time_idx], _EPS)
        loglik += -0.5 * (
            math.log(2.0 * math.pi * innovation_var)
            + float(innovation * innovation) / innovation_var
        )
        if time_idx + 1 < n_periods:
            pred_mean[time_idx + 1] = rho * filtered_mean[time_idx]
            pred_var[time_idx + 1] = max(rho * rho * filtered_var[time_idx] + sigma_eta2, _EPS)

    smooth_mean = filtered_mean.copy()
    smooth_var = filtered_var.copy()
    smoother_gain = np.zeros(max(n_periods - 1, 0), dtype=float)
    for time_idx in range(n_periods - 2, -1, -1):
        smoother_gain[time_idx] = filtered_var[time_idx] * rho / max(pred_var[time_idx + 1], _EPS)
        smooth_mean[time_idx] = filtered_mean[time_idx] + smoother_gain[time_idx] * (
            smooth_mean[time_idx + 1] - pred_mean[time_idx + 1]
        )
        smooth_var[time_idx] = filtered_var[time_idx] + smoother_gain[time_idx] ** 2 * (
            smooth_var[time_idx + 1] - pred_var[time_idx + 1]
        )
        smooth_var[time_idx] = max(smooth_var[time_idx], _EPS)

    lag_cov = np.zeros(n_periods, dtype=float)
    for time_idx in range(1, n_periods):
        lag_cov[time_idx] = smoother_gain[time_idx - 1] * smooth_var[time_idx]

    return _SmootherOutput(
        loglik=float(loglik),
        mean=smooth_mean,
        var=smooth_var,
        lag_cov=lag_cov,
    )


def _entity_mean_initial_weights(y: np.ndarray, k: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    entity_mean = y.mean(axis=1)
    jitter = 1e-8 * rng.normal(size=entity_mean.size)
    ranked = np.argsort(entity_mean + jitter)
    labels = np.empty(entity_mean.size, dtype=int)
    chunks = np.array_split(ranked, k)
    for idx, chunk in enumerate(chunks):
        labels[chunk] = idx
    weights = np.full((entity_mean.size, k), 0.02 / max(k - 1, 1), dtype=float)
    for row, label in enumerate(labels):
        weights[row, label] = 0.98
    if k == 1:
        weights[:, 0] = 1.0
    return weights / weights.sum(axis=1, keepdims=True)


def _initialize_params(
    panel: _LatentPanel,
    *,
    k: int,
    seed: int,
    rho_bound: float,
    var_floor: float,
    measurement_error_mode: str,
    fixed_sigma_e2: float | None,
) -> _FitParams:
    weights = _entity_mean_initial_weights(panel.y, k, seed)
    flat_design = panel.design.reshape(panel.n_entities * panel.n_periods, panel.n_features)
    flat_y = panel.y.reshape(-1)
    pooled_rho = _pooled_ar1(panel.y, panel.entity_weights)
    classes: list[_ClassParams] = []
    total_entity_weight = max(float(panel.entity_weights.sum()), _EPS)
    pi = np.clip(
        (panel.entity_weights[:, None] * weights).sum(axis=0) / total_entity_weight, _EPS, None
    )
    pi /= pi.sum()

    for cls_idx in range(k):
        entity_weights = panel.entity_weights * weights[:, cls_idx]
        obs_weights = np.repeat(entity_weights, panel.n_periods)
        beta = _weighted_lstsq(flat_design, flat_y, obs_weights)
        residual = panel.y - np.einsum("ntp,p->nt", panel.design, beta)
        lag = residual[:, :-1].reshape(-1)
        lead = residual[:, 1:].reshape(-1)
        lag_weights = np.repeat(entity_weights, panel.n_periods - 1)
        lag_centered = lag - float(np.average(lag, weights=np.clip(lag_weights, _EPS, None)))
        lead_centered = lead - float(np.average(lead, weights=np.clip(lag_weights, _EPS, None)))
        denom = float(np.sum(lag_weights * lag_centered * lag_centered))
        rho = (
            pooled_rho
            if denom <= _EPS
            else float(np.sum(lag_weights * lag_centered * lead_centered) / denom)
        )
        rho = float(np.clip(rho, -rho_bound, rho_bound))
        residual_var = float(
            np.average(residual.reshape(-1) ** 2, weights=np.clip(obs_weights, _EPS, None))
        )
        sigma_e2 = (
            max(float(fixed_sigma_e2), var_floor)
            if measurement_error_mode in {"known", "fixed", "fixed_grid"}
            and fixed_sigma_e2 is not None
            else max(0.15 * residual_var, var_floor)
        )
        sigma_eta2 = max((1.0 - rho * rho) * max(residual_var - sigma_e2, var_floor), var_floor)
        classes.append(
            _ClassParams(
                beta=beta,
                rho=rho,
                sigma_eta2=sigma_eta2,
                sigma_e2=sigma_e2,
            )
        )

    return _order_params(_FitParams(pi=pi, classes=tuple(classes)), panel)


def _long_run_means(params: _FitParams, panel: _LatentPanel) -> np.ndarray:
    average_design = panel.design.reshape(-1, panel.n_features).mean(axis=0)
    return np.asarray([float(average_design @ cls.beta) for cls in params.classes], dtype=float)


def _order_params(params: _FitParams, panel: _LatentPanel) -> _FitParams:
    order = np.argsort(_long_run_means(params, panel))
    pi = params.pi[order]
    classes = tuple(params.classes[int(idx)] for idx in order)
    return _FitParams(pi=pi, classes=classes)


def _e_step(
    panel: _LatentPanel,
    params: _FitParams,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    n_entities, n_periods = panel.n_entities, panel.n_periods
    k = params.k
    loglik_by_class = np.zeros((n_entities, k), dtype=float)
    smooth_mean = np.zeros((n_entities, k, n_periods), dtype=float)
    smooth_var = np.zeros((n_entities, k, n_periods), dtype=float)
    lag_cov = np.zeros((n_entities, k, n_periods), dtype=float)

    for cls_idx, cls in enumerate(params.classes):
        deterministic = np.einsum("ntp,p->nt", panel.design, cls.beta)
        residual = panel.y - deterministic
        for entity_idx in range(n_entities):
            smooth = _kalman_smooth_1d(
                residual[entity_idx],
                rho=cls.rho,
                sigma_eta2=cls.sigma_eta2,
                sigma_e2=cls.sigma_e2,
            )
            loglik_by_class[entity_idx, cls_idx] = smooth.loglik
            smooth_mean[entity_idx, cls_idx, :] = smooth.mean
            smooth_var[entity_idx, cls_idx, :] = smooth.var
            lag_cov[entity_idx, cls_idx, :] = smooth.lag_cov

    weighted_loglik = loglik_by_class + np.log(np.clip(params.pi, _EPS, None))[None, :]
    log_denom = _safe_logsumexp(weighted_loglik, axis=1)
    posterior = np.exp(weighted_loglik - log_denom[:, None])
    total_ll = float(np.sum(panel.entity_weights * log_denom))
    return posterior, smooth_mean, smooth_var, lag_cov, total_ll


def _m_step(
    panel: _LatentPanel,
    old_params: _FitParams,
    posterior: np.ndarray,
    smooth_mean: np.ndarray,
    smooth_var: np.ndarray,
    lag_cov: np.ndarray,
    *,
    min_class_share: float,
    rho_bound: float,
    var_floor: float,
    measurement_error_mode: str,
    fixed_sigma_e2: float | None,
) -> tuple[_FitParams, int]:
    k = old_params.k
    total_entity_weight = max(float(panel.entity_weights.sum()), _EPS)
    raw_pi = (panel.entity_weights[:, None] * posterior).sum(axis=0) / total_entity_weight
    pi = np.maximum(raw_pi, min_class_share if k > 1 else _EPS)
    pi /= pi.sum()
    flat_design = panel.design.reshape(panel.n_entities * panel.n_periods, panel.n_features)
    flat_y = panel.y.reshape(-1)
    classes: list[_ClassParams] = []
    floor_hits = 0

    for cls_idx in range(k):
        entity_weights = panel.entity_weights * posterior[:, cls_idx]
        obs_weights = np.repeat(entity_weights, panel.n_periods)
        target = (panel.y - smooth_mean[:, cls_idx, :]).reshape(-1)
        beta = _weighted_lstsq(flat_design, target, obs_weights)

        state_mean = smooth_mean[:, cls_idx, :]
        state_var = smooth_var[:, cls_idx, :]
        state_second = state_mean * state_mean + state_var
        cross_second = state_mean[:, 1:] * state_mean[:, :-1] + lag_cov[:, cls_idx, 1:]
        denom = float(np.sum(entity_weights[:, None] * state_second[:, :-1]))
        numer = float(np.sum(entity_weights[:, None] * cross_second))
        rho = old_params.classes[cls_idx].rho if denom <= _EPS else numer / denom
        rho = float(np.clip(rho, -rho_bound, rho_bound))

        innovation_second = (
            state_second[:, 1:] - 2.0 * rho * cross_second + rho * rho * state_second[:, :-1]
        )
        innovation_denom = max(float(np.sum(entity_weights) * max(panel.n_periods - 1, 1)), _EPS)
        sigma_eta2 = float(np.sum(entity_weights[:, None] * innovation_second) / innovation_denom)
        if sigma_eta2 < var_floor:
            floor_hits += 1
        sigma_eta2 = max(sigma_eta2, var_floor)

        deterministic = np.einsum("ntp,p->nt", panel.design, beta)
        residual = panel.y - deterministic
        measurement_second = (residual - state_mean) ** 2 + state_var
        measurement_denom = max(float(np.sum(entity_weights) * panel.n_periods), _EPS)
        if (
            measurement_error_mode in {"known", "fixed", "fixed_grid"}
            and fixed_sigma_e2 is not None
        ):
            sigma_e2 = max(float(fixed_sigma_e2), var_floor)
        else:
            sigma_e2 = float(
                np.sum(entity_weights[:, None] * measurement_second) / measurement_denom
            )
        if sigma_e2 < var_floor:
            floor_hits += 1
        sigma_e2 = max(sigma_e2, var_floor)

        classes.append(
            _ClassParams(
                beta=beta,
                rho=rho,
                sigma_eta2=sigma_eta2,
                sigma_e2=sigma_e2,
            )
        )

    return _order_params(_FitParams(pi=pi, classes=tuple(classes)), panel), floor_hits


def _parameter_count(k: int, n_features: int, *, measurement_fixed: bool) -> int:
    variance_terms = 2 if not measurement_fixed else 1
    return int((k - 1) + k * (n_features + 1 + variance_terms))


def _class_edges(values: np.ndarray, n_classes: int) -> np.ndarray:
    if n_classes < 2:
        raise ValueError("n_income_classes must be at least 2")
    quantiles = np.quantile(values, np.linspace(0.0, 1.0, n_classes + 1))
    internal = np.asarray(quantiles[1:-1], dtype=float)
    if np.unique(internal).size != internal.size:
        lo, hi = float(np.min(values)), float(np.max(values))
        if hi <= lo:
            hi = lo + 1.0
        internal = np.linspace(lo, hi, n_classes + 1)[1:-1]
    return np.concatenate(([-np.inf], internal, [np.inf])).astype(float)


def _assign_classes(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.digitize(values, edges[1:-1], right=False).astype(int)


def _destination_probabilities(mean: float, variance: float, edges: np.ndarray) -> np.ndarray:
    sd = math.sqrt(max(float(variance), _EPS))
    upper = _normal_cdf((edges[1:] - mean) / sd)
    lower = _normal_cdf((edges[:-1] - mean) / sd)
    probs = np.clip(upper - lower, 0.0, 1.0)
    total = float(probs.sum())
    if total <= _EPS:
        return np.full(edges.size - 1, 1.0 / (edges.size - 1), dtype=float)
    return probs / total


def _future_state_variance(rho: float, sigma_eta2: float, horizon: int) -> float:
    if horizon <= 0:
        return 0.0
    if abs(rho) >= 0.999:
        return float(horizon * sigma_eta2)
    return float(sigma_eta2 * (1.0 - rho ** (2 * horizon)) / max(1.0 - rho * rho, _EPS))


def _grouped_fixed_effects_robustness(
    panel: _LatentPanel,
    params: _FitParams,
    posterior: np.ndarray,
    pooled_ar1: float,
) -> dict[str, Any]:
    labels = np.argmax(posterior, axis=1)
    class_rho: list[float | None] = []
    class_counts: list[int] = []
    for cls_idx in range(params.k):
        mask = labels == cls_idx
        class_counts.append(int(mask.sum()))
        if int(mask.sum()) < 2 or panel.n_periods < 3:
            class_rho.append(None)
            continue
        y_cls = panel.y[mask]
        weights = np.repeat(panel.entity_weights[mask], panel.n_periods - 1)
        demeaned = y_cls - y_cls.mean(axis=1, keepdims=True)
        lag = demeaned[:, :-1].reshape(-1)
        lead = demeaned[:, 1:].reshape(-1)
        lag = lag - float(np.average(lag, weights=np.clip(weights, _EPS, None)))
        lead = lead - float(np.average(lead, weights=np.clip(weights, _EPS, None)))
        denom = float(np.sum(weights * lag * lag))
        class_rho.append(
            None
            if denom <= _EPS
            else float(np.clip(np.sum(weights * lag * lead) / denom, -0.995, 0.995))
        )

    finite_rho = [rho for rho in class_rho if rho is not None]
    return {
        "family": "classify_then_grouped_entity_demeaned_ar1",
        "class_counts": class_counts,
        "class_rho": class_rho,
        "pooled_ar1": float(pooled_ar1),
        "max_grouped_rho": None if not finite_rho else float(max(finite_rho)),
        "pooled_minus_max_grouped_rho": None
        if not finite_rho
        else float(pooled_ar1 - max(finite_rho)),
    }


def build_h_step_transition_kernels(
    fit_params: _FitParams,
    panel: _LatentPanel,
    posterior: np.ndarray,
    smooth_mean: np.ndarray,
    smooth_var: np.ndarray,
    *,
    horizons: Sequence[int],
    n_classes: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build aggregate and within-type posterior-weighted transition kernels."""

    clean_horizons = tuple(int(h) for h in horizons if int(h) > 0)
    if not clean_horizons:
        raise ValueError("horizons must contain at least one positive integer")
    if panel.class_edges is not None:
        edges = panel.class_edges
        n_classes = int(edges.size - 1)
    else:
        edges = _class_edges(panel.y.reshape(-1), n_classes)
    class_assignments = (
        panel.observed_classes.copy()
        if panel.observed_classes is not None
        else _assign_classes(panel.y, edges)
    )
    if np.any(class_assignments < 0) or np.any(class_assignments >= n_classes):
        raise ValueError("observed_classes must fall inside the declared income classes")
    k = fit_params.k
    aggregate = np.zeros((len(clean_horizons), n_classes, n_classes), dtype=float)
    within_type = np.zeros((k, len(clean_horizons), n_classes, n_classes), dtype=float)
    row_marginals = np.zeros((len(clean_horizons), n_classes), dtype=float)

    unconditional = np.bincount(
        class_assignments.reshape(-1),
        weights=np.repeat(panel.entity_weights, panel.n_periods),
        minlength=n_classes,
    ).astype(float)
    unconditional = unconditional / max(float(unconditional.sum()), _EPS)

    for h_idx, horizon in enumerate(clean_horizons):
        if horizon >= panel.n_periods:
            active_times = range(panel.n_periods - 1)
            effective_horizon = panel.n_periods - 1
        else:
            active_times = range(panel.n_periods - horizon)
            effective_horizon = horizon
        aggregate_den = np.zeros(n_classes, dtype=float)
        within_den = np.zeros((k, n_classes), dtype=float)

        for entity_idx in range(panel.n_entities):
            entity_weight = float(panel.entity_weights[entity_idx])
            for time_idx in active_times:
                origin = int(class_assignments[entity_idx, time_idx])
                row_marginals[h_idx, origin] += entity_weight
                for cls_idx, cls in enumerate(fit_params.classes):
                    weight = entity_weight * float(posterior[entity_idx, cls_idx])
                    if weight <= _EPS:
                        continue
                    destination_time = min(time_idx + effective_horizon, panel.n_periods - 1)
                    future_design = panel.design[entity_idx, destination_time]
                    mean = float(
                        future_design @ cls.beta
                        + (cls.rho**effective_horizon) * smooth_mean[entity_idx, cls_idx, time_idx]
                    )
                    variance = float(
                        (cls.rho ** (2 * effective_horizon))
                        * smooth_var[entity_idx, cls_idx, time_idx]
                        + _future_state_variance(cls.rho, cls.sigma_eta2, effective_horizon)
                        + cls.sigma_e2
                    )
                    probs = _destination_probabilities(mean, variance, edges)
                    aggregate[h_idx, origin, :] += weight * probs
                    aggregate_den[origin] += weight
                    within_type[cls_idx, h_idx, origin, :] += weight * probs
                    within_den[cls_idx, origin] += weight

        for row in range(n_classes):
            if aggregate_den[row] > _EPS:
                aggregate[h_idx, row, :] /= aggregate_den[row]
            else:
                aggregate[h_idx, row, :] = unconditional
        for cls_idx in range(k):
            for row in range(n_classes):
                if within_den[cls_idx, row] > _EPS:
                    within_type[cls_idx, h_idx, row, :] /= within_den[cls_idx, row]
                else:
                    within_type[cls_idx, h_idx, row, :] = aggregate[h_idx, row, :]

        row_total = float(row_marginals[h_idx].sum())
        if row_total > _EPS:
            row_marginals[h_idx] /= row_total
        else:
            row_marginals[h_idx] = np.full(n_classes, 1.0 / n_classes, dtype=float)

    return aggregate, within_type, row_marginals, edges, class_assignments


def fit_latent_mobility(
    panel: _LatentPanel,
    *,
    k_grid: Sequence[int] = (1, 2, 3),
    n_starts: int = 10,
    max_iter: int = 150,
    tol: float = 1e-5,
    min_class_share: float = 0.03,
    rho_bound: float = 0.995,
    var_floor: float = 1e-6,
    select_k: str = "bic",
    measurement_error_mode: str = "iid",
    fixed_sigma_e2: float | None = None,
    horizons: Sequence[int] = (1, 5, 10),
    n_classes: int = 10,
    random_seed: int = 17,
) -> LatentMobilityFit:
    """Estimate the finite-mixture mobility model with EM and Kalman smoothing."""

    clean_grid = tuple(sorted({int(k) for k in k_grid if int(k) >= 1}))
    if not clean_grid:
        raise ValueError("k_grid must contain at least one positive integer")
    if max(clean_grid) > panel.n_entities:
        raise ValueError("k_grid cannot exceed the number of panel entities")
    if n_starts < 1:
        raise ValueError("n_starts must be positive")

    score_name = str(select_k or "bic").strip().lower()
    if score_name not in {"bic", "icl"}:
        raise ValueError("select_k must be one of {'bic', 'icl'}")

    best: LatentMobilityFit | None = None
    best_score = math.inf
    pooled = _pooled_ar1(panel.y, panel.entity_weights)
    measurement_fixed = measurement_error_mode in {"known", "fixed", "fixed_grid"} and (
        fixed_sigma_e2 is not None
    )

    for k in clean_grid:
        for start in range(n_starts):
            current = _initialize_params(
                panel,
                k=k,
                seed=random_seed + 997 * start + 7919 * k,
                rho_bound=rho_bound,
                var_floor=var_floor,
                measurement_error_mode=measurement_error_mode,
                fixed_sigma_e2=fixed_sigma_e2,
            )
            previous_ll = -math.inf
            converged = False
            total_floor_hits = 0
            posterior = np.full((panel.n_entities, k), 1.0 / k, dtype=float)
            smooth_mean = np.zeros((panel.n_entities, k, panel.n_periods), dtype=float)
            smooth_var = np.zeros_like(smooth_mean)
            total_ll = -math.inf

            for iteration in range(1, max_iter + 1):
                posterior, smooth_mean, smooth_var, lag_cov, total_ll = _e_step(panel, current)
                updated, floor_hits = _m_step(
                    panel,
                    current,
                    posterior,
                    smooth_mean,
                    smooth_var,
                    lag_cov,
                    min_class_share=min_class_share,
                    rho_bound=rho_bound,
                    var_floor=var_floor,
                    measurement_error_mode=measurement_error_mode,
                    fixed_sigma_e2=fixed_sigma_e2,
                )
                total_floor_hits += floor_hits
                if math.isfinite(previous_ll):
                    rel_change = abs(total_ll - previous_ll) / max(abs(previous_ll), 1.0)
                    if rel_change < tol:
                        converged = True
                        current = updated
                        break
                previous_ll = total_ll
                current = updated
            else:
                iteration = max_iter

            posterior, smooth_mean, smooth_var, _, total_ll = _e_step(panel, current)
            entropy = float(
                -np.sum(
                    panel.entity_weights[:, None]
                    * posterior
                    * np.log(np.clip(posterior, _EPS, None))
                )
            )
            n_params = _parameter_count(k, panel.n_features, measurement_fixed=measurement_fixed)
            bic = float(-2.0 * total_ll + n_params * math.log(panel.n_obs_input))
            icl = float(bic + 2.0 * entropy)
            aggregate, within, row_marginals, edges, assignments = build_h_step_transition_kernels(
                current,
                panel,
                posterior,
                smooth_mean,
                smooth_var,
                horizons=horizons,
                n_classes=n_classes,
            )
            warnings: list[str] = []
            if not converged:
                warnings.append("EM did not reach the requested tolerance before max_iter")
            if np.min(current.pi) <= min_class_share + 1e-10 and k > 1:
                warnings.append("At least one latent class is at the minimum class-share floor")
            robustness = _grouped_fixed_effects_robustness(panel, current, posterior, pooled)

            candidate = LatentMobilityFit(
                params=current,
                posterior_probs=posterior,
                smoothed_state=np.einsum("ik,ikt->it", posterior, smooth_mean),
                smoothed_state_var=np.einsum("ik,ikt->it", posterior, smooth_var),
                log_likelihood=float(total_ll),
                bic=bic,
                icl=icl,
                iterations=int(iteration),
                converged=converged,
                selected_k=k,
                posterior_entropy=entropy,
                transition_tensor=aggregate,
                within_type_transition_tensor=within,
                row_marginals=row_marginals,
                horizons=tuple(int(h) for h in horizons if int(h) > 0),
                class_edges=edges,
                class_assignments=assignments,
                class_definition=dict(panel.class_definition),
                pooled_ar1=pooled,
                var_floor_hits=int(total_floor_hits),
                measurement_error_variance=None
                if fixed_sigma_e2 is None
                else float(fixed_sigma_e2),
                measurement_error_grid=() if fixed_sigma_e2 is None else (float(fixed_sigma_e2),),
                robustness=robustness,
                warnings=tuple(warnings),
                feature_names=panel.feature_names,
                n_entities=panel.n_entities,
                n_periods=panel.n_periods,
                n_obs_input=panel.n_obs_input,
            )
            score = candidate.bic if score_name == "bic" else candidate.icl
            if score < best_score:
                best = candidate
                best_score = score

    if best is None:
        raise RuntimeError("latent mobility EM did not produce a candidate fit")
    return best


def _mobility_stats(joint: np.ndarray, row_marginals: np.ndarray) -> dict[str, float]:
    upward = float(np.sum(np.triu(joint, k=1)))
    downward = float(np.sum(np.tril(joint, k=-1)))
    immobility = float(np.trace(joint))
    stats = {
        "upward_rate": upward,
        "downward_rate": downward,
        "immobility_rate": immobility,
    }
    n_classes = int(joint.shape[0])
    if n_classes > 1:
        safe_rows = np.clip(row_marginals, _EPS, None)
        persistence = float(np.sum(np.diag(joint) / safe_rows))
        stats["shorrocks_index"] = float(
            max(0.0, min(1.0, (n_classes - persistence) / (n_classes - 1.0)))
        )
    return stats


def build_latent_mobility_report(
    fit: LatentMobilityFit | Mapping[str, Any],
    *,
    horizon: int | None = None,
) -> MobilityReport:
    """Convert a latent-mobility fit or payload into the typed mobility IR."""

    if isinstance(fit, LatentMobilityFit):
        horizons = tuple(fit.horizons)
        transition_tensor = np.asarray(fit.transition_tensor, dtype=float)
        row_marginals_tensor = np.asarray(fit.row_marginals, dtype=float)
        params_dict = fit.to_params_dict()
        diagnostics = {
            "selected_k": fit.selected_k,
            "bic": fit.bic,
            "icl": fit.icl,
            "posterior_entropy": fit.posterior_entropy,
            "pooled_ar1": fit.pooled_ar1,
            "var_floor_hits": fit.var_floor_hits,
            "measurement_error_variance": fit.measurement_error_variance,
            "measurement_error_grid": list(fit.measurement_error_grid),
            "robustness": fit.robustness,
        }
        metadata = {
            "horizons": list(horizons),
            "class_edges": fit.class_edges.tolist(),
            "class_definition": dict(fit.class_definition),
            "within_type_transition_tensor": fit.within_type_transition_tensor.tolist(),
            "feature_names": list(fit.feature_names),
        }
        warnings = list(fit.warnings)
        n_entities = fit.n_entities
        n_periods = fit.n_periods
    else:
        horizons = tuple(int(h) for h in fit.get("horizons", (1,)))
        transition_tensor = np.asarray(fit["transition_tensor"], dtype=float)
        row_marginals_tensor = np.asarray(
            fit.get(
                "row_marginals",
                np.full(
                    (len(horizons), transition_tensor.shape[-1]), 1.0 / transition_tensor.shape[-1]
                ),
            ),
            dtype=float,
        )
        params_dict = dict(fit.get("params", {}))
        diagnostics = dict(fit.get("diagnostics", {}))
        metadata = dict(fit.get("metadata", {}))
        warnings = list(fit.get("warnings", ()))
        n_entities = int(fit.get("n_entities", 0))
        n_periods = int(fit.get("n_periods", 0))

    if transition_tensor.ndim != 3:
        raise ValueError("transition_tensor must have shape (n_horizons, n_classes, n_classes)")
    selected_horizon = int(horizon or (5 if 5 in horizons else horizons[0]))
    if selected_horizon not in horizons:
        raise ValueError("requested horizon is not present in the latent mobility payload")
    horizon_idx = horizons.index(selected_horizon)
    transition = transition_tensor[horizon_idx]
    row_marginals = row_marginals_tensor[horizon_idx]
    row_total = float(row_marginals.sum())
    if row_total <= _EPS:
        row_marginals = np.full(transition.shape[0], 1.0 / transition.shape[0], dtype=float)
    else:
        row_marginals = row_marginals / row_total
    joint = row_marginals[:, None] * transition
    col_marginals = joint.sum(axis=0)
    mobility_stats = _mobility_stats(joint, row_marginals)

    return MobilityReport(
        analysis_type="latent_mobility_transition_matrix",
        estimand_id=f"mobility.latent.h{selected_horizon}",
        status="warn" if warnings else "ok",
        population=MobilityPopulation(
            target_population="posterior-weighted balanced panel entities",
            panel_length=n_periods or None,
            waves_used=list(range(1, n_periods + 1)) if n_periods else [],
            class_definition=metadata.get(
                "class_definition",
                {"type": "observed_log_earnings_quantiles", "n_classes": int(transition.shape[0])},
            ),
        ),
        attrition=MobilityAttrition(mechanism_assumed="balanced_panel_or_prehandled_missingness"),
        point_estimate=MobilityPointEstimate(
            joint_matrix=joint.tolist(),
            transition_matrix=transition.tolist(),
            row_marginals=row_marginals.tolist(),
            col_marginals=col_marginals.tolist(),
            mobility_stats=mobility_stats,
        ),
        uncertainty=MobilityUncertainty(method="not_estimated"),
        diagnostics=MobilityDiagnostics(
            observed_full_cases=n_entities or None,
            warnings=warnings,
            sensitivity_grid={
                "selected_horizon": selected_horizon,
                "available_horizons": list(horizons),
                "pooled_ar1": diagnostics.get("pooled_ar1"),
                "measurement_error_variance": diagnostics.get("measurement_error_variance"),
                "measurement_error_grid": diagnostics.get("measurement_error_grid"),
            },
        ),
        assumptions=[
            "Finite latent worker types approximate persistent unobserved heterogeneity.",
            "Within-type transitory earnings follow a stationary Gaussian AR(1).",
            "Measurement error is separate from the transitory innovation.",
            "Latent class labels are ordered by fitted long-run mean earnings.",
        ],
        summary_metrics={
            "transition_matrix": transition.tolist(),
            "upward_mobility_rate": mobility_stats["upward_rate"],
            "downward_mobility_rate": mobility_stats["downward_rate"],
            "immobility_rate": mobility_stats["immobility_rate"],
            "n_classes": int(transition.shape[0]),
            "n_obs": n_entities,
            "selected_k": int(diagnostics.get("selected_k", params_dict.get("selected_k", 0))),
            "horizon": selected_horizon,
        },
        metadata={
            **metadata,
            "model": MobilityModelSpec(
                family="finite_mixture_ar_state_space",
                features=list(metadata.get("feature_names", [])),
                metadata={"params": params_dict, "diagnostics": diagnostics},
            ).model_dump(mode="json"),
        },
    )


def _econometric_result_from_fit(
    fit: LatentMobilityFit, *, measurement_error_mode: str
) -> EconometricResult:
    params: dict[str, float] = {}
    long_run = []
    average_share = np.asarray(fit.params.pi, dtype=float)
    for cls_idx, cls in enumerate(fit.params.classes):
        prefix = f"class_{cls_idx}"
        params[f"{prefix}_share"] = float(average_share[cls_idx])
        params[f"{prefix}_rho"] = float(cls.rho)
        params[f"{prefix}_sigma_eta"] = float(math.sqrt(max(cls.sigma_eta2, 0.0)))
        params[f"{prefix}_sigma_e"] = float(math.sqrt(max(cls.sigma_e2, 0.0)))
        params[f"{prefix}_long_run_mean"] = float(cls.beta[0])
        long_run.append(float(cls.beta[0]))
        for feature_name, value in zip(fit.feature_names, cls.beta):
            safe_name = str(feature_name).replace(" ", "_")
            params[f"{prefix}_beta_{safe_name}"] = float(value)

    rho_values = [float(cls.rho) for cls in fit.params.classes]
    return EconometricResult(
        method_name="latent_mobility",
        params=params,
        confidence_level=0.95,
        n_obs=fit.n_obs_input,
        n_entities=fit.n_entities,
        n_periods=fit.n_periods,
        diagnostics={
            "selected_k": fit.selected_k,
            "bic": fit.bic,
            "icl": fit.icl,
            "log_likelihood": fit.log_likelihood,
            "iterations": fit.iterations,
            "converged": fit.converged,
            "posterior_entropy": fit.posterior_entropy,
            "class_share": fit.params.pi.tolist(),
            "rho": rho_values,
            "rho_min": float(np.min(rho_values)),
            "rho_max": float(np.max(rho_values)),
            "pooled_ar1": fit.pooled_ar1,
            "var_floor_hits": fit.var_floor_hits,
            "horizons": list(fit.horizons),
            "n_income_classes": int(fit.transition_tensor.shape[-1]),
            "measurement_error_mode": measurement_error_mode,
            "measurement_error_variance": fit.measurement_error_variance,
            "measurement_error_grid": list(fit.measurement_error_grid),
            "robustness": fit.robustness,
        },
        model_info={
            "library": "numpy",
            "estimator": "finite_mixture_ar_state_space_em",
            "selection_criteria": {"bic": fit.bic, "icl": fit.icl},
        },
        metadata={
            "assumptions": [
                "constant_latent_type",
                "class_specific_profile",
                "stationary_ar1_transitory_component",
                "separate_iid_measurement_error",
            ],
            "warnings": list(fit.warnings),
            "feature_names": list(fit.feature_names),
            "class_edges": fit.class_edges.tolist(),
            "class_definition": dict(fit.class_definition),
            "long_run_means": long_run,
        },
    )


def _resolve_k_grid(params: Mapping[str, Any]) -> tuple[int, ...]:
    if "n_types" in params and params.get("n_types") is not None:
        return (int(params["n_types"]),)
    raw = params.get("k_grid", (1, 2, 3))
    if isinstance(raw, int):
        return (int(raw),)
    return tuple(int(item) for item in raw)


def _fixed_measurement_variance(params: Mapping[str, Any]) -> float | None:
    if "measurement_error_variance" in params and params["measurement_error_variance"] is not None:
        return float(params["measurement_error_variance"])
    if "sigma_e" in params and params["sigma_e"] is not None:
        sigma_e = float(params["sigma_e"])
        return sigma_e * sigma_e
    return None


def _measurement_grid_variances(
    panel: _LatentPanel, params: Mapping[str, Any]
) -> tuple[float, ...]:
    raw = params.get("measurement_error_variance_grid")
    if raw is not None:
        grid = tuple(float(item) for item in raw)
    else:
        raw_sigma = params.get("sigma_e_grid")
        if raw_sigma is not None:
            grid = tuple(float(item) ** 2 for item in raw_sigma)
        else:
            fixed = _fixed_measurement_variance(params)
            if fixed is not None:
                grid = (float(fixed),)
            else:
                y_var = max(float(np.var(panel.y)), _EPS)
                grid = tuple((share * share) * y_var for share in (0.02, 0.05, 0.10, 0.20))
    clean = tuple(sorted({max(float(item), 0.0) for item in grid}))
    if not clean:
        raise ValueError("measurement_error_variance_grid must contain at least one value")
    return clean


def _fit_with_params(
    panel: _LatentPanel,
    params: Mapping[str, Any],
    *,
    measurement_error_mode: str,
    fixed_sigma_e2: float | None,
    measurement_error_grid: tuple[float, ...] = (),
) -> LatentMobilityFit:
    horizons = tuple(int(h) for h in params.get("horizons", (1, 5, 10)))
    fit = fit_latent_mobility(
        panel,
        k_grid=_resolve_k_grid(params),
        n_starts=int(params.get("n_starts", 10)),
        max_iter=int(params.get("max_iter", 150)),
        tol=float(params.get("tol", 1e-5)),
        min_class_share=float(params.get("min_class_share", 0.03)),
        rho_bound=float(params.get("rho_bound", 0.995)),
        var_floor=float(params.get("var_floor", 1e-6)),
        select_k=str(params.get("select_k", "bic")),
        measurement_error_mode=measurement_error_mode,
        fixed_sigma_e2=fixed_sigma_e2,
        horizons=horizons,
        n_classes=int(params.get("n_income_classes", 10)),
        random_seed=int(params.get("random_seed", 17)),
    )
    if measurement_error_grid:
        return replace(
            fit,
            measurement_error_grid=tuple(float(item) for item in measurement_error_grid),
            warnings=tuple(
                list(fit.warnings)
                + ["Measurement-error variance was selected from a fixed sensitivity grid"]
            ),
        )
    return fit


def _fit_with_measurement_error_strategy(
    panel: _LatentPanel,
    params: Mapping[str, Any],
    *,
    measurement_error_mode: str,
) -> LatentMobilityFit:
    if measurement_error_mode != "fixed_grid":
        return _fit_with_params(
            panel,
            params,
            measurement_error_mode=measurement_error_mode,
            fixed_sigma_e2=_fixed_measurement_variance(params),
        )

    grid = _measurement_grid_variances(panel, params)
    selector = str(params.get("select_k", "bic")).strip().lower()
    best: LatentMobilityFit | None = None
    best_score = math.inf
    for sigma_e2 in grid:
        fit = _fit_with_params(
            panel,
            params,
            measurement_error_mode="fixed_grid",
            fixed_sigma_e2=float(sigma_e2),
            measurement_error_grid=grid,
        )
        score = fit.icl if selector == "icl" else fit.bic
        if score < best_score:
            best = fit
            best_score = score
    if best is None:
        raise RuntimeError("measurement-error grid did not produce a candidate fit")
    return best


def _with_bootstrap_diagnostics(
    fit: LatentMobilityFit,
    *,
    reps: int,
    random_seed: int,
) -> LatentMobilityFit:
    if reps <= 0:
        return fit
    rng = np.random.default_rng(random_seed)
    class_shares = np.zeros((reps, fit.selected_k), dtype=float)
    row_marginals = np.zeros(
        (reps, fit.row_marginals.shape[0], fit.row_marginals.shape[1]), dtype=float
    )
    for rep in range(reps):
        draw = rng.integers(0, fit.n_entities, size=fit.n_entities)
        class_shares[rep] = np.mean(fit.posterior_probs[draw], axis=0)
        sampled_classes = fit.class_assignments[draw]
        for h_idx in range(fit.row_marginals.shape[0]):
            counts = np.bincount(
                sampled_classes.reshape(-1),
                minlength=fit.row_marginals.shape[1],
            ).astype(float)
            total = float(counts.sum())
            row_marginals[rep, h_idx] = (
                counts / total
                if total > _EPS
                else np.full(fit.row_marginals.shape[1], 1.0 / fit.row_marginals.shape[1])
            )
    robustness = dict(fit.robustness)
    robustness["posterior_bootstrap"] = {
        "reps": int(reps),
        "class_share_sd": np.std(class_shares, axis=0, ddof=0).tolist(),
        "row_marginal_sd": np.std(row_marginals, axis=0, ddof=0).tolist(),
    }
    return replace(fit, robustness=robustness)


def _latent_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec.for_output_contract(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("result", "json"),
                output_contract=EconometricResult,
            ),
            SlotSpec(
                name="latent_type_posteriors",
                slot_type=SlotType.MATRIX,
                unit=Unit("posterior_probability", "probability"),
                shape=("n_entities", "n_types"),
            ),
            SlotSpec(
                name="smoothed_state",
                slot_type=SlotType.MATRIX,
                unit=Unit("latent_state", "log_earnings"),
                shape=("n_entities", "n_periods"),
            ),
            SlotSpec(
                name="transition_tensor",
                slot_type=SlotType.TENSOR,
                unit=Unit("transition_probability", "probability"),
                shape=("n_horizons", "n_classes", "n_classes"),
            ),
            SlotSpec(
                name="mobility_report",
                slot_type=SlotType.SCALAR,
                unit=Unit("result", "json"),
                contract_id=MobilityReport.contract_id,
            ),
            SlotSpec(
                name="mobility_report_ref",
                slot_type=SlotType.SCALAR,
                unit=Unit("artifact_ref", "json"),
            ),
        }
    )


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={"econometrics", "panel-data", "mobility", "latent-heterogeneity", "estimation"},
)
class LatentMobilityEstimator:
    """Finite-mixture AR state-space estimator for long-horizon income mobility."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="latent_mobility",
        namespace="",
        version="0.0.0",
        input_slots=_explicit_panel_input_slots(),
        output_slots=_latent_output_slots(),
        parameters=(
            ParameterSpec(name="n_types", default=None),
            ParameterSpec(name="k_grid", default=(1, 2, 3)),
            ParameterSpec(name="profile_order", default=1),
            ParameterSpec(name="measurement_error", default="iid"),
            ParameterSpec(name="measurement_error_variance", default=None),
            ParameterSpec(name="measurement_error_variance_grid", default=None),
            ParameterSpec(name="sigma_e_grid", default=None),
            ParameterSpec(name="allow_type_switching", default=False),
            ParameterSpec(name="bootstrap_reps", default=0),
            ParameterSpec(name="n_starts", default=10),
            ParameterSpec(name="max_iter", default=150),
            ParameterSpec(name="tol", default=1e-5),
            ParameterSpec(name="min_class_share", default=0.03),
            ParameterSpec(name="rho_bound", default=0.995),
            ParameterSpec(name="var_floor", default=1e-6),
            ParameterSpec(name="select_k", default="bic"),
            ParameterSpec(name="horizons", default=(1, 5, 10)),
            ParameterSpec(name="n_income_classes", default=10),
            ParameterSpec(name="random_seed", default=17),
            ParameterSpec(name="report_horizon", default=5),
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
            "Finite-mixture dynamic panel mobility model separating persistent latent "
            "heterogeneity from within-type mean reversion."
        ),
        tags=frozenset(
            {
                "econometrics",
                "panel",
                "mobility",
                "latent-heterogeneity",
                "estimation",
            }
        ),
        citations=(
            "Heckman, J. (1981). Heterogeneity and state dependence.",
            "Heckman, J. and Singer, B. (1984). Nonparametric maximum likelihood.",
            "Guvenen, F. (2009). An empirical investigation of labor income processes.",
            "Bonhomme, S. and Robin, J. M. (2009). Assessing the equalizing force of mobility.",
            "Bonhomme, S., Lamadon, T. and Manresa, E. (2022). Discretizing unobserved heterogeneity.",
        ),
        equations={
            "observation": "y_it = x_it beta_k + alpha_k + b_k a(t) + p_it + e_it",
            "state": "p_it = rho_k p_i,t-1 + eta_it",
            "transition": "P_h = sum_k Pr(G_i=k | data) P_h,k",
        },
        assumptions={
            "latent_type": "G_i is constant over the panel horizon in the baseline.",
            "mean_reversion": "Within-type transitory earnings follow a stationary AR(1).",
            "measurement_error": "Measurement error is iid and separate from AR innovations.",
            "labeling": "Classes are ordered by fitted long-run mean earnings.",
        },
        when_to_use=(
            "Long-horizon earnings mobility panels where pooled persistence may mix "
            "mean reversion with persistent unobserved heterogeneity."
        ),
        when_not_to_use=(
            "Very short panels with fewer than four waves, repeated cross-sections, or "
            "nonignorable attrition that has not been handled upstream."
        ),
        typical_min_obs=500,
        output_interpretation=(
            "Class-specific rho estimates within-type mean reversion; class means and "
            "posterior weights capture persistent heterogeneity; transition_tensor gives "
            "h-step income-class mobility."
        ),
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        measurement_error_mode = str(params.get("measurement_error", "iid")).strip().lower()
        if measurement_error_mode not in {"iid", "known", "fixed", "fixed_grid"}:
            raise ValueError("measurement_error must be one of {'iid', 'known', 'fixed_grid'}")
        if bool(params.get("allow_type_switching", False)):
            raise ValueError(
                "allow_type_switching=True is reserved for the slow-switching HMM extension; "
                "the Phase 4 baseline uses constant latent types"
            )

        panel = _coerce_latent_panel(state, params)
        fit = _fit_with_measurement_error_strategy(
            panel,
            params,
            measurement_error_mode=measurement_error_mode,
        )
        fit = _with_bootstrap_diagnostics(
            fit,
            reps=int(params.get("bootstrap_reps", 0)),
            random_seed=int(params.get("random_seed", 17)) + 193,
        )
        result = _econometric_result_from_fit(fit, measurement_error_mode=measurement_error_mode)
        report_horizon = int(params.get("report_horizon", 5))
        if report_horizon not in fit.horizons:
            report_horizon = fit.horizons[0]
        report = build_latent_mobility_report(fit, horizon=report_horizon)

        artifact_store = resolve_artifact_store(state, params)
        report_ref = (
            persist_mobility_report(artifact_store, report) if artifact_store is not None else None
        )

        return {
            "result": result,
            "latent_type_posteriors": fit.posterior_probs,
            "smoothed_state": fit.smoothed_state,
            "transition_tensor": fit.transition_tensor,
            "within_type_transition_tensor": fit.within_type_transition_tensor,
            "row_marginals": fit.row_marginals,
            "class_edges": fit.class_edges,
            "class_assignments": fit.class_assignments,
            "robustness": fit.robustness,
            "horizons": np.asarray(fit.horizons, dtype=int),
            "mobility_report": report,
            "mobility_report_ref": None
            if report_ref is None
            else report_ref.model_dump(mode="json"),
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        return _materialize_panel_data(bound_inputs, fallback_state)


__all__ = [
    "LatentMobilityEstimator",
    "LatentMobilityFit",
    "build_h_step_transition_kernels",
    "build_latent_mobility_report",
    "fit_latent_mobility",
]
