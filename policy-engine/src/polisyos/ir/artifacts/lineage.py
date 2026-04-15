"""Normalized artifact lineage graph for IR-level dependency analysis."""
from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.artifacts.contracts import ArtifactID


class ArtifactLineageNodeKind(str, Enum):
    """Kinds of nodes that can appear in the lineage graph."""

    ARTIFACT = "artifact"
    TASK = "task"


class ArtifactLineageRelationKind(str, Enum):
    """Directed lineage edge semantics."""

    PRODUCED_BY = "produced_by"
    CONSUMED_BY = "consumed_by"
    DERIVED_FROM = "derived_from"
    INVALIDATED_BY = "invalidated_by"


class ArtifactTaskBinding(BaseModel):
    """Attach semantic task ids to one or more produced/consumed artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    task_kind: str = "task"
    produced_artifact_ids: tuple[ArtifactID, ...] = ()
    consumed_artifact_ids: tuple[ArtifactID, ...] = ()
    invalidated_artifact_ids: tuple[ArtifactID, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactLineageNode(BaseModel):
    """One artifact or task vertex in the normalized lineage graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str
    kind: ArtifactLineageNodeKind
    artifact_id: ArtifactID | None = None
    task_id: str | None = None
    artifact_kind: str | None = None
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactLineageEdge(BaseModel):
    """One directed lineage relation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_node_id: str
    target_node_id: str
    relation: ArtifactLineageRelationKind
    role: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactLineageGraph(BaseModel):
    """Normalized lineage graph built from manifests plus optional task bindings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    nodes: tuple[ArtifactLineageNode, ...] = ()
    edges: tuple[ArtifactLineageEdge, ...] = ()

    def _artifact_node_id(self, artifact_id: ArtifactID | str) -> str:
        return f"artifact:{artifact_id}"

    def produced_by(self, artifact_id: ArtifactID | str) -> tuple[str, ...]:
        node_id = self._artifact_node_id(ArtifactID.model_validate(str(artifact_id)))
        return tuple(
            sorted(
                edge.target_node_id.split("task:", 1)[1]
                for edge in self.edges
                if edge.source_node_id == node_id
                and edge.relation is ArtifactLineageRelationKind.PRODUCED_BY
                and edge.target_node_id.startswith("task:")
            )
        )

    def consumed_by(self, artifact_id: ArtifactID | str) -> tuple[str, ...]:
        node_id = self._artifact_node_id(ArtifactID.model_validate(str(artifact_id)))
        return tuple(
            sorted(
                edge.target_node_id.split("task:", 1)[1]
                for edge in self.edges
                if edge.source_node_id == node_id
                and edge.relation is ArtifactLineageRelationKind.CONSUMED_BY
                and edge.target_node_id.startswith("task:")
            )
        )

    def derived_from(self, artifact_id: ArtifactID | str) -> tuple[str, ...]:
        node_id = self._artifact_node_id(ArtifactID.model_validate(str(artifact_id)))
        return tuple(
            sorted(
                edge.target_node_id.split("artifact:", 1)[1]
                for edge in self.edges
                if edge.source_node_id == node_id
                and edge.relation is ArtifactLineageRelationKind.DERIVED_FROM
                and edge.target_node_id.startswith("artifact:")
            )
        )

    def invalidated_by(self, artifact_id: ArtifactID | str) -> tuple[str, ...]:
        node_id = self._artifact_node_id(ArtifactID.model_validate(str(artifact_id)))
        return tuple(
            sorted(
                edge.target_node_id.split("task:", 1)[1]
                for edge in self.edges
                if edge.source_node_id == node_id
                and edge.relation is ArtifactLineageRelationKind.INVALIDATED_BY
                and edge.target_node_id.startswith("task:")
            )
        )

    def upstream_artifact_ids(self, artifact_id: ArtifactID | str) -> tuple[str, ...]:
        """Return the transitive closure of ``derived_from`` edges."""
        start = self._artifact_node_id(ArtifactID.model_validate(str(artifact_id)))
        visited: set[str] = set()
        queue = [start]
        while queue:
            node_id = queue.pop(0)
            for edge in self.edges:
                if edge.source_node_id != node_id:
                    continue
                if edge.relation is not ArtifactLineageRelationKind.DERIVED_FROM:
                    continue
                if edge.target_node_id in visited:
                    continue
                visited.add(edge.target_node_id)
                queue.append(edge.target_node_id)
        return tuple(
            sorted(
                node.split("artifact:", 1)[1]
                for node in visited
                if node.startswith("artifact:")
            )
        )


def _artifact_node_id(artifact_id: ArtifactID) -> str:
    return f"artifact:{artifact_id}"


def _task_node_id(task_id: str) -> str:
    return f"task:{task_id}"


def build_artifact_lineage_graph(
    store: Any,
    *,
    artifact_ids: Iterable[ArtifactID | str] | None = None,
    task_bindings: Iterable[ArtifactTaskBinding] | None = None,
) -> ArtifactLineageGraph:
    """Build a lineage graph from CAS manifests and optional semantic task bindings."""

    if artifact_ids is None:
        iter_ids = getattr(store, "iter_artifact_ids", None)
        if callable(iter_ids):
            artifact_ids = iter_ids()
        else:
            artifact_ids = []

    normalized_ids = tuple(
        ArtifactID.model_validate(str(artifact_id))
        for artifact_id in artifact_ids
    )
    bindings = tuple(
        binding
        if isinstance(binding, ArtifactTaskBinding)
        else ArtifactTaskBinding.model_validate(binding)
        for binding in (task_bindings or ())
    )
    nodes: dict[str, ArtifactLineageNode] = {}
    edges: dict[tuple[str, str, ArtifactLineageRelationKind, str | None], ArtifactLineageEdge] = {}

    def _add_node(node: ArtifactLineageNode) -> None:
        nodes.setdefault(node.node_id, node)

    def _add_edge(edge: ArtifactLineageEdge) -> None:
        key = (edge.source_node_id, edge.target_node_id, edge.relation, edge.role)
        edges.setdefault(key, edge)

    get_manifest = getattr(store, "get_manifest", None)
    for artifact_id in sorted(normalized_ids, key=str):
        manifest = get_manifest(artifact_id) if callable(get_manifest) else None
        node_id = _artifact_node_id(artifact_id)
        _add_node(
            ArtifactLineageNode(
                node_id=node_id,
                kind=ArtifactLineageNodeKind.ARTIFACT,
                artifact_id=artifact_id,
                artifact_kind=getattr(manifest, "kind", None),
                label=str(artifact_id),
            )
        )
        inputs = getattr(manifest, "inputs", ()) if manifest is not None else ()
        for input_ref in sorted(inputs, key=lambda item: (str(item.artifact_id), item.role)):
            upstream_artifact_id = ArtifactID.model_validate(str(input_ref.artifact_id))
            upstream_node_id = _artifact_node_id(upstream_artifact_id)
            _add_node(
                ArtifactLineageNode(
                    node_id=upstream_node_id,
                    kind=ArtifactLineageNodeKind.ARTIFACT,
                    artifact_id=upstream_artifact_id,
                    label=str(upstream_artifact_id),
                )
            )
            _add_edge(
                ArtifactLineageEdge(
                    source_node_id=node_id,
                    target_node_id=upstream_node_id,
                    relation=ArtifactLineageRelationKind.DERIVED_FROM,
                    role=input_ref.role,
                )
            )

    for binding in sorted(bindings, key=lambda item: item.task_id):
        task_node_id = _task_node_id(binding.task_id)
        _add_node(
            ArtifactLineageNode(
                node_id=task_node_id,
                kind=ArtifactLineageNodeKind.TASK,
                task_id=binding.task_id,
                label=binding.task_id,
                metadata={"task_kind": binding.task_kind, **binding.metadata},
            )
        )
        for artifact_id in sorted(binding.produced_artifact_ids, key=str):
            artifact_node_id = _artifact_node_id(artifact_id)
            _add_node(
                ArtifactLineageNode(
                    node_id=artifact_node_id,
                    kind=ArtifactLineageNodeKind.ARTIFACT,
                    artifact_id=artifact_id,
                    label=str(artifact_id),
                )
            )
            _add_edge(
                ArtifactLineageEdge(
                    source_node_id=artifact_node_id,
                    target_node_id=task_node_id,
                    relation=ArtifactLineageRelationKind.PRODUCED_BY,
                )
            )
        for artifact_id in sorted(binding.consumed_artifact_ids, key=str):
            artifact_node_id = _artifact_node_id(artifact_id)
            _add_node(
                ArtifactLineageNode(
                    node_id=artifact_node_id,
                    kind=ArtifactLineageNodeKind.ARTIFACT,
                    artifact_id=artifact_id,
                    label=str(artifact_id),
                )
            )
            _add_edge(
                ArtifactLineageEdge(
                    source_node_id=artifact_node_id,
                    target_node_id=task_node_id,
                    relation=ArtifactLineageRelationKind.CONSUMED_BY,
                )
            )
        for artifact_id in sorted(binding.invalidated_artifact_ids, key=str):
            artifact_node_id = _artifact_node_id(artifact_id)
            _add_node(
                ArtifactLineageNode(
                    node_id=artifact_node_id,
                    kind=ArtifactLineageNodeKind.ARTIFACT,
                    artifact_id=artifact_id,
                    label=str(artifact_id),
                )
            )
            _add_edge(
                ArtifactLineageEdge(
                    source_node_id=artifact_node_id,
                    target_node_id=task_node_id,
                    relation=ArtifactLineageRelationKind.INVALIDATED_BY,
                )
            )

    return ArtifactLineageGraph(
        nodes=tuple(sorted(nodes.values(), key=lambda node: node.node_id)),
        edges=tuple(
            sorted(
                edges.values(),
                key=lambda edge: (
                    edge.source_node_id,
                    edge.target_node_id,
                    edge.relation.value,
                    edge.role or "",
                ),
            )
        ),
    )


__all__ = [
    "ArtifactLineageEdge",
    "ArtifactLineageGraph",
    "ArtifactLineageNode",
    "ArtifactLineageNodeKind",
    "ArtifactLineageRelationKind",
    "ArtifactTaskBinding",
    "build_artifact_lineage_graph",
]
