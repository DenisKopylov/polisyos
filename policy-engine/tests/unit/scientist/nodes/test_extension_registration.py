from __future__ import annotations

from polisyos.core.components import Capability, ComponentKind, ComponentProvider
from polisyos.scientist.nodes import discover_scientist_nodes
from polisyos.scientist.nodes.components import (
    SCIENTIST_NODES_API_VERSION,
    builtin_node_components,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry, discover_nodes


def test_builtin_nodes_are_component_providers() -> None:
    components = builtin_node_components()
    component_ids = {str(component.metadata.component_id) for component in components}

    assert SCIENTIST_NODES_API_VERSION == ">=1.0.0,<2.0.0"
    assert "scientist.node_build_data_snapshot@1.0.0" in component_ids
    assert "scientist.node_run_policy_funnel_level5@1.0.0" not in component_ids
    for component in components:
        assert isinstance(component, ComponentProvider)
        assert component.metadata.kind is ComponentKind.SCIENTIST_NODE
        assert component.metadata.capabilities & Capability.SCIENTIST_NODE
        assert str(component.create().spec.metadata.component_id) == str(
            component.metadata.component_id
        )


def test_discover_nodes_loads_builtin_component_loader() -> None:
    registry = NodeRegistry()

    report = discover_nodes(registry, include_entry_points=False, include_dev_scan=False)

    assert report.errors == []
    assert report.discovery_errors == []
    assert "scientist.node_build_data_snapshot@1.0.0" in report.registered
    assert registry.get("scientist.node_build_data_snapshot@1.0.0").spec.metadata.kind is (
        ComponentKind.SCIENTIST_NODE
    )


def test_public_node_discovery_facade_returns_registry_and_report() -> None:
    registry, report = discover_scientist_nodes(include_dev_scan=False)

    assert report.errors == []
    assert "scientist.node_build_decision_packet@1.5.0" in {
        str(spec.metadata.component_id) for spec in registry.list()
    }
