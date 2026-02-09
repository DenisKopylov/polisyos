from __future__ import annotations

from typing import Iterable

from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
    ENTRY_POINT_GROUP_SCIENTIST_NODES,
    discover_components,
)
from polisyos.core.components.protocols import ComponentProvider
from polisyos.core.registry.generic import GenericRegistry

from polisyos.scientist.engine.errors import UnknownNodeError
from polisyos.scientist.engine.protocol import Node, NodeSpec


class NodeRegistry:
    """In-process registry for Scientist nodes."""

    def __init__(self) -> None:
        self._nodes = GenericRegistry[str, Node](
            key_fn=lambda node: str(node.spec.metadata.component_id),
            indexers={
                "component_key": lambda node: self._component_key(node.spec.metadata.component_id),
            },
        )

    @staticmethod
    def _component_key(component_id: ComponentId) -> str:
        return f"{component_id.namespace}.{component_id.name}"

    def register(self, node: Node) -> None:
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

        if self._nodes.get(node_id_str) is not None:
            raise ValueError(f"Duplicate node_id: {node_id_str}")
        component_versions = self._nodes.find("component_key", component_key)
        if component_versions and any(
            str(row.spec.metadata.component_id) != node_id_str for row in component_versions
        ):
            existing = str(component_versions[0].spec.metadata.component_id)
            raise ValueError(
                f"Conflicting node versions for {component_key}: {existing} vs {node_id_str}"
            )

        self._nodes.register(node)

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
            raise ValueError("Provider metadata component_id must match node.spec.metadata.component_id")
        self.register(node)

    def get(self, node_id: ComponentId | str) -> Node:
        comp = ComponentId.parse(node_id) if isinstance(node_id, str) else node_id
        node = self._nodes.get(str(comp))
        if node is None:
            raise UnknownNodeError(f"Unknown node_id: {comp}")
        return node

    def list(
        self,
        *,
        capability: Capability | None = None,
        tag: str | None = None,
    ) -> list[NodeSpec]:
        items: Iterable[Node] = self._nodes.values()
        results: list[NodeSpec] = []
        for node in items:
            spec = node.spec
            if capability is not None and not (spec.metadata.capabilities & capability) == capability:
                continue
            if tag is not None and tag not in spec.metadata.tags:
                continue
            results.append(spec)
        return results


def discover_nodes(registry: NodeRegistry) -> None:
    """Discover nodes via component discovery groups."""
    report = discover_components(groups=[ENTRY_POINT_GROUP_SCIENTIST_NODES])
    for item in report.components:
        provider = item.component
        if not isinstance(provider, ComponentProvider):
            continue
        metadata = provider.metadata
        if metadata.kind != ComponentKind.SCIENTIST_NODE:
            continue
        if metadata.capabilities & Capability.SCIENTIST_NODE:
            registry.register_provider(provider)
