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

from polisyos.scientist.engine.errors import UnknownNodeError
from polisyos.scientist.engine.protocol import Node, NodeSpec


class NodeRegistry:
    """In-process registry for Scientist nodes."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._component_keys: dict[str, str] = {}

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

        if node_id_str in self._nodes:
            raise ValueError(f"Duplicate node_id: {node_id_str}")
        if component_key in self._component_keys and self._component_keys[component_key] != node_id_str:
            raise ValueError(
                f"Conflicting node versions for {component_key}: {self._component_keys[component_key]} vs {node_id_str}"
            )

        self._nodes[node_id_str] = node
        self._component_keys[component_key] = node_id_str

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
