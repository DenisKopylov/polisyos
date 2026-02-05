"""Numerical normalization helpers for surrogate models."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True)
class Normalizer:
    """Mean/std normalization for scalar objective values."""

    output_mean: float = 0.0
    output_std: float = 1.0
    _fitted: bool = False
    _min_std: float = 1e-9

    def fit_output_stats(self, y: list[float]) -> None:
        if not y:
            self.output_mean = 0.0
            self.output_std = 1.0
            self._fitted = True
            return
        mean = sum(y) / len(y)
        variance = sum((value - mean) ** 2 for value in y) / max(1, len(y) - 1)
        std = math.sqrt(max(variance, self._min_std))
        self.output_mean = float(mean)
        self.output_std = float(max(std, self._min_std))
        self._fitted = True

    def normalize_outputs(self, y: list[float]) -> list[float]:
        if not self._fitted:
            self.fit_output_stats(y)
        return [(value - self.output_mean) / self.output_std for value in y]

    def denormalize_output(self, y_norm: float) -> float:
        return y_norm * self.output_std + self.output_mean

    def denormalize_std(self, std_norm: float) -> float:
        return std_norm * self.output_std

