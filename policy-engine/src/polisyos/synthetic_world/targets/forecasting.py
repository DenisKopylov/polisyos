"""Forecasting truth targets."""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def register_forecasting_targets(
    *,
    forecast_means: Mapping[int, np.ndarray],
    forecast_intervals: Mapping[int, tuple[np.ndarray, np.ndarray]],
    entity_ids: np.ndarray,
    coord_name: str,
) -> dict[str, dict[str, Any]]:
    """Create horizon-specific point, interval, and predictive-distribution targets."""
    targets: dict[str, dict[str, Any]] = {}
    ids = np.asarray(entity_ids).tolist()
    for horizon, mean in forecast_means.items():
        mean_array = np.asarray(mean, dtype=float)
        interval = forecast_intervals.get(horizon)
        std = None
        if interval is not None:
            lower, upper = interval
            lower_array = np.asarray(lower, dtype=float)
            upper_array = np.asarray(upper, dtype=float)
            targets[f"forecast.h{horizon}.interval_90"] = {
                "lower": lower_array.tolist(),
                "upper": upper_array.tolist(),
                "coords": {coord_name: ids},
                "horizon": int(horizon),
            }
            std = ((upper_array - lower_array) / (2.0 * 1.645)).tolist()
        targets[f"forecast.h{horizon}.mean"] = {
            "values": mean_array.tolist(),
            "coords": {coord_name: ids},
            "horizon": int(horizon),
        }
        targets[f"forecast.h{horizon}.distribution"] = {
            "mean": mean_array.tolist(),
            "std": std if std is not None else np.full(mean_array.shape, 0.0).tolist(),
            "coords": {coord_name: ids},
            "horizon": int(horizon),
        }
    return targets


__all__ = ["register_forecasting_targets"]

