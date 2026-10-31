"""The production registry exposes the protected Phase-5 candidate producer."""

from polisyos.scientist.nodes.builtins.decide.evaluate_verified_policy_phase5 import (
    EvaluateVerifiedPolicyPhase5Node,
)
from polisyos.scientist.orchestration.engine.protocol import InputAwareNodeSpec
from polisyos.scientist.orchestration.workflows.builder import build_registry_with_builtin_nodes


def test_production_registry_selects_the_restricted_phase5_builtin() -> None:
    registry = build_registry_with_builtin_nodes(include_discovered_nodes=False)
    node = registry.get("scientist.node_evaluate_verified_policy_phase5@1.0.0")

    assert isinstance(node, EvaluateVerifiedPolicyPhase5Node)
    assert isinstance(node.spec, InputAwareNodeSpec)
    assert node.spec.input_contract.contract_id == "policy_verified_phase5.v1"
    assert node.spec.input_contract.component_id == str(node.spec.metadata.component_id)
