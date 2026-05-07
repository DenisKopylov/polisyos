"""Example node exposed through `polisyos.scientist_nodes`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.state import ExperimentState


_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("example.scientist_node.annotate_state@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"scientist_nodes_api": ">=1.0.0,<2.0.0"},
    domains=["example"],
    jurisdictions=[],
    tags=["external-example", "scientist"],
    capabilities=Capability.SCIENTIST_NODE,
    deps=[],
    display_name="Example Annotate State Node",
    description="Offline Scientist node example for extension authors.",
    provides=["params.example_node_seen"],
)


@dataclass(frozen=True)
class AnnotateStateNode:
    """Scientist node that writes one deterministic marker into state params."""

    spec: NodeSpec

    def execute(self, ctx: object, state: ExperimentState) -> NodeOutcome:
        del ctx
        params = dict(state.params)
        params["example_node_seen"] = True
        return NodeOutcome(status="ok", state=state.model_copy(update={"params": params}))


@dataclass(frozen=True)
class ScientistNodeExampleComponent:
    """Component provider for the example Scientist node."""

    metadata: ComponentMetadata = field(default_factory=lambda: _METADATA)

    def create(self) -> AnnotateStateNode:
        return AnnotateStateNode(
            NodeSpec(
                metadata=self.metadata,
                state_reads=["params"],
                state_writes=["params"],
                produces=["params.example_node_seen"],
            )
        )


annotate_state_node_component = ScientistNodeExampleComponent()

__all__ = [
    "AnnotateStateNode",
    "ScientistNodeExampleComponent",
    "annotate_state_node_component",
]
