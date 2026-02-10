from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import Any, Sequence

from .discovery import discover_components
from .registry import ComponentEntry, ComponentRegistry, DuplicateComponentIdPolicy


@dataclass(slots=True)
class BootstrapDomainReport:
    registered: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    discovery_errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors and not self.discovery_errors


@dataclass(slots=True)
class BootstrapReport:
    components_total: int = 0
    sources_processed: int = 0
    discovery_errors: list[str] = field(default_factory=list)
    domains: dict[str, BootstrapDomainReport] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        if self.discovery_errors:
            return False
        return all(report.success for report in self.domains.values())


def build_components_index(
    *,
    groups: Sequence[str] | None = None,
    include_legacy_group: bool = False,
    include_dev_scan: bool = True,
    dev_scan_paths: Sequence[Path | str] | None = None,
    duplicate_policy: DuplicateComponentIdPolicy = DuplicateComponentIdPolicy.WARN,
) -> tuple[ComponentRegistry, Any]:
    """Discover components once and materialize a deterministic component index."""
    discovery_report = discover_components(
        groups=groups,
        include_legacy_group=include_legacy_group,
        include_dev_scan=include_dev_scan,
        dev_scan_paths=dev_scan_paths,
    )

    index = ComponentRegistry()
    for row in discovery_report.components:
        index.register(
            ComponentEntry(metadata=row.metadata, component=row.component, source=row.source),
            on_duplicate=duplicate_policy,
        )

    return index, discovery_report


def bootstrap_plugin_registries(
    components_index: ComponentRegistry,
    *,
    bootstrap_connectors: bool = True,
    bootstrap_methods: bool = True,
    bootstrap_evaluators: bool = True,
    bootstrap_extractors: bool = True,
    bootstrap_providers: bool = True,
    bootstrap_nodes: bool = True,
) -> BootstrapReport:
    """
    Bootstrap all runtime registries from one ComponentRegistry snapshot.

    This keeps discovery/indexing centralized while preserving existing runtime
    registries as execution-time lookup structures.
    """
    report = BootstrapReport(components_total=len(components_index.list_all()))

    if bootstrap_connectors:
        bridge_module = importlib.import_module("polisyos.fabric.connectors.components_bridge")
        bootstrap_connector_registry_from_components = getattr(
            bridge_module,
            "bootstrap_connector_registry_from_components",
        )
        report.domains["connectors"] = _as_domain_report(
            bootstrap_connector_registry_from_components(
                components_index,
            )
        )

    if bootstrap_methods:
        bridge_module = importlib.import_module("polisyos.foundry.methods.components_bridge")
        bootstrap_method_registry_from_components = getattr(
            bridge_module,
            "bootstrap_method_registry_from_components",
        )
        report.domains["methods"] = _as_domain_report(
            bootstrap_method_registry_from_components(components_index)
        )

    if bootstrap_evaluators:
        evaluator_module = importlib.import_module("polisyos.lex.legal_evaluation.evaluator_registry")
        bootstrap_component_evaluators = getattr(evaluator_module, "bootstrap_component_evaluators")
        report.domains["evaluators"] = _as_domain_report(
            bootstrap_component_evaluators(components_index)
        )

    if bootstrap_extractors:
        extractor_module = importlib.import_module("polisyos.fabric.claims.extractor_registry")
        bootstrap_component_extractors = getattr(extractor_module, "bootstrap_component_extractors")
        report.domains["extractors"] = _as_domain_report(
            bootstrap_component_extractors(components_index)
        )

    if bootstrap_providers:
        provider_module = importlib.import_module("polisyos.lex.normpack.provider_registry")
        bootstrap_component_providers = getattr(provider_module, "bootstrap_component_providers")
        report.domains["providers"] = _as_domain_report(
            bootstrap_component_providers(components_index)
        )

    if bootstrap_nodes:
        node_module = importlib.import_module("polisyos.scientist.engine.registry")
        NodeRegistry = getattr(node_module, "NodeRegistry")
        discover_nodes = getattr(node_module, "discover_nodes")
        registry = NodeRegistry()
        node_report = discover_nodes(registry, components_index=components_index)
        report.domains["nodes"] = _as_domain_report(node_report)

    return report


def _as_domain_report(raw: Any) -> BootstrapDomainReport:
    return BootstrapDomainReport(
        registered=sorted(set(_as_list(raw, "registered"))),
        duplicates=sorted(set(_as_list(raw, "duplicates"))),
        errors=sorted(set(_as_list(raw, "errors"))),
        discovery_errors=sorted(set(_as_list(raw, "discovery_errors"))),
    )


def _as_list(raw: Any, attr: str) -> list[str]:
    value = getattr(raw, attr, None)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(item) for item in value]


__all__ = [
    "BootstrapDomainReport",
    "BootstrapReport",
    "build_components_index",
    "bootstrap_plugin_registries",
]
