"""Ensemble surrogate combining GP and Random Forest for robust prediction.

Falls back gracefully when optional dependencies (torch/botorch, sklearn)
are unavailable.
"""

from __future__ import annotations

import math
from typing import Any

from polisyos.common.logger import get_logger

logger = get_logger(__name__)

__all__ = ["EnsembleSurrogate"]


class EnsembleSurrogate:
    """GP + Random Forest ensemble surrogate model.

    The ensemble prediction is a weighted average of the two models,
    providing robustness against GP mis-specification and RF's inability
    to extrapolate.

    Parameters
    ----------
    space_dim:
        Dimensionality of the input space.
    gp_weight:
        Weight for GP predictions in the ensemble (RF gets ``1 - gp_weight``).
    n_estimators:
        Number of trees in the Random Forest.
    """

    def __init__(
        self,
        space_dim: int,
        gp_weight: float = 0.6,
        n_estimators: int = 50,
    ) -> None:
        self._space_dim = space_dim
        self._gp_weight = gp_weight
        self._rf_weight = 1.0 - gp_weight
        self._n_estimators = n_estimators

        self._rf: Any = None
        self._gp: Any = None
        self._torch: Any = None
        self._gp_ready = False
        self._rf_ready = False

        # Attempt lazy imports
        try:
            from polisyos.scientist.search.strategies._deps import (
                ExactMarginalLogLikelihood as _EML,
                Normalize as _Norm,
                SingleTaskGP as _SGP,
                Standardize as _Std,
                fit_gpytorch_mll as _fit,
                require_torch,
            )
            self._torch = require_torch()
            self._SGP = _SGP
            self._Normalize = _Norm
            self._Standardize = _Std
            self._EML = _EML
            self._fit_mll = _fit
            self._gp_ready = True
        except Exception:
            logger.debug("GP components unavailable for ensemble")

        try:
            from sklearn.ensemble import RandomForestRegressor
            self._RFR = RandomForestRegressor
            self._rf_ready = True
        except ImportError:
            logger.debug("sklearn unavailable for ensemble RF")

    @property
    def is_ready(self) -> bool:
        """At least one surrogate must be available."""
        return self._gp_ready or self._rf_ready

    def fit(self, X: list[list[float]], y: list[float]) -> None:
        """Fit both GP and RF on the training data."""
        if self._gp_ready:
            self._fit_gp(X, y)
        if self._rf_ready:
            self._fit_rf(X, y)

    def predict(
        self, X: list[list[float]],
    ) -> tuple[list[float], list[float]]:
        """Return ensemble (mean, std) predictions for each row in *X*.

        When only one model is available, its predictions are used directly.
        """
        n = len(X)
        gp_mean: list[float] | None = None
        gp_std: list[float] | None = None
        rf_mean: list[float] | None = None
        rf_std: list[float] | None = None

        if self._gp_ready and self._gp is not None:
            gp_mean, gp_std = self._gp_predict(X)
        if self._rf_ready and self._rf is not None:
            rf_mean, rf_std = self._rf_predict(X)

        # Combine predictions
        if gp_mean is not None and rf_mean is not None:
            w_gp = self._gp_weight
            w_rf = self._rf_weight
            means = [w_gp * g + w_rf * r for g, r in zip(gp_mean, rf_mean)]
            stds = [
                math.sqrt(w_gp * gs**2 + w_rf * rs**2)
                for gs, rs in zip(gp_std or [0.0] * n, rf_std or [0.0] * n)
            ]
            return means, stds
        elif gp_mean is not None:
            return gp_mean, gp_std or [0.0] * n
        elif rf_mean is not None:
            return rf_mean, rf_std or [0.0] * n
        else:
            return [0.0] * n, [1.0] * n

    # ------------------------------------------------------------------
    # GP
    # ------------------------------------------------------------------

    def _fit_gp(self, X: list[list[float]], y: list[float]) -> None:
        torch = self._torch
        X_t = torch.tensor(X, dtype=torch.float64)
        y_t = torch.tensor([[v] for v in y], dtype=torch.float64)
        self._gp = self._SGP(
            train_X=X_t,
            train_Y=y_t,
            input_transform=self._Normalize(d=X_t.shape[-1]),
            outcome_transform=self._Standardize(m=1),
        )
        mll = self._EML(self._gp.likelihood, self._gp)
        self._fit_mll(mll)

    def _gp_predict(self, X: list[list[float]]) -> tuple[list[float], list[float]]:
        torch = self._torch
        X_t = torch.tensor(X, dtype=torch.float64)
        with torch.no_grad():
            posterior = self._gp.posterior(X_t)
            mean = posterior.mean.squeeze(-1).tolist()
            std = posterior.variance.sqrt().squeeze(-1).tolist()
        if isinstance(mean, float):
            mean = [mean]
            std = [std]
        return mean, std

    # ------------------------------------------------------------------
    # Random Forest
    # ------------------------------------------------------------------

    def _fit_rf(self, X: list[list[float]], y: list[float]) -> None:
        self._rf = self._RFR(
            n_estimators=self._n_estimators,
            random_state=42,
        )
        self._rf.fit(X, y)

    def _rf_predict(self, X: list[list[float]]) -> tuple[list[float], list[float]]:
        # Get predictions from individual trees for uncertainty estimate
        predictions = [tree.predict(X) for tree in self._rf.estimators_]
        n = len(X)
        means: list[float] = []
        stds: list[float] = []
        for i in range(n):
            tree_preds = [p[i] for p in predictions]
            m = sum(tree_preds) / len(tree_preds)
            var = sum((p - m) ** 2 for p in tree_preds) / len(tree_preds)
            means.append(m)
            stds.append(math.sqrt(var))
        return means, stds
