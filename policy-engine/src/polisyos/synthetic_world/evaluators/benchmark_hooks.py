"""Hook-level diagnostics for synthetic-world evaluation runs."""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def build_hook_diagnostics(
    *,
    hooks: tuple[str, ...],
    target_name: str,
    truth_payload: Mapping[str, Any],
    prediction: Any,
    metrics: Mapping[str, float],
) -> dict[str, Any]:
    """Compute hook-level diagnostics opportunistically."""
    diagnostics: dict[str, Any] = {}
    for hook in hooks:
        if hook == "coverage" and "coverage" in metrics:
            diagnostics["coverage"] = {"observed_coverage": float(metrics["coverage"])}
        elif hook == "pehe" and "pehe" in metrics:
            diagnostics["pehe"] = {"value": float(metrics["pehe"])}
        elif hook == "wasserstein" and "wasserstein" in metrics:
            diagnostics["wasserstein"] = {"value": float(metrics["wasserstein"])}
        elif hook == "calibration" and target_name == "ml.classification.probability" and isinstance(prediction, Mapping):
            probs = np.asarray(prediction.get("values"), dtype=float)
            labels = np.asarray(prediction.get("labels"), dtype=float)
            diagnostics["calibration"] = {
                "mean_probability": float(np.mean(probs)),
                "event_rate": float(np.mean(labels)),
            }
        elif hook == "calibration" and "lower" in truth_payload and "upper" in truth_payload and isinstance(prediction, Mapping):
            pred_lower = np.asarray(prediction.get("lower"), dtype=float)
            pred_upper = np.asarray(prediction.get("upper"), dtype=float)
            diagnostics["calibration"] = {
                "mean_interval_width": float(np.mean(pred_upper - pred_lower)),
            }
    return diagnostics


__all__ = ["build_hook_diagnostics"]

