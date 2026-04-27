"""Minimal Research DAG diffing."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.research_dag.models import ResearchDAGArtifact, ResearchNodeType

_SOURCE_NODE_TYPES = {
    ResearchNodeType.SOURCE_ACQUISITION,
    ResearchNodeType.SOURCE_READ,
}
_GOVERNANCE_NODE_TYPES = {
    ResearchNodeType.GOVERNANCE,
    ResearchNodeType.PUBLICATION,
}


class ResearchDAGDiff(BaseModel):
    """Compact diff between two research DAG artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    old_run_id: str
    new_run_id: str
    changed_sources: list[str] = Field(default_factory=list)
    changed_claim_ids: list[str] = Field(default_factory=list)
    changed_governance_outcomes: list[str] = Field(default_factory=list)
    added_node_ids: list[str] = Field(default_factory=list)
    removed_node_ids: list[str] = Field(default_factory=list)


def diff_research_dags(old: ResearchDAGArtifact, new: ResearchDAGArtifact) -> ResearchDAGDiff:
    """Compare two DAGs by source, claim, and governance/publication signals."""

    old_node_ids = {node.node_id for node in old.nodes}
    new_node_ids = {node.node_id for node in new.nodes}
    return ResearchDAGDiff(
        old_run_id=old.run_id,
        new_run_id=new.run_id,
        changed_sources=_changed_values(_source_signatures(old), _source_signatures(new)),
        changed_claim_ids=_changed_values(_claim_ids(old), _claim_ids(new)),
        changed_governance_outcomes=_changed_values(
            _governance_signatures(old),
            _governance_signatures(new),
        ),
        added_node_ids=sorted(new_node_ids - old_node_ids),
        removed_node_ids=sorted(old_node_ids - new_node_ids),
    )


def _source_signatures(dag: ResearchDAGArtifact) -> set[str]:
    signatures: set[str] = set()
    for node in dag.nodes:
        if node.node_type not in _SOURCE_NODE_TYPES:
            continue
        refs = [str(ref.artifact_id) for ref in node.artifact_refs]
        if refs:
            signatures.update(refs)
        else:
            signatures.add(f"{node.node_type.value}:{node.producer}:{node.summary}")
    return signatures


def _claim_ids(dag: ResearchDAGArtifact) -> set[str]:
    claim_ids: set[str] = set()
    for node in dag.nodes:
        claim_ids.update(node.claim_ids)
    for edge in dag.edges:
        claim_ids.update(edge.claim_ids)
    return claim_ids


def _governance_signatures(dag: ResearchDAGArtifact) -> set[str]:
    signatures: set[str] = set()
    for node in dag.nodes:
        if node.node_type not in _GOVERNANCE_NODE_TYPES:
            continue
        verdict = (
            node.metadata.get("verdict")
            or node.metadata.get("decision")
            or node.metadata.get("status")
            or node.summary
        )
        signatures.add(f"{node.node_type.value}:{node.producer}:{verdict}")
    return signatures


def _changed_values(old_values: set[str], new_values: set[str]) -> list[str]:
    added = [f"added:{value}" for value in sorted(new_values - old_values)]
    removed = [f"removed:{value}" for value in sorted(old_values - new_values)]
    return added + removed


__all__ = ["ResearchDAGDiff", "diff_research_dags"]
