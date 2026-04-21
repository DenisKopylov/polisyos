"""Family-aware evaluation metrics for truth-centric worlds."""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def _wasserstein_1d(lhs: np.ndarray, rhs: np.ndarray) -> float:
    left = np.sort(np.asarray(lhs, dtype=float))
    right = np.sort(np.asarray(rhs, dtype=float))
    if left.shape != right.shape:
        grid = np.linspace(0.0, 1.0, max(left.shape[0], right.shape[0]), endpoint=False) + 0.5 / max(left.shape[0], right.shape[0])
        left = np.quantile(left, grid)
        right = np.quantile(right, grid)
    return float(np.mean(np.abs(left - right)))


def _binary_log_loss(labels: np.ndarray, probs: np.ndarray) -> float:
    clipped = np.clip(np.asarray(probs, dtype=float), 1.0e-8, 1.0 - 1.0e-8)
    y = np.asarray(labels, dtype=float)
    return float(-np.mean(y * np.log(clipped) + (1.0 - y) * np.log(1.0 - clipped)))


def _brier_score(labels: np.ndarray, probs: np.ndarray) -> float:
    y = np.asarray(labels, dtype=float)
    p = np.asarray(probs, dtype=float)
    return float(np.mean((p - y) ** 2))


def _pinball_loss(values: np.ndarray, prediction: np.ndarray, quantile: float) -> float:
    diff = np.asarray(values, dtype=float) - np.asarray(prediction, dtype=float)
    return float(np.mean(np.maximum(quantile * diff, (quantile - 1.0) * diff)))


def evaluate_prediction(
    *,
    target_name: str,
    truth_payload: Mapping[str, Any],
    prediction: Any,
) -> tuple[dict[str, float], dict[str, Any]]:
    """Compute default metrics for a single truth target."""
    metrics: dict[str, float] = {}
    diagnostics: dict[str, Any] = {"truth_payload_keys": sorted(truth_payload)}

    if target_name == "ml.classification.probability" and isinstance(prediction, Mapping):
        probs = np.asarray(prediction.get("values"), dtype=float)
        labels = np.asarray(prediction.get("labels"), dtype=float)
        metrics["brier"] = _brier_score(labels, probs)
        metrics["log_loss"] = _binary_log_loss(labels, probs)
        return metrics, diagnostics

    if target_name.startswith("distributional.quantile.") and isinstance(prediction, Mapping):
        quantile_str = target_name.rsplit("p", 1)[-1]
        quantile = float(quantile_str) / 100.0
        pred_value = np.asarray(prediction.get("value"), dtype=float)
        metrics["pinball_loss"] = _pinball_loss(np.asarray([truth_payload["value"]]), np.asarray([pred_value]), quantile)
        return metrics, diagnostics

    if target_name == "distributional.cdf" and isinstance(prediction, Mapping):
        truth_values = np.asarray(truth_payload["values"], dtype=float)
        pred_values = np.asarray(prediction.get("values"), dtype=float)
        metrics["wasserstein"] = _wasserstein_1d(truth_values, pred_values)
        return metrics, diagnostics

    if target_name == "distributional.pdf" and isinstance(prediction, Mapping):
        truth_values = np.asarray(truth_payload["values"], dtype=float)
        pred_values = np.asarray(prediction.get("values"), dtype=float)
        if truth_values.shape != pred_values.shape:
            raise ValueError(f"Prediction shape mismatch for {target_name}: {pred_values.shape} != {truth_values.shape}")
        metrics["l1_error"] = float(np.mean(np.abs(pred_values - truth_values)))
        return metrics, diagnostics

    if "values" in truth_payload:
        truth_values = np.asarray(truth_payload["values"], dtype=float)
        pred_values = np.asarray(
            prediction["values"] if isinstance(prediction, Mapping) and "values" in prediction else prediction,
            dtype=float,
        )
        if truth_values.shape != pred_values.shape:
            raise ValueError(f"Prediction shape mismatch for {target_name}: {pred_values.shape} != {truth_values.shape}")
        rmse = float(np.sqrt(np.mean((pred_values - truth_values) ** 2)))
        metrics["rmse"] = rmse
        if target_name.endswith(("cate", "ite", "dynamic_ite", "spatial_ite")):
            metrics["pehe"] = rmse
        return metrics, diagnostics

    if "lower" in truth_payload and "upper" in truth_payload and isinstance(prediction, Mapping):
        lower = np.asarray(truth_payload["lower"], dtype=float)
        upper = np.asarray(truth_payload["upper"], dtype=float)
        pred_lower = np.asarray(prediction.get("lower"), dtype=float)
        pred_upper = np.asarray(prediction.get("upper"), dtype=float)
        midpoint = 0.5 * (lower + upper)
        coverage = (pred_lower <= midpoint) & (midpoint <= pred_upper)
        metrics["coverage"] = float(np.mean(coverage))
        metrics["mean_interval_width"] = float(np.mean(pred_upper - pred_lower))
        return metrics, diagnostics

    if "value" in truth_payload and np.isscalar(truth_payload["value"]):
        truth_value = float(truth_payload["value"])
        pred_value = float(prediction["value"] if isinstance(prediction, Mapping) and "value" in prediction else prediction)
        metrics["abs_error"] = abs(pred_value - truth_value)
        metrics["squared_error"] = (pred_value - truth_value) ** 2
        return metrics, diagnostics

    return metrics, diagnostics


__all__ = ["evaluate_prediction"]
