"""Canonical registry integration for Foundry method extensions."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from polisyos.core.components import ComponentEntry, ComponentRegistry, DuplicateComponentIdPolicy
from polisyos.foundry.methods.components.bridge import (
    ComponentsBridgeError,
    bootstrap_method_registry_from_components,
)
from polisyos.foundry.methods.selection.registry import (
    MethodRegistry,
    get_registry,
    get_registry_audit_log,  # noqa: F401
    registry_scope,  # noqa: F401
)


@dataclass(slots=True)
class FoundryExtensionRegistryReport:
    """Aggregate discovery and method-registry bridge outcomes."""

    registered: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    errors: list[ComponentsBridgeError] = field(default_factory=list)
    discovery_errors: list[str] = field(default_factory=list)
    components_total: int = 0
    sources_processed: int = 0

    @property
    def success(self) -> bool:
        return not self.errors and not self.discovery_errors


def bootstrap_foundry_method_registry(
    registry: MethodRegistry | None = None,
    *,
    components_index: ComponentRegistry | None = None,
    include_builtins: bool = True,
    include_entry_points: bool = True,
    include_dev_scan: bool = True,
    dev_scan_paths: Sequence[Path | str] | None = None,
    duplicate_policy: DuplicateComponentIdPolicy = DuplicateComponentIdPolicy.WARN,
) -> FoundryExtensionRegistryReport:
    """Discover Foundry method plugins and register them into a `MethodRegistry`."""
    method_registry = registry if registry is not None else get_registry()

    if components_index is None:
        from .discovery import build_foundry_method_components_index

        components_index, discovery_report = build_foundry_method_components_index(
            include_builtins=include_builtins,
            include_entry_points=include_entry_points,
            include_dev_scan=include_dev_scan,
            dev_scan_paths=dev_scan_paths,
            duplicate_policy=duplicate_policy,
        )
        discovery_errors = [
            f"{error.source}:{error.item or '<unknown>'}: {error.message}"
            for error in discovery_report.errors
        ]
        sources_processed = discovery_report.sources_processed
    else:
        discovery_errors = []
        sources_processed = 0

    bridge_report = bootstrap_method_registry_from_components(
        components_index,
        method_registry,
    )
    return FoundryExtensionRegistryReport(
        registered=bridge_report.registered,
        duplicates=bridge_report.duplicates,
        errors=bridge_report.errors,
        discovery_errors=discovery_errors,
        components_total=len(components_index.list_all()),
        sources_processed=sources_processed,
    )


def register_foundry_method_plugin(
    plugin: object,
    registry: MethodRegistry | None = None,
    *,
    override: bool = False,
) -> str:
    """Register one already-materialized Foundry method plugin."""
    method_registry = registry if registry is not None else get_registry()
    method_class = plugin.create()  # type: ignore[attr-defined]
    return method_registry.register(method_class, override=override)


def bootstrap_builtin_foundry_method_family(
    family: str,
    registry: MethodRegistry | None = None,
) -> FoundryExtensionRegistryReport:
    """Register one builtin method family through the canonical component bridge."""
    from polisyos.foundry.extensions._builtin_loader import builtin_foundry_method_components

    index = ComponentRegistry()
    for component in builtin_foundry_method_components([family]):
        index.register(
            ComponentEntry(
                metadata=component.metadata,
                component=component,
                source=f"builtin:{family}",
            ),
            on_duplicate=DuplicateComponentIdPolicy.WARN,
        )

    return bootstrap_foundry_method_registry(
        registry,
        components_index=index,
        include_builtins=False,
        include_entry_points=False,
        include_dev_scan=False,
    )


_RUNTIME_IMPORTS = {
    "MECHANISM_REGISTRY",
    "MECHANISM_SPECS",
    "MechanismRuntimeDescriptor",
    "MissingRuntimeMechanismSupportError",
    "UnsupportedRuntimeFidelityError",
    "create_mechanism",
    "create_mechanism_from_spec",
    "get_mechanism_class",
    "get_mechanism_descriptor",
    "get_mechanism_spec",
    "has_runtime_mechanism_support",
    "mechanism_catalog",
    "resolve_runtime_fidelity",
    "validate_mechanism_params",
}


def __getattr__(name: str) -> object:
    if name not in _RUNTIME_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.foundry.extensions.registry' has no attribute {name!r}"
        )
    value = getattr(importlib.import_module("polisyos.foundry._registry"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals()) + list(_RUNTIME_IMPORTS))


__all__ = sorted(
    [
        *_RUNTIME_IMPORTS,
        "ComponentsBridgeError",
        "FoundryExtensionRegistryReport",
        "MethodRegistry",
        "bootstrap_builtin_foundry_method_family",
        "bootstrap_foundry_method_registry",
        "get_registry",
        "get_registry_audit_log",
        "register_foundry_method_plugin",
        "registry_scope",
    ]
)
