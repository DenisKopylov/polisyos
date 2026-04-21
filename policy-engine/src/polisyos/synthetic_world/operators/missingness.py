"""Missingness operators for observed synthetic data."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

import numpy as np

from polisyos.synthetic_world.models import MissingnessMechanism


def _copy_table(table: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {name: np.asarray(values).copy() for name, values in table.items()}


def _standardize(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    std = float(np.std(arr))
    if std <= 1.0e-9:
        return np.zeros_like(arr)
    return (arr - float(np.mean(arr))) / std


def _safe_logit(probability: float) -> float:
    clipped = float(np.clip(probability, 1.0e-6, 1.0 - 1.0e-6))
    return float(np.log(clipped / (1.0 - clipped)))


def _sigmoid(value: np.ndarray | float) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    return 1.0 / (1.0 + np.exp(-np.clip(array, -30.0, 30.0)))


def apply_missingness(
    observed: Mapping[str, np.ndarray],
    *,
    clean_reference: Mapping[str, np.ndarray],
    mechanism: MissingnessMechanism,
    rate: float,
    strength: float,
    targets: Iterable[str],
    rng: np.random.Generator,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Apply missingness as an observation operator."""
    with_missing = _copy_table(observed)
    target_list = tuple(dict.fromkeys(str(item) for item in targets))
    diagnostics: dict[str, Any] = {
        "missingness_targets": list(target_list),
        "missingness_mechanism": mechanism.value,
    }
    if mechanism is MissingnessMechanism.NONE or not target_list:
        return with_missing, diagnostics

    baseline_driver = (
        np.asarray(clean_reference["feature_0"], dtype=float)
        if "feature_0" in clean_reference
        else np.asarray(next(iter(clean_reference.values())), dtype=float)
    )
    outcome_driver = (
        np.asarray(clean_reference["outcome"], dtype=float)
        if "outcome" in clean_reference
        else baseline_driver
    )

    for target in target_list:
        if target not in with_missing:
            continue
        arr = np.asarray(with_missing[target])
        if not np.issubdtype(arr.dtype, np.number):
            continue

        if mechanism is MissingnessMechanism.MCAR:
            probability = np.full(arr.shape, rate, dtype=float)
        elif mechanism is MissingnessMechanism.MAR:
            probability = np.clip(
                _sigmoid(_safe_logit(rate) + strength * _standardize(baseline_driver)),
                0.01,
                0.99,
            )
        else:
            probability = np.clip(
                _sigmoid(_safe_logit(rate) + strength * _standardize(outcome_driver)),
                0.01,
                0.99,
            )

        missing = rng.uniform(size=arr.shape) < probability
        arr_float = np.asarray(arr, dtype=float).copy()
        arr_float[missing] = np.nan
        with_missing[target] = arr_float
        diagnostics[target] = {"missing_rate": float(np.mean(missing))}
    return with_missing, diagnostics


__all__ = ["apply_missingness"]

