"""Public fabric trust module API."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import UncertaintyBounds, UncertaintyBoundsRef
from polisyos.fabric.trust.adapter import envelope_from_trust_bounds

if TYPE_CHECKING:
    from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope


def two_pass_compare(
    optimistic_value: float,
    pessimistic_value: float,
    *,
    method: str = "two_pass_compare",
) -> UncertaintyBounds:
    """Order two scenario values and compute their deterministic midpoint.

    Decimal values are constructed from the string form of each input float;
    the smaller and larger values become the lower and upper bounds. The
    caller-supplied method label is carried into the result. These bounds do
    not represent a probability or a statistically estimated interval.

    Args:
        optimistic_value: Value from the optimistic scenario.
        pessimistic_value: Value from the pessimistic scenario.
        method: Label stored with the resulting bounds.

    Returns:
        Bounds spanning both scenario values, with their arithmetic midpoint.
    """
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
    """Return deterministic scenario bounds and their trust-envelope projection.

    The bounds are computed by :func:`two_pass_compare` and then mapped by
    :func:`envelope_from_trust_bounds`. The envelope's distribution remains
    unknown unless the caller explicitly requests the optional triangular
    assumption; neither result estimates a probability distribution.

    Args:
        optimistic_value: Value from the optimistic scenario.
        pessimistic_value: Value from the pessimistic scenario.
        method: Label stored with the resulting bounds.
        trust_policy_id: Optional identifier copied into envelope metadata.
        assume_triangular: Whether to record a triangular distribution
            assumption in the envelope.

    Returns:
        A pair containing the deterministic bounds and the envelope derived
        from those bounds.
    """
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
    """Store uncertainty bounds in CAS and return their typed artifact reference.

    The serialized model is written as JSON with the Fabric uncertainty-bounds
    artifact kind. The optional schema name and version are recorded in the
    artifact metadata; this function does not recompute or alter the bounds.

    Args:
        store: CAS instance that receives the serialized bounds.
        bounds: Bounds payload to persist.
        schema_name: Artifact schema name, defaulting to the Fabric bounds
            schema.
        schema_version: Artifact schema version recorded with the payload.

    Returns:
        A validated :class:`UncertaintyBoundsRef` for the stored artifact.
    """
    ref = store.put_json(
        bounds.model_dump(),
        opts=PutOptions(
            kind="fabric.uncertainty_bounds",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
        ),
    )
    return UncertaintyBoundsRef.model_validate(ref.model_dump())
