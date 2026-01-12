from __future__ import annotations

from typing import Dict, Mapping, Tuple

import jax.numpy as jnp

from polisyos.ir.calibration import CalibrationConfig, CalibrationTarget


def _align_series(
    series: jnp.ndarray, *, steps: int, method: str = "linear", fill_value: float | None = None
) -> jnp.ndarray:
    """Простейшее выравнивание длины ряда под длину симуляции."""
    if series.shape[0] == steps:
        return series
    if series.shape[0] > steps:
        return series[:steps]
    # series короче: дополняем последним значением или fill_value
    pad_value = fill_value if fill_value is not None else float(series[-1]) if series.size > 0 else 0.0
    pad_len = steps - series.shape[0]
    padding = jnp.full((pad_len,), pad_value, dtype=series.dtype)
    return jnp.concatenate([series, padding], axis=0)


def prepare_targets(
    config: CalibrationConfig,
    *,
    raw_targets: Mapping[str, object],
    steps: int,
    default_eps: float = 1e-8,
) -> Tuple[Dict[str, jnp.ndarray], Dict[str, float]]:
    """
    Преобразовать сырые ряды (после fetch из Fabric) в jax-массивы нужной длины
    и вычислить масштабы для авто-нормализации.
    """
    aligned: Dict[str, jnp.ndarray] = {}
    scales: Dict[str, float] = {}

    targets_by_id: Dict[str, CalibrationTarget] = {t.target_id: t for t in config.targets}
    for target_id, raw in raw_targets.items():
        target_cfg = targets_by_id.get(target_id)
        if target_cfg is None:
            continue
        arr = jnp.asarray(raw)
        arr = _align_series(
            arr,
            steps=steps,
            method=target_cfg.align.method,
            fill_value=target_cfg.align.fill_value,
        )
        aligned[target_id] = arr
        scale = jnp.maximum(jnp.mean(jnp.abs(arr)), default_eps)
        scales[target_id] = float(scale)
    return aligned, scales
