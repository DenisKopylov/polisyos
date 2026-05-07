from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from polisyos.core.components import (
    Capability,
    ComponentEntry,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
    ComponentRegistry,
)
from polisyos.core.components.discovery import DiscoverySourceInfo
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry, discover_nodes


def _metadata(component_id: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(component_id),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        domains=[],
        jurisdictions=[],
        tags=["test"],
        capabilities=Capability.SCIENTIST_NODE,
        deps=[],
    )


@dataclass(frozen=True)
class _NodeA:
    spec: NodeSpec

    def execute(self, ctx: Any, state: Any) -> NodeOutcome:
        del ctx
        return NodeOutcome(status="skip", state=state)


@dataclass(frozen=True)
class _NodeB:
    spec: NodeSpec

    def execute(self, ctx: Any, state: Any) -> NodeOutcome:
        del ctx
        return NodeOutcome(status="skip", state=state)


@dataclass(frozen=True)
class _NodeComponent:
    metadata: ComponentMetadata
    node_cls: type

    def create(self) -> object:
        return self.node_cls(NodeSpec(metadata=self.metadata))


def test_discover_nodes_supports_dev_scan_override() -> None:
    component_id = "scientist.node_test_override@1.0.0"
    metadata = _metadata(component_id)

    registry = NodeRegistry()
    registry.register(_NodeA(NodeSpec(metadata=metadata)))

    components_index = ComponentRegistry()
    components_index.register(
        ComponentEntry(
            metadata=metadata,
            component=_NodeComponent(metadata=metadata, node_cls=_NodeB),
            source=DiscoverySourceInfo(source_type="dev_scan", location="tests"),
        )
    )

    report = discover_nodes(registry, components_index=components_index)

    assert report.errors == []
    assert report.duplicates == []
    assert report.registered == [component_id]
    assert isinstance(registry.get(component_id), _NodeB)


def test_discover_nodes_keeps_existing_for_non_dev_duplicate() -> None:
    component_id = "scientist.node_test_duplicate@1.0.0"
    metadata = _metadata(component_id)

    registry = NodeRegistry()
    registry.register(_NodeA(NodeSpec(metadata=metadata)))

    components_index = ComponentRegistry()
    components_index.register(
        ComponentEntry(
            metadata=metadata,
            component=_NodeComponent(metadata=metadata, node_cls=_NodeB),
            source=DiscoverySourceInfo(source_type="entry_point", location="tests"),
        )
    )

    report = discover_nodes(registry, components_index=components_index)

    assert report.errors == []
    assert report.registered == []
    assert report.duplicates == [component_id]
    assert isinstance(registry.get(component_id), _NodeA)


def test_discover_nodes_records_typed_runtime_provider_error() -> None:
    component_id = "scientist.node_test_error@1.0.0"
    metadata = _metadata(component_id)

    class _BrokenComponent(_NodeComponent):
        def create(self) -> object:
            raise RuntimeError("provider exploded")

    registry = NodeRegistry()
    components_index = ComponentRegistry()
    components_index.register(
        ComponentEntry(
            metadata=metadata,
            component=_BrokenComponent(metadata=metadata, node_cls=_NodeB),
            source=DiscoverySourceInfo(source_type="entry_point", location="tests"),
        )
    )

    report = discover_nodes(registry, components_index=components_index)

    assert report.registered == []
    assert report.duplicates == []
    assert report.errors == [f"{component_id}: provider exploded"]


def test_discover_nodes_does_not_swallow_assertion_errors() -> None:
    component_id = "scientist.node_test_assert@1.0.0"
    metadata = _metadata(component_id)

    class _BuggyComponent(_NodeComponent):
        def create(self) -> object:
            raise AssertionError("bug")

    registry = NodeRegistry()
    components_index = ComponentRegistry()
    components_index.register(
        ComponentEntry(
            metadata=metadata,
            component=_BuggyComponent(metadata=metadata, node_cls=_NodeB),
            source=DiscoverySourceInfo(source_type="entry_point", location="tests"),
        )
    )

    with pytest.raises(AssertionError, match="bug"):
        discover_nodes(registry, components_index=components_index)
