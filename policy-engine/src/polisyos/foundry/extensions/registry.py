"""Canonical registry integration for Foundry method extensions."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from polisyos.core.components import (
    ComponentDiscoveryManifest,
    ComponentEntry,
    ComponentRegistry,
    DuplicateComponentIdPolicy,
)
from polisyos.foundry.methods.base import FoundryMethod
from polisyos.foundry.methods.components.bridge import (
    _BOOTSTRAP_LOCK,
    ComponentsBridgeError,
    bootstrap_method_registry_from_components,
)
from polisyos.foundry.methods.selection.registry import (
    MethodEntry,
    MethodRegistry,
    RegistrySnapshot,
    get_registry,
    get_registry_audit_log,
    registry_scope,
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
    discovery_manifest: ComponentDiscoveryManifest | None = None
    preexisting_method_fqns: tuple[str, ...] = ()
    registry_fqns: tuple[str, ...] = ()
    registry_binding_sha256: str | None = None

    @property
    def success(self) -> bool:
        return not self.errors and not self.discovery_errors


class UnboundFoundryDiscoveryInputError(RuntimeError):
    """Refuse registry mutation when an ambient discovery input is not content-bound."""


def _selected_method_fqn(name: str, version: str | None) -> str:
    if type(name) is not str or not name or (version is not None and type(version) is not str):
        raise ValueError("selected_method_identity_invalid")
    if "@" in name:
        base, selected_version = name.rsplit("@", 1)
        if not base or not selected_version:
            raise ValueError("selected_method_identity_invalid")
        if version is not None and version != selected_version:
            raise ValueError("selected_method_version_conflict")
        return name
    if not version:
        raise ValueError("selected_method_version_missing")
    return f"{name}@{version}"


def _selected_method_entry(fqn: str, registry: MethodRegistry) -> MethodEntry | None:
    entry = registry.get_entry(fqn)
    if entry is not None:
        return entry
    default_registry = MethodRegistry.get_instance()
    if registry is not default_registry or get_registry() is not default_registry:
        return None

    from . import discovery

    # Discover against an isolated active registry without holding the
    # destination lock across imports. Only the selected component is then
    # admitted through the canonical bridge against a fresh locked snapshot.
    with registry_scope():
        index, report = discovery.build_foundry_method_components_index(
            include_builtins=True,
            include_entry_points=False,
            include_dev_scan=False,
        )
    manifest = report.manifest
    canonical_target = discovery._DEFAULT_BUILTIN_LOADER[0]
    if (
        report.errors
        or manifest is None
        or not manifest.is_bound
        or manifest.builtin_loaders != (canonical_target,)
        or manifest.entry_point_groups
        or manifest.entry_points
        or manifest.dev_scan_enabled
        or manifest.dev_scan_roots
        or manifest.dev_scan_files
    ):
        refusal = UnboundFoundryDiscoveryInputError("selected_method_builtin_discovery_not_bound")
        for error in report.errors:
            refusal.add_note(f"{error.source}:{error.item or '<unknown>'}: {error.message}")
        raise refusal
    selected = index.get(fqn)
    if selected is None:
        return None
    if str(selected.metadata.component_id) != fqn or fqn not in {
        row.component_id for row in manifest.components
    }:
        raise UnboundFoundryDiscoveryInputError(
            "selected_method_builtin_manifest_membership_mismatch"
        )
    selected_index = ComponentRegistry()
    selected_index.register(selected)

    # Match the canonical bridge's admission-lock -> destination-lock order.
    # Recheck after discovery because another admission may have supplied the
    # exact entry while imports were in progress.
    with _BOOTSTRAP_LOCK, registry.snapshot_scope() as before:
        entry = registry.get_entry(fqn)
        if entry is not None:
            return entry
        bridge = bootstrap_method_registry_from_components(
            selected_index,
            registry,
            allow_dev_overrides=False,
            mutate_registry_default_policy=False,
        )
        if bridge.errors or bridge.duplicates or bridge.registered != [fqn]:
            raise UnboundFoundryDiscoveryInputError(
                "selected_method_builtin_registry_admission_failed"
            )
        after = registry.snapshot()
        before_entries = {row.fqn: row for row in before.entries()}
        after_entries = {row.fqn: row for row in after.entries()}
        if set(after_entries) != {*before_entries, fqn} or any(
            after_entries[name] != value for name, value in before_entries.items()
        ):
            raise UnboundFoundryDiscoveryInputError(
                "selected_method_builtin_registry_footprint_mismatch"
            )
        return registry.get_entry(fqn)


def resolve_selected_method_entry(
    name: str,
    *,
    version: str | None = None,
    registry: MethodRegistry | None = None,
) -> MethodEntry | None:
    """Resolve one exact selected signature, admitting only a bound builtin miss.

    Args:
        name: Fully qualified method name, with or without its version suffix.
        version: Selected version; required when ``name`` has no suffix.
        registry: Explicit configured registry. Non-default registries remain
            lookup-only and are never populated from builtin discovery.

    Returns:
        The selected entry, or None for an unknown method or version.

    Raises:
        ValueError: If the selection has no version or its two versions conflict.
        UnboundFoundryDiscoveryInputError: If a cold builtin's complete discovery
            or its admission into the destination registry is not established.
    """
    fqn = _selected_method_fqn(name, version)
    selected_registry = registry if registry is not None else get_registry()
    return _selected_method_entry(fqn, selected_registry)


def resolve_selected_method(
    name: str,
    *,
    version: str | None = None,
    registry: MethodRegistry | None = None,
) -> type[FoundryMethod[Any, Any]]:
    """Load the exact selected method class without a newest-version fallback.

    Args:
        name: Fully qualified method name, optionally including its version.
        version: Selected version when it is not included in the name.
        registry: Explicit registry; isolated registries remain lookup-only.

    Returns:
        The actual class of the exact selected registered method.

    Raises:
        ValueError: If the version is missing or conflicts with the name.
        MethodNotFoundError: If that exact method/version is unavailable.
        UnboundFoundryDiscoveryInputError: If a cold builtin cannot be admitted.
    """
    from polisyos.foundry.methods.exceptions import MethodNotFoundError

    fqn = _selected_method_fqn(name, version)
    selected_registry = registry if registry is not None else get_registry()
    if _selected_method_entry(fqn, selected_registry) is None:
        raise MethodNotFoundError(fqn)
    return selected_registry.get(fqn)


def bootstrap_foundry_method_registry(
    registry: MethodRegistry | None = None,
    *,
    components_index: ComponentRegistry | None = None,
    include_builtins: bool = True,
    include_entry_points: bool = True,
    include_dev_scan: bool = True,
    dev_scan_paths: Sequence[Path | str] | None = None,
    duplicate_policy: DuplicateComponentIdPolicy = DuplicateComponentIdPolicy.WARN,
    require_bound_discovery_manifest: bool = False,
) -> FoundryExtensionRegistryReport:
    """Discover Foundry method plugins and register them into a `MethodRegistry`."""
    method_registry = registry if registry is not None else get_registry()
    preexisting_method_fqns = tuple(entry.fqn for entry in method_registry.snapshot().entries())

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
        discovery_manifest = discovery_report.manifest
        if require_bound_discovery_manifest and (
            discovery_manifest is None or not discovery_manifest.is_bound
        ):
            if discovery_manifest is None:
                reasons = ("discovery_manifest_missing",)
            else:
                predicate_reasons = tuple(
                    f"predicate_provenance_not_admitted:{row.predicate}:{row.classification}"
                    for row in discovery_manifest.predicate_provenance
                    if row.classification not in {"recomputed", "independently_reconciled"}
                )
                reasons = tuple(
                    dict.fromkeys((*discovery_manifest.unbound_inputs, *predicate_reasons))
                )
                if not reasons:
                    reasons = ("discovery_manifest_not_bound",)
            raise UnboundFoundryDiscoveryInputError(
                "unbound_foundry_discovery_input:" + "|".join(reasons)
            )
    else:
        discovery_errors = []
        sources_processed = 0
        discovery_manifest = None
        if require_bound_discovery_manifest:
            raise UnboundFoundryDiscoveryInputError(
                "unbound_foundry_discovery_input:discovery_manifest_missing:"
                "caller_supplied_components_index"
            )

    bridge_report = bootstrap_method_registry_from_components(
        components_index,
        method_registry,
    )
    admitted_snapshot = method_registry.snapshot()
    return FoundryExtensionRegistryReport(
        registered=bridge_report.registered,
        duplicates=bridge_report.duplicates,
        errors=bridge_report.errors,
        discovery_errors=discovery_errors,
        components_total=len(components_index.list_all()),
        sources_processed=sources_processed,
        discovery_manifest=discovery_manifest,
        preexisting_method_fqns=preexisting_method_fqns,
        registry_fqns=tuple(entry.fqn for entry in admitted_snapshot.entries()),
        registry_binding_sha256=_method_registry_snapshot_binding_sha256(admitted_snapshot),
    )


@contextmanager
def controlled_builtin_foundry_method_registry_scope() -> Iterator[
    tuple[MethodRegistry, FoundryExtensionRegistryReport]
]:
    """Yield a fresh registry whose governed basis is bound builtins only.

    Raises:
        UnboundFoundryDiscoveryInputError: If the controlled discovery basis is
            unbound or its component bridge cannot be admitted completely.
    """

    with registry_scope() as registry:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            report = bootstrap_foundry_method_registry(
                registry,
                include_builtins=True,
                include_entry_points=False,
                include_dev_scan=False,
                require_bound_discovery_manifest=True,
            )
        if not report.success:
            raise UnboundFoundryDiscoveryInputError("controlled_foundry_registry_bootstrap_failed")
        yield registry, report


def _method_registry_snapshot_binding_sha256(snapshot: RegistrySnapshot) -> str:
    """Content-bind one already-frozen registry snapshot."""
    rows = [
        {
            "fqn": entry.fqn,
            "signature_digest": entry.signature.stable_digest(),
            "representation_digest": entry.signature.representation_digest(),
            "metadata_digest": entry.metadata.stable_digest(),
            "import_module": entry.import_module,
            "import_qualname": entry.import_qualname,
        }
        for entry in snapshot.entries()
    ]
    encoded = json.dumps(
        rows,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


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
    value = getattr(
        importlib.import_module("polisyos.foundry.methods.catalog.mechanism.runtime_registry"),
        name,
    )
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
        "UnboundFoundryDiscoveryInputError",
        "bootstrap_builtin_foundry_method_family",
        "bootstrap_foundry_method_registry",
        "controlled_builtin_foundry_method_registry_scope",
        "get_registry",
        "get_registry_audit_log",
        "register_foundry_method_plugin",
        "resolve_selected_method",
        "resolve_selected_method_entry",
        "registry_scope",
    ]
)
