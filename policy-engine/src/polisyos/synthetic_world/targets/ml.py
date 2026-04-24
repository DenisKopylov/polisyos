"""ML-oriented truth targets."""

from __future__ import annotations

from typing import Any

import numpy as np


def _calibration_bins(probs: np.ndarray, labels: np.ndarray, bins: int = 10) -> dict[str, Any]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    bin_ids = np.clip(np.digitize(probs, edges[1:-1], right=False), 0, bins - 1)
    mean_probability: list[float] = []
    event_rate: list[float] = []
    counts: list[int] = []
    lower: list[float] = []
    upper: list[float] = []
    for idx in range(bins):
        mask = bin_ids == idx
        lower.append(float(edges[idx]))
        upper.append(float(edges[idx + 1]))
        counts.append(int(np.sum(mask)))
        if np.any(mask):
            mean_probability.append(float(np.mean(probs[mask])))
            event_rate.append(float(np.mean(labels[mask])))
        else:
            mean_probability.append(0.5 * float(edges[idx] + edges[idx + 1]))
            event_rate.append(0.0)
    return {
        "bin_lower": lower,
        "bin_upper": upper,
        "mean_probability": mean_probability,
        "event_rate": event_rate,
        "counts": counts,
    }


def register_regression_targets(
    *,
    conditional_mean: np.ndarray,
    conditional_variance: np.ndarray,
    unit_ids: np.ndarray,
) -> dict[str, dict[str, Any]]:
    """Regression/probabilistic-ML truth."""
    return {
        "ml.regression.conditional_mean": {
            "values": np.asarray(conditional_mean, dtype=float).tolist(),
            "coords": {"unit_id": np.asarray(unit_ids).tolist()},
        },
        "ml.regression.conditional_variance": {
            "values": np.asarray(conditional_variance, dtype=float).tolist(),
            "coords": {"unit_id": np.asarray(unit_ids).tolist()},
        },
    }


def register_binary_classification_targets(
    *,
    class_probability: np.ndarray,
    labels: np.ndarray,
    entity_ids: np.ndarray,
    coord_name: str,
) -> dict[str, dict[str, Any]]:
    """Binary classification truth with calibrated probabilities."""
    probs = np.asarray(class_probability, dtype=float)
    y = np.asarray(labels, dtype=int)
    return {
        "ml.classification.probability": {
            "values": probs.tolist(),
            "coords": {coord_name: np.asarray(entity_ids).tolist()},
            "positive_class": 1,
        },
        "ml.classification.label": {
            "values": y.tolist(),
            "coords": {coord_name: np.asarray(entity_ids).tolist()},
            "positive_class": 1,
        },
        "ml.classification.calibration_map": {
            **_calibration_bins(probs, y),
            "positive_class": 1,
        },
    }


__all__ = ["register_binary_classification_targets", "register_regression_targets"]
