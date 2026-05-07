"""Component-provider declarations for builtin Scientist DAG nodes."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from polisyos.core.components import Capability, ComponentKind, ComponentMetadata
from polisyos.scientist.nodes.builtins import builtin_nodes

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.scientist.orchestration.engine.protocol import Node

SCIENTIST_NODES_API_VERSION = ">=1.0.0,<2.0.0"


@dataclass(frozen=True)
class ScientistNodeComponent:
    """Component provider wrapper for a Scientist DAG node."""

    metadata: ComponentMetadata
    node_factory: Callable[[], Node]

    def create(self) -> Node:
        """Instantiate the host-side node implementation."""
        return self.node_factory()


def scientist_node_component(node: Node) -> ScientistNodeComponent:
    """Wrap a builtin node in the public component-provider contract."""
    metadata = node.spec.metadata
    if metadata.kind != ComponentKind.SCIENTIST_NODE:
        raise ValueError("Scientist node component metadata.kind must be scientist_node")
    if not (metadata.capabilities & Capability.SCIENTIST_NODE):
        raise ValueError("Scientist node component must declare SCIENTIST_NODE capability")

    return ScientistNodeComponent(metadata=metadata, node_factory=lambda: node)


@lru_cache(maxsize=1)
def builtin_node_components() -> tuple[ScientistNodeComponent, ...]:
    """Return builtin Scientist nodes as component providers."""
    return tuple(scientist_node_component(node) for node in builtin_nodes())


def __getattr__(name: str) -> object:
    if name == "__polisyos_components__":
        return builtin_node_components()
    raise AttributeError(name)


__polisyos_components__: tuple[ScientistNodeComponent, ...]

__all__ = [
    "SCIENTIST_NODES_API_VERSION",
    "ScientistNodeComponent",
    "__polisyos_components__",
    "builtin_node_components",
    "scientist_node_component",
]
