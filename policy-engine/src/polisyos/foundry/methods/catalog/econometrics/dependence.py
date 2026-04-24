"""Shared cross-sectional dependence routing helpers for panel-like estimators."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from statistics import NormalDist
from typing import Any

import numpy as np

from .protocols import CrossSectionalDependenceDiagnostic, EconometricDiagnosticResult

_FLOAT_EPS = 1e-12
_PERMUTATIONS = 199


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


def _normal_p_value(statistic: float | None) -> float | None:
    if statistic is None or not np.isfinite(statistic):
        return None
    tail = 1.0 - NormalDist().cdf(abs(float(statistic)))
    return float(min(max(2.0 * tail, 0.0), 1.0))


def _to_1d_array(value: Any, *, expected_size: int | None = None) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value)
    if arr.ndim != 1:
        return None
    if expected_size is not None and arr.shape[0] != expected_size:
        return None
    return arr


def _panel_residual_matrix(
    residuals: Any,
    *,
    entity_ids: Any,
    time_ids: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    resid = np.asarray(residuals, dtype=float).reshape(-1)
    entity = np.asarray(entity_ids).reshape(-1)
    time = np.asarray(time_ids).reshape(-1)
    if resid.shape[0] != entity.shape[0] or resid.shape[0] != time.shape[0]:
        raise ValueError("residuals, entity_ids, and time_ids must have the same length")

    order = np.lexsort((time, entity))
    resid = resid[order]
    entity = entity[order]
    time = time[order]

    unique_entities, entity_index = np.unique(entity, return_inverse=True)
    unique_times, time_index = np.unique(time, return_inverse=True)
    matrix = np.full((unique_entities.size, unique_times.size), np.nan, dtype=float)
    counts = np.zeros_like(matrix, dtype=int)

    for value, entity_pos, time_pos in zip(resid, entity_index, time_index, strict=False):
        if not np.isfinite(value):
            continue
        if counts[entity_pos, time_pos] == 0:
            matrix[entity_pos, time_pos] = value
        else:
            matrix[entity_pos, time_pos] += value
        counts[entity_pos, time_pos] += 1

    repeated = counts > 1
    if repeated.any():
        matrix[repeated] = matrix[repeated] / counts[repeated]

    return matrix, unique_entities, unique_times


def _pairwise_correlations(
    matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n_entities = matrix.shape[0]
    pairs_i: list[int] = []
    pairs_j: list[int] = []
    correlations: list[float] = []
    overlaps: list[int] = []

    for left in range(n_entities):
        x_raw = matrix[left]
        x_mask = np.isfinite(x_raw)
        for right in range(left + 1, n_entities):
            y_raw = matrix[right]
            mask = x_mask & np.isfinite(y_raw)
            overlap = int(mask.sum())
            if overlap < 3:
                continue
            x = x_raw[mask] - np.nanmean(x_raw[mask])
            y = y_raw[mask] - np.nanmean(y_raw[mask])
            denom = float(np.linalg.norm(x) * np.linalg.norm(y))
            if denom <= _FLOAT_EPS:
                continue
            rho = float(np.dot(x, y) / denom)
            pairs_i.append(left)
            pairs_j.append(right)
            correlations.append(float(np.clip(rho, -1.0, 1.0)))
            overlaps.append(overlap)

    return (
        np.asarray(pairs_i, dtype=int),
        np.asarray(pairs_j, dtype=int),
        np.asarray(correlations, dtype=float),
        np.asarray(overlaps, dtype=int),
    )


def _pairwise_summary(
    correlations: np.ndarray,
    overlaps: np.ndarray,
) -> dict[str, float | int | bool | None]:
    n_pairs = int(correlations.size)
    if n_pairs == 0:
        return {
            "n_pairs": 0,
            "avg_overlap": 0.0,
            "mean_corr": None,
            "mean_abs_corr": None,
            "statistic": None,
            "p_value": None,
            "balanced_like": False,
        }
    avg_overlap = float(np.mean(overlaps))
    stat = float(np.sum(correlations) * np.sqrt(max(avg_overlap, 1.0) / n_pairs))
    return {
        "n_pairs": n_pairs,
        "avg_overlap": avg_overlap,
        "mean_corr": float(np.mean(correlations)),
        "mean_abs_corr": float(np.mean(np.abs(correlations))),
        "statistic": stat,
        "p_value": _normal_p_value(stat),
        "balanced_like": bool(np.std(overlaps) < 1e-6),
    }


def _build_cd_result(
    test_name: str,
    *,
    summary: Mapping[str, float | int | bool | None],
    alpha: float,
) -> EconometricDiagnosticResult:
    p_value = _safe_float(summary.get("p_value"))
    mean_abs_corr = _safe_float(summary.get("mean_abs_corr"))
    passed = bool(
        (p_value is not None and p_value >= alpha)
        or (mean_abs_corr is not None and mean_abs_corr < 0.10)
    )
    return EconometricDiagnosticResult(
        test_name=test_name,
        statistic=_safe_float(summary.get("statistic")),
        p_value=p_value,
        passed=passed,
        metadata={
            "n_pairs": int(summary.get("n_pairs", 0) or 0),
            "avg_overlap": _safe_float(summary.get("avg_overlap")),
            "mean_corr": _safe_float(summary.get("mean_corr")),
            "mean_abs_corr": mean_abs_corr,
            "balanced_like": bool(summary.get("balanced_like", False)),
        },
    )


def _time_center_matrix(matrix: np.ndarray) -> np.ndarray:
    centered = matrix.copy()
    col_means = np.nanmean(centered, axis=0)
    col_means = np.where(np.isfinite(col_means), col_means, 0.0)
    centered = centered - col_means[np.newaxis, :]
    return centered


def _factor_metrics(matrix: np.ndarray) -> dict[str, float | int | None]:
    centered = _time_center_matrix(matrix)
    fill_values = np.nanmean(centered, axis=0)
    fill_values = np.where(np.isfinite(fill_values), fill_values, 0.0)
    completed = np.where(np.isfinite(centered), centered, fill_values[np.newaxis, :])
    if completed.shape[0] < 2 or completed.shape[1] < 2:
        return {
            "factor_count": 0,
            "dominant_share": 0.0,
            "spectral_gap": 0.0,
            "leading_eigenvalue": 0.0,
            "alpha_hat": 0.0,
        }

    covariance = completed @ completed.T / max(completed.shape[1], 1)
    eigenvalues = np.linalg.eigvalsh(covariance)
    eigenvalues = np.sort(np.clip(eigenvalues, 0.0, None))[::-1]
    if eigenvalues.size == 0 or float(np.sum(eigenvalues)) <= _FLOAT_EPS:
        return {
            "factor_count": 0,
            "dominant_share": 0.0,
            "spectral_gap": 0.0,
            "leading_eigenvalue": 0.0,
            "alpha_hat": 0.0,
        }

    total = float(np.sum(eigenvalues))
    leading_eigenvalue = float(eigenvalues[0])
    dominant_share = float(eigenvalues[0] / total)
    baseline = (
        float(np.median(eigenvalues[eigenvalues > _FLOAT_EPS]))
        if np.any(eigenvalues > _FLOAT_EPS)
        else 0.0
    )
    threshold = max(baseline * 2.5, total * 0.05)
    factor_count = int(np.sum(eigenvalues > threshold))
    spectral_gap = (
        float(eigenvalues[0] / max(eigenvalues[1], _FLOAT_EPS))
        if eigenvalues.size > 1
        else float("inf")
    )
    alpha_hat = float(
        np.clip(
            np.log(max(leading_eigenvalue, 1.0)) / np.log(max(completed.shape[0], 2)),
            0.0,
            1.0,
        )
    )
    return {
        "factor_count": factor_count,
        "dominant_share": dominant_share,
        "spectral_gap": spectral_gap,
        "leading_eigenvalue": leading_eigenvalue,
        "alpha_hat": alpha_hat,
    }


def _build_factor_result(metrics: Mapping[str, float | int | None]) -> EconometricDiagnosticResult:
    dominant_share = _safe_float(metrics.get("dominant_share")) or 0.0
    factor_count = int(metrics.get("factor_count", 0) or 0)
    spectral_gap = _safe_float(metrics.get("spectral_gap"))
    passed = bool(factor_count == 0 or dominant_share < 0.35)
    return EconometricDiagnosticResult(
        test_name="latent_factor_screen",
        statistic=dominant_share,
        p_value=None,
        passed=passed,
        critical_value=0.35,
        metadata={
            "factor_count": factor_count,
            "dominant_share": dominant_share,
            "spectral_gap": spectral_gap,
        },
    )


def _align_entity_metadata(
    value: Any,
    *,
    entity_obs: np.ndarray,
    unique_entities: np.ndarray,
) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value)
    if arr.ndim == 2 and 1 in arr.shape:
        arr = arr.reshape(-1)
    if arr.ndim == 1 and arr.shape[0] == unique_entities.shape[0]:
        return arr
    if arr.ndim == 1 and arr.shape[0] == entity_obs.shape[0]:
        aligned = np.empty(unique_entities.shape[0], dtype=arr.dtype)
        for pos, entity in enumerate(unique_entities):
            values = arr[entity_obs == entity]
            if values.size == 0:
                return None
            aligned[pos] = values[0]
            if np.any(values != values[0]):
                return None
        return aligned
    return None


def _pair_mask_statistic(
    correlations: np.ndarray,
    positive_mask: np.ndarray,
) -> float | None:
    if correlations.size == 0:
        return None
    if positive_mask.shape[0] != correlations.shape[0]:
        return None
    if not np.any(positive_mask) or np.all(positive_mask):
        return None
    within = np.abs(correlations[positive_mask])
    outside = np.abs(correlations[~positive_mask])
    if within.size == 0 or outside.size == 0:
        return None
    return float(np.mean(within) - np.mean(outside))


def _permutation_p_value(
    correlations: np.ndarray,
    *,
    observed: float | None,
    n_entities: int,
    mask_builder: Callable[[np.ndarray], np.ndarray],
) -> float | None:
    if observed is None or not np.isfinite(observed):
        return None
    n_pairs = correlations.shape[0]
    if n_pairs == 0:
        return None
    rng = np.random.default_rng(0)
    exceedances = 0
    for _ in range(_PERMUTATIONS):
        perm = rng.permutation(n_entities)
        mask = mask_builder(perm)
        stat = _pair_mask_statistic(correlations, mask)
        if stat is None:
            continue
        if abs(stat) >= abs(observed) - 1e-12:
            exceedances += 1
    return float((exceedances + 1) / (_PERMUTATIONS + 1))


def _block_screen(
    *,
    correlations: np.ndarray,
    pairs_i: np.ndarray,
    pairs_j: np.ndarray,
    cluster_ids: np.ndarray | None,
    alpha: float,
) -> tuple[EconometricDiagnosticResult | None, bool]:
    if cluster_ids is None or cluster_ids.shape[0] < 3 or correlations.size == 0:
        return None, False

    def mask_builder(candidate_ids: np.ndarray) -> np.ndarray:
        current = cluster_ids if candidate_ids.size == 0 else cluster_ids[candidate_ids]
        return current[pairs_i] == current[pairs_j]

    positive_mask = mask_builder(np.arange(0))
    observed = _pair_mask_statistic(correlations, positive_mask)
    p_value = _permutation_p_value(
        correlations,
        observed=observed,
        n_entities=int(cluster_ids.shape[0]),
        mask_builder=mask_builder,
    )
    passed = not (observed is not None and observed > 0.05 and (p_value is None or p_value < alpha))
    return (
        EconometricDiagnosticResult(
            test_name="block_dependence_screen",
            statistic=observed,
            p_value=p_value,
            passed=passed,
            critical_value=0.05,
            metadata={
                "n_clusters": int(np.unique(cluster_ids).size),
            },
        ),
        not passed,
    )


def _weights_from_coords(coords: np.ndarray) -> np.ndarray | None:
    if coords.ndim != 2 or coords.shape[0] < 3:
        return None
    n_entities = coords.shape[0]
    distances = np.linalg.norm(coords[:, np.newaxis, :] - coords[np.newaxis, :, :], axis=2)
    weights = np.zeros((n_entities, n_entities), dtype=float)
    n_neighbors = min(4, n_entities - 1)
    for row in range(n_entities):
        order = np.argsort(distances[row])
        neighbors = [idx for idx in order if idx != row][:n_neighbors]
        for neighbor in neighbors:
            distance = max(float(distances[row, neighbor]), 1e-6)
            weights[row, neighbor] = 1.0 / distance
    row_sums = weights.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums > 0.0, row_sums, 1.0)
    return weights / row_sums


def _spatial_or_network_screen(
    *,
    test_name: str,
    correlations: np.ndarray,
    pairs_i: np.ndarray,
    pairs_j: np.ndarray,
    weights: np.ndarray | None,
    alpha: float,
) -> tuple[EconometricDiagnosticResult | None, bool]:
    if (
        weights is None
        or weights.ndim != 2
        or weights.shape[0] != weights.shape[1]
        or correlations.size == 0
    ):
        return None, False
    neighbor_mask = weights[pairs_i, pairs_j] > 0.0
    observed = _pair_mask_statistic(correlations, neighbor_mask)
    p_value = None
    if observed is not None:
        rng = np.random.default_rng(0)
        exceedances = 0
        for _ in range(_PERMUTATIONS):
            perm = rng.permutation(weights.shape[0])
            perm_mask = weights[perm[pairs_i], perm[pairs_j]] > 0.0
            stat = _pair_mask_statistic(correlations, perm_mask)
            if stat is None:
                continue
            if abs(stat) >= abs(observed) - 1e-12:
                exceedances += 1
        p_value = float((exceedances + 1) / (_PERMUTATIONS + 1))
    passed = not (observed is not None and observed > 0.05 and (p_value is None or p_value < alpha))
    return (
        EconometricDiagnosticResult(
            test_name=test_name,
            statistic=observed,
            p_value=p_value,
            passed=passed,
            critical_value=0.05,
            metadata={
                "neighbor_pairs": int(np.sum(neighbor_mask)),
            },
        ),
        not passed,
    )


def _classify_strength(
    *,
    class_label: str,
    mean_abs_corr: float | None,
    dominant_share: float | None,
) -> str:
    if class_label == "none":
        return "none"
    if class_label == "weak_or_none":
        return "weak"
    if class_label == "factor":
        return "strong"
    if dominant_share is not None and dominant_share >= 0.45:
        return "strong"
    if mean_abs_corr is not None and mean_abs_corr >= 0.25:
        return "strong"
    if class_label in {"block", "spatial_local", "network_local", "common_shock_removed"}:
        return "weak"
    return "unknown"


def _recommended_covariance(
    class_label: str,
    n_clusters: int | None,
    *,
    method_context: str,
) -> str:
    if class_label in {"none", "weak_or_none", "common_shock_removed"}:
        if method_context == "dynamic_gmm":
            return "windmeijer"
        return "double_corrected_gmm"
    if class_label == "block":
        if n_clusters is not None and n_clusters <= 12:
            return "fixed_g_cluster"
        return "cluster"
    if class_label == "spatial_local":
        return "conley_spatial_hac"
    if class_label == "network_local":
        return "network_hac"
    if class_label == "factor":
        return "cce_reroute"
    return "none"


def _normalize_requested_covariance(value: Any) -> str:
    text = str(value or "auto").strip().lower()
    mapping = {
        "cluster": "cluster",
        "multiway_cluster": "multiway_cluster",
        "conley": "conley_spatial_hac",
        "conley_spatial_hac": "conley_spatial_hac",
        "network_hac": "network_hac",
        "windmeijer": "windmeijer",
        "double_corrected": "double_corrected_gmm",
        "double_corrected_gmm": "double_corrected_gmm",
        "fixed_g_cluster": "fixed_g_cluster",
    }
    return mapping.get(text, text)


def _estimator_status(
    *,
    class_label: str,
    dependence_fallback: str,
    covariance_applied: bool,
) -> str:
    if class_label in {"none", "weak_or_none", "common_shock_removed"}:
        return "ok"
    if class_label in {"block", "spatial_local", "network_local"}:
        if covariance_applied:
            return "ok"
        return "ok_conservative" if dependence_fallback == "conservative" else "reroute_required"
    if class_label in {"factor", "mixed"}:
        return "unsafe_for_default_inference"
    return "ok_conservative" if dependence_fallback == "conservative" else "reroute_required"


def route_cross_sectional_dependence(
    residuals: Any,
    *,
    entity_ids: Any,
    time_ids: Any,
    dependence_metadata: Mapping[str, Any] | None = None,
    used_time_dummies: bool = False,
    dependence_covariance: Any = "auto",
    dependence_fallback: str = "conservative",
    covariance_applied: bool = False,
    alpha: float = 0.05,
    method_context: str = "panel",
    shared_artifacts_ref: str | None = None,
) -> CrossSectionalDependenceDiagnostic:
    """Classify residual cross-sectional dependence and route downstream inference posture."""
    metadata = dict(dependence_metadata or {})
    entity_obs = np.asarray(entity_ids).reshape(-1)
    matrix, unique_entities, unique_times = _panel_residual_matrix(
        residuals,
        entity_ids=entity_ids,
        time_ids=time_ids,
    )

    pairs_i, pairs_j, correlations, overlaps = _pairwise_correlations(matrix)
    base_summary = _pairwise_summary(correlations, overlaps)
    base_cd = _build_cd_result("pesaran_cd", summary=base_summary, alpha=alpha)
    syr_cd = (
        _build_cd_result("syr_gmm_cd", summary=base_summary, alpha=alpha)
        if method_context == "dynamic_gmm"
        else None
    )

    centered_matrix = _time_center_matrix(matrix)
    centered_pairs = _pairwise_correlations(centered_matrix)
    centered_summary = _pairwise_summary(centered_pairs[2], centered_pairs[3])
    centered_cd = _build_cd_result("time_centered_cd", summary=centered_summary, alpha=alpha)
    centered_cd_star = _build_cd_result("pesaran_cd_star", summary=centered_summary, alpha=alpha)
    factor_metrics = _factor_metrics(centered_matrix)
    factor_result = _build_factor_result(factor_metrics)

    tests = [base_cd]
    if syr_cd is not None:
        tests.append(syr_cd)
    tests.extend([centered_cd, centered_cd_star, factor_result])
    structural_hits: list[str] = []

    cluster_ids = _align_entity_metadata(
        metadata.get("cluster_ids"), entity_obs=entity_obs, unique_entities=unique_entities
    )
    block_result, block_trigger = _block_screen(
        correlations=correlations,
        pairs_i=pairs_i,
        pairs_j=pairs_j,
        cluster_ids=cluster_ids,
        alpha=alpha,
    )
    if block_result is not None:
        tests.append(block_result)
    if block_trigger:
        structural_hits.append("block")

    coords = metadata.get("coords")
    coords_arr = np.asarray(coords) if coords is not None else None
    if coords_arr is not None and coords_arr.ndim == 1:
        coords_arr = coords_arr.reshape(-1, 1)
    aligned_coords = None
    if coords_arr is not None and coords_arr.ndim == 2:
        if coords_arr.shape[0] == unique_entities.shape[0]:
            aligned_coords = coords_arr
        elif coords_arr.shape[0] == entity_obs.shape[0]:
            index_map = {entity: pos for pos, entity in enumerate(unique_entities)}
            aligned_coords = np.zeros((unique_entities.shape[0], coords_arr.shape[1]), dtype=float)
            seen: set[int] = set()
            for entity_value, coord in zip(entity_obs, coords_arr, strict=False):
                pos = index_map.get(entity_value)
                if pos is None or pos in seen:
                    continue
                aligned_coords[pos] = coord
                seen.add(pos)

    weights = metadata.get("W")
    weights_arr = np.asarray(weights, dtype=float) if weights is not None else None
    if weights_arr is None and aligned_coords is not None:
        weights_arr = _weights_from_coords(np.asarray(aligned_coords, dtype=float))

    spatial_result, spatial_trigger = _spatial_or_network_screen(
        test_name="spatial_dependence_screen",
        correlations=correlations,
        pairs_i=pairs_i,
        pairs_j=pairs_j,
        weights=weights_arr,
        alpha=alpha,
    )
    if spatial_result is not None:
        tests.append(spatial_result)
    if spatial_trigger:
        structural_hits.append("spatial_local")

    graph = metadata.get("graph")
    graph_arr = None
    if isinstance(graph, Mapping) and "adjacency" in graph:
        graph_arr = np.asarray(graph["adjacency"], dtype=float)
    elif graph is not None:
        graph_arr = np.asarray(graph, dtype=float)

    network_result, network_trigger = _spatial_or_network_screen(
        test_name="network_dependence_screen",
        correlations=correlations,
        pairs_i=pairs_i,
        pairs_j=pairs_j,
        weights=graph_arr,
        alpha=alpha,
    )
    if network_result is not None:
        tests.append(network_result)
    if network_trigger:
        structural_hits.append("network_local")

    mean_abs_corr = _safe_float(base_summary.get("mean_abs_corr"))
    centered_mean_abs_corr = _safe_float(centered_summary.get("mean_abs_corr"))
    dominant_share = _safe_float(factor_metrics.get("dominant_share"))
    factor_count = int(factor_metrics.get("factor_count", 0) or 0)
    alpha_hat = _safe_float(factor_metrics.get("alpha_hat"))

    base_detected = bool((not base_cd.passed) or ((mean_abs_corr or 0.0) >= 0.10))
    dependence_removed_by_time_effects = bool(
        base_detected
        and mean_abs_corr is not None
        and centered_mean_abs_corr is not None
        and centered_mean_abs_corr <= max(0.15, 0.50 * mean_abs_corr)
        and (centered_cd.passed or (factor_count == 0 and (dominant_share or 0.0) < 0.35))
    )
    localized_eigen_structure = bool(
        structural_hits and factor_count > 0 and (dominant_share or 0.0) < 0.45
    )
    factor_trigger = bool(
        (not factor_result.passed)
        and not dependence_removed_by_time_effects
        and not localized_eigen_structure
    )

    if not base_detected and factor_count == 0:
        class_label = "none" if (mean_abs_corr or 0.0) < 0.05 else "weak_or_none"
    elif dependence_removed_by_time_effects and not structural_hits and factor_count == 0:
        class_label = "common_shock_removed"
    elif factor_trigger and structural_hits:
        class_label = "mixed"
    elif factor_trigger:
        class_label = "factor"
    elif len(structural_hits) > 1:
        class_label = "mixed"
    elif structural_hits:
        class_label = structural_hits[0]
    else:
        class_label = "inconclusive" if base_detected else "weak_or_none"

    recommended_covariance = _recommended_covariance(
        class_label,
        int(np.unique(cluster_ids).size) if cluster_ids is not None else None,
        method_context=method_context,
    )
    estimator_status = _estimator_status(
        class_label=class_label,
        dependence_fallback=str(dependence_fallback),
        covariance_applied=bool(covariance_applied),
    )

    requested_covariance = _normalize_requested_covariance(dependence_covariance)
    evidence: dict[str, Any] = {
        "n_entities": int(unique_entities.size),
        "n_periods": int(unique_times.size),
        "n_pairs": int(base_summary.get("n_pairs", 0) or 0),
        "mean_abs_corr": mean_abs_corr,
        "time_centered_mean_abs_corr": centered_mean_abs_corr,
        "dominant_factor_share": dominant_share,
        "leading_eigenvalue": _safe_float(factor_metrics.get("leading_eigenvalue")),
        "factor_count_proxy": factor_count,
        "alpha_hat": alpha_hat,
        "structural_hits": structural_hits,
        "requested_covariance": requested_covariance,
        "covariance_applied": bool(covariance_applied),
        "router_version": "phase1",
        "method_context": method_context,
    }
    if (
        requested_covariance not in {"auto", "none"}
        and requested_covariance != recommended_covariance
    ):
        evidence["forced_covariance_mismatch"] = {
            "requested": requested_covariance,
            "recommended": recommended_covariance,
        }

    return CrossSectionalDependenceDiagnostic(
        detected=class_label not in {"none", "weak_or_none"},
        class_label=class_label,
        strength=_classify_strength(
            class_label=class_label,
            mean_abs_corr=mean_abs_corr,
            dominant_share=dominant_share,
        ),
        estimator_status=estimator_status,
        recommended_covariance=recommended_covariance,
        tests=tests,
        factor_count=factor_count if factor_count > 0 else None,
        alpha_hat=alpha_hat,
        alpha_ci=None,
        used_time_dummies=used_time_dummies,
        dependence_removed_by_time_effects=dependence_removed_by_time_effects,
        evidence=evidence,
        shared_artifacts_ref=shared_artifacts_ref,
    )


__all__ = ["route_cross_sectional_dependence"]
