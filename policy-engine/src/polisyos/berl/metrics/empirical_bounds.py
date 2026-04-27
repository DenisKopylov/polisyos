"""High-confidence bounds for held-out explanation reconstruction losses."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

BoundType = Literal["hoeffding", "empirical_bernstein"]


@dataclass(frozen=True, slots=True)
class EmpiricalBoundResult:
    """A finite-sample upper bound for expected held-out loss."""

    point_estimate: float
    upper_bound: float
    confidence: float
    n: int
    residual_cap: float
    bound_type: BoundType
    sample_variance: float

    @property
    def delta(self) -> float:
        """Return the failure probability associated with this claim."""

        return 1.0 - self.confidence


def hoeffding_upper_bound(
    losses: Iterable[float],
    *,
    confidence: float,
    residual_cap: float,
) -> EmpiricalBoundResult:
    """Bound expected bounded loss with Hoeffding's inequality."""

    values = _bounded_losses(losses, residual_cap=residual_cap)
    delta = _delta_from_confidence(confidence)
    n = len(values)
    point = _mean(values)
    radius = residual_cap * math.sqrt(math.log(1.0 / delta) / (2.0 * n))
    return EmpiricalBoundResult(
        point_estimate=point,
        upper_bound=point + radius,
        confidence=confidence,
        n=n,
        residual_cap=residual_cap,
        bound_type="hoeffding",
        sample_variance=_sample_variance(values, point),
    )


def empirical_bernstein_upper_bound(
    losses: Iterable[float],
    *,
    confidence: float,
    residual_cap: float,
) -> EmpiricalBoundResult:
    """Bound expected bounded loss with an empirical-Bernstein radius."""

    values = _bounded_losses(losses, residual_cap=residual_cap)
    delta = _delta_from_confidence(confidence)
    n = len(values)
    point = _mean(values)
    variance = _sample_variance(values, point)
    log_term = math.log(3.0 / delta)
    radius = math.sqrt((2.0 * variance * log_term) / n)
    radius += (3.0 * residual_cap * log_term) / n
    return EmpiricalBoundResult(
        point_estimate=point,
        upper_bound=point + radius,
        confidence=confidence,
        n=n,
        residual_cap=residual_cap,
        bound_type="empirical_bernstein",
        sample_variance=variance,
    )


def upper_bound_from_losses(
    losses: Iterable[float],
    *,
    confidence: float,
    residual_cap: float,
    bound_type: BoundType = "empirical_bernstein",
) -> EmpiricalBoundResult:
    """Dispatch to the configured bounded-loss confidence bound."""

    if bound_type == "hoeffding":
        return hoeffding_upper_bound(
            losses,
            confidence=confidence,
            residual_cap=residual_cap,
        )
    return empirical_bernstein_upper_bound(
        losses,
        confidence=confidence,
        residual_cap=residual_cap,
    )


def adjust_confidence_for_union(*, global_confidence: float, claim_count: int) -> float:
    """Return per-claim confidence for a simultaneous union-bound guarantee."""

    if claim_count <= 0:
        raise ValueError("claim_count must be positive")
    delta = _delta_from_confidence(global_confidence)
    return 1.0 - (delta / claim_count)


def squared_losses_from_residuals(
    residuals: Iterable[float],
    *,
    weights: Iterable[float] | None = None,
    residual_cap: float | None = None,
) -> tuple[float, ...]:
    """Convert reconstruction residuals to squared, optionally weighted losses."""

    values = _finite_tuple(residuals, name="residuals")
    if weights is None:
        losses = tuple(value * value for value in values)
    else:
        weight_values = _finite_tuple(weights, name="weights")
        if len(weight_values) != len(values):
            raise ValueError("weights must have the same length as residuals")
        if any(weight < 0.0 for weight in weight_values):
            raise ValueError("weights must be non-negative")
        losses = tuple(
            weight * value * value for value, weight in zip(values, weight_values, strict=True)
        )
    if residual_cap is None:
        return losses
    return _bounded_losses(losses, residual_cap=residual_cap)


def _delta_from_confidence(confidence: float) -> float:
    if not math.isfinite(confidence) or not (0.0 < confidence < 1.0):
        raise ValueError("confidence must be finite and in (0, 1)")
    return 1.0 - confidence


def _bounded_losses(losses: Iterable[float], *, residual_cap: float) -> tuple[float, ...]:
    if not math.isfinite(residual_cap) or residual_cap <= 0.0:
        raise ValueError("residual_cap must be finite and positive")
    values = _finite_tuple(losses, name="losses")
    if not values:
        raise ValueError("at least one loss is required")
    if any(value < 0.0 for value in values):
        raise ValueError("losses must be non-negative")
    if any(value > residual_cap for value in values):
        raise ValueError("loss exceeds declared residual_cap")
    return values


def _finite_tuple(values: Iterable[float], *, name: str) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if any(not math.isfinite(value) for value in result):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _mean(values: tuple[float, ...]) -> float:
    return sum(values) / len(values)


def _sample_variance(values: tuple[float, ...], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)
