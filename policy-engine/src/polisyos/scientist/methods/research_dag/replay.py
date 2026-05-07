"""High-level replay and replay planning for research DAG artifacts."""

from __future__ import annotations

from collections import defaultdict, deque
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.research_dag.models import (
    FORBIDDEN_PUBLIC_ARTIFACT_KIND_TOKENS,
    FORBIDDEN_PUBLIC_METADATA_TOKENS,
    ResearchDAGArtifact,
    ResearchDAGNode,
    ResearchNodeType,
    is_hidden_artifact_ref,
)

_PINNED_REPLAY_NODE_TYPES = {
    ResearchNodeType.SOURCE_ACQUISITION,
    ResearchNodeType.SOURCE_READ,
    ResearchNodeType.EXTRACTION,
    ResearchNodeType.VERIFICATION,
}
_FORBIDDEN_PUBLIC_TEXT_TOKENS = (
    *FORBIDDEN_PUBLIC_METADATA_TOKENS,
    *FORBIDDEN_PUBLIC_ARTIFACT_KIND_TOKENS,
)


class ReplayMode(str, Enum):
    """Supported replay planning modes for Research DAG v2.2."""

    AUDIT_RECONSTRUCTION = "audit_reconstruction"
    PINNED_INPUT_REPLAY = "pinned_input_replay"
    VARIANCE_ENVELOPE = "variance_envelope"


class ResearchReplayPlan(BaseModel):
    """Replay plan over a persisted Research DAG and its pinned artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    workflow_id: str
    mode: ReplayMode
    dag_ref: ArtifactRef
    required_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    live_fetch_required: bool = False
    unsupported_steps: list[str] = Field(default_factory=list)
    replay_status: Literal["available", "legacy_minimal"] = "available"
    variance_envelope: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reject_live_fetch_for_audit_mode(self) -> ResearchReplayPlan:
        if self.mode is ReplayMode.AUDIT_RECONSTRUCTION and self.live_fetch_required:
            raise ValueError("audit replay cannot require live web or provider fetches")
        return self


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
    research_dag_status: Literal["available", "legacy_missing", "legacy_minimal"] = "available"
    replay_status: Literal["available", "legacy_missing", "legacy_minimal"] = "available"
    hidden_content_redacted: bool = True
    unsupported_steps: list[str] = Field(default_factory=list)
    steps: list[ResearchReplayStep] = Field(default_factory=list)


def plan_research_replay(
    dag: ResearchDAGArtifact,
    *,
    dag_ref: ArtifactRef,
    mode: ReplayMode | str = ReplayMode.AUDIT_RECONSTRUCTION,
) -> ResearchReplayPlan:
    """Plan audit/pinned replay without triggering live web or provider calls."""

    resolved_mode = ReplayMode(mode)
    required_refs = _dedupe_artifact_refs(
        ref for node in dag.nodes for ref in node.artifact_refs if not is_hidden_artifact_ref(ref)
    )
    unsupported_steps = _unsupported_steps_for_mode(dag, resolved_mode)
    live_fetch_required = any(_node_requires_live_fetch(node) for node in dag.nodes)
    variance_envelope = _variance_envelope(dag) if resolved_mode is ReplayMode.VARIANCE_ENVELOPE else {}
    return ResearchReplayPlan(
        run_id=dag.run_id,
        workflow_id=dag.workflow_id,
        mode=resolved_mode,
        dag_ref=dag_ref,
        required_artifact_refs=required_refs,
        live_fetch_required=live_fetch_required,
        unsupported_steps=unsupported_steps,
        replay_status=_replay_status_for_dag(dag),
        variance_envelope=variance_envelope,
    )


def replay_research_path(dag: ResearchDAGArtifact) -> ResearchDAGReplay:
    """Reconstruct the high-level research path without raw LLM transcript text."""

    node_by_id = {node.node_id: node for node in dag.nodes}
    ordered_ids = _topological_node_order(dag)
    steps: list[ResearchReplayStep] = []
    for position, node_id in enumerate(ordered_ids, start=1):
        node = node_by_id[node_id]
        steps.append(
            ResearchReplayStep(
                node_id=_public_text(node.node_id, fallback=f"redacted_node_{position}"),
                node_type=node.node_type.value,
                producer=_public_text(node.producer, fallback="redacted_producer"),
                summary=_public_text(node.summary, fallback="Redacted research DAG step."),
                artifact_ids=[
                    str(ref.artifact_id)
                    for ref in node.artifact_refs
                    if not is_hidden_artifact_ref(ref)
                ],
                claim_ids=list(node.claim_ids),
                safety_labels=_public_labels(node.safety_labels),
            )
        )
    return ResearchDAGReplay(
        run_id=dag.run_id,
        workflow_id=dag.workflow_id,
        research_dag_status=_replay_status_for_dag(dag),
        replay_status=_replay_status_for_dag(dag),
        hidden_content_redacted=True,
        unsupported_steps=[
            _public_text(step, fallback="redacted_unsupported_step")
            for step in _unsupported_steps_for_mode(dag, ReplayMode.PINNED_INPUT_REPLAY)
        ],
        steps=steps,
    )


def public_replay_export(dag: ResearchDAGArtifact) -> dict[str, Any]:
    """Return an audit-safe replay export with hidden artifact refs omitted."""

    return replay_research_path(dag).model_dump(mode="json")


def legacy_research_dag_status(research_dag_ref: ArtifactRef | str | None) -> str:
    """Return rendering status for old runs without research_dag_ref."""

    return "available" if research_dag_ref is not None else "legacy_missing"


def legacy_replay_status(dag: ResearchDAGArtifact | None) -> str:
    """Return replay rendering status for old/minimal Research DAG artifacts."""

    if dag is None:
        return "legacy_missing"
    return _replay_status_for_dag(dag)


def _unsupported_steps_for_mode(
    dag: ResearchDAGArtifact,
    mode: ReplayMode,
) -> list[str]:
    unsupported: list[str] = []
    for node in dag.nodes:
        if _node_requires_live_fetch(node):
            node_id = _public_text(node.node_id, fallback="redacted_node")
            unsupported.append(f"{node_id}:live_fetch_required")
            continue
        if mode is ReplayMode.PINNED_INPUT_REPLAY and node.node_type in _PINNED_REPLAY_NODE_TYPES:
            if not _node_has_pinned_replay_material(node):
                node_id = _public_text(node.node_id, fallback="redacted_node")
                unsupported.append(f"{node_id}:missing_pinned_artifact_or_fingerprint")
    return sorted(set(unsupported))


def _node_has_pinned_replay_material(node: ResearchDAGNode) -> bool:
    if any(not is_hidden_artifact_ref(ref) for ref in node.artifact_refs):
        return True
    return bool(
        node.output_fingerprint
        or node.input_fingerprint
        or node.metadata.get("untrusted_content_fingerprint")
        or node.metadata.get("snippet_id")
    )


def _node_requires_live_fetch(node: ResearchDAGNode) -> bool:
    return bool(
        node.metadata.get("live_fetch_required")
        or node.metadata.get("requires_live_fetch")
        or node.metadata.get("requires_live_web")
        or "live_fetch_required" in node.safety_labels
    )


def _replay_status_for_dag(
    dag: ResearchDAGArtifact,
) -> Literal["available", "legacy_minimal"]:
    return (
        "legacy_minimal"
        if _unsupported_steps_for_mode(dag, ReplayMode.PINNED_INPUT_REPLAY)
        else "available"
    )


def _variance_envelope(dag: ResearchDAGArtifact) -> dict[str, Any]:
    variable_nodes = [
        _public_text(node.node_id, fallback="redacted_node")
        for node in dag.nodes
        if _node_requires_live_fetch(node)
        or "llm" in node.producer.lower()
        or "web" in node.producer.lower()
        or "variance" in node.safety_labels
    ]
    return {
        "deterministic_token_replay": False,
        "live_web_replay": False,
        "variable_node_ids": sorted(set(variable_nodes)),
        "bounded_by_pinned_artifacts": bool(
            [ref for node in dag.nodes for ref in node.artifact_refs]
        ),
    }


def _dedupe_artifact_refs(refs: Any) -> list[ArtifactRef]:
    output: list[ArtifactRef] = []
    seen: set[str] = set()
    for ref in refs:
        artifact_id = str(ref.artifact_id)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        output.append(ref)
    return output


def _public_text(value: str, *, fallback: str) -> str:
    text = str(value)
    lowered = text.lower()
    if any(token in lowered for token in _FORBIDDEN_PUBLIC_TEXT_TOKENS):
        return fallback
    return text


def _public_labels(labels: list[str]) -> list[str]:
    output: list[str] = []
    for label in labels:
        safe_label = _public_text(label, fallback="redacted_label")
        if safe_label not in output:
            output.append(safe_label)
    return output


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
    "ReplayMode",
    "ResearchDAGReplay",
    "ResearchReplayPlan",
    "ResearchReplayStep",
    "legacy_replay_status",
    "legacy_research_dag_status",
    "plan_research_replay",
    "public_replay_export",
    "replay_research_path",
]
