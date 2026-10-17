"""Small sklearn-compatible fallback used by calibration diagnostics."""

from __future__ import annotations

import numpy as np

try:  # pragma: no cover - exercised only when sklearn is present
    from sklearn.linear_model import LogisticRegression

    SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - fallback covered instead
    SKLEARN_AVAILABLE = False

    def _as_2d(features: np.ndarray | list[list[float]] | list[float]) -> np.ndarray:
        arr = np.asarray(features, dtype=float)
        if arr.ndim == 1:
            return arr.reshape(-1, 1)
        return arr

    def _sigmoid(values: np.ndarray) -> np.ndarray:
        clipped = np.clip(values, -35.0, 35.0)
        return 1.0 / (1.0 + np.exp(-clipped))

    class LogisticRegression:
        def __init__(
            self,
            *,
            max_iter: int = 500,
            solver: str = "lbfgs",
            **kwargs: object,
        ) -> None:
            regularization = kwargs.pop("C", 1.0)
            if kwargs:
                unknown = ", ".join(sorted(kwargs))
                raise TypeError(f"Unsupported LogisticRegression arguments: {unknown}")
            self.max_iter = int(max_iter)
            self.regularization = float(regularization)
            self.solver = solver
            self.coef_ = np.array([], dtype=float)
            self.intercept_ = 0.0
            self.classes_ = np.array([0.0, 1.0], dtype=float)

        def fit(self, features: np.ndarray, target: np.ndarray) -> LogisticRegression:
            feature_arr = _as_2d(features)
            target_arr = np.asarray(target, dtype=float).reshape(-1)
            design = np.hstack([np.ones((feature_arr.shape[0], 1)), feature_arr])
            beta = np.zeros(design.shape[1], dtype=float)
            penalty = 1.0 / max(self.regularization, 1e-6)
            eye = np.eye(design.shape[1], dtype=float)
            eye[0, 0] = 0.0

            for _ in range(self.max_iter):
                eta = design @ beta
                probabilities = np.clip(_sigmoid(eta), 1e-6, 1.0 - 1e-6)
                grad = design.T @ (target_arr - probabilities) - penalty * (eye @ beta)
                weights = probabilities * (1.0 - probabilities)
                hessian = design.T @ (design * weights[:, None]) + penalty * eye
                step = np.linalg.solve(
                    hessian + np.eye(hessian.shape[0]) * 1e-10,
                    grad,
                )
                beta_next = beta + step
                if np.max(np.abs(step)) < 1e-8:
                    beta = beta_next
                    break
                beta = beta_next

            self.intercept_ = float(beta[0])
            self.coef_ = np.asarray(beta[1:], dtype=float)
            return self

        def predict_proba(self, features: np.ndarray) -> np.ndarray:
            feature_arr = _as_2d(features)
            positive = np.clip(
                _sigmoid(feature_arr @ self.coef_ + self.intercept_),
                1e-6,
                1.0 - 1e-6,
            )
            return np.column_stack([1.0 - positive, positive])

        def predict(self, features: np.ndarray) -> np.ndarray:
            return (self.predict_proba(features)[:, 1] >= 0.5).astype(int)


__all__ = ["SKLEARN_AVAILABLE", "LogisticRegression"]
