"""Canonical discovery path for Foundry method extensions."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from polisyos.core.components import (
    ComponentEntry,
    ComponentRegistry,
    DuplicateComponentIdPolicy,
)
from polisyos.core.components.discovery import (
    ENTRY_POINT_GROUP_FOUNDRY_METHODS,
    BuiltinLoaderSpec,
    DiscoveryReport,
    discover_components,
)

ENTRY_POINT_GROUP = ENTRY_POINT_GROUP_FOUNDRY_METHODS
BUILTIN_LOADER = (
    "polisyos.foundry.extensions._builtin_loader:builtin_foundry_method_components",
    lambda: _builtin_foundry_method_components(),
)


def discover_foundry_method_components(
    *,
    include_builtins: bool = True,
    include_entry_points: bool = True,
    include_dev_scan: bool = True,
    dev_scan_paths: Sequence[Path | str] | None = None,
    builtin_loaders: Sequence[BuiltinLoaderSpec] | None = None,
) -> DiscoveryReport:
    """Discover Foundry method components from entry points, builtins, and dev roots."""
    groups = [ENTRY_POINT_GROUP] if include_entry_points else []
    loaders: list[BuiltinLoaderSpec] = []
    if include_builtins:
        loaders.append(BUILTIN_LOADER)
    loaders.extend(builtin_loaders or ())

    return discover_components(
        groups=groups,
        include_legacy_group=False,
        include_dev_scan=include_dev_scan,
        dev_scan_paths=dev_scan_paths,
        builtin_loaders=loaders,
    )


def build_foundry_method_components_index(
    *,
    include_builtins: bool = True,
    include_entry_points: bool = True,
    include_dev_scan: bool = True,
    dev_scan_paths: Sequence[Path | str] | None = None,
    duplicate_policy: DuplicateComponentIdPolicy = DuplicateComponentIdPolicy.WARN,
    builtin_loaders: Sequence[BuiltinLoaderSpec] | None = None,
) -> tuple[ComponentRegistry, DiscoveryReport]:
    """Build a component index containing only Foundry method components."""
    report = discover_foundry_method_components(
        include_builtins=include_builtins,
        include_entry_points=include_entry_points,
        include_dev_scan=include_dev_scan,
        dev_scan_paths=dev_scan_paths,
        builtin_loaders=builtin_loaders,
    )

    index = ComponentRegistry()
    for row in report.components:
        index.register(
            ComponentEntry(metadata=row.metadata, component=row.component, source=row.source),
            on_duplicate=duplicate_policy,
        )

    return index, report


__all__ = [
    "BUILTIN_LOADER",
    "ENTRY_POINT_GROUP",
    "build_foundry_method_components_index",
    "discover_foundry_method_components",
]


def _builtin_foundry_method_components() -> object:
    from polisyos.foundry.extensions._builtin_loader import builtin_foundry_method_components

    return builtin_foundry_method_components()
