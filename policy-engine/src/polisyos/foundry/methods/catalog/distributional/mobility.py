"""Public distributional mobility module API."""

from __future__ import annotations

from collections.abc import Mapping
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
from polisyos.foundry.methods.catalog._phase1_artifacts import resolve_artifact_store
from polisyos.ir.analytics.mobility import (
    MobilityAttrition,
    MobilityBalanceDiagnostics,
    MobilityBounds,
    MobilityDiagnostics,
    MobilityModelSpec,
    MobilityPointEstimate,
    MobilityPopulation,
    MobilityReport,
    MobilityUncertainty,
    persist_mobility_report,
)
from polisyos.ir.analytics.partial_identification import (
    build_mobility_bounds_bundle,
    persist_bounds_bundle,
)

_EPS = 1e-12


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="result",
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


def _values_payload(state: Any, *, key: str = "values") -> np.ndarray:
    if isinstance(state, Mapping):
        values = state.get(key)
    else:
        values = state
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if arr.size == 0:
        raise ValueError(f"{key} must not be empty")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _class_vector(
    state: Mapping[str, Any],
    key: str,
    *,
    allow_missing: bool = False,
) -> np.ndarray:
    values = np.asarray(state[key])
    if values.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if values.size == 0:
        raise ValueError(f"{key} must not be empty")
    if np.issubdtype(values.dtype, np.floating):
        if not allow_missing and np.any(~np.isfinite(values)):
            raise ValueError(f"{key} must contain only finite values")
        cleaned = np.where(np.isnan(values), -1, values)
        values = cleaned.astype(int)
    else:
        values = values.astype(int)
    return values


def _binary_vector(state: Mapping[str, Any], key: str, *, length: int) -> np.ndarray:
    values = np.asarray(state[key], dtype=int)
    if values.ndim != 1 or values.size != length:
        raise ValueError(f"{key} must be a 1D vector with length {length}")
    if np.any((values != 0) & (values != 1)):
        raise ValueError(f"{key} must contain only 0/1 values")
    return values


def _optional_weights(state: Mapping[str, Any], n_obs: int) -> np.ndarray:
    weights = state.get("sample_weights", state.get("weights"))
    if weights is None:
        return np.ones(n_obs, dtype=float)
    arr = np.asarray(weights, dtype=float)
    if arr.ndim != 1 or arr.size != n_obs:
        raise ValueError("sample_weights must be a 1D vector aligned with observations")
    if np.any(~np.isfinite(arr)) or np.any(arr < 0):
        raise ValueError("sample_weights must be finite and non-negative")
    if float(arr.sum()) <= 0.0:
        raise ValueError("sample_weights must sum to a positive value")
    return arr


def _feature_matrix(
    state: Mapping[str, Any],
    n_obs: int,
    *,
    fallback: np.ndarray | None = None,
) -> np.ndarray:
    for key in ("attrition_features", "features", "covariates", "baseline_features"):
        if key not in state:
            continue
        arr = np.asarray(state[key], dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1)
        if arr.ndim != 2 or arr.shape[0] != n_obs:
            raise ValueError(f"{key} must be a matrix with shape (n_obs, n_features)")
        if np.any(~np.isfinite(arr)):
            raise ValueError(f"{key} must contain only finite values")
        return arr
    if fallback is None:
        raise ValueError("attrition_features or equivalent covariate matrix is required")
    arr = np.asarray(fallback, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.shape[0] != n_obs:
        raise ValueError("fallback feature matrix must align with observations")
    return arr


def _normalize_weights(weights: np.ndarray, mask: np.ndarray) -> np.ndarray:
    normalized = np.asarray(weights, dtype=float).copy()
    normalized[~mask] = 0.0
    total = float(normalized.sum())
    if total <= 0.0:
        raise ValueError("weights on the valid support must sum to a positive value")
    normalized /= total
    return normalized


def _resolve_feature_names(
    state: Mapping[str, Any],
    n_features: int,
    *,
    include_origin: bool,
    n_classes: int,
) -> list[str]:
    raw = state.get("feature_names")
    if isinstance(raw, (list, tuple)) and len(raw) == n_features:
        names = [str(item) for item in raw]
    else:
        names = [f"x_{index}" for index in range(n_features)]
    if include_origin:
        names.extend(f"origin_class_{index}" for index in range(1, n_classes))
    return names


def _augment_features_with_origin(
    features: np.ndarray,
    origin: np.ndarray,
    n_classes: int,
    *,
    include_origin: bool = True,
) -> np.ndarray:
    if not include_origin or n_classes <= 1:
        return features
    one_hot = np.zeros((origin.size, n_classes - 1), dtype=float)
    for cls in range(1, n_classes):
        one_hot[:, cls - 1] = (origin == cls).astype(float)
    return np.concatenate((features, one_hot), axis=1)


def _weighted_joint_matrix(
    origin: np.ndarray,
    destination: np.ndarray,
    *,
    n_classes: int,
    weights: np.ndarray,
    mask: np.ndarray | None = None,
) -> np.ndarray:
    joint = np.zeros((n_classes, n_classes), dtype=float)
    active = np.ones(origin.size, dtype=bool) if mask is None else np.asarray(mask, dtype=bool)
    for row, col, weight, keep in zip(origin, destination, weights, active):
        if not keep:
            continue
        if 0 <= row < n_classes and 0 <= col < n_classes:
            joint[row, col] += float(weight)
    return joint


def _weighted_row_marginals(
    origin: np.ndarray,
    *,
    n_classes: int,
    weights: np.ndarray,
    mask: np.ndarray | None = None,
) -> np.ndarray:
    rows = np.zeros(n_classes, dtype=float)
    active = np.ones(origin.size, dtype=bool) if mask is None else np.asarray(mask, dtype=bool)
    for row, weight, keep in zip(origin, weights, active):
        if keep and 0 <= row < n_classes:
            rows[row] += float(weight)
    return rows


def _row_normalize(joint: np.ndarray, row_marginals: np.ndarray | None = None) -> np.ndarray:
    row_totals = (
        joint.sum(axis=1) if row_marginals is None else np.asarray(row_marginals, dtype=float)
    )
    transition = np.zeros_like(joint)
    for row in range(joint.shape[0]):
        denom = float(row_totals[row])
        if denom > _EPS:
            transition[row] = joint[row] / denom
    return transition


def _mobility_stats(joint: np.ndarray, row_marginals: np.ndarray) -> dict[str, float]:
    upward = float(np.sum(np.triu(joint, k=1)))
    downward = float(np.sum(np.tril(joint, k=-1)))
    immobility = float(np.trace(joint))
    stats = {
        "upward_rate": upward,
        "downward_rate": downward,
        "immobility_rate": immobility,
    }
    if joint.shape[0] == joint.shape[1] and joint.shape[0] > 1:
        safe_rows = np.clip(row_marginals, _EPS, None)
        persistence = float(np.sum(np.diag(joint) / safe_rows))
        stats["shorrocks_index"] = float(
            max(0.0, min(1.0, (joint.shape[0] - persistence) / (joint.shape[0] - 1.0)))
        )
    return stats


def _legacy_summary_metrics(
    transition_matrix: np.ndarray,
    mobility_stats: Mapping[str, float],
    *,
    n_classes: int,
    n_obs: int,
) -> dict[str, Any]:
    return {
        "transition_matrix": transition_matrix.tolist(),
        "upward_mobility_rate": float(mobility_stats.get("upward_rate", 0.0)),
        "downward_mobility_rate": float(mobility_stats.get("downward_rate", 0.0)),
        "immobility_rate": float(mobility_stats.get("immobility_rate", 0.0)),
        "n_classes": int(n_classes),
        "n_obs": int(n_obs),
    }


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _add_intercept(features: np.ndarray) -> np.ndarray:
    return np.concatenate((np.ones((features.shape[0], 1), dtype=float), features), axis=1)


def _fit_weighted_logistic_probabilities(
    features: np.ndarray,
    outcomes: np.ndarray,
    sample_weight: np.ndarray,
    *,
    ridge: float = 1e-6,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> np.ndarray:
    y = np.asarray(outcomes, dtype=float)
    w = np.asarray(sample_weight, dtype=float)
    if y.ndim != 1 or y.size != features.shape[0]:
        raise ValueError("outcomes must align with features")
    if np.unique(y).size < 2:
        mean = float(np.average(y, weights=np.clip(w, 0.0, None)))
        return np.full(y.size, np.clip(mean, 1e-6, 1.0 - 1e-6), dtype=float)

    design = _add_intercept(features)
    beta = np.zeros(design.shape[1], dtype=float)
    identity = np.eye(design.shape[1], dtype=float)
    for _ in range(max_iter):
        eta = design @ beta
        probs = np.clip(_sigmoid(eta), 1e-6, 1.0 - 1e-6)
        variance = probs * (1.0 - probs)
        working_weight = np.clip(w * variance, 1e-10, None)
        pseudo = eta + (y - probs) / np.clip(variance, 1e-10, None)
        xtwx = design.T @ (working_weight[:, None] * design) + ridge * identity
        xtwz = design.T @ (working_weight * pseudo)
        beta_new = np.linalg.solve(xtwx, xtwz)
        if np.max(np.abs(beta_new - beta)) < tol:
            beta = beta_new
            break
        beta = beta_new
    return np.clip(_sigmoid(design @ beta), 1e-6, 1.0 - 1e-6)


def _predict_weighted_linear_probability(
    x_train: np.ndarray,
    y_train: np.ndarray,
    sample_weight: np.ndarray,
    x_pred: np.ndarray,
    *,
    ridge: float = 1e-6,
) -> np.ndarray:
    if x_train.shape[0] == 0:
        return np.zeros(x_pred.shape[0], dtype=float)
    design_train = _add_intercept(x_train)
    design_pred = _add_intercept(x_pred)
    w = np.asarray(sample_weight, dtype=float)
    if float(w.sum()) <= 0.0:
        mean = float(np.mean(y_train))
        return np.full(x_pred.shape[0], np.clip(mean, 0.0, 1.0), dtype=float)
    xtwx = design_train.T @ (w[:, None] * design_train) + ridge * np.eye(design_train.shape[1])
    xtwy = design_train.T @ (w * y_train)
    beta = np.linalg.solve(xtwx, xtwy)
    return np.clip(design_pred @ beta, 0.0, 1.0)


def _weighted_mean(features: np.ndarray, weights: np.ndarray) -> np.ndarray:
    total = float(weights.sum())
    if total <= 0.0:
        return np.zeros(features.shape[1], dtype=float)
    return (weights[:, None] * features).sum(axis=0) / total


def _weighted_var(features: np.ndarray, weights: np.ndarray, mean: np.ndarray) -> np.ndarray:
    total = float(weights.sum())
    if total <= 0.0:
        return np.zeros(features.shape[1], dtype=float)
    centered = features - mean
    return (weights[:, None] * (centered**2)).sum(axis=0) / total


def _max_abs_smd(
    reference_features: np.ndarray, reference_weights: np.ndarray, other_weights: np.ndarray
) -> float | None:
    if reference_features.size == 0:
        return None
    ref_mean = _weighted_mean(reference_features, reference_weights)
    other_mean = _weighted_mean(reference_features, other_weights)
    ref_var = _weighted_var(reference_features, reference_weights, ref_mean)
    other_var = _weighted_var(reference_features, other_weights, other_mean)
    pooled = np.sqrt(np.clip(0.5 * (ref_var + other_var), _EPS, None))
    smd = np.abs(ref_mean - other_mean) / pooled
    return float(np.max(smd)) if smd.size else None


def _effective_sample_size(weights: np.ndarray) -> float | None:
    active = np.asarray(weights, dtype=float)
    total = float(active.sum())
    if total <= 0.0:
        return None
    denom = float(np.sum(active**2))
    if denom <= 0.0:
        return None
    return float((total**2) / denom)


def _clip_probabilities(probabilities: np.ndarray, floor: float) -> np.ndarray:
    clipped_floor = min(max(float(floor), 1e-6), 0.49)
    return np.clip(np.asarray(probabilities, dtype=float), clipped_floor, 1.0 - clipped_floor)


def _cell_bounds_payload(lower: np.ndarray, upper: np.ndarray) -> dict[str, tuple[float, float]]:
    payload: dict[str, tuple[float, float]] = {}
    for row in range(lower.shape[0]):
        for col in range(lower.shape[1]):
            payload[f"{row},{col}"] = (float(lower[row, col]), float(upper[row, col]))
    return payload


def _retention_matrix(state: Mapping[str, Any], key: str, *, n_obs: int) -> np.ndarray:
    values = np.asarray(state[key], dtype=int)
    if values.ndim != 2 or values.shape[0] != n_obs:
        raise ValueError(f"{key} must be a 2D matrix with shape (n_obs, n_waves)")
    if np.any((values != 0) & (values != 1)):
        raise ValueError(f"{key} must contain only 0/1 values")
    return values


def _feature_tensor_by_wave(
    state: Mapping[str, Any],
    *,
    n_obs: int,
    n_waves: int,
    fallback_features: np.ndarray,
) -> np.ndarray:
    if "attrition_features_by_wave" in state:
        tensor = np.asarray(state["attrition_features_by_wave"], dtype=float)
        if tensor.ndim != 3 or tensor.shape[0] != n_obs or tensor.shape[1] != n_waves:
            raise ValueError(
                "attrition_features_by_wave must have shape (n_obs, n_waves, n_features)"
            )
        if np.any(~np.isfinite(tensor)):
            raise ValueError("attrition_features_by_wave must contain only finite values")
        return tensor
    repeated = np.repeat(fallback_features[:, None, :], n_waves, axis=1)
    return repeated


def _fit_sequential_retention_probabilities(
    *,
    retention_matrix: np.ndarray,
    features_by_wave: np.ndarray,
    valid_origin_mask: np.ndarray,
    base_weights: np.ndarray,
    positivity_floor: float,
    provided_probabilities_by_wave: np.ndarray | None = None,
) -> tuple[np.ndarray, list[float]]:
    n_obs, n_waves = retention_matrix.shape
    clipped = np.ones((n_obs, n_waves), dtype=float)
    observed_retention_rates: list[float] = []

    if provided_probabilities_by_wave is not None:
        provided = np.asarray(provided_probabilities_by_wave, dtype=float)
        if provided.shape != (n_obs, n_waves):
            raise ValueError("retention_probabilities_by_wave must have shape (n_obs, n_waves)")
        if np.any(~np.isfinite(provided)) or np.any(provided <= 0.0):
            raise ValueError("retention_probabilities_by_wave must be finite and strictly positive")
        return _clip_probabilities(provided, positivity_floor), [
            float(np.sum(base_weights[valid_origin_mask & (retention_matrix[:, wave] == 1)]))
            for wave in range(n_waves)
        ]

    at_risk = valid_origin_mask.copy()
    for wave in range(n_waves):
        risk_weights = np.where(at_risk, base_weights, 0.0)
        if np.sum(at_risk) == 0:
            observed_retention_rates.append(1.0)
            continue
        clipped[at_risk, wave] = _fit_weighted_logistic_probabilities(
            features_by_wave[at_risk, wave, :],
            retention_matrix[at_risk, wave].astype(float),
            risk_weights[at_risk],
        )
        observed_retention_rates.append(
            float(np.sum(base_weights[at_risk & (retention_matrix[:, wave] == 1)]))
            / max(float(np.sum(base_weights[at_risk])), _EPS)
        )
        at_risk = at_risk & (retention_matrix[:, wave] == 1)
    return _clip_probabilities(clipped, positivity_floor), observed_retention_rates


def _independent_residual_completion(
    observed_joint: np.ndarray,
    row_marginals: np.ndarray,
    column_marginals: np.ndarray,
) -> np.ndarray:
    lower = np.asarray(observed_joint, dtype=float)
    rows = np.asarray(row_marginals, dtype=float)
    cols = np.asarray(column_marginals, dtype=float)
    residual_rows = rows - lower.sum(axis=1)
    residual_cols = cols - lower.sum(axis=0)
    total_residual = float(residual_rows.sum())
    if total_residual < -1e-9:
        raise ValueError("observed_joint exceeds supplied marginals")
    if total_residual <= _EPS:
        return lower.copy()
    if np.any(residual_rows < -1e-9) or np.any(residual_cols < -1e-9):
        raise ValueError("observed_joint exceeds row or column marginals")
    residual = np.outer(np.clip(residual_rows, 0.0, None), np.clip(residual_cols, 0.0, None))
    residual /= max(float(residual.sum()), _EPS)
    residual *= total_residual
    return lower + residual


def _column_marginals_from_refreshment(
    state: Mapping[str, Any],
    *,
    n_classes: int,
) -> np.ndarray:
    supplied = state.get("destination_marginals")
    if supplied is not None:
        col_marginals = np.asarray(supplied, dtype=float)
        if col_marginals.ndim != 1 or col_marginals.size != n_classes:
            raise ValueError("destination_marginals must be a 1D vector of length n_classes")
        if np.any(~np.isfinite(col_marginals)) or np.any(col_marginals < 0.0):
            raise ValueError("destination_marginals must be finite and non-negative")
        total = float(col_marginals.sum())
        if total <= 0.0:
            raise ValueError("destination_marginals must sum to a positive value")
        return col_marginals / total

    refreshment_destinations = state.get("refreshment_destination_classes")
    if refreshment_destinations is None:
        raise ValueError(
            "destination_marginals or refreshment_destination_classes is required for refreshment mode"
        )
    refreshment = np.asarray(refreshment_destinations, dtype=int)
    if refreshment.ndim != 1 or refreshment.size == 0:
        raise ValueError("refreshment_destination_classes must be a non-empty 1D vector")
    weights = state.get("refreshment_weights")
    if weights is None:
        refreshment_weights = np.ones(refreshment.size, dtype=float)
    else:
        refreshment_weights = np.asarray(weights, dtype=float)
        if refreshment_weights.ndim != 1 or refreshment_weights.size != refreshment.size:
            raise ValueError("refreshment_weights must align with refreshment_destination_classes")
        if np.any(~np.isfinite(refreshment_weights)) or np.any(refreshment_weights < 0.0):
            raise ValueError("refreshment_weights must be finite and non-negative")
    valid = (refreshment >= 0) & (refreshment < n_classes)
    if not np.any(valid):
        raise ValueError("refreshment sample must contain at least one valid destination class")
    normalized = _normalize_weights(refreshment_weights, valid)
    col_marginals = np.zeros(n_classes, dtype=float)
    for cls, weight, keep in zip(refreshment, normalized, valid):
        if keep:
            col_marginals[int(cls)] += float(weight)
    return col_marginals


def _refreshment_column_counts(
    state: Mapping[str, Any],
    *,
    n_classes: int,
    fallback_total: float,
) -> np.ndarray:
    supplied = state.get("destination_marginals")
    if supplied is not None:
        marginals = _column_marginals_from_refreshment(state, n_classes=n_classes)
        return marginals * max(float(fallback_total), 1.0)

    refreshment_destinations = state.get("refreshment_destination_classes")
    if refreshment_destinations is None:
        raise ValueError(
            "destination_marginals or refreshment_destination_classes is required for refreshment mode"
        )
    refreshment = np.asarray(refreshment_destinations, dtype=int)
    if refreshment.ndim != 1 or refreshment.size == 0:
        raise ValueError("refreshment_destination_classes must be a non-empty 1D vector")
    weights = state.get("refreshment_weights")
    if weights is None:
        refreshment_weights = np.ones(refreshment.size, dtype=float)
    else:
        refreshment_weights = np.asarray(weights, dtype=float)
        if refreshment_weights.ndim != 1 or refreshment_weights.size != refreshment.size:
            raise ValueError("refreshment_weights must align with refreshment_destination_classes")
        if np.any(~np.isfinite(refreshment_weights)) or np.any(refreshment_weights < 0.0):
            raise ValueError("refreshment_weights must be finite and non-negative")
    valid = (refreshment >= 0) & (refreshment < n_classes)
    if not np.any(valid):
        raise ValueError("refreshment sample must contain at least one valid destination class")
    counts = np.zeros(n_classes, dtype=float)
    for cls, weight, keep in zip(refreshment, refreshment_weights, valid):
        if keep:
            counts[int(cls)] += float(weight)
    return counts


def _fit_refreshment_additive_nonignorable_joint(
    observed_joint: np.ndarray,
    row_totals: np.ndarray,
    column_totals: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    observed_joint = np.asarray(observed_joint, dtype=float)
    row_totals = np.asarray(row_totals, dtype=float)
    column_totals = np.asarray(column_totals, dtype=float)
    if observed_joint.ndim != 2:
        raise ValueError("observed_joint must be a matrix")
    if row_totals.ndim != 1 or row_totals.size != observed_joint.shape[0]:
        raise ValueError("row_totals must align with observed_joint rows")
    if column_totals.ndim != 1 or column_totals.size != observed_joint.shape[1]:
        raise ValueError("column_totals must align with observed_joint columns")
    if np.any(~np.isfinite(observed_joint)) or np.any(observed_joint < 0.0):
        raise ValueError("observed_joint must be finite and non-negative")
    if np.any(~np.isfinite(row_totals)) or np.any(row_totals < 0.0):
        raise ValueError("row_totals must be finite and non-negative")
    if np.any(~np.isfinite(column_totals)) or np.any(column_totals < 0.0):
        raise ValueError("column_totals must be finite and non-negative")

    row_total_mass = float(row_totals.sum())
    col_total_mass = float(column_totals.sum())
    if row_total_mass <= 0.0 or col_total_mass <= 0.0:
        raise ValueError("row_totals and column_totals must sum to a positive value")

    row_probs = row_totals / row_total_mass
    col_probs = column_totals / col_total_mass
    observed_probs = observed_joint / row_total_mass
    attrition_by_origin = np.clip(row_totals - observed_joint.sum(axis=1), 0.0, None)

    fallback_joint = _independent_residual_completion(
        observed_probs,
        row_probs,
        col_probs,
    )

    try:
        from scipy.optimize import minimize
        from scipy.special import expit, logsumexp
    except ModuleNotFoundError:
        return fallback_joint, {
            "family": "independent_residual_transport_completion",
            "optimizer_success": False,
            "fallback_used": True,
            "reason": "scipy_unavailable",
        }

    n_rows, n_cols = observed_joint.shape

    def _unpack(params: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        gamma = params[: n_rows * n_cols].reshape(n_rows, n_cols)
        alpha = params[n_rows * n_cols : n_rows * n_cols + n_rows]
        beta = np.zeros(n_cols, dtype=float)
        beta[1:] = params[n_rows * n_cols + n_rows :]
        joint = np.exp(gamma - logsumexp(gamma))
        retention = expit(alpha[:, None] + beta[None, :])
        retention = np.clip(retention, 1e-6, 1.0 - 1e-6)
        return joint, retention

    def _objective(params: np.ndarray) -> float:
        joint, retention = _unpack(params)
        stayer = np.clip(joint * retention, _EPS, None)
        attriter_origin = np.clip((joint * (1.0 - retention)).sum(axis=1), _EPS, None)
        destination = np.clip(joint.sum(axis=0), _EPS, None)

        loss = -float(np.sum(observed_joint * np.log(stayer)))
        loss -= float(np.sum(attrition_by_origin * np.log(attriter_origin)))
        loss -= float(np.sum(column_totals * np.log(destination)))
        structural_params = params[n_rows * n_cols :]
        loss += 1e-6 * float(structural_params @ structural_params)
        return loss

    x0 = np.concatenate(
        [
            np.log(np.clip(fallback_joint, 1e-6, None)).ravel(),
            np.zeros(n_rows, dtype=float),
            np.zeros(max(n_cols - 1, 0), dtype=float),
        ]
    )
    result = minimize(
        _objective,
        x0,
        method="L-BFGS-B",
        options={"maxiter": 2000},
    )
    if (not result.success) or np.any(~np.isfinite(result.x)):
        return fallback_joint, {
            "family": "independent_residual_transport_completion",
            "optimizer_success": False,
            "fallback_used": True,
            "reason": str(result.message),
        }

    fitted_joint, fitted_retention = _unpack(np.asarray(result.x, dtype=float))
    return fitted_joint, {
        "family": "additive_nonignorable_logit_refreshment",
        "optimizer_success": True,
        "fallback_used": False,
        "optimizer_message": str(result.message),
        "selection_surface": fitted_retention.tolist(),
    }


def _build_complete_case_report(
    *,
    analysis_type: str,
    status: str,
    n_classes: int,
    n_obs: int,
    transition_matrix: np.ndarray,
    joint_matrix: np.ndarray,
    row_marginals: np.ndarray,
    col_marginals: np.ndarray,
    mobility_stats: Mapping[str, float],
    metadata: dict[str, Any] | None = None,
) -> MobilityReport:
    return MobilityReport(
        analysis_type=analysis_type,
        estimand_id=f"mobility.{analysis_type}",
        status=status,
        population=MobilityPopulation(
            target_population="paired complete cases",
            panel_length=2,
            waves_used=[1, 2],
            class_definition={"type": "preclassified", "n_classes": n_classes},
        ),
        attrition=MobilityAttrition(
            mechanism_assumed="complete_case_pairwise_observation",
        ),
        point_estimate=MobilityPointEstimate(
            joint_matrix=joint_matrix.tolist(),
            transition_matrix=transition_matrix.tolist(),
            row_marginals=row_marginals.tolist(),
            col_marginals=col_marginals.tolist(),
            mobility_stats=dict(mobility_stats),
        ),
        uncertainty=MobilityUncertainty(method="not_estimated"),
        diagnostics=MobilityDiagnostics(observed_full_cases=n_obs),
        summary_metrics=_legacy_summary_metrics(
            transition_matrix,
            mobility_stats,
            n_classes=n_classes,
            n_obs=n_obs,
        ),
        metadata=dict(metadata or {}),
    )


@foundry_method(
    namespace="distributional.mobility",
    version="1.0.0",
    tags={"distributional", "mobility", "transition", "cross-section"},
)
class MobilityMatrixEstimator:
    """Estimate transition matrices that summarize movement across income ranks."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="transition_matrix",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "origin_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "destination_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="n_classes", default=5),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Transition probability matrix from paired origin/destination class data.",
        tags=frozenset({"distributional", "mobility", "transition", "cross-section"}),
        when_to_use="Social mobility analysis; estimating probability of moving between income or occupational classes across generations or time",
        output_interpretation="Row i, column j = probability of moving from class i to class j. High diagonal = low mobility.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("state must provide origin_classes and destination_classes")
        origin = _class_vector(state, "origin_classes")
        destination = _class_vector(state, "destination_classes")
        if origin.shape[0] != destination.shape[0]:
            raise ValueError("origin_classes and destination_classes must have same length")

        n_classes = int(params.get("n_classes", 5))
        valid_mask = (
            (origin >= 0) & (origin < n_classes) & (destination >= 0) & (destination < n_classes)
        )
        n_valid = int(valid_mask.sum())
        if n_valid == 0:
            raise ValueError("at least one valid origin/destination pair is required")

        weights = _normalize_weights(np.ones(origin.size, dtype=float), valid_mask)
        joint_matrix = _weighted_joint_matrix(
            origin,
            destination,
            n_classes=n_classes,
            weights=weights,
            mask=valid_mask,
        )
        row_marginals = joint_matrix.sum(axis=1)
        transition_matrix = _row_normalize(joint_matrix, row_marginals)
        col_marginals = joint_matrix.sum(axis=0)
        mobility_stats = _mobility_stats(joint_matrix, row_marginals)

        artifact_store = resolve_artifact_store(state, params)
        report = _build_complete_case_report(
            analysis_type="transition_matrix",
            status="ok",
            n_classes=n_classes,
            n_obs=n_valid,
            transition_matrix=transition_matrix,
            joint_matrix=joint_matrix,
            row_marginals=row_marginals,
            col_marginals=col_marginals,
            mobility_stats=mobility_stats,
            metadata={"valid_observations": n_valid},
        )
        report_ref = (
            persist_mobility_report(artifact_store, report) if artifact_store is not None else None
        )
        return {
            "result": report,
            "mobility_report_ref": None
            if report_ref is None
            else report_ref.model_dump(mode="json"),
        }


@foundry_method(
    namespace="distributional.mobility",
    version="1.0.0",
    tags={"distributional", "mobility", "attrition", "panel", "ipcw", "aipw"},
)
class AttritionAdjustedMobilityMatrixEstimator:
    """Estimate mobility matrices under panel attrition using IPCW or AIPW."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="transition_matrix_attrition_adjusted",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "origin_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "destination_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "retention_indicators",
                    SlotType.VECTOR,
                    Unit("indicator", "binary"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "attrition_features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_features"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_classes", default=5),
            ParameterSpec(name="estimator", default="aipw"),
            ParameterSpec(name="positivity_floor", default=0.05),
            ParameterSpec(name="compute_bounds", default=True),
            ParameterSpec(name="include_origin_in_retention_model", default=True),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Attrition-aware mobility matrix using IPCW/AIPW under MAR-style assumptions.",
        tags=frozenset({"distributional", "mobility", "attrition", "panel", "ipcw", "aipw"}),
        when_to_use="Panel mobility analysis when destination classes are missing due to panel attrition and retention can be modeled from observed covariates/history.",
        output_interpretation="Returns a Phase 2 mobility report with point estimates, diagnostics, and optional transport-style bounds fallback.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError(
                "state must provide origin_classes, destination_classes, retention_indicators, and attrition_features"
            )
        origin = _class_vector(state, "origin_classes")
        destination = _class_vector(state, "destination_classes", allow_missing=True)
        if destination.shape[0] != origin.shape[0]:
            raise ValueError("destination_classes must align with origin_classes")
        retained = _binary_vector(state, "retention_indicators", length=origin.shape[0])

        n_obs = origin.shape[0]
        n_classes = int(params.get("n_classes", 5))
        estimator = str(params.get("estimator", "aipw")).strip().lower()
        if estimator not in {"ipcw", "aipw"}:
            raise ValueError("estimator must be one of {'ipcw', 'aipw'}")
        positivity_floor = float(params.get("positivity_floor", 0.05))
        include_origin = bool(params.get("include_origin_in_retention_model", True))
        raw_features = _feature_matrix(state, n_obs, fallback=origin.reshape(-1, 1))
        feature_names = _resolve_feature_names(
            state,
            raw_features.shape[1],
            include_origin=include_origin,
            n_classes=n_classes,
        )
        retention_features = _augment_features_with_origin(
            raw_features,
            origin,
            n_classes,
            include_origin=include_origin,
        )
        base_weights = _optional_weights(state, n_obs)

        valid_origin_mask = (origin >= 0) & (origin < n_classes)
        if not np.any(valid_origin_mask):
            raise ValueError("origin_classes must contain at least one valid class index")
        normalized_weights = _normalize_weights(base_weights, valid_origin_mask)
        observed_mask = (
            valid_origin_mask & (retained == 1) & (destination >= 0) & (destination < n_classes)
        )

        row_marginals = _weighted_row_marginals(
            origin,
            n_classes=n_classes,
            weights=normalized_weights,
            mask=valid_origin_mask,
        )
        observed_joint = _weighted_joint_matrix(
            origin,
            destination,
            n_classes=n_classes,
            weights=normalized_weights,
            mask=observed_mask,
        )

        provided_retention = state.get("retention_probabilities")
        if provided_retention is not None:
            retention_probabilities = np.asarray(provided_retention, dtype=float)
            if retention_probabilities.ndim != 1 or retention_probabilities.size != n_obs:
                raise ValueError("retention_probabilities must align with observations")
            if np.any(~np.isfinite(retention_probabilities)) or np.any(
                retention_probabilities <= 0
            ):
                raise ValueError("retention_probabilities must be finite and strictly positive")
            retention_model = MobilityModelSpec(
                family="provided_probabilities",
                features=[],
                metadata={"source": "state.retention_probabilities"},
            )
        else:
            retention_probabilities = np.ones(n_obs, dtype=float)
            retention_probabilities[valid_origin_mask] = _fit_weighted_logistic_probabilities(
                retention_features[valid_origin_mask],
                retained[valid_origin_mask].astype(float),
                normalized_weights[valid_origin_mask],
            )
            retention_model = MobilityModelSpec(
                family="weighted_logit",
                features=feature_names,
            )
        retention_probabilities = _clip_probabilities(retention_probabilities, positivity_floor)

        adjusted_weights = np.zeros(n_obs, dtype=float)
        adjusted_weights[observed_mask] = (
            normalized_weights[observed_mask] / retention_probabilities[observed_mask]
        )

        transition_matrix = np.zeros((n_classes, n_classes), dtype=float)
        outcome_model: MobilityModelSpec | None = None
        for row in range(n_classes):
            row_mask = valid_origin_mask & (origin == row)
            row_total = float(row_marginals[row])
            if row_total <= _EPS:
                continue
            if estimator == "ipcw":
                row_joint = _weighted_joint_matrix(
                    origin[row_mask],
                    destination[row_mask],
                    n_classes=n_classes,
                    weights=adjusted_weights[row_mask],
                    mask=observed_mask[row_mask],
                )
                row_probs = row_joint[row] / max(float(row_joint[row].sum()), _EPS)
            else:
                x_row = raw_features[row_mask]
                observed_row_mask = observed_mask[row_mask]
                row_probs = np.zeros(n_classes, dtype=float)
                for col in range(n_classes):
                    y_train = (destination[row_mask][observed_row_mask] == col).astype(float)
                    if observed_row_mask.sum() == 0:
                        mu_hat = np.full(x_row.shape[0], 1.0 / n_classes, dtype=float)
                    else:
                        mu_hat = _predict_weighted_linear_probability(
                            x_row[observed_row_mask],
                            y_train,
                            normalized_weights[row_mask][observed_row_mask],
                            x_row,
                        )
                    y_full = ((destination[row_mask] == col) & observed_row_mask).astype(float)
                    contribution = mu_hat + (
                        observed_row_mask.astype(float) / retention_probabilities[row_mask]
                    ) * (y_full - mu_hat)
                    row_probs[col] = float(
                        np.sum(normalized_weights[row_mask] * contribution) / row_total
                    )
                row_probs = np.clip(row_probs, 0.0, None)
                outcome_model = MobilityModelSpec(
                    family="weighted_linear_probability",
                    features=feature_names[: raw_features.shape[1]],
                )
            row_sum = float(row_probs.sum())
            if row_sum <= _EPS:
                row_probs = np.full(n_classes, 1.0 / n_classes, dtype=float)
            else:
                row_probs = row_probs / row_sum
            transition_matrix[row] = row_probs

        joint_matrix = row_marginals[:, None] * transition_matrix
        col_marginals = joint_matrix.sum(axis=0)
        mobility_stats = _mobility_stats(joint_matrix, row_marginals)

        reference_weights = normalized_weights[valid_origin_mask]
        reference_features = raw_features[valid_origin_mask]
        before_weights = np.zeros(n_obs, dtype=float)
        before_weights[observed_mask] = normalized_weights[observed_mask]
        before_smd = _max_abs_smd(
            reference_features, reference_weights, before_weights[valid_origin_mask]
        )
        after_smd = _max_abs_smd(
            reference_features, reference_weights, adjusted_weights[valid_origin_mask]
        )

        positive_weights = adjusted_weights[adjusted_weights > 0.0]
        warnings: list[str] = []
        if positive_weights.size and float(np.max(positive_weights)) > 10.0:
            warnings.append("large_ipcw_weights")
        if (
            float(np.min(retention_probabilities[valid_origin_mask]))
            <= min(max(positivity_floor, 1e-6), 0.49) + 1e-9
        ):
            warnings.append("positivity_floor_active")
        invalid_observed = int(np.sum((retained == 1) & ~observed_mask & valid_origin_mask))
        if invalid_observed > 0:
            warnings.append("retained_records_missing_destination_class")

        bounds_bundle = None
        bounds_ref = None
        bounds_payload = MobilityBounds()
        if bool(params.get("compute_bounds", True)):
            destination_marginals = state.get("destination_marginals")
            normalized_destination_marginals = None
            if destination_marginals is not None:
                normalized_destination_marginals = np.asarray(destination_marginals, dtype=float)
                if (
                    normalized_destination_marginals.ndim != 1
                    or normalized_destination_marginals.size != n_classes
                ):
                    raise ValueError(
                        "destination_marginals must be a 1D vector of length n_classes"
                    )
                if np.any(~np.isfinite(normalized_destination_marginals)) or np.any(
                    normalized_destination_marginals < 0
                ):
                    raise ValueError("destination_marginals must be finite and non-negative")
                total_dest = float(normalized_destination_marginals.sum())
                if total_dest <= 0.0:
                    raise ValueError("destination_marginals must sum to a positive value")
                normalized_destination_marginals = normalized_destination_marginals / total_dest

            bounds_bundle, cell_lower, cell_upper, summary_bounds = build_mobility_bounds_bundle(
                observed_joint,
                row_marginals,
                column_marginals=normalized_destination_marginals,
                headline_metric="upward_rate",
                metadata={
                    "analysis_type": "transition_matrix_attrition_adjusted",
                    "estimator": estimator,
                },
            )
            artifact_store = resolve_artifact_store(state, params)
            if artifact_store is not None:
                bounds_ref = persist_bounds_bundle(artifact_store, bounds_bundle)
            bounds_payload = MobilityBounds(
                bundle_ref=bounds_ref,
                cell_bounds=_cell_bounds_payload(cell_lower, cell_upper),
                summary_bounds={
                    key: tuple(map(float, value)) for key, value in summary_bounds.items()
                },
                sharpness_status=(
                    "sharp_with_known_marginals"
                    if normalized_destination_marginals is not None
                    else "sharp_with_row_marginals"
                ),
                method=str(bounds_bundle.metadata.get("bounds_method", "transport_bounds")),
            )
        else:
            artifact_store = resolve_artifact_store(state, params)

        diagnostics = MobilityDiagnostics(
            effective_sample_size=_effective_sample_size(positive_weights),
            max_weight=(float(np.max(positive_weights)) if positive_weights.size else None),
            p99_weight=(
                float(np.quantile(positive_weights, 0.99)) if positive_weights.size else None
            ),
            min_retention_probability=float(np.min(retention_probabilities[valid_origin_mask])),
            max_retention_probability=float(np.max(retention_probabilities[valid_origin_mask])),
            observed_retention_rate=float(np.sum(normalized_weights[retained == 1])),
            observed_full_cases=int(observed_mask.sum()),
            balance=MobilityBalanceDiagnostics(
                max_abs_smd_before=before_smd,
                max_abs_smd_after=after_smd,
            ),
            warnings=warnings,
        )

        report_status = "warn" if warnings else "ok"
        upstream_refs: list[str] = []
        if bounds_ref is not None:
            upstream_refs.append(f"artifact://{bounds_ref.artifact_id}")
        report = MobilityReport(
            analysis_type="transition_matrix_attrition_adjusted",
            estimand_id="mobility.transition_matrix.attrition_adjusted",
            status=report_status,
            population=MobilityPopulation(
                target_population="panel baseline cohort",
                weights_design="sample_weights"
                if "sample_weights" in state or "weights" in state
                else "uniform",
                panel_length=int(params.get("panel_length", 2)),
                waves_used=list(params.get("waves_used", [1, 2])),
                class_definition={
                    "type": "preclassified",
                    "n_classes": n_classes,
                },
            ),
            attrition=MobilityAttrition(
                pattern=str(params.get("attrition_pattern", "panel_attrition")),
                monotone=bool(params.get("monotone", True)),
                mechanism_assumed=str(params.get("mechanism_assumed", "mar_given_observables")),
                refreshment_sample=bool(params.get("refreshment_sample", False)),
                positivity_floor=min(max(positivity_floor, 1e-6), 0.49),
                weight_model=retention_model,
                outcome_model=outcome_model,
            ),
            point_estimate=MobilityPointEstimate(
                joint_matrix=joint_matrix.tolist(),
                transition_matrix=transition_matrix.tolist(),
                row_marginals=row_marginals.tolist(),
                col_marginals=col_marginals.tolist(),
                mobility_stats=mobility_stats,
            ),
            uncertainty=MobilityUncertainty(method=f"{estimator}_point_only"),
            bounds=bounds_payload,
            diagnostics=diagnostics,
            assumptions=[
                "class_definition_fixed_ex_ante",
                "mar_given_observables",
                "positivity",
                "origin_class_observed_for_all_units",
            ],
            summary_metrics=_legacy_summary_metrics(
                transition_matrix,
                mobility_stats,
                n_classes=n_classes,
                n_obs=int(observed_mask.sum()),
            ),
            upstream_refs=upstream_refs,
            metadata={
                "estimator": estimator,
                "n_valid_origin": int(valid_origin_mask.sum()),
                "invalid_retained_destinations": invalid_observed,
                "bounds_headline_metric": (
                    None if bounds_bundle is None else bounds_bundle.metadata.get("headline_metric")
                ),
            },
        )

        report_ref = (
            persist_mobility_report(artifact_store, report) if artifact_store is not None else None
        )
        return {
            "result": report,
            "mobility_report_ref": None
            if report_ref is None
            else report_ref.model_dump(mode="json"),
        }


@foundry_method(
    namespace="distributional.mobility",
    version="1.0.0",
    tags={"distributional", "mobility", "attrition", "panel", "sequential", "ipcw", "aipw"},
)
class SequentialIPCWLifetimeMobilityEstimator:
    """Estimate mobility for multi-wave panels under sequential attrition."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sequential_lifetime_transition_matrix",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "origin_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "destination_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "retention_indicators_by_wave",
                    SlotType.MATRIX,
                    Unit("indicator", "binary"),
                    shape=("n_obs", "n_waves"),
                ),
                SlotSpec(
                    "attrition_features_by_wave",
                    SlotType.TENSOR,
                    Unit("feature", "value"),
                    shape=("n_obs", "n_waves", "n_features"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_classes", default=5),
            ParameterSpec(name="estimator", default="aipw"),
            ParameterSpec(name="positivity_floor", default=0.05),
            ParameterSpec(name="compute_bounds", default=True),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Sequential IPCW/AIPW estimator for mobility matrices in multi-wave panels.",
        tags=frozenset(
            {"distributional", "mobility", "attrition", "panel", "sequential", "ipcw", "aipw"}
        ),
        when_to_use="Lifetime or long-panel mobility when final class requires survival through multiple waves and attrition is modeled sequentially.",
        output_interpretation="Returns a mobility report with sequential retention diagnostics, point estimates, and bounds fallback.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError(
                "state must provide origin_classes, destination_classes, retention_indicators_by_wave, and attrition features"
            )
        origin = _class_vector(state, "origin_classes")
        destination = _class_vector(state, "destination_classes", allow_missing=True)
        if destination.shape[0] != origin.shape[0]:
            raise ValueError("destination_classes must align with origin_classes")
        n_obs = origin.shape[0]
        retention_matrix = _retention_matrix(state, "retention_indicators_by_wave", n_obs=n_obs)
        n_waves = retention_matrix.shape[1]
        n_classes = int(params.get("n_classes", 5))
        estimator = str(params.get("estimator", "aipw")).strip().lower()
        if estimator not in {"ipcw", "aipw"}:
            raise ValueError("estimator must be one of {'ipcw', 'aipw'}")
        positivity_floor = float(params.get("positivity_floor", 0.05))

        base_features = _feature_matrix(state, n_obs, fallback=origin.reshape(-1, 1))
        base_weights = _optional_weights(state, n_obs)
        valid_origin_mask = (origin >= 0) & (origin < n_classes)
        if not np.any(valid_origin_mask):
            raise ValueError("origin_classes must contain at least one valid class index")
        normalized_weights = _normalize_weights(base_weights, valid_origin_mask)
        features_by_wave = _feature_tensor_by_wave(
            state,
            n_obs=n_obs,
            n_waves=n_waves,
            fallback_features=base_features,
        )
        provided_by_wave = state.get("retention_probabilities_by_wave")
        provided_matrix = (
            None if provided_by_wave is None else np.asarray(provided_by_wave, dtype=float)
        )
        wave_probabilities, observed_retention_rates = _fit_sequential_retention_probabilities(
            retention_matrix=retention_matrix,
            features_by_wave=features_by_wave,
            valid_origin_mask=valid_origin_mask,
            base_weights=normalized_weights,
            positivity_floor=positivity_floor,
            provided_probabilities_by_wave=provided_matrix,
        )
        combined_retention_probabilities = np.prod(wave_probabilities, axis=1)
        fully_retained = np.all(retention_matrix == 1, axis=1)
        observed_mask = (
            valid_origin_mask & fully_retained & (destination >= 0) & (destination < n_classes)
        )

        row_marginals = _weighted_row_marginals(
            origin,
            n_classes=n_classes,
            weights=normalized_weights,
            mask=valid_origin_mask,
        )
        observed_joint = _weighted_joint_matrix(
            origin,
            destination,
            n_classes=n_classes,
            weights=normalized_weights,
            mask=observed_mask,
        )
        adjusted_weights = np.zeros(n_obs, dtype=float)
        adjusted_weights[observed_mask] = (
            normalized_weights[observed_mask] / combined_retention_probabilities[observed_mask]
        )

        transition_matrix = np.zeros((n_classes, n_classes), dtype=float)
        for row in range(n_classes):
            row_mask = valid_origin_mask & (origin == row)
            row_total = float(row_marginals[row])
            if row_total <= _EPS:
                continue
            if estimator == "ipcw":
                row_joint = _weighted_joint_matrix(
                    origin[row_mask],
                    destination[row_mask],
                    n_classes=n_classes,
                    weights=adjusted_weights[row_mask],
                    mask=observed_mask[row_mask],
                )
                row_probs = row_joint[row] / max(float(row_joint[row].sum()), _EPS)
            else:
                x_row = base_features[row_mask]
                observed_row_mask = observed_mask[row_mask]
                row_probs = np.zeros(n_classes, dtype=float)
                for col in range(n_classes):
                    y_train = (destination[row_mask][observed_row_mask] == col).astype(float)
                    if observed_row_mask.sum() == 0:
                        mu_hat = np.full(x_row.shape[0], 1.0 / n_classes, dtype=float)
                    else:
                        mu_hat = _predict_weighted_linear_probability(
                            x_row[observed_row_mask],
                            y_train,
                            normalized_weights[row_mask][observed_row_mask],
                            x_row,
                        )
                    y_full = ((destination[row_mask] == col) & observed_row_mask).astype(float)
                    contribution = mu_hat + (
                        observed_row_mask.astype(float) / combined_retention_probabilities[row_mask]
                    ) * (y_full - mu_hat)
                    row_probs[col] = float(
                        np.sum(normalized_weights[row_mask] * contribution) / row_total
                    )
                row_probs = np.clip(row_probs, 0.0, None)
            row_sum = float(row_probs.sum())
            transition_matrix[row] = (
                np.full(n_classes, 1.0 / n_classes, dtype=float)
                if row_sum <= _EPS
                else row_probs / row_sum
            )

        joint_matrix = row_marginals[:, None] * transition_matrix
        col_marginals = joint_matrix.sum(axis=0)
        mobility_stats = _mobility_stats(joint_matrix, row_marginals)

        bounds_bundle = None
        bounds_ref = None
        bounds_payload = MobilityBounds()
        artifact_store = resolve_artifact_store(state, params)
        if bool(params.get("compute_bounds", True)):
            destination_marginals = state.get("destination_marginals")
            normalized_destination_marginals = None
            if destination_marginals is not None:
                normalized_destination_marginals = np.asarray(destination_marginals, dtype=float)
                if (
                    normalized_destination_marginals.ndim != 1
                    or normalized_destination_marginals.size != n_classes
                ):
                    raise ValueError(
                        "destination_marginals must be a 1D vector of length n_classes"
                    )
                if np.any(~np.isfinite(normalized_destination_marginals)) or np.any(
                    normalized_destination_marginals < 0.0
                ):
                    raise ValueError("destination_marginals must be finite and non-negative")
                normalized_destination_marginals /= max(
                    float(normalized_destination_marginals.sum()), _EPS
                )
            bounds_bundle, cell_lower, cell_upper, summary_bounds = build_mobility_bounds_bundle(
                observed_joint,
                row_marginals,
                column_marginals=normalized_destination_marginals,
                headline_metric="upward_rate",
                metadata={
                    "analysis_type": "sequential_lifetime_transition_matrix",
                    "estimator": estimator,
                    "n_waves": n_waves,
                },
            )
            if artifact_store is not None:
                bounds_ref = persist_bounds_bundle(artifact_store, bounds_bundle)
            bounds_payload = MobilityBounds(
                bundle_ref=bounds_ref,
                cell_bounds=_cell_bounds_payload(cell_lower, cell_upper),
                summary_bounds={
                    key: tuple(map(float, value)) for key, value in summary_bounds.items()
                },
                sharpness_status=(
                    "sharp_with_known_marginals"
                    if normalized_destination_marginals is not None
                    else "sharp_with_row_marginals"
                ),
                method=str(bounds_bundle.metadata.get("bounds_method", "transport_bounds")),
            )

        positive_weights = adjusted_weights[adjusted_weights > 0.0]
        wave_observed = {
            f"wave_{wave + 1}_retention_rate": float(rate)
            for wave, rate in enumerate(observed_retention_rates)
        }
        diagnostics = MobilityDiagnostics(
            effective_sample_size=_effective_sample_size(positive_weights),
            max_weight=(float(np.max(positive_weights)) if positive_weights.size else None),
            p99_weight=(
                float(np.quantile(positive_weights, 0.99)) if positive_weights.size else None
            ),
            min_retention_probability=float(
                np.min(combined_retention_probabilities[valid_origin_mask])
            ),
            max_retention_probability=float(
                np.max(combined_retention_probabilities[valid_origin_mask])
            ),
            observed_retention_rate=float(np.sum(normalized_weights[fully_retained])),
            observed_full_cases=int(observed_mask.sum()),
            sensitivity_grid=wave_observed,
            warnings=(
                ["sequential_positivity_floor_active"]
                if float(np.min(wave_probabilities[valid_origin_mask]))
                <= min(max(positivity_floor, 1e-6), 0.49) + 1e-9
                else []
            ),
        )
        report = MobilityReport(
            analysis_type="sequential_lifetime_transition_matrix",
            estimand_id="mobility.sequential_lifetime_transition_matrix",
            status="warn" if diagnostics.warnings else "ok",
            population=MobilityPopulation(
                target_population="panel baseline cohort",
                weights_design="sample_weights"
                if "sample_weights" in state or "weights" in state
                else "uniform",
                panel_length=n_waves + 1,
                waves_used=list(params.get("waves_used", list(range(1, n_waves + 2)))),
                class_definition={
                    "type": str(params.get("class_type", "preclassified")),
                    "n_classes": n_classes,
                    "lifetime_rule": str(
                        params.get("lifetime_rule", "provided_destination_classes")
                    ),
                },
            ),
            attrition=MobilityAttrition(
                pattern=str(params.get("attrition_pattern", "monotone_dropout")),
                monotone=bool(params.get("monotone", True)),
                mechanism_assumed="sequential_mar_given_history",
                refreshment_sample=bool(params.get("refreshment_sample", False)),
                positivity_floor=min(max(positivity_floor, 1e-6), 0.49),
                weight_model=MobilityModelSpec(
                    family=(
                        "provided_wave_probabilities"
                        if provided_by_wave is not None
                        else "weighted_logit_per_wave"
                    ),
                    features=_resolve_feature_names(
                        state,
                        base_features.shape[1],
                        include_origin=False,
                        n_classes=n_classes,
                    ),
                    metadata={"n_waves": n_waves},
                ),
                outcome_model=(
                    None
                    if estimator == "ipcw"
                    else MobilityModelSpec(
                        family="weighted_linear_probability",
                        features=_resolve_feature_names(
                            state,
                            base_features.shape[1],
                            include_origin=False,
                            n_classes=n_classes,
                        ),
                    )
                ),
            ),
            point_estimate=MobilityPointEstimate(
                joint_matrix=joint_matrix.tolist(),
                transition_matrix=transition_matrix.tolist(),
                row_marginals=row_marginals.tolist(),
                col_marginals=col_marginals.tolist(),
                mobility_stats=mobility_stats,
            ),
            uncertainty=MobilityUncertainty(method=f"sequential_{estimator}_point_only"),
            bounds=bounds_payload,
            diagnostics=diagnostics,
            assumptions=[
                "class_definition_fixed_ex_ante",
                "sequential_mar_given_history",
                "positivity",
                "monotone_dropout_assumption"
                if bool(params.get("monotone", True))
                else "nonmonotone_retention_supplied",
            ],
            summary_metrics=_legacy_summary_metrics(
                transition_matrix,
                mobility_stats,
                n_classes=n_classes,
                n_obs=int(observed_mask.sum()),
            ),
            upstream_refs=([] if bounds_ref is None else [f"artifact://{bounds_ref.artifact_id}"]),
            metadata={
                "estimator": estimator,
                "n_waves": n_waves,
                "wave_retention_rates": wave_observed,
            },
        )
        report_ref = (
            persist_mobility_report(artifact_store, report) if artifact_store is not None else None
        )
        return {
            "result": report,
            "mobility_report_ref": None
            if report_ref is None
            else report_ref.model_dump(mode="json"),
        }


@foundry_method(
    namespace="distributional.mobility",
    version="1.0.0",
    tags={"distributional", "mobility", "refreshment", "panel", "mnar"},
)
class RefreshmentSampleMobilityEstimator:
    """Refreshment-sample anchored mobility completion under weaker attrition assumptions."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="refreshment_transition_matrix",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "origin_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "destination_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "retention_indicators",
                    SlotType.VECTOR,
                    Unit("indicator", "binary"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "refreshment_destination_classes",
                    SlotType.VECTOR,
                    Unit("class", "index"),
                    shape=("n_refreshment",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_classes", default=5),
            ParameterSpec(name="compute_bounds", default=True),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Refreshment-sample anchored mobility estimator using observed stayers plus destination marginals.",
        tags=frozenset({"distributional", "mobility", "refreshment", "panel", "mnar"}),
        when_to_use="Use when panel attrition may depend on unobservables and an external or internal refreshment sample identifies destination marginals.",
        output_interpretation="Returns a model-based point estimate anchored by refreshment-sample destination marginals plus sharp transport bounds.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError(
                "state must provide origin_classes, destination_classes, retention_indicators, and refreshment destination information"
            )
        origin = _class_vector(state, "origin_classes")
        destination = _class_vector(state, "destination_classes", allow_missing=True)
        retained = _binary_vector(state, "retention_indicators", length=origin.shape[0])
        if destination.shape[0] != origin.shape[0]:
            raise ValueError("destination_classes must align with origin_classes")
        n_classes = int(params.get("n_classes", 5))
        base_weights = _optional_weights(state, origin.shape[0])
        valid_origin_mask = (origin >= 0) & (origin < n_classes)
        normalized_weights = _normalize_weights(base_weights, valid_origin_mask)
        observed_mask = (
            valid_origin_mask & (retained == 1) & (destination >= 0) & (destination < n_classes)
        )

        baseline_row_marginals = _weighted_row_marginals(
            origin,
            n_classes=n_classes,
            weights=normalized_weights,
            mask=valid_origin_mask,
        )
        observed_joint = _weighted_joint_matrix(
            origin,
            destination,
            n_classes=n_classes,
            weights=normalized_weights,
            mask=observed_mask,
        )
        destination_marginals = _column_marginals_from_refreshment(state, n_classes=n_classes)
        raw_row_totals = _weighted_row_marginals(
            origin,
            n_classes=n_classes,
            weights=base_weights,
            mask=valid_origin_mask,
        )
        raw_observed_joint = _weighted_joint_matrix(
            origin,
            destination,
            n_classes=n_classes,
            weights=base_weights,
            mask=observed_mask,
        )
        refreshment_column_totals = _refreshment_column_counts(
            state,
            n_classes=n_classes,
            fallback_total=float(np.sum(base_weights[valid_origin_mask])),
        )
        joint_matrix, refreshment_fit = _fit_refreshment_additive_nonignorable_joint(
            raw_observed_joint,
            raw_row_totals,
            refreshment_column_totals,
        )
        row_marginals = joint_matrix.sum(axis=1)
        transition_matrix = _row_normalize(joint_matrix, row_marginals)
        mobility_stats = _mobility_stats(joint_matrix, row_marginals)

        artifact_store = resolve_artifact_store(state, params)
        bounds_bundle = None
        bounds_ref = None
        bounds_payload = MobilityBounds()
        if bool(params.get("compute_bounds", True)):
            bounds_bundle, cell_lower, cell_upper, summary_bounds = build_mobility_bounds_bundle(
                observed_joint,
                baseline_row_marginals,
                column_marginals=destination_marginals,
                headline_metric="upward_rate",
                metadata={
                    "analysis_type": "refreshment_transition_matrix",
                    "refreshment_model_family": refreshment_fit["family"],
                },
            )
            if artifact_store is not None:
                bounds_ref = persist_bounds_bundle(artifact_store, bounds_bundle)
            bounds_payload = MobilityBounds(
                bundle_ref=bounds_ref,
                cell_bounds=_cell_bounds_payload(cell_lower, cell_upper),
                summary_bounds={
                    key: tuple(map(float, value)) for key, value in summary_bounds.items()
                },
                sharpness_status="sharp_with_known_marginals",
                method=str(bounds_bundle.metadata.get("bounds_method", "transport_bounds")),
            )
        report = MobilityReport(
            analysis_type="refreshment_transition_matrix",
            estimand_id="mobility.refreshment_transition_matrix",
            status="warn",
            population=MobilityPopulation(
                target_population="panel baseline cohort with refreshment sample",
                weights_design="sample_weights"
                if "sample_weights" in state or "weights" in state
                else "uniform",
                panel_length=2,
                waves_used=list(params.get("waves_used", [1, 2])),
                class_definition={"type": "preclassified", "n_classes": n_classes},
            ),
            attrition=MobilityAttrition(
                pattern=str(params.get("attrition_pattern", "dropout_with_refreshment")),
                monotone=bool(params.get("monotone", True)),
                mechanism_assumed="selection_on_unobservables_refreshment",
                refreshment_sample=True,
                weight_model=MobilityModelSpec(
                    family=str(refreshment_fit["family"]),
                    features=["origin_class", "destination_class"],
                    metadata={"identified_by": "refreshment_destination_marginals"},
                ),
            ),
            point_estimate=MobilityPointEstimate(
                joint_matrix=joint_matrix.tolist(),
                transition_matrix=transition_matrix.tolist(),
                row_marginals=row_marginals.tolist(),
                col_marginals=destination_marginals.tolist(),
                mobility_stats=mobility_stats,
            ),
            uncertainty=MobilityUncertainty(method="refreshment_completion_point_only"),
            bounds=bounds_payload,
            diagnostics=MobilityDiagnostics(
                observed_retention_rate=float(np.sum(normalized_weights[retained == 1])),
                observed_full_cases=int(observed_mask.sum()),
                warnings=(
                    ["refreshment_additive_nonignorable_logit_structural_fit"]
                    if not bool(refreshment_fit.get("fallback_used", False))
                    else ["refreshment_structural_fit_failed_fallback_residual_completion"]
                ),
            ),
            assumptions=[
                "origin_marginals_observed_at_baseline",
                "destination_marginals_identified_from_refreshment_sample",
                (
                    "additive_nonignorable_selection_model"
                    if not bool(refreshment_fit.get("fallback_used", False))
                    else "residual_completion_independence_for_point_estimate"
                ),
            ],
            summary_metrics=_legacy_summary_metrics(
                transition_matrix,
                mobility_stats,
                n_classes=n_classes,
                n_obs=int(observed_mask.sum()),
            ),
            upstream_refs=([] if bounds_ref is None else [f"artifact://{bounds_ref.artifact_id}"]),
            metadata={
                "refreshment_sample_size": int(
                    np.asarray(state.get("refreshment_destination_classes", [])).size
                ),
                "refreshment_fit": refreshment_fit,
            },
        )
        report_ref = (
            persist_mobility_report(artifact_store, report) if artifact_store is not None else None
        )
        return {
            "result": report,
            "mobility_report_ref": None
            if report_ref is None
            else report_ref.model_dump(mode="json"),
        }


@foundry_method(
    namespace="distributional.mobility",
    version="1.0.0",
    tags={"distributional", "mobility", "intergenerational", "ige", "cross-section"},
)
class IntergenerationalElasticityEstimator:
    """Estimate parent-child income elasticity for intergenerational mobility audits."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="intergenerational_elasticity",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "parent_values",
                    SlotType.VECTOR,
                    Unit("income", "amount"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "child_values",
                    SlotType.VECTOR,
                    Unit("income", "amount"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Intergenerational elasticity (IGE): log-log OLS of child on parent income.",
        tags=frozenset({"distributional", "mobility", "intergenerational", "ige", "cross-section"}),
        when_to_use="Intergenerational income mobility; quantifying persistence of economic status across generations",
        output_interpretation="IGE near 0 = high mobility (child income independent of parent). IGE near 1 = low mobility (strong persistence).",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("state must provide parent_values and child_values")
        parent = np.asarray(state["parent_values"], dtype=float)
        child = np.asarray(state["child_values"], dtype=float)
        if parent.ndim != 1 or child.ndim != 1:
            raise ValueError("parent_values and child_values must be 1D")
        if parent.shape[0] != child.shape[0]:
            raise ValueError("parent_values and child_values must have same length")
        if parent.shape[0] < 2:
            raise ValueError("need at least 2 observations")
        if np.any(parent <= 0) or np.any(child <= 0):
            raise ValueError("all values must be positive for log transformation")

        log_parent = np.log(parent)
        log_child = np.log(child)

        n = log_parent.shape[0]
        x_mean = float(np.mean(log_parent))
        y_mean = float(np.mean(log_child))
        x_centered = log_parent - x_mean
        y_centered = log_child - y_mean

        ss_xx = float(np.sum(x_centered**2))
        ss_xy = float(np.sum(x_centered * y_centered))
        ss_yy = float(np.sum(y_centered**2))

        if ss_xx < 1e-12:
            raise ValueError("parent_values have zero variance")

        beta = ss_xy / ss_xx
        alpha = y_mean - beta * x_mean
        r_squared = 1.0 if ss_yy < 1e-12 else (ss_xy**2) / (ss_xx * ss_yy)

        artifact_store = resolve_artifact_store(state, params)
        report = MobilityReport(
            analysis_type="intergenerational_elasticity",
            estimand_id="mobility.intergenerational_elasticity",
            status="ok",
            point_estimate=MobilityPointEstimate(
                mobility_stats={
                    "ige": float(beta),
                    "intercept": float(alpha),
                    "r_squared": float(max(0.0, min(1.0, r_squared))),
                }
            ),
            uncertainty=MobilityUncertainty(method="ols_closed_form_pending"),
            diagnostics=MobilityDiagnostics(observed_full_cases=n),
            summary_metrics={
                "ige": float(beta),
                "intercept": float(alpha),
                "r_squared": float(max(0.0, min(1.0, r_squared))),
                "n": n,
            },
            metadata={"log_scale": True},
        )
        report_ref = (
            persist_mobility_report(artifact_store, report) if artifact_store is not None else None
        )
        return {
            "result": report,
            "mobility_report_ref": None
            if report_ref is None
            else report_ref.model_dump(mode="json"),
        }


__all__ = [
    "AttritionAdjustedMobilityMatrixEstimator",
    "IntergenerationalElasticityEstimator",
    "MobilityMatrixEstimator",
    "RefreshmentSampleMobilityEstimator",
    "SequentialIPCWLifetimeMobilityEstimator",
]
