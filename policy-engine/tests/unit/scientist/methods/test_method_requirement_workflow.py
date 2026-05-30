from __future__ import annotations

from polisyos.scientist.methods.requirements import (
    compile_method_requirements_for_claims,
    method_requirements_to_research_dag_node,
)
from polisyos.scientist.methods.research_dag.models import ResearchNodeType


def test_scientist_workflow_compiles_method_requirements_and_dag_node() -> None:
    artifact = compile_method_requirements_for_claims(
        run_id="run_w7c",
        workflow_id="workflow_policy_design",
        claims=[
            {
                "claim_id": "claim_effect",
                "run_id": "run_w7c",
                "claim_type": "causal",
                "claim_family": "causal",
                "claim_use": "decision_support",
                "text": "The intervention improves the outcome.",
                "facet_refs": ["facet_outcome"],
                "obligation_refs": ["obl_method"],
                "method_need_preconditions": [
                    {
                        "precondition_id": "need_causal",
                        "claim_id": "claim_effect",
                        "claim_type": "causal",
                        "method_need": "causal_identification",
                        "reason": "Causal claims require identification.",
                    }
                ],
            }
        ],
    )
    node = method_requirements_to_research_dag_node(
        artifact,
        run_id="run_w7c",
        workflow_id="workflow_policy_design",
    )

    assert artifact.metadata["workflow_id"] == "workflow_policy_design"
    assert artifact.metadata["producer"] == "scientist.methods.method_requirement_workflow"
    assert artifact.requirements[0].claim_id == "claim_effect"
    assert node.node_type is ResearchNodeType.VERIFICATION
    assert node.producer == "scientist.methods.method_requirement_workflow"
    assert node.claim_ids == ["claim_effect"]
    assert node.metadata["requirement_refs"] == [artifact.requirements[0].requirement_id]
    assert node.metadata["bridge_consumers"] == ["foundry", "ir_analytics_bridge"]
