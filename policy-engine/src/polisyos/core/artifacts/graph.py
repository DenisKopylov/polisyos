"""Resolve direct/transitive manifest inputs into an artifact dependency graph."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .ids import ArtifactID
from .manifest import ArtifactManifest, ArtifactRef
from .protocol import resolve_manifest_by_profile


class NodeStatus(str, Enum):
    """Represent artifact availability/integrity status during lineage traversal."""

    PRESENT = "present"
    MISSING = "missing"
    MISSING_BLOB = "missing_blob"
    MISSING_MANIFEST = "missing_manifest"
    CORRUPTED = "corrupted"
    SKIPPED_MAX_DEPTH = "skipped_max_depth"
    SKIPPED_TIMEOUT = "skipped_timeout"


@dataclass(frozen=True)
class DependencyEdge:
    """Represent one directed parent→child manifest edge with an input role label."""

    parent_id: ArtifactID
    child_id: ArtifactID
    role: str
    parent_manifest_profile_sha256: str | None = None
    child_manifest_profile_sha256: str | None = None


@dataclass
class DependencyNode:
    """Store manifest metadata and traversal state for one artifact node."""

    artifact_id: ArtifactID
    role: str | None = None
    kind: str | None = None
    status: NodeStatus = NodeStatus.PRESENT
    byte_size: int = 0
    depth: int = 0
    manifest_profile_sha256: str | None = None
    media_type: str | None = None
    manifest: ArtifactManifest | None = None

    @property
    def is_present(self) -> bool:
        """Return whether this node resolved to an intact CAS artifact."""
        return self.status == NodeStatus.PRESENT


@dataclass
class DependencyGraph:
    """Hold the transitive CAS lineage DAG rooted at one artifact ID."""

    root_id: ArtifactID
    root_manifest_profile_sha256: str | None = None
    nodes: dict[str, DependencyNode] = field(default_factory=dict)
    edges: list[DependencyEdge] = field(default_factory=list)
    timed_out: bool = False

    @property
    def total_size_bytes(self) -> int:
        """Return the sum of known blob sizes across all visited nodes."""
        return sum(node.byte_size for node in self.nodes.values())

    @property
    def total_artifacts(self) -> int:
        """Return the number of unique artifact nodes in the graph."""
        return len(self.nodes)

    @property
    def missing_nodes(self) -> list[DependencyNode]:
        """Return all nodes that are missing, corrupted, or depth-skipped."""
        return [node for node in self.nodes.values() if not node.is_present]

    @property
    def is_complete(self) -> bool:
        """Return `True` when every visited node is present and verified."""
        return len(self.missing_nodes) == 0

    def all_artifact_ids(self) -> list[ArtifactID]:
        """Return all graph node IDs in deterministic hex order."""
        ids = {node.artifact_id.hex: node.artifact_id for node in self.nodes.values()}
        return [ids[hex_id] for hex_id in sorted(ids)]


def resolve_dependency_graph(
    store: Any,
    root_id: ArtifactID | ArtifactRef,
    *,
    root_role: str = "root",
    max_depth: int = 200,
    max_nodes: int = 10_000,
    verify_integrity: bool = True,
    timeout_seconds: float | None = None,
    batch_size: int = 128,
    preserve_manifest_profiles: bool | None = None,
) -> DependencyGraph:
    """
    Resolve transitive CAS dependencies through ArtifactManifest.inputs.

    The traversal is iterative (stack-based) to avoid Python recursion limits.
    """
    root_ref = root_id if isinstance(root_id, ArtifactRef) else None
    root_artifact_id = root_ref.artifact_id if root_ref is not None else root_id
    preserve_profiles = (
        root_ref is not None if preserve_manifest_profiles is None else preserve_manifest_profiles
    )
    root_profile = root_ref.manifest_profile_sha256 if preserve_profiles and root_ref else None
    graph = DependencyGraph(
        root_id=root_artifact_id,
        root_manifest_profile_sha256=root_profile,
    )
    deadline = (
        time.monotonic() + max(float(timeout_seconds), 0.0) if timeout_seconds is not None else None
    )
    budget_check_interval = max(1, int(batch_size))
    visited_since_budget_check = 0
    expanded: set[str] = set()
    stack: deque[tuple[ArtifactID, str | None, ArtifactID | None, str | None, str, int]] = deque(
        [(root_artifact_id, root_profile, None, None, root_role, 0)]
    )

    while stack:
        artifact_id, profile, parent_id, parent_profile, role, depth = stack.pop()
        hex_id = artifact_id.hex
        node_key = _dependency_node_key(hex_id, profile)

        visited_since_budget_check += 1
        if deadline is not None and visited_since_budget_check >= budget_check_interval:
            visited_since_budget_check = 0
            if time.monotonic() >= deadline:
                node = graph.nodes.get(node_key)
                if node is None:
                    node = DependencyNode(
                        artifact_id=artifact_id,
                        role=role,
                        depth=depth,
                        manifest_profile_sha256=profile,
                    )
                    graph.nodes[node_key] = node
                node.status = NodeStatus.SKIPPED_TIMEOUT
                graph.timed_out = True
                break

        if len(graph.nodes) >= max_nodes and node_key not in graph.nodes:
            raise ValueError(f"Dependency graph exceeded max_nodes={max_nodes}")

        node = graph.nodes.get(node_key)
        if node is None:
            node = DependencyNode(
                artifact_id=artifact_id,
                role=role,
                depth=depth,
                manifest_profile_sha256=profile,
            )
            graph.nodes[node_key] = node

        if parent_id is not None:
            graph.edges.append(
                DependencyEdge(
                    parent_id=parent_id,
                    child_id=artifact_id,
                    role=role,
                    parent_manifest_profile_sha256=parent_profile,
                    child_manifest_profile_sha256=profile,
                )
            )

        if node_key in expanded:
            continue
        expanded.add(node_key)

        if depth > max_depth:
            node.status = NodeStatus.SKIPPED_MAX_DEPTH
            continue

        # A profile-preserving read cannot claim the store's mutable default
        # manifest for a persisted child whose InputRef omitted its profile.
        # Keep that historical edge visible as unresolved instead of silently
        # substituting whichever profile happens to be the default today.
        if preserve_profiles and depth > 0 and profile is None:
            node.status = NodeStatus.MISSING_MANIFEST
            continue

        try:
            exists = bool(store.has(artifact_id)) if profile is None else True
        except Exception:
            node.status = NodeStatus.MISSING
            continue
        if not exists:
            node.status = NodeStatus.MISSING
            continue

        try:
            manifest = (
                resolve_manifest_by_profile(store, artifact_id, profile)
                if preserve_profiles and profile is not None
                else store.get_manifest(artifact_id)
            )
        except Exception:
            node.status = NodeStatus.MISSING_MANIFEST
            continue

        if root_ref is not None and depth == 0:
            mismatched_fields = []
            if root_ref.kind != manifest.kind:
                mismatched_fields.append("kind")
            if root_ref.media_type != manifest.media_type:
                mismatched_fields.append("media_type")
            if mismatched_fields:
                fields = ", ".join(mismatched_fields)
                raise ValueError(
                    f"root ArtifactRef does not match the resolved CAS manifest for {fields}"
                )

        node.kind = manifest.kind
        node.media_type = manifest.media_type
        node.byte_size = int(manifest.byte_size)
        node.manifest = manifest

        if verify_integrity:
            verification_ref = ArtifactRef(
                artifact_id=artifact_id,
                kind=manifest.kind,
                media_type=manifest.media_type,
                manifest_profile_sha256=profile,
            )
            verification = store.verify(verification_ref if preserve_profiles else artifact_id)
            if not verification.ok:
                node.status = NodeStatus.CORRUPTED
                continue

        node.status = NodeStatus.PRESENT
        for input_ref in manifest.inputs:
            input_profile = input_ref.manifest_profile_sha256 if preserve_profiles else None
            stack.append(
                (
                    input_ref.artifact_id,
                    input_profile,
                    artifact_id,
                    profile,
                    input_ref.role,
                    depth + 1,
                )
            )

    return graph


def _dependency_node_key(artifact_id_hex: str, profile: str | None) -> str:
    """Keep legacy ID-only keys while distinguishing explicitly selected views."""
    return artifact_id_hex if profile is None else f"{artifact_id_hex}@{profile}"


__all__ = [
    "DependencyEdge",
    "DependencyGraph",
    "DependencyNode",
    "NodeStatus",
    "resolve_dependency_graph",
]
