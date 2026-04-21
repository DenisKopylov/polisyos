"""Serializable plot specs for synthetic-world diagnostics."""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def build_plot_specs(
    *,
    target_name: str,
    truth_payload: Mapping[str, Any],
    prediction: Any,
) -> dict[str, Any]:
    """Return lightweight plot specs for benchmark reports and UI hooks."""
    plots: dict[str, Any] = {}
    if target_name == "ml.classification.probability" and isinstance(prediction, Mapping):
        probs = np.asarray(prediction.get("values"), dtype=float)
        labels = np.asarray(prediction.get("labels"), dtype=float)
        plots["calibration_curve"] = {
            "type": "calibration_curve",
            "probabilities": probs.tolist(),
            "labels": labels.tolist(),
        }
    elif target_name.endswith(("cate", "ite")) and isinstance(prediction, Mapping):
        pred_values = np.asarray(prediction.get("values"), dtype=float)
        truth_values = np.asarray(truth_payload.get("values"), dtype=float)
        plots["cate_scatter"] = {
            "type": "scatter",
            "truth": truth_values.tolist(),
            "prediction": pred_values.tolist(),
        }
    elif "lower" in truth_payload and "upper" in truth_payload and isinstance(prediction, Mapping):
        plots["coverage_profile"] = {
            "type": "interval_coverage",
            "truth_lower": np.asarray(truth_payload["lower"], dtype=float).tolist(),
            "truth_upper": np.asarray(truth_payload["upper"], dtype=float).tolist(),
            "pred_lower": np.asarray(prediction.get("lower"), dtype=float).tolist(),
            "pred_upper": np.asarray(prediction.get("upper"), dtype=float).tolist(),
        }
    elif target_name == "distributional.cdf" and isinstance(prediction, Mapping):
        plots["distribution_curve"] = {
            "type": "cdf",
            "truth_grid": list(truth_payload.get("grid") or []),
            "truth_values": list(truth_payload.get("values") or []),
            "pred_values": list(prediction.get("values") or []),
        }
    return plots


__all__ = ["build_plot_specs"]

