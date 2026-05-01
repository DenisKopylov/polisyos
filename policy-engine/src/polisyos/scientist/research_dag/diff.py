"""Minimal Research DAG diffing."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.research_dag.models import (
    FORBIDDEN_PUBLIC_ARTIFACT_KIND_TOKENS,
    FORBIDDEN_PUBLIC_METADATA_TOKENS,
    ResearchDAGArtifact,
    ResearchNodeType,
    is_hidden_artifact_ref,
)

_SOURCE_NODE_TYPES = {
    ResearchNodeType.SOURCE_ACQUISITION,
    ResearchNodeType.SOURCE_READ,
}
_GOVERNANCE_NODE_TYPES = {
    ResearchNodeType.GOVERNANCE,
    ResearchNodeType.PUBLICATION,
}
_FORBIDDEN_PUBLIC_TEXT_TOKENS = (
    *FORBIDDEN_PUBLIC_METADATA_TOKENS,
    *FORBIDDEN_PUBLIC_ARTIFACT_KIND_TOKENS,
)


class ResearchDAGDiff(BaseModel):
    """Compact diff between two research DAG artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    old_run_id: str
    new_run_id: str
    changed_queries: list[str] = Field(default_factory=list)
    changed_sources: list[str] = Field(default_factory=list)
    changed_snippets: list[str] = Field(default_factory=list)
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
        changed_queries=_changed_values(_query_signatures(old), _query_signatures(new)),
        changed_sources=_changed_values(_source_signatures(old), _source_signatures(new)),
        changed_snippets=_changed_values(_snippet_signatures(old), _snippet_signatures(new)),
        changed_claim_ids=_changed_values(_claim_ids(old), _claim_ids(new)),
        changed_governance_outcomes=_changed_values(
            _governance_signatures(old),
            _governance_signatures(new),
        ),
        added_node_ids=sorted(new_node_ids - old_node_ids),
        removed_node_ids=sorted(old_node_ids - new_node_ids),
    )


def _query_signatures(dag: ResearchDAGArtifact) -> set[str]:
    signatures: set[str] = set()
    for node in dag.nodes:
        if node.node_type not in {ResearchNodeType.QUESTION, ResearchNodeType.PLAN}:
            continue
        query = (
            node.metadata.get("query")
            or node.metadata.get("search_query")
            or node.metadata.get("normalized_query")
            or node.summary
        )
        signatures.add(_public_signature(query, fallback="redacted_query"))
    return signatures


def _source_signatures(dag: ResearchDAGArtifact) -> set[str]:
    signatures: set[str] = set()
    for node in dag.nodes:
        if node.node_type not in _SOURCE_NODE_TYPES:
            continue
        public_refs = [
            str(ref.artifact_id)
            for ref in node.artifact_refs
            if not is_hidden_artifact_ref(ref)
        ]
        hidden_ref_count = sum(1 for ref in node.artifact_refs if is_hidden_artifact_ref(ref))
        if public_refs:
            signatures.update(public_refs)
        if hidden_ref_count:
            signatures.add(f"{node.node_type.value}:redacted_source")
            continue
        if public_refs:
            continue
        fallback = f"{node.node_type.value}:redacted_source"
        signature = f"{node.node_type.value}:{node.producer}:{node.summary}"
        safe_signature = _public_signature(signature, fallback=fallback)
        if safe_signature:
            signatures.add(safe_signature)
    return signatures


def _snippet_signatures(dag: ResearchDAGArtifact) -> set[str]:
    signatures: set[str] = set()
    for node in dag.nodes:
        if node.node_type is not ResearchNodeType.EXTRACTION:
            continue
        snippet_id = (
            node.metadata.get("snippet_id")
            or node.metadata.get("source_snippet_id")
            or node.metadata.get("quote_id")
            or node.output_fingerprint
            or node.summary
        )
        signatures.add(_public_signature(snippet_id, fallback="redacted_snippet"))
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
        signature = f"{node.node_type.value}:{node.producer}:{verdict}"
        signatures.add(
            _public_signature(
                signature,
                fallback=f"{node.node_type.value}:redacted_governance",
            )
        )
    return signatures


def _changed_values(old_values: set[str], new_values: set[str]) -> list[str]:
    added = [f"added:{value}" for value in sorted(new_values - old_values)]
    removed = [f"removed:{value}" for value in sorted(old_values - new_values)]
    return added + removed


def _public_signature(value: object, *, fallback: str) -> str:
    text = str(value)
    lowered = text.lower()
    if any(token in lowered for token in _FORBIDDEN_PUBLIC_TEXT_TOKENS):
        return fallback
    return text


__all__ = ["ResearchDAGDiff", "diff_research_dags"]
