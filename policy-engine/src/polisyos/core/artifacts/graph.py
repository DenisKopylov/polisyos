"""Public artifacts graph module API."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from .ids import ArtifactID
from .manifest import ArtifactManifest
from .store import FileSystemCAS


class NodeStatus(str, Enum):
    """Node status public type."""
    PRESENT = "present"
    MISSING = "missing"
    MISSING_BLOB = "missing_blob"
    MISSING_MANIFEST = "missing_manifest"
    CORRUPTED = "corrupted"
    SKIPPED_MAX_DEPTH = "skipped_max_depth"


@dataclass(frozen=True)
class DependencyEdge:
    """Dependency edge public type."""
    parent_id: ArtifactID
    child_id: ArtifactID
    role: str


@dataclass
class DependencyNode:
    """Dependency node implementation."""
    artifact_id: ArtifactID
    role: str | None = None
    kind: str | None = None
    status: NodeStatus = NodeStatus.PRESENT
    byte_size: int = 0
    depth: int = 0
    manifest: ArtifactManifest | None = None

    @property
    def is_present(self) -> bool:
        return self.status == NodeStatus.PRESENT


@dataclass
class DependencyGraph:
    """Dependency graph public type."""
    root_id: ArtifactID
    nodes: dict[str, DependencyNode] = field(default_factory=dict)
    edges: list[DependencyEdge] = field(default_factory=list)

    @property
    def total_size_bytes(self) -> int:
        return sum(node.byte_size for node in self.nodes.values())

    @property
    def total_artifacts(self) -> int:
        return len(self.nodes)

    @property
    def missing_nodes(self) -> list[DependencyNode]:
        return [node for node in self.nodes.values() if not node.is_present]

    @property
    def is_complete(self) -> bool:
        return len(self.missing_nodes) == 0

    def all_artifact_ids(self) -> list[ArtifactID]:
        return [ArtifactID.from_sha256_hex(hex_id) for hex_id in sorted(self.nodes)]


def resolve_dependency_graph(
    store: FileSystemCAS,
    root_id: ArtifactID,
    *,
    root_role: str = "root",
    max_depth: int = 200,
    max_nodes: int = 10_000,
    verify_integrity: bool = True,
) -> DependencyGraph:
    """
    Resolve transitive CAS dependencies through ArtifactManifest.inputs.

    The traversal is iterative (stack-based) to avoid Python recursion limits.
    """
    graph = DependencyGraph(root_id=root_id)
    expanded: set[str] = set()
    stack: deque[tuple[ArtifactID, ArtifactID | None, str, int]] = deque(
        [(root_id, None, root_role, 0)]
    )

    while stack:
        artifact_id, parent_id, role, depth = stack.pop()
        hex_id = artifact_id.hex

        if len(graph.nodes) > max_nodes:
            raise ValueError(f"Dependency graph exceeded max_nodes={max_nodes}")

        node = graph.nodes.get(hex_id)
        if node is None:
            node = DependencyNode(artifact_id=artifact_id, role=role, depth=depth)
            graph.nodes[hex_id] = node

        if parent_id is not None:
            graph.edges.append(
                DependencyEdge(parent_id=parent_id, child_id=artifact_id, role=role)
            )

        if hex_id in expanded:
            continue
        expanded.add(hex_id)

        if depth > max_depth:
            node.status = NodeStatus.SKIPPED_MAX_DEPTH
            continue

        blob_path, manifest_path = store.get_paths(artifact_id)
        blob_exists = blob_path.exists()
        manifest_exists = manifest_path.exists()

        if not blob_exists and not manifest_exists:
            node.status = NodeStatus.MISSING
            continue
        if not blob_exists:
            node.status = NodeStatus.MISSING_BLOB
            continue
        if not manifest_exists:
            node.status = NodeStatus.MISSING_MANIFEST
            continue

        try:
            manifest = store.get_manifest(artifact_id)
        except Exception:
            node.status = NodeStatus.MISSING_MANIFEST
            continue

        node.kind = manifest.kind
        node.byte_size = int(manifest.byte_size)
        node.manifest = manifest

        if verify_integrity:
            verification = store.verify(artifact_id)
            if not verification.ok:
                node.status = NodeStatus.CORRUPTED
                continue

        node.status = NodeStatus.PRESENT
        for input_ref in manifest.inputs:
            stack.append((input_ref.artifact_id, artifact_id, input_ref.role, depth + 1))

    return graph


__all__ = [
    "DependencyEdge",
    "DependencyGraph",
    "DependencyNode",
    "NodeStatus",
    "resolve_dependency_graph",
]
