from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.causal._sklearn_compat import (
    LogisticRegression,
    SKLEARN_AVAILABLE,
)

if SKLEARN_AVAILABLE:  # pragma: no cover - exercised in integration tests
    from sklearn.isotonic import IsotonicRegression
else:  # pragma: no cover - fallback only
    IsotonicRegression = None


@dataclass
class CalibrationResult:
    mode: str
    fitted: bool
    calibration_size: int
    fit_size: int


def make_calibrated_propensity_prediction(
    X: np.ndarray,
    treatment: np.ndarray,
    *,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    base_model: Any,
    stabilizer_model: Any | None,
    calibration_mode: str,
    clip: float,
    seed: int,
) -> tuple[np.ndarray, CalibrationResult]:
    X = np.asarray(X, dtype=float)
    treatment = np.asarray(treatment, dtype=float).reshape(-1)
    train_idx = np.asarray(train_idx, dtype=int).reshape(-1)
    test_idx = np.asarray(test_idx, dtype=int).reshape(-1)
    if train_idx.size == 0 or test_idx.size == 0:
        mean_prop = float(np.clip(np.mean(treatment[train_idx]) if train_idx.size else np.mean(treatment), clip, 1.0 - clip))
        return np.full(test_idx.size, mean_prop, dtype=float), CalibrationResult(
            mode="constant",
            fitted=False,
            calibration_size=0,
            fit_size=int(train_idx.size),
        )

    fit_idx, calib_idx = _split_fit_and_calibration(train_idx, seed=seed)
    fit_targets = treatment[fit_idx]
    calib_targets = treatment[calib_idx]
    if np.unique(fit_targets).size < 2 or np.unique(calib_targets).size < 2:
        base_model.fit(X[train_idx], treatment[train_idx])
        return _average_propensity_predictions(
            base_model,
            stabilizer_model,
            X[test_idx],
            clip=clip,
            seed=seed,
        ), CalibrationResult(
            mode="constant",
            fitted=False,
            calibration_size=int(calib_idx.size),
            fit_size=int(fit_idx.size),
        )

    base_model.fit(X[fit_idx], fit_targets)
    base_prob = _base_probability(base_model, X[calib_idx], clip=clip)
    calib_mode = calibration_mode.strip().lower()
    calibrated = _fit_calibrator(base_prob, calib_targets, calib_mode)
    base_pred = _calibrate_scores(calibrated, _base_probability(base_model, X[test_idx], clip=clip))

    if stabilizer_model is None:
        return np.clip(base_pred, clip, 1.0 - clip), CalibrationResult(
            mode=calib_mode,
            fitted=True,
            calibration_size=int(calib_idx.size),
            fit_size=int(fit_idx.size),
        )

    stabilizer_model.fit(X[fit_idx], fit_targets)
    stabilizer_pred = _base_probability(stabilizer_model, X[test_idx], clip=clip)
    pred = 0.5 * base_pred + 0.5 * stabilizer_pred
    return np.clip(pred, clip, 1.0 - clip), CalibrationResult(
        mode=calib_mode,
        fitted=True,
        calibration_size=int(calib_idx.size),
        fit_size=int(fit_idx.size),
    )


def _split_fit_and_calibration(train_idx: np.ndarray, *, seed: int) -> tuple[np.ndarray, np.ndarray]:
    train_idx = np.asarray(train_idx, dtype=int).reshape(-1)
    if train_idx.size <= 3:
        return train_idx, train_idx
    rng = np.random.default_rng(seed)
    order = np.array(train_idx, copy=True)
    rng.shuffle(order)
    calib_size = max(1, int(round(order.size * 0.25)))
    calib_idx = np.sort(order[:calib_size])
    fit_idx = np.sort(order[calib_size:])
    if fit_idx.size == 0:
        fit_idx = calib_idx
    return fit_idx, calib_idx


def _fit_calibrator(scores: np.ndarray, targets: np.ndarray, calibration_mode: str) -> Any:
    scores = np.asarray(scores, dtype=float).reshape(-1)
    targets = np.asarray(targets, dtype=float).reshape(-1)
    if scores.size == 0:
        return None

    if calibration_mode == "sigmoid":
        return _fit_sigmoid_calibrator(scores, targets)

    if IsotonicRegression is None:  # pragma: no cover - fallback only
        return _fit_sigmoid_calibrator(scores, targets)

    try:
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(scores, targets)
        return ("isotonic", ir)
    except Exception:
        return _fit_sigmoid_calibrator(scores, targets)


def _fit_sigmoid_calibrator(scores: np.ndarray, targets: np.ndarray) -> tuple[str, Any]:
    if scores.size == 0:
        return ("identity", None)
    model = LogisticRegression(max_iter=2000, C=1000.0)
    model.fit(scores.reshape(-1, 1), targets)
    return ("sigmoid", model)


def _calibrate_scores(calibrator: Any, scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float).reshape(-1)
    if calibrator is None:
        return scores
    kind, obj = calibrator
    if kind == "isotonic":
        return np.asarray(obj.transform(scores), dtype=float).reshape(-1)
    if kind == "sigmoid":
        proba = np.asarray(obj.predict_proba(scores.reshape(-1, 1)), dtype=float)
        return proba[:, 1]
    return scores


def _base_probability(model: Any, X: np.ndarray, *, clip: float) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    if hasattr(model, "predict_proba"):
        proba = np.asarray(model.predict_proba(X), dtype=float)
        if proba.ndim == 2 and proba.shape[1] >= 2:
            return np.clip(proba[:, 1], clip, 1.0 - clip)
    if hasattr(model, "decision_function"):
        score = np.asarray(model.decision_function(X), dtype=float).reshape(-1)
        return np.clip(1.0 / (1.0 + np.exp(-score)), clip, 1.0 - clip)
    pred = np.asarray(model.predict(X), dtype=float).reshape(-1)
    return np.clip(pred, clip, 1.0 - clip)


def _average_propensity_predictions(
    base_model: Any,
    stabilizer_model: Any | None,
    X: np.ndarray,
    *,
    clip: float,
    seed: int,
) -> np.ndarray:
    base_pred = _base_probability(base_model, X, clip=clip)
    if stabilizer_model is None:
        return base_pred
    try:
        stabilizer_pred = _base_probability(stabilizer_model, X, clip=clip)
    except Exception:
        return base_pred
    return np.clip(0.5 * base_pred + 0.5 * stabilizer_pred, clip, 1.0 - clip)


__all__ = [
    "CalibrationResult",
    "make_calibrated_propensity_prediction",
]
