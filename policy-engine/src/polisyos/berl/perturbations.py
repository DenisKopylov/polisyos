"""Local perturbation sampling and held-out infidelity evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.berl.adapters._utils import DeterministicUniform
from polisyos.berl.metrics.infidelity import PerturbationRecord

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from polisyos.berl.adapters.protocol import ExplanationAdapter, RawExplanation, ScalarModel


@dataclass(frozen=True, slots=True)
class FeatureConstraint:
    """Closed numeric support interval for a feature."""

    lower: float | None = None
    upper: float | None = None

    def contains(self, value: float) -> bool:
        """Return whether value is inside the declared feature support."""

        if self.lower is not None and value < self.lower:
            return False
        return not (self.upper is not None and value > self.upper)


@dataclass(frozen=True, slots=True)
class PerturbedPoint:
    """One local perturbation plus its explanation representation."""

    features: Mapping[str, float]
    deltas: Mapping[str, float]
    weight: float = 1.0
    ood: bool = False
    constraint_violation: bool = False


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


def build_heldout_records(
    *,
    model: ScalarModel,
    x: Mapping[str, float],
    explanation: RawExplanation,
    adapter: ExplanationAdapter,
    perturbations: Sequence[PerturbedPoint],
) -> tuple[PerturbationRecord, ...]:
    """Compute held-out model residual records for one adapter explanation."""

    original_output = float(model(x))
    records: list[PerturbationRecord] = []
    for point in perturbations:
        actual_delta = original_output - float(model(point.features))
        reconstructed_delta = adapter.reconstruct_delta(explanation, point.deltas)
        records.append(
            PerturbationRecord(
                actual_delta=actual_delta,
                reconstructed_delta=reconstructed_delta,
                weight=point.weight,
            )
        )
    return tuple(records)


def perturbation_support_rates(perturbations: Sequence[PerturbedPoint]) -> tuple[float, float]:
    """Return OOD and constraint-violation rates for sampled perturbations."""

    if not perturbations:
        return (0.0, 0.0)
    ood_rate = sum(point.ood for point in perturbations) / len(perturbations)
    violation_rate = sum(point.constraint_violation for point in perturbations) / len(perturbations)
    return (ood_rate, violation_rate)
