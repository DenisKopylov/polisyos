"""Public engine registry module API."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from polisyos.core.components import (
    ENTRY_POINT_GROUP_SCIENTIST_NODES,
    Capability,
    ComponentEntry,
    ComponentId,
    ComponentKind,
    ComponentRegistry,
    DuplicateComponentIdPolicy,
    discover_components,
)
from polisyos.core.components.protocols import ComponentProvider
from polisyos.core.registry import BaseRegistry
from polisyos.scientist.engine.errors import UnknownNodeError
from polisyos.scientist.engine.protocol import Node, NodeSpec


@dataclass(slots=True)
class NodeBootstrapReport:
    """Node bootstrap report data model."""
    registered: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    discovery_errors: list[str] = field(default_factory=list)


class NodeRegistry(BaseRegistry[str, Node]):
    """In-process registry for Scientist nodes."""

    def __init__(self) -> None:
        super().__init__(
            key_fn=lambda node: str(node.spec.metadata.component_id),
            indexers={
                "component_key": lambda node: self._component_key(node.spec.metadata.component_id),
            },
        )

    @staticmethod
    def _component_key(component_id: ComponentId) -> str:
        return f"{component_id.namespace}.{component_id.name}"

    def register(self, node: Node, *, override: bool = False) -> None:
        if not isinstance(node, Node):
            raise TypeError("NodeRegistry.register expects a Node instance")
        spec = node.spec
        if spec.metadata.kind != ComponentKind.SCIENTIST_NODE:
            raise ValueError("NodeSpec.metadata.kind must be scientist_node")
        if not (spec.metadata.capabilities & Capability.SCIENTIST_NODE):
            raise ValueError("NodeSpec.metadata.capabilities must include SCIENTIST_NODE")

        node_id = spec.metadata.component_id
        node_id_str = str(node_id)
        component_key = self._component_key(node_id)

        if super().get(node_id_str) is not None and not override:
            raise ValueError(f"Duplicate node_id: {node_id_str}")
        component_versions = self.find("component_key", component_key)
        if component_versions and any(
            str(row.spec.metadata.component_id) != node_id_str for row in component_versions
        ) and not override:
            existing = str(component_versions[0].spec.metadata.component_id)
            raise ValueError(
                f"Conflicting node versions for {component_key}: {existing} vs {node_id_str}"
            )

        super().register(node, override=override)

    def register_provider(self, provider: ComponentProvider) -> None:
        metadata = provider.metadata
        if metadata.kind != ComponentKind.SCIENTIST_NODE:
            raise ValueError("Provider metadata.kind must be scientist_node")
        if not (metadata.capabilities & Capability.SCIENTIST_NODE):
            raise ValueError("Provider metadata must include SCIENTIST_NODE capability")
        node = provider.create()
        if not isinstance(node, Node):
            raise TypeError("ComponentProvider.create() must return a Node instance")
        if str(metadata.component_id) != str(node.spec.metadata.component_id):
            raise ValueError(
                "Provider metadata component_id must match "
                "node.spec.metadata.component_id"
            )
        self.register(node)

    def get(self, node_id: ComponentId | str) -> Node:
        comp = ComponentId.parse(node_id) if isinstance(node_id, str) else node_id
        node = super().get(str(comp))
        if node is None:
            raise UnknownNodeError(f"Unknown node_id: {comp}")
        return node

    def list(
        self,
        *,
        capability: Capability | None = None,
        tag: str | None = None,
    ) -> list[NodeSpec]:
        items: Iterable[Node] = self.values()
        results: list[NodeSpec] = []
        for node in items:
            spec = node.spec
            if (
                capability is not None
                and not (spec.metadata.capabilities & capability) == capability
            ):
                continue
            if tag is not None and tag not in spec.metadata.tags:
                continue
            results.append(spec)
        return results


def discover_nodes(
    registry: NodeRegistry,
    *,
    components_index: ComponentRegistry | None = None,
    include_dev_scan: bool = True,
) -> NodeBootstrapReport:
    """Discover nodes via component discovery groups or a prebuilt component index."""
    bootstrap_report = NodeBootstrapReport()

    if components_index is None:
        discovered = discover_components(
            groups=[ENTRY_POINT_GROUP_SCIENTIST_NODES],
            include_dev_scan=include_dev_scan,
        )
        component_index = ComponentRegistry()
        for row in discovered.components:
            component_index.register(
                ComponentEntry(
                    metadata=row.metadata,
                    component=row.component,
                    source=row.source,
                ),
                on_duplicate=DuplicateComponentIdPolicy.WARN,
            )
        bootstrap_report.discovery_errors = [
            f"{error.source}:{error.item or '<unknown>'}: {error.message}"
            for error in discovered.errors
        ]
    else:
        component_index = components_index

    entries = component_index.query(kind=ComponentKind.SCIENTIST_NODE)
    for entry in sorted(entries, key=lambda item: str(item.metadata.component_id)):
        provider = entry.component
        component_id = str(entry.metadata.component_id)

        if not isinstance(provider, ComponentProvider):
            bootstrap_report.errors.append(
                f"{component_id}: component must implement ComponentProvider"
            )
            continue

        metadata = provider.metadata
        if metadata.kind != ComponentKind.SCIENTIST_NODE:
            continue
        if not (metadata.capabilities & Capability.SCIENTIST_NODE):
            bootstrap_report.errors.append(
                f"{component_id}: missing SCIENTIST_NODE capability"
            )
            continue

        existing = BaseRegistry.get(registry, component_id)
        override = bool(existing is not None and _source_type(entry) == "dev_scan")
        if existing is not None and not override:
            bootstrap_report.duplicates.append(component_id)
            continue

        if override:
            registry.unregister(component_id)

        try:
            node = provider.create()
            if not isinstance(node, Node):
                raise TypeError("ComponentProvider.create() must return a Node instance")
            registry.register(node, override=override)
            bootstrap_report.registered.append(component_id)
        except Exception as exc:
            bootstrap_report.errors.append(f"{component_id}: {exc}")

    bootstrap_report.registered.sort()
    bootstrap_report.duplicates.sort()
    bootstrap_report.errors.sort()
    bootstrap_report.discovery_errors.sort()
    return bootstrap_report


def _source_type(entry: ComponentEntry) -> str:
    source = entry.source
    if source is None:
        return ""
    return str(getattr(source, "source_type", ""))
