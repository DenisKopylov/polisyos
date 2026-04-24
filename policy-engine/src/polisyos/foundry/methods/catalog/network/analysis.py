"""Estimate network structure, diffusion, contagion, and multiplex diagnostics."""

from __future__ import annotations

import math
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

from .embedding_fidelity import maybe_compute_embedding_fidelity_certificate
from .missingness import (
    NetworkMissingnessRequest,
    build_network_missingness_assessment,
    maybe_build_missingness_assessment,
)
from .protocols import (
    BoundEstimate,
    IdentificationDiagnostics,
    IntervalEstimate,
    MultiplexNetworkData,
    NetworkData,
    NetworkResult,
    PeerEffectDecomposition,
)


def _network_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, NetworkData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        nested = state.get("network_data")
        if isinstance(nested, NetworkData):
            return nested.model_dump(mode="python")
        if isinstance(nested, Mapping):
            payload = dict(nested)
            payload.update({k: v for k, v in state.items() if k not in {"network_data"}})
            return payload
        return dict(state)
    raise TypeError("state must be NetworkData or mapping")


def _multiplex_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, MultiplexNetworkData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        return dict(state)
    raise TypeError("state must be MultiplexNetworkData or mapping")


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("network", "json"),
                contract_id=NetworkResult.contract_id,
            )
        }
    )


def _missingness_passthrough_parameters() -> tuple[ParameterSpec, ...]:
    return (
        ParameterSpec(name="missingness", default=None),
        ParameterSpec(name="missingness_assessment", default=None),
    )


def _missingness_request_parameters() -> tuple[ParameterSpec, ...]:
    return (
        ParameterSpec(name="mode", default="bounds_only"),
        ParameterSpec(name="missingness_type", default="link_censoring"),
        ParameterSpec(name="frame_observed", default=True),
        ParameterSpec(name="estimands", default=()),
        ParameterSpec(name="assumptions", default=()),
        ParameterSpec(name="missingness_hypotheses", default=()),
        ParameterSpec(name="node_observed_mask", default=None),
        ParameterSpec(name="dyad_observed_mask", default=None),
        ParameterSpec(name="confirmed_absence_mask", default=None),
        ParameterSpec(name="structural_missing_dyad_mask", default=None),
        ParameterSpec(name="node_inclusion_probabilities", default=None),
        ParameterSpec(name="dyad_inclusion_probabilities", default=None),
        ParameterSpec(name="gold_standard_adjacency", default=None),
        ParameterSpec(name="validation_node_mask", default=None),
        ParameterSpec(name="shortest_path_pairs", default=()),
        ParameterSpec(name="fixed_choice_limit", default=None),
        ParameterSpec(name="sensitivity_parameter", default="delta"),
        ParameterSpec(name="sensitivity_values", default=()),
        ParameterSpec(name="posterior_draws", default=256),
        ParameterSpec(name="credible_level", default=0.95),
        ParameterSpec(name="prior_edge_alpha", default=1.0),
        ParameterSpec(name="prior_edge_beta", default=1.0),
        ParameterSpec(name="posterior_seed", default=0),
        ParameterSpec(name="metadata", default=None),
        ParameterSpec(name="missingness", default=None),
        ParameterSpec(name="missingness_assessment", default=None),
    )


def _network_embedding_fidelity_certificate(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
) -> dict[str, Any] | None:
    return maybe_compute_embedding_fidelity_certificate(state, params=params)


def _network_result_metadata(
    metadata: Mapping[str, Any] | None,
    embedding_fidelity_certificate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(metadata or {})
    if embedding_fidelity_certificate is not None:
        merged.setdefault("embedding_fidelity_certificate", dict(embedding_fidelity_certificate))
    return merged


def _missingness_request_payload(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
    raw = params.get("missingness_assessment") or params.get("missingness")
    if isinstance(raw, NetworkMissingnessRequest):
        return raw.model_dump(mode="python")
    if isinstance(raw, Mapping):
        return dict(raw)
    payload = {}
    defaults = state.metadata.get("missingness_assessment") or state.metadata.get("missingness")
    if isinstance(defaults, NetworkMissingnessRequest):
        payload.update(defaults.model_dump(mode="python"))
    elif isinstance(defaults, Mapping):
        payload.update(defaults)
    request_fields = set(NetworkMissingnessRequest.model_fields)
    payload.update(
        {key: value for key, value in params.items() if key in request_fields and value is not None}
    )
    return payload


def _row_normalize(adjacency: np.ndarray) -> np.ndarray:
    arr = np.asarray(adjacency, dtype=float)
    row_sums = np.sum(arr, axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    return arr / row_sums


def _symmetrize(adjacency: np.ndarray) -> np.ndarray:
    arr = np.asarray(adjacency, dtype=float)
    return 0.5 * (arr + arr.T)


def _component_labels(adjacency: np.ndarray) -> np.ndarray:
    graph = _symmetrize(np.asarray(adjacency, dtype=float))
    active = graph > 0.0
    n_nodes = active.shape[0]
    labels = -np.ones(n_nodes, dtype=int)
    current = 0
    for start in range(n_nodes):
        if labels[start] >= 0:
            continue
        stack = [start]
        labels[start] = current
        while stack:
            node = stack.pop()
            neighbors = np.flatnonzero(active[node] | active[:, node])
            for neighbor in neighbors:
                if labels[neighbor] >= 0:
                    continue
                labels[neighbor] = current
                stack.append(int(neighbor))
        current += 1
    return labels


def _demean_by_labels(values: np.ndarray, labels: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    out = arr.copy()
    for label in np.unique(labels):
        mask = labels == label
        if arr.ndim == 1:
            out[mask] = arr[mask] - np.mean(arr[mask])
        else:
            out[mask, :] = arr[mask, :] - np.mean(arr[mask, :], axis=0, keepdims=True)
    return out


def _density(adjacency: np.ndarray) -> float:
    arr = np.asarray(adjacency, dtype=float)
    n_nodes = arr.shape[0]
    if n_nodes <= 1:
        return 0.0
    nonzero = float(np.count_nonzero(arr))
    return nonzero / float(n_nodes * (n_nodes - 1))


def _intransitivity_index(adjacency: np.ndarray) -> float:
    graph = (_symmetrize(adjacency) > 0.0).astype(float)
    np.fill_diagonal(graph, 0.0)
    degree = np.sum(graph, axis=1)
    triplets = float(np.sum(degree * np.maximum(degree - 1.0, 0.0) / 2.0))
    if triplets <= 0.0:
        return 0.0
    triangles = float(np.trace(graph @ graph @ graph) / 6.0)
    clustering = float(np.clip((3.0 * triangles) / triplets, 0.0, 1.0))
    return float(1.0 - clustering)


def _spectral_radius(adjacency: np.ndarray) -> float:
    eigvals = np.linalg.eigvals(np.asarray(adjacency, dtype=float))
    return float(np.max(np.abs(eigvals))) if eigvals.size else 0.0


def _ensure_2d_features(features: np.ndarray) -> np.ndarray:
    arr = np.asarray(features, dtype=float)
    if arr.ndim == 1:
        return arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError("node_features must be a 1D or 2D array")
    return arr


def _safe_standardize(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 1:
        mean = np.mean(arr)
        scale = float(np.std(arr))
        if scale <= 1e-12:
            scale = 1.0
        return (arr - mean) / scale, np.asarray([mean]), np.asarray([scale])
    mean = np.mean(arr, axis=0)
    scale = np.std(arr, axis=0)
    scale = np.where(scale <= 1e-12, 1.0, scale)
    return (arr - mean) / scale, mean, scale


def _column_stack(*arrays: np.ndarray) -> np.ndarray:
    columns: list[np.ndarray] = []
    for arr in arrays:
        if arr is None:
            continue
        current = np.asarray(arr, dtype=float)
        if current.ndim == 1:
            columns.append(current.reshape(-1, 1))
        else:
            columns.append(current)
    return np.column_stack(columns) if columns else np.empty((0, 0), dtype=float)


def _rank_summary(matrix: np.ndarray) -> tuple[bool, float | None]:
    arr = np.asarray(matrix, dtype=float)
    if arr.size == 0:
        return False, None
    rank = np.linalg.matrix_rank(arr)
    full_rank = rank == arr.shape[1]
    try:
        cond = float(np.linalg.cond(arr))
    except np.linalg.LinAlgError:
        cond = None
    return full_rank, cond


def _fit_ols(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    design = np.asarray(X, dtype=float)
    outcome = np.asarray(y, dtype=float).reshape(-1, 1)
    xtx_inv = np.linalg.pinv(design.T @ design)
    beta = xtx_inv @ design.T @ outcome
    resid = outcome - design @ beta
    dof = max(design.shape[0] - design.shape[1], 1)
    sigma2 = float((resid.T @ resid).item() / dof)
    cov = sigma2 * xtx_inv
    se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    return beta.reshape(-1), se, resid.reshape(-1)


def _fit_wls(
    y: np.ndarray, X: np.ndarray, weights: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    design = np.asarray(X, dtype=float)
    outcome = np.asarray(y, dtype=float).reshape(-1, 1)
    weight_vec = np.asarray(weights, dtype=float).reshape(-1)
    if design.shape[0] != weight_vec.shape[0]:
        raise ValueError("weights must align with the number of observations")
    root_w = np.sqrt(np.clip(weight_vec, 1.0e-12, None)).reshape(-1, 1)
    return _fit_ols((root_w[:, 0] * outcome[:, 0]), root_w * design)


def _fit_2sls(
    y: np.ndarray, X: np.ndarray, Z: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    regressors = np.asarray(X, dtype=float)
    instruments = np.asarray(Z, dtype=float)
    outcome = np.asarray(y, dtype=float).reshape(-1, 1)
    ztz_inv = np.linalg.pinv(instruments.T @ instruments)
    projection = instruments @ ztz_inv @ instruments.T
    xt_pz_x = regressors.T @ projection @ regressors
    beta = np.linalg.pinv(xt_pz_x) @ regressors.T @ projection @ outcome
    resid = outcome - regressors @ beta
    dof = max(regressors.shape[0] - regressors.shape[1], 1)
    sigma2 = float((resid.T @ resid).item() / dof)
    cov = sigma2 * np.linalg.pinv(xt_pz_x)
    se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    return beta.reshape(-1), se, resid.reshape(-1)


def _two_sided_normal_p_value(z_score: float) -> float:
    return float(math.erfc(abs(float(z_score)) / math.sqrt(2.0)))


def _confidence_interval(estimate: float, std_error: float, ci_level: float) -> tuple[float, float]:
    alpha = float(np.clip(1.0 - ci_level, 1e-6, 0.5))
    z_value = float(NormalDist().inv_cdf(1.0 - alpha / 2.0))
    margin = z_value * std_error
    return estimate - margin, estimate + margin


def _first_stage_f_stat(target: np.ndarray, exog: np.ndarray, excluded: np.ndarray) -> float | None:
    if excluded.size == 0:
        return None
    unrestricted = _column_stack(exog, excluded)
    if unrestricted.shape[0] <= unrestricted.shape[1]:
        return None
    _, _, resid_restricted = _fit_ols(target, exog)
    _, _, resid_unrestricted = _fit_ols(target, unrestricted)
    rss_r = float(np.sum(resid_restricted**2))
    rss_u = float(np.sum(resid_unrestricted**2))
    q = excluded.shape[1]
    dof = unrestricted.shape[0] - unrestricted.shape[1]
    if dof <= 0 or q <= 0 or rss_u <= 1e-12:
        return None
    improvement = max(rss_r - rss_u, 0.0) / q
    return float(improvement / (rss_u / dof))


def _first_stage_min_f_stat(
    targets: np.ndarray, exog: np.ndarray, excluded: np.ndarray
) -> float | None:
    arr = np.asarray(targets, dtype=float)
    if arr.ndim == 1:
        return _first_stage_f_stat(arr, exog, excluded)
    f_stats = [
        _first_stage_f_stat(arr[:, column], exog, excluded) for column in range(arr.shape[1])
    ]
    finite = [value for value in f_stats if value is not None and np.isfinite(value)]
    if not finite:
        return None
    return float(min(finite))


def _interval_from_estimate(
    estimate: float | None,
    std_error: float | None,
    *,
    ci_level: float,
    units: str,
    method: str,
) -> IntervalEstimate | None:
    if estimate is None:
        return None
    ci_lower = None
    ci_upper = None
    p_value = None
    if std_error is not None and np.isfinite(std_error) and std_error > 0.0:
        ci_lower, ci_upper = _confidence_interval(float(estimate), float(std_error), ci_level)
        p_value = _two_sided_normal_p_value(float(estimate) / float(std_error))
    return IntervalEstimate(
        estimate=float(estimate),
        std_error=float(std_error) if std_error is not None and np.isfinite(std_error) else None,
        ci_level=ci_level,
        ci_lower=float(ci_lower) if ci_lower is not None else None,
        ci_upper=float(ci_upper) if ci_upper is not None else None,
        p_value=p_value,
        units=units,
        method=method,
    )


def _sensitivity_bounds(
    *,
    center: float | None,
    scale: float,
    observability_rate: float,
    rank_condition_ok: bool,
    weak_flag: bool,
    explicit_radius: float | None,
) -> BoundEstimate | None:
    if scale <= 0.0 or not np.isfinite(scale):
        return None
    if explicit_radius is not None:
        radius = max(float(explicit_radius), 0.0)
    else:
        radius = max(0.0, 1.0 - observability_rate)
        if not rank_condition_ok:
            radius += 0.25
        if weak_flag:
            radius += 0.15
    anchor = float(center) if center is not None and np.isfinite(center) else 0.0
    width = radius * scale
    return BoundEstimate(
        lower=anchor - width,
        upper=anchor + width,
        assumptions=[
            "sensitivity envelope around reduced-form center",
            f"observability_rate={observability_rate:.3f}",
        ],
        bound_type="sensitivity",
    )


def _optional_array(
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *keys: str,
) -> Any | None:
    for key in keys:
        if key in params and params[key] is not None:
            return params[key]
        if key in metadata and metadata[key] is not None:
            return metadata[key]
    return None


def _optional_matrix(
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *keys: str,
) -> np.ndarray | None:
    value = _optional_array(params, metadata, *keys)
    if value is None:
        return None
    return _ensure_2d_features(np.asarray(value, dtype=float))


def _optional_vector(
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *keys: str,
) -> np.ndarray | None:
    value = _optional_array(params, metadata, *keys)
    if value is None:
        return None
    vector = np.asarray(value, dtype=float).reshape(-1)
    return vector


def _optional_tensor(
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *keys: str,
) -> np.ndarray | None:
    value = _optional_array(params, metadata, *keys)
    if value is None:
        return None
    tensor = np.asarray(value, dtype=float)
    return tensor


def _normalize_panel_outcomes(panel: np.ndarray, n_nodes: int) -> np.ndarray:
    arr = np.asarray(panel, dtype=float)
    if arr.ndim != 2:
        raise ValueError("panel outcomes must be a 2D array")
    if arr.shape[1] == n_nodes:
        return arr
    if arr.shape[0] == n_nodes:
        return arr.T
    raise ValueError("panel outcomes must align with node count")


def _normalize_panel_features(panel: np.ndarray, n_nodes: int) -> np.ndarray:
    arr = np.asarray(panel, dtype=float)
    if arr.ndim != 3:
        raise ValueError("panel features must be a 3D array")
    if arr.shape[1] == n_nodes:
        return arr
    if arr.shape[0] == n_nodes:
        return np.transpose(arr, (1, 0, 2))
    raise ValueError("panel features must align with node count")


def _normalize_panel_adjacency(panel: np.ndarray, n_nodes: int) -> np.ndarray:
    arr = np.asarray(panel, dtype=float)
    if arr.ndim == 2:
        return np.repeat(arr[None, :, :], repeats=2, axis=0)
    if arr.ndim != 3:
        raise ValueError("panel adjacency must be a 2D or 3D array")
    if arr.shape[1:] == (n_nodes, n_nodes):
        return arr
    raise ValueError("panel adjacency must align with node count")


def _coefficient_units(
    *,
    estimand_scale: str,
    focal_feature_index: int,
) -> tuple[str, str, str]:
    endogenous_units = (
        "SD(y) per 1 SD(peer mean y)"
        if estimand_scale == "standardized"
        else "outcome-units per 1-unit change in peer mean outcome"
    )
    contextual_units = (
        f"SD(y) per 1 SD(peer mean x[{focal_feature_index}])"
        if estimand_scale == "standardized"
        else f"outcome-units per 1-unit change in peer mean feature[{focal_feature_index}]"
    )
    total_units = "SD(y)" if estimand_scale == "standardized" else "outcome-units"
    return endogenous_units, contextual_units, total_units


def _correlated_proxy(
    *,
    residuals: np.ndarray,
    adjacency: np.ndarray,
    y_raw: np.ndarray,
    components: np.ndarray,
    use_component_fe: bool,
    ci_level: float,
) -> tuple[IntervalEstimate | None, str | None]:
    if use_component_fe:
        total_variance = float(np.var(y_raw))
        residual_variance = float(np.var(_demean_by_labels(y_raw, components)))
        estimate = (
            0.0
            if total_variance <= 1e-12
            else max(
                0.0,
                min(1.0, 1.0 - residual_variance / total_variance),
            )
        )
        return (
            _interval_from_estimate(
                estimate,
                None,
                ci_level=ci_level,
                units="share of outcome variance",
                method="component_fe_variance_share",
            ),
            "component_fe_variance_share",
        )
    residual_network = np.asarray(adjacency, dtype=float) @ np.asarray(residuals, dtype=float)
    if np.std(residuals) > 1e-12 and np.std(residual_network) > 1e-12:
        estimate = float(np.corrcoef(residuals, residual_network)[0, 1])
    else:
        estimate = 0.0
    return (
        _interval_from_estimate(
            estimate,
            None,
            ci_level=ci_level,
            units="correlation coefficient",
            method="residual_network_autocorrelation",
        ),
        "residual_network_autocorrelation",
    )


def _estimate_linear_peer_model(
    *,
    y: np.ndarray,
    X: np.ndarray,
    WY: np.ndarray,
    WX: np.ndarray,
    W2X: np.ndarray,
    W3X: np.ndarray | None,
    focal_feature_index: int,
    ci_level: float,
    estimand_scale: str,
    use_intercept: bool,
    endogenous_wx: bool = False,
    extra_exog: np.ndarray | None = None,
    instrument_wx: np.ndarray | None = None,
    instrument_w2x: np.ndarray | None = None,
    instrument_w3x: np.ndarray | None = None,
) -> dict[str, Any]:
    y_vec = np.asarray(y, dtype=float).reshape(-1)
    X_mat = _ensure_2d_features(np.asarray(X, dtype=float))
    wy_vec = np.asarray(WY, dtype=float).reshape(-1)
    wx_mat = _ensure_2d_features(np.asarray(WX, dtype=float))
    w2x_mat = _ensure_2d_features(np.asarray(W2X, dtype=float))
    w3x_mat = _ensure_2d_features(np.asarray(W3X if W3X is not None else W2X, dtype=float))
    extra_mat = (
        None if extra_exog is None else _ensure_2d_features(np.asarray(extra_exog, dtype=float))
    )
    instrument_wx_mat = (
        None
        if instrument_wx is None
        else _ensure_2d_features(np.asarray(instrument_wx, dtype=float))
    )
    instrument_w2x_mat = (
        w2x_mat
        if instrument_w2x is None
        else _ensure_2d_features(np.asarray(instrument_w2x, dtype=float))
    )
    instrument_w3x_mat = (
        w3x_mat
        if instrument_w3x is None
        else _ensure_2d_features(np.asarray(instrument_w3x, dtype=float))
    )

    intercept = None if not use_intercept else np.ones(y_vec.shape[0], dtype=float)
    endogenous_units, contextual_units, total_units = _coefficient_units(
        estimand_scale=estimand_scale,
        focal_feature_index=focal_feature_index,
    )

    if endogenous_wx:
        exog = _column_stack(intercept, X_mat, extra_mat)
        endogenous = _column_stack(wy_vec, wx_mat)
        excluded = _column_stack(instrument_wx_mat, instrument_w2x_mat, instrument_w3x_mat)
        regressors = _column_stack(endogenous, exog)
        instruments = _column_stack(exog, excluded)
        beta_hat, beta_se, residuals = _fit_2sls(y_vec, regressors, instruments)
        first_stage_f = _first_stage_min_f_stat(endogenous, exog, excluded)
        contextual_index = 1 + focal_feature_index
        intercept_count = 1 if use_intercept else 0
        gamma_start = 1 + X_mat.shape[1] + intercept_count
        gamma_end = gamma_start + X_mat.shape[1]
        delta_coefficients = beta_hat[1 : 1 + X_mat.shape[1]]
        gamma_coefficients = beta_hat[gamma_start:gamma_end]
    else:
        exog = _column_stack(intercept, X_mat, wx_mat, extra_mat)
        excluded = _column_stack(instrument_w2x_mat, instrument_w3x_mat)
        regressors = _column_stack(wy_vec, exog)
        instruments = _column_stack(exog, excluded)
        beta_hat, beta_se, residuals = _fit_2sls(y_vec, regressors, instruments)
        first_stage_f = _first_stage_f_stat(wy_vec, exog, excluded)
        intercept_count = 1 if use_intercept else 0
        contextual_index = 1 + intercept_count + X_mat.shape[1] + focal_feature_index
        gamma_start = 1 + intercept_count
        gamma_end = gamma_start + X_mat.shape[1]
        delta_start = gamma_end
        delta_coefficients = beta_hat[delta_start : delta_start + X_mat.shape[1]]
        gamma_coefficients = beta_hat[gamma_start:gamma_end]

    reduced_form_design = _column_stack(intercept, X_mat, wx_mat, extra_mat)
    reduced_form_beta, reduced_form_se, _ = _fit_ols(y_vec, reduced_form_design)
    reduced_form_index = (1 if use_intercept else 0) + X_mat.shape[1] + focal_feature_index
    reduced_form_interval = _interval_from_estimate(
        float(reduced_form_beta[reduced_form_index]),
        float(reduced_form_se[reduced_form_index]),
        ci_level=ci_level,
        units=contextual_units,
        method="reduced_form_ols",
    )

    endogenous_estimate = float(beta_hat[0])
    endogenous_std_error = float(beta_se[0])
    contextual_estimate = float(beta_hat[contextual_index])
    contextual_std_error = float(beta_se[contextual_index])
    total_estimate = endogenous_estimate + contextual_estimate
    total_std_error = float(np.sqrt(endogenous_std_error**2 + contextual_std_error**2))

    return {
        "beta_hat": beta_hat,
        "beta_se": beta_se,
        "residuals": residuals,
        "first_stage_f": first_stage_f,
        "endogenous_effect": _interval_from_estimate(
            endogenous_estimate,
            endogenous_std_error,
            ci_level=ci_level,
            units=endogenous_units,
            method="2SLS",
        ),
        "contextual_effect": _interval_from_estimate(
            contextual_estimate,
            contextual_std_error,
            ci_level=ci_level,
            units=contextual_units,
            method="2SLS",
        ),
        "total_peer_effect": _interval_from_estimate(
            total_estimate,
            total_std_error,
            ci_level=ci_level,
            units=total_units,
            method="delta_method_diagonal",
        ),
        "reduced_form_peer_multiplier": reduced_form_interval,
        "gamma_coefficients": gamma_coefficients.tolist(),
        "delta_coefficients": delta_coefficients.tolist(),
    }


def _estimate_randomization_effects(
    *,
    y: np.ndarray,
    X: np.ndarray,
    adjacency: np.ndarray,
    treatment: np.ndarray,
    assignment_probabilities: np.ndarray,
    ci_level: float,
    estimand_scale: str,
) -> dict[str, Any]:
    y_vec = np.asarray(y, dtype=float).reshape(-1)
    X_mat = _ensure_2d_features(np.asarray(X, dtype=float))
    treatment_vec = np.asarray(treatment, dtype=float).reshape(-1)
    prob_vec = np.asarray(assignment_probabilities, dtype=float).reshape(-1)
    if treatment_vec.shape[0] != y_vec.shape[0]:
        raise ValueError("treatment vector must align with node_states")
    if prob_vec.shape[0] == 1:
        prob_vec = np.repeat(prob_vec, y_vec.shape[0])
    if prob_vec.shape[0] != y_vec.shape[0]:
        raise ValueError("assignment_probabilities must align with node_states")
    exposure = np.asarray(adjacency, dtype=float) @ treatment_vec
    weights = 1.0 / np.clip(
        np.where(treatment_vec > 0.5, prob_vec, 1.0 - prob_vec),
        1.0e-6,
        None,
    )
    if estimand_scale == "standardized":
        y_vec, _, _ = _safe_standardize(y_vec)
        X_mat, _, _ = _safe_standardize(X_mat)
        exposure, _, _ = _safe_standardize(exposure)
    design = _column_stack(np.ones(y_vec.shape[0]), treatment_vec, exposure, X_mat)
    beta_hat, beta_se, _ = _fit_wls(y_vec, design, weights)
    units = "SD(y)" if estimand_scale == "standardized" else "outcome-units"
    direct_effect = _interval_from_estimate(
        float(beta_hat[1]),
        float(beta_se[1]),
        ci_level=ci_level,
        units=units,
        method="design_based_wls",
    )
    spillover_effect = _interval_from_estimate(
        float(beta_hat[2]),
        float(beta_se[2]),
        ci_level=ci_level,
        units=units,
        method="design_based_wls",
    )
    total_effect = _interval_from_estimate(
        float(beta_hat[1] + beta_hat[2]),
        float(np.sqrt(beta_se[1] ** 2 + beta_se[2] ** 2)),
        ci_level=ci_level,
        units=units,
        method="design_based_delta_method",
    )
    return {
        "direct_effect": direct_effect,
        "spillover_effect": spillover_effect,
        "total_peer_effect": total_effect,
        "reduced_form_peer_multiplier": spillover_effect,
        "design_coefficients": beta_hat.tolist(),
    }


@foundry_method(
    namespace="network.community",
    version="1.0.0",
    tags={"network", "community-detection"},
)
class CommunityDetectionEstimator:
    """Detect spectral communities in a weighted adjacency matrix; avoid networks without clear block structure or a plausible `k`."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="community_detection",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "adjacency",
                    SlotType.MATRIX,
                    Unit("network", "weight"),
                    shape=("n_nodes", "n_nodes"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="n_clusters", default=3),)
        + _missingness_passthrough_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Spectral community detection on a weighted adjacency matrix.",
        tags=frozenset({"network", "community-detection"}),
        when_to_use="Identify cohesive subgroups; detect clusters in social/trade networks",
        citations=(
            "Newman, M. (2006). Modularity and community structure in networks. PNAS, 103(23), 8577-8582.",
        ),
        when_not_to_use="No clear community structure; number of communities k is fully unknown and elbow is flat",
        output_interpretation="Community assignments. Modularity Q: >0.3 = meaningful community structure.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state)
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        from sklearn.cluster import SpectralClustering

        data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
        payload = data.model_dump(mode="python")
        adjacency = _symmetrize(np.asarray(data.adjacency, dtype=float))
        n_clusters = max(2, min(int(params.get("n_clusters", 3)), adjacency.shape[0] - 1))
        clustering = SpectralClustering(
            n_clusters=n_clusters,
            affinity="precomputed",
            random_state=int(params.get("__seed__", 0)),
            assign_labels="kmeans",
        )
        labels = clustering.fit_predict(adjacency)
        total_weight = float(np.sum(adjacency))
        degree = np.sum(adjacency, axis=1)
        modularity = 0.0
        if total_weight > 1e-12:
            for i in range(adjacency.shape[0]):
                for j in range(adjacency.shape[1]):
                    if labels[i] == labels[j]:
                        modularity += adjacency[i, j] - degree[i] * degree[j] / total_weight
            modularity /= total_weight
        missingness_assessment = maybe_build_missingness_assessment(data, params)
        embedding_fidelity_certificate = _network_embedding_fidelity_certificate(payload, params)
        return {
            "result": NetworkResult(
                method_name="community_detection",
                metrics={"modularity": float(modularity), "n_clusters": float(n_clusters)},
                labels=np.asarray(labels, dtype=int),
                missingness_assessment=missingness_assessment,
                embedding_fidelity_certificate=embedding_fidelity_certificate,
                metadata=_network_result_metadata(
                    {"algorithm": "spectral_clustering"},
                    embedding_fidelity_certificate,
                ),
            )
        }


@foundry_method(
    namespace="network.io",
    version="1.0.0",
    tags={"network", "input-output-network"},
)
class InputOutputNetworkEstimator:
    """Estimate Leontief-style linkage centrality from economic flow matrices; avoid adjacency matrices that are not interpretable as flows."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="input_output_network",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "adjacency",
                    SlotType.MATRIX,
                    Unit("network", "weight"),
                    shape=("n_nodes", "n_nodes"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=_missingness_passthrough_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Network linkage analysis using a Leontief-like inverse over the adjacency matrix.",
        tags=frozenset({"network", "input-output-network"}),
        when_to_use="Identify influential nodes; policy diffusion through economic input-output networks; forward/backward linkage analysis",
        citations=(
            "Leontief, W. (1986). Input-Output Economics. Oxford University Press.",
            "Acemoglu, D. et al. (2012). The network origins of aggregate fluctuations. Econometrica, 80(5), 1977-2016.",
        ),
        when_not_to_use="Non-economic networks; adjacency matrix is not interpretable as flow/share matrix",
        output_interpretation="Centrality scores per node. High betweenness = bottleneck. Backward/forward linkages from Leontief inverse.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state)
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
        payload = data.model_dump(mode="python")
        adjacency = _row_normalize(np.asarray(data.adjacency, dtype=float))
        identity = np.eye(adjacency.shape[0], dtype=float)
        inverse = np.linalg.pinv(identity - 0.8 * adjacency)
        backward = np.sum(inverse, axis=0)
        forward = np.sum(inverse, axis=1)
        missingness_assessment = maybe_build_missingness_assessment(data, params)
        embedding_fidelity_certificate = _network_embedding_fidelity_certificate(payload, params)
        return {
            "result": NetworkResult(
                method_name="input_output_network",
                metrics={
                    "spectral_radius": float(np.max(np.abs(np.linalg.eigvals(adjacency)))),
                    "total_backward_linkage": float(np.sum(backward)),
                },
                node_scores=np.column_stack([forward, backward]),
                missingness_assessment=missingness_assessment,
                embedding_fidelity_certificate=embedding_fidelity_certificate,
                metadata=_network_result_metadata(
                    {"inverse": inverse.tolist()},
                    embedding_fidelity_certificate,
                ),
            )
        }


@foundry_method(
    namespace="network.diffusion",
    version="1.0.0",
    tags={"network", "diffusion"},
)
class NetworkDiffusionEstimator:
    """Simulate DeGroot-style diffusion from initial node states; avoid stochastic contagion questions that require SIS/SIR dynamics."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="network_diffusion",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "adjacency",
                    SlotType.MATRIX,
                    Unit("network", "weight"),
                    shape=("n_nodes", "n_nodes"),
                ),
                SlotSpec(
                    "node_states", SlotType.VECTOR, Unit("state", "value"), shape=("n_nodes",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="diffusion_rate", default=0.3),
            ParameterSpec(name="decay", default=0.05),
            ParameterSpec(name="n_steps", default=10),
        )
        + _missingness_passthrough_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="DeGroot-style network diffusion from initial node states.",
        tags=frozenset({"network", "diffusion"}),
        when_to_use="Spread of behavior, information, or beliefs on network; opinion dynamics; DeGroot learning model",
        citations=(
            "DeGroot, M. (1974). Reaching a consensus. Journal of the American Statistical Association, 69(345), 118-121.",
            "Jackson, M. (2008). Social and Economic Networks. Princeton University Press.",
        ),
        when_not_to_use="Non-network processes; need stochastic contagion (use SIS/SIR); no adjacency structure",
        output_interpretation="Final node states after diffusion. Trajectory shows convergence path. Consensus = all nodes reach same state.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state)
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
        payload = data.model_dump(mode="python")
        adjacency = _row_normalize(np.asarray(data.adjacency, dtype=float))
        current = np.asarray(data.node_states, dtype=float)
        rate = float(params.get("diffusion_rate", 0.3))
        decay = float(params.get("decay", 0.05))
        n_steps = max(1, int(params.get("n_steps", 10)))
        trajectories = [current.copy()]
        for _ in range(n_steps):
            current = np.clip((1.0 - decay) * current + rate * (adjacency @ current), 0.0, 1.0)
            trajectories.append(current.copy())
        traj = np.asarray(trajectories, dtype=float)
        missingness_assessment = maybe_build_missingness_assessment(data, params)
        embedding_fidelity_certificate = _network_embedding_fidelity_certificate(payload, params)
        return {
            "result": NetworkResult(
                method_name="network_diffusion",
                metrics={"final_mean_state": float(np.mean(traj[-1]))},
                node_scores=traj[-1],
                state_trajectories=traj,
                missingness_assessment=missingness_assessment,
                embedding_fidelity_certificate=embedding_fidelity_certificate,
                metadata=_network_result_metadata(
                    {"n_steps": n_steps},
                    embedding_fidelity_certificate,
                ),
            )
        }


@foundry_method(
    namespace="network.missingness",
    version="1.0.0",
    tags={"network", "missingness", "partial-observability", "identification"},
)
class NetworkMissingnessAssessmentEstimator:
    """Assess identification of network statistics under node/link missingness and return typed bounds or model-based diagnostics."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="network_missingness_assessment",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "adjacency",
                    SlotType.MATRIX,
                    Unit("network", "weight"),
                    shape=("n_nodes", "n_nodes"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=_missingness_request_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N3,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Identification-aware assessment of network statistics under partial observability, including HT corrections, bounds, and model-dependent posterior summaries.",
        tags=frozenset({"network", "missingness", "partial-observability"}),
        when_to_use="Audit whether network statistics are point-identified, set-identified, or model-dependent under node sampling, link censoring, or strategic non-disclosure.",
        citations=(
            "Rubin, D. (1976). Inference and missing data. Biometrika, 63(3), 581-592.",
            "Handcock, M. & Gile, K. (2010). Modeling social networks from sampled data. Annals of Applied Statistics, 4(1), 5-25.",
            "Frank, O. (1978). Estimation of graph totals. Scandinavian Journal of Statistics, 5(2), 81-89.",
        ),
        when_not_to_use="No graph structure is available at all; node universe is unknown and no defensible superpopulation model is declared.",
        output_interpretation="Returns a typed missingness assessment with per-estimand identification status. Local totals may be point-identified, path/connectivity metrics are often set-identified, and posterior reconstructions remain model-dependent.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state)
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
        payload = data.model_dump(mode="python")
        request_payload = _missingness_request_payload(data, params)
        assessment = build_network_missingness_assessment(data, request_payload)
        statuses = [item.identification_status.value for item in assessment.estimands.values()]
        metrics = {
            "n_estimands": float(len(assessment.estimands)),
            "point_identified_count": float(
                sum(status == "point_identified" for status in statuses)
            ),
            "set_identified_count": float(sum(status == "set_identified" for status in statuses)),
            "model_dependent_count": float(sum(status == "model_dependent" for status in statuses)),
            "not_identified_count": float(sum(status == "not_identified" for status in statuses)),
        }
        embedding_fidelity_certificate = _network_embedding_fidelity_certificate(payload, params)
        return {
            "result": NetworkResult(
                method_name="network_missingness_assessment",
                metrics=metrics,
                missingness_assessment=assessment,
                embedding_fidelity_certificate=embedding_fidelity_certificate,
                metadata=_network_result_metadata(
                    {
                        "mode": request_payload.get(
                            "mode", data.metadata.get("mode", "bounds_only")
                        ),
                        "requested_estimands": tuple(request_payload.get("estimands", ())),
                    },
                    embedding_fidelity_certificate,
                ),
            )
        }


@foundry_method(
    namespace="network.peer_effects",
    version="1.0.0",
    tags={"network", "peer-effects", "identification", "partial-identification"},
)
class PeerEffectDecompositionEstimator:
    """Decompose peer effects with a conservative topology-IV baseline and explicit blocking mode."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="peer_effect_decomposition",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "adjacency",
                    SlotType.MATRIX,
                    Unit("network", "weight"),
                    shape=("n_nodes", "n_nodes"),
                ),
                SlotSpec(
                    "node_features",
                    SlotType.MATRIX,
                    Unit("feature", "value"),
                    shape=("n_nodes", "n_features"),
                ),
                SlotSpec(
                    "node_states", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_nodes",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="strategy", default="auto"),
            ParameterSpec(name="model_class", default="auto"),
            ParameterSpec(name="ci_level", default=0.95),
            ParameterSpec(name="weak_iv_threshold", default=10.0),
            ParameterSpec(name="min_observability", default=0.95),
            ParameterSpec(name="focal_feature_index", default=0),
            ParameterSpec(name="use_component_fixed_effects", default=False),
            ParameterSpec(name="outcome_scale", default="raw"),
            ParameterSpec(name="partial_id_radius", default=None),
        )
        + _missingness_passthrough_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Manski-style peer effect decomposition with rank diagnostics, weak-IV checks, and partial-identification fallback.",
        tags=frozenset({"network", "peer-effects", "identification", "partial-identification"}),
        when_to_use="Need a structured peer-effects result that distinguishes identified, weakly identified, and blocked network decompositions",
        citations=(
            "Manski, C. (1993). Identification of endogenous social effects: The reflection problem. Review of Economic Studies, 60(3), 531-542.",
            "Bramoulle, Y., Djebbari, H., & Fortin, B. (2009). Identification of peer effects through social networks. Journal of Econometrics, 150(1), 41-55.",
        ),
        when_not_to_use="No node outcomes/features are available, or the caller cannot supply the metadata required for panel, randomization, reconstruction, or endogenous-network routes",
        output_interpretation="Returns a typed decomposition bundle whose strategy_used field shows whether the estimator relied on topology-IV, panel variation, control functions, leave-own-out instruments, graphical reconstruction, or design-based spillover estimation.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state)
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
        payload = data.model_dump(mode="python")
        if data.node_states is None:
            raise ValueError("peer_effect_decomposition requires node_states as the outcome vector")
        if data.node_features is None:
            raise ValueError(
                "peer_effect_decomposition requires node_features for contextual effects"
            )

        metadata = dict(data.metadata)
        adjacency = _row_normalize(np.asarray(data.adjacency, dtype=float))
        y_raw = np.asarray(data.node_states, dtype=float).reshape(-1)
        X_raw = _ensure_2d_features(np.asarray(data.node_features, dtype=float))
        n_nodes = adjacency.shape[0]

        requested_strategy = str(params.get("strategy", "auto")).lower()
        requested_model_class = str(params.get("model_class", "auto")).lower()
        ci_level = float(params.get("ci_level", 0.95))
        weak_iv_threshold = float(params.get("weak_iv_threshold", 10.0))
        min_observability = float(params.get("min_observability", 0.95))
        focal_feature_index = int(params.get("focal_feature_index", 0))
        use_component_fe = bool(
            params.get(
                "use_component_fixed_effects",
                metadata.get("use_component_fixed_effects", False),
            )
        )
        scale_mode = str(params.get("outcome_scale", "raw")).lower()
        partial_id_radius = params.get("partial_id_radius")
        if focal_feature_index < 0 or focal_feature_index >= X_raw.shape[1]:
            raise ValueError("focal_feature_index must reference an existing node_features column")

        assumptions: list[str] = [
            "linear-in-means baseline",
            "row-normalized adjacency with zero self-weight",
        ]
        robustness_checks = ["rank_condition", "reduced_form_fallback"]
        warnings: list[str] = []

        estimand_scale = "standardized" if scale_mode == "standardized" else "outcome_units"
        contextual_units = _coefficient_units(
            estimand_scale=estimand_scale,
            focal_feature_index=focal_feature_index,
        )[1]
        observability_rate = float(
            metadata.get(
                "network_observability_rate",
                metadata.get("observability_rate", 1.0),
            )
        )
        mobility_variation = metadata.get("mobility_variation")

        reconstructed_adjacency = _optional_tensor(
            params,
            metadata,
            "reconstructed_adjacency",
            "graphical_reconstruction_adjacency",
        )
        reconstructed_samples = _optional_tensor(
            params,
            metadata,
            "reconstructed_adjacency_samples",
            "graphical_reconstruction_samples",
        )
        external_instruments = _optional_matrix(
            params,
            metadata,
            "external_instruments",
            "iv_matrix",
            "iv",
        )
        control_function_features = _optional_matrix(
            params,
            metadata,
            "control_function_features",
            "control_function_controls",
        )
        control_function_residuals = _optional_matrix(
            params,
            metadata,
            "control_function_residuals",
            "cf_residuals",
        )
        leave_own_out_adjacency = _optional_tensor(
            params,
            metadata,
            "leave_own_out_adjacency",
            "loo_adjacency",
        )
        leave_own_out_instruments = _optional_matrix(
            params,
            metadata,
            "leave_own_out_instruments",
            "loo_instruments",
        )
        panel_outcomes_raw = _optional_tensor(
            params,
            metadata,
            "panel_outcomes",
            "node_states_panel",
        )
        panel_features_raw = _optional_tensor(
            params,
            metadata,
            "panel_features",
            "node_features_panel",
        )
        panel_adjacency_raw = _optional_tensor(
            params,
            metadata,
            "panel_adjacency",
            "adjacency_panel",
        )
        panel_treatment_raw = _optional_tensor(
            params,
            metadata,
            "panel_treatment",
            "treatment_panel",
        )
        treatment = _optional_vector(params, metadata, "treatment", "assignment")
        assignment_probabilities = _optional_vector(
            params,
            metadata,
            "assignment_probabilities",
            "treatment_probabilities",
        )

        for name, matrix in (
            ("external_instruments", external_instruments),
            ("control_function_features", control_function_features),
            ("control_function_residuals", control_function_residuals),
            ("leave_own_out_instruments", leave_own_out_instruments),
        ):
            if matrix is not None and matrix.shape[0] != n_nodes:
                raise ValueError(f"{name} must have one row per node")

        reconstructed_effective: np.ndarray | None = None
        if reconstructed_samples is not None:
            if reconstructed_samples.ndim != 3 or reconstructed_samples.shape[1:] != (
                n_nodes,
                n_nodes,
            ):
                raise ValueError(
                    "reconstructed_adjacency_samples must have shape (n_draws, n_nodes, n_nodes)"
                )
            reconstructed_effective = _row_normalize(np.mean(reconstructed_samples, axis=0))
        elif reconstructed_adjacency is not None:
            reconstructed_effective = np.asarray(reconstructed_adjacency, dtype=float)
            if reconstructed_effective.shape != (n_nodes, n_nodes):
                raise ValueError("reconstructed_adjacency must match adjacency shape")
            reconstructed_effective = _row_normalize(reconstructed_effective)

        leave_own_out_effective: np.ndarray | None = None
        if leave_own_out_adjacency is not None:
            leave_own_out_effective = np.asarray(leave_own_out_adjacency, dtype=float)
            if leave_own_out_effective.shape != (n_nodes, n_nodes):
                raise ValueError("leave_own_out_adjacency must match adjacency shape")
            leave_own_out_effective = _row_normalize(leave_own_out_effective)

        has_randomization = treatment is not None and assignment_probabilities is not None
        can_reconstruct = bool(metadata.get("can_reconstruct", reconstructed_effective is not None))
        has_external_iv = bool(metadata.get("has_external_iv", external_instruments is not None))
        has_panel = bool(metadata.get("has_panel", panel_outcomes_raw is not None))
        has_control_function = bool(
            metadata.get(
                "has_control_function",
                metadata.get(
                    "has_cf",
                    control_function_features is not None or control_function_residuals is not None,
                ),
            )
        )
        has_leave_own_out = bool(
            metadata.get(
                "has_leave_own_out",
                leave_own_out_effective is not None or leave_own_out_instruments is not None,
            )
        )
        network_endogenous = bool(
            metadata.get("network_endogenous", has_control_function or has_leave_own_out)
        )

        if use_component_fe:
            assumptions.append("component fixed effects remove time-invariant common shocks")
            robustness_checks.append("component_fixed_effects")

        def _prepare_cross_section(adjacency_matrix: np.ndarray) -> dict[str, Any]:
            normalized = _row_normalize(np.asarray(adjacency_matrix, dtype=float))
            if normalized.shape != (n_nodes, n_nodes):
                raise ValueError("adjacency route must match the base node universe")
            components_local = _component_labels(normalized)
            y_local = y_raw.copy()
            X_local = X_raw.copy()
            WY_local = normalized @ y_raw
            WX_local = normalized @ X_raw
            W2X_local = normalized @ WX_local
            W3X_local = normalized @ W2X_local
            if use_component_fe:
                y_local = _demean_by_labels(y_local, components_local)
                X_local = _demean_by_labels(X_local, components_local)
                WY_local = _demean_by_labels(WY_local, components_local)
                WX_local = _demean_by_labels(WX_local, components_local)
                W2X_local = _demean_by_labels(W2X_local, components_local)
                W3X_local = _demean_by_labels(W3X_local, components_local)
            if scale_mode == "standardized":
                y_local, _, _ = _safe_standardize(y_local)
                X_local, _, _ = _safe_standardize(X_local)
                WY_local, _, _ = _safe_standardize(WY_local)
                WX_local, _, _ = _safe_standardize(WX_local)
                W2X_local, _, _ = _safe_standardize(W2X_local)
                W3X_local, _, _ = _safe_standardize(W3X_local)
            rank_ok, cond = _rank_summary(_column_stack(X_local, WX_local, W2X_local))
            return {
                "adjacency": normalized,
                "components": components_local,
                "component_count": int(np.unique(components_local).size),
                "density": _density(normalized),
                "intransitivity": _intransitivity_index(normalized),
                "spectral_radius": _spectral_radius(normalized),
                "y": y_local,
                "X": X_local,
                "WY": WY_local,
                "WX": WX_local,
                "W2X": W2X_local,
                "W3X": W3X_local,
                "rank_condition_ok": rank_ok,
                "condition_number": cond,
            }

        def _transform_auxiliary(matrix: np.ndarray, labels: np.ndarray) -> np.ndarray:
            aux = _ensure_2d_features(np.asarray(matrix, dtype=float))
            if aux.shape[0] != labels.shape[0]:
                raise ValueError("auxiliary matrix must align with the transformed design")
            if use_component_fe:
                aux = _demean_by_labels(aux, labels)
            if scale_mode == "standardized":
                aux, _, _ = _safe_standardize(aux)
            return aux

        observed_design = _prepare_cross_section(adjacency)
        observed_intercept = None if use_component_fe else np.ones(n_nodes, dtype=float)
        observed_exog = _column_stack(
            observed_intercept, observed_design["X"], observed_design["WX"]
        )
        observed_excluded = _column_stack(observed_design["W2X"], observed_design["W3X"])
        observed_first_stage_f = _first_stage_f_stat(
            observed_design["WY"],
            observed_exog,
            observed_excluded,
        )
        if observed_first_stage_f is not None:
            robustness_checks.append("first_stage_f_proxy")
        observed_reduced_form_design = _column_stack(
            observed_intercept,
            observed_design["X"],
            observed_design["WX"],
        )
        observed_reduced_form_beta, observed_reduced_form_se, _ = _fit_ols(
            observed_design["y"],
            observed_reduced_form_design,
        )
        observed_reduced_form_index = (
            (0 if use_component_fe else 1) + observed_design["X"].shape[1] + focal_feature_index
        )
        reduced_form_interval = _interval_from_estimate(
            float(observed_reduced_form_beta[observed_reduced_form_index]),
            float(observed_reduced_form_se[observed_reduced_form_index]),
            ci_level=ci_level,
            units=contextual_units,
            method="reduced_form_ols",
        )

        if mobility_variation is None and panel_adjacency_raw is not None:
            panel_adjacency_arr = np.asarray(panel_adjacency_raw, dtype=float)
            if panel_adjacency_arr.ndim == 3 and panel_adjacency_arr.shape[0] >= 2:
                mobility_variation = float(
                    np.mean(
                        [
                            np.linalg.norm(panel_adjacency_arr[t] - panel_adjacency_arr[t - 1])
                            / max(n_nodes, 1)
                            for t in range(1, panel_adjacency_arr.shape[0])
                        ]
                    )
                )

        resolved_strategy = requested_strategy
        structural_block_reason: str | None = None
        if requested_strategy not in {
            "auto",
            "topology_iv",
            "external_iv",
            "panel",
            "control_function",
            "leave_own_out",
            "randomization",
            "graphical_reconstruction",
            "partial_id",
        }:
            structural_block_reason = "unknown_strategy"
            resolved_strategy = "partial_id"
            warnings.append(
                "Unknown peer-effects strategy requested; falling back to partial identification."
            )
        elif requested_strategy == "partial_id":
            structural_block_reason = "partial_id_requested"
            resolved_strategy = "partial_id"
        elif requested_strategy == "auto":
            if observability_rate < min_observability:
                if can_reconstruct:
                    resolved_strategy = "graphical_reconstruction"
                else:
                    structural_block_reason = "not_identified_partial_network"
                    resolved_strategy = "partial_id"
            elif network_endogenous:
                if has_external_iv:
                    resolved_strategy = "external_iv"
                elif has_randomization:
                    resolved_strategy = "randomization"
                elif has_panel:
                    resolved_strategy = "panel"
                elif has_leave_own_out:
                    resolved_strategy = "leave_own_out"
                elif has_control_function:
                    resolved_strategy = "control_function"
                else:
                    structural_block_reason = "not_identified_endogenous_network"
                    resolved_strategy = "partial_id"
            elif has_randomization and (
                requested_model_class == "potential_outcomes_network"
                or bool(metadata.get("design_based", False))
            ):
                resolved_strategy = "randomization"
            elif has_panel and (
                requested_model_class == "dynamic_contagion"
                or bool(metadata.get("prefer_panel_strategy", False))
            ):
                resolved_strategy = "panel"
            elif has_external_iv and bool(metadata.get("prefer_external_iv", False)):
                resolved_strategy = "external_iv"
            else:
                resolved_strategy = "topology_iv"

        route_result: dict[str, Any] | None = None
        endogenous_interval: IntervalEstimate | None = None
        contextual_interval: IntervalEstimate | None = None
        total_interval: IntervalEstimate | None = None
        correlated_proxy: IntervalEstimate | None = None
        direct_effect: IntervalEstimate | None = None
        spillover_effect: IntervalEstimate | None = None
        contagion_effect: IntervalEstimate | None = None
        infectiousness_effect: IntervalEstimate | None = None
        effective_first_stage_f = observed_first_stage_f
        rank_condition_ok = bool(observed_design["rank_condition_ok"])
        condition_number = observed_design["condition_number"]
        component_count = int(observed_design["component_count"])
        density = float(observed_design["density"])
        intransitivity = float(observed_design["intransitivity"])
        spectral_radius = float(observed_design["spectral_radius"])
        model_class = "linear_in_means"
        route_components = observed_design["components"]
        weak_iv_flag = False
        provenance: dict[str, Any] = {
            "estimator_version": "1.0.0",
            "requested_strategy": requested_strategy,
            "resolved_strategy": resolved_strategy,
            "requested_model_class": requested_model_class,
            "focal_feature_index": focal_feature_index,
            "condition_number": condition_number,
            "network_endogenous": network_endogenous,
        }

        if structural_block_reason is None:
            if (
                resolved_strategy != "graphical_reconstruction"
                and observability_rate < min_observability
            ):
                structural_block_reason = "not_identified_partial_network"
            elif (
                resolved_strategy == "graphical_reconstruction" and reconstructed_effective is None
            ):
                structural_block_reason = (
                    "graphical_reconstruction_requires_reconstructed_adjacency"
                )
            elif resolved_strategy == "topology_iv" and network_endogenous:
                structural_block_reason = "topology_iv_forbidden_under_endogenous_network"
            elif resolved_strategy == "external_iv" and external_instruments is None:
                structural_block_reason = "external_iv_requires_instruments"
            elif resolved_strategy == "panel" and panel_outcomes_raw is None:
                structural_block_reason = "panel_requires_panel_outcomes"
            elif (
                resolved_strategy == "control_function"
                and control_function_features is None
                and control_function_residuals is None
            ):
                structural_block_reason = "control_function_requires_controls"
            elif (
                resolved_strategy == "leave_own_out"
                and leave_own_out_effective is None
                and leave_own_out_instruments is None
            ):
                structural_block_reason = "leave_own_out_requires_network_or_instruments"
            elif resolved_strategy == "randomization" and not has_randomization:
                structural_block_reason = "randomization_requires_assignment_probabilities"

        if structural_block_reason is None and resolved_strategy == "graphical_reconstruction":
            route_design = _prepare_cross_section(reconstructed_effective)
            rank_condition_ok = bool(route_design["rank_condition_ok"])
            condition_number = route_design["condition_number"]
            component_count = int(route_design["component_count"])
            density = float(route_design["density"])
            intransitivity = float(route_design["intransitivity"])
            spectral_radius = float(route_design["spectral_radius"])
            route_components = route_design["components"]
            provenance["graphical_reconstruction_draws"] = (
                int(reconstructed_samples.shape[0]) if reconstructed_samples is not None else 1
            )
            assumptions.append(
                "missing links are addressed through caller-supplied reconstructed network draws"
            )
            robustness_checks.append("graphical_reconstruction")
            if not rank_condition_ok:
                structural_block_reason = "not_identified_reflection"
            else:
                route_result = _estimate_linear_peer_model(
                    y=route_design["y"],
                    X=route_design["X"],
                    WY=route_design["WY"],
                    WX=route_design["WX"],
                    W2X=route_design["W2X"],
                    W3X=route_design["W3X"],
                    focal_feature_index=focal_feature_index,
                    ci_level=ci_level,
                    estimand_scale=estimand_scale,
                    use_intercept=not use_component_fe,
                )

        if structural_block_reason is None and resolved_strategy == "topology_iv":
            if not observed_design["rank_condition_ok"]:
                structural_block_reason = "not_identified_reflection"
            else:
                route_result = _estimate_linear_peer_model(
                    y=observed_design["y"],
                    X=observed_design["X"],
                    WY=observed_design["WY"],
                    WX=observed_design["WX"],
                    W2X=observed_design["W2X"],
                    W3X=observed_design["W3X"],
                    focal_feature_index=focal_feature_index,
                    ci_level=ci_level,
                    estimand_scale=estimand_scale,
                    use_intercept=not use_component_fe,
                )

        if structural_block_reason is None and resolved_strategy == "external_iv":
            external_iv_work = _transform_auxiliary(
                external_instruments, observed_design["components"]
            )
            rank_condition_ok, condition_number = _rank_summary(
                _column_stack(observed_design["X"], observed_design["WX"], external_iv_work)
            )
            assumptions.append(
                "external instruments satisfy exclusion for the peer-outcome channel"
            )
            robustness_checks.append("external_iv_route")
            if not rank_condition_ok:
                structural_block_reason = "external_iv_rank_failure"
            else:
                route_result = _estimate_linear_peer_model(
                    y=observed_design["y"],
                    X=observed_design["X"],
                    WY=observed_design["WY"],
                    WX=observed_design["WX"],
                    W2X=observed_design["W2X"],
                    W3X=observed_design["W3X"],
                    focal_feature_index=focal_feature_index,
                    ci_level=ci_level,
                    estimand_scale=estimand_scale,
                    use_intercept=not use_component_fe,
                    endogenous_wx=network_endogenous,
                    instrument_wx=external_iv_work if network_endogenous else None,
                    instrument_w2x=_column_stack(external_iv_work, observed_design["W2X"]),
                    instrument_w3x=observed_design["W3X"],
                )

        if structural_block_reason is None and resolved_strategy == "control_function":
            cf_blocks: list[np.ndarray] = []
            if control_function_features is not None:
                cf_blocks.append(
                    _transform_auxiliary(control_function_features, observed_design["components"])
                )
            if control_function_residuals is not None:
                cf_blocks.append(
                    _transform_auxiliary(control_function_residuals, observed_design["components"])
                )
            cf_controls = _column_stack(*cf_blocks) if cf_blocks else None
            assumptions.append(
                "control-function covariates capture endogenous network formation residuals"
            )
            robustness_checks.append("control_function")
            if cf_controls is None:
                structural_block_reason = "control_function_requires_controls"
            else:
                rank_condition_ok, condition_number = _rank_summary(
                    _column_stack(
                        observed_design["X"],
                        observed_design["WX"],
                        observed_design["W2X"],
                        cf_controls,
                    )
                )
                if not rank_condition_ok:
                    structural_block_reason = "control_function_rank_failure"
                else:
                    extra_instruments = (
                        _column_stack(
                            _transform_auxiliary(
                                external_instruments, observed_design["components"]
                            ),
                            observed_design["W2X"],
                        )
                        if external_instruments is not None
                        else observed_design["W2X"]
                    )
                    route_result = _estimate_linear_peer_model(
                        y=observed_design["y"],
                        X=observed_design["X"],
                        WY=observed_design["WY"],
                        WX=observed_design["WX"],
                        W2X=observed_design["W2X"],
                        W3X=observed_design["W3X"],
                        focal_feature_index=focal_feature_index,
                        ci_level=ci_level,
                        estimand_scale=estimand_scale,
                        use_intercept=not use_component_fe,
                        extra_exog=cf_controls,
                        instrument_w2x=extra_instruments,
                        instrument_w3x=observed_design["W3X"],
                    )

        if structural_block_reason is None and resolved_strategy == "leave_own_out":
            loo_wx = None
            loo_w2x = None
            loo_w3x = None
            if leave_own_out_effective is not None:
                loo_wx = leave_own_out_effective @ X_raw
                loo_w2x = leave_own_out_effective @ loo_wx
                loo_w3x = leave_own_out_effective @ loo_w2x
                loo_wx = _transform_auxiliary(loo_wx, observed_design["components"])
                loo_w2x = _transform_auxiliary(loo_w2x, observed_design["components"])
                loo_w3x = _transform_auxiliary(loo_w3x, observed_design["components"])
            loo_instruments = (
                _transform_auxiliary(leave_own_out_instruments, observed_design["components"])
                if leave_own_out_instruments is not None
                else loo_wx
            )
            assumptions.append(
                "leave-own-out network statistics are conditionally exogenous for ego outcomes"
            )
            robustness_checks.append("leave_own_out")
            if loo_instruments is None:
                structural_block_reason = "leave_own_out_requires_network_or_instruments"
            else:
                rank_condition_ok, condition_number = _rank_summary(
                    _column_stack(
                        observed_design["X"],
                        observed_design["WX"],
                        loo_instruments,
                        loo_w2x if loo_w2x is not None else observed_design["W2X"],
                    )
                )
                if not rank_condition_ok:
                    structural_block_reason = "leave_own_out_rank_failure"
                else:
                    route_result = _estimate_linear_peer_model(
                        y=observed_design["y"],
                        X=observed_design["X"],
                        WY=observed_design["WY"],
                        WX=observed_design["WX"],
                        W2X=observed_design["W2X"],
                        W3X=observed_design["W3X"],
                        focal_feature_index=focal_feature_index,
                        ci_level=ci_level,
                        estimand_scale=estimand_scale,
                        use_intercept=not use_component_fe,
                        endogenous_wx=True,
                        instrument_wx=loo_instruments,
                        instrument_w2x=loo_w2x if loo_w2x is not None else observed_design["W2X"],
                        instrument_w3x=loo_w3x if loo_w3x is not None else observed_design["W3X"],
                    )

        if structural_block_reason is None and resolved_strategy == "panel":
            panel_outcomes = _normalize_panel_outcomes(
                np.asarray(panel_outcomes_raw, dtype=float), n_nodes
            )
            n_periods = int(panel_outcomes.shape[0])
            if n_periods < 2:
                structural_block_reason = "panel_requires_two_waves"
            else:
                if panel_features_raw is None:
                    panel_features = np.repeat(X_raw[None, :, :], repeats=n_periods, axis=0)
                else:
                    panel_features = _normalize_panel_features(
                        np.asarray(panel_features_raw, dtype=float), n_nodes
                    )
                    if panel_features.shape[0] != n_periods:
                        raise ValueError("panel_features must have one slice per panel wave")
                if panel_adjacency_raw is None:
                    panel_adjacency = np.repeat(adjacency[None, :, :], repeats=n_periods, axis=0)
                else:
                    raw_panel_adjacency = np.asarray(panel_adjacency_raw, dtype=float)
                    if raw_panel_adjacency.ndim == 2:
                        panel_adjacency = np.repeat(
                            raw_panel_adjacency[None, :, :], repeats=n_periods, axis=0
                        )
                    else:
                        panel_adjacency = _normalize_panel_adjacency(raw_panel_adjacency, n_nodes)
                        if panel_adjacency.shape[0] != n_periods:
                            raise ValueError("panel_adjacency must have one slice per panel wave")
                mobility_variation = float(
                    mobility_variation
                    if mobility_variation is not None
                    else np.mean(
                        [
                            np.linalg.norm(panel_adjacency[t] - panel_adjacency[t - 1])
                            / max(n_nodes, 1)
                            for t in range(1, n_periods)
                        ]
                    )
                )
                assumptions.append(
                    "panel route uses first differences with lagged peer outcomes to soften simultaneity"
                )
                robustness_checks.extend(["panel_first_difference", "mover_variation"])

                diff_y_blocks: list[np.ndarray] = []
                diff_x_blocks: list[np.ndarray] = []
                lag_peer_y_blocks: list[np.ndarray] = []
                diff_wx_blocks: list[np.ndarray] = []
                w2x_blocks: list[np.ndarray] = []
                w3x_blocks: list[np.ndarray] = []
                for t in range(1, n_periods):
                    W_t = _row_normalize(panel_adjacency[t])
                    W_tm1 = _row_normalize(panel_adjacency[t - 1])
                    y_t = panel_outcomes[t]
                    y_tm1 = panel_outcomes[t - 1]
                    X_t = panel_features[t]
                    X_tm1 = panel_features[t - 1]
                    wx_t = W_t @ X_t
                    wx_tm1 = W_tm1 @ X_tm1
                    diff_y_blocks.append(y_t - y_tm1)
                    diff_x_blocks.append(X_t - X_tm1)
                    lag_peer_y_blocks.append(W_t @ y_tm1)
                    diff_wx_blocks.append(wx_t - wx_tm1)
                    w2x_blocks.append(W_t @ wx_t)
                    w3x_blocks.append(W_t @ (W_t @ wx_t))

                panel_y = np.concatenate(diff_y_blocks, axis=0)
                panel_X = np.concatenate(diff_x_blocks, axis=0)
                panel_WY = np.concatenate(lag_peer_y_blocks, axis=0)
                panel_WX = np.concatenate(diff_wx_blocks, axis=0)
                panel_W2X = np.concatenate(w2x_blocks, axis=0)
                panel_W3X = np.concatenate(w3x_blocks, axis=0)
                if scale_mode == "standardized":
                    panel_y, _, _ = _safe_standardize(panel_y)
                    panel_X, _, _ = _safe_standardize(panel_X)
                    panel_WY, _, _ = _safe_standardize(panel_WY)
                    panel_WX, _, _ = _safe_standardize(panel_WX)
                    panel_W2X, _, _ = _safe_standardize(panel_W2X)
                    panel_W3X, _, _ = _safe_standardize(panel_W3X)
                rank_condition_ok, condition_number = _rank_summary(
                    _column_stack(panel_X, panel_WX, panel_W2X)
                )
                density = float(
                    np.mean(
                        [_density(_row_normalize(panel_adjacency[t])) for t in range(n_periods)]
                    )
                )
                intransitivity = float(
                    np.mean(
                        [
                            _intransitivity_index(_row_normalize(panel_adjacency[t]))
                            for t in range(n_periods)
                        ]
                    )
                )
                spectral_radius = float(
                    np.mean(
                        [
                            _spectral_radius(_row_normalize(panel_adjacency[t]))
                            for t in range(n_periods)
                        ]
                    )
                )
                if not rank_condition_ok:
                    structural_block_reason = "panel_rank_failure"
                else:
                    route_result = _estimate_linear_peer_model(
                        y=panel_y,
                        X=panel_X,
                        WY=panel_WY,
                        WX=panel_WX,
                        W2X=panel_W2X,
                        W3X=panel_W3X,
                        focal_feature_index=focal_feature_index,
                        ci_level=ci_level,
                        estimand_scale=estimand_scale,
                        use_intercept=False,
                    )
                    route_components = np.tile(np.arange(n_nodes), n_periods - 1)
                    model_class = (
                        "dynamic_contagion"
                        if requested_model_class == "dynamic_contagion"
                        or panel_treatment_raw is not None
                        else "linear_in_means"
                    )
                    if panel_treatment_raw is not None:
                        panel_treatment = _normalize_panel_outcomes(
                            np.asarray(panel_treatment_raw, dtype=float), n_nodes
                        )
                        if panel_treatment.shape[0] != n_periods:
                            raise ValueError("panel_treatment must have one wave per panel period")
                        incident_y_blocks: list[np.ndarray] = []
                        own_treat_blocks: list[np.ndarray] = []
                        peer_outcome_blocks: list[np.ndarray] = []
                        peer_treat_blocks: list[np.ndarray] = []
                        level_x_blocks: list[np.ndarray] = []
                        for t in range(1, n_periods):
                            W_t = _row_normalize(panel_adjacency[t])
                            incident_y_blocks.append(panel_outcomes[t] - panel_outcomes[t - 1])
                            own_treat_blocks.append(panel_treatment[t])
                            peer_outcome_blocks.append(W_t @ panel_outcomes[t - 1])
                            peer_treat_blocks.append(W_t @ panel_treatment[t])
                            level_x_blocks.append(panel_features[t])
                        incident_y = np.concatenate(incident_y_blocks, axis=0)
                        own_treat = np.concatenate(own_treat_blocks, axis=0)
                        peer_outcome = np.concatenate(peer_outcome_blocks, axis=0)
                        peer_treat = np.concatenate(peer_treat_blocks, axis=0)
                        level_x = np.concatenate(level_x_blocks, axis=0)
                        if scale_mode == "standardized":
                            incident_y, _, _ = _safe_standardize(incident_y)
                            own_treat, _, _ = _safe_standardize(own_treat)
                            peer_outcome, _, _ = _safe_standardize(peer_outcome)
                            peer_treat, _, _ = _safe_standardize(peer_treat)
                            level_x, _, _ = _safe_standardize(level_x)
                        contagion_design = _column_stack(
                            np.ones(incident_y.shape[0], dtype=float),
                            own_treat,
                            peer_outcome,
                            peer_treat,
                            level_x,
                        )
                        contagion_beta, contagion_se, contagion_residuals = _fit_ols(
                            incident_y, contagion_design
                        )
                        units = "SD(y)" if estimand_scale == "standardized" else "outcome-units"
                        direct_effect = _interval_from_estimate(
                            float(contagion_beta[1]),
                            float(contagion_se[1]),
                            ci_level=ci_level,
                            units=units,
                            method="panel_ols",
                        )
                        contagion_effect = _interval_from_estimate(
                            float(contagion_beta[2]),
                            float(contagion_se[2]),
                            ci_level=ci_level,
                            units=units,
                            method="panel_ols",
                        )
                        infectiousness_effect = _interval_from_estimate(
                            float(contagion_beta[3]),
                            float(contagion_se[3]),
                            ci_level=ci_level,
                            units=units,
                            method="panel_ols",
                        )
                        spillover_effect = infectiousness_effect
                        if np.std(contagion_residuals) > 1e-12 and np.std(peer_outcome) > 1e-12:
                            proxy_estimate = float(
                                np.corrcoef(contagion_residuals, peer_outcome)[0, 1]
                            )
                            correlated_proxy = _interval_from_estimate(
                                proxy_estimate,
                                None,
                                ci_level=ci_level,
                                units="correlation coefficient",
                                method="panel_residual_peer_correlation",
                            )
                            provenance["correlated_estimand"] = "panel_residual_peer_correlation"

        if structural_block_reason is None and resolved_strategy == "randomization":
            route_result = _estimate_randomization_effects(
                y=y_raw,
                X=X_raw,
                adjacency=adjacency,
                treatment=treatment,
                assignment_probabilities=assignment_probabilities,
                ci_level=ci_level,
                estimand_scale=estimand_scale,
            )
            assumptions.append("assignment probabilities and exposure mapping are treated as known")
            robustness_checks.extend(["randomization_weights", "exposure_mapping"])
            model_class = "potential_outcomes_network"

        if route_result is not None and resolved_strategy in {
            "topology_iv",
            "graphical_reconstruction",
            "external_iv",
            "control_function",
            "leave_own_out",
            "panel",
        }:
            effective_first_stage_f = route_result.get("first_stage_f")
            weak_iv_flag = (
                effective_first_stage_f is None or effective_first_stage_f < weak_iv_threshold
            )
            endogenous_interval = route_result.get("endogenous_effect")
            contextual_interval = route_result.get("contextual_effect")
            total_interval = route_result.get("total_peer_effect")
            reduced_form_interval = route_result.get(
                "reduced_form_peer_multiplier", reduced_form_interval
            )
            if (
                route_result.get("residuals") is not None
                and correlated_proxy is None
                and resolved_strategy != "panel"
            ):
                correlated_proxy, correlated_estimand = _correlated_proxy(
                    residuals=route_result["residuals"],
                    adjacency=adjacency
                    if resolved_strategy != "graphical_reconstruction"
                    else reconstructed_effective,
                    y_raw=y_raw,
                    components=route_components,
                    use_component_fe=use_component_fe,
                    ci_level=ci_level,
                )
                provenance["correlated_estimand"] = correlated_estimand
            provenance["gamma_coefficients"] = route_result.get("gamma_coefficients")
            provenance["delta_coefficients"] = route_result.get("delta_coefficients")
            provenance["first_stage_f_proxy"] = effective_first_stage_f
        elif route_result is not None and resolved_strategy == "randomization":
            weak_iv_flag = False
            direct_effect = route_result.get("direct_effect")
            spillover_effect = route_result.get("spillover_effect")
            total_interval = route_result.get("total_peer_effect")
            reduced_form_interval = route_result.get(
                "reduced_form_peer_multiplier", reduced_form_interval
            )
            provenance["design_coefficients"] = route_result.get("design_coefficients")
        else:
            weak_iv_flag = (
                observed_first_stage_f is None or observed_first_stage_f < weak_iv_threshold
            )

        if resolved_strategy != "panel" and resolved_strategy != "randomization":
            model_class = "linear_in_means"

        if (
            structural_block_reason is None
            and resolved_strategy
            in {
                "topology_iv",
                "graphical_reconstruction",
                "external_iv",
                "control_function",
                "leave_own_out",
            }
            and not rank_condition_ok
        ):
            structural_block_reason = "not_identified_reflection"

        bounds_scale = (
            1.0 if estimand_scale == "standardized" else max(float(np.std(y_raw)), 1.0e-6)
        )
        endogenous_bounds = None
        contextual_bounds = None
        if structural_block_reason is not None or (
            weak_iv_flag
            and resolved_strategy
            in {
                "topology_iv",
                "graphical_reconstruction",
                "external_iv",
                "control_function",
                "leave_own_out",
                "panel",
            }
            and route_result is not None
        ):
            if structural_block_reason is not None:
                assumptions.append(
                    "structural decomposition blocked; reporting reduced-form plus sensitivity bounds"
                )
            else:
                assumptions.append(
                    "weak first stage detected; sensitivity envelope complements asymptotic intervals"
                )
                robustness_checks.append("weak_iv_sensitivity_bounds")
            endogenous_bounds = _sensitivity_bounds(
                center=endogenous_interval.estimate if endogenous_interval is not None else 0.0,
                scale=bounds_scale,
                observability_rate=observability_rate,
                rank_condition_ok=rank_condition_ok,
                weak_flag=weak_iv_flag,
                explicit_radius=float(partial_id_radius) if partial_id_radius is not None else None,
            )
            contextual_bounds = _sensitivity_bounds(
                center=(
                    contextual_interval.estimate
                    if contextual_interval is not None
                    else (
                        reduced_form_interval.estimate if reduced_form_interval is not None else 0.0
                    )
                ),
                scale=bounds_scale,
                observability_rate=observability_rate,
                rank_condition_ok=rank_condition_ok,
                weak_flag=weak_iv_flag,
                explicit_radius=float(partial_id_radius) if partial_id_radius is not None else None,
            )

        if structural_block_reason is None:
            identification_status = (
                "weakly_identified"
                if weak_iv_flag and resolved_strategy != "randomization"
                else "identified"
            )
            strategy_used = resolved_strategy
        else:
            identification_status = (
                "partially_identified" if reduced_form_interval is not None else "not_identified"
            )
            strategy_used = "partial_id"
            warnings.append(f"Blocking mode activated: {structural_block_reason}.")

        if requested_model_class not in {"auto", model_class} and structural_block_reason is None:
            warnings.append(
                f"Requested model_class='{requested_model_class}' is incompatible with strategy '{resolved_strategy}'; returned '{model_class}'."
            )

        testable_implications = [
            "observability metadata must support the chosen identification route",
            "rank and exclusion restrictions must hold on the transformed design",
        ]
        if resolved_strategy in {
            "topology_iv",
            "graphical_reconstruction",
            "external_iv",
            "control_function",
            "leave_own_out",
        }:
            testable_implications.append(
                "excluded instruments are relevant for the peer-outcome channel"
            )
        if resolved_strategy == "panel":
            testable_implications.append(
                "future peers should not predict past outcomes under exogenous mobility"
            )
        if resolved_strategy == "randomization":
            testable_implications.append(
                "assignment probabilities must be strictly positive and correctly specified"
            )

        diagnostics = IdentificationDiagnostics(
            identification_status=identification_status,
            strategy_used=strategy_used,
            rank_condition_ok=rank_condition_ok,
            weak_iv_flag=weak_iv_flag if resolved_strategy != "randomization" else False,
            kp_rk_f=effective_first_stage_f,
            ar_p_value=None,
            overid_p_value=None,
            network_observability_rate=observability_rate,
            component_count=component_count,
            density=density,
            intransitivity_index=intransitivity,
            mobility_variation=float(mobility_variation)
            if mobility_variation is not None
            else None,
            spectral_radius_W=spectral_radius,
            blocking_reason=structural_block_reason,
            warnings=warnings,
        )

        decomposition = PeerEffectDecomposition(
            model_class=model_class,
            estimand_scale=estimand_scale,
            endogenous_effect=endogenous_interval if structural_block_reason is None else None,
            contextual_effect=contextual_interval if structural_block_reason is None else None,
            correlated_effect_proxy=correlated_proxy if structural_block_reason is None else None,
            direct_effect=direct_effect if structural_block_reason is None else None,
            spillover_effect=spillover_effect if structural_block_reason is None else None,
            total_peer_effect=total_interval if structural_block_reason is None else None,
            reduced_form_peer_multiplier=reduced_form_interval,
            contagion_effect=contagion_effect if structural_block_reason is None else None,
            infectiousness_effect=infectiousness_effect
            if structural_block_reason is None
            else None,
            endogenous_bounds=endogenous_bounds,
            contextual_bounds=contextual_bounds,
            diagnostics=diagnostics,
            assumptions=assumptions,
            testable_implications=testable_implications,
            data_requirements_met={
                "full_network_observed": observability_rate >= min_observability,
                "node_features_available": data.node_features is not None,
                "node_states_available": data.node_states is not None,
                "component_fixed_effects_applied": use_component_fe
                and resolved_strategy != "panel",
                "external_iv_available": external_instruments is not None,
                "panel_available": panel_outcomes_raw is not None,
                "randomization_available": has_randomization,
                "control_function_available": control_function_features is not None
                or control_function_residuals is not None,
                "leave_own_out_available": leave_own_out_effective is not None
                or leave_own_out_instruments is not None,
                "reconstruction_available": reconstructed_effective is not None,
            },
            robustness_checks_run=robustness_checks,
            provenance=provenance,
        )
        missingness_assessment = maybe_build_missingness_assessment(data, params)

        metrics = {
            "n_nodes": float(n_nodes),
            "density": density,
            "observability_rate": observability_rate,
        }
        if effective_first_stage_f is not None:
            metrics["first_stage_f_proxy"] = float(effective_first_stage_f)
        if mobility_variation is not None:
            metrics["mobility_variation"] = float(mobility_variation)
        embedding_fidelity_certificate = _network_embedding_fidelity_certificate(payload, params)

        return {
            "result": NetworkResult(
                method_name="peer_effect_decomposition",
                metrics=metrics,
                peer_effect_decomposition=decomposition,
                missingness_assessment=missingness_assessment,
                embedding_fidelity_certificate=embedding_fidelity_certificate,
                metadata=_network_result_metadata(
                    {
                        "focal_feature_index": focal_feature_index,
                        "requested_strategy": requested_strategy,
                        "resolved_strategy": resolved_strategy,
                        "requested_model_class": requested_model_class,
                        "rank_condition_ok": rank_condition_ok,
                    },
                    embedding_fidelity_certificate,
                ),
            )
        }


@foundry_method(
    namespace="network.contagion",
    version="1.0.0",
    tags={"network", "contagion-model"},
)
class ContagionModelEstimator:
    """Simulate SIS/SIR contagion over a weighted network; avoid homogeneous-mixing settings where compartmental ODEs are simpler."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="contagion_model",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "adjacency",
                    SlotType.MATRIX,
                    Unit("network", "weight"),
                    shape=("n_nodes", "n_nodes"),
                ),
                SlotSpec(
                    "node_states", SlotType.VECTOR, Unit("state", "value"), shape=("n_nodes",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="beta", default=0.4),
            ParameterSpec(name="gamma", default=0.1),
            ParameterSpec(name="n_steps", default=12),
            ParameterSpec(name="model_type", default="sis"),
        )
        + _missingness_passthrough_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Discrete-time SIS/SIR contagion model on a weighted network.",
        tags=frozenset({"network", "contagion-model"}),
        when_to_use="Spread of behavior, disease, or information on network; threshold models",
        citations=(
            "Kermack, W. & McKendrick, A. (1927). A contribution to the mathematical theory of epidemics. Proceedings of the Royal Society A, 115(772), 700-721.",
            "Pastor-Satorras, R. & Vespignani, A. (2001). Epidemic spreading in scale-free networks. Physical Review Letters, 86(14), 3200.",
        ),
        when_not_to_use="Non-network contagion; homogeneous mixing sufficient (use compartmental ODE); no adjacency data",
        output_interpretation="Cascade size and timing. R0>1 = systemic spread. Identification of superspreaders.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state)
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        rng = params.get("__rng__")
        if rng is None or not hasattr(rng, "uniform"):
            rng = np.random.default_rng(int(params.get("__seed__", 0)))
        data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
        payload = data.model_dump(mode="python")
        adjacency = _row_normalize(np.asarray(data.adjacency, dtype=float))
        infected = (np.asarray(data.node_states, dtype=float) > 0.0).astype(float)
        recovered = np.zeros_like(infected)
        beta = float(params.get("beta", 0.4))
        gamma = float(params.get("gamma", 0.1))
        n_steps = max(1, int(params.get("n_steps", 12)))
        model_type = str(params.get("model_type", "sis")).lower()
        trajectories = [infected.copy()]
        peak = float(np.mean(infected))
        for _ in range(n_steps):
            exposure = adjacency @ infected
            infection_prob = np.clip(beta * exposure, 0.0, 1.0)
            recovery_prob = np.clip(np.full_like(infected, gamma), 0.0, 1.0)
            new_infected = (
                (rng.uniform(size=infected.shape[0]) < infection_prob)
                & (infected < 0.5)
                & (recovered < 0.5)
            ).astype(float)
            recoveries = (
                (rng.uniform(size=infected.shape[0]) < recovery_prob) & (infected > 0.5)
            ).astype(float)
            infected = np.clip(infected + new_infected - recoveries, 0.0, 1.0)
            if model_type == "sir":
                recovered = np.clip(recovered + recoveries, 0.0, 1.0)
            trajectories.append(infected.copy())
            peak = max(peak, float(np.mean(infected)))
        traj = np.asarray(trajectories, dtype=float)
        missingness_assessment = maybe_build_missingness_assessment(data, params)
        embedding_fidelity_certificate = _network_embedding_fidelity_certificate(payload, params)
        return {
            "result": NetworkResult(
                method_name="contagion_model",
                metrics={
                    "final_prevalence": float(np.mean(traj[-1])),
                    "peak_prevalence": peak,
                },
                node_scores=traj[-1],
                state_trajectories=traj,
                missingness_assessment=missingness_assessment,
                embedding_fidelity_certificate=embedding_fidelity_certificate,
                metadata=_network_result_metadata(
                    {"model_type": model_type, "recovered_share": float(np.mean(recovered))},
                    embedding_fidelity_certificate,
                ),
            )
        }


@foundry_method(
    namespace="network.multiplex",
    version="1.0.0",
    tags={"network", "multiplex-network"},
)
class MultiplexNetworkEstimator:
    """Summarize multi-layer network structure across aligned adjacency layers; avoid layer sets with incompatible node universes."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="multiplex_network",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "adjacency_layers",
                    SlotType.TENSOR,
                    Unit("network", "weight"),
                    shape=("n_layers", "n_nodes", "n_nodes"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=_missingness_passthrough_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Multiplex network analytics over several adjacency layers.",
        tags=frozenset({"network", "multiplex-network"}),
        when_to_use="Networks with multiple relationship types (trade, social, information); multilayer network analysis",
        citations=(
            "Kivela, M. et al. (2014). Multilayer networks. Journal of Complex Networks, 2(3), 203-271.",
        ),
        when_not_to_use="Single-layer network; layers are not meaningfully distinct; no inter-layer coupling",
        output_interpretation="Aggregate centrality across layers. Interlayer difference = divergence across network types. Dominant eigenvector = cross-layer influential nodes.",
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any], fallback_state: Any
    ) -> MultiplexNetworkData:
        payload = _multiplex_payload(fallback_state)
        payload.update(bound_inputs)
        return MultiplexNetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: MultiplexNetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, MultiplexNetworkData)
            else MultiplexNetworkData.model_validate(state)
        )
        payload = data.model_dump(mode="python")
        layers = np.asarray(data.adjacency_layers, dtype=float)
        aggregate = np.mean(layers, axis=0)
        overlap = float(
            np.mean(
                [
                    np.mean(np.abs(layers[i] - layers[j]))
                    for i in range(layers.shape[0])
                    for j in range(i + 1, layers.shape[0])
                ]
            )
        )
        eigvals, eigvecs = np.linalg.eig(_symmetrize(aggregate))
        dominant = np.real(eigvecs[:, int(np.argmax(np.real(eigvals)))])
        dominant = np.abs(dominant)
        if np.sum(dominant) > 0:
            dominant = dominant / np.sum(dominant)
        aggregate_network = NetworkData(
            adjacency=aggregate,
            node_features=data.node_features,
            node_ids=data.node_ids,
            metadata=data.metadata,
        )
        missingness_assessment = maybe_build_missingness_assessment(aggregate_network, params)
        embedding_fidelity_certificate = _network_embedding_fidelity_certificate(payload, params)
        return {
            "result": NetworkResult(
                method_name="multiplex_network",
                metrics={
                    "mean_interlayer_difference": overlap,
                    "aggregate_density": float(np.mean(aggregate > 0)),
                },
                node_scores=dominant,
                missingness_assessment=missingness_assessment,
                embedding_fidelity_certificate=embedding_fidelity_certificate,
                metadata=_network_result_metadata(
                    {
                        "aggregate_adjacency": aggregate.tolist(),
                        "missingness_projection": "aggregate_layer_mean"
                        if missingness_assessment is not None
                        else None,
                    },
                    embedding_fidelity_certificate,
                ),
            )
        }


__all__ = [
    "CommunityDetectionEstimator",
    "ContagionModelEstimator",
    "InputOutputNetworkEstimator",
    "MultiplexNetworkEstimator",
    "NetworkDiffusionEstimator",
    "NetworkMissingnessAssessmentEstimator",
    "PeerEffectDecompositionEstimator",
]
