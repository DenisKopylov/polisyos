"""Small sklearn-compatible estimators used when sklearn is unavailable."""
from __future__ import annotations

from typing import Any

import numpy as np

try:  # pragma: no cover - exercised only when sklearn is present
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.svm import SVC

    SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - fallback covered instead
    SKLEARN_AVAILABLE = False

    def _as_2d(X: np.ndarray | list[list[float]] | list[float]) -> np.ndarray:
        arr = np.asarray(X, dtype=float)
        if arr.ndim == 1:
            return arr.reshape(-1, 1)
        return arr


    def _weighted_linear_solve(
        X: np.ndarray,
        y: np.ndarray,
        *,
        sample_weight: np.ndarray | None = None,
        fit_intercept: bool = True,
        ridge: float = 1e-8,
    ) -> tuple[np.ndarray, float]:
        X_arr = _as_2d(X)
        y_arr = np.asarray(y, dtype=float).reshape(-1)
        if fit_intercept:
            X_design = np.hstack([np.ones((X_arr.shape[0], 1)), X_arr])
        else:
            X_design = X_arr

        if sample_weight is None:
            sqrt_w = np.ones(X_design.shape[0], dtype=float)
        else:
            sqrt_w = np.sqrt(np.clip(np.asarray(sample_weight, dtype=float), 1e-12, None))

        Xw = X_design * sqrt_w[:, None]
        yw = y_arr * sqrt_w
        gram = Xw.T @ Xw
        penalty = np.eye(gram.shape[0]) * ridge
        if fit_intercept:
            penalty[0, 0] = 0.0
        beta = np.linalg.solve(gram + penalty, Xw.T @ yw)

        if fit_intercept:
            return np.asarray(beta[1:], dtype=float), float(beta[0])
        return np.asarray(beta, dtype=float), 0.0


    def _sigmoid(z: np.ndarray) -> np.ndarray:
        z_clip = np.clip(z, -35.0, 35.0)
        return 1.0 / (1.0 + np.exp(-z_clip))


    class LinearRegression:
        def __init__(self, *, fit_intercept: bool = True) -> None:
            self.fit_intercept = fit_intercept
            self.coef_ = np.array([], dtype=float)
            self.intercept_ = 0.0

        def fit(self, X: np.ndarray, y: np.ndarray) -> "LinearRegression":
            self.coef_, self.intercept_ = _weighted_linear_solve(
                X,
                y,
                fit_intercept=self.fit_intercept,
            )
            return self

        def predict(self, X: np.ndarray) -> np.ndarray:
            X_arr = _as_2d(X)
            return X_arr @ self.coef_ + self.intercept_


    class LogisticRegression:
        def __init__(
            self,
            *,
            max_iter: int = 500,
            C: float = 1.0,
            solver: str = "lbfgs",
        ) -> None:
            self.max_iter = int(max_iter)
            self.C = float(C)
            self.solver = solver
            self.coef_ = np.array([], dtype=float)
            self.intercept_ = 0.0
            self.classes_ = np.array([0.0, 1.0], dtype=float)

        def fit(self, X: np.ndarray, y: np.ndarray) -> "LogisticRegression":
            X_arr = _as_2d(X)
            y_arr = np.asarray(y, dtype=float).reshape(-1)
            X_design = np.hstack([np.ones((X_arr.shape[0], 1)), X_arr])
            beta = np.zeros(X_design.shape[1], dtype=float)
            penalty = 1.0 / max(self.C, 1e-6)
            eye = np.eye(X_design.shape[1], dtype=float)
            eye[0, 0] = 0.0

            for _ in range(self.max_iter):
                eta = X_design @ beta
                p = np.clip(_sigmoid(eta), 1e-6, 1.0 - 1e-6)
                grad = X_design.T @ (y_arr - p) - penalty * (eye @ beta)
                w = p * (1.0 - p)
                hessian = X_design.T @ (X_design * w[:, None]) + penalty * eye
                step = np.linalg.solve(hessian + np.eye(hessian.shape[0]) * 1e-10, grad)
                beta_next = beta + step
                if np.max(np.abs(step)) < 1e-8:
                    beta = beta_next
                    break
                beta = beta_next

            self.intercept_ = float(beta[0])
            self.coef_ = np.asarray(beta[1:], dtype=float)
            return self

        def predict_proba(self, X: np.ndarray) -> np.ndarray:
            X_arr = _as_2d(X)
            p1 = np.clip(_sigmoid(X_arr @ self.coef_ + self.intercept_), 1e-6, 1.0 - 1e-6)
            return np.column_stack([1.0 - p1, p1])

        def predict(self, X: np.ndarray) -> np.ndarray:
            return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


    class SVC:
        def __init__(self, *, kernel: str = "linear", C: float = 1.0) -> None:
            self.kernel = kernel
            self.C = float(C)
            self.coef_ = np.array([], dtype=float)
            self.intercept_ = 0.0
            self.classes_ = np.array([-1, 1], dtype=int)
            self._alpha: np.ndarray | None = None
            self._train_X: np.ndarray | None = None

        def fit(
            self,
            X: np.ndarray,
            y: np.ndarray,
            sample_weight: np.ndarray | None = None,
        ) -> "SVC":
            X_arr = _as_2d(X)
            y_arr = np.asarray(y).reshape(-1)
            classes = np.unique(y_arr)
            if classes.size != 2:
                raise ValueError("Fallback SVC supports binary classification only")
            neg_label, pos_label = classes[0], classes[-1]
            y_signed = np.where(y_arr == pos_label, 1.0, -1.0)
            self.classes_ = np.array([neg_label, pos_label])

            if self.kernel == "linear":
                self.coef_, self.intercept_ = _weighted_linear_solve(
                    X_arr,
                    y_signed,
                    sample_weight=sample_weight,
                    fit_intercept=True,
                    ridge=1.0 / max(self.C, 1e-6),
                )
                self._alpha = None
                self._train_X = None
                return self

            self._train_X = X_arr
            K = self._kernel(X_arr, X_arr)
            weights = (
                np.ones(X_arr.shape[0], dtype=float)
                if sample_weight is None
                else np.clip(np.asarray(sample_weight, dtype=float), 1e-12, None)
            )
            sqrt_w = np.sqrt(weights)
            Kw = K * sqrt_w[:, None]
            yw = y_signed * sqrt_w
            ridge = np.eye(K.shape[0], dtype=float) * (1.0 / max(self.C, 1e-6))
            self._alpha = np.linalg.solve(Kw.T @ Kw + ridge, Kw.T @ yw)
            self.intercept_ = float(np.mean(y_signed - K @ self._alpha))
            self.coef_ = np.array([], dtype=float)
            return self

        def _kernel(self, X: np.ndarray, Y: np.ndarray) -> np.ndarray:
            if self.kernel == "rbf":
                x_norm = np.sum(X**2, axis=1)[:, None]
                y_norm = np.sum(Y**2, axis=1)[None, :]
                sq_dist = np.clip(x_norm + y_norm - 2.0 * X @ Y.T, 0.0, None)
                gamma = 1.0 / max(X.shape[1], 1)
                return np.exp(-gamma * sq_dist)
            return X @ Y.T

        def decision_function(self, X: np.ndarray) -> np.ndarray:
            X_arr = _as_2d(X)
            if self._alpha is None or self._train_X is None:
                return X_arr @ self.coef_ + self.intercept_
            return self._kernel(X_arr, self._train_X) @ self._alpha + self.intercept_

        def predict(self, X: np.ndarray) -> np.ndarray:
            scores = self.decision_function(X)
            return np.where(scores >= 0.0, self.classes_[1], self.classes_[0])


__all__ = [
    "LinearRegression",
    "LogisticRegression",
    "SKLEARN_AVAILABLE",
    "SVC",
]
