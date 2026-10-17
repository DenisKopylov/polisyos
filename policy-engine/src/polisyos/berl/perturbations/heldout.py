"""Held-out residual construction and perturbation support summaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.berl.metrics.infidelity import PerturbationRecord

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from polisyos.berl.adapters.protocol import (
        ExplanationAdapter,
        RawExplanation,
        ScalarModel,
    )
    from polisyos.berl.perturbations import PerturbedPoint


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


def perturbation_support_rates(
    perturbations: Sequence[PerturbedPoint],
) -> tuple[float, float]:
    """Return OOD and constraint-violation rates for sampled perturbations."""

    if not perturbations:
        return (0.0, 0.0)
    ood_rate = sum(point.ood for point in perturbations) / len(perturbations)
    violation_rate = sum(point.constraint_violation for point in perturbations) / len(perturbations)
    return (ood_rate, violation_rate)
