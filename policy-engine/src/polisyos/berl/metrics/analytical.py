"""Analytical infidelity bounds for special model classes."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalyticalBoundResult:
    """A deterministic analytical upper bound."""

    upper_bound: float
    bound_type: str
    assumptions: tuple[str, ...]


def linear_exact_infidelity_bound() -> AnalyticalBoundResult:
    """Return the exact zero-infidelity claim for aligned linear explanations."""

    return AnalyticalBoundResult(
        upper_bound=0.0,
        bound_type="linear_exact",
        assumptions=("same output scale", "same feature representation", "additive linear model"),
    )


def taylor_curvature_infidelity_bound(
    *,
    hessian_operator_bound: float,
    fourth_moment_radius: float,
) -> AnalyticalBoundResult:
    """Bound gradient-explanation infidelity with Taylor curvature."""

    if hessian_operator_bound < 0.0 or not math.isfinite(hessian_operator_bound):
        raise ValueError("hessian_operator_bound must be finite and non-negative")
    if fourth_moment_radius < 0.0 or not math.isfinite(fourth_moment_radius):
        raise ValueError("fourth_moment_radius must be finite and non-negative")
    return AnalyticalBoundResult(
        upper_bound=(hessian_operator_bound * hessian_operator_bound * fourth_moment_radius) / 4.0,
        bound_type="taylor_curvature",
        assumptions=(
            "twice differentiable model in local perturbation support",
            "bounded Hessian operator norm",
            "declared perturbation fourth moment",
        ),
    )
