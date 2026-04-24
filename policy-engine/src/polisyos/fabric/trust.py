"""Public fabric trust module API."""

from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import UncertaintyBounds, UncertaintyBoundsRef
from polisyos.fabric.trust_adapter import envelope_from_trust_bounds
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope


def two_pass_compare(
    optimistic_value: float,
    pessimistic_value: float,
    *,
    method: str = "two_pass_compare",
) -> UncertaintyBounds:
    """Two pass compare helper."""
    lower = Decimal(str(min(optimistic_value, pessimistic_value)))
    upper = Decimal(str(max(optimistic_value, pessimistic_value)))
    value = (lower + upper) / Decimal("2")
    return UncertaintyBounds(value=value, lower=lower, upper=upper, method=method)


def two_pass_compare_with_envelope(
    optimistic_value: float,
    pessimistic_value: float,
    *,
    method: str = "two_pass_compare",
    trust_policy_id: str | None = None,
    assume_triangular: bool = False,
) -> tuple[UncertaintyBounds, UncertaintyEnvelope]:
    """Two pass compare with envelope helper."""
    bounds = two_pass_compare(
        optimistic_value=optimistic_value,
        pessimistic_value=pessimistic_value,
        method=method,
    )
    envelope = envelope_from_trust_bounds(
        bounds,
        trust_policy_id=trust_policy_id,
        assume_triangular=assume_triangular,
    )
    return bounds, envelope


def persist_uncertainty_bounds(
    store: FileSystemCAS,
    bounds: UncertaintyBounds,
    *,
    schema_name: str = "fabric.uncertainty_bounds",
    schema_version: str = "1.0",
) -> UncertaintyBoundsRef:
    """Persist uncertainty bounds helper."""
    ref = store.put_json(
        bounds.model_dump(),
        opts=PutOptions(
            kind="fabric.uncertainty_bounds",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
        ),
    )
    return UncertaintyBoundsRef.model_validate(ref.model_dump())
