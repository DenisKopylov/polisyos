"""Public builtins noop module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState

_NOOP_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_noop@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="No-op",
    description="No-op node for engine smoke tests.",
    tags=["builtin"],
    capabilities=Capability.SCIENTIST_NODE,
)

_NOOP_SPEC = NodeSpec(metadata=_NOOP_METADATA)


@dataclass(frozen=True)
class NoopNode:
    """Identity node used when a DAG edge needs an executable placeholder with no side effects."""

    @property
    def spec(self) -> NodeSpec:
        return _NOOP_SPEC

    def bind(self, params: dict[str, object]) -> NoopNode:
        return self

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return NodeOutcome(status="ok", state=state)
