"""Minimal high-level replay for research DAG artifacts."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.research_dag.models import ResearchDAGArtifact


class ResearchReplayStep(BaseModel):
    """One public replay step, with raw transcript metadata omitted."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    node_type: str
    producer: str
    summary: str
    artifact_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    safety_labels: list[str] = Field(default_factory=list)


class ResearchDAGReplay(BaseModel):
    """Replayable high-level path through a research DAG."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    workflow_id: str
    research_dag_status: Literal["available", "legacy_missing"] = "available"
    hidden_content_redacted: bool = True
    steps: list[ResearchReplayStep] = Field(default_factory=list)


def replay_research_path(dag: ResearchDAGArtifact) -> ResearchDAGReplay:
    """Reconstruct the high-level research path without raw LLM transcript text."""

    node_by_id = {node.node_id: node for node in dag.nodes}
    ordered_ids = _topological_node_order(dag)
    steps = [
        ResearchReplayStep(
            node_id=node.node_id,
            node_type=node.node_type.value,
            producer=node.producer,
            summary=node.summary,
            artifact_ids=[str(ref.artifact_id) for ref in node.artifact_refs],
            claim_ids=list(node.claim_ids),
            safety_labels=list(node.safety_labels),
        )
        for node_id in ordered_ids
        for node in [node_by_id[node_id]]
    ]
    return ResearchDAGReplay(
        run_id=dag.run_id,
        workflow_id=dag.workflow_id,
        hidden_content_redacted=dag.hidden_content_redacted,
        steps=steps,
    )


def legacy_research_dag_status(research_dag_ref: ArtifactRef | str | None) -> str:
    """Return rendering status for old runs without research_dag_ref."""

    return "available" if research_dag_ref is not None else "legacy_missing"


def _topological_node_order(dag: ResearchDAGArtifact) -> list[str]:
    node_ids = [node.node_id for node in dag.nodes]
    index = {node_id: position for position, node_id in enumerate(node_ids)}
    outgoing: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = dict.fromkeys(node_ids, 0)
    for edge in dag.edges:
        outgoing[edge.source_node_id].append(edge.target_node_id)
        indegree[edge.target_node_id] += 1

    queue = deque(sorted((node_id for node_id, degree in indegree.items() if degree == 0), key=index.get))
    ordered: list[str] = []
    while queue:
        current = queue.popleft()
        ordered.append(current)
        for child in sorted(outgoing[current], key=index.get):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if len(ordered) != len(node_ids):
        return node_ids
    return ordered


__all__ = [
    "ResearchDAGReplay",
    "ResearchReplayStep",
    "legacy_research_dag_status",
    "replay_research_path",
]
