from __future__ import annotations

from decimal import Decimal
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import UncertaintyBounds, UncertaintyBoundsRef


def two_pass_compare(
    optimistic_value: float,
    pessimistic_value: float,
    *,
    method: str = "two_pass_compare",
) -> UncertaintyBounds:
    lower = Decimal(str(min(optimistic_value, pessimistic_value)))
    upper = Decimal(str(max(optimistic_value, pessimistic_value)))
    value = (lower + upper) / Decimal("2")
    return UncertaintyBounds(value=value, lower=lower, upper=upper, method=method)


def persist_uncertainty_bounds(
    store: FileSystemCAS,
    bounds: UncertaintyBounds,
    *,
    schema_name: str = "fabric.uncertainty_bounds",
    schema_version: str = "1.0",
) -> UncertaintyBoundsRef:
    ref = store.put_json(
        bounds.model_dump(),
        opts=PutOptions(
            kind="fabric.uncertainty_bounds",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
        ),
    )
    return UncertaintyBoundsRef.model_validate(ref.model_dump())
