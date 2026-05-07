"""Stable facade for Scientist node implementations and extension discovery.

The package exposes `builtin_nodes()` for direct builtin inventory inspection
and component-provider helpers used by `polisyos.scientist_nodes` discovery.
Individual node classes live under `nodes.builtins.*` and declare their state
contract through `NodeSpec`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.nodes.builtins import builtin_nodes
from polisyos.scientist.nodes.components import (
    SCIENTIST_NODES_API_VERSION,
    ScientistNodeComponent,
    builtin_node_components,
    scientist_node_component,
)

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.registry import (
        NodeBootstrapReport,
        NodeRegistry,
    )


def discover_scientist_nodes(
    registry: NodeRegistry | None = None,
    *,
    include_dev_scan: bool = True,
) -> tuple[NodeRegistry, NodeBootstrapReport]:
    """Discover builtin and external Scientist node components.

    External packages register nodes through the `polisyos.scientist_nodes`
    entry-point group. Builtin nodes use the same component-provider pathway
    through `polisyos.scientist.nodes.components:builtin_node_components`.
    """
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry, discover_nodes

    resolved_registry = registry or NodeRegistry()
    report = discover_nodes(resolved_registry, include_dev_scan=include_dev_scan)
    return resolved_registry, report


__all__ = [
    "SCIENTIST_NODES_API_VERSION",
    "ScientistNodeComponent",
    "builtin_node_components",
    "builtin_nodes",
    "discover_scientist_nodes",
    "scientist_node_component",
]
