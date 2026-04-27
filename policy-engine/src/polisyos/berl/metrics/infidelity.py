"""Local reconstruction-infidelity helpers for explanation claims."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.berl.metrics.empirical_bounds import (
    BoundType,
    EmpiricalBoundResult,
    squared_losses_from_residuals,
    upper_bound_from_losses,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class PerturbationRecord:
    """One held-out perturbation used to audit an explanation."""

    actual_delta: float
    reconstructed_delta: float
    weight: float = 1.0

    @property
    def residual(self) -> float:
        """Return actual model change minus explanation-reconstructed change."""

        return self.actual_delta - self.reconstructed_delta


def model_output_delta(*, original_output: float, perturbed_output: float) -> float:
    """Return the scalar model-output change explained by BERL."""

    return _finite(original_output, name="original_output") - _finite(
        perturbed_output,
        name="perturbed_output",
    )


def additive_reconstruct_delta(
    attributions: Mapping[str, float],
    perturbation: Mapping[str, float],
) -> float:
    """Reconstruct a local model-output delta with an additive attribution vector."""

    total = 0.0
    for feature, attribution in attributions.items():
        total += _finite(attribution, name=f"attribution[{feature}]") * _finite(
            perturbation.get(feature, 0.0),
            name=f"perturbation[{feature}]",
        )
    return total


def reconstruction_residuals(records: Iterable[PerturbationRecord]) -> tuple[float, ...]:
    """Extract finite reconstruction residuals from held-out perturbation records."""

    values = tuple(record.residual for record in records)
    if any(not math.isfinite(value) for value in values):
        raise ValueError("perturbation residuals must be finite")
    if not values:
        raise ValueError("at least one perturbation record is required")
    return values


def perturbation_weights(records: Iterable[PerturbationRecord]) -> tuple[float, ...]:
    """Extract non-negative locality weights from perturbation records."""

    values = tuple(_finite(record.weight, name="weight") for record in records)
    if any(value < 0.0 for value in values):
        raise ValueError("perturbation weights must be non-negative")
    if not values:
        raise ValueError("at least one perturbation record is required")
    return values


def estimate_local_infidelity(
    records: Iterable[PerturbationRecord],
    *,
    confidence: float,
    residual_cap: float,
    bound_type: BoundType = "empirical_bernstein",
) -> EmpiricalBoundResult:
    """Estimate and upper-bound expected local reconstruction infidelity."""

    heldout = tuple(records)
    residuals = reconstruction_residuals(heldout)
    weights = perturbation_weights(heldout)
    losses = squared_losses_from_residuals(
        residuals,
        weights=weights,
        residual_cap=residual_cap,
    )
    return upper_bound_from_losses(
        losses,
        confidence=confidence,
        residual_cap=residual_cap,
        bound_type=bound_type,
    )


def _finite(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result
