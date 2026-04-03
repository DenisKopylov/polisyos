"""Public fabric trust adapter module API."""
from __future__ import annotations

from polisyos.core.contracts.fabric import UncertaintyBounds
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def envelope_from_trust_bounds(
    bounds: UncertaintyBounds,
    *,
    trust_policy_id: str | None = None,
    assume_triangular: bool = False,
) -> UncertaintyEnvelope:
    """Envelope from trust bounds helper."""
    distribution = (
        DistributionFamily.TRIANGULAR if assume_triangular else DistributionFamily.UNKNOWN
    )
    metadata = {
        "method": bounds.method,
        "trust_policy_id": trust_policy_id,
        "original_value_decimal": str(bounds.value),
        "original_lower_decimal": str(bounds.lower),
        "original_upper_decimal": str(bounds.upper),
    }
    if assume_triangular:
        metadata["distribution_assumption"] = "triangular_optional"

    return UncertaintyEnvelope(
        point_estimate=float(bounds.value),
        confidence_interval=(float(bounds.lower), float(bounds.upper)),
        confidence_level=None,
        distribution_family=distribution,
        source=UncertaintySource.TRUST,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        is_heuristic_ci=False,
        gate_eligible=True,
        metadata=metadata,
    )


__all__ = ["envelope_from_trust_bounds"]
