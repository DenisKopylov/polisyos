"""Weighted scoring helpers shared by evaluators, governance, and runtime summaries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar

T = TypeVar("T")


def clamp01(value: float) -> float:
    """Clamp an arbitrary numeric score into the normalized ``[0, 1]`` interval."""
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class WeightedScoreResult:
    """Normalized scoring breakdown with the final score, inputs, and effective weights."""
    score: float
    components: dict[str, float]
    contributions: dict[str, float]
    effective_weights: dict[str, float]


class WeightedScorer:
    """
    Normalize weighted component scores with graceful handling of missing values.
    """

    def __init__(self, weights: Mapping[str, float]) -> None:
        normalized = _normalize_weights(weights)
        if not normalized:
            raise ValueError("weights cannot be empty")
        self._weights = normalized

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def score(self, component_scores: Mapping[str, float | None]) -> WeightedScoreResult:
        usable: dict[str, float] = {}
        usable_weights: dict[str, float] = {}

        for name, weight in self._weights.items():
            raw = component_scores.get(name)
            if raw is None:
                continue
            usable[name] = clamp01(raw)
            usable_weights[name] = weight

        if not usable:
            return WeightedScoreResult(
                score=0.0,
                components={},
                contributions={},
                effective_weights={},
            )

        effective_weights = _normalize_weights(usable_weights)
        contributions = {
            name: effective_weights[name] * usable[name]
            for name in usable
        }
        final_score = clamp01(sum(contributions.values()))

        return WeightedScoreResult(
            score=final_score,
            components=usable,
            contributions=contributions,
            effective_weights=effective_weights,
        )


@dataclass(frozen=True)
class ThresholdBand(Generic[T]):
    """Threshold band public type."""
    min_score: float
    value: T


class ThresholdMapper(Generic[T]):
    """Threshold mapper public type."""
    def __init__(self, bands: list[ThresholdBand[T]], *, default: T) -> None:
        if not bands:
            raise ValueError("bands cannot be empty")
        self._bands = sorted(bands, key=lambda row: row.min_score, reverse=True)
        self._default = default

    def map(self, score: float | None) -> T:
        if score is None:
            return self._default
        numeric = clamp01(score)
        for band in self._bands:
            if numeric >= band.min_score:
                return band.value
        return self._default


def _normalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    filtered = {name: max(0.0, float(value)) for name, value in weights.items()}
    total = sum(filtered.values())
    if total <= 0.0:
        return {}
    return {name: value / total for name, value in filtered.items()}
