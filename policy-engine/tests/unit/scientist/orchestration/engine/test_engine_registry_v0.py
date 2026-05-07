from __future__ import annotations

import pytest
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.builtins import NoopNode
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import UnknownNodeError
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState


class DummyNode:
    def __init__(self, component_id: str) -> None:
        metadata = ComponentMetadata(
            component_id=ComponentId.parse(component_id),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Dummy",
            description="Dummy",
            capabilities=Capability.SCIENTIST_NODE,
        )
        self._spec = NodeSpec(metadata=metadata)

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return NodeOutcome(status="ok", state=state)


def test_registry_register_and_get():
    registry = NodeRegistry()
    registry.register(NoopNode())

    node = registry.get("scientist.node_noop@1.0.0")
    assert node.spec.metadata.component_id == ComponentId.parse("scientist.node_noop@1.0.0")

    specs = registry.list(capability=Capability.SCIENTIST_NODE)
    assert specs


def test_registry_rejects_conflicting_versions():
    registry = NodeRegistry()
    registry.register(DummyNode("scientist.node_dummy@1.0.0"))
    with pytest.raises(ValueError):
        registry.register(DummyNode("scientist.node_dummy@1.1.0"))


def test_registry_unknown_node():
    registry = NodeRegistry()
    with pytest.raises(UnknownNodeError):
        registry.get("scientist.node_missing@1.0.0")
