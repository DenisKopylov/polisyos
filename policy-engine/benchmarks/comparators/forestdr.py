"""Benchmark-side ForestDR comparator wrapper.

The core causal stack does not currently expose a dedicated ForestDR estimator,
so the benchmark layer provides an adapter that prefers econml when installed
and falls back to the existing DR learner implementation. The benchmark
contracts still see a uniform PolicyOS-style payload.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


def _bootstrap_interval(values: np.ndarray, *, seed: int, draws: int) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float).reshape(-1)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan"), float("nan")
    if arr.size == 1:
        return float(arr[0]), float(arr[0])
    rng = np.random.default_rng(seed)
    samples = np.empty(draws, dtype=float)
    for idx in range(draws):
        sample = rng.choice(arr, size=arr.size, replace=True)
        samples[idx] = float(np.mean(sample))
    return float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def _as_state(state: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if hasattr(state, "covariates") and hasattr(state, "treatment") and hasattr(state, "outcome"):
        X = np.asarray(state.covariates, dtype=float)
        T = np.asarray(state.treatment, dtype=float).reshape(-1)
        Y = np.asarray(state.outcome, dtype=float).reshape(-1)
        return X, T, Y
    if isinstance(state, Mapping):
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float).reshape(-1)
        Y = np.asarray(state["outcome"], dtype=float).reshape(-1)
        return X, T, Y
    raise TypeError("Unsupported ForestDR benchmark state")


class ForestDRLearnerComparator:
    """Benchmark adapter for ForestDR-style heterogeneous effect estimation."""

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        X, T, Y = _as_state(state)
        seed = int(params.get("random_state", params.get("__seed__", 0)))
        confidence_level = float(params.get("confidence_level", 0.95))
        n_estimators = int(params.get("n_estimators", 240))
        min_samples_leaf = int(params.get("min_samples_leaf", 5))
        max_depth = params.get("max_depth")
        cv_folds = int(params.get("cv_folds", 3))
        bootstrap_draws = max(40, int(params.get("bootstrap_draws", 100)))

        try:  # pragma: no cover - optional dependency path
            from econml.dr import ForestDRLearner  # type: ignore[import]

            model = ForestDRLearner(
                n_estimators=n_estimators,
                min_samples_leaf=min_samples_leaf,
                max_depth=max_depth,
                cv=cv_folds,
                random_state=seed,
                honest=True,
            )
            model.fit(Y, T, X=X)
            cate_predictions = np.asarray(model.effect(X), dtype=float).reshape(-1)
            ate = float(np.mean(cate_predictions))
            try:
                interval = model.effect_interval(X, alpha=1.0 - confidence_level)
                ci_lower = float(np.mean(np.asarray(interval[0], dtype=float).reshape(-1)))
                ci_upper = float(np.mean(np.asarray(interval[1], dtype=float).reshape(-1)))
            except Exception:
                ci_lower, ci_upper = _bootstrap_interval(
                    cate_predictions,
                    seed=seed + 17,
                    draws=bootstrap_draws,
                )
            feature_importances = getattr(model, "feature_importances_", None)
            if feature_importances is not None:
                feature_importances = np.asarray(feature_importances, dtype=float).reshape(-1)
            return {
                "result": {
                    "ate": ate,
                    "ci_lower": ci_lower,
                    "ci_upper": ci_upper,
                    "cate_predictions": cate_predictions.tolist(),
                    "feature_importances": None
                    if feature_importances is None
                    else feature_importances.tolist(),
                    "backend_used": "econml.ForestDRLearner",
                    "confidence_level": confidence_level,
                }
            }
        except Exception:
            from polisyos.foundry.methods.catalog.causal.advanced_designs import DRLearnerEstimator

            fallback = DRLearnerEstimator.pure_step(
                {"X": X, "treatment": T, "outcome": Y},
                dict(params),
            )
            payload = dict(fallback.get("result", {}))
            payload["backend_used"] = "policyos.DRLearnerEstimator"
            return {"result": payload}
