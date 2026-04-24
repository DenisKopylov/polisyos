"""Dynamic panel GMM estimators with dependence-aware inference posture."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, ClassVar

import numpy as np

try:  # pragma: no cover - exercised in full scientific environments.
    from scipy.stats import chi2, norm
    from scipy.stats import t as student_t
except ImportError:  # pragma: no cover - keeps IR/schema reflection importable.
    chi2 = None  # type: ignore[assignment]
    norm = None  # type: ignore[assignment]
    student_t = None  # type: ignore[assignment]

from polisyos.common.logger import get_logger
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    foundry_method,
)
from polisyos.foundry.methods.catalog._phase1_artifacts import resolve_artifact_store
from polisyos.ir.analytics.dependence_structure import (
    dependence_structure_from_econometrics,
    persist_dependence_structure,
)

from .dependence import route_cross_sectional_dependence
from .panel import (
    _apply_dependence_posture,
    _explicit_panel_input_slots,
    _feature_names,
    _materialize_panel_data,
    _panel_output_slots,
    _resolve_dependence_metadata,
)
from .protocols import EconometricResult, PanelData

logger = get_logger(__name__)

_FLOAT_EPS = 1e-12
_STANDARD_NORMAL = NormalDist()


def _normal_sf(value: float) -> float:
    if norm is not None:
        return float(norm.sf(value))
    return float(1.0 - _STANDARD_NORMAL.cdf(value))


def _student_t_ppf(probability: float, df: int) -> float:
    if student_t is not None:
        return float(student_t.ppf(probability, df))
    return float(_STANDARD_NORMAL.inv_cdf(probability))


def _student_t_sf(value: float, df: int) -> float:
    if student_t is not None:
        return float(student_t.sf(value, df))
    return _normal_sf(value)


@dataclass(frozen=True)
class _EntityDesign:
    y: np.ndarray
    X: np.ndarray
    Z: np.ndarray
    diff_rows: int


@dataclass(frozen=True)
class _DynamicPanelDesign:
    entities: tuple[_EntityDesign, ...]
    param_names: tuple[str, ...]
    method_name: str
    n_entities: int
    n_periods: int
    n_obs_input: int
    instrument_count: int
    stacked_observations: int
    diff_entity_ids: np.ndarray
    diff_time_ids: np.ndarray
    unique_entities: np.ndarray
    unique_times: np.ndarray


@dataclass(frozen=True)
class _GMMFit:
    beta: np.ndarray
    covariance: np.ndarray
    weight_matrix: np.ndarray
    zx: np.ndarray
    residuals_by_entity: tuple[np.ndarray, ...]
    diff_residuals: np.ndarray
    moment_vectors: np.ndarray
    hansen_stat: float | None
    hansen_df: int
    hansen_pvalue: float | None


@dataclass(frozen=True)
class _InferenceContext:
    covariance_kind: str
    distribution: str
    df: int | None
    warnings: tuple[str, ...] = ()


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


def _normalize_covariance_request(value: Any) -> str:
    text = str(value or "auto").strip().lower()
    mapping = {
        "cluster": "cluster",
        "multiway_cluster": "multiway_cluster",
        "fixed_g_cluster": "fixed_g_cluster",
        "conley": "conley_spatial_hac",
        "conley_spatial_hac": "conley_spatial_hac",
        "network_hac": "network_hac",
        "windmeijer": "windmeijer",
        "double_corrected": "double_corrected_gmm",
        "double_corrected_gmm": "double_corrected_gmm",
        "robust": "robust_gmm",
        "robust_gmm": "robust_gmm",
        "none": "none",
    }
    return mapping.get(text, text)


def _balanced_panel_arrays(
    state: PanelData,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray, np.ndarray]:
    order = np.lexsort((state.time_ids, state.entity_ids))
    dependent = np.asarray(state.dependent, dtype=float)[order]
    exog = np.asarray(state.exog, dtype=float)[order]
    entity_ids = np.asarray(state.entity_ids)[order]
    time_ids = np.asarray(state.time_ids)[order]
    instruments = (
        np.asarray(state.instrument_ids, dtype=float)[order]
        if state.instrument_ids is not None
        else None
    )

    unique_entities = np.unique(entity_ids)
    unique_times = np.unique(time_ids)
    n_entities = unique_entities.size
    n_periods = unique_times.size
    if dependent.shape[0] != n_entities * n_periods:
        raise ValueError("dynamic panel GMM currently requires a balanced panel")
    if n_periods < 4:
        raise ValueError("dynamic panel GMM requires at least 4 time periods")

    entity_lookup = {value: idx for idx, value in enumerate(unique_entities)}
    time_lookup = {value: idx for idx, value in enumerate(unique_times)}
    y = np.full((n_entities, n_periods), np.nan, dtype=float)
    x = np.full((n_entities, n_periods, exog.shape[1]), np.nan, dtype=float)
    z = (
        np.full((n_entities, n_periods, instruments.shape[1]), np.nan, dtype=float)
        if instruments is not None
        else None
    )
    counts = np.zeros((n_entities, n_periods), dtype=int)

    for row in range(dependent.shape[0]):
        entity_pos = entity_lookup[entity_ids[row]]
        time_pos = time_lookup[time_ids[row]]
        counts[entity_pos, time_pos] += 1
        if counts[entity_pos, time_pos] > 1:
            raise ValueError("dynamic panel GMM requires unique entity-time observations")
        y[entity_pos, time_pos] = dependent[row]
        x[entity_pos, time_pos, :] = exog[row]
        if z is not None:
            z[entity_pos, time_pos, :] = instruments[row]

    if np.any(counts != 1):
        raise ValueError("dynamic panel GMM requires a complete balanced panel without gaps")
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        raise ValueError("dynamic panel GMM inputs contain non-finite values")
    if z is not None and not np.isfinite(z).all():
        raise ValueError("dynamic panel GMM instruments contain non-finite values")
    return y, x, z, unique_entities, unique_times


def _max_lag_depth(n_periods: int, params: Mapping[str, Any]) -> int:
    value = params.get("max_lag_depth")
    if value is None:
        return max(2, n_periods - 2)
    depth = int(value)
    if depth < 2:
        raise ValueError("max_lag_depth must be at least 2")
    return min(depth, n_periods - 2)


def _instrument_count(
    *,
    n_periods: int,
    n_exog: int,
    n_external: int,
    system_gmm: bool,
    include_time_effects: bool,
    collapse_instruments: bool,
    max_lag_depth: int,
) -> int:
    diff_time = max(n_periods - 2, 0) if include_time_effects else 0
    level_time = diff_time if (include_time_effects and system_gmm) else 0
    if collapse_instruments:
        diff_count = (max_lag_depth - 1) + n_exog + n_external + diff_time
        if not system_gmm:
            return diff_count
        return diff_count + 1 + n_exog + n_external + level_time

    diff_y = sum(min(max_lag_depth, time_idx) - 1 for time_idx in range(2, n_periods))
    diff_exog = (n_periods - 2) * (n_exog + n_external)
    diff_count = diff_y + diff_exog + diff_time
    if not system_gmm:
        return diff_count
    level_count = (n_periods - 2) * (1 + n_exog + n_external) + level_time
    return diff_count + level_count


def _difference_time_basis(n_periods: int, time_idx: int, enabled: bool) -> np.ndarray:
    if not enabled:
        return np.empty(0, dtype=float)
    basis = np.zeros(n_periods - 2, dtype=float)
    basis[time_idx - 2] = 1.0
    return basis


def _level_time_basis(n_periods: int, time_idx: int, enabled: bool) -> np.ndarray:
    if not enabled:
        return np.empty(0, dtype=float)
    basis = np.zeros(n_periods - 2, dtype=float)
    basis[time_idx - 2] = 1.0
    return basis


def _populate_difference_instruments(
    row: int,
    time_idx: int,
    *,
    y_i: np.ndarray,
    dx_i: np.ndarray,
    dz_i: np.ndarray | None,
    z_row: np.ndarray,
    n_periods: int,
    n_exog: int,
    n_external: int,
    include_time_effects: bool,
    collapse_instruments: bool,
    max_lag_depth: int,
) -> None:
    if collapse_instruments:
        for lag in range(2, max_lag_depth + 1):
            source_idx = time_idx - lag
            if source_idx >= 0:
                z_row[lag - 2] = y_i[source_idx]
        offset = max_lag_depth - 1
        z_row[offset : offset + n_exog] = dx_i[time_idx - 1]
        offset += n_exog
        if dz_i is not None and n_external > 0:
            z_row[offset : offset + n_external] = dz_i[time_idx - 1]
            offset += n_external
        if include_time_effects:
            z_row[offset : offset + (n_periods - 2)] = _difference_time_basis(
                n_periods, time_idx, True
            )
        return

    offset = 0
    for current_time in range(2, n_periods):
        max_valid_lag = min(max_lag_depth, current_time)
        for lag in range(2, max_valid_lag + 1):
            if current_time == time_idx:
                z_row[offset] = y_i[current_time - lag]
            offset += 1
    for current_time in range(2, n_periods):
        if current_time == time_idx:
            z_row[offset : offset + n_exog] = dx_i[current_time - 1]
            if dz_i is not None and n_external > 0:
                z_row[offset + n_exog : offset + n_exog + n_external] = dz_i[current_time - 1]
        offset += n_exog + n_external
    if include_time_effects:
        z_row[offset : offset + (n_periods - 2)] = _difference_time_basis(n_periods, time_idx, True)


def _populate_level_instruments(
    row: int,
    time_idx: int,
    *,
    x_i: np.ndarray,
    z_i: np.ndarray | None,
    dy_i: np.ndarray,
    z_row: np.ndarray,
    n_periods: int,
    n_exog: int,
    n_external: int,
    include_time_effects: bool,
    collapse_instruments: bool,
    max_lag_depth: int,
    diff_instrument_count: int,
) -> None:
    if collapse_instruments:
        offset = diff_instrument_count
        z_row[offset] = dy_i[time_idx - 2]
        offset += 1
        z_row[offset : offset + n_exog] = x_i[time_idx]
        offset += n_exog
        if z_i is not None and n_external > 0:
            z_row[offset : offset + n_external] = z_i[time_idx]
            offset += n_external
        if include_time_effects:
            z_row[offset : offset + (n_periods - 2)] = _level_time_basis(n_periods, time_idx, True)
        return

    offset = diff_instrument_count
    for current_time in range(2, n_periods):
        if current_time == time_idx:
            z_row[offset] = dy_i[current_time - 2]
        offset += 1
    for current_time in range(2, n_periods):
        if current_time == time_idx:
            z_row[offset : offset + n_exog] = x_i[current_time]
            if z_i is not None and n_external > 0:
                z_row[offset + n_exog : offset + n_exog + n_external] = z_i[current_time]
        offset += n_exog + n_external
    if include_time_effects:
        z_row[offset : offset + (n_periods - 2)] = _level_time_basis(n_periods, time_idx, True)


def _build_design(
    state: PanelData,
    params: Mapping[str, Any],
    *,
    method_name: str,
    system_gmm: bool,
) -> _DynamicPanelDesign:
    y, x, z, unique_entities, unique_times = _balanced_panel_arrays(state)
    n_entities, n_periods = y.shape
    n_exog = x.shape[2]
    n_external = 0 if z is None else z.shape[2]
    include_time_effects = bool(params.get("include_time_effects", False))
    collapse_instruments = bool(params.get("collapse_instruments", True))
    max_lag_depth = _max_lag_depth(n_periods, params)
    diff_rows_per_entity = n_periods - 2
    if diff_rows_per_entity < 1:
        raise ValueError("dynamic panel GMM requires at least two post-lag observations")

    feature_names = _feature_names(state)
    param_names: list[str] = ["lagged_dependent", *feature_names]
    if include_time_effects:
        param_names.extend(f"diff_time[{unique_times[t]}]" for t in range(2, n_periods))
        if system_gmm:
            param_names.extend(f"level_time[{unique_times[t]}]" for t in range(2, n_periods))

    q = _instrument_count(
        n_periods=n_periods,
        n_exog=n_exog,
        n_external=n_external,
        system_gmm=system_gmm,
        include_time_effects=include_time_effects,
        collapse_instruments=collapse_instruments,
        max_lag_depth=max_lag_depth,
    )
    diff_instrument_count = _instrument_count(
        n_periods=n_periods,
        n_exog=n_exog,
        n_external=n_external,
        system_gmm=False,
        include_time_effects=include_time_effects,
        collapse_instruments=collapse_instruments,
        max_lag_depth=max_lag_depth,
    )

    entity_blocks: list[_EntityDesign] = []
    diff_entity_ids = np.repeat(unique_entities, diff_rows_per_entity)
    diff_time_ids = np.tile(unique_times[2:], n_entities)

    for entity_idx in range(n_entities):
        y_i = y[entity_idx]
        x_i = x[entity_idx]
        z_i = None if z is None else z[entity_idx]
        dy_i = np.diff(y_i)
        dx_i = np.diff(x_i, axis=0)
        dz_i = None if z_i is None else np.diff(z_i, axis=0)

        dep_rows: list[float] = []
        reg_rows: list[np.ndarray] = []
        z_rows = np.zeros(
            ((2 * diff_rows_per_entity) if system_gmm else diff_rows_per_entity, q),
            dtype=float,
        )

        for row, time_idx in enumerate(range(2, n_periods)):
            diff_reg = [np.array([dy_i[time_idx - 2]], dtype=float), dx_i[time_idx - 1]]
            if include_time_effects:
                diff_reg.append(_difference_time_basis(n_periods, time_idx, True))
            dep_rows.append(dy_i[time_idx - 1])
            reg_rows.append(np.concatenate(diff_reg))
            _populate_difference_instruments(
                row,
                time_idx,
                y_i=y_i,
                dx_i=dx_i,
                dz_i=dz_i,
                z_row=z_rows[row],
                n_periods=n_periods,
                n_exog=n_exog,
                n_external=n_external,
                include_time_effects=include_time_effects,
                collapse_instruments=collapse_instruments,
                max_lag_depth=max_lag_depth,
            )

        if system_gmm:
            for level_row, time_idx in enumerate(range(2, n_periods), start=diff_rows_per_entity):
                level_reg = [np.array([y_i[time_idx - 1]], dtype=float), x_i[time_idx]]
                if include_time_effects:
                    level_reg.append(_level_time_basis(n_periods, time_idx, True))
                dep_rows.append(y_i[time_idx])
                reg_rows.append(np.concatenate(level_reg))
                _populate_level_instruments(
                    level_row,
                    time_idx,
                    x_i=x_i,
                    z_i=z_i,
                    dy_i=dy_i,
                    z_row=z_rows[level_row],
                    n_periods=n_periods,
                    n_exog=n_exog,
                    n_external=n_external,
                    include_time_effects=include_time_effects,
                    collapse_instruments=collapse_instruments,
                    max_lag_depth=max_lag_depth,
                    diff_instrument_count=diff_instrument_count,
                )

        entity_blocks.append(
            _EntityDesign(
                y=np.asarray(dep_rows, dtype=float),
                X=np.vstack(reg_rows).astype(float),
                Z=z_rows,
                diff_rows=diff_rows_per_entity,
            )
        )

    stacked_rows = diff_rows_per_entity * n_entities * (2 if system_gmm else 1)
    return _DynamicPanelDesign(
        entities=tuple(entity_blocks),
        param_names=tuple(param_names),
        method_name=method_name,
        n_entities=n_entities,
        n_periods=n_periods,
        n_obs_input=state.n_obs,
        instrument_count=q,
        stacked_observations=stacked_rows,
        diff_entity_ids=np.asarray(diff_entity_ids),
        diff_time_ids=np.asarray(diff_time_ids),
        unique_entities=unique_entities,
        unique_times=unique_times,
    )


def _solve_gmm(
    zx: np.ndarray,
    zy: np.ndarray,
    weight_matrix: np.ndarray,
) -> np.ndarray:
    system = zx.T @ weight_matrix @ zx
    rhs = zx.T @ weight_matrix @ zy
    return np.linalg.pinv(system) @ rhs


def _symmetrize(matrix: np.ndarray) -> np.ndarray:
    return 0.5 * (matrix + matrix.T)


def _fit_gmm(design: _DynamicPanelDesign, *, step_count: int) -> _GMMFit:
    n_entities = design.n_entities
    zx = sum(entity.Z.T @ entity.X for entity in design.entities) / n_entities
    zy = sum(entity.Z.T @ entity.y for entity in design.entities) / n_entities
    ztz = sum(entity.Z.T @ entity.Z for entity in design.entities) / n_entities
    weight_matrix = np.linalg.pinv(_symmetrize(ztz))
    beta = _solve_gmm(zx, zy, weight_matrix)

    for _ in range(max(step_count - 1, 0)):
        residuals_by_entity = tuple(entity.y - entity.X @ beta for entity in design.entities)
        moment_vectors = np.vstack(
            [
                entity.Z.T @ residual
                for entity, residual in zip(design.entities, residuals_by_entity, strict=False)
            ]
        )
        covariance = _symmetrize(moment_vectors.T @ moment_vectors / n_entities)
        weight_matrix = np.linalg.pinv(covariance)
        beta = _solve_gmm(zx, zy, weight_matrix)

    residuals_by_entity = tuple(entity.y - entity.X @ beta for entity in design.entities)
    diff_residuals = np.concatenate(
        [
            residual[: entity.diff_rows]
            for entity, residual in zip(design.entities, residuals_by_entity, strict=False)
        ]
    )
    moment_vectors = np.vstack(
        [
            entity.Z.T @ residual
            for entity, residual in zip(design.entities, residuals_by_entity, strict=False)
        ]
    )
    base_s = _symmetrize(moment_vectors.T @ moment_vectors / n_entities)
    base_covariance = _symmetrize(
        np.linalg.pinv(zx.T @ weight_matrix @ zx)
        @ (zx.T @ weight_matrix @ base_s @ weight_matrix @ zx)
        @ np.linalg.pinv(zx.T @ weight_matrix @ zx)
        / n_entities
    )

    g_bar = np.mean(moment_vectors, axis=0)
    hansen_df = max(moment_vectors.shape[1] - beta.shape[0], 0)
    hansen_stat = None
    hansen_pvalue = None
    if hansen_df > 0:
        stat = float(n_entities * (g_bar.T @ weight_matrix @ g_bar))
        if np.isfinite(stat) and stat >= 0.0:
            hansen_stat = stat
            hansen_pvalue = float(chi2.sf(stat, hansen_df)) if chi2 is not None else None

    return _GMMFit(
        beta=beta,
        covariance=base_covariance,
        weight_matrix=weight_matrix,
        zx=zx,
        residuals_by_entity=residuals_by_entity,
        diff_residuals=diff_residuals,
        moment_vectors=moment_vectors,
        hansen_stat=hansen_stat,
        hansen_df=hansen_df,
        hansen_pvalue=hansen_pvalue,
    )


def _align_entity_metadata(
    value: Any,
    *,
    entity_ids: np.ndarray,
    unique_entities: np.ndarray,
) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value)
    if arr.ndim == 2 and 1 in arr.shape:
        arr = arr.reshape(-1)
    if arr.ndim == 1 and arr.shape[0] == unique_entities.shape[0]:
        return arr
    if arr.ndim == 1 and arr.shape[0] == entity_ids.shape[0]:
        aligned = []
        for entity_value in unique_entities:
            values = arr[entity_ids == entity_value]
            if values.size == 0:
                return None
            reference = values[0]
            if np.any(values != reference):
                return None
            aligned.append(reference)
        return np.asarray(aligned)
    return None


def _align_entity_matrix(
    value: Any,
    *,
    entity_ids: np.ndarray,
    unique_entities: np.ndarray,
) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        return None
    if arr.shape[0] == unique_entities.shape[0]:
        return arr
    if arr.shape[0] == entity_ids.shape[0]:
        aligned = np.zeros((unique_entities.shape[0], arr.shape[1]), dtype=float)
        for idx, entity_value in enumerate(unique_entities):
            values = arr[entity_ids == entity_value]
            if values.shape[0] == 0:
                return None
            reference = values[0]
            if np.any(np.abs(values - reference) > 1e-12):
                return None
            aligned[idx] = reference
        return aligned
    return None


def _weights_from_coords(coords: np.ndarray) -> np.ndarray | None:
    if coords.ndim != 2 or coords.shape[0] < 3:
        return None
    distances = np.linalg.norm(coords[:, np.newaxis, :] - coords[np.newaxis, :, :], axis=2)
    positive = distances[distances > _FLOAT_EPS]
    if positive.size == 0:
        return None
    cutoff = float(np.quantile(positive, 0.35))
    cutoff = max(cutoff, float(np.min(positive)))
    kernel = np.maximum(1.0 - (distances / max(cutoff, _FLOAT_EPS)), 0.0)
    np.fill_diagonal(kernel, 1.0)
    return kernel


def _moment_covariance_from_groups(
    moment_vectors: np.ndarray,
    labels: np.ndarray,
    *,
    scale: float,
) -> tuple[np.ndarray, int]:
    unique_labels = np.unique(labels)
    aggregated = np.zeros((unique_labels.size, moment_vectors.shape[1]), dtype=float)
    for idx, label in enumerate(unique_labels):
        aggregated[idx] = np.sum(moment_vectors[labels == label], axis=0)
    covariance = _symmetrize(aggregated.T @ aggregated / scale)
    return covariance, int(unique_labels.size)


def _multiway_cluster_covariance(
    moment_vectors: np.ndarray,
    labels: np.ndarray,
) -> tuple[np.ndarray, int]:
    if labels.ndim != 2 or labels.shape[1] < 2:
        covariance, n_groups = _moment_covariance_from_groups(
            moment_vectors,
            labels.reshape(-1),
            scale=max(moment_vectors.shape[0], 1),
        )
        return covariance, n_groups

    n_entities = moment_vectors.shape[0]
    covariance = np.zeros((moment_vectors.shape[1], moment_vectors.shape[1]), dtype=float)
    n_groups = 0
    n_dims = labels.shape[1]
    for mask in range(1, 1 << n_dims):
        subset_indices = [idx for idx in range(n_dims) if (mask >> idx) & 1]
        if len(subset_indices) == 1:
            subset_labels = labels[:, subset_indices[0]]
        else:
            subset_labels = np.array(
                [tuple(row[idx] for idx in subset_indices) for row in labels],
                dtype=object,
            )
        subset_covariance, subset_groups = _moment_covariance_from_groups(
            moment_vectors,
            subset_labels,
            scale=max(n_entities, 1),
        )
        if len(subset_indices) % 2 == 1:
            covariance += subset_covariance
        else:
            covariance -= subset_covariance
        n_groups = max(n_groups, subset_groups)
    return _symmetrize(covariance), n_groups


def _build_network_kernel(graph: Any, n_entities: int) -> np.ndarray | None:
    if graph is None:
        return None
    graph_arr = None
    if isinstance(graph, Mapping) and "adjacency" in graph:
        graph_arr = np.asarray(graph["adjacency"], dtype=float)
    else:
        graph_arr = np.asarray(graph, dtype=float)
    if graph_arr.ndim != 2 or graph_arr.shape != (n_entities, n_entities):
        return None
    kernel = np.maximum(graph_arr, graph_arr.T)
    kernel = np.where(kernel > 0.0, 1.0, 0.0)
    np.fill_diagonal(kernel, 1.0)
    return kernel


def _covariance_from_kernel(
    moment_vectors: np.ndarray,
    kernel: np.ndarray | None,
    *,
    scale: float,
) -> np.ndarray | None:
    if kernel is None:
        return None
    if (
        kernel.ndim != 2
        or kernel.shape[0] != moment_vectors.shape[0]
        or kernel.shape[1] != moment_vectors.shape[0]
    ):
        return None
    return _symmetrize(moment_vectors.T @ kernel @ moment_vectors / scale)


def _finalize_covariance(
    covariance_matrix: np.ndarray,
    fit: _GMMFit,
    design: _DynamicPanelDesign,
) -> np.ndarray:
    core = fit.zx.T @ fit.weight_matrix @ fit.zx
    inv_core = np.linalg.pinv(core)
    covariance = (
        inv_core
        @ (fit.zx.T @ fit.weight_matrix @ covariance_matrix @ fit.weight_matrix @ fit.zx)
        @ inv_core
    )
    covariance = _symmetrize(covariance / max(design.n_entities, 1))
    diag = np.clip(np.diag(covariance), 0.0, None)
    covariance[np.diag_indices_from(covariance)] = diag
    return covariance


def _build_inference_context(
    *,
    covariance_kind: str,
    metadata: Mapping[str, Any],
    moment_vectors: np.ndarray,
    entity_ids: np.ndarray,
    unique_entities: np.ndarray,
) -> _InferenceContext:
    if covariance_kind in {"windmeijer", "double_corrected_gmm", "robust_gmm", "none"}:
        warning = ()
        if covariance_kind in {"windmeijer", "double_corrected_gmm"}:
            warning = (
                "Finite-sample GMM correction uses the robust entity-aggregated sandwich as a conservative proxy.",
            )
        return _InferenceContext(
            covariance_kind="robust_gmm",
            distribution="normal",
            df=None,
            warnings=warning,
        )

    cluster_ids = _align_entity_metadata(
        metadata.get("cluster_ids"),
        entity_ids=entity_ids,
        unique_entities=unique_entities,
    )
    if covariance_kind == "cluster":
        if cluster_ids is None:
            return _InferenceContext(
                covariance_kind="robust_gmm",
                distribution="normal",
                df=None,
                warnings=(
                    "Cluster covariance requested but cluster_ids are unavailable; used robust GMM.",
                ),
            )
        group_count = int(np.unique(cluster_ids).size)
        return _InferenceContext(
            covariance_kind="cluster",
            distribution="normal",
            df=max(group_count - 1, 1),
        )

    if covariance_kind == "fixed_g_cluster":
        if cluster_ids is None:
            return _InferenceContext(
                covariance_kind="robust_gmm",
                distribution="normal",
                df=None,
                warnings=(
                    "Fixed-G cluster covariance requested but cluster_ids are unavailable; used robust GMM.",
                ),
            )
        group_count = int(np.unique(cluster_ids).size)
        return _InferenceContext(
            covariance_kind="fixed_g_cluster",
            distribution="t",
            df=max(group_count - 1, 1),
        )

    if covariance_kind == "multiway_cluster":
        labels = _align_entity_matrix(
            metadata.get("cluster_ids"),
            entity_ids=entity_ids,
            unique_entities=unique_entities,
        )
        if labels is None:
            return _InferenceContext(
                covariance_kind="robust_gmm",
                distribution="normal",
                df=None,
                warnings=(
                    "Multiway clustering requested but cluster_ids are unavailable; used robust GMM.",
                ),
            )
        return _InferenceContext(covariance_kind="multiway_cluster", distribution="normal", df=None)

    if covariance_kind == "conley_spatial_hac":
        weights = metadata.get("W")
        kernel = None
        if weights is not None:
            weight_matrix = np.asarray(weights, dtype=float)
            if weight_matrix.shape == (unique_entities.size, unique_entities.size):
                kernel = np.maximum(weight_matrix, weight_matrix.T)
                np.fill_diagonal(kernel, 1.0)
        if kernel is None:
            coords = _align_entity_matrix(
                metadata.get("coords"),
                entity_ids=entity_ids,
                unique_entities=unique_entities,
            )
            if coords is not None:
                kernel = _weights_from_coords(coords)
        if kernel is None:
            return _InferenceContext(
                covariance_kind="robust_gmm",
                distribution="normal",
                df=None,
                warnings=(
                    "Spatial HAC requested but no aligned W/coords metadata was found; used robust GMM.",
                ),
            )
        return _InferenceContext(
            covariance_kind="conley_spatial_hac", distribution="normal", df=None
        )

    if covariance_kind == "network_hac":
        kernel = _build_network_kernel(metadata.get("graph"), unique_entities.size)
        if kernel is None:
            return _InferenceContext(
                covariance_kind="robust_gmm",
                distribution="normal",
                df=None,
                warnings=(
                    "Network HAC requested but no aligned graph metadata was found; used robust GMM.",
                ),
            )
        return _InferenceContext(covariance_kind="network_hac", distribution="normal", df=None)

    return _InferenceContext(covariance_kind="robust_gmm", distribution="normal", df=None)


def _compute_dependence_covariance(
    *,
    fit: _GMMFit,
    design: _DynamicPanelDesign,
    covariance_kind: str,
    metadata: Mapping[str, Any],
    state: PanelData,
) -> tuple[np.ndarray, _InferenceContext]:
    context = _build_inference_context(
        covariance_kind=covariance_kind,
        metadata=metadata,
        moment_vectors=fit.moment_vectors,
        entity_ids=np.asarray(state.entity_ids),
        unique_entities=design.unique_entities,
    )

    if context.covariance_kind == "robust_gmm":
        covariance_matrix = _symmetrize(
            fit.moment_vectors.T @ fit.moment_vectors / design.n_entities
        )
        return _finalize_covariance(covariance_matrix, fit, design), context

    cluster_ids = _align_entity_metadata(
        metadata.get("cluster_ids"),
        entity_ids=np.asarray(state.entity_ids),
        unique_entities=design.unique_entities,
    )
    if context.covariance_kind in {"cluster", "fixed_g_cluster"} and cluster_ids is not None:
        covariance_matrix, group_count = _moment_covariance_from_groups(
            fit.moment_vectors,
            cluster_ids,
            scale=max(design.n_entities, 1),
        )
        covariance = _finalize_covariance(covariance_matrix, fit, design)
        if context.covariance_kind == "fixed_g_cluster" and group_count > 1:
            covariance *= float(group_count / max(group_count - 1, 1))
        return covariance, context

    labels = _align_entity_matrix(
        metadata.get("cluster_ids"),
        entity_ids=np.asarray(state.entity_ids),
        unique_entities=design.unique_entities,
    )
    if context.covariance_kind == "multiway_cluster" and labels is not None:
        covariance_matrix, _ = _multiway_cluster_covariance(fit.moment_vectors, labels)
        return _finalize_covariance(covariance_matrix, fit, design), context

    if context.covariance_kind == "conley_spatial_hac":
        kernel = None
        weights = metadata.get("W")
        if weights is not None:
            weight_matrix = np.asarray(weights, dtype=float)
            if weight_matrix.shape == (design.n_entities, design.n_entities):
                kernel = np.maximum(weight_matrix, weight_matrix.T)
                np.fill_diagonal(kernel, 1.0)
        if kernel is None:
            coords = _align_entity_matrix(
                metadata.get("coords"),
                entity_ids=np.asarray(state.entity_ids),
                unique_entities=design.unique_entities,
            )
            if coords is not None:
                kernel = _weights_from_coords(coords)
        covariance_matrix = _covariance_from_kernel(
            fit.moment_vectors,
            kernel,
            scale=max(design.n_entities, 1),
        )
        if covariance_matrix is not None:
            return _finalize_covariance(covariance_matrix, fit, design), context

    if context.covariance_kind == "network_hac":
        kernel = _build_network_kernel(metadata.get("graph"), design.n_entities)
        covariance_matrix = _covariance_from_kernel(
            fit.moment_vectors,
            kernel,
            scale=max(design.n_entities, 1),
        )
        if covariance_matrix is not None:
            return _finalize_covariance(covariance_matrix, fit, design), context

    fallback = _InferenceContext(
        covariance_kind="robust_gmm",
        distribution="normal",
        df=None,
        warnings=context.warnings
        + (f"Requested covariance '{covariance_kind}' fell back to robust GMM.",),
    )
    covariance_matrix = _symmetrize(fit.moment_vectors.T @ fit.moment_vectors / design.n_entities)
    return _finalize_covariance(covariance_matrix, fit, design), fallback


def _serial_correlation_test(
    diff_residuals: np.ndarray, n_entities: int, n_periods: int, lag: int
) -> tuple[float | None, float | None]:
    diff_matrix = diff_residuals.reshape(n_entities, n_periods - 2)
    if diff_matrix.shape[1] <= lag:
        return None, None
    current = diff_matrix[:, lag:]
    lagged = diff_matrix[:, :-lag]
    numerator = float(np.sum(current * lagged))
    denominator = float(np.sqrt(np.sum(current**2) * np.sum(lagged**2)))
    if denominator <= _FLOAT_EPS:
        return None, None
    correlation = numerator / denominator
    n_pairs = int(current.size)
    statistic = float(correlation * np.sqrt(max(n_pairs, 1)))
    p_value = float(2.0 * _normal_sf(abs(statistic)))
    return statistic, p_value


def _confidence_interval(
    estimate: float,
    std_error: float,
    confidence_level: float,
    *,
    distribution: str,
    df: int | None,
) -> tuple[float, float] | None:
    if std_error <= _FLOAT_EPS:
        return None
    alpha = 1.0 - confidence_level
    if distribution == "t" and df is not None and df > 0:
        critical = _student_t_ppf(1.0 - alpha / 2.0, df)
    else:
        critical = float(_STANDARD_NORMAL.inv_cdf(1.0 - alpha / 2.0))
    return (estimate - critical * std_error, estimate + critical * std_error)


def _p_value_and_statistic(
    estimate: float,
    std_error: float,
    *,
    distribution: str,
    df: int | None,
) -> tuple[float | None, float | None]:
    if std_error <= _FLOAT_EPS:
        return None, None
    statistic = float(estimate / std_error)
    if distribution == "t" and df is not None and df > 0:
        p_value = float(2.0 * _student_t_sf(abs(statistic), df))
    else:
        p_value = float(2.0 * _normal_sf(abs(statistic)))
    return statistic, p_value


def _build_result(
    *,
    design: _DynamicPanelDesign,
    fit: _GMMFit,
    covariance: np.ndarray,
    inference: _InferenceContext,
    confidence_level: float,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
    dependence_ref: Any = None,
    cross_sectional_dependence_diagnostic: Any = None,
) -> EconometricResult:
    std_errors: dict[str, float] = {}
    t_stats: dict[str, float] = {}
    p_values: dict[str, float] = {}
    confidence_intervals: dict[str, tuple[float, float]] = {}
    params = {name: float(value) for name, value in zip(design.param_names, fit.beta, strict=False)}

    for idx, name in enumerate(design.param_names):
        std_error = float(np.sqrt(max(covariance[idx, idx], 0.0)))
        std_errors[name] = std_error
        statistic, p_value = _p_value_and_statistic(
            params[name],
            std_error,
            distribution=inference.distribution,
            df=inference.df,
        )
        interval = _confidence_interval(
            params[name],
            std_error,
            confidence_level,
            distribution=inference.distribution,
            df=inference.df,
        )
        if statistic is not None:
            t_stats[name] = statistic
        if p_value is not None:
            p_values[name] = p_value
        if interval is not None:
            confidence_intervals[name] = interval

    return EconometricResult(
        method_name=design.method_name,
        params=params,
        std_errors=std_errors,
        t_stats=t_stats,
        p_values=p_values,
        confidence_intervals=confidence_intervals,
        confidence_level=confidence_level,
        n_obs=design.n_obs_input,
        n_entities=design.n_entities,
        n_periods=design.n_periods,
        diagnostics=dict(diagnostics),
        model_info={
            "library": "numpy",
            "estimator": design.method_name,
            "gmm_steps": diagnostics.get("step_count"),
            "inference_distribution": inference.distribution,
            "inference_df": inference.df,
        },
        metadata=dict(metadata),
        dependence_ref=dependence_ref,
        cross_sectional_dependence_diagnostic=cross_sectional_dependence_diagnostic,
    )


def _route_dependence(
    *,
    fit: _GMMFit,
    design: _DynamicPanelDesign,
    params: Mapping[str, Any],
    state: PanelData,
    covariance_applied: bool,
    applied_covariance: str,
) -> Any | None:
    dependence_mode = str(params.get("dependence_mode", "auto")).strip().lower()
    if dependence_mode in {"", "off", "none", "false"}:
        return None
    return route_cross_sectional_dependence(
        fit.diff_residuals,
        entity_ids=design.diff_entity_ids,
        time_ids=design.diff_time_ids,
        dependence_metadata=_resolve_dependence_metadata(state, params),
        used_time_dummies=bool(params.get("include_time_effects", False)),
        dependence_covariance=applied_covariance,
        dependence_fallback=str(params.get("dependence_fallback", "suppress_inference"))
        .strip()
        .lower(),
        covariance_applied=covariance_applied,
        method_context="dynamic_gmm",
    )


def _persist_dependence(
    *,
    diagnostic: Any | None,
    params: Mapping[str, Any],
    state: PanelData,
    source_method: str,
) -> tuple[Any | None, Any | None]:
    if diagnostic is None:
        return None, None
    artifact_store = resolve_artifact_store(
        state.model_dump(mode="python") if isinstance(state, PanelData) else state,
        params,
    )
    if artifact_store is None:
        return None, diagnostic
    dependence_structure = dependence_structure_from_econometrics(
        diagnostic,
        source_method=source_method,
    )
    dependence_ref = persist_dependence_structure(artifact_store, dependence_structure)
    updated_diagnostic = diagnostic.model_copy(
        update={"shared_artifacts_ref": str(dependence_ref.artifact_id)}
    )
    return dependence_ref, updated_diagnostic


def _select_covariance(
    *,
    params: Mapping[str, Any],
    diagnostic: Any | None,
) -> str:
    requested = _normalize_covariance_request(params.get("dependence_covariance", "auto"))
    if requested not in {"", "auto"}:
        return requested
    if diagnostic is None:
        return "robust_gmm"
    recommended = str(getattr(diagnostic, "recommended_covariance", "robust_gmm"))
    if recommended in {"windmeijer", "double_corrected_gmm"}:
        return recommended
    if recommended in {
        "cluster",
        "multiway_cluster",
        "fixed_g_cluster",
        "conley_spatial_hac",
        "network_hac",
    }:
        return recommended
    return "robust_gmm"


def _run_dynamic_panel_gmm(
    state: PanelData,
    params: Mapping[str, Any],
    *,
    method_name: str,
    system_gmm: bool,
) -> EconometricResult:
    design = _build_design(state, params, method_name=method_name, system_gmm=system_gmm)
    step_count = max(1, int(params.get("step_count", 2)))
    fit = _fit_gmm(design, step_count=step_count)

    preliminary_diagnostic = _route_dependence(
        fit=fit,
        design=design,
        params=params,
        state=state,
        covariance_applied=False,
        applied_covariance=_normalize_covariance_request(
            params.get("dependence_covariance", "auto")
        ),
    )
    covariance_choice = _select_covariance(params=params, diagnostic=preliminary_diagnostic)
    covariance, inference = _compute_dependence_covariance(
        fit=fit,
        design=design,
        covariance_kind=covariance_choice,
        metadata=_resolve_dependence_metadata(state, params),
        state=state,
    )

    dependence_diagnostic = _route_dependence(
        fit=fit,
        design=design,
        params=params,
        state=state,
        covariance_applied=inference.covariance_kind != "robust_gmm"
        or covariance_choice in {"windmeijer", "double_corrected_gmm"},
        applied_covariance=inference.covariance_kind,
    )
    dependence_ref, dependence_diagnostic = _persist_dependence(
        diagnostic=dependence_diagnostic,
        params=params,
        state=state,
        source_method=method_name,
    )

    ar1_stat, ar1_pvalue = _serial_correlation_test(
        fit.diff_residuals,
        design.n_entities,
        design.n_periods,
        lag=1,
    )
    ar2_stat, ar2_pvalue = _serial_correlation_test(
        fit.diff_residuals,
        design.n_entities,
        design.n_periods,
        lag=2,
    )

    diagnostics: dict[str, Any] = {
        "step_count": step_count,
        "instrument_count": design.instrument_count,
        "collapse_instruments": bool(params.get("collapse_instruments", True)),
        "effective_observations": design.stacked_observations,
        "hansen_j": fit.hansen_stat,
        "hansen_df": fit.hansen_df,
        "hansen_pvalue": fit.hansen_pvalue,
        "ar1_statistic": ar1_stat,
        "ar1_pvalue": ar1_pvalue,
        "ar2_statistic": ar2_stat,
        "ar2_pvalue": ar2_pvalue,
        "applied_covariance": inference.covariance_kind,
        "requested_covariance": _normalize_covariance_request(
            params.get("dependence_covariance", "auto")
        ),
    }

    warnings = list(inference.warnings)
    if fit.hansen_df <= 0:
        warnings.append("Model is exactly identified; Hansen J is not informative.")

    result = _build_result(
        design=design,
        fit=fit,
        covariance=covariance,
        inference=inference,
        confidence_level=float(params.get("confidence_level", 0.95)),
        diagnostics=diagnostics,
        metadata={"warnings": warnings},
        dependence_ref=dependence_ref,
        cross_sectional_dependence_diagnostic=dependence_diagnostic,
    )
    return _apply_dependence_posture(result, params=params)


_DYNAMIC_PANEL_METADATA = MethodMetadata(
    description="Dynamic panel GMM estimators for short panels with lagged dependent variables and dependence-aware inference posture.",
    tags=frozenset({"econometrics", "panel-data", "dynamic-panel", "gmm"}),
    citations=(
        "Arellano, M., & Bond, S. (1991). Some tests of specification for panel data: Monte Carlo evidence and an application to employment equations.",
        "Blundell, R., & Bond, S. (1998). Initial conditions and moment restrictions in dynamic panel data models.",
        "Sarafidis, V., Yamagata, T., & Robertson, D. (2009). A test of cross section dependence for a linear dynamic panel model with regressors.",
    ),
    equations={
        "difference_gmm": "Delta y_it = rho * Delta y_i,t-1 + Delta X_it * beta + Delta epsilon_it",
        "system_gmm": "[Delta y_it, y_it] = rho * [Delta y_i,t-1, y_i,t-1] + [Delta X_it, X_it] * beta + stacked errors",
    },
    assumptions={
        "difference_gmm": "No serial correlation in level errors beyond order one after differencing; lagged levels are valid instruments.",
        "system_gmm": "Additional mean-stationarity style restrictions validate lagged differences as level-equation instruments.",
        "local_dependence": "Cross-sectional dependence may be local/block-structured; factor dependence triggers degraded inference mode.",
    },
    when_to_use="Short-T panel with lagged outcomes and potential endogeneity from the lagged dependent variable.",
    when_not_to_use="Repeated cross-sections, panels with strong latent common factors that survive time effects, or settings needing explicit spatial/network outcome spillovers.",
    typical_min_obs=40,
)

_DIFFERENCE_GMM_METADATA = MethodMetadata(
    description=_DYNAMIC_PANEL_METADATA.description,
    tags=_DYNAMIC_PANEL_METADATA.tags,
    citations=_DYNAMIC_PANEL_METADATA.citations,
    equations=_DYNAMIC_PANEL_METADATA.equations,
    assumptions=_DYNAMIC_PANEL_METADATA.assumptions,
    when_to_use=_DYNAMIC_PANEL_METADATA.when_to_use,
    when_not_to_use=_DYNAMIC_PANEL_METADATA.when_not_to_use,
    typical_min_obs=_DYNAMIC_PANEL_METADATA.typical_min_obs,
    output_interpretation="Difference-GMM coefficient on lagged_dependent captures persistence net of fixed effects. AR(2) should usually not reject under valid level-error assumptions.",
)

_SYSTEM_GMM_METADATA = MethodMetadata(
    description=_DYNAMIC_PANEL_METADATA.description,
    tags=_DYNAMIC_PANEL_METADATA.tags,
    citations=_DYNAMIC_PANEL_METADATA.citations,
    equations=_DYNAMIC_PANEL_METADATA.equations,
    assumptions=_DYNAMIC_PANEL_METADATA.assumptions,
    when_to_use=_DYNAMIC_PANEL_METADATA.when_to_use,
    when_not_to_use=_DYNAMIC_PANEL_METADATA.when_not_to_use,
    typical_min_obs=_DYNAMIC_PANEL_METADATA.typical_min_obs,
    output_interpretation="System-GMM stacks differenced and level moments. It is typically more precise than difference-GMM when persistence is high and the additional level moments are credible.",
)


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={"econometrics", "panel-data", "dynamic-panel", "difference-gmm"},
)
class DifferenceGMMEstimator:
    """Arellano-Bond style difference-GMM estimator."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="difference_gmm",
        namespace="",
        version="0.0.0",
        input_slots=_explicit_panel_input_slots(),
        output_slots=_panel_output_slots(),
        parameters=(
            ParameterSpec(name="step_count", default=2),
            ParameterSpec(name="max_lag_depth", default=None),
            ParameterSpec(name="collapse_instruments", default=True),
            ParameterSpec(name="include_time_effects", default=False),
            ParameterSpec(name="dependence_mode", default="auto"),
            ParameterSpec(name="dependence_covariance", default="auto"),
            ParameterSpec(name="dependence_fallback", default="suppress_inference"),
            ParameterSpec(name="dependence_metadata", default=None),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = _DIFFERENCE_GMM_METADATA

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        result = _run_dynamic_panel_gmm(
            data,
            params,
            method_name="difference_gmm",
            system_gmm=False,
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        return _materialize_panel_data(bound_inputs, fallback_state)


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={"econometrics", "panel-data", "dynamic-panel", "system-gmm"},
)
class SystemGMMEstimator:
    """Blundell-Bond style system-GMM estimator."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="system_gmm",
        namespace="",
        version="0.0.0",
        input_slots=_explicit_panel_input_slots(),
        output_slots=_panel_output_slots(),
        parameters=DifferenceGMMEstimator.signature.parameters,
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = _SYSTEM_GMM_METADATA

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        result = _run_dynamic_panel_gmm(
            data,
            params,
            method_name="system_gmm",
            system_gmm=True,
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        return _materialize_panel_data(bound_inputs, fallback_state)


__all__ = [
    "DifferenceGMMEstimator",
    "SystemGMMEstimator",
]
