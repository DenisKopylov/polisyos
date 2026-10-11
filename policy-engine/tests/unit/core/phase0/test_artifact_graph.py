from __future__ import annotations

import pytest

from polisyos.core.artifacts.graph import NodeStatus, resolve_dependency_graph
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions


def _put_json(
    store: FileSystemCAS,
    payload: dict[str, object],
    *,
    kind: str,
    inputs: list[InputRef] | None = None,
):
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            inputs=inputs,
        ),
    )


def test_resolve_dependency_graph_traverses_inputs(store: FileSystemCAS) -> None:
    leaf = _put_json(store, {"leaf": True}, kind="test.leaf")
    mid = _put_json(
        store,
        {"mid": True},
        kind="test.mid",
        inputs=[InputRef(artifact_id=leaf.artifact_id, role="leaf")],
    )
    root = _put_json(
        store,
        {"root": True},
        kind="test.root",
        inputs=[InputRef(artifact_id=mid.artifact_id, role="mid")],
    )

    graph = resolve_dependency_graph(store, root.artifact_id)

    assert graph.total_artifacts == 3
    assert graph.is_complete
    assert graph.nodes[root.artifact_id.hex].status == NodeStatus.PRESENT
    assert graph.nodes[mid.artifact_id.hex].status == NodeStatus.PRESENT
    assert graph.nodes[leaf.artifact_id.hex].status == NodeStatus.PRESENT


def test_resolve_dependency_graph_reports_missing_dependency(store: FileSystemCAS) -> None:
    missing = ArtifactID.from_sha256_hex("f" * 64)
    root = _put_json(
        store,
        {"root": True},
        kind="test.root",
        inputs=[InputRef(artifact_id=missing, role="missing_input")],
    )

    graph = resolve_dependency_graph(store, root.artifact_id)
    missing_node = graph.nodes[missing.hex]

    assert missing_node.status == NodeStatus.MISSING
    assert not graph.is_complete


def test_resolve_dependency_graph_reports_corruption(store: FileSystemCAS) -> None:
    child = _put_json(store, {"child": 1}, kind="test.child")
    root = _put_json(
        store,
        {"root": 1},
        kind="test.root",
        inputs=[InputRef(artifact_id=child.artifact_id, role="child")],
    )
    blob_path, _ = store._paths(child.artifact_id)
    blob_path.write_bytes(b"corrupted")

    graph = resolve_dependency_graph(store, root.artifact_id)

    assert graph.nodes[child.artifact_id.hex].status == NodeStatus.CORRUPTED


def test_resolve_dependency_graph_respects_timeout_budget(store: FileSystemCAS) -> None:
    root = _put_json(store, {"root": True}, kind="test.root")

    graph = resolve_dependency_graph(
        store,
        root.artifact_id,
        timeout_seconds=0.0,
        batch_size=1,
    )

    assert graph.timed_out is True
    assert graph.nodes[root.artifact_id.hex].status == NodeStatus.SKIPPED_TIMEOUT
    assert graph.is_complete is False


@pytest.mark.parametrize(
    ("kind", "media_type"),
    [
        ("forged.kind", "application/json"),
        ("test.root", "text/plain"),
    ],
)
def test_resolve_dependency_graph_rejects_root_ref_metadata_not_in_manifest(
    store: FileSystemCAS,
    kind: str,
    media_type: str,
) -> None:
    root = _put_json(store, {"root": True}, kind="test.root")
    ref = ArtifactRef(
        artifact_id=root.artifact_id,
        kind=kind,
        media_type=media_type,
        manifest_profile_sha256=root.manifest_profile_sha256,
    )

    with pytest.raises(ValueError, match="root ArtifactRef does not match"):
        resolve_dependency_graph(store, ref)


def test_resolve_dependency_graph_accepts_root_ref_matching_manifest(store: FileSystemCAS) -> None:
    root = _put_json(store, {"root": True}, kind="test.root")
    manifest = store.get_manifest(root.artifact_id)
    ref = ArtifactRef(
        artifact_id=root.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
    )

    graph = resolve_dependency_graph(store, ref)

    assert graph.is_complete
    assert graph.nodes[root.artifact_id.hex].kind == manifest.kind
    assert graph.nodes[root.artifact_id.hex].media_type == manifest.media_type


def test_profiled_graph_does_not_default_an_unprofiled_child(store: FileSystemCAS) -> None:
    child = _put_json(store, {"child": 1}, kind="test.child.v1")
    child_sibling = store.put_json(
        {"child": 1},
        PutOptions(kind="test.child.v2", media_type="application/json"),
    )
    assert child.artifact_id == child_sibling.artifact_id
    assert child.manifest_profile_sha256 != child_sibling.manifest_profile_sha256

    root = _put_json(
        store,
        {"root": 1},
        kind="test.root",
        inputs=[InputRef(artifact_id=child.artifact_id, role="unprofiled_child")],
    )
    root_manifest = store.get_manifest(root.artifact_id)
    root_ref = ArtifactRef(
        artifact_id=root.artifact_id,
        kind=root_manifest.kind,
        media_type=root_manifest.media_type,
        manifest_profile_sha256=root.manifest_profile_sha256,
    )

    graph = resolve_dependency_graph(store, root_ref)
    child_node = graph.nodes[child.artifact_id.hex]

    assert child_node.status == NodeStatus.MISSING_MANIFEST
    assert child_node.manifest is None
    assert graph.is_complete is False
