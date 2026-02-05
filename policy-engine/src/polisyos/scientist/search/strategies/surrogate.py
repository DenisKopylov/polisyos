"""Surrogate model protocol and simple implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Protocol


class SurrogateModel(Protocol):
    """Protocol for surrogate models used by strategies."""

    def fit(self, X: list[tuple[float, ...]], y: list[float]) -> None:
        """Fit model to observations."""

    def predict(self, X: list[tuple[float, ...]]) -> tuple[list[float], list[float]]:
        """Return predicted means and std values."""

    def get_state(self) -> dict:
        """Serialize model state."""

    def set_state(self, state: dict) -> None:
        """Restore model state."""


@dataclass(slots=True)
class MeanVarianceSurrogate:
    """
    Lightweight fallback surrogate.

    This is not used for BO, but gives deterministic behavior in environments
    without heavy ML dependencies.
    """

    _mean: float = 0.0
    _std: float = 1.0
    _fitted: bool = False
    _n: int = 0
    _x_dim: int = 0
    _x_digest: list[float] = field(default_factory=list)

    def fit(self, X: list[tuple[float, ...]], y: list[float]) -> None:
        if not y:
            self._mean = 0.0
            self._std = 1.0
            self._fitted = True
            self._n = 0
            self._x_dim = len(X[0]) if X else 0
            self._x_digest = [0.0] * self._x_dim
            return
        self._mean = float(mean(y))
        self._std = max(float(pstdev(y)), 1e-9)
        self._fitted = True
        self._n = len(y)
        self._x_dim = len(X[0]) if X else 0
        self._x_digest = [sum(row[idx] for row in X) / max(1, len(X)) for idx in range(self._x_dim)]

    def predict(self, X: list[tuple[float, ...]]) -> tuple[list[float], list[float]]:
        if not self._fitted:
            self.fit([], [])
        means = [self._mean for _ in X]
        stds = [self._std for _ in X]
        return means, stds

    def get_state(self) -> dict:
        return {
            "mean": self._mean,
            "std": self._std,
            "fitted": self._fitted,
            "n": self._n,
            "x_dim": self._x_dim,
            "x_digest": list(self._x_digest),
        }

    def set_state(self, state: dict) -> None:
        self._mean = float(state.get("mean", 0.0))
        self._std = float(state.get("std", 1.0))
        self._fitted = bool(state.get("fitted", False))
        self._n = int(state.get("n", 0))
        self._x_dim = int(state.get("x_dim", 0))
        digest = state.get("x_digest", [])
        self._x_digest = [float(item) for item in digest]

