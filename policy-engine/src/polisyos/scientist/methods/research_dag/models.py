"""Typed research DAG contracts for Scientist runs."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef

FORBIDDEN_PUBLIC_METADATA_TOKENS: tuple[str, ...] = (
    "hidden_benchmark",
    "hidden_eval",
    "hidden_holdout",
    "private_eval",
    "raw_transcript",
    "system_prompt",
    "developer_prompt",
)
FORBIDDEN_PUBLIC_ARTIFACT_KIND_TOKENS: tuple[str, ...] = (
    "hidden_benchmark",
    "hidden_eval",
    "hidden_holdout",
    "private_eval",
)


class ResearchNodeType(str, Enum):
    """High-level research action families preserved in the DAG."""

    QUESTION = "question"
    PLAN = "plan"
    SOURCE_ACQUISITION = "source_acquisition"
    SOURCE_READ = "source_read"
    EXTRACTION = "extraction"
    VERIFICATION = "verification"
    SYNTHESIS = "synthesis"
    CRITIQUE = "critique"
    GOVERNANCE = "governance"
    PUBLICATION = "publication"


class ResearchDAGNode(BaseModel):
    """One replayable, high-signal research action."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    node_type: ResearchNodeType
    run_id: str = Field(min_length=1)
    workflow_id: str | None = None
    producer: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    input_fingerprint: str | None = None
    output_fingerprint: str | None = None
    safety_labels: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchEdgeType(str, Enum):
    """Typed relationships between research DAG nodes."""

    DEPENDS_ON = "depends_on"
    SUPPORTS = "supports"
    REFUTES = "refutes"
    SUMMARIZES = "summarizes"
    DERIVES = "derives"
    GATES = "gates"
    SUPERSEDES = "supersedes"


class ResearchDAGEdge(BaseModel):
    """Directed relation between two research nodes."""

    model_config = ConfigDict(extra="forbid")

    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    edge_type: ResearchEdgeType
    claim_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchDAGArtifact(BaseModel):
    """CAS-persisted research DAG sidecar for one Scientist run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    nodes: list[ResearchDAGNode] = Field(min_length=1)
    edges: list[ResearchDAGEdge] = Field(default_factory=list)
    claim_ledger_ref: ArtifactRef | None = None
    hidden_content_redacted: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_graph_shape(self) -> ResearchDAGArtifact:
        node_ids = [node.node_id for node in self.nodes]
        node_id_set = set(node_ids)
        if len(node_ids) != len(node_id_set):
            raise ValueError("ResearchDAGArtifact node_id values must be unique")
        for node in self.nodes:
            if node.run_id != self.run_id:
                raise ValueError("ResearchDAGArtifact node run_id values must match artifact run_id")
            if node.workflow_id is not None and node.workflow_id != self.workflow_id:
                raise ValueError(
                    "ResearchDAGArtifact node workflow_id values must match artifact workflow_id"
                )
        for edge in self.edges:
            if edge.source_node_id not in node_id_set:
                raise ValueError(f"Research DAG edge source is orphaned: {edge.source_node_id}")
            if edge.target_node_id not in node_id_set:
                raise ValueError(f"Research DAG edge target is orphaned: {edge.target_node_id}")
        _raise_if_cyclic(self.nodes, self.edges)
        if self.hidden_content_redacted:
            _raise_if_forbidden_public_metadata(self.metadata, path="metadata")
            for node in self.nodes:
                for ref in node.artifact_refs:
                    if is_hidden_artifact_ref(ref):
                        raise ValueError(
                            "Research DAG public export contains hidden artifact ref: "
                            f"{ref.kind}"
                        )
                _raise_if_forbidden_public_metadata(
                    node.metadata,
                    path=f"nodes.{node.node_id}.metadata",
                )
            for index, edge in enumerate(self.edges):
                _raise_if_forbidden_public_metadata(edge.metadata, path=f"edges.{index}.metadata")
        return self


def has_forbidden_public_metadata(value: Any) -> bool:
    """Return whether a value carries hidden eval/transcript metadata keys."""

    try:
        _raise_if_forbidden_public_metadata(value, path="value")
    except ValueError:
        return True
    return False


def is_hidden_artifact_ref(ref: ArtifactRef) -> bool:
    """Return whether an artifact ref should be excluded from public DAG exports."""

    kind = str(ref.kind).lower()
    return any(token in kind for token in FORBIDDEN_PUBLIC_ARTIFACT_KIND_TOKENS)


def _raise_if_forbidden_public_metadata(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in FORBIDDEN_PUBLIC_METADATA_TOKENS):
                raise ValueError(f"Research DAG public export contains forbidden metadata: {path}.{key}")
            _raise_if_forbidden_public_metadata(item, path=f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _raise_if_forbidden_public_metadata(item, path=f"{path}[{index}]")


def _raise_if_cyclic(nodes: list[ResearchDAGNode], edges: list[ResearchDAGEdge]) -> None:
    outgoing: dict[str, list[str]] = {node.node_id: [] for node in nodes}
    indegree: dict[str, int] = {node.node_id: 0 for node in nodes}
    for edge in edges:
        outgoing[edge.source_node_id].append(edge.target_node_id)
        indegree[edge.target_node_id] += 1

    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for child in outgoing[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(nodes):
        raise ValueError("Research DAG edges must be acyclic")


__all__ = [
    "FORBIDDEN_PUBLIC_ARTIFACT_KIND_TOKENS",
    "FORBIDDEN_PUBLIC_METADATA_TOKENS",
    "ResearchDAGArtifact",
    "ResearchDAGEdge",
    "ResearchDAGNode",
    "ResearchEdgeType",
    "ResearchNodeType",
    "has_forbidden_public_metadata",
    "is_hidden_artifact_ref",
]
