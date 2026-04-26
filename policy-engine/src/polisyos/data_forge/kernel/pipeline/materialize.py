"""Minimal materialization contracts for asset definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import timedelta

from polisyos.data_forge.errors import DataForgeValidationError
from polisyos.data_forge.kernel.artifacts import RetentionClass

from .assets import AssetKey, AssetSpec
from .partitions import NoPartition, PartitionSpec

F = TypeVar("F")


@dataclass(frozen=True, slots=True)
class MaterializationContext:
    """Execution context passed to a materialization function."""

    run_id: str
    snapshot_id: str | None = None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AssetDefinition:
    """Bind an asset spec to the callable that materializes it."""

    spec: AssetSpec
    materializer: object


def asset(
    *,
    key: AssetKey,
    deps: tuple[AssetKey, ...] = (),
    partitions: PartitionSpec | None = None,
    io: str | None = None,
    schema_id: str | None = None,
    freshness_sla: timedelta | None = None,
    retention: RetentionClass = RetentionClass.HOT,
    owner: str,
) -> Callable[[F], F]:
    """Decorate a callable with a Data Forge asset specification."""

    freshness_sla_seconds = (
        int(freshness_sla.total_seconds()) if freshness_sla is not None else None
    )
    spec = AssetSpec(
        key=key,
        deps=tuple(deps),
        partitions=partitions or NoPartition(),
        io=io,
        schema_id=schema_id,
        freshness_sla_seconds=freshness_sla_seconds,
        retention=retention,
        owner=owner,
    )

    def _decorate(fn: F) -> F:
        fn.__data_forge_asset__ = AssetDefinition(spec=spec, materializer=fn)
        return fn

    return _decorate


def plan_asset_specs(specs: tuple[AssetSpec, ...]) -> tuple[AssetSpec, ...]:
    """Return specs in dependency order and reject missing deps or cycles."""
    by_key = {spec.key: spec for spec in specs}
    ordered: list[AssetSpec] = []
    visiting: set[AssetKey] = set()
    visited: set[AssetKey] = set()

    def visit(key: AssetKey) -> None:
        if key in visited:
            return
        if key in visiting:
            raise DataForgeValidationError(f"cycle detected at asset {key}")
        spec = by_key.get(key)
        if spec is None:
            raise DataForgeValidationError(f"missing asset dependency: {key}")
        visiting.add(key)
        for dep in spec.deps:
            visit(dep)
        visiting.remove(key)
        visited.add(key)
        ordered.append(spec)

    for key in tuple(by_key):
        visit(key)
    return tuple(ordered)


__all__ = ["AssetDefinition", "MaterializationContext", "asset", "plan_asset_specs"]
