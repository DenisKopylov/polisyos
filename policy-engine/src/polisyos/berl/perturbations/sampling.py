"""Deterministic local perturbation sampling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.berl.adapters._utils import DeterministicUniform
from polisyos.berl.perturbations import PerturbedPoint

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from polisyos.berl.perturbations import FeatureConstraint


def sample_local_perturbations(
    *,
    x: Mapping[str, float],
    feature_names: Sequence[str],
    n: int,
    radius: float,
    random_seed: int | None,
    constraints: Mapping[str, FeatureConstraint] | None = None,
) -> tuple[PerturbedPoint, ...]:
    """Sample numeric local perturbations around x under a declared radius."""

    if n <= 0:
        raise ValueError("n must be positive")
    if radius <= 0.0:
        raise ValueError("radius must be positive")
    rng = DeterministicUniform(random_seed)
    points: list[PerturbedPoint] = []
    for _ in range(n):
        perturbed = dict(x)
        deltas: dict[str, float] = {}
        violation = False
        for feature in feature_names:
            offset = rng.uniform(-radius, radius)
            base = float(x.get(feature, 0.0))
            value = base + offset
            perturbed[feature] = value
            deltas[feature] = base - value
            constraint = (constraints or {}).get(feature)
            if constraint is not None and not constraint.contains(value):
                violation = True
        points.append(
            PerturbedPoint(
                features=perturbed,
                deltas=deltas,
                weight=1.0,
                ood=violation,
                constraint_violation=violation,
            )
        )
    return tuple(points)
