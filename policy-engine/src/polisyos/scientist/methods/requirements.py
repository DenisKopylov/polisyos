"""Scientist workflow bridge for method validity requirement compilation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.method_requirement import (
    MethodValidityRequirementArtifact,
    compile_method_validity_requirements,
)
from polisyos.scientist.methods.research_dag.models import (
    ResearchDAGNode,
    ResearchNodeType,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from typing import Any


def compile_method_requirements_for_claims(
    *,
    run_id: str,
    workflow_id: str,
    claims: Sequence[Mapping[str, Any] | object],
    requirement_graph_ref: str | None = None,
) -> MethodValidityRequirementArtifact:
    """Compile claim-bound method requirements from a Scientist workflow."""

    artifact = compile_method_validity_requirements(
        run_id=run_id,
        claims=claims,
        requirement_graph_ref=requirement_graph_ref,
        metadata={
            "workflow_id": workflow_id,
            "producer": "scientist.methods.method_requirement_workflow",
            "bridge_consumers": ["foundry", "ir_analytics_bridge"],
        },
    )
    return artifact


def method_requirements_to_research_dag_node(
    artifact: MethodValidityRequirementArtifact,
    *,
    run_id: str,
    workflow_id: str,
) -> ResearchDAGNode:
    """Project a method requirement artifact into the public Scientist research DAG."""

    requirement_refs = [requirement.requirement_id for requirement in artifact.requirements]
    claim_ids = [requirement.claim_id for requirement in artifact.requirements]
    return ResearchDAGNode(
        node_id=f"{workflow_id}:method-requirement:{artifact.run_id}",
        node_type=ResearchNodeType.VERIFICATION,
        run_id=run_id,
        workflow_id=workflow_id,
        producer="scientist.methods.method_requirement_workflow",
        summary=(
            "Compiled claim-bound MethodValidityRequirementSpec records for Foundry "
            "selection and IR analytics binding."
        ),
        claim_ids=claim_ids,
        metadata={
            "requirement_refs": requirement_refs,
            "bridge_consumers": ["foundry", "ir_analytics_bridge"],
            "requirement_count": len(requirement_refs),
            "capability_reality_label": artifact.capability_reality_label,
        },
    )


__all__ = [
    "compile_method_requirements_for_claims",
    "method_requirements_to_research_dag_node",
]
