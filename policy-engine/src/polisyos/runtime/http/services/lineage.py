"""Resolve artifact dependency DAGs into runtime lineage response DTOs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.artifacts.graph import NodeStatus, resolve_dependency_graph
from polisyos.core.contracts.runtime import (
    ArtifactLineageEdge,
    ArtifactLineageNode,
    ArtifactLineageView,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.protocol import ArtifactStore


class LineageService:
    """Build bounded upstream dependency graphs from CAS manifests.

    Traversal is capped by `default_max_depth` and `default_max_nodes` to keep
    API responses predictable. Missing or corrupted dependencies are surfaced in
    the returned `ArtifactLineageView` rather than raised as hard failures.
    """

    def __init__(
        self,
        *,
        store: ArtifactStore,
        default_max_depth: int = 64,
        default_max_nodes: int = 2000,
        default_timeout_seconds: float = 1.5,
        traversal_batch_size: int = 128,
    ) -> None:
        self._store = store
        self._default_max_depth = max(default_max_depth, 1)
        self._default_max_nodes = max(default_max_nodes, 1)
        self._default_timeout_seconds = max(default_timeout_seconds, 0.01)
        self._traversal_batch_size = max(traversal_batch_size, 1)

    def build_for_artifact_ids(
        self,
        artifact_ids: list[ArtifactID],
        *,
        max_depth: int | None = None,
        max_nodes: int | None = None,
        timeout_seconds: float | None = None,
    ) -> ArtifactLineageView:
        """Return a merged lineage graph for one or more root artifacts."""
        if not artifact_ids:
            return ArtifactLineageView(root_artifact_ids=[])

        depth_limit = max_depth if max_depth is not None else self._default_max_depth
        node_limit = max_nodes if max_nodes is not None else self._default_max_nodes
        timeout_budget = (
            max(float(timeout_seconds), 0.01)
            if timeout_seconds is not None
            else self._default_timeout_seconds
        )

        node_map: dict[str, ArtifactLineageNode] = {}
        edge_map: dict[tuple[str, str, str], ArtifactLineageEdge] = {}
        missing_ids: set[str] = set()
        corrupted_ids: set[str] = set()
        is_complete = True

        for root_id in artifact_ids:
            graph = resolve_dependency_graph(
                self._store,
                root_id,
                max_depth=depth_limit,
                max_nodes=node_limit,
                verify_integrity=True,
                timeout_seconds=timeout_budget,
                batch_size=self._traversal_batch_size,
            )
            if graph.timed_out or not graph.is_complete:
                is_complete = False

            for node in graph.nodes.values():
                artifact_id = str(node.artifact_id)
                status = node.status.value
                existing = node_map.get(artifact_id)
                candidate = ArtifactLineageNode(
                    artifact_id=artifact_id,
                    role=node.role,
                    kind=node.kind,
                    status=status,
                    byte_size=max(int(node.byte_size), 0),
                    depth=max(int(node.depth), 0),
                )
                if existing is None:
                    node_map[artifact_id] = candidate
                else:
                    node_map[artifact_id] = _merge_nodes(existing, candidate)

                if node.status == NodeStatus.CORRUPTED:
                    corrupted_ids.add(artifact_id)
                    is_complete = False
                elif node.status != NodeStatus.PRESENT:
                    missing_ids.add(artifact_id)
                    is_complete = False

            for edge in graph.edges:
                key = (str(edge.parent_id), str(edge.child_id), edge.role)
                if key not in edge_map:
                    edge_map[key] = ArtifactLineageEdge(
                        parent_artifact_id=key[0],
                        child_artifact_id=key[1],
                        role=key[2],
                    )

        nodes = sorted(node_map.values(), key=lambda item: (item.depth, item.artifact_id))
        edges = sorted(
            edge_map.values(),
            key=lambda item: (item.parent_artifact_id, item.child_artifact_id, item.role),
        )
        total_size = sum(node.byte_size for node in nodes)

        return ArtifactLineageView(
            root_artifact_ids=[str(item) for item in artifact_ids],
            total_nodes=len(nodes),
            total_edges=len(edges),
            total_size_bytes=total_size,
            is_complete=is_complete,
            missing_artifact_ids=sorted(missing_ids),
            corrupted_artifact_ids=sorted(corrupted_ids),
            nodes=nodes,
            edges=edges,
        )


def _merge_nodes(lhs: ArtifactLineageNode, rhs: ArtifactLineageNode) -> ArtifactLineageNode:
    best_status = lhs.status
    if lhs.status != "present" and rhs.status == "present":
        best_status = rhs.status
    elif lhs.status != "present" and rhs.status != "present":
        best_status = min(lhs.status, rhs.status)

    return ArtifactLineageNode(
        artifact_id=lhs.artifact_id,
        role=lhs.role or rhs.role,
        kind=lhs.kind or rhs.kind,
        status=best_status,
        byte_size=max(lhs.byte_size, rhs.byte_size),
        depth=min(lhs.depth, rhs.depth),
    )
