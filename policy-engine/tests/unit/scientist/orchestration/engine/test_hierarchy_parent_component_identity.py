"""Pin the actual composition parent to its engine-observed implementation."""

import pytest

from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
    RunHierarchicalPolicySearchNode,
)
from polisyos.scientist.orchestration.engine.component_identity import (
    capture_engine_component_identity,
    matches_engine_component_identity,
)


def test_hierarchy_identity_reconciles_actual_producer_and_rejects_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node = RunHierarchicalPolicySearchNode()
    component_id = str(node.spec.metadata.component_id)
    identity = capture_engine_component_identity(node, component_id, {})
    assert identity is not None
    assert matches_engine_component_identity(identity, component_id, {})
    assert capture_engine_component_identity(object(), component_id, {}) is None
    monkeypatch.setattr(RunHierarchicalPolicySearchNode, "execute", lambda *_args: None)
    assert capture_engine_component_identity(node, component_id, {}) is None
    assert not matches_engine_component_identity(identity, component_id, {})
