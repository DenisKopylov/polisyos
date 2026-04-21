"""Post-hoc recalibration helpers for binary and multiclass predictions."""
from __future__ import annotations

import math
from typing import Any, Literal, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.calibration.diagnostics import evaluate_binary
from polisyos.calibration.multiclass import evaluate_multiclass
from polisyos.foundry.methods.catalog.causal._sklearn_compat import (
    LogisticRegression,
    SKLEARN_AVAILABLE,
)
from polisyos.ir.analytics.calibration_diagnostics import CalibrationMetrics

try:  # pragma: no cover - exercised when scipy is available
    from scipy.optimize import minimize_scalar
except Exception:  # pragma: no cover - fallback path
    minimize_scalar = None

if SKLEARN_AVAILABLE:  # pragma: no cover - exercised in environments with sklearn
    from sklearn.isotonic import IsotonicRegression
else:  # pragma: no cover - fallback only
    IsotonicRegression = None

_EPSILON = 1e-12


class FittedCalibrator(BaseModel):
    """Serializable fitted calibrator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["identity", "sigmoid", "temperature", "isotonic"]
    task: Literal["binary", "multiclass"]
    input_type: Literal["probability", "logit"] = "probability"
    n_calibration: int = Field(ge=0)
    class_count: int | None = Field(default=None, ge=2)
    parameters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CalibratorComparisonEntry(BaseModel):
    """One candidate in a calibrator comparison sweep."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: str
    selected: bool = False
    passes_guardrails: bool = True
    metrics: CalibrationMetrics
    deltas: dict[str, float] = Field(default_factory=dict)
    calibrator: FittedCalibrator


class CalibratorComparisonReport(BaseModel):
    """Selection report across multiple calibrators."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task: Literal["binary", "multiclass"]
    selection_metric: str
    selected_method: str
    entries: tuple[CalibratorComparisonEntry, ...]
    guardrails: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def fit_calibrator(
    *,
    method: str,
    y_true: Sequence[int | float | str],
    scores: Sequence[float] | Sequence[Sequence[float]],
    task: Literal["binary", "multiclass"] = "binary",
    input_type: Literal["probability", "logit"] = "probability",
    class_labels: Sequence[int | str] | None = None,
) -> FittedCalibrator:
    """Fit a post-hoc calibrator and return a serializable spec."""

    normalized_method = _normalize_method(method)
    if task == "binary":
        y_arr = np.asarray(y_true, dtype=float).reshape(-1)
        score_arr = np.asarray(scores, dtype=float).reshape(-1)
        if y_arr.size != score_arr.size:
            raise ValueError("binary calibrator requires scores and y_true of identical length")
        if normalized_method == "identity":
            return FittedCalibrator(
                method="identity",
                task="binary",
                input_type=input_type,
                n_calibration=int(y_arr.size),
            )
        if normalized_method == "sigmoid":
            return _fit_binary_sigmoid(y_arr, score_arr, input_type=input_type)
        if normalized_method == "isotonic":
            return _fit_binary_isotonic(y_arr, score_arr, input_type=input_type)
        if normalized_method == "temperature":
            return _fit_binary_temperature(y_arr, score_arr, input_type=input_type)
        raise ValueError(f"Unsupported binary calibration method: {method}")

    y_idx, class_count = _encode_multiclass_targets(y_true, class_labels=class_labels)
    score_arr = np.asarray(scores, dtype=float)
    if score_arr.ndim != 2:
        raise ValueError("multiclass calibrator expects a 2D score matrix")
    if score_arr.shape[0] != y_idx.size:
        raise ValueError("multiclass scores must align with y_true length")
    if score_arr.shape[1] != class_count:
        raise ValueError("multiclass class count does not match y_true support")
    if normalized_method == "identity":
        return FittedCalibrator(
            method="identity",
            task="multiclass",
            input_type=input_type,
            n_calibration=int(y_idx.size),
            class_count=int(class_count),
        )
    if normalized_method == "temperature":
        return _fit_multiclass_temperature(y_idx, score_arr, input_type=input_type)
    if normalized_method == "sigmoid":
        return _fit_multiclass_sigmoid(y_idx, score_arr, input_type=input_type)
    if normalized_method == "isotonic":
        return _fit_multiclass_isotonic(y_idx, score_arr, input_type=input_type)
    raise ValueError(f"Unsupported multiclass calibration method: {method}")


def apply_calibrator(
    *,
    calibrator: FittedCalibrator,
    scores: Sequence[float] | Sequence[Sequence[float]],
) -> np.ndarray:
    """Apply a fitted calibrator and return calibrated probabilities."""

    if calibrator.task == "binary":
        score_arr = np.asarray(scores, dtype=float).reshape(-1)
        if calibrator.method == "identity":
            return _binary_probability_view(score_arr, input_type=calibrator.input_type)
        if calibrator.method == "sigmoid":
            feature = _binary_feature_view(score_arr, input_type=calibrator.input_type)
            coef = float(calibrator.parameters["coef"])
            intercept = float(calibrator.parameters["intercept"])
            return _sigmoid(intercept + coef * feature)
        if calibrator.method == "temperature":
            logits = _binary_logit_view(score_arr, input_type=calibrator.input_type)
            temperature = float(calibrator.parameters["temperature"])
            return _sigmoid(logits / max(temperature, _EPSILON))
        if calibrator.method == "isotonic":
            feature = _binary_feature_view(score_arr, input_type=calibrator.input_type)
            return _apply_binary_spec(feature, calibrator.parameters)
        raise ValueError(f"Unsupported calibrator method {calibrator.method!r}")

    score_arr = np.asarray(scores, dtype=float)
    if score_arr.ndim != 2:
        raise ValueError("multiclass calibrator expects a 2D score matrix")
    if calibrator.method == "identity":
        return _multiclass_probability_view(score_arr, input_type=calibrator.input_type)
    if calibrator.method == "temperature":
        logits = _multiclass_logit_view(score_arr, input_type=calibrator.input_type)
        temperature = float(calibrator.parameters["temperature"])
        return _softmax(logits / max(temperature, _EPSILON))
    if calibrator.method == "sigmoid":
        feature = _multiclass_feature_view(score_arr, input_type=calibrator.input_type)
        calibrated = np.zeros_like(feature, dtype=float)
        for class_index, params in enumerate(calibrator.parameters["per_class"]):
            calibrated[:, class_index] = _apply_binary_spec(
                feature[:, class_index],
                params,
            )
        return _normalize_probability_rows(calibrated)
    if calibrator.method == "isotonic":
        feature = _multiclass_feature_view(score_arr, input_type=calibrator.input_type)
        calibrated = np.zeros_like(feature, dtype=float)
        for class_index, params in enumerate(calibrator.parameters["per_class"]):
            calibrated[:, class_index] = _apply_binary_spec(
                feature[:, class_index],
                params,
            )
        return _normalize_probability_rows(calibrated)
    raise ValueError(f"Unsupported calibrator method {calibrator.method!r}")


def compare_calibrators(
    *,
    base_predictions: Sequence[float] | Sequence[Sequence[float]],
    y_true: Sequence[int | float | str],
    methods: Sequence[str],
    selection_metric: str = "log_loss",
    guardrails: dict[str, float] | None = None,
    task: Literal["binary", "multiclass"] = "binary",
    input_type: Literal["probability", "logit"] = "probability",
    curves: dict[str, Any] | None = None,
    tests: Sequence[str] | None = None,
    uncertainty: dict[str, Any] | None = None,
    groups: dict[str, Sequence[str]] | None = None,
    class_labels: Sequence[int | str] | None = None,
) -> CalibratorComparisonReport:
    """Fit and compare multiple calibrators on the same calibration surface."""

    entries: list[CalibratorComparisonEntry] = []
    normalized_guardrails = dict(guardrails or {})
    baseline_calibrator = fit_calibrator(
        method="identity",
        y_true=y_true,
        scores=base_predictions,
        task=task,
        input_type=input_type,
        class_labels=class_labels,
    )
    baseline_metrics = _evaluate_calibrator(
        calibrator=baseline_calibrator,
        base_predictions=base_predictions,
        y_true=y_true,
        task=task,
        class_labels=class_labels,
        curves=curves,
        tests=tests,
        uncertainty=uncertainty,
        groups=groups,
    ).metrics

    for raw_method in methods:
        calibrator = fit_calibrator(
            method=raw_method,
            y_true=y_true,
            scores=base_predictions,
            task=task,
            input_type=input_type,
            class_labels=class_labels,
        )
        diagnostics = _evaluate_calibrator(
            calibrator=calibrator,
            base_predictions=base_predictions,
            y_true=y_true,
            task=task,
            class_labels=class_labels,
            curves=curves,
            tests=tests,
            uncertainty=uncertainty,
            groups=groups,
        )
        deltas = _metric_deltas(baseline_metrics, diagnostics.metrics)
        passes_guardrails = _passes_guardrails(
            metrics=diagnostics.metrics,
            deltas=deltas,
            guardrails=normalized_guardrails,
        )
        entries.append(
            CalibratorComparisonEntry(
                method=_normalize_method(raw_method),
                metrics=diagnostics.metrics,
                passes_guardrails=passes_guardrails,
                deltas=deltas,
                calibrator=calibrator,
            )
        )

    selected_method, fallback_used = _select_best_method(
        entries=entries,
        selection_metric=selection_metric,
    )
    finalized_entries = tuple(
        entry if entry.method != selected_method else entry.model_copy(update={"selected": True})
        for entry in entries
    )
    return CalibratorComparisonReport(
        task=task,
        selection_metric=selection_metric,
        selected_method=selected_method,
        entries=finalized_entries,
        guardrails=normalized_guardrails,
        metadata={"guardrail_fallback_used": fallback_used},
    )


def _fit_binary_sigmoid(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    input_type: str,
) -> FittedCalibrator:
    feature = _binary_feature_view(scores, input_type=input_type)
    if np.unique(y_true).size < 2:
        constant = float(np.mean(y_true))
        return FittedCalibrator(
            method="sigmoid",
            task="binary",
            input_type=input_type,
            n_calibration=int(y_true.size),
            parameters={"mode": "constant", "value": constant, "coef": 0.0, "intercept": _safe_logit(constant)},
        )
    model = LogisticRegression(max_iter=2000, C=1000.0)
    model.fit(feature.reshape(-1, 1), y_true)
    coef = float(np.asarray(model.coef_, dtype=float).reshape(-1)[0])
    intercept = float(np.asarray(model.intercept_, dtype=float).reshape(-1)[0])
    return FittedCalibrator(
        method="sigmoid",
        task="binary",
        input_type=input_type,
        n_calibration=int(y_true.size),
        parameters={"coef": coef, "intercept": intercept},
    )


def _fit_binary_isotonic(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    input_type: str,
) -> FittedCalibrator:
    feature = _binary_feature_view(scores, input_type=input_type)
    if np.unique(y_true).size < 2 or IsotonicRegression is None:
        return _fit_binary_sigmoid(y_true, scores, input_type=input_type).model_copy(
            update={"method": "isotonic"}
        )
    ir = IsotonicRegression(out_of_bounds="clip")
    ir.fit(feature, y_true)
    return FittedCalibrator(
        method="isotonic",
        task="binary",
        input_type=input_type,
        n_calibration=int(y_true.size),
        parameters={
            "mode": "piecewise_linear",
            "x_thresholds": np.asarray(ir.X_thresholds_, dtype=float).tolist(),
            "y_thresholds": np.asarray(ir.y_thresholds_, dtype=float).tolist(),
        },
    )


def _fit_binary_temperature(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    input_type: str,
) -> FittedCalibrator:
    logits = _binary_logit_view(scores, input_type=input_type)
    objective = lambda temp: _binary_temperature_objective(temp, logits, y_true)
    temperature = _minimize_temperature(objective)
    return FittedCalibrator(
        method="temperature",
        task="binary",
        input_type=input_type,
        n_calibration=int(y_true.size),
        parameters={"temperature": float(temperature)},
    )


def _fit_multiclass_temperature(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    input_type: str,
) -> FittedCalibrator:
    logits = _multiclass_logit_view(scores, input_type=input_type)
    objective = lambda temp: _multiclass_temperature_objective(temp, logits, y_true)
    temperature = _minimize_temperature(objective)
    return FittedCalibrator(
        method="temperature",
        task="multiclass",
        input_type=input_type,
        n_calibration=int(y_true.size),
        class_count=int(logits.shape[1]),
        parameters={"temperature": float(temperature)},
    )


def _fit_multiclass_sigmoid(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    input_type: str,
) -> FittedCalibrator:
    feature = _multiclass_feature_view(scores, input_type=input_type)
    per_class: list[dict[str, Any]] = []
    for class_index in range(feature.shape[1]):
        per_class.append(
            _fit_binary_spec(target=(y_true == class_index).astype(float), feature=feature[:, class_index])
        )
    return FittedCalibrator(
        method="sigmoid",
        task="multiclass",
        input_type=input_type,
        n_calibration=int(y_true.size),
        class_count=int(feature.shape[1]),
        parameters={"per_class": per_class},
    )


def _fit_multiclass_isotonic(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    input_type: str,
) -> FittedCalibrator:
    feature = _multiclass_feature_view(scores, input_type=input_type)
    per_class: list[dict[str, Any]] = []
    for class_index in range(feature.shape[1]):
        per_class.append(
            _fit_binary_spec(
                target=(y_true == class_index).astype(float),
                feature=feature[:, class_index],
                prefer_isotonic=True,
            )
        )
    return FittedCalibrator(
        method="isotonic",
        task="multiclass",
        input_type=input_type,
        n_calibration=int(y_true.size),
        class_count=int(feature.shape[1]),
        parameters={"per_class": per_class},
    )


def _fit_binary_spec(
    *,
    target: np.ndarray,
    feature: np.ndarray,
    prefer_isotonic: bool = False,
) -> dict[str, Any]:
    if np.unique(target).size < 2:
        return {"mode": "constant", "value": float(np.mean(target))}
    if prefer_isotonic and IsotonicRegression is not None:
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(feature, target)
        return {
            "mode": "piecewise_linear",
            "x_thresholds": np.asarray(ir.X_thresholds_, dtype=float).tolist(),
            "y_thresholds": np.asarray(ir.y_thresholds_, dtype=float).tolist(),
        }
    model = LogisticRegression(max_iter=2000, C=1000.0)
    model.fit(feature.reshape(-1, 1), target)
    return {
        "mode": "sigmoid",
        "coef": float(np.asarray(model.coef_, dtype=float).reshape(-1)[0]),
        "intercept": float(np.asarray(model.intercept_, dtype=float).reshape(-1)[0]),
    }


def _apply_binary_spec(feature: np.ndarray, spec: dict[str, Any]) -> np.ndarray:
    mode = str(spec.get("mode", "sigmoid"))
    if mode == "constant":
        return np.full(feature.shape[0], float(spec["value"]), dtype=float)
    if mode == "piecewise_linear":
        return _apply_piecewise_linear(feature, spec)
    coef = float(spec["coef"])
    intercept = float(spec["intercept"])
    return _sigmoid(intercept + coef * feature)


def _apply_piecewise_linear(feature: np.ndarray, spec: dict[str, Any]) -> np.ndarray:
    x_thresholds = np.asarray(spec["x_thresholds"], dtype=float)
    y_thresholds = np.asarray(spec["y_thresholds"], dtype=float)
    if x_thresholds.size == 1:
        return np.full(feature.shape[0], float(y_thresholds[0]), dtype=float)
    return np.interp(
        feature,
        x_thresholds,
        y_thresholds,
        left=float(y_thresholds[0]),
        right=float(y_thresholds[-1]),
    ).astype(float)


def _metric_deltas(
    baseline: CalibrationMetrics,
    current: CalibrationMetrics,
) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for metric_name in ("brier", "log_loss", "ece"):
        base_value = getattr(baseline, metric_name)
        current_value = getattr(current, metric_name)
        if base_value is None or current_value is None:
            continue
        deltas[f"delta_{metric_name}"] = float(base_value - current_value)
    return deltas


def _passes_guardrails(
    *,
    metrics: CalibrationMetrics,
    deltas: dict[str, float],
    guardrails: dict[str, float],
) -> bool:
    for key, threshold in guardrails.items():
        value = float(threshold)
        if key == "ece_max" and metrics.ece is not None and metrics.ece > value:
            return False
        if key == "brier_max" and metrics.brier is not None and metrics.brier > value:
            return False
        if key == "log_loss_max" and metrics.log_loss is not None and metrics.log_loss > value:
            return False
        if key == "delta_brier_min" and deltas.get("delta_brier", float("-inf")) < value:
            return False
        if key == "delta_log_loss_min" and deltas.get("delta_log_loss", float("-inf")) < value:
            return False
    return True


def _select_best_method(
    *,
    entries: Sequence[CalibratorComparisonEntry],
    selection_metric: str,
) -> tuple[str, bool]:
    eligible = [entry for entry in entries if entry.passes_guardrails]
    fallback_used = False
    if not eligible:
        eligible = list(entries)
        fallback_used = True
    try:
        selected = min(
            eligible,
            key=lambda entry: _selection_value(entry.metrics, selection_metric),
        )
    except AttributeError as exc:  # pragma: no cover - defensive only
        raise ValueError(f"Unknown selection metric: {selection_metric}") from exc
    return selected.method, fallback_used


def _selection_value(metrics: CalibrationMetrics, selection_metric: str) -> float:
    value = getattr(metrics, selection_metric)
    if value is None:
        raise ValueError(f"Selection metric {selection_metric!r} is unavailable for this task")
    return float(value)


def _normalize_method(method: str) -> Literal["identity", "sigmoid", "temperature", "isotonic"]:
    normalized = str(method).strip().lower()
    if normalized in {"none", "identity"}:
        return "identity"
    if normalized not in {"sigmoid", "temperature", "isotonic"}:
        raise ValueError(f"Unsupported calibration method: {method}")
    return normalized  # type: ignore[return-value]


def _encode_multiclass_targets(
    y_true: Sequence[int | float | str],
    *,
    class_labels: Sequence[int | str] | None = None,
) -> tuple[np.ndarray, int]:
    y_values = list(y_true)
    if not y_values:
        raise ValueError("y_true must not be empty")
    if class_labels is None:
        unique = sorted({str(value) for value in y_values})
        index_map = {label: index for index, label in enumerate(unique)}
        return np.asarray([index_map[str(value)] for value in y_values], dtype=int), len(unique)
    label_map = {str(label): index for index, label in enumerate(class_labels)}
    try:
        encoded = [label_map[str(value)] for value in y_values]
    except KeyError as exc:  # pragma: no cover - defensive only
        raise ValueError(f"Unknown class label {exc.args[0]!r}") from exc
    return np.asarray(encoded, dtype=int), len(class_labels)


def _evaluate_calibrator(
    *,
    calibrator: FittedCalibrator,
    base_predictions: Sequence[float] | Sequence[Sequence[float]],
    y_true: Sequence[int | float | str],
    task: Literal["binary", "multiclass"],
    class_labels: Sequence[int | str] | None,
    curves: dict[str, Any] | None,
    tests: Sequence[str] | None,
    uncertainty: dict[str, Any] | None,
    groups: dict[str, Sequence[str]] | None,
) -> Any:
    calibrated = apply_calibrator(calibrator=calibrator, scores=base_predictions)
    if task == "binary":
        return evaluate_binary(
            y_true=np.asarray(y_true, dtype=float).tolist(),
            y_prob=calibrated.tolist(),
            curves=curves,
            tests=tests,
            uncertainty=uncertainty,
            groups=groups,
            strict=True,
        )
    return evaluate_multiclass(
        y_true=y_true,
        y_prob=calibrated.tolist(),
        class_labels=class_labels,
        curves=curves,
        tests=tests,
        uncertainty=uncertainty,
        groups=groups,
        strict=True,
    )


def _binary_feature_view(scores: np.ndarray, *, input_type: str) -> np.ndarray:
    if input_type == "logit":
        return np.asarray(scores, dtype=float).reshape(-1)
    probabilities = _binary_probability_view(scores, input_type=input_type)
    return _safe_logit(probabilities)


def _binary_logit_view(scores: np.ndarray, *, input_type: str) -> np.ndarray:
    if input_type == "logit":
        return np.asarray(scores, dtype=float).reshape(-1)
    return _safe_logit(_binary_probability_view(scores, input_type=input_type))


def _binary_probability_view(scores: np.ndarray, *, input_type: str) -> np.ndarray:
    arr = np.asarray(scores, dtype=float).reshape(-1)
    if input_type == "logit":
        return _sigmoid(arr)
    return np.clip(arr, _EPSILON, 1.0 - _EPSILON)


def _multiclass_feature_view(scores: np.ndarray, *, input_type: str) -> np.ndarray:
    if input_type == "logit":
        return np.asarray(scores, dtype=float)
    probabilities = _multiclass_probability_view(scores, input_type=input_type)
    return np.log(np.clip(probabilities, _EPSILON, 1.0))


def _multiclass_logit_view(scores: np.ndarray, *, input_type: str) -> np.ndarray:
    if input_type == "logit":
        return np.asarray(scores, dtype=float)
    return np.log(np.clip(_multiclass_probability_view(scores, input_type=input_type), _EPSILON, 1.0))


def _multiclass_probability_view(scores: np.ndarray, *, input_type: str) -> np.ndarray:
    arr = np.asarray(scores, dtype=float)
    if arr.ndim != 2:
        raise ValueError("multiclass scores must be 2D")
    if input_type == "logit":
        return _softmax(arr)
    return _normalize_probability_rows(np.clip(arr, _EPSILON, None))


def _normalize_probability_rows(probabilities: np.ndarray) -> np.ndarray:
    row_sums = np.sum(probabilities, axis=1, keepdims=True)
    row_sums = np.clip(row_sums, _EPSILON, None)
    normalized = probabilities / row_sums
    return np.clip(normalized, _EPSILON, 1.0)


def _sigmoid(values: np.ndarray | float) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    return 1.0 / (1.0 + np.exp(-np.clip(arr, -35.0, 35.0)))


def _safe_logit(probabilities: np.ndarray | float) -> np.ndarray:
    arr = np.asarray(probabilities, dtype=float)
    clipped = np.clip(arr, _EPSILON, 1.0 - _EPSILON)
    return np.log(clipped / (1.0 - clipped))


def _softmax(logits: np.ndarray) -> np.ndarray:
    arr = np.asarray(logits, dtype=float)
    shifted = arr - np.max(arr, axis=1, keepdims=True)
    exp_values = np.exp(np.clip(shifted, -50.0, 50.0))
    return exp_values / np.clip(np.sum(exp_values, axis=1, keepdims=True), _EPSILON, None)


def _binary_temperature_objective(
    temperature: float,
    logits: np.ndarray,
    y_true: np.ndarray,
) -> float:
    probabilities = _sigmoid(logits / max(float(temperature), _EPSILON))
    return float(
        np.mean(
            -y_true * np.log(np.clip(probabilities, _EPSILON, 1.0 - _EPSILON))
            - (1.0 - y_true) * np.log(np.clip(1.0 - probabilities, _EPSILON, 1.0 - _EPSILON))
        )
    )


def _multiclass_temperature_objective(
    temperature: float,
    logits: np.ndarray,
    y_true: np.ndarray,
) -> float:
    probabilities = _softmax(logits / max(float(temperature), _EPSILON))
    return float(
        np.mean(-np.log(np.clip(probabilities[np.arange(y_true.size), y_true], _EPSILON, 1.0)))
    )


def _minimize_temperature(objective: Any) -> float:
    if minimize_scalar is None:  # pragma: no cover - fallback only
        grid = np.linspace(0.25, 5.0, 40)
        losses = [float(objective(float(temp))) for temp in grid]
        return float(grid[int(np.argmin(np.asarray(losses, dtype=float)))])
    result = minimize_scalar(
        lambda temp: float(objective(float(temp))),
        bounds=(0.05, 10.0),
        method="bounded",
        options={"xatol": 1e-3},
    )
    return float(result.x)


__all__ = [
    "CalibratorComparisonEntry",
    "CalibratorComparisonReport",
    "FittedCalibrator",
    "apply_calibrator",
    "compare_calibrators",
    "fit_calibrator",
]
