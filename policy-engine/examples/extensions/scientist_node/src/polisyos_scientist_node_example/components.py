"""Local dev-scan declaration for the example Scientist node."""

from .node import annotate_state_node_component

__polisyos_components__ = [annotate_state_node_component]

__all__ = ["__polisyos_components__"]
