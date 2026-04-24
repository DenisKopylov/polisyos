"""Measurement-error operators for observed synthetic data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np

from polisyos.synthetic_world.models import MeasurementErrorKind


def _copy_table(table: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {name: np.asarray(values).copy() for name, values in table.items()}


def apply_measurement_error(
    table: Mapping[str, np.ndarray],
    *,
    kind: MeasurementErrorKind,
    scale: float,
    misclassification_probability: float,
    heaping_base: float,
    top_code_quantile: float,
    targets: Iterable[str],
    rng: np.random.Generator,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Apply one measurement-error model to selected columns."""
    observed = _copy_table(table)
    target_list = tuple(dict.fromkeys(str(item) for item in targets))
    diagnostics: dict[str, Any] = {
        "measurement_targets": list(target_list),
        "measurement_kind": kind.value,
    }
    if kind is MeasurementErrorKind.NONE or not target_list:
        return observed, diagnostics

    if kind in {MeasurementErrorKind.CLASSICAL_ADDITIVE, MeasurementErrorKind.BERKSON}:
        for target in target_list:
            if target not in observed:
                continue
            arr = np.asarray(observed[target], dtype=float).copy()
            arr += rng.normal(scale=scale, size=arr.shape)
            observed[target] = arr
    elif kind is MeasurementErrorKind.MISCLASSIFICATION:
        for target in target_list:
            if target not in observed:
                continue
            arr = np.asarray(observed[target], dtype=int).copy()
            flips = rng.uniform(size=arr.shape) < misclassification_probability
            arr[flips] = 1 - arr[flips]
            observed[target] = arr
    elif kind is MeasurementErrorKind.HEAPING:
        for target in target_list:
            if target not in observed:
                continue
            arr = np.asarray(observed[target], dtype=float).copy()
            observed[target] = np.round(arr / heaping_base) * heaping_base
    elif kind is MeasurementErrorKind.TOP_CODING:
        for target in target_list:
            if target not in observed:
                continue
            arr = np.asarray(observed[target], dtype=float).copy()
            cutoff = float(np.quantile(arr, top_code_quantile))
            arr[arr > cutoff] = cutoff
            observed[target] = arr

    diagnostics.update(
        {
            "measurement_scale": float(scale),
            "misclassification_probability": float(misclassification_probability),
            "heaping_base": float(heaping_base),
            "top_code_quantile": float(top_code_quantile),
        }
    )
    return observed, diagnostics


__all__ = ["apply_measurement_error"]
