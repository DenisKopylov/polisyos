"""Public fabric trust adapter module API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

if TYPE_CHECKING:
    from polisyos.core.contracts.fabric import UncertaintyBounds


def envelope_from_trust_bounds(
    bounds: UncertaintyBounds,
    *,
    trust_policy_id: str | None = None,
    assume_triangular: bool = False,
) -> UncertaintyEnvelope:
    """Represent explicit trust bounds as a deterministic uncertainty envelope.

    The bounds remain deterministic and do not receive a confidence level.
    Their decimal values are also retained in envelope metadata. Unless
    ``assume_triangular`` is true, the distribution family stays unknown; when
    true, the envelope records that optional assumption as triangular. This
    adapter maps the supplied bounds and does not independently establish the
    provenance or validity of their source.

    Args:
        bounds: Point value and lower/upper bounds to carry into the envelope.
        trust_policy_id: Optional policy identifier copied to envelope metadata.
        assume_triangular: Whether to label the optional triangular distribution
            assumption in the envelope.

    Returns:
        An envelope marked with trust source, deterministic-bound semantics,
        no propagation method, and the supplied numeric interval.
    """
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
