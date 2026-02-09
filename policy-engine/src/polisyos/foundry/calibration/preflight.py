from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

import numpy as np
import jax.numpy as jnp

from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.analytics.data_views import DataViewRequest


def _normalize_raw_target(raw: object) -> tuple[np.ndarray, np.ndarray | None]:
    if isinstance(raw, tuple) and len(raw) == 2:
        values, time = raw
        values_arr = np.asarray(values)
        if values_arr.ndim == 0:
            values_arr = values_arr.reshape(1)
        time_arr = np.asarray(time) if time is not None else None
        if time_arr is not None and time_arr.ndim == 0:
            time_arr = time_arr.reshape(1)
        return values_arr, time_arr
    if isinstance(raw, dict):
        values = raw.get("values") if "values" in raw else raw.get("series")
        time = raw.get("time")
        if values is None:
            raise ValueError("Raw target dict must contain 'values' or 'series'")
        values_arr = np.asarray(values)
        if values_arr.ndim == 0:
            values_arr = values_arr.reshape(1)
        time_arr = np.asarray(time) if time is not None else None
        if time_arr is not None and time_arr.ndim == 0:
            time_arr = time_arr.reshape(1)
        return values_arr, time_arr
    values_arr = np.asarray(raw)
    if values_arr.ndim == 0:
        values_arr = values_arr.reshape(1)
    return values_arr, None


def _align_by_length(values: np.ndarray, steps: int, fill_value: float | None) -> np.ndarray:
    if values.shape[0] == steps:
        return values
    if values.shape[0] > steps:
        return values[:steps]
    pad_value = fill_value if fill_value is not None else float(values[-1]) if values.size > 0 else 0.0
    pad_len = steps - values.shape[0]
    padding = np.full((pad_len,), pad_value, dtype=values.dtype)
    return np.concatenate([values, padding], axis=0)


def _resample_series(
    values: np.ndarray,
    time: np.ndarray | None,
    *,
    target_time: np.ndarray | None,
    steps: int | None,
    method: str,
    fill_value: float | None,
) -> np.ndarray:
    if target_time is None and (steps is None or steps == values.shape[0]):
        return values
    if target_time is None:
        return _align_by_length(values, steps=steps or values.shape[0], fill_value=fill_value)
    src_time = np.asarray(time) if time is not None else np.arange(values.shape[0], dtype=float)
    tgt_time = np.asarray(target_time, dtype=float)
    if src_time.size == 0:
        return np.full((tgt_time.shape[0],), fill_value if fill_value is not None else 0.0)
    if method == "linear":
        left = fill_value if fill_value is not None else float(values[0])
        right = fill_value if fill_value is not None else float(values[-1])
        return np.interp(tgt_time, src_time, values, left=left, right=right)
    if method == "ffill":
        idx = np.searchsorted(src_time, tgt_time, side="right") - 1
        idx = np.clip(idx, 0, values.shape[0] - 1)
        out = values[idx]
        if fill_value is not None:
            out = np.where(tgt_time < src_time[0], fill_value, out)
            out = np.where(tgt_time > src_time[-1], fill_value, out)
        return out
    return _align_by_length(values, steps=steps or values.shape[0], fill_value=fill_value)


def resolve_steps(config: CalibrationConfig, raw_targets: Mapping[str, object]) -> int:
    if config.time_axis is not None:
        if config.steps is not None and len(config.time_axis) != config.steps:
            raise ValueError("config.steps must match length of config.time_axis")
        return len(config.time_axis)
    if config.steps is not None:
        return config.steps
    steps = None
    for target in config.targets:
        if target.align.steps is None:
            continue
        if steps is None:
            steps = target.align.steps
        elif steps != target.align.steps:
            raise ValueError("Conflicting target.align.steps values in calibration config")
    if steps is not None:
        return steps
    lengths: list[int] = []
    for raw in raw_targets.values():
        values, _ = _normalize_raw_target(raw)
        lengths.append(int(values.shape[0]))
    return max(lengths) if lengths else 0


def fetch_targets(
    config: CalibrationConfig,
    *,
    udf_engine: Any | None = None,
    fetcher: Any | None = None,
) -> Dict[str, object]:
    if udf_engine is None and fetcher is None:
        raise ValueError("fetch_targets requires udf_engine or fetcher")
    raw_targets: Dict[str, object] = {}
    for target in config.targets:
        if target.fabric_query is None:
            continue
        request = DataViewRequest.model_validate(target.fabric_query)
        if fetcher is not None:
            result = fetcher(target, request)
        else:
            result = udf_engine.query(request)
        raw_targets[target.target_id] = extract_fabric_series(result, target, request)
    return raw_targets


def extract_fabric_series(result: Any, target: CalibrationTarget, request: DataViewRequest) -> object:
    if isinstance(result, dict) and ("values" in result or "series" in result):
        return result
    if isinstance(result, tuple) and len(result) == 2:
        return result
    columns = getattr(result, "columns", None)
    if columns is not None:
        column_names = list(columns)
        metric = target.fabric_metric
        if metric is None and target.target_id in column_names:
            metric = target.target_id
        if metric is None and len(request.metrics) == 1 and request.metrics[0] in column_names:
            metric = request.metrics[0]
        if metric is None and len(column_names) == 1:
            metric = column_names[0]
        if metric is None:
            raise ValueError(
                f"Unable to infer Fabric metric column for target '{target.target_id}'"
            )
        values = result[metric].to_numpy()
        time_col = target.align.time_column
        if time_col and time_col in column_names:
            time = result[time_col].to_numpy()
            return {"values": values, "time": time}
        return values
    return result


def prepare_targets(
    config: CalibrationConfig,
    *,
    raw_targets: Mapping[str, object],
    steps: int,
    time_axis: list[float] | None = None,
    default_eps: float = 1e-8,
) -> Tuple[Dict[str, jnp.ndarray], Dict[str, float], Dict[str, list[float]]]:
    """
    Преобразовать сырые ряды (после fetch из Fabric) в jax-массивы нужной длины
    и вычислить масштабы для авто-нормализации, возвращая также ось времени.
    """
    aligned: Dict[str, jnp.ndarray] = {}
    scales: Dict[str, float] = {}
    time_axes: Dict[str, list[float]] = {}

    targets_by_id: Dict[str, CalibrationTarget] = {t.target_id: t for t in config.targets}
    for target_id, raw in raw_targets.items():
        target_cfg = targets_by_id.get(target_id)
        if target_cfg is None:
            continue
        values, time = _normalize_raw_target(raw)
        if time_axis is not None:
            if target_cfg.align.steps is not None and target_cfg.align.steps != len(time_axis):
                raise ValueError(f"Target '{target_id}' align.steps conflicts with config.time_axis")
            target_steps = len(time_axis)
            target_time_axis = np.asarray(time_axis, dtype=float)
            report_time_axis = target_time_axis
        else:
            target_steps = target_cfg.align.steps or steps
            target_time_axis = None
            report_time_axis = None
            if time is not None:
                if time.size == target_steps:
                    report_time_axis = time.astype(float)
                else:
                    start = float(time[0]) if time.size > 0 else 0.0
                    end = float(time[-1]) if time.size > 0 else float(target_steps - 1)
                    report_time_axis = np.linspace(start, end, target_steps)
                    target_time_axis = report_time_axis
            else:
                report_time_axis = np.arange(target_steps, dtype=float)
        resampled = _resample_series(
            values,
            time,
            target_time=target_time_axis,
            steps=target_steps,
            method=target_cfg.align.method,
            fill_value=target_cfg.align.fill_value,
        )
        arr = jnp.asarray(resampled)
        aligned[target_id] = arr
        scales[target_id] = float(_compute_scale(arr, target_cfg, default_eps))
        time_axes[target_id] = [float(val) for val in np.asarray(report_time_axis, dtype=float)]
    return aligned, scales, time_axes


def _compute_scale(arr: jnp.ndarray, target_cfg: CalibrationTarget, default_eps: float) -> float:
    if not target_cfg.loss.relative:
        return 1.0
    method = target_cfg.loss.scale
    abs_arr = jnp.abs(arr)
    if method == "std":
        scale = jnp.std(arr)
    elif method == "max":
        scale = jnp.max(abs_arr)
    elif method == "p95":
        scale = jnp.quantile(abs_arr, 0.95)
    elif method == "none":
        scale = jnp.array(1.0)
    else:
        scale = jnp.mean(abs_arr)
    return float(jnp.maximum(scale, default_eps))
